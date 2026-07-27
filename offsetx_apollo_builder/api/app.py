from __future__ import annotations

import hmac
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..discovery import DiscoveryService
from ..locked_categories import LOCKED_CATEGORIES
from ..io_utils import read_apollo_exclusion_ledgers, read_apollo_rejection_ledgers
from ..outreach.automation import AutomationService
from ..outreach.backup import create_encrypted_backup, restore_encrypted_backup
from ..outreach.engine import OutreachEngine
from ..outreach.gmail import GmailMailProvider, LocalOutboxProvider
from ..outreach.models import ProviderConfig, ROUTES, utc_now
from ..outreach.ai_chat import AIChatService
from ..outreach.notion import (
    NotionClient,
    NotionError,
    NotionExporter,
    NotionSettingsStore,
    export_campaign_contacts,
    export_sales_leads,
)
from ..ai import (
    DataClass,
    ModeRunner,
    RunMode,
    EgressBlocked,
    EgressBroker,
    EgressLog,
    EgressRequest,
    NoPermittedProvider,
    PersonPublic,
    PolicyViolation,
    ProviderRegistry,
    QuotaTracker,
    RegistryError,
)
from ..ai.discovery import discover_models
from ..ai.workspace import WorkspaceAISettingsStore
from ..outreach.provider_profiles import ProviderProfileStore, create_guarded_provider
from ..outreach.providers import ProviderError
from ..outreach.sales import SalesConflictError, SalesTracker
from .auth import DemoSessionAuth, LoginAttemptLimiter, SESSION_COOKIE
from .config import AppSettings
from .schemas import (
    AutomationUpdate,
    BackupExport,
    CampaignCreate,
    CampaignUpdate,
    ContactUpdate,
    DraftApprove,
    DraftBulkReplace,
    DraftEdit,
    DraftGenerate,
    DraftSchedule,
    DemoLogin,
    DiscoveryDecision,
    DiscoveryRunCreate,
    DiscoverySelection,
    ResearchInteractionCreate,
    SalesGoalUpdate,
    SalesLeadCreate,
    SalesLeadMove,
    SalesLeadUpdate,
    SalesProjectionRequest,
    SetterActivityUpsert,
    ProviderHealthRequest,
    ProviderProfileUpsert,
    ReplySyncRequest,
    SendRequest,
    TemplateImport,
    MemoryApproval,
    MemoryCreate,
    NotionExportRequest,
    NotionSettingsUpdate,
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

def _ai_chat(request: Request) -> AIChatService:
    return request.app.state.ai_chat


def _settings(request: Request) -> AppSettings:
    return request.app.state.settings


def _sales(request: Request) -> SalesTracker:
    return request.app.state.sales


def _discovery(request: Request) -> DiscoveryService:
    settings = _settings(request)
    return DiscoveryService(
        _engine(request).store,
        project_root=settings.project_root,
        data_dir=settings.data_dir,
        fetcher_factory=getattr(request.app.state, "discovery_fetcher_factory", None),
    )


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
        app.state.ai_chat = AIChatService(app.state.engine.store)
        app.state.sales = SalesTracker(app.state.engine.store)
        app.state.campaign_locks = CampaignLocks()
        app.state.maintenance_lock = threading.Lock()
        app.state.provider_profiles = ProviderProfileStore(resolved.data_dir)
        app.state.ai_registry = ProviderRegistry()
        app.state.ai_workspaces = WorkspaceAISettingsStore(
            resolved.data_dir, app.state.ai_registry
        )
        app.state.ai_egress_log = EgressLog(resolved.data_dir / "ai_egress.db")
        app.state.ai_quota = QuotaTracker(resolved.data_dir)
        app.state.ai_broker = EgressBroker(
            registry=app.state.ai_registry,
            credential_resolver=lambda provider_id: "",
            quota=app.state.ai_quota,
            logger=app.state.ai_egress_log.record,
        )
        app.state.notion = NotionSettingsStore(resolved.data_dir)
        app.state.discovery_fetcher_factory = None
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
            app.state.ai_egress_log.close()

    app = FastAPI(
        title="off_CRM",
        version=__version__,
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
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-off-CRM-Token"],
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

    @app.exception_handler(NotionError)
    async def notion_failure(_: Request, exc: NotionError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_failure(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(SalesConflictError)
    async def stale_sales_card(_: Request, exc: SalesConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

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
            "name": "off_CRM",
            "version": __version__,
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

    @app.get(f"{API_PREFIX}/sales/meta")
    def sales_meta(request: Request) -> dict[str, Any]:
        return _sales(request).metadata()

    @app.get(f"{API_PREFIX}/sales/board")
    def sales_board(
        request: Request,
        rep_name: str = Query("", max_length=160),
        source: str = Query("", max_length=120),
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        search: str = Query("", max_length=200),
    ) -> dict[str, Any]:
        return _sales(request).board(
            rep_name=rep_name,
            source=source,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )

    @app.get(f"{API_PREFIX}/sales/leads")
    def sales_leads(
        request: Request,
        status: str = Query("", max_length=40),
        rep_name: str = Query("", max_length=160),
        source: str = Query("", max_length=120),
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        search: str = Query("", max_length=200),
        sort_by: str = Query("updated_at", max_length=40),
        sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
        limit: int = Query(200, ge=1, le=5000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _sales(request).list_leads(
            status=status,
            rep_name=rep_name,
            source=source,
            start_date=start_date,
            end_date=end_date,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/sales/leads", status_code=201)
    def create_sales_lead(
        body: SalesLeadCreate,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return _idempotent(
            _engine(request),
            "sales-lead:create",
            idempotency_key,
            lambda: _sales(request).create_lead(body.model_dump(exclude_none=True)),
        )

    @app.get(f"{API_PREFIX}/sales/leads/{{lead_id}}")
    def sales_lead(lead_id: str, request: Request) -> dict[str, Any]:
        return _sales(request).get_lead(lead_id)

    @app.patch(f"{API_PREFIX}/sales/leads/{{lead_id}}")
    def update_sales_lead(
        lead_id: str, body: SalesLeadUpdate, request: Request
    ) -> dict[str, Any]:
        changes = body.model_dump(exclude_unset=True)
        expected_revision = changes.pop("expected_revision", None)
        return _sales(request).update_lead(
            lead_id,
            changes,
            expected_revision=expected_revision,
        )

    @app.post(f"{API_PREFIX}/sales/leads/{{lead_id}}/move")
    def move_sales_lead(
        lead_id: str, body: SalesLeadMove, request: Request
    ) -> dict[str, Any]:
        return _sales(request).move_lead(
            lead_id,
            body.lead_status,
            expected_revision=body.expected_revision,
        )

    @app.get(f"{API_PREFIX}/sales/leads/{{lead_id}}/events")
    def sales_lead_events(
        lead_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = _sales(request).lead_events(lead_id, limit=limit)
        return {"items": items, "total": len(items)}

    @app.get(f"{API_PREFIX}/sales/activity")
    def sales_activity(
        request: Request,
        setter_name: str = Query("", max_length=160),
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _sales(request).list_activity(
            setter_name=setter_name,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/sales/activity")
    def save_sales_activity(
        body: SetterActivityUpsert, request: Request
    ) -> dict[str, Any]:
        return _sales(request).upsert_activity(body.model_dump())

    @app.get(f"{API_PREFIX}/sales/goals/{{month}}")
    def sales_goal(month: str, request: Request) -> dict[str, Any]:
        return _sales(request).get_goal(month)

    @app.patch(f"{API_PREFIX}/sales/goals/{{month}}")
    def save_sales_goal(
        month: str, body: SalesGoalUpdate, request: Request
    ) -> dict[str, Any]:
        return _sales(request).set_goal(month, **body.model_dump())

    @app.get(f"{API_PREFIX}/sales/dashboard")
    def sales_dashboard(
        request: Request,
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        rep_name: str = Query("", max_length=160),
        source: str = Query("", max_length=120),
        search: str = Query("", max_length=200),
        goal_month: str = Query("", max_length=7),
    ) -> dict[str, Any]:
        return _sales(request).dashboard(
            start_date=start_date,
            end_date=end_date,
            rep_name=rep_name,
            source=source,
            search=search,
            goal_month=goal_month,
        )

    @app.post(f"{API_PREFIX}/sales/projection")
    def sales_projection(
        body: SalesProjectionRequest, request: Request
    ) -> dict[str, Any]:
        return _sales(request).projection(body.model_dump(exclude_none=True))

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
            "memory": _engine(request).store.memory_stats(),
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

    @app.get(f"{API_PREFIX}/provider-calls")
    def provider_calls(
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        profile_id: str = Query("", max_length=80),
        status: str = Query("", max_length=40),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_provider_calls(
            limit=limit, offset=offset, profile_id=profile_id, status=status
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/memory/stats")
    def memory_stats(request: Request) -> dict[str, Any]:
        return _engine(request).store.memory_stats()

    @app.get(f"{API_PREFIX}/memory")
    def memory_items(
        request: Request,
        query: str = Query("", max_length=1000),
        scope: str = Query("", max_length=200),
        kind: str = Query("", max_length=80),
        approved_only: bool = Query(False),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.search_memory_items(
            query,
            scope=scope,
            kind=kind,
            approved_only=approved_only,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/memory", status_code=201)
    def create_memory(body: MemoryCreate, request: Request) -> dict[str, Any]:
        memory_id = _engine(request).email_expert.memory.add_manual(
            content=body.content,
            kind=body.kind,
            scope=body.scope,
            tags=body.tags,
        )
        items, _ = _engine(request).store.search_memory_items("", limit=1000)
        return next(item for item in items if item["id"] == memory_id)

    @app.patch(f"{API_PREFIX}/memory/{{memory_id}}")
    def approve_memory(
        memory_id: str, body: MemoryApproval, request: Request
    ) -> dict[str, Any]:
        return _engine(request).store.set_memory_approval(memory_id, body.approved)

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
                send_window_start=body.send_window_start,
                send_window_end=body.send_window_end,
                send_weekdays=body.send_weekdays,
                experiment_hypothesis=body.experiment_hypothesis,
                experiment_metric=body.experiment_metric,
                experiment_min_sample=body.experiment_min_sample,
                control_variant=body.control_variant,
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
        updated = _engine(request).store.update_campaign_contact(
            campaign_id, campaign_contact_id, body.model_dump(exclude_none=True)
        )
        if body.outcome_label:
            _engine(request).email_expert.memory.remember_feedback(
                campaign_id=campaign_id,
                campaign_contact_id=campaign_contact_id,
                outcome_label=body.outcome_label,
                notes=body.notes or str(updated.get("notes", "")),
                contact=updated,
            )
        return updated

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/discovery/runs")
    def discovery_runs(
        campaign_id: str,
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_discovery_runs(
            campaign_id, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/discovery/runs", status_code=201)
    def create_discovery_run_endpoint(
        campaign_id: str,
        body: DiscoveryRunCreate,
        request: Request,
    ) -> dict[str, Any]:
        with request.app.state.campaign_locks.hold(f"discovery:{campaign_id}"):
            return _discovery(request).run(
                campaign_id=campaign_id,
                seed_urls=body.seed_urls,
                allowed_domains=body.allowed_domains,
                category=body.category,
                max_pages=body.max_pages,
                max_depth=body.max_depth,
                obey_robots=body.obey_robots,
                request_delay_seconds=body.request_delay_seconds,
                engine=body.engine,
                objective_prompt=body.objective_prompt,
                target_count=body.target_count,
                parallel_workers=body.parallel_workers,
            )

    def _notion_store(request: Request) -> NotionSettingsStore:
        return request.app.state.notion

    def _notion_client(request: Request) -> NotionClient:
        return NotionClient(_notion_store(request).token())

    @app.get(f"{API_PREFIX}/notion/settings")
    def notion_settings(request: Request) -> dict[str, Any]:
        return _notion_store(request).status()

    @app.post(f"{API_PREFIX}/notion/settings")
    def update_notion_settings(body: NotionSettingsUpdate, request: Request) -> dict[str, Any]:
        return _notion_store(request).update(
            token=body.token or None,
            workspace_name=body.workspace_name or None,
            contacts_database_id=body.contacts_database_id or None,
            sales_database_id=body.sales_database_id or None,
        )

    @app.post(f"{API_PREFIX}/notion/disconnect")
    def notion_disconnect(request: Request) -> dict[str, Any]:
        return _notion_store(request).disconnect()

    @app.post(f"{API_PREFIX}/notion/test")
    def notion_test(request: Request) -> dict[str, Any]:
        return _notion_client(request).me()

    @app.get(f"{API_PREFIX}/notion/databases")
    def notion_databases(request: Request) -> dict[str, Any]:
        return {"items": _notion_client(request).list_databases()}

    @app.post(f"{API_PREFIX}/notion/export")
    def notion_export(body: NotionExportRequest, request: Request) -> dict[str, Any]:
        status = _notion_store(request).status()
        exporter = NotionExporter(_notion_client(request))
        if body.scope == "contacts":
            if not body.campaign_id:
                raise NotionError("Pick a campaign to export contacts from.")
            return export_campaign_contacts(
                exporter=exporter,
                database_id=status["contacts_database_id"],
                list_contacts=_engine(request).store.list_campaign_contacts,
                campaign_id=body.campaign_id,
                limit=body.limit,
            )
        return export_sales_leads(
            exporter=exporter,
            database_id=status["sales_database_id"],
            list_leads=_sales(request).list_leads,
            limit=body.limit,
        )


    # ── AI Copilot chat ──────────────────────────────────────────────────────

    @app.get(f"{API_PREFIX}/ai/projects")
    def ai_list_projects(request: Request) -> dict[str, Any]:
        return {"items": _ai_chat(request).list_projects()}

    @app.post(f"{API_PREFIX}/ai/projects")
    def ai_create_project(body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _ai_chat(request).create_project(str(body.get("name", "")))

    @app.delete(f"{API_PREFIX}/ai/projects/{{project_id}}")
    def ai_delete_project(project_id: str, request: Request) -> dict[str, Any]:
        _ai_chat(request).delete_project(project_id)
        return {"deleted": project_id}

    @app.get(f"{API_PREFIX}/ai/chats")
    def ai_list_chats(request: Request, project_id: str = Query("", max_length=64), limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
        chats = _ai_chat(request).list_chats(project_id=project_id or None, limit=limit)
        return {"items": chats}

    @app.post(f"{API_PREFIX}/ai/chats")
    def ai_create_chat(body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _ai_chat(request).create_chat(title=str(body.get("title", "New chat")), project_id=body.get("project_id"))

    @app.delete(f"{API_PREFIX}/ai/chats/{{chat_id}}")
    def ai_delete_chat(chat_id: str, request: Request) -> dict[str, Any]:
        _ai_chat(request).delete_chat(chat_id)
        return {"deleted": chat_id}

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/move")
    def ai_move_chat(chat_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        from fastapi import HTTPException
        result = _ai_chat(request).move_chat(chat_id, body.get("project_id"))
        if not result:
            raise HTTPException(404, "Chat not found")
        return result

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/rename")
    def ai_rename_chat(chat_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        from fastapi import HTTPException
        result = _ai_chat(request).rename_chat(chat_id, str(body.get("title", "")))
        if not result:
            raise HTTPException(404, "Chat not found")
        return result

    @app.get(f"{API_PREFIX}/ai/chats/{{chat_id}}/messages")
    def ai_list_messages(chat_id: str, request: Request) -> dict[str, Any]:
        return {"items": _ai_chat(request).list_messages(chat_id)}

    # ── AI module: workspace, providers, egress ──────────────────────────

    def _ai(request: Request) -> tuple[Any, Any, Any]:
        """(broker, workspace store, egress log) for the current request."""
        state = request.app.state
        return state.ai_broker, state.ai_workspaces, state.ai_egress_log

    def _ai_error(exc: Exception) -> HTTPException:
        """Turn a policy refusal into an answer the owner can act on.

        Never a raw stack trace: a refused call is a normal, explainable outcome
        of the trust rules, not a crash.
        """
        if isinstance(exc, EgressBlocked):
            return HTTPException(422, detail=exc.to_dict())
        if isinstance(exc, PolicyViolation):
            return HTTPException(403, detail=exc.to_dict())
        if isinstance(exc, NoPermittedProvider):
            return HTTPException(409, detail=exc.to_dict())
        if isinstance(exc, RegistryError):
            return HTTPException(400, detail={"error": "registry_error", "message": str(exc)})
        if isinstance(exc, ValueError):
            return HTTPException(400, detail={"error": "invalid_request", "message": str(exc)})
        return HTTPException(500, detail={"error": "ai_error", "message": str(exc)})

    def _workspace_id(request: Request) -> str:
        return "local"

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/messages")
    def ai_send_message(chat_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Send a chat turn through the egress broker.

        ``data_class`` decides which providers may answer. ``public`` is for
        code and general questions and lets restricted-tier models help;
        ``campaign`` is the default and keeps the conversation on trusted tiers.
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        broker.credential_resolver = workspaces.credential_resolver(workspace_id)

        requested_class = str(body.get("data_class", "campaign")).strip().lower()
        if requested_class not in {"public", "campaign"}:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid_data_class",
                    "message": "Chat runs as 'public' or 'campaign'. Mailbox and CRM "
                    "records are not reachable from chat.",
                },
            )
        data_class = DataClass(requested_class)
        provider_id = str(body.get("provider_id", "")).strip()
        model_id = str(body.get("model_id", "")).strip()
        if model_id and provider_id:
            # Pin one model rather than the whole key's model list.
            settings.enabled_models = {**settings.enabled_models, provider_id: (model_id,)}

        chosen: dict[str, str] = {}

        def responder(*, turns: list[dict[str, str]]) -> dict[str, str]:
            egress = EgressRequest(
                task_type="ai_chat",
                data_class=data_class,
                conversation=turns,
                positioning_line=settings.positioning_line,
                task_tags=("writing", "reasoning"),
            )
            result = broker.call(
                egress,
                settings,
                system_prompt=AIChatService.DEFAULT_SYSTEM_PROMPT,
                provider_id=provider_id,
            )
            chosen.update({"provider": result.provider_name, "model": result.model_id})
            return {
                "text": result.text,
                "provider": result.provider_name,
                "model": result.model_id,
            }

        try:
            return _ai_chat(request).send_message(
                chat_id=chat_id,
                user_content=str(body.get("content", "")),
                responder=responder,
                workspace_id=workspace_id,
            )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc

    @app.get(f"{API_PREFIX}/ai/providers")
    def ai_providers(request: Request) -> dict[str, Any]:
        """Registry plus this workspace's connection state, tiers and usage."""
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        try:
            payload = workspaces.describe(workspace_id)
        except RegistryError as exc:
            raise _ai_error(exc) from exc
        usage = {
            row["provider_id"]: row
            for row in broker.usage(workspaces.egress_settings(workspace_id))
        }
        for row in payload["providers"]:
            row["usage"] = usage.get(row["id"])
        return payload

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/connect")
    def ai_connect_provider(
        provider_id: str, body: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        _, workspaces, _ = _ai(request)
        try:
            return workspaces.connect_provider(
                _workspace_id(request),
                provider_id,
                api_key=str(body.get("api_key", "")),
                model_id=str(body.get("model_id", "")),
                model_ids=[str(item) for item in (body.get("model_ids") or [])],
                data_policy=str(body.get("data_policy", "")),
                enabled=bool(body.get("enabled", True)),
                requests_per_minute=body.get("requests_per_minute"),
                requests_per_day=body.get("requests_per_day"),
                max_spend_usd_per_day=body.get("max_spend_usd_per_day"),
            )
        except (RegistryError, ValueError) as exc:
            raise _ai_error(exc) from exc

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/disconnect")
    def ai_disconnect_provider(provider_id: str, request: Request) -> dict[str, str]:
        _, workspaces, _ = _ai(request)
        workspaces.disconnect_provider(_workspace_id(request), provider_id)
        return {"status": "disconnected", "provider_id": provider_id}

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/discover-models")
    def ai_discover_models(provider_id: str, request: Request) -> dict[str, Any]:
        """Ask the provider which models this key reaches.

        Sends no owner data — it is a catalogue request carrying only the key.
        Each returned model is classified against config/providers.yaml, so trust
        is decided here and never by what the provider says about itself.
        """
        _, workspaces, log = _ai(request)
        workspace_id = _workspace_id(request)
        try:
            result = discover_models(
                request.app.state.ai_registry,
                provider_id,
                workspaces.key_for(workspace_id, provider_id),
                logger=log.record,
                workspace_id=workspace_id,
            )
        except RegistryError as exc:
            raise _ai_error(exc) from exc
        return result.to_dict()

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/override")
    def ai_override_provider(
        provider_id: str, body: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        """Raise or lower a provider's trust for this workspace, with a reason."""
        _, workspaces, _ = _ai(request)
        try:
            return workspaces.set_override(
                _workspace_id(request),
                provider_id,
                trust_tier=str(body.get("trust_tier", "")),
                data_policy=str(body.get("data_policy", "")),
                allow_above_ceiling=bool(body.get("allow_above_ceiling", False)),
                reason=str(body.get("reason", "")),
                decided_by=str(body.get("decided_by", "")),
            )
        except (RegistryError, ValueError) as exc:
            raise _ai_error(exc) from exc

    @app.post(f"{API_PREFIX}/ai/workspace")
    def ai_update_workspace(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Positioning line, owner domains and addresses.

        The positioning line is the only sender-side content permitted to leave.
        The domains and addresses are what the pre-flight scanner watches for.
        """
        _, workspaces, _ = _ai(request)
        values: dict[str, Any] = {}
        if "positioning_line" in body:
            values["positioning_line"] = str(body["positioning_line"])[:500]
        if "owner_domains" in body:
            values["owner_domains"] = [
                str(item).strip().lower().lstrip("@")
                for item in (body.get("owner_domains") or [])
                if str(item).strip()
            ][:20]
        if "owner_addresses" in body:
            values["owner_addresses"] = [
                str(item).strip().lower()
                for item in (body.get("owner_addresses") or [])
                if str(item).strip()
            ][:20]
        workspaces.save(_workspace_id(request), values)
        return workspaces.describe(_workspace_id(request))

    @app.post(f"{API_PREFIX}/ai/workspace/mailbox-unlock")
    def ai_mailbox_unlock(body: dict[str, Any], request: Request) -> dict[str, Any]:
        _, workspaces, _ = _ai(request)
        try:
            workspaces.unlock_mailbox(_workspace_id(request), str(body.get("phrase", "")))
        except ValueError as exc:
            raise HTTPException(400, detail={"error": "bad_phrase", "message": str(exc)}) from exc
        return workspaces.describe(_workspace_id(request))

    @app.post(f"{API_PREFIX}/ai/plan")
    def ai_plan(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Dry run: which provider would take this task, and who was filtered out.

        Lets the Connectors screen answer 'what happens if I run this?' without
        spending a call.
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        data_class = DataClass(str(body.get("data_class", "person_public")).strip().lower())
        egress = EgressRequest(
            task_type=str(body.get("task_type", "draft_email")),
            data_class=data_class,
            task_tags=tuple(str(tag) for tag in body.get("task_tags") or ()),
        )
        try:
            permitted, rejected = broker.plan(egress, settings)
        except (PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc
        return {
            "data_class": data_class.value,
            "would_use": permitted[0].to_dict() if permitted else None,
            "chain": [item.to_dict() for item in permitted],
            "excluded": rejected,
        }

    @app.get(f"{API_PREFIX}/ai/modes")
    def ai_modes(request: Request) -> dict[str, Any]:
        """The three run modes plus which ones are usable right now.

        Returning `available` and `blocked_reason` lets the picker disable a
        mode with an explanation rather than failing after the user commits.
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        connected = len(settings.enabled_provider_ids)

        planners: list[str] = []
        for provider_id in settings.enabled_provider_ids:
            try:
                resolved = request.app.state.ai_registry.resolve(
                    provider_id, override=settings.overrides.get(provider_id)
                )
            except RegistryError:
                continue
            if resolved.tier.value in {"A", "B"}:
                planners.append(provider_id)

        def availability(mode: RunMode) -> tuple[bool, str]:
            if connected == 0:
                return False, "No AI provider is connected yet."
            if mode is RunMode.COMPARE and connected < 2:
                return False, "Connect at least two models to compare answers."
            if mode is RunMode.ORCHESTRATED and not planners:
                return False, (
                    "Planning needs a model at Highest or Default trust, such as "
                    "Mistral, Claude, GPT or NVIDIA."
                )
            return True, ""

        modes = []
        for mode in RunMode:
            available, reason = availability(mode)
            modes.append(
                {
                    "value": mode.value,
                    "label": mode.label,
                    "description": mode.description,
                    "available": available,
                    "blocked_reason": reason,
                }
            )
        return {
            "modes": modes,
            "connected_count": connected,
            "planner_provider_ids": planners,
            "usage": broker.usage(settings),
        }

    @app.post(f"{API_PREFIX}/ai/run")
    def ai_run(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Run one instruction in the chosen mode.

        simple       → one model
        compare      → every permitted model at once, all answers returned
        orchestrated → a tier A/B model plans, each step routed normally
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        broker.credential_resolver = workspaces.credential_resolver(workspace_id)

        raw_mode = str(body.get("mode", "simple")).strip().lower()
        if raw_mode not in {item.value for item in RunMode}:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid_mode",
                    "message": "Mode must be simple, compare, or orchestrated.",
                },
            )
        mode = RunMode(raw_mode)

        raw_class = str(body.get("data_class", "public")).strip().lower()
        if raw_class not in {"public", "person_public", "campaign"}:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid_data_class",
                    "message": "Runs use public, person_public or campaign. Mailbox and "
                    "CRM records are not reachable this way.",
                },
            )

        egress = EgressRequest(
            task_type=str(body.get("task_type", "ai_run"))[:120],
            data_class=DataClass(raw_class),
            # Stripped, so whitespace-only input is treated as empty rather
            # than sailing past the check below as a truthy string.
            instructions=str(body.get("instructions", "")).strip()[:6000],
            positioning_line=settings.positioning_line,
            template_text=str(body.get("template_text", ""))[:12000],
            public_text=str(body.get("public_text", ""))[:20000],
            task_tags=tuple(str(tag) for tag in (body.get("task_tags") or ()))[:4],
        )
        if not egress.instructions:
            raise HTTPException(
                400,
                detail={"error": "empty_instructions", "message": "Tell the models what to do."},
            )

        runner = ModeRunner(broker)
        system_prompt = str(body.get("system_prompt", "")) or AIChatService.DEFAULT_SYSTEM_PROMPT
        try:
            if mode is RunMode.COMPARE:
                result = runner.run_compare(
                    egress,
                    settings,
                    system_prompt=system_prompt,
                    include_lower_tiers=bool(body.get("include_lower_tiers", True)),
                )
            elif mode is RunMode.ORCHESTRATED:
                result = runner.run_orchestrated(
                    egress,
                    settings,
                    system_prompt=system_prompt,
                    planner_provider_id=str(body.get("planner_provider_id", "")),
                )
            else:
                pinned_provider = str(body.get("provider_id", "")).strip()
                pinned_model = str(body.get("model_id", "")).strip()
                if pinned_provider and pinned_model:
                    settings.enabled_models = {
                        **settings.enabled_models,
                        pinned_provider: (pinned_model,),
                    }
                result = runner.run_simple(
                    egress,
                    settings,
                    system_prompt=system_prompt,
                    provider_id=pinned_provider,
                )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc
        return result.to_dict()

    @app.get(f"{API_PREFIX}/ai/egress-log")
    def ai_egress_log(
        request: Request,
        provider_id: str = Query("", max_length=80),
        status: str = Query("", max_length=30),
        data_class: str = Query("", max_length=30),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        _, _, log = _ai(request)
        items, total = log.list(
            workspace_id=_workspace_id(request),
            provider_id=provider_id,
            status=status,
            data_class=data_class,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/ai/egress-log/stats")
    def ai_egress_stats(request: Request) -> dict[str, Any]:
        _, _, log = _ai(request)
        return log.stats(workspace_id=_workspace_id(request))

    @app.get(f"{API_PREFIX}/ai/egress-log/{{log_id}}")
    def ai_egress_entry(log_id: str, request: Request) -> dict[str, Any]:
        """The exact payload that was sent, so the guarantee is verified."""
        _, _, log = _ai(request)
        record = log.get(log_id)
        if record is None:
            raise HTTPException(404, "Egress log entry not found")
        return record

    @app.get(f"{API_PREFIX}/discovery/runs/{{run_id}}/candidates")
    def discovery_candidates(
        run_id: str,
        request: Request,
        limit: int = Query(500, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        status: str = Query("", max_length=30),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_discovery_candidates(
            run_id, limit=limit, offset=offset, status=status
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post(f"{API_PREFIX}/discovery/runs/{{run_id}}/decision")
    def decide_discovery_candidates(
        run_id: str, body: DiscoveryDecision, request: Request
    ) -> dict[str, int]:
        return _discovery(request).decide(run_id, body.candidate_ids, body.decision)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/discovery/runs/{{run_id}}/import")
    def import_discovery_candidates(
        campaign_id: str,
        run_id: str,
        body: DiscoverySelection,
        request: Request,
    ) -> dict[str, Any]:
        with request.app.state.campaign_locks.hold(campaign_id):
            return _discovery(request).import_to_campaign(
                run_id, campaign_id, body.candidate_ids
            )

    @app.post(f"{API_PREFIX}/discovery/runs/{{run_id}}/apollo-queue")
    def queue_discovery_candidates_for_apollo(
        run_id: str, body: DiscoverySelection, request: Request
    ) -> dict[str, Any]:
        return _discovery(request).queue_for_apollo(run_id, body.candidate_ids)

    @app.get(f"{API_PREFIX}/research/graph")
    def research_graph(
        request: Request,
        run_id: str = Query("", max_length=100),
        query: str = Query("", max_length=500),
        limit: int = Query(250, ge=1, le=500),
    ) -> dict[str, Any]:
        return _discovery(request).research_graph(run_id=run_id, query=query, limit=limit)

    @app.post(f"{API_PREFIX}/research/interactions", status_code=201)
    def record_research_interaction(
        body: ResearchInteractionCreate,
        request: Request,
    ) -> dict[str, Any]:
        return _discovery(request).record_social_interaction(**body.model_dump())

    @app.get(f"{API_PREFIX}/apollo/rejections")
    def apollo_rejections(
        request: Request,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        reason: str = Query("", max_length=200),
    ) -> dict[str, Any]:
        settings = _settings(request)
        paths = list(settings.project_root.glob("output*/offsetx_apollo_rejection_ledger.csv"))
        paths.extend(settings.data_dir.glob("output*/offsetx_apollo_rejection_ledger.csv"))
        direct = settings.data_dir / "offsetx_apollo_rejection_ledger.csv"
        if direct.exists():
            paths.append(direct)
        items, total = read_apollo_rejection_ledgers(
            paths, limit=limit, offset=offset, reason=reason
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/apollo/exclusions")
    def apollo_exclusions(
        request: Request,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        settings = _settings(request)
        paths = [
            settings.project_root / "old_pois" / "offsetx_auto_exclusion_ledger.csv",
            settings.data_dir / "old_pois" / "offsetx_auto_exclusion_ledger.csv",
        ]
        paths.extend(
            settings.project_root.glob("output*/runs/*/offsetx_new_accepts_for_exclusion.csv")
        )
        items, total = read_apollo_exclusion_ledgers(paths, limit=limit, offset=offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

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
                    strategy=body.fallback_strategy,
                    audit_callback=engine.store.record_provider_call,
                )
            elif body.provider:
                provider = create_guarded_provider(
                    ProviderConfig(**body.provider.model_dump()),
                    data_policy=body.data_policy,
                    audit_callback=engine.store.record_provider_call,
                    profile_id="request-supplied",
                )
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

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts/bulk-replace")
    def bulk_replace_drafts_endpoint(
        campaign_id: str, body: DraftBulkReplace, request: Request
    ) -> dict[str, Any]:
        if not body.draft_ids and not body.stages:
            raise HTTPException(status_code=400, detail="Select draft_ids or stages")
        with request.app.state.campaign_locks.hold(campaign_id):
            return _engine(request).bulk_replace_drafts(
                campaign_id,
                find=body.find,
                replace=body.replace,
                draft_ids=body.draft_ids,
                stages=body.stages,
                fields=body.fields,
                preview_only=body.preview_only,
            )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/drafts/schedule")
    def schedule_drafts_endpoint(
        campaign_id: str, body: DraftSchedule, request: Request
    ) -> dict[str, int]:
        return _engine(request).schedule_drafts(
            campaign_id,
            draft_ids=body.draft_ids,
            scheduled_at=body.scheduled_at,
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
