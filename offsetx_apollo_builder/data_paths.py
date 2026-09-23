"""Where durable data lives when nothing names it: one rule for every entry point.

The web app, the outreach CLI and the notebook CLI must open the same CRM
database by default. Each had its own default, and when the web app's began to
follow `OFFSETX_DATA_DIR` — the one durable root a backup covers — the CLIs
kept `local_data/` and quietly opened a second, empty CRM beside it (D-127).

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
