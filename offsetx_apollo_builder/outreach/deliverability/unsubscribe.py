from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .store import DeliverabilityStore


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class UnsubscribeService:
    def __init__(
        self,
        store: DeliverabilityStore,
        *,
        secret: bytes,
        public_base_url: str,
    ):
        if len(secret) < 32:
            raise ValueError("Unsubscribe signing secret must contain at least 32 bytes")
        self.store = store
        self.secret = secret
        self.public_base_url = public_base_url.rstrip("/")
        if self.public_base_url:
            parsed = urlparse(self.public_base_url)
            local = parsed.hostname in {"127.0.0.1", "localhost", "testserver"}
            if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
                raise ValueError("Public unsubscribe URL must use HTTPS")
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Public unsubscribe URL is invalid")

    @property
    def available(self) -> bool:
        return bool(self.public_base_url)

    @classmethod
    def from_path(
        cls,
        store: DeliverabilityStore,
        path: Path,
        *,
        public_base_url: str,
        configured_secret: str = "",
    ) -> "UnsubscribeService":
        if configured_secret:
            secret = configured_secret.encode("utf-8")
        elif path.exists():
            secret = path.read_bytes()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            generated = secrets.token_bytes(32)
            temporary = path.with_name(
                f".{path.name}.{secrets.token_hex(8)}.tmp"
            )
            temporary.write_bytes(generated)
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            try:
                # A hard link publishes the fully written inode without
                # replacing another web/worker process's winning secret.
                os.link(temporary, path)
            except FileExistsError:
                pass
            finally:
                temporary.unlink(missing_ok=True)
            secret = path.read_bytes()
        return cls(store, secret=secret, public_base_url=public_base_url)

    def _signature(self, token_id: str) -> str:
        return _b64(hmac.new(self.secret, token_id.encode("ascii"), hashlib.sha256).digest())

    def issue(self, *, email: str, campaign_id: str, stream: str) -> str:
        if not self.available:
            raise ValueError("A public base URL is required for unsubscribe links")
        token_id = str(uuid.uuid4())
        self.store.create_unsubscribe_token(
            token_id, email=email, campaign_id=campaign_id, stream=stream
        )
        token = f"{token_id}.{self._signature(token_id)}"
        return f"{self.public_base_url}/api/v1/email/unsubscribe/{token}"

    def verify(self, token: str) -> str:
        try:
            token_id, supplied = token.split(".", 1)
            uuid.UUID(token_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Unsubscribe link is invalid or expired") from exc
        if not hmac.compare_digest(supplied, self._signature(token_id)):
            raise ValueError("Unsubscribe link is invalid or expired")
        return token_id

    def unsubscribe(self, token: str) -> dict[str, str]:
        token_id = self.verify(token)
        record = self.store.use_unsubscribe_token(token_id)
        email = str(record["email"])
        self.store.set_permission(
            email,
            status="denied",
            basis="recipient_unsubscribe",
            source="one_click_unsubscribe",
            evidence=f"token:{token_id}",
        )
        self.store.suppress(
            email,
            reason="unsubscribe",
            source="one_click_unsubscribe",
        )
        return {
            "email": email,
            "status": "unsubscribed",
            "token_id": token_id,
            "campaign_id": str(record.get("campaign_id") or ""),
            "occurred_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }

    @staticmethod
    def prepare_content(
        body: str, *, url: str, include_list_headers: bool
    ) -> tuple[str, dict[str, str]]:
        marker = "Manage email preferences:"
        rendered = body.rstrip()
        if marker not in rendered:
            rendered += f"\n\n---\n{marker} {url}"
        headers: dict[str, str] = {}
        if include_list_headers:
            headers = {
                "List-Unsubscribe": f"<{url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        return rendered, headers
