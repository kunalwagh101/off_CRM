"""Opening a database, whichever backend is behind it.

The object returned by :func:`open_database` answers ``execute``,
``executescript``, ``transaction`` and ``close``, and hands back rows that
support ``row["column"]`` and ``dict(row)`` — the surface the stores already
use against ``sqlite3.Connection``. Swapping the backend is then a change of
what a store is *given*, not a rewrite of what it does.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .translate import translate_params

#: A single place to point everything at Postgres. A store may still be handed
#: its own target explicitly, which wins.
DATABASE_URL_ENV = "OFFSETX_DATABASE_URL"

_POSTGRES_SCHEMES = ("postgres://", "postgresql://", "psql://")


class DatabaseError(RuntimeError):
    """Connection or configuration problem, with the fix in the message."""


class DatabaseUnavailable(DatabaseError):
    """The database did not answer — down, unreachable, or it dropped the
    connection mid-statement. Whether a statement that failed this way ran is
    unknown, so nothing here sends it again."""


def is_postgres_url(target: object) -> bool:
    """Whether this target names a Postgres server rather than a file.

    Anything that is not a Postgres URL is a path. That default matters: a typo
    in a DSN should not silently create an empty SQLite file and look like it
    worked, so the schemes are matched explicitly and everything else is a
    path — which is what off_CRM has always been.
    """
    if isinstance(target, Path):
        return False
    text = str(target or "").strip().lower()
    return text.startswith(_POSTGRES_SCHEMES)


def resolve_target(explicit: object = None, *, default: object = None) -> str:
    """Decide what to open, in priority order.

    An explicit argument beats the environment, and the environment beats the
    caller's default path. That ordering lets a deployment set one variable
    without every call site learning about it, while a test can still point a
    store at a scratch file and be sure the environment cannot reach in.
    """
    if explicit is not None and str(explicit).strip():
        return str(explicit)
    from_env = os.getenv(DATABASE_URL_ENV, "").strip()
    if from_env:
        return from_env
    if default is not None:
        return str(default)
    raise DatabaseError(
        "No database target. Pass one, or set "
        f"{DATABASE_URL_ENV} to a postgresql:// URL."
    )


def describe_target(target: object) -> str:
    """A one-line description safe to print — the password is never shown."""
    if not is_postgres_url(target):
        return f"sqlite at {target}"
    text = str(target)
    if "@" in text:
        scheme, _, rest = text.partition("://")
        credentials, _, host = rest.rpartition("@")
        user = credentials.split(":", 1)[0]
        return f"postgres at {scheme}://{user}:***@{host}"
    return f"postgres at {text}"


class Database:
    """Base class. Concrete backends fill in connect and translate."""

    name = "unknown"

    #: The backend's "a constraint refused this row" — a duplicate key, say.
    #: Caught by class, never by message: the two word it differently.
    integrity_error: type[BaseException] = Exception

    def __init__(self, target: str) -> None:
        self.target = target
        self._lock = threading.RLock()

    # ── the surface stores use ──────────────────────────────────────────────

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        raise NotImplementedError

    def executescript(self, sql: str) -> None:
        raise NotImplementedError

    def columns(self, table: str) -> set[str]:
        """The column names of a table, or an empty set if it does not exist.

        The one piece of schema introspection that differs between the backends
        — SQLite has ``PRAGMA table_info``, Postgres has ``information_schema``
        — so it lives here rather than in every store that needs a migration.
        """
        raise NotImplementedError

    def add_column_if_missing(self, table: str, column: str, definition: str) -> bool:
        """Additive migration, and the only kind either backend gets for free.

        Returns whether it added anything. Checking first rather than catching a
        duplicate-column error: the two backends word that error differently, and
        matching on message text is how a real failure gets swallowed.
        """
        if not self.columns(table):
            return False
        if column in self.columns(table):
            return False
        self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        return True

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SQLiteDatabase(Database):
    """The original behaviour, unchanged.

    Same pragmas, same ``sqlite3.Row``, same autocommit. This class exists so
    there is one shape for both backends, not to alter how SQLite behaves —
    every existing test has to keep passing through it untouched.
    """

    name = "sqlite"
    integrity_error = sqlite3.IntegrityError

    def __init__(self, target: str, *, wal: bool = True) -> None:
        super().__init__(target)
        self.path = Path(target)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None
        )
        self.raw.row_factory = sqlite3.Row
        if wal:
            self.raw.execute("PRAGMA journal_mode=WAL")
        self.raw.execute("PRAGMA busy_timeout=5000")

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        with self._lock:
            return self.raw.execute(sql, tuple(params or ()))

    def executescript(self, sql: str) -> None:
        with self._lock:
            self.raw.executescript(sql)

    def columns(self, table: str) -> set[str]:
        with self._lock:
            rows = self.raw.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    @contextmanager
    def transaction(self) -> Iterator["SQLiteDatabase"]:
        with self._lock:
            self.raw.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self.raw.execute("ROLLBACK")
                raise
            self.raw.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            self.raw.close()


class PostgresDatabase(Database):
    """psycopg 3, in autocommit, with dict rows and ``?`` translated to ``%s``.

    Autocommit matches SQLite's ``isolation_level=None``, which is what the
    stores were written against: they open an explicit transaction when they
    need one and otherwise expect a statement to be durable when it returns.
    Leaving psycopg's default transaction block in place would silently change
    that contract for every existing caller.

    Written for any host (DD-70). The URL goes to the driver untouched, so a
    host's own options — ``sslmode``, ``sslrootcert``, ``channel_binding`` —
    ride in it. A server drops idle connections: Neon's compute sleeps after
    five minutes, and AWS and Azure close idle ones behind their load
    balancers. One connection held for the life of the process failed every
    query after the first such drop, until a restart (D-199).
    """

    name = "postgres"

    #: A connection idle this long is checked before it is used. Cheaper than
    #: a check per statement, and a drop is only likely after a quiet spell.
    idle_check_seconds: float = 30.0

    def __init__(self, target: str, *, connect_timeout: int = 10) -> None:
        super().__init__(target)
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise DatabaseError(
                "Postgres support needs psycopg. Install the extra:\n"
                "    uv pip install 'offsetx-apollo-builder[postgres]'\n"
                "or run against SQLite by leaving "
                f"{DATABASE_URL_ENV} unset."
            ) from exc

        self._psycopg = psycopg
        self.integrity_error = psycopg.IntegrityError
        self._dict_row = dict_row
        self._connect_timeout = connect_timeout
        self.raw = self._connect()
        self._last_used = time.monotonic()
        self._transaction_depth = 0

    def _connect(self) -> Any:
        try:
            # No server-side prepared statements (`prepare_threshold=None`): a
            # pooler in transaction mode — PgBouncer, Neon's pooled URL, RDS
            # Proxy — hands each transaction a different server connection,
            # where a statement prepared on another does not exist.
            return self._psycopg.connect(
                self.target,
                autocommit=True,
                row_factory=self._dict_row,
                connect_timeout=self._connect_timeout,
                prepare_threshold=None,
            )
        except self._psycopg.Error as exc:
            raise DatabaseUnavailable(
                f"Could not connect to {describe_target(self.target)}: {exc}"
            ) from exc

    def _live(self) -> Any:
        """The connection, reopened if the server is known to have dropped it.

        Only ever *before* a statement. A statement that fails mid-flight is
        not sent again: whether it ran is unknown, and repeating a write that
        did run is how a record gets made twice. The failure goes to the
        caller, and the broken connection is replaced before the next one.
        """
        raw = self.raw
        if self._transaction_depth:
            # Never swapped inside a transaction: the statements after it
            # would run outside it, committed one by one.
            return raw
        dropped = raw.closed or raw.broken
        if not dropped and time.monotonic() - self._last_used >= self.idle_check_seconds:
            try:
                raw.execute("SELECT 1")
            except self._psycopg.OperationalError:
                dropped = True
        if dropped:
            try:
                raw.close()
            except self._psycopg.Error:
                pass
            self.raw = self._connect()
        self._last_used = time.monotonic()
        return self.raw

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        with self._lock:
            # Always pass a sequence, never None. psycopg only treats `%` as a
            # placeholder marker when parameters are present, so passing None
            # sometimes and a tuple other times would make the same translated
            # SQL mean two different things.
            raw = self._live()
            try:
                return raw.execute(translate_params(sql), tuple(params or ()))
            except self._psycopg.OperationalError as exc:
                raise DatabaseUnavailable(
                    f"{describe_target(self.target)} stopped answering: {exc}"
                ) from exc

    def executescript(self, sql: str) -> None:
        with self._lock:
            # No parameters here, so `%` is not special and the SQL goes as
            # written. psycopg runs multiple statements in one call.
            raw = self._live()
            try:
                raw.execute(sql)
            except self._psycopg.OperationalError as exc:
                raise DatabaseUnavailable(
                    f"{describe_target(self.target)} stopped answering: {exc}"
                ) from exc

    def columns(self, table: str) -> set[str]:
        rows = self.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = current_schema() AND table_name = ?",
            [table],
        ).fetchall()
        return {str(row["column_name"]) for row in rows}

    @contextmanager
    def transaction(self) -> Iterator["PostgresDatabase"]:
        with self._lock:
            raw = self._live()
            self._transaction_depth += 1
            try:
                with raw.transaction():
                    yield self
            finally:
                self._transaction_depth -= 1

    def close(self) -> None:
        with self._lock:
            self.raw.close()


def open_database(
    target: object = None, *, default: object = None, wal: bool = True
) -> Database:
    """Open whichever backend the target names."""
    resolved = resolve_target(target, default=default)
    if is_postgres_url(resolved):
        return PostgresDatabase(resolved)
    return SQLiteDatabase(resolved, wal=wal)
