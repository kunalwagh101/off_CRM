from __future__ import annotations

import os
import secrets
import stat
from dataclasses import dataclass, field
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
    demo_username: str = ""
    demo_password: str = ""
    session_secret: str = ""
    session_hours: int = 8
    max_upload_bytes: int = 10 * 1024 * 1024
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
            port=int(os.getenv("PORT") or os.getenv("OFFSETX_WEB_PORT", "8766")),
            api_token=os.getenv("OFFSETX_LOCAL_API_TOKEN", "").strip(),
            demo_username=os.getenv("OFFSETX_DEMO_USERNAME", "").strip(),
            demo_password=os.getenv("OFFSETX_DEMO_PASSWORD", ""),
            session_secret=os.getenv("OFFSETX_SESSION_SECRET", ""),
            session_hours=int(os.getenv("OFFSETX_SESSION_HOURS", "8")),
            max_upload_bytes=int(
                os.getenv("OFFSETX_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
            ),
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
        if not 1 <= self.session_hours <= 24:
            raise ValueError("OFFSETX_SESSION_HOURS must be between 1 and 24")
        if self.unsubscribe_secret and len(self.unsubscribe_secret.encode("utf-8")) < 32:
            raise ValueError("OFFSETX_UNSUBSCRIBE_SECRET must contain at least 32 bytes")

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
            return self.api_token
        token = secrets.token_urlsafe(32)
        # Create with the mode set, rather than creating then chmod-ing: between
        # those two calls the token is world-readable.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token)
        self.api_token = token
        return token

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
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
