"""Manual, loss-aware import of old SQLite AI task context to hosted storage.

An operator must stop the app and workers before using this procedure.
Models have no interface to this module.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing, contextmanager
from pathlib import Path

from ..ai.context import ContextLayer
from ..db.connection import is_postgres_url
from ..outreach.backup import restore_pending
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock

TABLES = {
    "ai_task_state": (
        "id", "workspace_id", "kind", "title", "status", "steps",
        "decisions", "facts", "summary", "created_at", "updated_at",
    ),
    "ai_template_stats": (
        "id", "workspace_id", "template_id", "variant_id", "label",
        "template_text", "sends", "replies", "is_winner", "retired",
        "parent_id", "created_at", "updated_at",
    ),
}


class ContextImportError(ValueError):
    """Import is unsafe or incomplete; keep the original source."""


@contextmanager
def _exclusive(root: Path):
    try:
        with WorkspaceLock(root, exclusive=True):
            if restore_pending(root):
                raise ContextImportError(
                    "A restore is pending. Resolve recovery before migrating AI context."
                )
            yield
    except WorkspaceBusy:
        raise ContextImportError(
            "The workspace is busy; stop the app and worker before migration."
        ) from None


def _reader(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _snapshot_rows(con: sqlite3.Connection) -> dict[str, list[tuple]]:
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ContextImportError("The source AI context database is invalid.")
    records = {}
    for table, columns in TABLES.items():
        found = {
            str(row["name"])
            for row in con.execute(f"PRAGMA table_info({table})")
        }
        if found != set(columns):
            raise ContextImportError(
                "The source AI context schema is unsupported; keep the original and migrate with a compatible release."
            )
        values = ", ".join(columns)
        records[table] = [
            tuple(row[name] for name in columns)
            for row in con.execute(f"SELECT {values} FROM {table} ORDER BY id")
        ]
    return records


def _private_archive(source: Path, archive: Path, expected: dict) -> None:
    if archive.is_symlink():
        raise ContextImportError("The archive cannot be a symbolic link.")
    folder = archive.parent
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    if folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode) & 0o077:
        raise ContextImportError("The archive folder must be private (0700).")
    if archive.exists():
        if not archive.is_file() or stat.S_IMODE(archive.stat().st_mode) & 0o077:
            raise ContextImportError("The existing archive is not a private SQLite file.")
        with closing(_reader(archive)) as snapshot:
            if _snapshot_rows(snapshot) != expected:
                raise ContextImportError(
                    "The archive contains different data; choose a fresh private archive."
                )
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(archive, flags, 0o600)
    os.close(fd)
    try:
        with closing(_reader(source)) as original, closing(sqlite3.connect(archive)) as backup:
            original.backup(backup)
        with closing(_reader(archive)) as check:
            if _snapshot_rows(check) != expected:
                raise ContextImportError("Archived AI history differs from the source.")
        descriptor = os.open(archive, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if os.name != "nt":
            descriptor = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except BaseException:
        archive.unlink(missing_ok=True)
        raise


def _target_rows(database) -> dict[str, list[tuple]]:
    result = {}
    for table, columns in TABLES.items():
        values = ", ".join(columns)
        result[table] = [
            tuple(row[name] for name in columns)
            for row in database.execute(
                f"SELECT {values} FROM {table} ORDER BY id"
            ).fetchall()
        ]
    return result


def import_context(
    source_path: Path,
    database_target: str,
    archive_path: Path,
    *,
    skip: bool = False,
) -> dict[str, int]:
    """Archive first, then copy *both* tables transactionally or choose skip.

    A retry after a committed copy and interrupted local cleanup is allowed
    only when every destination row still matches the archived source.
    """
    source_arg = Path(source_path).expanduser()
    archive_arg = Path(archive_path).expanduser()
    if source_arg.is_symlink() or not source_arg.is_file():
        raise ContextImportError("The local AI context source must be an existing regular file.")
    if archive_arg.is_symlink():
        raise ContextImportError("The archive cannot be a symbolic link.")
    source = source_arg.resolve()
    archive = archive_arg.resolve()
    root = source.parent
    if archive == source or archive.is_relative_to(root):
        raise ContextImportError("Choose a durable archive outside the local data folder.")
    if not database_target:
        raise ContextImportError("Set a hosted database target before migrating AI context.")
    if not is_postgres_url(database_target):
        target = Path(database_target).expanduser().resolve()
        if target in (source, archive):
            raise ContextImportError("Source, archive and hosted database must be different files.")

    with _exclusive(root):
        with closing(_reader(source)) as local:
            expected = _snapshot_rows(local)
        _private_archive(source, archive, expected)

        hosted = ContextLayer(source, database_target=database_target)
        try:
            database = hosted.connection
            with database.transaction():
                if database.name == "postgres":
                    database.execute("SELECT pg_advisory_xact_lock(?)", [7103206306])
                existing = _target_rows(database)
                if not skip:
                    if any(existing.values()):
                        if existing != expected:
                            raise ContextImportError(
                                "The hosted AI context already contains other records; no merge was attempted."
                            )
                    else:
                        for table, columns in TABLES.items():
                            placeholders = ", ".join("?" for _ in columns)
                            names = ", ".join(columns)
                            for record in expected[table]:
                                database.execute(
                                    f"INSERT INTO {table}({names}) VALUES({placeholders})",
                                    record,
                                )
                        if _target_rows(database) != expected:
                            raise ContextImportError("Hosted row verification failed; import rolled back.")
        finally:
            hosted.close()

        # A writer ignoring the workspace lock must never cause silent loss.
        with closing(_reader(source)) as local:
            if _snapshot_rows(local) != expected:
                raise ContextImportError(
                    "The source AI context changed during migration; stop its writer and retry."
                )
        source.unlink()
        return {table: len(rows) for table, rows in expected.items()}
