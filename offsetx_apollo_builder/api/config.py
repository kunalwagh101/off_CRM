from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _resolved(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


@dataclass(slots=True)
class AppSettings:
    project_root: Path
    database_path: Path
    data_dir: Path
    export_dir: Path
    frontend_dist: Path
    host: str = "127.0.0.1"
    port: int = 8766
    api_token: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024
    gmail_client_secrets: Path | None = None
    gmail_token: Path | None = None
    own_email: str = ""

    @classmethod
    def from_env(cls, project_root: Path | str | None = None) -> "AppSettings":
        root = Path(project_root or Path.cwd()).resolve()
        data_dir = _resolved(os.getenv("OFFSETX_DATA_DIR", "local_data"), root)
        gmail_secrets = os.getenv("OFFSETX_GMAIL_CLIENT_SECRETS", "").strip()
        gmail_token = os.getenv("OFFSETX_GMAIL_TOKEN", "local_data/gmail_token.json").strip()
        settings = cls(
            project_root=root,
            database_path=_resolved(
                os.getenv("OFFSETX_OUTREACH_DB", "local_data/offsetx_outreach.db"), root
            ),
            data_dir=data_dir,
            export_dir=data_dir / "exports",
            frontend_dist=root / "frontend" / "dist",
            host=os.getenv("OFFSETX_WEB_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("OFFSETX_WEB_PORT", "8766")),
            api_token=os.getenv("OFFSETX_LOCAL_API_TOKEN", "").strip(),
            max_upload_bytes=int(
                os.getenv("OFFSETX_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
            ),
            gmail_client_secrets=_resolved(gmail_secrets, root) if gmail_secrets else None,
            gmail_token=_resolved(gmail_token, root) if gmail_token else None,
            own_email=os.getenv("OFFSETX_OWN_EMAIL", "").strip().lower(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        loopback = self.host in {"127.0.0.1", "localhost", "::1"}
        if not loopback and len(self.api_token) < 32:
            raise ValueError(
                "A non-loopback host requires OFFSETX_LOCAL_API_TOKEN with at least 32 characters"
            )
        if not 1 <= self.port <= 65535:
            raise ValueError("OFFSETX_WEB_PORT must be between 1 and 65535")
        if self.max_upload_bytes < 1024:
            raise ValueError("OFFSETX_MAX_UPLOAD_BYTES is too small")

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
