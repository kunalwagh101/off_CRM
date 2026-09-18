from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Mapping


SESSION_COOKIE = "offsetx_crm_session"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    username: str
    expires_at: int
    workspace_id: str = "local"


class DemoSessionAuth:
    """One stateless login bound to exactly one workspace.

    The class name stays for backwards compatibility with existing single-user
    deployments and tests.  The workspace claim is signed into the cookie, so a
    caller cannot switch workspaces by changing a header or form value.
    """

    def __init__(
        self,
        *,
        username: str,
        password: str,
        session_secret: str,
        session_hours: int,
        workspace_id: str = "local",
    ) -> None:
        self.username = username
        self.workspace_id = str(workspace_id or "local").strip().lower()
        self._password = password
        self._secret = session_secret.encode("utf-8")
        self.session_seconds = session_hours * 60 * 60

    @property
    def enabled(self) -> bool:
        return bool(self.username and self._password and self._secret and self.workspace_id)

    def authenticate(self, username: str, password: str) -> bool:
        """Both comparisons always run, so the answer takes the same time.

        `and` short-circuits: chaining the two `compare_digest` calls meant a
        wrong username returned before the password was ever compared, and the
        difference is measurable. The bitwise `&` is deliberate.
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
            raise RuntimeError("Workspace login is not configured")
        current = int(time.time()) if now is None else now
        expires_at = current + self.session_seconds
        payload = (
            f"{self.username}\n{self.workspace_id}\n{expires_at}\n"
            f"{secrets.token_urlsafe(18)}"
        ).encode("utf-8")
        encoded = _encode(payload)
        signature = _encode(
            hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
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
            parts = _decode(encoded).decode("utf-8").split("\n")
            if len(parts) == 4:
                username, workspace_id, expires_text, _nonce = parts
            elif len(parts) == 3:
                # Cookies issued before workspace-bound sessions existed were
                # local-only. Accept them only for the legacy local login.
                username, expires_text, _nonce = parts
                workspace_id = "local"
            else:
                return None
            expires_at = int(expires_text)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return None
        user_ok = hmac.compare_digest(username, self.username)
        workspace_ok = hmac.compare_digest(workspace_id, self.workspace_id)
        current = int(time.time()) if now is None else now
        if not (user_ok & workspace_ok) or expires_at <= current:
            return None
        return SessionIdentity(
            username=username,
            expires_at=expires_at,
            workspace_id=workspace_id,
        )


class WorkspaceSessionAuth:
    """Many workspace logins behind one signed-session interface.

    Usernames are unique across configured workspaces. Authentication evaluates
    every configured login instead of returning on the first username match, so
    adding workspaces does not reintroduce the username timing oracle fixed in
    `DemoSessionAuth`.
    """

    def __init__(
        self,
        *,
        logins: Mapping[str, tuple[str, str]],
        session_secret: str,
        session_hours: int,
    ) -> None:
        self._auth_by_workspace = {
            str(workspace_id).strip().lower(): DemoSessionAuth(
                username=str(credentials[0]),
                password=str(credentials[1]),
                session_secret=session_secret,
                session_hours=session_hours,
                workspace_id=str(workspace_id).strip().lower(),
            )
            for workspace_id, credentials in logins.items()
        }

    @property
    def enabled(self) -> bool:
        return bool(self._auth_by_workspace) and all(
            auth.enabled for auth in self._auth_by_workspace.values()
        )

    @property
    def workspaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._auth_by_workspace))

    def authenticate(self, username: str, password: str) -> SessionIdentity | None:
        matched: SessionIdentity | None = None
        for workspace_id, auth in self._auth_by_workspace.items():
            if auth.authenticate(username, password):
                matched = SessionIdentity(
                    username=auth.username,
                    expires_at=0,
                    workspace_id=workspace_id,
                )
        return matched

    def issue(self, identity: SessionIdentity, *, now: int | None = None) -> str:
        auth = self._auth_by_workspace.get(identity.workspace_id)
        if auth is None or not hmac.compare_digest(auth.username, identity.username):
            raise RuntimeError("Workspace login is not configured")
        return auth.issue(now=now)

    def verify(self, token: str, *, now: int | None = None) -> SessionIdentity | None:
        # Every workspace uses the same deployment signing secret, but each
        # verifier also checks its signed workspace claim. Looping therefore
        # cannot turn a valid cookie for A into a valid cookie for B.
        for auth in self._auth_by_workspace.values():
            identity = auth.verify(token, now=now)
            if identity is not None:
                return identity
        return None


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
        """Drop the key once its window is empty, not just the timestamps in it."""
        if not attempts:
            self._attempts.pop(key, None)
