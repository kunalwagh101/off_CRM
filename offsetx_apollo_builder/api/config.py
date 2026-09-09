from __future__ import annotations

import os
import tempfile
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from ..outreach.backup import DEFAULT_MAX_BACKUP_BYTES


def _resolved(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


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
    api_token_from_file: bool = False
    demo_username: str = ""
    demo_password: str = ""
    session_secret: str = ""
    session_hours: int = 8
    max_upload_bytes: int = 10 * 1024 * 1024
    backup_max_bytes: int = DEFAULT_MAX_BACKUP_BYTES
    production: bool = False
    persistent_mount: Path | None = None
    gmail_client_secrets: Path | None = None
    gmail_token: Path | None = None
    own_email: str = ""
    public_base_url: str = ""
    unsubscribe_secret: str = ""
    #: Host header values this server answers to. Empty means "derive from
    #: `host` plus the loopback names", which is right for a local install and
    #: wrong for a public deployment — that one names its own domain.
    allowed_hosts: tuple[str, ...] = ()
    #: Serve the API with no authentication at all. **Only a test harness may
    #: set this.** It exists so the fail-closed check in `create_app` has an
    #: explicit, greppable opt-out rather than a silent one: a config that
    #: simply forgot a token used to be indistinguishable from one that meant it.
    allow_unauthenticated: bool = False

    @classmethod
    def from_env(cls, project_root: Path | str | None = None) -> "AppSettings":
        root = Path(project_root or Path.cwd()).resolve()
        data_dir = _resolved(os.getenv("OFFSETX_DATA_DIR", "local_data"), root)
        gmail_secrets = os.getenv("OFFSETX_GMAIL_CLIENT_SECRETS", "").strip()
        gmail_token = os.getenv("OFFSETX_GMAIL_TOKEN", str(data_dir / "gmail_token.json")).strip()
        persistent_mount = os.getenv("OFFSETX_PERSISTENT_MOUNT", "").strip()
        settings = cls(
            project_root=root,
            database_path=_resolved(
                os.getenv("OFFSETX_OUTREACH_DB", str(data_dir / "offsetx_outreach.db")), root
            ),
            data_dir=data_dir,
            export_dir=data_dir / "exports",
            frontend_dist=root / "frontend" / "dist",
            host=os.getenv("OFFSETX_WEB_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("PORT") or os.getenv("OFFSETX_WEB_PORT", "8766")),
            api_token=os.getenv("OFFSETX_LOCAL_API_TOKEN", "").strip(),
            demo_username=os.getenv("OFFSETX_DEMO_USERNAME", "").strip(),
            demo_password=os.getenv("OFFSETX_DEMO_PASSWORD", ""),
            session_secret=os.getenv("OFFSETX_SESSION_SECRET", ""),
            session_hours=int(os.getenv("OFFSETX_SESSION_HOURS", "8")),
            max_upload_bytes=int(
                os.getenv("OFFSETX_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
            ),
            backup_max_bytes=int(
                os.getenv("OFFSETX_BACKUP_MAX_BYTES", str(DEFAULT_MAX_BACKUP_BYTES))
            ),
            production=_enabled(os.getenv("OFFSETX_PRODUCTION", "")),
            persistent_mount=_resolved(persistent_mount, root) if persistent_mount else None,
            gmail_client_secrets=_resolved(gmail_secrets, root) if gmail_secrets else None,
            gmail_token=_resolved(gmail_token, root) if gmail_token else None,
            own_email=os.getenv("OFFSETX_OWN_EMAIL", "").strip().lower(),
            public_base_url=os.getenv("OFFSETX_PUBLIC_BASE_URL", "").strip(),
            unsubscribe_secret=os.getenv("OFFSETX_UNSUBSCRIBE_SECRET", ""),
            allowed_hosts=tuple(
                item.strip().lower()
                for item in os.getenv("OFFSETX_ALLOWED_HOSTS", "").split(",")
                if item.strip()
            ),
        )
        # Provision before validating: `validate` now requires authentication on
        # every host including loopback, and a local install that has never been
        # configured should get a token rather than an error it has to fix by
        # hand. Order matters — validate would refuse the very config this is
        # about to make valid.
        settings.validate_storage()
        settings.verify_persistent_mount()
        settings.ensure_api_token()
        settings.validate()
        return settings

    def validate(self) -> None:
        loopback = self.host in {"127.0.0.1", "localhost", "::1"}
        demo_values = (self.demo_username, self.demo_password, self.session_secret)
        if any(demo_values) and not all(demo_values):
            raise ValueError(
                "Demo login requires OFFSETX_DEMO_USERNAME, OFFSETX_DEMO_PASSWORD, "
                "and OFFSETX_SESSION_SECRET"
            )
        if self.demo_password and len(self.demo_password) < 12:
            raise ValueError("OFFSETX_DEMO_PASSWORD must contain at least 12 characters")
        if self.session_secret and len(self.session_secret) < 32:
            raise ValueError("OFFSETX_SESSION_SECRET must contain at least 32 characters")
        if self.api_token and len(self.api_token) < 32:
            raise ValueError("OFFSETX_LOCAL_API_TOKEN must contain at least 32 characters")
        if not (self.api_token or self.demo_login_enabled or self.allow_unauthenticated):
            raise ValueError(
                "off_CRM requires an API token or complete demo login settings. "
                "This applies on 127.0.0.1 too: an unauthenticated local API is "
                "readable by every other process and user on the machine, and by "
                "any web page that can rebind a hostname to loopback. Run through "
                "`run_offsetx_web.py` and one will be generated for you, or set "
                "OFFSETX_LOCAL_API_TOKEN yourself."
            )
        if not 1 <= self.port <= 65535:
            raise ValueError("OFFSETX_WEB_PORT must be between 1 and 65535")
        if self.max_upload_bytes < 1024:
            raise ValueError("OFFSETX_MAX_UPLOAD_BYTES is too small")
        if self.backup_max_bytes < 1024 * 1024:
            raise ValueError("OFFSETX_BACKUP_MAX_BYTES must be at least 1 MiB")
        if not 1 <= self.session_hours <= 24:
            raise ValueError("OFFSETX_SESSION_HOURS must be between 1 and 24")
        if self.unsubscribe_secret and len(self.unsubscribe_secret.encode("utf-8")) < 32:
            raise ValueError("OFFSETX_UNSUBSCRIBE_SECRET must contain at least 32 bytes")

        self.validate_storage()

    def validate_storage(self) -> None:
        if self.production:
            temporary_root = Path(tempfile.gettempdir()).resolve()
            if any(_inside(self.data_dir, path) for path in (temporary_root, Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))):
                raise ValueError(
                    "Production OFFSETX_DATA_DIR cannot live under the operating-system temporary directory"
                )
            if not _inside(self.database_path, self.data_dir):
                raise ValueError(
                    "Production OFFSETX_OUTREACH_DB must live under OFFSETX_DATA_DIR so one durable root owns local state"
                )
            for path in (self.export_dir, self.gmail_token, self.gmail_client_secrets):
                if path is not None and not _inside(path, self.data_dir):
                    raise ValueError("Production exports and Gmail files must live under OFFSETX_DATA_DIR")
            if os.getenv("OFFSETX_DATABASE_URL", "").strip():
                raise ValueError("This production topology requires all stores on the persistent local root; unset OFFSETX_DATABASE_URL")
            if not self.persistent_mount or not _inside(self.data_dir, self.persistent_mount) or self.data_dir.resolve() == self.persistent_mount.resolve():
                raise ValueError("Set OFFSETX_PERSISTENT_MOUNT to the mounted disk and put OFFSETX_DATA_DIR in a subdirectory")

    def verify_persistent_mount(self) -> None:
        if self.production and (not self.persistent_mount or not self.persistent_mount.is_mount()):
            raise ValueError("Persistent disk is not mounted. Attach OFFSETX_PERSISTENT_MOUNT before starting the production service")

    #: Where an auto-provisioned local token lives. Beside the data it protects.
    TOKEN_FILENAME = "local_api_token"

    def ensure_api_token(self) -> str:
        """Give a local install a token instead of an error.

        Nothing is generated when a token or a demo login is already configured,
        so an explicit choice is never overwritten.

        The file is `0600`. That is not theatre: anything able to read it can
        already open the SQLite database beside it, so this does not add a
        secret to protect — it closes the gap between "can read my files" and
        "can reach my API", which is the gap a browser extension, another user
        account, or a DNS-rebinding page sits in.
        """
        if self.api_token or self.demo_login_enabled or self.allow_unauthenticated:
            return self.api_token
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / self.TOKEN_FILENAME
        try:
            existing = path.read_text(encoding="utf-8").strip()
        except OSError:
            existing = ""
        if len(existing) >= 32:
            self.api_token = existing
            self.api_token_from_file = True
            return self.api_token
        token = secrets.token_urlsafe(32)
        # Create with the mode set, rather than creating then chmod-ing: between
        # those two calls the token is world-readable.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token)
        self.api_token = token
        self.api_token_from_file = True
        return token

    def reload_local_api_token(self) -> None:
        """Restore file-managed authentication with the workspace it protects."""
        if self.api_token_from_file:
            token = (self.data_dir / self.TOKEN_FILENAME).read_text(encoding="utf-8").strip()
            if len(token) < 32 or not token.isascii():
                raise ValueError("Restored local API token is invalid")
            self.api_token = token

    def host_allowlist(self) -> frozenset[str]:
        """Host header values this server answers to.

        A `Host` allowlist is the defence against DNS rebinding, and rebinding is
        the attack that makes "it only listens on localhost" untrue: a page can
        point a name it controls at 127.0.0.1 and reach the API with the
        browser's cooperation. CORS does not stop the request being made.
        """
        names = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}
        if self.host:
            names.add(self.host.strip().lower())
        names.update(self.allowed_hosts)
        if self.public_base_url:
            from urllib.parse import urlsplit

            public = urlsplit(self.public_base_url).hostname
            if public:
                names.add(public.lower())
        return frozenset(name for name in names if name)

    @property
    def demo_login_enabled(self) -> bool:
        return bool(self.demo_username and self.demo_password and self.session_secret)

    def prepare(self) -> None:
        self.verify_persistent_mount()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
