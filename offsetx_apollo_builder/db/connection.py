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

    def __init__(self, target: str) -> None:
        self.target = target
        self._lock = threading.RLock()

    # ── the surface stores use ──────────────────────────────────────────────

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        raise NotImplementedError

    def executescript(self, sql: str) -> None:
        raise NotImplementedError

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
    """

    name = "postgres"

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
        try:
            self.raw = psycopg.connect(
                target,
                autocommit=True,
                row_factory=dict_row,
                connect_timeout=connect_timeout,
            )
        except psycopg.Error as exc:
            raise DatabaseError(
                f"Could not connect to {describe_target(target)}: {exc}"
            ) from exc

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        with self._lock:
            # Always pass a sequence, never None. psycopg only treats `%` as a
            # placeholder marker when parameters are present, so passing None
            # sometimes and a tuple other times would make the same translated
            # SQL mean two different things.
            return self.raw.execute(translate_params(sql), tuple(params or ()))

    def executescript(self, sql: str) -> None:
        with self._lock:
            # No parameters here, so `%` is not special and the SQL goes as
            # written. psycopg runs multiple statements in one call.
            self.raw.execute(sql)

    @contextmanager
    def transaction(self) -> Iterator["PostgresDatabase"]:
        with self._lock:
            with self.raw.transaction():
                yield self

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
