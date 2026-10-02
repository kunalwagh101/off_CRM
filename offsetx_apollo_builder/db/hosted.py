"""The hosted database's own part: named documents, and the key that opens the
secret ones (`S-06.03.02`).

With `OFFSETX_DATABASE_URL` set, what a person types into the app — provider
keys, each workspace's AI settings, limits and trust — and the counters behind
those limits live here instead of in the data folder a free-plan deploy wipes.
Each is one named document in the shape its store already kept as a file, so a
store changes where it reads and writes, not what it does.

`OFFSETX_SECRETS_KEY`, which encrypts the provider keys, is never written
anywhere: the database holds ciphertext and a check value, the environment
holds the key. A copy of the database — a dump, a host's own backup — opens
nothing on its own. Any PostgreSQL 13 or newer will do (`DD-70`); a path, as
in the tests, is a SQLite file through the same seam.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

from .connection import DATABASE_URL_ENV, Database, describe_target, is_postgres_url, open_database
from .schema import ensure_schema

SECRETS_KEY_ENV = "OFFSETX_SECRETS_KEY"
NEW_KEY_COMMAND = "offsetx-db new-secrets-key"
FORGET_COMMAND = "offsetx-db forget-provider-keys --yes"

#: The documents, by name. Each store owns its own.
SETTINGS = "ai_workspaces"
PROVIDER_KEYS = "ai_provider_keys"
QUOTA = "ai_quota"
KEY_CHECK = "secrets_key_check"
#: What the owner decided about a data folder that held these stores before
#: the database did: imported, or skipped (D-210).
LOCAL_IMPORT = "local_import"

#: Where a local install keeps what this database takes over.
LOCAL_FILES = ("ai_workspaces.json", "ai_provider_keys.enc", "ai_quota.json", "workspace_auth.db")
IMPORT_COMMAND = "offsetx-db import-local --yes"
SKIP_COMMAND = "offsetx-db import-local --skip"

_CHECK_PLAINTEXT = b"off_CRM: the key the provider keys were stored with"

#: PostgreSQL's advisory lock for writing documents. Every writer of every
#: instance takes it, so one read-change-write is never interleaved with
#: another — across processes and instances, as well as threads.
_WRITE_LOCK = 7_103_206_302


class HostedStorageError(ValueError):
    """The hosted database cannot be used as configured. The message says what
    to do, and never repeats a secret."""


def secrets_fernet(secrets_key: str) -> Fernet:
    """The cipher for provider keys, or a refusal that says how to get a key."""
    try:
        return Fernet(secrets_key.strip().encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        # `from None`: the cause would quote the value back.
        raise HostedStorageError(
            f"{SECRETS_KEY_ENV} is not a key: it must be the 44 characters that "
            f"`{NEW_KEY_COMMAND}` prints. Run it once, set {SECRETS_KEY_ENV} to what "
            "it prints, and keep a copy somewhere safe — without it the stored provider "
            "keys cannot be read."
        ) from None


def validate_pair(database_url: str, secrets_key: str) -> None:
    """The hosted database and the key that opens its provider keys come as a
    pair; refuse half of one, and a key that is not a key, before any use."""
    key = secrets_key.strip()
    if database_url and not (is_postgres_url(database_url) or Path(database_url).is_absolute()):
        # Never repeated back: a libpq key/value string or a quoted URL carries
        # the password, and it used to become the name of a SQLite file in the
        # working directory, on the disk a deploy wipes (D-206).
        raise HostedStorageError(
            f"{DATABASE_URL_ENV} must be a PostgreSQL URL — postgresql://user:password@host/dbname "
            "— copied exactly as the database host shows it, without quotes or spaces. What is "
            "set is not one, so nothing was opened and nothing was written. (On a machine with "
            "its own disk, the absolute path of a SQLite file also works.)"
        )
    if database_url and not key:
        raise HostedStorageError(
            f"{DATABASE_URL_ENV} is set, so provider keys are kept in that database, "
            f"encrypted with {SECRETS_KEY_ENV} — which is not set. Run `{NEW_KEY_COMMAND}` "
            f"once, set {SECRETS_KEY_ENV} to what it prints, and keep a copy somewhere safe."
        )
    if key and not database_url:
        raise HostedStorageError(
            f"{SECRETS_KEY_ENV} is set but {DATABASE_URL_ENV} is not. The key opens provider "
            "keys kept in a hosted database; a local install keeps its own key file in the "
            f"data folder. Set {DATABASE_URL_ENV} too, or unset {SECRETS_KEY_ENV}."
        )
    if key:
        secrets_fernet(key)


def _create_documents(database: Database) -> None:
    database.execute(
        "CREATE TABLE offcrm_documents ("
        " name TEXT PRIMARY KEY,"
        " body TEXT NOT NULL,"
        " updated_at TEXT NOT NULL)"
    )


#: Oldest first; a step's position is its version (`db/schema.py`).
DOCUMENT_STEPS = (_create_documents,)


def local_leftovers(data_dir: Path) -> list[str]:
    """The files of a local install that hold what the database now keeps.

    A login file with no logins is not counted: every local start makes one.
    One that cannot be read is, so the owner decides rather than this code.
    """
    found = []
    for name in LOCAL_FILES:
        path = Path(data_dir) / name
        if not path.is_file():
            continue
        if name == "workspace_auth.db":
            try:
                reader = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
                try:
                    if reader.execute("SELECT 1 FROM workspace_users LIMIT 1").fetchone() is None:
                        continue
                finally:
                    reader.close()
            except sqlite3.Error:
                pass
        found.append(name)
    return found


class HostedStorage:
    """Named documents in the hosted database, and the provider keys' cipher.

    The connection is opened on first use and again after `close()`, like the
    egress log's, so closing every service for a restore cannot strand it.
    """

    def __init__(self, target: str, secrets_key: str | None) -> None:
        self.target = str(target)
        #: None only for `forget_provider_keys`, the way back from a lost key.
        self.fernet = secrets_fernet(secrets_key) if secrets_key is not None else None
        self._lock = threading.RLock()
        self._connection: Database | None = None

    @classmethod
    def configured(cls, secrets_key: str) -> "HostedStorage | None":
        """The hosted storage `OFFSETX_DATABASE_URL` names, or None for a local
        install; half a pair is refused with the next step."""
        target = os.getenv(DATABASE_URL_ENV, "").strip()
        validate_pair(target, secrets_key)
        return cls(target, secrets_key) if target else None

    def describe(self) -> str:
        return describe_target(self.target)

    @property
    def connection(self) -> Database:
        with self._lock:
            if self._connection is None:
                database = open_database(self.target)
                try:
                    ensure_schema(database, "documents", DOCUMENT_STEPS)
                except BaseException:
                    database.close()
                    raise
                self._connection = database
            return self._connection

    def read(self, name: str) -> str | None:
        row = self.connection.execute(
            "SELECT body FROM offcrm_documents WHERE name = ?", [name]
        ).fetchone()
        return None if row is None else str(row["body"])

    def write(self, name: str, body: str) -> None:
        self.connection.execute(
            "INSERT INTO offcrm_documents(name, body, updated_at) VALUES(?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at",
            [name, body, datetime.now(timezone.utc).isoformat()],
        )

    def delete(self, name: str) -> None:
        self.connection.execute("DELETE FROM offcrm_documents WHERE name = ?", [name])

    @contextmanager
    def exclusive(self) -> Iterator["HostedStorage"]:
        """One writer at a time, across threads, processes and instances.

        Reads inside see every write that finished before; the changes inside
        commit together or not at all.
        """
        with self._lock:
            database = self.connection
            with database.transaction():
                if database.name == "postgres":
                    database.execute("SELECT pg_advisory_xact_lock(?)", [_WRITE_LOCK])
                yield self

    def probe(self) -> None:
        """For readiness: the database answers a query."""
        self.connection.execute("SELECT 1").fetchone()

    def _wrong_key(self) -> HostedStorageError:
        return HostedStorageError(
            f"{SECRETS_KEY_ENV} does not open the provider keys stored in {self.describe()}: "
            "it is not the key they were saved with. Set it to the key this install was set "
            "up with. If that key is lost, nobody can read the stored keys: run "
            f"`{FORGET_COMMAND}` to clear them, start with the new key, and paste each "
            "provider key in Connectors again."
        )

    def check_secrets_key(self) -> None:
        """Refuse a key that cannot open what is stored, before anything is served.

        A check value is written with the first key, so a wrong key is caught
        even before any provider key exists. Without it a second key would be
        accepted while nothing was stored, and every key saved under it would
        be unreadable to the first.
        """
        with self.exclusive():
            check = self.read(KEY_CHECK)
            if check is not None:
                if self.open(check) != _CHECK_PLAINTEXT:
                    raise self._wrong_key()
                return
            stored = self.read(PROVIDER_KEYS)
            if stored is not None:
                self.open(stored)
            if self.fernet is None:
                raise self._wrong_key()
            self.write(KEY_CHECK, self.fernet.encrypt(_CHECK_PLAINTEXT).decode("ascii"))

    def open(self, token: str) -> bytes:
        if self.fernet is None:
            raise self._wrong_key()
        try:
            return self.fernet.decrypt(token.encode("ascii"))
        except (InvalidToken, UnicodeEncodeError):
            raise self._wrong_key() from None

    def check_local_folder(self, data_dir: Path) -> None:
        """Refuse to hide a data folder's keys, settings and logins (D-210).

        An install with a real disk that switches the database on keeps those
        files, and nothing reads them any more: colleagues could not sign in,
        and keys and trust decisions vanished from every screen without a word.
        The owner says once what happens to them.
        """
        found = local_leftovers(data_dir)
        if found and self.read(LOCAL_IMPORT) is None:
            raise HostedStorageError(
                f"This data folder still holds {', '.join(found)} from before {DATABASE_URL_ENV} "
                "was set, and the database has not been told what to do with them. Copy them in "
                f"with `{IMPORT_COMMAND}`, or keep the database as it is with `{SKIP_COMMAND}`. "
                "The files stay where they are either way."
            )

    def record_local_decision(self, decision: dict) -> None:
        """Write what was decided about the data folder; the caller holds `exclusive`."""
        self.write(LOCAL_IMPORT, json.dumps(
            {**decision, "at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False))

    def forget_provider_keys(self) -> None:
        """Clear the stored keys and the check: the way back from a lost key.
        Every workspace pastes its keys again; settings, limits and trust stay."""
        with self.exclusive():
            self.delete(PROVIDER_KEYS)
            self.delete(KEY_CHECK)

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
