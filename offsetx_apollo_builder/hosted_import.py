"""Moving a local install's keys, settings, counters and logins into the hosted
database, once — `offsetx-db import-local` (`S-06.03.02`, D-210).

An install with a real disk — Docker's `./local_data`, a server with its own
volume — that switches `OFFSETX_DATABASE_URL` on keeps those files, and the app
refuses to start until the owner says what happens to them: copied in, or left
where they are. Either way the files are not touched, so going back is a matter
of unsetting the two settings.

Only into a database that holds none of them yet: merging two sets of logins
or two key stores would have to pick a winner, and that is the owner's call.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .ai.registry import ProviderRegistry
from .ai.workspace import WorkspaceAISettingsStore
from .api.auth import USER_STEPS
from .db.hosted import (
    LOCAL_IMPORT,
    PROVIDER_KEYS,
    QUOTA,
    SETTINGS,
    SKIP_COMMAND,
    HostedStorage,
    HostedStorageError,
    local_leftovers,
)
from .db.schema import ensure_schema

_USER_COLUMNS = (
    "username", "workspace_id", "password_salt", "password_hash",
    "session_version", "enabled", "created_at", "updated_at",
)


def _counters(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _logins(path: Path) -> list[tuple[Any, ...]]:
    if not path.is_file():
        return []
    reader = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        return reader.execute(
            f"SELECT {', '.join(_USER_COLUMNS)} FROM workspace_users ORDER BY username"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        reader.close()


def _undecided_and_empty(hosted: HostedStorage) -> None:
    """The caller holds `hosted.exclusive()`."""
    if hosted.read(LOCAL_IMPORT) is not None:
        raise HostedStorageError(
            "The database was already told what to do with a data folder; nothing was changed."
        )
    held = [name for name in (SETTINGS, PROVIDER_KEYS, QUOTA) if hosted.read(name) is not None]
    if hosted.connection.execute("SELECT 1 FROM workspace_users LIMIT 1").fetchone() is not None:
        held.append("logins")
    if held:
        raise HostedStorageError(
            f"The database already holds {', '.join(held)}, and importing over them would lose "
            f"one side. Nothing was changed. To keep the database as it is: `{SKIP_COMMAND}`."
        )


def import_local(hosted: HostedStorage, data_dir: Path) -> list[str]:
    """Copy the folder's settings, keys, counters and logins in, in one write.

    The keys are decrypted with the folder's own master key and stored again
    under `OFFSETX_SECRETS_KEY`; the folder's key never reaches the database.
    """
    data_dir = Path(data_dir)
    found = local_leftovers(data_dir)
    document, keys = WorkspaceAISettingsStore(data_dir, ProviderRegistry()).snapshot()
    counters = _counters(data_dir / "ai_quota.json")
    logins = _logins(data_dir / "workspace_auth.db")
    if hosted.fernet is None:  # pragma: no cover - `configured` always gives one
        raise HostedStorageError("Importing provider keys needs OFFSETX_SECRETS_KEY.")
    # Before the write window: a schema step takes its own transaction.
    ensure_schema(hosted.connection, "workspace_users", USER_STEPS)
    with hosted.exclusive():
        _undecided_and_empty(hosted)
        if document:
            hosted.write(SETTINGS, json.dumps(document, ensure_ascii=False))
        if keys:
            token = hosted.fernet.encrypt(json.dumps(keys, ensure_ascii=False).encode("utf-8"))
            hosted.write(PROVIDER_KEYS, token.decode("ascii"))
        if counters:
            hosted.write(QUOTA, json.dumps(counters, ensure_ascii=False))
        marks = ", ".join("?" for _ in _USER_COLUMNS)
        for row in logins:
            hosted.connection.execute(
                f"INSERT INTO workspace_users({', '.join(_USER_COLUMNS)}) VALUES({marks})", list(row)
            )
        hosted.record_local_decision({"imported": found})
    return found


def skip_local(hosted: HostedStorage, data_dir: Path) -> list[str]:
    """Keep the database as it is; the folder's files stay, unread."""
    found = local_leftovers(Path(data_dir))
    with hosted.exclusive():
        if hosted.read(LOCAL_IMPORT) is not None:
            raise HostedStorageError(
                "The database was already told what to do with a data folder; nothing was changed."
            )
        hosted.record_local_decision({"skipped": found})
    return found
