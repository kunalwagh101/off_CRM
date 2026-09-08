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


SESSION_COOKIE = "offsetx_crm_session"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    username: str
    expires_at: int


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
        return SessionIdentity(username=username, expires_at=expires_at)


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
