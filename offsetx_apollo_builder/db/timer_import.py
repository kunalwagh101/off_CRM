"""Explicit cutover for legacy email/content timer JSON into hosted settings.

This is a manual operator tool, not an application startup migration. Its job
is to keep consent, queue pacing and originals intact on failures.
"""
from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from .hosted import HostedStorage
from ..outreach.backup import restore_pending
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock

TIMERS = (
    ("automation.json", "timer.email"),
    ("content_automation.json", "timer.content"),
)


class TimerMigrationError(ValueError):
    """The operator must fix a conflict or invalid source before retrying."""


def _document(name: str, raw: bytes) -> str:
    """Prepare inert settings for the hosted store, never a live send on import."""
    try:
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("settings object required")
        if name == "automation.json":
            for key in ("interval_seconds", "max_messages_per_campaign"):
                if key in value:
                    int(value[key])
            value["enabled"] = False
            value["gmail_live_authorized"] = False
        else:
            # Use the same parser that the actual content runner uses, so an
            # invalid pipeline or rate fails before either store is changed.
            from ..distribution.automation import ContentAutomationService

            if "pipelines" in value and not isinstance(value["pipelines"], list):
                raise ValueError("pipelines must be a list")
            declared = value.get("pipelines") or []
            for pair in declared:
                if not isinstance(pair, dict):
                    raise ValueError("Each declared pipeline must be an object")
                if "account_ids" in pair and not isinstance(pair["account_ids"], list):
                    raise ValueError("Pipeline account_ids must be a list")
            value = ContentAutomationService._normalise(value)
            if len(value["pipelines"]) != len(declared):
                raise ValueError("A legacy pipeline has incomplete campaign IDs")
            value["enabled"] = False
            value["pipelines"] = [
                {**pipeline, "enabled": False}
                for pipeline in value["pipelines"]
            ]
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise TimerMigrationError(
            f"{name} has invalid settings. Keep the original and correct it before import."
        ) from None
    return json.dumps(value, indent=2)


def _archive_one(target: Path, raw: bytes) -> None:
    """Create a private backup once. Existing bytes may match, never overwrite."""
    if target.is_symlink():
        raise TimerMigrationError("An archive entry is a symbolic link; refuse to follow it.")
    if target.exists():
        if not target.is_file() or target.read_bytes() != raw:
            raise TimerMigrationError("The existing archive has different data; choose an empty archive directory.")
        if stat.S_IMODE(target.stat().st_mode) & 0o077:
            raise TimerMigrationError("An archive entry is not private; set its permissions to 0600.")
        return

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if fd != -1:
            os.close(fd)
        target.unlink(missing_ok=True)
        raise


@contextmanager
def _exclusive_workspace_lock(root: Path):
    """No active web request, timer mutation or workspace restore may overlap."""
    try:
        with WorkspaceLock(root, exclusive=True):
            if restore_pending(root):
                raise TimerMigrationError(
                    "A workspace restore is pending. Resolve recovery before changing timer settings."
                )
            yield
    except WorkspaceBusy:
        raise TimerMigrationError(
            "The workspace is busy. Stop the app and worker before migrating timers."
        ) from None


def migrate_timers(
    storage: HostedStorage, data_dir: Path, archive_dir: Path, *, import_settings: bool
) -> list[str]:
    """Copy originals to a protected archive, then explicitly import or skip.

    An operator must stop web/worker processes before running this command.
    No file is unlinked before the backups are durable and the DB write commits.
    """
    root = Path(data_dir).expanduser().resolve()
    archive_arg = Path(archive_dir).expanduser()
    if archive_arg.is_symlink():
        raise TimerMigrationError("The archive directory is a symbolic link.")
    archive = archive_arg.resolve()
    if archive == root or root in archive.parents:
        raise TimerMigrationError("Choose an archive outside the temporary data workspace.")
    if archive in (root / filename for filename, _ in TIMERS):
        raise TimerMigrationError("Choose an archive outside the temporary data workspace.")
    with _exclusive_workspace_lock(root):
        storage.claim_install(os.getenv('OFFSETX_INSTALL_ID', ''))
        sources: dict[str, bytes] = {}
        for filename, _ in TIMERS:
            local = root / filename
            if local.is_symlink():
                raise TimerMigrationError("A timer settings source is a symbolic link; refuse to follow it.")
            if local.exists():
                if not local.is_file():
                    raise TimerMigrationError("A timer settings source is not a regular file.")
                sources[filename] = local.read_bytes()
        if not sources:
            raise TimerMigrationError("No legacy timer settings files found; nothing was changed.")

        documents = {
            key: _document(filename, raw)
            for filename, key in TIMERS
            if import_settings and (raw := sources.get(filename)) is not None
        }
        # Validate old files and any hosted conflicts *before* archiving.
        storage.check_secrets_key()
        with storage.exclusive():
            if import_settings:
                for key, body in documents.items():
                    existing = storage.read(key)
                    if existing is not None:
                        try:
                            same = json.loads(existing) == json.loads(body)
                        except (ValueError, TypeError):
                            same = False
                        if not same:
                            raise TimerMigrationError(
                                "Hosted timer settings already exist with different data. "
                                "Use --skip to keep hosted settings, or resolve the conflict manually."
                            )

        archive.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not archive.is_dir() or stat.S_IMODE(archive.stat().st_mode) & 0o077:
            raise TimerMigrationError("The archive must be a private directory (0700).")
        for filename, raw in sources.items():
            _archive_one(archive / filename, raw)
        # Flush directory metadata too: a successful DB write alone is not a
        # backup if the directory entry never reaches the disk.
        if os.name != "nt":
            fd = os.open(archive, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

        with storage.exclusive():
            for key, body in documents.items():
                existing = storage.read(key)
                if existing is not None:
                    try:
                        same = json.loads(existing) == json.loads(body)
                    except (ValueError, TypeError):
                        same = False
                    if not same:
                        raise TimerMigrationError("Hosted timer settings changed during migration; retry.")
                else:
                    storage.write(key, body)

        # If a writer bypassed the workspace lease, do not discard its changes.
        # App startup refuses remaining local files, so a partial removal fails
        # closed and the operator can safely re-run after stopping that writer.
        for filename, raw in sources.items():
            local = root / filename
            if local.is_symlink() or local.read_bytes() != raw:
                raise TimerMigrationError("A source timer file changed during import; stop its writer and retry.")
        for filename in sources:
            (root / filename).unlink()
        return sorted(sources)
