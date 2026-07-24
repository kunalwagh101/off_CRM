from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _resolved(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


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
    demo_username: str = ""
    demo_password: str = ""
    session_secret: str = ""
    session_hours: int = 8
    max_upload_bytes: int = 10 * 1024 * 1024
    gmail_client_secrets: Path | None = None
    gmail_token: Path | None = None
    own_email: str = ""
    public_positioning: str = ""
    owner_domains: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, project_root: Path | str | None = None) -> "AppSettings":
        root = Path(project_root or Path.cwd()).resolve()
        data_dir = _resolved(
            _env("OFF_CRM_DATA_DIR", "OFFSETX_DATA_DIR", default="local_data"),
            root,
        )
        gmail_secrets = _env(
            "OFF_CRM_GMAIL_CLIENT_SECRETS",
            "OFFSETX_GMAIL_CLIENT_SECRETS",
        ).strip()
        gmail_token = _env(
            "OFF_CRM_GMAIL_TOKEN",
            "OFFSETX_GMAIL_TOKEN",
            default="local_data/gmail_token.json",
        ).strip()
        settings = cls(
            project_root=root,
            database_path=_resolved(
                _env(
                    "OFF_CRM_DB",
                    "OFFSETX_OUTREACH_DB",
                    default="local_data/off_crm.db",
                ),
                root,
            ),
            data_dir=data_dir,
            export_dir=data_dir / "exports",
            frontend_dist=root / "frontend" / "dist",
            host=_env(
                "OFF_CRM_WEB_HOST", "OFFSETX_WEB_HOST", default="127.0.0.1"
            ).strip(),
            port=int(
                os.getenv("PORT")
                or _env("OFF_CRM_WEB_PORT", "OFFSETX_WEB_PORT", default="8766")
            ),
            api_token=_env(
                "OFF_CRM_LOCAL_API_TOKEN", "OFFSETX_LOCAL_API_TOKEN"
            ).strip(),
            demo_username=_env(
                "OFF_CRM_DEMO_USERNAME", "OFFSETX_DEMO_USERNAME"
            ).strip(),
            demo_password=_env(
                "OFF_CRM_DEMO_PASSWORD", "OFFSETX_DEMO_PASSWORD"
            ),
            session_secret=_env(
                "OFF_CRM_SESSION_SECRET", "OFFSETX_SESSION_SECRET"
            ),
            session_hours=int(
                _env(
                    "OFF_CRM_SESSION_HOURS",
                    "OFFSETX_SESSION_HOURS",
                    default="8",
                )
            ),
            max_upload_bytes=int(
                _env(
                    "OFF_CRM_MAX_UPLOAD_BYTES",
                    "OFFSETX_MAX_UPLOAD_BYTES",
                    default=str(10 * 1024 * 1024),
                )
            ),
            gmail_client_secrets=_resolved(gmail_secrets, root) if gmail_secrets else None,
            gmail_token=_resolved(gmail_token, root) if gmail_token else None,
            own_email=(
                _env("OFF_CRM_OWN_EMAIL", "OFFSETX_OWN_EMAIL")
            ).strip().lower(),
            public_positioning=(
                _env("OFF_CRM_PUBLIC_POSITIONING", "OFFSETX_PUBLIC_POSITIONING")
            ).strip(),
            owner_domains=tuple(
                dict.fromkeys(
                    item.strip().lower().lstrip("@")
                    for item in (
                        _env("OFF_CRM_OWNER_DOMAINS", "OFFSETX_OWNER_DOMAINS")
                    ).split(",")
                    if item.strip()
                )
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        loopback = self.host in {"127.0.0.1", "localhost", "::1"}
        demo_values = (self.demo_username, self.demo_password, self.session_secret)
        if any(demo_values) and not all(demo_values):
            raise ValueError(
                "Demo login requires OFF_CRM_DEMO_USERNAME, OFF_CRM_DEMO_PASSWORD, "
                "and OFF_CRM_SESSION_SECRET"
            )
        if self.demo_password and len(self.demo_password) < 12:
            raise ValueError("OFF_CRM_DEMO_PASSWORD must contain at least 12 characters")
        if self.session_secret and len(self.session_secret) < 32:
            raise ValueError("OFF_CRM_SESSION_SECRET must contain at least 32 characters")
        if self.api_token and len(self.api_token) < 32:
            raise ValueError("OFF_CRM_LOCAL_API_TOKEN must contain at least 32 characters")
        if not loopback and not (self.api_token or self.demo_login_enabled):
            raise ValueError(
                "A non-loopback host requires a strong API token or complete demo login settings"
            )
        if not 1 <= self.port <= 65535:
            raise ValueError("OFF_CRM_WEB_PORT must be between 1 and 65535")
        if self.max_upload_bytes < 1024:
            raise ValueError("OFF_CRM_MAX_UPLOAD_BYTES is too small")
        if not 1 <= self.session_hours <= 24:
            raise ValueError("OFF_CRM_SESSION_HOURS must be between 1 and 24")

    @property
    def demo_login_enabled(self) -> bool:
        return bool(self.demo_username and self.demo_password and self.session_secret)

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
