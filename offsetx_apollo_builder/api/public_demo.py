"""A disposable visitor installation, never a second login over private CRM data."""
from __future__ import annotations

import os
import hashlib
import re

from ..outreach.models import ContactInput


def validate_layout(settings) -> None:
    if not settings.public_demo:
        return
    if (settings.production or settings.api_token or settings.allow_unauthenticated
            or os.getenv("OFFSETX_DATABASE_URL", "").strip() or settings.secrets_key
            or settings.gmail_client_secrets or settings.own_email
            or not settings.demo_login_enabled):
        raise ValueError("Public demo requires dedicated storage, a demo login, and no private integrations or API token")
    root = settings.data_dir.resolve()
    for path in (settings.database_path, settings.export_dir, settings.gmail_token):
        if path is not None and not path.resolve().is_relative_to(root):
            raise ValueError("Public demo requires dedicated storage for every data file")


def prepare(settings) -> None:
    if not settings.public_demo:
        return
    validate_layout(settings)
    root = settings.data_dir
    marker = root / "public_demo_installation"
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise ValueError("Public demo requires an empty dedicated data folder; do not reuse private or QA data")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("Disposable sample data only.\n", encoding="utf-8")


def workspace_for(session_token: str) -> str:
    """One browser session owns its AI state, even with a shared public login."""
    return "demo-" + hashlib.sha256(session_token.encode("utf-8")).hexdigest()[:40]


def request_allowed(method: str, path: str) -> bool:
    if method == "POST" and path in {"/api/v1/auth/login", "/api/v1/auth/logout"}:
        return True
    ai_reads = {
        "/api/v1/ai/providers", "/api/v1/ai/modes", "/api/v1/ai/projects",
        "/api/v1/ai/chats", "/api/v1/ai/egress-log", "/api/v1/ai/egress-log/stats",
        "/api/v1/ai/failure-kinds",
    }
    if method in {"GET", "HEAD"}:
        if not path.startswith("/api/"):
            return True
        return path in ai_reads | {
            "/api/v1/auth/session", "/api/v1/meta", "/api/v1/dashboard",
            "/api/v1/settings/status", "/api/v1/campaign-kinds", "/api/v1/templates",
        } or bool(re.fullmatch(r"/api/v1/ai/chats/[^/]+/messages", path)) or bool(
            re.fullmatch(r"/api/v1/ai/egress-log/[^/]+", path)
        ) or any(path == root or path.startswith(root + "/") for root in (
            "/api/v1/campaigns", "/api/v1/crm", "/api/v1/sales",
        ))
    if method == "POST":
        return path in {
            "/api/v1/ai/run", "/api/v1/ai/plan", "/api/v1/ai/image", "/api/v1/ai/chats",
            "/api/v1/ai/projects", "/api/v1/ai/workspace",
        } or bool(re.fullmatch(
            r"/api/v1/ai/providers/[^/]+/(connect|disconnect|discover-models|trust|override|balance)", path
        )) or bool(re.fullmatch(r"/api/v1/ai/chats/[^/]+/(messages|move)", path))
    if method == "PATCH":
        return bool(re.fullmatch(r"/api/v1/ai/chats/[^/]+", path))
    if method == "DELETE":
        return bool(re.fullmatch(r"/api/v1/ai/(chats|projects)/[^/]+", path))
    return False


def seed(engine) -> None:
    store = engine.store
    # One transaction makes a failed/retried startup either complete or empty.
    with store.transaction():
        if store.list_campaigns()[0]:
            return
        campaign_id = store.create_campaign(
            name="Visitor demo · sample outreach", daily_send_limit=10,
            initial_status="paused",
        )
        for name, email, company, title in (
            ("Anita Rao", "anita@example.com", "Example Exports", "Trade Compliance Lead"),
            ("Rohan Shah", "rohan@example.com", "Sample Steel", "Operations Manager"),
            ("Meera Patil", "meera@example.com", "Demo Aluminium", "Sustainability Lead"),
        ):
            contact_id = store.upsert_contact(ContactInput(
                full_name=name, email=email, company=company, title=title,
                category="CBAM / Trade Compliance", notes="Fictional visitor demo contact.",
            ))
            store.add_contact_to_campaign(campaign_id, contact_id)
