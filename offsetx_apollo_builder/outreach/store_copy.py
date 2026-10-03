"""Copying a CRM between SQLite and PostgreSQL, whole and reconciled (`S-06.03.03`).

`offsetx-db import-crm` brings a local install's CRM file into the database
`OFFSETX_DATABASE_URL` names, once. Any other copy — the way back to SQLite
included — goes through the same `copy_crm`.

**Only into an empty CRM.** Merging two would have to pick a winner for every
row both hold, and that is the owner's call, not this code's.

**The source is read, never written** — not even upgraded. An older file's
missing columns are filled by the destination's defaults, which is exactly
what upgrading it would have written; a column the destination does not know
stops the copy rather than being dropped.

**All or nothing.** Every row goes in one transaction, parents before
children. A value the destination refuses — SQLite keeps text in a number
column, PostgreSQL will not — aborts the whole copy and names the table, so a
half-copied CRM never looks whole. The counts of every table are compared
afterwards.
"""

from __future__ import annotations

import functools
import json
import re
import sqlite3
import tempfile
import threading
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ..db import DatabaseError, describe_target, is_postgres_url, open_database
from ..db.hosted import HostedStorage, HostedStorageError
from .schema import CRM_TABLES, SCHEMA_SQL
from .store import GuardedConnection, OutreachStore

#: What was decided about a local CRM file, kept beside phase 1's decision.
CRM_DECISION = "crm_import"
IMPORT_CRM_COMMAND = "offsetx-db import-crm --yes"
SKIP_CRM_COMMAND = "offsetx-db import-crm --skip"

#: Rows per INSERT. One statement per row is a round trip each to a hosted
#: database; a few hundred values per statement stay far inside both
#: backends' limits on parameters.
_BATCH = 200


class CrmCopyError(RuntimeError):
    """Why a copy did not happen, as a sentence with the next step."""


@dataclass(frozen=True)
class CrmCopyReport:
    source: str
    destination: str
    tables: dict[str, tuple[int, int]]

    @property
    def ok(self) -> bool:
        return all(before == after for before, after in self.tables.values())

    def describe(self) -> str:
        lines = [f"{self.source} -> {self.destination}"]
        lines += [
            f"  {table} {before} -> {after}" + ("" if before == after else "   DOES NOT MATCH")
            for table, (before, after) in self.tables.items()
        ]
        return "\n".join(lines)


def _copy_order() -> list[str]:
    """Every CRM table, each after the tables it references (from the schema)."""
    bodies = dict(re.findall(r"^CREATE TABLE IF NOT EXISTS (\w+) \(\n(.*?)^\);", SCHEMA_SQL, re.M | re.S))
    needs = {
        table: {parent for parent in re.findall(r"\bREFERENCES (\w+)\b", body) if parent != table}
        for table, body in bodies.items()
    }
    ordered: list[str] = []
    while needs:
        ready = sorted(table for table, parents in needs.items() if parents <= set(ordered))
        if not ready:
            raise CrmCopyError(f"The CRM schema's references form a loop: {sorted(needs)}.")
        ordered += ready
        for table in ready:
            del needs[table]
    return ordered


class _Source:
    """Read-only access to a CRM, whichever backend holds it."""

    def __init__(self, target: Path | str) -> None:
        self.target = str(target)
        # Every read sees the CRM as it was at the first: read table by table
        # while the app writes, a contact added mid-copy could reference a
        # campaign already read past — a failed copy, or counts that differ.
        self._snapshot = ExitStack()
        if is_postgres_url(self.target):
            self._database = open_database(self.target)
            self._sqlite = None
            self._snapshot.enter_context(self._database.transaction())
            self._database.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            self._database.execute("SELECT 1")  # the snapshot is taken at the first read
            return
        path = Path(self.target)
        if not path.is_file():
            raise CrmCopyError(f"There is no CRM file at {path}; nothing was copied.")
        # Read-only by URI: opening through the store would switch an old file
        # to WAL and run its migrations — both writes to what is being copied.
        # Guarded like every connection kept on an object in this package
        # (`test_no_shared_connection_escapes_the_guard`), though only one
        # thread reads it: the rule has no exceptions to remember.
        self._sqlite = GuardedConnection(
            sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5),
            threading.RLock(),
        )
        self._sqlite.row_factory = sqlite3.Row
        self._database = None
        # A read transaction, pinned by its first read: WAL keeps this view
        # while the app goes on writing.
        self._sqlite.execute("BEGIN")
        self._sqlite.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()

    def columns(self, table: str) -> list[str]:
        if self._database is not None:
            rows = self._database.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = current_schema() AND table_name = ? ORDER BY ordinal_position",
                [table],
            ).fetchall()
            return [str(row["column_name"]) for row in rows]
        return [str(row["name"]) for row in self._sqlite.execute(f"PRAGMA table_info({table})")]

    def rows(self, table: str, columns: list[str]) -> Iterator[tuple[Any, ...]]:
        sql = f"SELECT {', '.join(columns)} FROM {table}"
        if self._database is not None:
            for row in self._database.execute(sql).fetchall():
                yield tuple(row[column] for column in columns)
            return
        cursor = self._sqlite.execute(sql)
        while batch := cursor.fetchmany(_BATCH):
            yield from (tuple(row) for row in batch)

    def counts(self) -> dict[str, int]:
        return {
            table: self._count(table) if self.columns(table) else 0
            for table in sorted(CRM_TABLES)
        }

    def _count(self, table: str) -> int:
        sql = f"SELECT COUNT(*) AS count FROM {table}"
        if self._database is not None:
            return int(self._database.execute(sql).fetchone()["count"])
        return int(self._sqlite.execute(sql).fetchone()["count"])

    def matching(self, table: str, column: str, values: frozenset[str]) -> int:
        """Rows of `table` whose `column` is one of `values` (SQLite only)."""
        if not values:
            return 0
        marks = ", ".join("?" for _ in values)
        row = self._sqlite.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE {column} IN ({marks})", sorted(values)
        ).fetchone()
        return int(row["count"])

    def close(self) -> None:
        try:
            self._snapshot.close()  # PostgreSQL: ends the read-only transaction
        finally:
            (self._database or self._sqlite).close()


def copy_crm(source: Path | str, destination: Path | str) -> CrmCopyReport:
    """Copy every CRM row from `source` into an empty CRM at `destination`."""
    if str(source) == str(destination):
        raise CrmCopyError("The source and the destination are the same CRM; nothing was copied.")
    reader = _Source(source)
    try:
        if not any(reader.columns(table) for table in CRM_TABLES):
            raise CrmCopyError(f"{describe_target(source)} holds no CRM tables; nothing was copied.")
        with OutreachStore(destination) as store:
            store.initialize()
            held = {table: rows for table, rows in store.table_counts().items() if rows}
            if held:
                raise CrmCopyError(
                    f"{describe_target(destination)} already holds a CRM ({_listed(held)}). Copying "
                    "into it would mix two; nothing was copied. Copy into an empty database."
                )
            try:
                with store.transaction(immediate=True) as connection:
                    for table in _copy_order():
                        _copy_table(reader, connection, table, set(_store_columns(store, table)))
                    if store.fts_enabled:
                        # SQLite's search index is the store's to fill; a copy
                        # of the rows alone leaves expert search empty.
                        connection.execute(
                            "INSERT INTO expert_chunks_fts (chunk_id, document_name, expert_name, content, tags)"
                            " SELECT id, document_name, expert_name, content, tags FROM expert_chunks"
                        )
            except CrmCopyError:
                raise
            except (store.integrity_error, DatabaseError, sqlite3.Error, ValueError) as exc:
                raise CrmCopyError(f"Nothing was copied: {exc}") from exc
            after = store.table_counts()
        before = reader.counts()
    finally:
        reader.close()
    return CrmCopyReport(
        source=describe_target(source),
        destination=describe_target(destination),
        tables={table: (before[table], after[table]) for table in sorted(CRM_TABLES)},
    )


def _store_columns(store: OutreachStore, table: str) -> list[str]:
    if store.database is not None:
        return sorted(store.database.columns(table))
    return [str(row["name"]) for row in store.connection.execute(f"PRAGMA table_info({table})")]


def _copy_table(reader: _Source, connection: Any, table: str, known: set[str]) -> None:
    columns = reader.columns(table)
    if not columns:
        return  # a file older than this table: nothing to bring
    unknown = [column for column in columns if column not in known]
    if unknown:
        raise CrmCopyError(
            f"The source's {table} has columns this release does not know ({', '.join(unknown)}); "
            "nothing was copied. Copy with the release that wrote it."
        )
    head = f"INSERT INTO {table} ({', '.join(columns)}) VALUES "
    one = "(" + ", ".join("?" for _ in columns) + ")"
    batch: list[tuple[Any, ...]] = []

    def flush() -> None:
        if not batch:
            return
        try:
            connection.execute(head + ", ".join(one for _ in batch), [value for row in batch for value in row])
        except Exception as exc:
            # Named here, where the table is known; the transaction above
            # undoes every table already copied.
            raise CrmCopyError(f"Nothing was copied: the {table} table could not be written ({exc}).") from exc
        batch.clear()

    for row in reader.rows(table, columns):
        batch.append(row)
        if len(batch) >= _BATCH:
            flush()
    flush()


def _listed(counts: dict[str, int]) -> str:
    return ", ".join(f"{rows} {table}" for table, rows in sorted(counts.items()))


# ── a local CRM file, when the database is switched on ───────────────────────

@functools.lru_cache(maxsize=1)
def _built_in() -> tuple[frozenset[str], frozenset[str]]:
    """The template ids and expert-note fingerprints every start writes.

    Asked of the real seeding — an engine over a scratch file — rather than
    written out again here, where the two copies would drift apart.
    """
    from .engine import OutreachEngine

    with tempfile.TemporaryDirectory() as scratch:
        engine = OutreachEngine(Path(scratch) / "built-in.db")
        try:
            rows = engine.store.connection
            templates = frozenset(str(row["id"]) for row in rows.execute("SELECT id FROM email_templates"))
            notes = frozenset(
                str(row["content_sha256"]) for row in rows.execute("SELECT content_sha256 FROM expert_chunks")
            )
        finally:
            engine.close()
    return templates, notes


def local_crm_rows(path: Path) -> int | None:
    """Rows the owner put in a local CRM file; None when there is no file.

    What every start writes does not count: the built-in templates and expert
    notes are written again into the database's CRM at its first start, and a
    built-in template edited locally is rewritten at every start anyway. A
    file that cannot be read counts as holding rows, so the owner decides
    rather than this code.
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        reader = _Source(path)
    except (CrmCopyError, sqlite3.Error):
        return 1
    try:
        counts = reader.counts()
        templates, notes = _built_in()
        if counts.get("email_templates") and reader.columns("email_templates"):
            counts["email_templates"] -= reader.matching("email_templates", "id", templates)
        if counts.get("expert_chunks") and reader.columns("expert_chunks"):
            counts["expert_chunks"] -= reader.matching("expert_chunks", "content_sha256", notes)
        return sum(counts.values())
    except sqlite3.Error:
        return 1
    finally:
        reader.close()


def _decided(hosted: HostedStorage) -> bool:
    return hosted.read(CRM_DECISION) is not None


def check_local_crm(hosted: HostedStorage, database_path: Path, crm: str) -> None:
    """Refuse to hide a local CRM file's rows once the CRM is in the database.

    As phase 1 does for keys and logins (D-210): an install with its own disk
    that switches `OFFSETX_DATABASE_URL` on would otherwise start on an empty
    CRM, every campaign and contact gone from the screens without a word.
    """
    if not is_postgres_url(crm) and Path(crm).resolve() == Path(database_path).resolve():
        return  # the CRM is this very file
    rows = local_crm_rows(database_path)
    if rows and not _decided(hosted):
        raise HostedStorageError(
            f"The CRM file {database_path} still holds {rows} rows from before "
            "OFFSETX_DATABASE_URL was set, and the database has not been told what to do "
            f"with them. Copy them in with `{IMPORT_CRM_COMMAND}`, or start on the database's "
            f"CRM with `{SKIP_CRM_COMMAND}`. The file stays where it is either way."
        )


def import_crm(hosted: HostedStorage, database_path: Path, crm: str) -> CrmCopyReport:
    """Copy a local CRM file into the database's CRM, once."""
    if _decided(hosted):
        raise HostedStorageError(
            "The database was already told what to do with a CRM file; nothing was changed."
        )
    report = copy_crm(database_path, crm)
    # After the copy, not around it: the copy takes its own transaction, and on
    # SQLite two at once on one file would wait on each other.
    with hosted.exclusive():
        hosted.write(CRM_DECISION, json.dumps({"imported": str(database_path), "tables": report.tables}))
    return report


def skip_crm(hosted: HostedStorage, database_path: Path) -> int:
    """Start on the database's CRM; the file stays, unread. Returns its rows."""
    rows = local_crm_rows(database_path) or 0
    with hosted.exclusive():
        if _decided(hosted):
            raise HostedStorageError(
                "The database was already told what to do with a CRM file; nothing was changed."
            )
        hosted.write(CRM_DECISION, json.dumps({"skipped": str(database_path), "rows": rows}))
    return rows
