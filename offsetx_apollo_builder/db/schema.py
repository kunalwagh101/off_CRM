"""A schema version per store in a shared database (`S-06.03.02`, `DD-70`).

`CREATE TABLE IF NOT EXISTS` makes a table once and never changes it again. A
store meant to outlive the host it starts on — Render or Neon today, AWS or
Azure later — has to know what shape its tables are in, so a database moved to
a new host, or opened by a newer release, is upgraded from where it is rather
than guessed at.

Each store names its steps, oldest first; a step's position is its version.
`ensure_schema` runs the steps a database has not had, recording each version
in the same transaction as the step, under a lock that two instances starting
together cannot both hold. Steps only ever go forward: undoing one is a restore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Sequence

from .connection import Database, DatabaseError

Step = Callable[[Database], None]

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS offcrm_schema (
    component TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    updated_at TEXT NOT NULL
)
"""

#: PostgreSQL's advisory lock for schema changes. SQLite needs none: the
#: transaction is `BEGIN IMMEDIATE`, already exclusive across processes.
_SCHEMA_LOCK = 7_103_206_301


def schema_version(database: Database, component: str) -> int:
    """The last step this database has had for a store; 0 for none."""
    if not database.columns("offcrm_schema"):
        return 0
    row = database.execute(
        "SELECT version FROM offcrm_schema WHERE component = ?", [component]
    ).fetchone()
    return int(row["version"]) if row else 0


def ensure_schema(database: Database, component: str, steps: Sequence[Step]) -> int:
    """Bring a store's tables up to the newest step this release knows."""
    newest = len(steps)
    if schema_version(database, component) == newest:
        return newest
    with database.transaction():
        if database.name == "postgres":
            database.execute("SELECT pg_advisory_xact_lock(?)", [_SCHEMA_LOCK])
        # Inside the lock, so a second instance waiting here sees what the
        # first one did instead of doing it again.
        database.execute(_SCHEMA_TABLE)
        current = schema_version(database, component)
        if current > newest:
            raise DatabaseError(
                f"The database's {component} tables are at version {current}, newer than "
                f"this release knows ({newest}). Run the release that upgraded them, or "
                "restore the database from before the upgrade."
            )
        for version in range(current + 1, newest + 1):
            steps[version - 1](database)
            database.execute(
                "INSERT INTO offcrm_schema(component, version, updated_at) VALUES(?, ?, ?)"
                " ON CONFLICT(component) DO UPDATE SET"
                " version = excluded.version, updated_at = excluded.updated_at",
                [component, version, datetime.now(timezone.utc).isoformat()],
            )
    return newest


def ensure_initial_sql_schema(
    database: Database, component: str, script: str, *,
    large_integer_columns: dict[str, tuple[str, ...]] | None = None,
) -> int:
    """Version a trusted initial SQL schema without SQLite implicit commits."""
    def create(target: Database) -> None:
        for statement in script.split(";"):
            if statement.strip():
                target.execute(statement)
    steps = [create]
    if large_integer_columns:
        def widen(target: Database) -> None:
            if target.name == "postgres":
                for table, columns in large_integer_columns.items():
                    for column in columns:
                        target.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE BIGINT')
        steps.append(widen)
    return ensure_schema(database, component, steps)
