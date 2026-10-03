"""Where durable data lives when nothing names it: one rule for every entry point.

The web app and every command-line tool must open the same files by default.
Each had its own default, and when the web app's began to follow
`OFFSETX_DATA_DIR` — the one durable root a backup covers — the CLIs kept
`local_data/` and quietly opened a second, empty CRM beside it (D-127), and
later a Gmail token and an egress log the web app never read (D-138).

Its own module rather than a function in `api/config.py`: importing anything
from `api` imports the whole web app, which a command-line tool should not pay
for.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolved(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def data_dir(root: Path) -> Path:
    return resolved(os.getenv("OFFSETX_DATA_DIR", "local_data"), root)


def database_path(root: Path | str | None = None) -> Path:
    base = Path(root or Path.cwd()).resolve()
    return resolved(
        os.getenv("OFFSETX_OUTREACH_DB", str(data_dir(base) / "offsetx_outreach.db")), base
    )


def crm_target(explicit: str | Path | None = None, root: Path | str | None = None) -> str:
    """The CRM to open: one named on the command line, then `OFFSETX_DATABASE_URL`,
    then `OFFSETX_OUTREACH_DB` — the order every hosted store follows, so a tool
    opens the CRM the web app does (`S-06.03.03`). Before it, the tools baked
    the file in as their default, and the email worker would have sent from an
    empty local CRM while the web app's was in the database."""
    from .db.connection import resolve_target

    return resolve_target(explicit, default=database_path(root))


def gmail_token_path(root: Path | str | None = None) -> Path | None:
    """The Gmail token file; None when OFFSETX_GMAIL_TOKEN is set but empty,
    which is how the web app has always read "Gmail is off"."""
    base = Path(root or Path.cwd()).resolve()
    value = os.getenv("OFFSETX_GMAIL_TOKEN", str(data_dir(base) / "gmail_token.json")).strip()
    return resolved(value, base) if value else None
