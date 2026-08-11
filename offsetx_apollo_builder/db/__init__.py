"""Database backends.

off_CRM is SQLite-first and stays that way for a single owner on one machine.
Postgres exists for the case SQLite genuinely cannot serve: a deployment where
the filesystem does not survive a restart, or more than one process writing.

The seam is deliberately thin. Stores keep writing readable SQL with ``?``
placeholders; :func:`open_database` returns something that behaves like the
``sqlite3.Connection`` they already use, and translates on the way to Postgres.
An ORM would have replaced auditable SQL with expression trees, which is a bad
trade in a codebase whose security argument depends on being able to read the
queries.
"""

from .connection import (
    DATABASE_URL_ENV,
    Database,
    DatabaseError,
    PostgresDatabase,
    SQLiteDatabase,
    describe_target,
    is_postgres_url,
    open_database,
    resolve_target,
)
from .translate import translate_params

__all__ = [
    "DATABASE_URL_ENV",
    "Database",
    "DatabaseError",
    "PostgresDatabase",
    "SQLiteDatabase",
    "describe_target",
    "is_postgres_url",
    "open_database",
    "resolve_target",
    "translate_params",
]
