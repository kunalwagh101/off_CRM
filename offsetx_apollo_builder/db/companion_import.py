"""Explicit archive-first cutover for companion profiles/procedures (S-06.03.06).

The SQLite file also owns executable tool registrations and execution policy.
Do NOT delete that file. Preserve a full private archive before copying only
the known companion rows into hosted SQL, then clear only those local rows.
Never silently import tool grants whose registry has no durable hosted home.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from ..agent.companions import ensure_companion_schema
from ..db.hosted import HostedStorage
from ..outreach.backup import restore_pending
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock


TABLES: dict[str, tuple[str, ...]] = {
    "agent_companions": (
        "id", "workspace_id", "name", "instructions", "memory_scope",
        "granted_tool_ids", "enabled", "created_at", "updated_at",
    ),
    "agent_companion_skills": (
        "id", "workspace_id", "name", "content", "enabled",
        "created_at", "updated_at",
    ),
}


class CompanionImportError(ValueError):
    """Source migration was refused; keep the original and its private archive."""


def _reader(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def _snapshot_rows(con: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Reject unexpected schemas or grants we cannot carry onto the new host."""
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise CompanionImportError("The local tool registry is damaged")
        result: dict[str, list[tuple]] = {}
        for table, columns in TABLES.items():
            found = {
                str(row["name"])
                for row in con.execute(f"PRAGMA table_info({table})")
            }
            if not found and table == "agent_companion_skills":
                # The skill table was added after original companion profiles.
                result[table] = []
                continue
            if found != set(columns):
                raise CompanionImportError(
                    "The local companion schema is unsupported; preserve the original file"
                )
            selected = ", ".join(columns)
            result[table] = [
                tuple(row[column] for column in columns)
                for row in con.execute(f"SELECT {selected} FROM {table} ORDER BY id")
            ]
        for row in result["agent_companions"]:
            try:
                grants = json.loads(str(row[5]))
            except (ValueError, TypeError):
                raise CompanionImportError(
                    "An old companion has invalid executable tool grants"
                ) from None
            if grants != []:
                raise CompanionImportError(
                    "Local companion tool grants cannot be migrated yet: "
                    "the executable tool registry still has no durable hosted home. "
                    "Preserve the source file and migrate tool registration first."
                )
        return result
    except sqlite3.DatabaseError:
        raise CompanionImportError(
            "The local tool registry is damaged or unreadable; preserve the original"
        ) from None


def _private_archive(source: Path, archive: Path, expected: dict[str, list[tuple]]) -> None:
    """Retain a complete ToolRegistry database, not only the companion tables."""
    parent = archive.parent
    if archive.is_symlink() or parent.is_symlink():
        raise CompanionImportError("A private archive path cannot be a symbolic link")
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise CompanionImportError("The archive directory must be private (0700)")
    if archive.exists():
        if not archive.is_file() or stat.S_IMODE(archive.stat().st_mode) & 0o077:
            raise CompanionImportError("An existing archive must be a private regular file (0600)")
        with closing(_reader(archive)) as previous:
            if _snapshot_rows(previous) != expected:
                raise CompanionImportError(
                    "Existing archive differs from the original. Use a new private archive."
                )
        return

    # Back up SQLite through the SQLite API, including WAL pages. Never copy a
    # live .db file with shutil.copyfile (the last committed rows may be in WAL).
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
                raise CompanionImportError("The private SQLite archive did not reconcile")
        file_fd = os.open(archive, os.O_RDONLY)
        try:
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        if os.name != "nt":
            dir_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except BaseException:
        archive.unlink(missing_ok=True)
        raise


def _target_rows(database) -> dict[str, list[tuple]]:
    result = {}
    for table, columns in TABLES.items():
        selected = ", ".join(columns)
        result[table] = [
            tuple(row[column] for column in columns)
            for row in database.execute(
                f"SELECT {selected} FROM {table} ORDER BY id"
            ).fetchall()
        ]
    return result


def _clear_local_rows(source: Path, expected: dict[str, list[tuple]]) -> None:
    """Remove ONLY migrated companion rows, transactionally, never tools."""
    with closing(sqlite3.connect(source, isolation_level=None, timeout=5)) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN IMMEDIATE")
        try:
            if _snapshot_rows(con) != expected:
                raise CompanionImportError(
                    "The source changed during the import. Stop other processes and retry."
                )
            for table in reversed(tuple(TABLES)):
                # A historical file may predate the skill table entirely.
                if con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone():
                    con.execute(f"DELETE FROM {table}")
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise


def import_companions(
    source_path: Path, hosted: HostedStorage, archive_path: Path,
) -> dict[str, int]:
    """Import rows exactly once into hosted DB; retain a complete local archive.

    Requires app and workers stopped, an archive on durable private storage and
    an owner-supplied hosted key. Safe to retry after hosted commit but before
    local cleanup; refuses merging with different hosted rows.
    """
    source_arg, archive_arg = Path(source_path).expanduser(), Path(archive_path).expanduser()
    if source_arg.is_symlink() or not source_arg.is_file():
        raise CompanionImportError("The source must be an existing non-symlink local tool database")
    if archive_arg.is_symlink() or archive_arg.parent.is_symlink():
        raise CompanionImportError("The archive path cannot be a symlink")
    source, archive = source_arg.resolve(), archive_arg.resolve()
    root = source.parent
    if archive == source or archive.is_relative_to(root):
        raise CompanionImportError("Choose a private durable archive outside the old data directory")
    # It is not safe to treat the live local SQLite file as the hosted target.
    from ..db.connection import is_postgres_url
    if (not is_postgres_url(hosted.target)
            and Path(hosted.target).expanduser().resolve() == source):
        raise CompanionImportError("The source and hosted database must be different")
    try:
        with WorkspaceLock(root, exclusive=True):
            if restore_pending(root):
                raise CompanionImportError("Resolve a pending workspace restore before migrating companions")
            with closing(_reader(source)) as old:
                expected = _snapshot_rows(old)
            if not any(expected.values()):
                raise CompanionImportError("The local registry has no companion rows to migrate")
            _private_archive(source, archive, expected)
            hosted.check_secrets_key()
            with hosted.exclusive():
                database = hosted.connection
                ensure_companion_schema(database)
                current = _target_rows(database)
                if any(current.values()):
                    if current != expected:
                        raise CompanionImportError(
                            "Hosted companions contain different records. "
                            "No merge occurred; reconcile using the private source archive."
                        )
                else:
                    for table, columns in TABLES.items():
                        names = ", ".join(columns)
                        placeholders = ", ".join("?" for _ in columns)
                        for row in expected[table]:
                            database.execute(
                                f"INSERT INTO {table} ({names}) VALUES ({placeholders})", row,
                            )
                    if _target_rows(database) != expected:
                        raise CompanionImportError(
                            "The hosted companion rows failed reconciliation; import rolled back"
                        )
            # Keep executable tool registry and history; only clear the rows
            # moved above so subsequent hosted edits don't conflict at startup.
            _clear_local_rows(source, expected)
            return {name: len(rows) for name, rows in expected.items()}
    except WorkspaceBusy:
        raise CompanionImportError(
            "Stop the app and workers before migrating the local companions"
        ) from None
