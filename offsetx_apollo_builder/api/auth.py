from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
import re
from pathlib import Path
from collections import deque
from dataclasses import dataclass


SESSION_COOKIE = "offsetx_crm_session"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    username: str
    workspace_id: str = "local"
    expires_at: int = 0
    session_version: int = 1


_WORKSPACE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_USERNAME = re.compile(r"^[^\\x00\\r\\n]{1,100}$")
_PASSWORD_MIN = 12
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


class WorkspaceAuthError(ValueError):
    """Workspace account configuration is invalid."""


class WorkspaceAuthStore:
    """Persistent workspace-bound logins and signed sessions.

    Passwords are scrypt hashes. Session cookies contain only username,
    workspace id, expiry, session version and a nonce, signed with the install's
    session secret. Bumping session_version invalidates every old cookie for an
    account without storing server-side sessions.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS workspace_users (
        username TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL UNIQUE,
        password_salt BLOB NOT NULL,
        password_hash BLOB NOT NULL,
        session_version INTEGER NOT NULL DEFAULT 1,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    """

    def __init__(self, path: Path | str, *, session_secret: str, session_hours: int) -> None:
        if not session_secret or len(session_secret) < 32:
            raise WorkspaceAuthError("Workspace sessions require a 32+ character session secret")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = session_secret.encode("utf-8")
        self.session_seconds = int(session_hours) * 60 * 60
        with self._connection() as conn:
            conn.executescript(self.SCHEMA)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def _workspace(value: str) -> str:
        workspace = str(value or "").strip().lower()
        if not _WORKSPACE_ID.fullmatch(workspace):
            raise WorkspaceAuthError(
                "workspace_id must be 1-64 lowercase letters, digits, '-' or '_'"
            )
        return workspace

    @staticmethod
    def _username(value: str) -> str:
        username = str(value or "").strip()
        if not _USERNAME.fullmatch(username):
            raise WorkspaceAuthError("username must be 1-100 characters on one line")
        return username

    @staticmethod
    def _password(value: str) -> str:
        password = str(value or "")
        if len(password) < _PASSWORD_MIN:
            raise WorkspaceAuthError(
                f"password must contain at least {_PASSWORD_MIN} characters"
            )
        if "\x00" in password:
            raise WorkspaceAuthError("password contains an invalid character")
        return password

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=32,
        )

    @property
    def enabled(self) -> bool:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM workspace_users WHERE enabled = 1 LIMIT 1"
            ).fetchone()
        return row is not None

    def create(
        self,
        *,
        username: str,
        workspace_id: str,
        password: str,
    ) -> SessionIdentity:
        user = self._username(username)
        workspace = self._workspace(workspace_id)
        secret = self._password(password)
        salt = secrets.token_bytes(16)
        digest = self._derive(secret, salt)
        now = int(time.time())
        try:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO workspace_users(
                        username, workspace_id, password_salt, password_hash,
                        session_version, enabled, created_at, updated_at
                    ) VALUES(?,?,?,?,1,1,?,?)
                    """,
                    (user, workspace, salt, digest, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise WorkspaceAuthError(
                "username or workspace_id already exists"
            ) from exc
        return SessionIdentity(user, workspace, 0, 1)

    def bootstrap(self, *, username: str, password: str, workspace_id: str = "local") -> None:
        """Create the legacy configured login once; never overwrite persisted auth."""
        if not (str(username or "").strip() and str(password or "")):
            return
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT 1 FROM workspace_users WHERE username = ? OR workspace_id = ?",
                (str(username).strip(), self._workspace(workspace_id)),
            ).fetchone()
        if existing is None:
            self.create(username=username, workspace_id=workspace_id, password=password)

    def list_accounts(self) -> list[dict[str, object]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT username, workspace_id, enabled, created_at, updated_at
                FROM workspace_users ORDER BY workspace_id, username
                """
            ).fetchall()
        return [
            {
                "username": str(row["username"]),
                "workspace_id": str(row["workspace_id"]),
                "enabled": bool(row["enabled"]),
                "created_at": int(row["created_at"]),
                "updated_at": int(row["updated_at"]),
            }
            for row in rows
        ]

    def authenticate(self, username: str, password: str) -> SessionIdentity | None:
        user = str(username or "").strip()
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT username, workspace_id, password_salt, password_hash,
                       session_version, enabled
                FROM workspace_users WHERE username = ?
                """,
                (user,),
            ).fetchone()
        # Unknown usernames still pay the scrypt cost, avoiding a cheap username oracle.
        salt = bytes(row["password_salt"]) if row is not None else b"\x00" * 16
        expected = bytes(row["password_hash"]) if row is not None else b"\x00" * 32
        try:
            actual = self._derive(str(password or ""), salt)
        except (ValueError, TypeError):
            actual = b"\xff" * 32
        password_ok = hmac.compare_digest(actual, expected)
        enabled = bool(row["enabled"]) if row is not None else False
        if row is None or not (password_ok & enabled):
            return None
        return SessionIdentity(
            username=str(row["username"]),
            workspace_id=str(row["workspace_id"]),
            expires_at=0,
            session_version=int(row["session_version"]),
        )

    def issue(self, identity: SessionIdentity, *, now: int | None = None) -> str:
        current = int(time.time()) if now is None else int(now)
        expires_at = current + self.session_seconds
        payload = (
            f"{identity.username}\n{identity.workspace_id}\n{expires_at}\n"
            f"{identity.session_version}\n{secrets.token_urlsafe(18)}"
        ).encode("utf-8")
        encoded = _encode(payload)
        signature = _encode(
            hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}"

    def verify(self, token: str, *, now: int | None = None) -> SessionIdentity | None:
        if not token:
            return None
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = _encode(
                hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            username, workspace, expires_text, version_text, _nonce = (
                _decode(encoded).decode("utf-8").split("\n", 4)
            )
            expires_at = int(expires_text)
            version = int(version_text)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return None
        current = int(time.time()) if now is None else int(now)
        if expires_at <= current:
            return None
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT workspace_id, session_version, enabled
                FROM workspace_users WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None or not bool(row["enabled"]):
            return None
        if not hmac.compare_digest(str(row["workspace_id"]), workspace):
            return None
        if int(row["session_version"]) != version:
            return None
        return SessionIdentity(username, workspace, expires_at, version)

    def set_password(self, username: str, password: str) -> None:
        secret = self._password(password)
        salt = secrets.token_bytes(16)
        digest = self._derive(secret, salt)
        now = int(time.time())
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE workspace_users
                SET password_salt = ?, password_hash = ?,
                    session_version = session_version + 1, updated_at = ?
                WHERE username = ?
                """,
                (salt, digest, now, str(username).strip()),
            )
        if cursor.rowcount != 1:
            raise WorkspaceAuthError("workspace account not found")

    def set_enabled(self, username: str, enabled: bool) -> None:
        now = int(time.time())
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE workspace_users
                SET enabled = ?, session_version = session_version + 1, updated_at = ?
                WHERE username = ?
                """,
                (int(bool(enabled)), now, str(username).strip()),
            )
        if cursor.rowcount != 1:
            raise WorkspaceAuthError("workspace account not found")


class DemoSessionAuth:
    """Small, stateless session layer for a single-user demo deployment."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        session_secret: str,
        session_hours: int,
    ) -> None:
        self.username = username
        self._password = password
        self._secret = session_secret.encode("utf-8")
        self.session_seconds = session_hours * 60 * 60

    @property
    def enabled(self) -> bool:
        return bool(self.username and self._password and self._secret)

    def authenticate(self, username: str, password: str) -> bool:
        """Both comparisons always run, so the answer takes the same time.

        `and` short-circuits: chaining the two `compare_digest` calls meant a
        wrong username returned before the password was ever compared, and the
        difference is measurable. That is a username oracle — an attacker learns
        which name is real from the timing, and the constant-time comparison
        underneath it is wasted. The `&` is deliberate and must stay.
        """
        if not self.enabled:
            return False
        user_ok = hmac.compare_digest(
            username.encode("utf-8"), self.username.encode("utf-8")
        )
        password_ok = hmac.compare_digest(
            password.encode("utf-8"), self._password.encode("utf-8")
        )
        return user_ok & password_ok

    def issue(self, *, now: int | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("Demo login is not configured")
        current = int(time.time()) if now is None else now
        expires_at = current + self.session_seconds
        payload = f"{self.username}\n{expires_at}\n{secrets.token_urlsafe(18)}".encode("utf-8")
        encoded = _encode(payload)
        signature = _encode(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def verify(self, token: str, *, now: int | None = None) -> SessionIdentity | None:
        if not self.enabled or not token:
            return None
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = _encode(
                hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            username, expires_text, _nonce = _decode(encoded).decode("utf-8").split("\n", 2)
            expires_at = int(expires_text)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return None
        if not hmac.compare_digest(username, self.username):
            return None
        current = int(time.time()) if now is None else now
        if expires_at <= current:
            return None
        return SessionIdentity(username=username, workspace_id="local", expires_at=expires_at)


class LoginAttemptLimiter:
    def __init__(self, *, maximum: int = 5, window_seconds: int = 5 * 60) -> None:
        self.maximum = maximum
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allowed(self, key: str, *, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        with self._lock:
            attempts = self._attempts.setdefault(key, deque())
            self._prune(attempts, current)
            allowed = len(attempts) < self.maximum
            self._forget_if_empty(key, attempts)
            return allowed

    def failed(self, key: str, *, now: float | None = None) -> None:
        current = now if now is not None else time.monotonic()
        with self._lock:
            attempts = self._attempts.setdefault(key, deque())
            self._prune(attempts, current)
            attempts.append(current)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def _prune(self, attempts: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

    def _forget_if_empty(self, key: str, attempts: deque[float]) -> None:
        """Drop the key once its window is empty, not just the timestamps in it.

        Pruning emptied the deque and left the key behind, so the dict only ever
        grew. The key is a client address: one IPv6 /64 — a single residential
        allocation — is 18 quintillion of them, so the growth is bounded only by
        memory. Measured at 50,000 retained keys with every window long expired.
        """
        if not attempts:
            self._attempts.pop(key, None)
