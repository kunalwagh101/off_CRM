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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ..locked_categories import LOCKED_CATEGORIES
from ..outreach.automation import AutomationService
from ..outreach.backup import create_encrypted_backup, restore_encrypted_backup
from ..outreach.engine import OutreachEngine
from ..outreach.gmail import GmailMailProvider, LocalOutboxProvider
from ..outreach.models import ProviderConfig, ROUTES, utc_now
from ..outreach.provider_profiles import ProviderProfileStore
from ..outreach.providers import ProviderError, create_provider
from .auth import DemoSessionAuth, LoginAttemptLimiter, SESSION_COOKIE
from .config import AppSettings
from .schemas import (
    AutomationUpdate,
    BackupExport,
    CampaignCreate,
    CampaignUpdate,
    ContactUpdate,
    DraftApprove,
    DraftEdit,
    DraftGenerate,
    DemoLogin,
    ProviderHealthRequest,
    ProviderProfileUpsert,
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
    session_auth = DemoSessionAuth(
        username=resolved.demo_username,
        password=resolved.demo_password,
        session_secret=resolved.session_secret,
        session_hours=resolved.session_hours,
    )
    login_limiter = LoginAttemptLimiter()
    loopback = resolved.host in {"127.0.0.1", "localhost", "::1"}

    def valid_api_token(request: Request) -> bool:
        if not resolved.api_token:
            return False
        authorization = request.headers.get("authorization", "")
        supplied = request.headers.get("x-offsetx-token", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        return hmac.compare_digest(supplied, resolved.api_token)

    def session_identity(request: Request):
        return session_auth.verify(request.cookies.get(SESSION_COOKIE, ""))

    def security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not loopback:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' http://127.0.0.1:8766 http://localhost:8766; "
            "img-src 'self' data:; font-src 'self'"
        )
        return response

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.prepare()
        app.state.settings = resolved
        app.state.engine = OutreachEngine(resolved.database_path)
        app.state.campaign_locks = CampaignLocks()
        app.state.maintenance_lock = threading.Lock()
        app.state.provider_profiles = ProviderProfileStore(resolved.data_dir)
        app.state.automation = AutomationService(
            resolved.data_dir / "automation.json",
            engine_factory=lambda: OutreachEngine(resolved.database_path),
            mail_provider_factory=lambda mode, authorized: _mail_provider(
                resolved,
                mode,
                LIVE_SEND_CONFIRMATION if authorized else "",
            ),
            own_email_factory=lambda: resolved.own_email,
        )
        await app.state.automation.start()
        try:
            yield
        finally:
            await app.state.automation.stop()
            app.state.engine.close()

    app = FastAPI(
        title="OffsetX Local Outreach CRM",
        version="0.7.0",
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
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-OffsetX-Token"],
    )

    @app.middleware("http")
    async def local_security(request: Request, call_next: Any):
        public_paths = {
            f"{API_PREFIX}/meta",
            f"{API_PREFIX}/auth/session",
            f"{API_PREFIX}/auth/login",
            f"{API_PREFIX}/auth/logout",
        }
        protected = (
            request.url.path.startswith("/api/")
            and request.url.path not in public_paths
            and (bool(resolved.api_token) or session_auth.enabled)
        )
        if protected and not (valid_api_token(request) or session_identity(request)):
            return security_headers(
                JSONResponse(status_code=401, content={"detail": "CRM login required"})
            )
        return security_headers(await call_next(request))

    @app.exception_handler(KeyError)
    async def not_found(_: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc).strip("'")})

    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_failure(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

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
            "version": "0.7.0",
            "categories": list(LOCKED_CATEGORIES),
            "routes": list(ROUTES),
            "provider_types": [
                "openai", "anthropic", "openai_compatible", "template_engine_http"
            ],
            "mail_modes": ["local", "gmail"],
            "live_send_confirmation": LIVE_SEND_CONFIRMATION,
        }

    @app.get(f"{API_PREFIX}/auth/session")
    def auth_session(request: Request) -> dict[str, Any]:
        identity = session_identity(request)
        token_authenticated = valid_api_token(request)
        return {
            "configured": session_auth.enabled,
            "authenticated": not session_auth.enabled or bool(identity) or token_authenticated,
            "username": identity.username if identity else "",
            "expires_at": identity.expires_at if identity else None,
        }

    @app.post(f"{API_PREFIX}/auth/login")
    def auth_login(body: DemoLogin, request: Request) -> Response:
        if not session_auth.enabled:
            raise HTTPException(status_code=404, detail="Demo login is not configured")
        client_key = request.client.host if request.client else "unknown"
        if not login_limiter.allowed(client_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again in five minutes."},
                headers={"Retry-After": "300"},
            )
        if not session_auth.authenticate(body.username, body.password):
            login_limiter.failed(client_key)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        login_limiter.clear(client_key)
        response = JSONResponse(
            content={"authenticated": True, "username": resolved.demo_username}
        )
        response.set_cookie(
            SESSION_COOKIE,
            session_auth.issue(),
            max_age=session_auth.session_seconds,
            httponly=True,
            secure=not loopback,
            samesite="strict",
            path="/",
        )
        return response

    @app.post(f"{API_PREFIX}/auth/logout")
    def auth_logout() -> Response:
        response = JSONResponse(content={"authenticated": False})
        response.delete_cookie(
            SESSION_COOKIE,
            httponly=True,
            secure=not loopback,
            samesite="strict",
            path="/",
        )
        return response

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
            "provider_profiles": len(request.app.state.provider_profiles.list()),
            "automation": request.app.state.automation.status(),
        }

    @app.get(f"{API_PREFIX}/provider-profiles")
    def provider_profiles(
        request: Request,
        owner: str = Query("", max_length=100),
    ) -> dict[str, Any]:
        items = request.app.state.provider_profiles.list(owner=owner)
        return {"items": items, "total": len(items)}

    @app.post(f"{API_PREFIX}/provider-profiles", status_code=201)
    def save_provider_profile(
        body: ProviderProfileUpsert, request: Request
    ) -> dict[str, Any]:
        payload = body.model_dump(exclude={"api_key"})
        return request.app.state.provider_profiles.upsert(payload, api_key=body.api_key)

    @app.post(f"{API_PREFIX}/provider-profiles/{{profile_id}}/test")
    def test_provider_profile(
        profile_id: str,
        body: ProviderHealthRequest,
        request: Request,
    ) -> dict[str, Any]:
        result = request.app.state.provider_profiles.health(
            profile_id, probe=body.live_probe
        )
        if result["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.post(f"{API_PREFIX}/provider-profiles/{{profile_id}}/delete")
    def delete_provider_profile(profile_id: str, request: Request) -> dict[str, bool]:
        request.app.state.provider_profiles.delete(profile_id)
        return {"deleted": True}

    @app.get(f"{API_PREFIX}/automation")
    def automation_status(request: Request) -> dict[str, Any]:
        return request.app.state.automation.status()

    @app.patch(f"{API_PREFIX}/automation")
    def update_automation(body: AutomationUpdate, request: Request) -> dict[str, Any]:
        return request.app.state.automation.update(
            body.model_dump(exclude={"gmail_confirmation"}),
            gmail_confirmation=body.gmail_confirmation,
        )

    @app.post(f"{API_PREFIX}/automation/run")
    def run_automation(request: Request) -> dict[str, Any]:
        results = request.app.state.automation.run_once()
        return {"results": results, "total": len(results)}

    @app.post(f"{API_PREFIX}/backups/export")
    def export_backup(body: BackupExport, request: Request) -> Response:
        content = create_encrypted_backup(
            database_path=_settings(request).database_path,
            data_dir=_settings(request).data_dir,
            passphrase=body.passphrase,
        )
        filename = f"offsetx-backup-{uuid.uuid4().hex[:8]}.oxbackup"
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post(f"{API_PREFIX}/backups/restore")
    async def restore_backup(
        request: Request,
        file: UploadFile = File(...),
        passphrase: str = Form(..., min_length=12, max_length=500),
    ) -> dict[str, Any]:
        settings = _settings(request)
        content = await file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Backup exceeds the upload limit")
        if not request.app.state.maintenance_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Maintenance is already running")
        automation = request.app.state.automation
        await automation.stop()
        current_engine = request.app.state.engine
        current_engine.close()
        try:
            for suffix in ("-wal", "-shm"):
                Path(str(settings.database_path) + suffix).unlink(missing_ok=True)
            result = restore_encrypted_backup(
                content,
                database_path=settings.database_path,
                data_dir=settings.data_dir,
                passphrase=passphrase,
            )
            request.app.state.engine = OutreachEngine(settings.database_path)
            return result
        finally:
            if getattr(request.app.state, "engine", None) is current_engine:
                request.app.state.engine = OutreachEngine(settings.database_path)
            await automation.start()
            request.app.state.maintenance_lock.release()

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
            if body.use_provider_fallback:
                if body.provider:
                    raise ValueError(
                        "Choose either a direct provider or the configured fallback chain"
                    )
                provider = request.app.state.provider_profiles.router(
                    owner=body.provider_owner,
                    profile_ids=body.provider_profile_ids,
                )
            elif body.provider:
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
