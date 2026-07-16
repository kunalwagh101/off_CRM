from __future__ import annotations

import hmac
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..locked_categories import LOCKED_CATEGORIES
from ..outreach.engine import OutreachEngine
from ..outreach.gmail import GmailMailProvider, LocalOutboxProvider
from ..outreach.models import ProviderConfig, ROUTES, utc_now
from ..outreach.providers import create_provider
from .config import AppSettings
from .schemas import (
    CampaignCreate,
    CampaignUpdate,
    ContactUpdate,
    DraftApprove,
    DraftEdit,
    DraftGenerate,
    ReplySyncRequest,
    SendRequest,
    TemplateImport,
)


API_PREFIX = "/api/v1"
LIVE_SEND_CONFIRMATION = "SEND LIVE EMAILS"
CONTACT_UPLOAD_TYPES = {".csv", ".xlsx", ".xls"}
EXPERT_UPLOAD_TYPES = {".md", ".txt"}


class CampaignLocks:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def hold(self, campaign_id: str) -> Iterator[None]:
        with self._guard:
            lock = self._locks.setdefault(campaign_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="A campaign operation is already running")
        try:
            yield
        finally:
            lock.release()


def _engine(request: Request) -> OutreachEngine:
    return request.app.state.engine


def _settings(request: Request) -> AppSettings:
    return request.app.state.settings


def _mail_provider(settings: AppSettings, mode: str, confirmation: str = "") -> Any:
    if mode == "local":
        return LocalOutboxProvider(settings.data_dir / "mail")
    if confirmation != LIVE_SEND_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f"Gmail live send requires confirmation: {LIVE_SEND_CONFIRMATION}",
        )
    if not settings.gmail_client_secrets or not settings.gmail_token:
        raise HTTPException(status_code=503, detail="Gmail OAuth paths are not configured")
    if not settings.gmail_client_secrets.exists() or not settings.gmail_token.exists():
        raise HTTPException(status_code=503, detail="Gmail is not connected on this device")
    if not settings.own_email:
        raise HTTPException(status_code=503, detail="OFFSETX_OWN_EMAIL is required for Gmail")
    return GmailMailProvider(
        client_secrets_path=settings.gmail_client_secrets,
        token_path=settings.gmail_token,
    )


async def _read_upload(
    upload: UploadFile, *, allowed: set[str], max_bytes: int
) -> tuple[str, bytes]:
    filename = Path(upload.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=415, detail="Unsupported file type. Allowed: " + ", ".join(sorted(allowed))
        )
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return filename, content


def _temporary_upload(filename: str, content: bytes) -> Path:
    suffix = Path(filename).suffix.lower()
    with NamedTemporaryFile(prefix="offsetx-upload-", suffix=suffix, delete=False) as handle:
        handle.write(content)
        return Path(handle.name)


def _idempotent(
    engine: OutreachEngine, scope: str, key: str | None, operation: Any
) -> dict[str, Any]:
    if key:
        cached = engine.store.get_idempotency(scope, key)
        if cached is not None:
            return {**cached, "idempotent_replay": True}
    result = operation()
    if key:
        engine.store.save_idempotency(scope, key, result)
    return result


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved = settings or AppSettings.from_env()
    resolved.validate()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.prepare()
        app.state.settings = resolved
        app.state.engine = OutreachEngine(resolved.database_path)
        app.state.campaign_locks = CampaignLocks()
        yield
        app.state.engine.close()

    app = FastAPI(
        title="OffsetX Local Outreach CRM",
        version="0.5.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8766",
            "http://localhost:8766",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-OffsetX-Token"],
    )

    @app.middleware("http")
    async def local_security(request: Request, call_next: Any):
        if resolved.api_token and request.url.path.startswith("/api/") and request.url.path not in {
            "/api/v1/meta", "/api/openapi.json", "/api/docs"
        }:
            authorization = request.headers.get("authorization", "")
            supplied = request.headers.get("x-offsetx-token", "")
            if authorization.lower().startswith("bearer "):
                supplied = authorization[7:].strip()
            if not hmac.compare_digest(supplied, resolved.api_token):
                return JSONResponse(status_code=401, content={"detail": "Local API token required"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' http://127.0.0.1:8766 http://localhost:8766; "
            "img-src 'self' data:; font-src 'self'"
        )
        return response

    @app.exception_handler(KeyError)
    async def not_found(_: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc).strip("'")})

    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(request: Request) -> dict[str, str]:
        _engine(request).store.connection.execute("SELECT 1").fetchone()
        return {"status": "ready"}

    @app.get(f"{API_PREFIX}/meta")
    def meta() -> dict[str, Any]:
        return {
            "name": "OffsetX Local Outreach CRM",
            "version": "0.5.0",
            "categories": list(LOCKED_CATEGORIES),
            "routes": list(ROUTES),
            "provider_types": [
                "openai", "anthropic", "openai_compatible", "template_engine_http"
            ],
            "mail_modes": ["local", "gmail"],
            "live_send_confirmation": LIVE_SEND_CONFIRMATION,
        }

    @app.get(f"{API_PREFIX}/dashboard")
    def dashboard(request: Request) -> dict[str, Any]:
        return _engine(request).store.dashboard_summary()

    @app.get(f"{API_PREFIX}/settings/status")
    def settings_status(request: Request) -> dict[str, Any]:
        settings = _settings(request)
        return {
            "storage": "local_sqlite",
            "database_path": str(settings.database_path),
            "api_token_enabled": bool(settings.api_token),
            "gmail_configured": bool(
                settings.gmail_client_secrets
                and settings.gmail_client_secrets.exists()
                and settings.gmail_token
                and settings.gmail_token.exists()
                and settings.own_email
            ),
            "own_email": settings.own_email,
            "local_outbox": str(settings.data_dir / "mail" / "outbox"),
            "expert_sources": _engine(request).store.expert_source_summary(),
        }

    @app.get(f"{API_PREFIX}/campaigns")
    def campaigns(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        status: str = Query("", max_length=20),
        search: str = Query("", max_length=120),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_campaigns(
            limit=limit, offset=offset, status=status, search=search
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/campaigns", status_code=201)
    def create_campaign_endpoint(
        body: CampaignCreate,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            campaign_id = engine.create_campaign(
                name=body.name,
                daily_send_limit=body.daily_send_limit,
                timezone_name=body.timezone,
                followup1_working_days=body.followup1_working_days,
                followup2_working_days=body.followup2_working_days,
                approval_mode=body.approval_mode,
                variants=body.variants,
            )
            return engine.store.get_campaign(campaign_id)

        return _idempotent(engine, "create_campaign", idempotency_key, operation)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}")
    def campaign(campaign_id: str, request: Request) -> dict[str, Any]:
        return _engine(request).store.get_campaign(campaign_id)

    @app.patch(f"{API_PREFIX}/campaigns/{{campaign_id}}")
    def update_campaign_endpoint(
        campaign_id: str, body: CampaignUpdate, request: Request
    ) -> dict[str, Any]:
        return _engine(request).store.update_campaign(
            campaign_id, body.model_dump(exclude_none=True)
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/summary")
    def campaign_summary(campaign_id: str, request: Request) -> dict[str, Any]:
        return _engine(request).store.campaign_summary(campaign_id)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/import")
    async def import_contacts_endpoint(
        campaign_id: str,
        request: Request,
        file: UploadFile = File(...),
        default_category: str = Form("Sustainability / ESG / Climate"),
    ) -> dict[str, Any]:
        filename, content = await _read_upload(
            file, allowed=CONTACT_UPLOAD_TYPES, max_bytes=_settings(request).max_upload_bytes
        )
        temporary = _temporary_upload(filename, content)
        try:
            with request.app.state.campaign_locks.hold(campaign_id):
                return _engine(request).import_contacts(
                    campaign_id, temporary, default_category=default_category
                )
        finally:
            temporary.unlink(missing_ok=True)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts")
    def contacts(
        campaign_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        search: str = Query("", max_length=120),
        status: str = Query("", max_length=40),
        category: str = Query("", max_length=120),
        variant_id: str = Query("", max_length=20),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_campaign_contacts(
            campaign_id,
            limit=limit,
            offset=offset,
            search=search,
            status=status,
            category=category,
            variant_id=variant_id,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.patch(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/{{campaign_contact_id}}")
    def update_contact_endpoint(
        campaign_id: str,
        campaign_contact_id: str,
        body: ContactUpdate,
        request: Request,
    ) -> dict[str, Any]:
        return _engine(request).store.update_campaign_contact(
            campaign_id, campaign_contact_id, body.model_dump(exclude_none=True)
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts/generate")
    def generate_drafts_endpoint(
        campaign_id: str,
        body: DraftGenerate,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            provider = None
            if body.provider:
                provider = create_provider(ProviderConfig(**body.provider.model_dump()))
            with request.app.state.campaign_locks.hold(campaign_id):
                return engine.generate_drafts(
                    campaign_id,
                    campaign_contact_ids=body.campaign_contact_ids,
                    stages=body.stages,
                    provider=provider,
                )

        return _idempotent(engine, f"generate:{campaign_id}", idempotency_key, operation)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts")
    def drafts(
        campaign_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        stage: str = Query("", max_length=20),
        approval_status: str = Query("", max_length=40),
        sendable: bool | None = Query(None),
        search: str = Query("", max_length=120),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_drafts(
            campaign_id,
            limit=limit,
            offset=offset,
            stage=stage,
            approval_status=approval_status,
            sendable=sendable,
            search=search,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.patch(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts/{{draft_id}}")
    def edit_draft_endpoint(
        campaign_id: str, draft_id: str, body: DraftEdit, request: Request
    ) -> dict[str, Any]:
        return _engine(request).edit_draft(
            campaign_id, draft_id, subject=body.subject, body=body.body
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts/approve")
    def approve_drafts_endpoint(
        campaign_id: str, body: DraftApprove, request: Request
    ) -> dict[str, int]:
        if not body.draft_ids and not body.stages:
            raise HTTPException(status_code=400, detail="Select draft_ids or stages to approve")
        return _engine(request).approve_drafts(
            campaign_id, draft_ids=body.draft_ids, stages=body.stages
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/queue")
    def queue(campaign_id: str, request: Request) -> dict[str, Any]:
        items = _engine(request).store.send_queue(campaign_id, now=utc_now())
        return {"items": items, "total": len(items)}

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/send")
    def send(
        campaign_id: str,
        body: SendRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        settings = _settings(request)
        provider = _mail_provider(settings, body.mode, body.confirmation)
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            with request.app.state.campaign_locks.hold(campaign_id):
                return engine.run_due(
                    campaign_id,
                    mail_provider=provider,
                    own_email=settings.own_email,
                    sync_replies_first=body.sync_replies_first,
                    max_messages=body.max_messages,
                )

        return _idempotent(engine, f"send:{campaign_id}", idempotency_key, operation)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/replies/sync")
    def sync_replies_endpoint(
        campaign_id: str, body: ReplySyncRequest, request: Request
    ) -> dict[str, int]:
        settings = _settings(request)
        if body.mode == "gmail":
            provider = _mail_provider(settings, body.mode, LIVE_SEND_CONFIRMATION)
        else:
            provider = _mail_provider(settings, body.mode)
        with request.app.state.campaign_locks.hold(campaign_id):
            return _engine(request).sync_replies(
                campaign_id, mail_provider=provider, own_email=settings.own_email
            )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/reports/ab")
    def ab_report(campaign_id: str, request: Request) -> dict[str, Any]:
        items = _engine(request).store.ab_report(campaign_id)
        return {"items": items, "total": len(items)}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/events")
    def events(
        campaign_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_events(
            campaign_id, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/export")
    def export_campaign(
        campaign_id: str,
        request: Request,
        format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    ) -> FileResponse:
        settings = _settings(request)
        destination = settings.export_dir / f"offsetx-crm-{campaign_id[:8]}-{uuid.uuid4().hex[:8]}.{format}"
        _engine(request).export_crm(campaign_id, destination)
        return FileResponse(destination, filename=destination.name)

    @app.get(f"{API_PREFIX}/templates")
    def templates(
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        active_only: bool = True,
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_templates(
            limit=limit, offset=offset, active_only=active_only
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/templates/import")
    def import_templates(body: TemplateImport, request: Request) -> dict[str, int]:
        engine = _engine(request)
        for item in body.templates:
            engine.store.upsert_template(item)
        return {"imported": len(body.templates)}

    @app.post(f"{API_PREFIX}/expert-sources/import")
    async def import_expert_source(
        request: Request,
        file: UploadFile = File(...),
        expert_name: str = Form(""),
        tags: str = Form(""),
        source_url: str = Form(""),
        source_type: str = Form("notes"),
        rights_basis: str = Form("user_provided"),
    ) -> dict[str, int]:
        filename, content = await _read_upload(
            file, allowed=EXPERT_UPLOAD_TYPES, max_bytes=_settings(request).max_upload_bytes
        )
        temporary = _temporary_upload(filename, content)
        try:
            return _engine(request).import_expert_sources(
                [temporary],
                expert_name=expert_name,
                tags=tags,
                source_url=source_url,
                source_type=source_type,
                rights_basis=rights_basis,
            )
        finally:
            temporary.unlink(missing_ok=True)

    if resolved.frontend_dist.exists():
        app.mount("/", StaticFiles(directory=resolved.frontend_dist, html=True), name="frontend")

    return app
