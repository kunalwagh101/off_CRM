from __future__ import annotations

import html
import secrets
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..outreach.gmail import (
    DEFAULT_SCOPES,
    GmailError,
    GmailOAuthClient,
    GmailOAuthConfig,
    GmailTokenStore,
    _pkce_pair,
)


class GmailConnectorManager:
    """Browser-safe Gmail OAuth coordinator. Tokens remain inside the mail module."""

    def __init__(
        self,
        *,
        client_secrets_path: Path | None,
        token_path: Path | None,
        own_email: str = "",
    ):
        self.client_secrets_path = client_secrets_path
        self.token_path = token_path
        self.own_email = own_email
        self._pending: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        configured = bool(
            self.client_secrets_path
            and self.client_secrets_path.exists()
            and self.token_path
        )
        connected = bool(configured and self.token_path and self.token_path.exists())
        return {
            "configured": configured,
            "connected": connected,
            "account": self.own_email if connected else "",
            "scopes": list(DEFAULT_SCOPES) if connected else [],
            "token_location": "mail_module_only" if connected else "",
            "ai_access": False,
            "reply_sync_boundary": "CRM-owned threads only",
        }

    @staticmethod
    def _origin(request: Request) -> str:
        candidate = (request.headers.get("origin") or "").strip()
        if not candidate:
            forwarded = request.headers.get("x-forwarded-proto", "").strip()
            scheme = forwarded or request.url.scheme
            candidate = f"{scheme}://{request.headers.get('host') or request.url.netloc}"
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise GmailError("CRM origin is invalid")
        if parsed.scheme == "http" and parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise GmailError("Hosted Gmail OAuth requires HTTPS")
        return f"{parsed.scheme}://{parsed.netloc}"

    def start(self, request: Request) -> dict[str, str]:
        if not self.client_secrets_path or not self.client_secrets_path.exists():
            raise GmailError(
                "Add a Google OAuth client-secret JSON path before connecting Gmail"
            )
        if not self.token_path:
            raise GmailError("Gmail token path is not configured")
        origin = self._origin(request)
        redirect_uri = f"{origin}/api/v1/connectors/gmail/callback"
        config = GmailOAuthConfig.from_client_secrets(self.client_secrets_path)
        config.redirect_uri = redirect_uri
        state = secrets.token_urlsafe(32)
        verifier, challenge = _pkce_pair()
        with self._lock:
            self._pending = {
                key: value
                for key, value in self._pending.items()
                if float(value.get("created_at", 0)) > time.time() - 600
            }
            self._pending[state] = {
                "verifier": verifier,
                "created_at": time.time(),
                "redirect_uri": redirect_uri,
                "origin": origin,
            }
        url = GmailOAuthClient(config).build_authorization_url(
            state=state,
            code_challenge=challenge,
            scopes=DEFAULT_SCOPES,
        )
        return {"authorization_url": url, "state": state}

    def callback(self, *, state: str, code: str, error: str = "") -> tuple[str, str]:
        with self._lock:
            pending = self._pending.pop(state, None)
        if not pending or float(pending.get("created_at", 0)) < time.time() - 600:
            raise GmailError("Google OAuth state is missing or expired")
        if error:
            raise GmailError(f"Google OAuth failed: {error}")
        if not code:
            raise GmailError("Google OAuth callback did not contain a code")
        if not self.client_secrets_path or not self.token_path:
            raise GmailError("Gmail connector is not configured")
        config = GmailOAuthConfig.from_client_secrets(self.client_secrets_path)
        config.redirect_uri = str(pending["redirect_uri"])
        token = GmailOAuthClient(config).exchange_code(
            code=code, code_verifier=str(pending["verifier"])
        )
        GmailTokenStore(self.token_path).save(token)
        return "Gmail connected to OFF_CRM.", str(pending["origin"])

    def disconnect(self) -> dict[str, bool]:
        removed = False
        if self.token_path and self.token_path.exists():
            self.token_path.unlink()
            removed = True
        return {"disconnected": True, "token_removed": removed}


def build_connectors_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/connectors", tags=["Connectors"])

    @router.get("")
    def connectors(request: Request) -> dict[str, Any]:
        return {
            "gmail": request.app.state.gmail_connector.status(),
            "ai_providers": request.app.state.off_ai.broker.list_models(),
        }

    @router.post("/gmail/start")
    def gmail_start(request: Request) -> dict[str, str]:
        return request.app.state.gmail_connector.start(request)

    @router.get("/gmail/callback", response_class=HTMLResponse)
    def gmail_callback(
        request: Request, state: str = "", code: str = "", error: str = ""
    ) -> HTMLResponse:
        try:
            message, origin = request.app.state.gmail_connector.callback(
                state=state, code=code, error=error
            )
            success = True
        except Exception as exc:
            message = str(exc)
            origin = "*"
            success = False
        safe_message = html.escape(message)
        safe_origin = origin.replace("\\", "\\\\").replace("'", "\\'")
        body = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>OFF_CRM Gmail</title>
<body style="font:16px system-ui;padding:32px;max-width:620px;margin:auto">
<h1>{'Connected' if success else 'Connection failed'}</h1>
<p>{safe_message}</p>
<script>
if (window.opener) {{
  window.opener.postMessage(
    {{type: 'off-crm-gmail-connector', success: {str(success).lower()}}},
    '{safe_origin}'
  );
  window.setTimeout(() => window.close(), 800);
}}
</script>
</body></html>"""
        return HTMLResponse(body, status_code=200 if success else 400)

    @router.post("/gmail/disconnect")
    def gmail_disconnect(request: Request) -> dict[str, bool]:
        return request.app.state.gmail_connector.disconnect()

    return router
