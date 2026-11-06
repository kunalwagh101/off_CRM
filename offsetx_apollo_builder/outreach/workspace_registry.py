"""Leased native CRM books; activation never guesses legacy ownership.

Runtime wiring and manifest cutover are separate callers of this component.
The control database owns routing; a ready book is never silently recreated.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator

from ..db import DatabaseError, is_postgres_url, open_database
from ..db.hosted import HostedStorage
from ..db.schema import ensure_schema
from .engine import OutreachEngine
from .schema import CRM_TABLES, SCHEMA_SQL, SCHEMA_VERSION
from .store import names_a_url
from .workspace_lock import WorkspaceLock

_ROUTING_LOCK = 7_103_206_309
_IDENTITY_LOCK = 7_103_206_310
_WORKSPACE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_TABLE = 'crm_workspace_routing'
_IDENTITY = 'crm_workspace_identity'


class CrmRoutingError(DatabaseError):
    """A content-free routing refusal; ordinary requests must fail closed."""


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _uuid(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
        if not parsed.int:
            raise ValueError
        return str(parsed)
    except (ValueError, TypeError, AttributeError):
        raise CrmRoutingError('Set a stable installation UUID before opening workspace storage') from None


def _key(install: str, generation: str, workspace: str) -> str:
    return 'crm_ws_' + hashlib.sha256((install+'|'+generation+'|'+workspace).encode()).hexdigest()[:32]


@lru_cache(maxsize=1)
def _columns():
    source = sqlite3.connect(':memory:')
    try:
        source.executescript(SCHEMA_SQL)
        return {table: [(row[1], row[2]) for row in source.execute(f'PRAGMA table_info({table})')]
                for table in CRM_TABLES}
    finally:
        source.close()


@dataclass(frozen=True)
class CrmLocation:
    database: str = field(repr=False)
    namespace: str | None
    workspace: str
    generation: str
    install: str
    ready: bool


@dataclass
class _Cached:
    engine: OutreachEngine
    active: int = 0
    touched: float = 0.0
    generation: str = ""
    file_identity: tuple[int, int] | None = None


class _Catalogue:
    def __init__(self, target: str, expected_install: str | None):
        self.target = target
        self.expected_install = _uuid(expected_install) if expected_install else None
        if not is_postgres_url(target):
            path = Path(target).resolve()
            if not path.is_file() and Path(str(path)+'.workspaces').exists():
                raise CrmRoutingError('Workspace control storage is missing; restore its verified backup')
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os, 'O_NOFOLLOW', 0), 0o600)
                os.close(descriptor)
            except FileExistsError:
                pass
        self.database = open_database(target)
        try:
            self.schema = None
            self.path = None if self.database.name == 'postgres' else Path(target).resolve()
            self.file_identity = None
            if self.path is not None:
                state = self.path.stat()
                self.file_identity = (state.st_dev, state.st_ino)
            if self.database.name == 'postgres':
                row = self.database.execute('SELECT current_schema() AS name').fetchone()
                if not row or not row['name']:
                    raise CrmRoutingError('The installation control schema is unavailable')
                self.schema = str(row['name'])
                # A default search_path can resolve legacy tables in public
                # while putting new control tables in a different schema.
                # Never classify that split topology as an empty install.
                for table in (*CRM_TABLES, _TABLE, 'offcrm_schema'):
                    visible = self.database.execute(
                        'SELECT n.nspname FROM pg_catalog.pg_class c '
                        'JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace '
                        'WHERE c.oid=pg_catalog.to_regclass(?)', [table]).fetchone()
                    if visible and visible['nspname'] != self.schema:
                        raise CrmRoutingError('Review split control and legacy schemas before workspace activation')
            ensure_schema(self.database, 'crm_workspace_routing', [
                lambda connection: connection.execute(
                    f'CREATE TABLE IF NOT EXISTS {self.qual(_TABLE)} '
                    '(id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)')
            ])
            with self._write():
                receipt = self.read()
                if receipt is None:
                    if self.database.name == 'sqlite':
                        existing_books = Path(str(Path(target).resolve())+'.workspaces').exists()
                    else:
                        existing_books = self.database.execute(
                            "SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname ~ '^crm_ws_[a-f0-9]{32}$' LIMIT 1").fetchone() is not None
                    if existing_books:
                        raise CrmRoutingError('Workspace routing is missing beside existing books; restore its verified backup')
                    self._require_empty_legacy()
                    receipt = {'version': 1, 'install_id': self.expected_install or str(uuid.uuid4()),
                               'generation': uuid.uuid4().hex, 'backend': self.database.name,
                               'origin': 'empty', 'namespaces': {}}
                    self._freeze_empty_legacy()
                    self.save(receipt)
                self.validate(receipt)
        except BaseException:
            self.database.close()
            raise

    def qual(self, table: str) -> str:
        return (_quote(self.schema)+'.' if self.schema else '')+_quote(table)

    @contextmanager
    def _write(self):
        with self.database.transaction():
            if self.database.name == 'postgres':
                self.database.execute("SET LOCAL lock_timeout = '5s'")
                self.database.execute('SELECT pg_advisory_xact_lock(?)', [_ROUTING_LOCK])
            yield

    def read(self):
        if self.path is not None:
            try:
                state = self.path.stat()
                if self.path.is_symlink() or (state.st_dev, state.st_ino) != self.file_identity:
                    raise OSError('changed control file')
            except OSError:
                raise CrmRoutingError('Workspace control storage changed; reopen its verified restore') from None
        if not self.database.columns(_TABLE):
            raise CrmRoutingError('Workspace routing metadata is missing; restore its verified backup')
        row = self.database.execute(f'SELECT document FROM {self.qual(_TABLE)} WHERE id=1').fetchone()
        if row is None:
            return None
        try:
            return self.validate(json.loads(row['document']))
        except (ValueError, TypeError, KeyError):
            raise CrmRoutingError('Workspace routing metadata is invalid; restore its verified backup') from None

    def validate(self, receipt):
        required = {'version', 'install_id', 'generation', 'backend', 'origin', 'namespaces'}
        if not isinstance(receipt, dict) or set(receipt) != required or type(receipt['version']) is not int or receipt['version'] != 1:
            raise CrmRoutingError('Workspace routing metadata is invalid; restore its verified backup')
        install = _uuid(receipt['install_id'])
        if install != receipt['install_id']:
            raise CrmRoutingError('Workspace installation identity is not canonical')
        if self.expected_install and install != self.expected_install:
            raise CrmRoutingError('Workspace storage belongs to another installation')
        generation = receipt['generation']
        if not isinstance(generation, str) or uuid.UUID(generation).hex != generation:
            raise CrmRoutingError('Workspace routing generation is invalid')
        if receipt['backend'] != self.database.name or receipt['origin'] != 'empty' or not isinstance(receipt['namespaces'], dict):
            raise CrmRoutingError('Workspace routing topology is invalid')
        for workspace, entry in receipt['namespaces'].items():
            if not isinstance(workspace, str) or not _WORKSPACE.fullmatch(workspace):
                raise CrmRoutingError('Workspace routing ownership is invalid')
            if not isinstance(entry, dict) or set(entry) != {'key', 'status'} or entry['status'] not in {'preparing', 'ready'}:
                raise CrmRoutingError('Workspace routing state is invalid')
            if entry['key'] != _key(install, generation, workspace):
                raise CrmRoutingError('Workspace routing ownership does not reconcile')
        return receipt

    def save(self, receipt):
        self.validate(receipt)
        self.database.execute(f'INSERT INTO {self.qual(_TABLE)}(id,document) VALUES(1,?) '
                              'ON CONFLICT(id) DO UPDATE SET document=excluded.document',
                              [json.dumps(receipt, sort_keys=True)])

    def _relations(self):
        if self.database.name == 'sqlite':
            return {str(row['name']): str(row['type']) for row in self.database.execute(
                "SELECT name,type FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
        return {str(row['relname']): ('table' if row['relkind'] in ('r', 'p') else 'view')
                for row in self.database.execute(
                    'SELECT c.relname,c.relkind FROM pg_catalog.pg_class c '
                    'JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace '
                    'WHERE n.nspname=? AND c.relkind IN (\'r\',\'p\',\'v\',\'m\')', [self.schema]).fetchall()}

    def _require_empty_legacy(self):
        relations = self._relations()
        for table in CRM_TABLES:
            if table not in relations:
                continue
            if relations[table] != 'table':
                raise CrmRoutingError('Legacy routing needs an explicit reviewed ownership manifest')
            if self.database.columns(table) != {name for name, _ in _columns()[table]}:
                raise CrmRoutingError('Legacy schema needs an explicit reviewed ownership manifest')
            if self.database.execute(f'SELECT count(*) AS n FROM {self.qual(table)}').fetchone()['n']:
                raise CrmRoutingError('Existing CRM records require an explicit ownership manifest; nothing was assigned')
        if self.database.name == 'sqlite' and 'expert_chunks_fts' in relations:
            if self.database.execute('SELECT count(*) AS n FROM expert_chunks_fts').fetchone()['n']:
                raise CrmRoutingError('Legacy reference data needs an explicit reviewed ownership manifest')
        if self.database.name == 'sqlite':
            for table, kind in relations.items():
                if kind != 'table' or table in CRM_TABLES:
                    continue
                if any(row['table'] in CRM_TABLES for row in self.database.execute(f'PRAGMA foreign_key_list({_quote(table)})').fetchall()):
                    raise CrmRoutingError('Review external CRM dependencies before workspace activation')

    def _freeze_empty_legacy(self):
        # This caller has proved the source empty. Full legacy cutover must
        # archive and reconcile data before using an equivalent guarded switch.
        relations = self._relations()
        if self.database.name == 'postgres':
            present = [self.qual(table) for table in CRM_TABLES if relations.get(table) == 'table']
            if present:
                self.database.execute('LOCK TABLE '+','.join(present)+' IN ACCESS EXCLUSIVE MODE')
                self._require_empty_legacy()
        for table in reversed(CRM_TABLES):
            if relations.get(table) == 'table':
                self.database.execute(f'DROP TABLE {self.qual(table)}')
        if self.database.name == 'sqlite':
            if 'expert_chunks_fts' in relations:
                self.database.execute('DROP TABLE expert_chunks_fts')
            for table, columns in _columns().items():
                selection = ','.join('crm_legacy_closed() AS '+_quote(name) for name, _ in columns)
                self.database.execute(f'CREATE VIEW {self.qual(table)} AS SELECT {selection}')
            self.database.execute(f'PRAGMA user_version={SCHEMA_VERSION+1}')
        else:
            function = self.qual('crm_legacy_closed')
            self.database.execute(f'''CREATE FUNCTION {function}() RETURNS text LANGUAGE plpgsql VOLATILE AS
                $$ BEGIN RAISE EXCEPTION 'Workspace routing is active; restart with a workspace-aware application'; END $$''')
            for table, columns in _columns().items():
                selection = ','.join(f'CAST({function}() AS {kind}) AS {_quote(name)}' for name, kind in columns)
                self.database.execute(f'CREATE VIEW {self.qual(table)} AS SELECT {selection}')
            self.database.execute('UPDATE offcrm_schema SET version=version+1 WHERE component=\'crm\'')

    def prepare(self, workspace: str) -> CrmLocation:
        with self._write():
            receipt = self.read()
            if receipt is None:
                raise CrmRoutingError('Workspace routing disappeared; restore its verified backup')
            key = _key(receipt['install_id'], receipt['generation'], workspace)
            entry = receipt['namespaces'].get(workspace)
            ready = bool(entry and entry['status'] == 'ready')
            if self.database.name == 'postgres':
                exists = self.database.execute('SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname=?', [key]).fetchone()
                if ready and exists is None:
                    raise CrmRoutingError('Workspace storage is missing; restore its verified backup')
                if exists is None:
                    self.database.execute(f'CREATE SCHEMA {_quote(key)}')
                target, namespace = self.target, key
            else:
                root = Path(self.target).resolve()
                directory = Path(str(root)+'.workspaces')/receipt['generation']
                if directory.parent.is_symlink() or directory.is_symlink():
                    raise CrmRoutingError('Workspace storage directory is invalid; restore verified storage')
                if ready and not (directory/(key+'.db')).is_file():
                    raise CrmRoutingError('Workspace storage is missing; restore its verified backup')
                directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                directory.mkdir(exist_ok=True, mode=0o700)
                target, namespace = str(directory/(key+'.db')), None
                if Path(target).is_symlink():
                    raise CrmRoutingError('Workspace storage is invalid; restore its verified backup')
                if not ready:
                    try:
                        descriptor = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os, 'O_NOFOLLOW', 0), 0o600)
                        os.close(descriptor)
                    except FileExistsError:
                        pass
            if entry is None:
                receipt['namespaces'][workspace] = {'key': key, 'status': 'preparing'}
                self.save(receipt)
            return CrmLocation(target, namespace, workspace, receipt['generation'], receipt['install_id'], ready)

    def ready(self, location: CrmLocation):
        with self._write():
            receipt = self.read()
            if receipt is None or receipt['generation'] != location.generation:
                raise CrmRoutingError('Workspace generation changed; restart the application')
            receipt['namespaces'][location.workspace]['status'] = 'ready'
            self.save(receipt)

    def close(self):
        self.database.close()


def _verify_identity(location: CrmLocation):
    try:
        with open_database(location.database, namespace=location.namespace) as database:
            with database.transaction():
                if database.name == 'postgres':
                    database.execute("SET LOCAL lock_timeout='5s'")
                    database.execute('SELECT pg_advisory_xact_lock(?)', [_IDENTITY_LOCK])
                if not database.columns(_IDENTITY):
                    if location.ready:
                        raise CrmRoutingError('Workspace ownership metadata is missing; restore its verified backup')
                    if database.name == 'sqlite':
                        tables = database.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                    else:
                        tables = database.execute('SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=current_schema()').fetchall()
                    if tables:
                        raise CrmRoutingError('Unrecognised workspace data cannot be adopted automatically')
                    database.execute(f'CREATE TABLE {_IDENTITY}(id INTEGER PRIMARY KEY CHECK(id=1), '
                                     'schema_version INTEGER NOT NULL CHECK(schema_version=1), workspace_id TEXT NOT NULL, generation TEXT NOT NULL, install_id TEXT NOT NULL)')
                    database.execute(f'INSERT INTO {_IDENTITY} VALUES(1,1,?,?,?)',
                                     [location.workspace, location.generation, location.install])
                row = database.execute(f'SELECT * FROM {_IDENTITY} WHERE id=1').fetchone()
                if row is None or row['schema_version'] != 1 or (row['workspace_id'], row['generation'], row['install_id']) != (location.workspace, location.generation, location.install):
                    raise CrmRoutingError('Workspace ownership does not match; restore its verified backup')
    except CrmRoutingError:
        raise
    except (DatabaseError, sqlite3.DatabaseError, OSError, KeyError, TypeError, ValueError):
        raise CrmRoutingError('Workspace storage is unavailable; restore its verified backup') from None


class WorkspaceCrmRegistry:
    def __init__(self, *, root_target: str, data_dir: Path | str,
                 known_workspaces: Callable[[], Any], max_cached: int = 8,
                 install_id: str | None = None, hosted_storage: HostedStorage | None = None,
                 engine_factory: Callable[[CrmLocation], OutreachEngine] | None = None):
        if type(max_cached) is not int or not 1 <= max_cached <= 32:
            raise CrmRoutingError('Workspace connection cache must contain between1 and32 books')
        if not is_postgres_url(root_target) and names_a_url(root_target):
            raise CrmRoutingError('Workspace storage requires a SQLite file or PostgreSQL database')
        self.data_dir = Path(data_dir).resolve()
        if not is_postgres_url(root_target):
            if not str(root_target).strip() or str(root_target) == ':memory:':
                raise CrmRoutingError('Workspace storage requires a durable SQLite file')
            path = Path(root_target).expanduser()
            if path.is_symlink():
                raise CrmRoutingError('Workspace control storage cannot be a symbolic link')
            path = path.resolve()
            if not path.is_relative_to(self.data_dir):
                raise CrmRoutingError('Keep workspace CRM storage inside the data directory for complete recovery')
            root_target = str(path)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.known_workspaces = known_workspaces
        self.max_cached = max_cached
        self.factory = engine_factory
        self._lock = threading.RLock()
        self._cache: dict[str, _Cached] = {}
        self._closed = False
        expected = install_id or os.getenv('OFFSETX_INSTALL_ID', '') or None
        self._owned_hosted = None
        if is_postgres_url(root_target) and hosted_storage is None:
            self._owned_hosted = hosted_storage = HostedStorage(root_target, os.getenv('OFFSETX_SECRETS_KEY', ''))
        try:
            if hosted_storage is not None:
                if str(hosted_storage.target) != str(root_target):
                    raise CrmRoutingError('Workspace routing must use the configured installation database')
                hosted_storage.claim_install(expected or '')
            self.catalogue = _Catalogue(str(root_target), expected)
            self._generation = self.catalogue.read()['generation']
        except BaseException:
            if self._owned_hosted is not None:
                self._owned_hosted.close()
            raise

    @contextmanager
    def lease(self, workspace: str) -> Iterator[OutreachEngine]:
        with self._lock:
            if self._closed:
                raise CrmRoutingError('This workspace registry is closed; reopen the runtime')
            if not isinstance(workspace, str) or not _WORKSPACE.fullmatch(workspace) or workspace not in self.known_workspaces():
                raise CrmRoutingError('Select an authenticated workspace before opening CRM data')
        with WorkspaceLock(self.data_dir):
            with self._lock:
                if self._closed:
                    raise CrmRoutingError('This workspace registry is closed; reopen the runtime')
                receipt = self.catalogue.read()
                if receipt is None:
                    raise CrmRoutingError('Workspace routing is missing; restore its verified backup')
                if receipt['generation'] != self._generation:
                    if any(entry.active for entry in self._cache.values()):
                        raise CrmRoutingError('Finish active workspace work before changing storage generation')
                    for entry in self._cache.values():
                        entry.engine.close()
                    self._cache.clear()
                    self._generation = receipt['generation']
                cached = self._cache.get(workspace)
                if cached is not None:
                    binding = receipt['namespaces'].get(workspace)
                    if not binding or binding['status'] != 'ready':
                        raise CrmRoutingError('Workspace routing changed; restore verified routing metadata')
                    if cached.file_identity is not None:
                        path = cached.engine.store.path
                        if path is None or path.is_symlink() or not path.is_file():
                            raise CrmRoutingError('Workspace storage is missing; restore its verified backup')
                        state = path.stat()
                        if (state.st_dev, state.st_ino) != cached.file_identity:
                            raise CrmRoutingError('Workspace storage was replaced; reopen the verified runtime')
                    _verify_identity(CrmLocation(cached.engine.store.target, cached.engine.store.namespace,
                        workspace, receipt['generation'], receipt['install_id'], True))
                if cached is None:
                    if len(self._cache) >= self.max_cached:
                        idle = [(key, entry) for key, entry in self._cache.items() if not entry.active]
                        if not idle:
                            raise CrmRoutingError('Workspace connections are busy; retry when active work finishes')
                        key, old = min(idle, key=lambda pair: pair[1].touched)
                        old.engine.close()
                        del self._cache[key]
                    location = self.catalogue.prepare(workspace)
                    _verify_identity(location)
                    engine = self.factory(location) if self.factory else OutreachEngine(
                        location.database, workspace_id=workspace, storage_namespace=location.namespace)
                    if engine.workspace_id != workspace or engine.store.namespace != location.namespace or engine.store.target != location.database:
                        engine.close()
                        raise CrmRoutingError('Workspace engine binding is invalid; restart with verified configuration')
                    try:
                        self.catalogue.ready(location)
                    except BaseException:
                        engine.close()
                        raise
                    identity = None
                    if engine.store.path is not None:
                        state = engine.store.path.stat()
                        identity = (state.st_dev, state.st_ino)
                    cached = self._cache[workspace] = _Cached(engine, generation=location.generation, file_identity=identity)
                cached.active += 1
            try:
                yield cached.engine
            finally:
                with self._lock:
                    cached.active -= 1
                    cached.touched = time.monotonic()

    def close(self):
        with self._lock:
            if self._closed:
                return
            if any(entry.active for entry in self._cache.values()):
                raise CrmRoutingError('Finish active workspace operations before closing or restoring storage')
            self._closed = True
            resources = [entry.engine for entry in self._cache.values()] + [self.catalogue]
            if self._owned_hosted is not None:
                resources.append(self._owned_hosted)
            self._cache.clear()
            failed = False
            for resource in resources:
                try:
                    resource.close()
                except Exception:
                    failed = True
            if failed:
                raise CrmRoutingError('Unable to close every workspace resource; restart the runtime') from None
