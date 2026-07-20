from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import requests

from .models import IncomingMessage, SendResult, parse_datetime, to_utc_iso, utc_now

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_SCOPES = (GMAIL_SEND_SCOPE, GMAIL_READONLY_SCOPE)
DEFAULT_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailError(RuntimeError):
    pass


@dataclass(slots=True)
class GmailOAuthConfig:
    client_id: str
    client_secret: str
    auth_uri: str = DEFAULT_AUTH_URI
    token_uri: str = DEFAULT_TOKEN_URI
    redirect_uri: str = "http://127.0.0.1:8765/callback"

    @classmethod
    def from_client_secrets(
        cls, path: Path | str, *, port: int = 8765
    ) -> "GmailOAuthConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        config = payload.get("installed") or payload.get("web")
        if not isinstance(config, dict):
            raise GmailError("Google client-secret JSON must contain installed or web settings")
        client_id = str(config.get("client_id", "")).strip()
        client_secret = str(config.get("client_secret", "")).strip()
        if not client_id or not client_secret:
            raise GmailError("Google client-secret JSON is missing client_id or client_secret")
        redirect_uris = list(config.get("redirect_uris") or [])
        redirect_uri = next(
            (
                uri
                for uri in redirect_uris
                if uri.startswith("http://127.0.0.1") or uri.startswith("http://localhost")
            ),
            f"http://127.0.0.1:{port}/callback",
        )
        parsed = urllib.parse.urlparse(redirect_uri)
        if parsed.hostname in {"127.0.0.1", "localhost"}:
            redirect_uri = f"http://127.0.0.1:{port}{parsed.path or '/callback'}"
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            auth_uri=str(config.get("auth_uri") or DEFAULT_AUTH_URI),
            token_uri=str(config.get("token_uri") or DEFAULT_TOKEN_URI),
            redirect_uri=redirect_uri,
        )


class GmailTokenStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise GmailError(f"Gmail token file not found: {self.path}")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise GmailError("Gmail token file is invalid")
        return payload

    def save(self, token: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(token, indent=2), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.path)


class GmailOAuthClient:
    def __init__(self, config: GmailOAuthConfig, *, session: Any | None = None):
        self.config = config
        self.session = session or requests.Session()

    def build_authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
    ) -> str:
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.config.auth_uri}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, *, code: str, code_verifier: str) -> dict[str, Any]:
        response = self.session.post(
            self.config.token_uri,
            data={
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            timeout=60,
        )
        if not response.ok:
            raise GmailError(f"Google OAuth token exchange failed: {response.text[:1000]}")
        payload = response.json()
        payload["expires_at"] = to_utc_iso(
            utc_now() + timedelta(seconds=int(payload.get("expires_in", 3600)))
        )
        return payload

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        response = self.session.post(
            self.config.token_uri,
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=60,
        )
        if not response.ok:
            raise GmailError(f"Google OAuth refresh failed: {response.text[:1000]}")
        payload = response.json()
        payload["refresh_token"] = payload.get("refresh_token") or refresh_token
        payload["expires_at"] = to_utc_iso(
            utc_now() + timedelta(seconds=int(payload.get("expires_in", 3600)))
        )
        return payload


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorize_interactive(
    *,
    client_secrets_path: Path | str,
    token_path: Path | str,
    port: int = 8765,
    open_browser: bool = True,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Run Google's installed-app OAuth flow using a temporary loopback callback."""

    config = GmailOAuthConfig.from_client_secrets(client_secrets_path, port=port)
    client = GmailOAuthClient(config)
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    received: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            received["code"] = params.get("code", [""])[0]
            received["state"] = params.get("state", [""])[0]
            received["error"] = params.get("error", [""])[0]
            body = b"OffsetX Gmail connection received. You can close this window."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = timeout_seconds
    url = client.build_authorization_url(state=state, code_challenge=challenge)
    if open_browser:
        webbrowser.open(url)
    else:
        print(url)
    server.handle_request()
    server.server_close()
    if received.get("error"):
        raise GmailError(f"Google OAuth failed: {received['error']}")
    if received.get("state") != state or not received.get("code"):
        raise GmailError("Google OAuth callback was missing or did not match the request")
    token = client.exchange_code(code=received["code"], code_verifier=verifier)
    GmailTokenStore(token_path).save(token)
    return token


class GmailMailProvider:
    API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(
        self,
        *,
        client_secrets_path: Path | str,
        token_path: Path | str,
        session: Any | None = None,
    ):
        self.session = session or requests.Session()
        self.oauth_config = GmailOAuthConfig.from_client_secrets(client_secrets_path)
        self.oauth_client = GmailOAuthClient(self.oauth_config, session=self.session)
        self.token_store = GmailTokenStore(token_path)

    def _access_token(self) -> str:
        token = self.token_store.load()
        expires_at = parse_datetime(token.get("expires_at"))
        if (
            not token.get("access_token")
            or not expires_at
            or expires_at <= utc_now() + timedelta(seconds=60)
        ):
            refresh_token = str(token.get("refresh_token", ""))
            if not refresh_token:
                raise GmailError("Gmail token has expired and has no refresh token")
            token = self.oauth_client.refresh(refresh_token)
            self.token_store.save(token)
        return str(token["access_token"])

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.session.request(
            method,
            f"{self.API_ROOT}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            params=params,
            json=payload,
            timeout=60,
        )
        if not response.ok:
            raise GmailError(f"Gmail API returned {response.status_code}: {response.text[:1000]}")
        data = response.json()
        if not isinstance(data, dict):
            raise GmailError("Gmail API returned invalid JSON")
        return data

    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: str = "",
        idempotency_key: str = "",
    ) -> SendResult:
        message = EmailMessage()
        message["To"] = to_email
        message["Subject"] = subject
        if idempotency_key:
            digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
            message["Message-ID"] = f"<offsetx-{digest}@offsetx.local>"
            message["X-OffsetX-Idempotency-Key"] = idempotency_key
        else:
            message["Message-ID"] = make_msgid(domain="offsetx.local")
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        data = self._request("POST", "messages/send", payload=payload)
        return SendResult(
            provider_message_id=str(data.get("id", "")),
            thread_id=str(data.get("threadId", thread_id)),
            internet_message_id=str(message["Message-ID"]),
            raw=data,
        )

    @staticmethod
    def _headers(payload: dict[str, Any]) -> dict[str, str]:
        return {
            str(item.get("name", "")).lower(): str(item.get("value", ""))
            for item in payload.get("headers", [])
            if isinstance(item, dict)
        }

    def list_replies(self, *, since: datetime, own_email: str) -> list[IncomingMessage]:
        timestamp = int(since.astimezone(timezone.utc).timestamp())
        query = f"after:{timestamp} -from:{own_email}"
        message_refs: list[dict[str, Any]] = []
        page_token = ""
        while len(message_refs) < 500:
            params: dict[str, Any] = {"q": query, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token
            listing = self._request("GET", "messages", params=params)
            message_refs.extend(
                item for item in listing.get("messages", []) if isinstance(item, dict)
            )
            page_token = str(listing.get("nextPageToken", ""))
            if not page_token:
                break

        replies: list[IncomingMessage] = []
        for item in message_refs[:500]:
            message_id = str(item.get("id", ""))
            if not message_id:
                continue
            data = self._request(
                "GET",
                f"messages/{message_id}",
                params={
                    "format": "metadata",
                    "metadataHeaders": ["From", "To", "Subject", "Date", "Message-ID"],
                },
            )
            headers = self._headers(data.get("payload") or {})
            from_email = parseaddr(headers.get("from", ""))[1].lower()
            if not from_email or from_email == own_email.lower():
                continue
            received_at = utc_now()
            internal_date = str(data.get("internalDate", ""))
            if internal_date.isdigit():
                received_at = datetime.fromtimestamp(
                    int(internal_date) / 1000, tz=timezone.utc
                )
            elif headers.get("date"):
                try:
                    parsed = parsedate_to_datetime(headers["date"])
                    received_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pass
            replies.append(
                IncomingMessage(
                    provider_message_id=message_id,
                    thread_id=str(data.get("threadId", "")),
                    from_email=from_email,
                    subject=headers.get("subject", ""),
                    body_preview=str(data.get("snippet", "")),
                    received_at=received_at,
                    internet_message_id=headers.get("message-id", ""),
                    raw=data,
                )
            )
        return replies


class LocalOutboxProvider:
    """Safe local provider used before Gmail is enabled."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.outbox = self.root / "outbox"
        self.inbox = self.root / "inbox"
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.inbox.mkdir(parents=True, exist_ok=True)

    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: str = "",
        idempotency_key: str = "",
    ) -> SendResult:
        if idempotency_key:
            digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
            path = self.outbox / f"{digest}.json"
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                return SendResult(
                    provider_message_id=str(existing["id"]),
                    thread_id=str(existing["thread_id"]),
                    internet_message_id=str(existing["internet_message_id"]),
                    raw={"local_path": str(path), "replayed": True},
                )
        else:
            path = self.outbox / f"local-{uuid.uuid4()}.json"
        provider_message_id = f"local-{uuid.uuid4()}"
        thread_id = thread_id or f"thread-{uuid.uuid4()}"
        internet_message_id = f"<{provider_message_id}@offsetx.local>"
        payload = {
            "id": provider_message_id,
            "thread_id": thread_id,
            "internet_message_id": internet_message_id,
            "idempotency_key": idempotency_key,
            "to": to_email,
            "subject": subject,
            "body": body,
            "in_reply_to": in_reply_to,
            "references": references,
            "created_at": to_utc_iso(),
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return SendResult(
            provider_message_id=provider_message_id,
            thread_id=thread_id,
            internet_message_id=internet_message_id,
            raw={"local_path": str(path)},
        )

    def list_replies(self, *, since: datetime, own_email: str) -> list[IncomingMessage]:
        replies: list[IncomingMessage] = []
        for path in sorted(self.inbox.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            received_at = parse_datetime(payload.get("received_at")) or utc_now()
            if received_at < since:
                continue
            replies.append(
                IncomingMessage(
                    provider_message_id=str(payload.get("id") or f"local-reply-{path.stem}"),
                    thread_id=str(payload.get("thread_id", "")),
                    from_email=str(payload.get("from", "")),
                    subject=str(payload.get("subject", "")),
                    body_preview=str(payload.get("body", "")),
                    received_at=received_at,
                    internet_message_id=str(payload.get("message_id", "")),
                    raw={"local_path": str(path)},
                )
            )
        return replies
