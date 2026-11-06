"""Archive-first, owner-invoked cutover for hosted content metadata.

Media bytes stay on their separately configured durable filesystem. This command
never uploads media, merges conflicting customer rows, or deletes source files.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from ..agent.routines import SCHEMA as ROUTINES
from ..meetings.store import SCHEMA as MEETINGS
from ..distribution.store import SCHEMA as POSTS, LARGE_INTEGER_COLUMNS as POST_COUNTERS
from ..distribution.trends import (
    SCHEMA as TRENDS,
    LARGE_INTEGER_COLUMNS as TREND_COUNTERS,
)
from ..imagery.store import SCHEMA as IMAGERY, LARGE_INTEGER_COLUMNS as IMAGE_COUNTERS
from ..outreach.backup import restore_pending
from ..outreach.workspace_lock import WorkspaceLock
from .hosted import HostedStorage
from .connection import is_postgres_url
from .schema import ensure_initial_sql_schema

COUNTERS = {
    "routines": {},
    "meetings": {},
    "imagery": IMAGE_COUNTERS,
    "distribution": POST_COUNTERS,
    "trends": TREND_COUNTERS,
}

STORES = {
    "routines": ("agent_routines.db", ROUTINES),
    "meetings": ("meeting_transcripts.db", MEETINGS),
    "imagery": ("imagery.db", IMAGERY),
    "distribution": ("distribution.db", POSTS),
    "trends": ("trends.db", TRENDS),
}


class ContentImportError(ValueError):
    """Keep the original data until an operator resolves the unsafe cutover."""


def _layout(kind):
    try:
        schema = STORES[kind][1]
    except KeyError:
        raise ContentImportError("Choose imagery, distribution, trends, routines or meetings") from None
    with closing(sqlite3.connect(":memory:")) as sample:
        sample.executescript(schema)
        tables = [
            r[0]
            for r in sample.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            table: tuple(r[1] for r in sample.execute(f'PRAGMA table_info("{table}")'))
            for table in tables
        }


def _source_rows(connection, layout):
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ContentImportError("Local content database is damaged; preserve it")
    found = {
        r[0]
        for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if "offcrm_schema" in found:
        if any(
            int(row[0]) > 2
            for row in connection.execute("SELECT version FROM offcrm_schema")
        ):
            raise ContentImportError(
                "Local content belongs to a newer release; preserve it"
            )
        found.remove("offcrm_schema")
    if found != set(layout):
        raise ContentImportError("Local content schema is unsupported; preserve it")
    for table, columns in layout.items():
        if (
            tuple(r[1] for r in connection.execute(f'PRAGMA table_info("{table}")'))
            != columns
        ):
            raise ContentImportError(
                "Local content columns are unsupported; preserve it"
            )
    return _rows(connection, layout)


def _rows(connection, layout):
    # Sorting in Python avoids different SQLite/PostgreSQL text collations.
    return {
        table: sorted(
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT "
                    + ",".join('"' + col + '"' for col in columns)
                    + f' FROM "{table}"'
                ).fetchall()
            ],
            key=repr,
        )
        for table, columns in layout.items()
    }


def _hosted_rows(database, layout):
    return {
        table: sorted(
            [
                tuple(row[col] for col in columns)
                for row in database.execute(
                    "SELECT "
                    + ",".join('"' + col + '"' for col in columns)
                    + f' FROM "{table}"'
                ).fetchall()
            ],
            key=repr,
        )
        for table, columns in layout.items()
    }


def _digest(connection):
    return hashlib.sha256("\n".join(connection.iterdump()).encode()).hexdigest()


def _reader(source):
    return sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)


def check_local_content(root: Path):
    """Refuse hidden legacy data; an explicitly emptied migration source is safe."""
    for kind, (filename, _) in STORES.items():
        source = root / filename
        if not source.exists() and not source.is_symlink():
            continue
        try:
            if source.is_symlink() or not source.is_file():
                raise ContentImportError("Invalid source")
            with closing(_reader(source.resolve())) as local:
                if any(_source_rows(local, _layout(kind)).values()):
                    raise ContentImportError("Unmigrated rows")
        except (sqlite3.Error, OSError, ContentImportError):
            raise ContentImportError(
                "Existing local content requires an explicit content migration before hosted startup. "
                "Stop the app, preserve "
                + filename
                + ", then use offsetx-db import-content."
            ) from None


def _same_file(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


def _archive(source, archive, expected_digest):
    if archive.resolve().is_relative_to(source.parent):
        raise ContentImportError(
            "Keep the private durable archive outside the old data directory"
        )
    if archive.is_symlink() or _same_file(archive, source):
        raise ContentImportError("The private archive must be a different regular file")
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (
        archive.parent.is_symlink()
        or stat.S_IMODE(archive.parent.stat().st_mode) & 0o077
    ):
        raise ContentImportError("Use a private durable archive directory (0700)")
    if archive.exists():
        if not archive.is_file() or stat.S_IMODE(archive.stat().st_mode) & 0o077:
            raise ContentImportError(
                "The archive must be a private regular file (0600)"
            )
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(archive, flags, 0o600)
        os.close(descriptor)
        with (
            closing(_reader(source)) as original,
            closing(sqlite3.connect(archive)) as copied,
        ):
            original.backup(copied)
    with closing(_reader(archive.resolve())) as copied:
        if _digest(copied) != expected_digest:
            raise ContentImportError(
                "The private archive differs from the complete source; choose a fresh archive"
            )
    for path in (archive, archive.parent):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def import_content(source: Path, hosted: HostedStorage, archive: Path, *, kind: str, reactivate_routines: bool = False):
    if source.is_symlink() or not source.is_file():
        raise ContentImportError(
            "Choose an existing local content database, not a symlink"
        )
    source = source.resolve()
    if not is_postgres_url(hosted.target) and _same_file(Path(hosted.target), source):
        raise ContentImportError("The hosted target must differ from the local source")
    archive = archive.absolute()
    if not is_postgres_url(hosted.target) and _same_file(Path(hosted.target), archive):
        raise ContentImportError("The private archive cannot be the hosted target")
    if _same_file(source, archive):
        raise ContentImportError("The private archive must differ from the local source")
    layout = _layout(kind)
    with WorkspaceLock(source.parent, exclusive=True):
        if restore_pending(source.parent):
            raise ContentImportError(
                "Resolve the pending restore before content migration"
            )
        hosted.check_secrets_key()
        with closing(_reader(source)) as local:
            local.execute("BEGIN")
            expected = _source_rows(local, layout)
            digest = _digest(local)
        if kind == "routines" and not reactivate_routines:
            enabled_index = layout["agent_routines"].index("enabled")
            if any(row[enabled_index] for row in expected["agent_routines"]):
                raise ContentImportError(
                    "Enabled routines may run immediately after hosted startup. Disable them locally first, "
                    "or explicitly pass --reactivate-routines to authorise resuming scheduled work"
                )
        # Alias preflight must precede this first target mutation. The same
        # key does not authorise a second installation to import/clear rows.
        hosted.claim_install(os.getenv("OFFSETX_INSTALL_ID", ""))
        _archive(source, archive, digest)
        database = hosted.connection
        # Trusted repository schema only; execute statements individually so
        # SQLite's executescript cannot commit a migration transaction early.
        ensure_initial_sql_schema(
            database, kind, STORES[kind][1], large_integer_columns=COUNTERS[kind]
        )
        with hosted.exclusive():
            existing = _hosted_rows(database, layout)
            if any(expected.values()):
                if any(existing.values()) and existing != expected:
                    raise ContentImportError(
                        "Hosted content conflicts with the source; neither copy was changed"
                    )
                if not any(existing.values()):
                    for table, columns in layout.items():
                        sql = (
                            'INSERT INTO "'
                            + table
                            + '" ('
                            + ",".join('"' + c + '"' for c in columns)
                            + ") VALUES ("
                            + ",".join("?" for _ in columns)
                            + ")"
                        )
                        for row in expected[table]:
                            database.execute(sql, row)
                if _hosted_rows(database, layout) != expected:
                    raise ContentImportError(
                        "Hosted content reconciliation failed; source retained"
                    )
        # Crash after the hosted commit is safe: an identical target is accepted
        # on retry. An uncooperative local writer is detected before cleanup.
        _clear_source(source, expected, digest, layout)
        return {table: len(rows) for table, rows in expected.items()}


def _clear_source(source, expected, digest, layout):
    with closing(sqlite3.connect(source, timeout=5)) as local:
        local.execute("BEGIN EXCLUSIVE")
        try:
            if _digest(local) != digest or _source_rows(local, layout) != expected:
                raise ContentImportError(
                    "Local content changed during migration; source retained"
                )
            for table in reversed(tuple(layout)):
                local.execute(f'DELETE FROM "{table}"')
            local.commit()
        except BaseException:
            local.rollback()
            raise
