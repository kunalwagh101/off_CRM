from __future__ import annotations

import hmac
import os
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
from ..ai.failures import describe_kinds as describe_failure_kinds
from ..campaigns import list_kinds as list_campaign_kinds
from ..distribution.engine import DistributionEngine
from ..distribution.platforms import list_platforms as list_distribution_platforms
from ..distribution.pipeline import TrendPipeline
from ..distribution.publishers import LocalOutboxPublisher
from ..distribution.trends import TrendWatcher
from ..distribution.youtube import YouTubeClient, YouTubeError
from ..distribution.store import DistributionStore
from ..imagery.engine import ImageCampaignEngine
from ..imagery.store import ImageStore
from ..video.edits import OPERATIONS as VIDEO_OPERATIONS
from ..video.engine import VideoEditorEngine
from ..video.store import VideoStore
from ..video.timeline import FRAME_RATES, PRESETS as CANVAS_PRESETS, TICKS_PER_SECOND
from ..db import resolve_target as resolve_database_target
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
    CACHEABLE_TASK_TYPES,
    ProviderFailure,
    NEVER_CACHE_TASK_TYPES,
    ResponseCache,
    checks_for,
    DataClass,
    DataPolicy,
    build_payload,
    coerce_policy,
    scan_payload,
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
from ..ai.context import ContextLayer
from ..ai.recall import MAX_SNIPPETS_IN_PAYLOAD, SentMailIndex
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
        # Both are built before the engine: sending writes through them.
        app.state.ai_context = ContextLayer(resolved.data_dir / "ai_context.db")
        app.state.ai_recall = SentMailIndex(resolved.data_dir / "ai_recall.db")
        app.state.engine = OutreachEngine(
            resolved.database_path,
            template_counter=app.state.ai_context,
            mail_archive=app.state.ai_recall,
        )
        app.state.ai_chat = AIChatService(app.state.engine.store)
        app.state.sales = SalesTracker(app.state.engine.store)
        app.state.campaign_locks = CampaignLocks()
        app.state.maintenance_lock = threading.Lock()
        app.state.provider_profiles = ProviderProfileStore(resolved.data_dir)
        app.state.ai_registry = ProviderRegistry()
        app.state.ai_workspaces = WorkspaceAISettingsStore(
            resolved.data_dir, app.state.ai_registry
        )
        # Resolved rather than passed straight through, so OFFSETX_DATABASE_URL
        # can move the log off a disposable disk without every call site
        # learning about it. On a deployment whose filesystem does not survive
        # a restart, the audit trail is the one thing that must not live there.
        app.state.ai_egress_log = EgressLog(
            resolve_database_target(default=resolved.data_dir / "ai_egress.db")
        )
        app.state.ai_quota = QuotaTracker(resolved.data_dir)
        # The cache only reuses answers for task types on its allowlist — work
        # whose output is a fact, never work whose output is a message. Drafting
        # is excluded by name: at pseudonymous policy two prospects with the same
        # title and an equivalent hook build a byte-identical payload, so a hit
        # would send them the same email.
        app.state.ai_cache = ResponseCache(resolved.data_dir / "ai_cache.db")
        app.state.ai_broker = EgressBroker(
            registry=app.state.ai_registry,
            credential_resolver=lambda provider_id: "",
            quota=app.state.ai_quota,
            logger=app.state.ai_egress_log.record,
            cache=app.state.ai_cache,
        )
        app.state.image_store = ImageStore(
            resolved.data_dir / "imagery.db",
            assets_dir=resolved.data_dir / "image_assets",
        )
        app.state.distribution_store = DistributionStore(
            resolved.data_dir / "distribution.db",
            outbox_dir=resolved.data_dir / "post_outbox",
        )
        app.state.video_store = VideoStore(
            resolved.data_dir / "video.db",
            renders_dir=resolved.data_dir / "video_renders",
        )
        app.state.trends_path = resolved.data_dir / "trends.db"
        app.state.notion = NotionSettingsStore(resolved.data_dir)
        app.state.discovery_fetcher_factory = None
        app.state.automation = AutomationService(
            resolved.data_dir / "automation.json",
            # The unattended sender records too, or overnight runs go unlogged.
            engine_factory=lambda: OutreachEngine(
                resolved.database_path,
                template_counter=app.state.ai_context,
                mail_archive=app.state.ai_recall,
            ),
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
            app.state.image_store.close()
            app.state.distribution_store.close()
            app.state.video_store.close()
            app.state.ai_context.close()
            app.state.ai_recall.close()

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

    @app.exception_handler(ProviderFailure)
    async def provider_failure_classified(_: Request, exc: ProviderFailure) -> JSONResponse:
        """A failure the broker refused to work around.

        502 rather than 503: the upstream gave a definite answer and off_CRM
        chose not to route around it. The body carries the kind and what the
        owner has to do, because "try again later" is the wrong advice for a
        rejected key.
        """
        return JSONResponse(status_code=502, content=exc.to_dict())

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
            request.app.state.engine = OutreachEngine(
                settings.database_path,
                template_counter=request.app.state.ai_context,
                mail_archive=request.app.state.ai_recall,
            )
            return result
        finally:
            if getattr(request.app.state, "engine", None) is current_engine:
                request.app.state.engine = OutreachEngine(
                    settings.database_path,
                    template_counter=request.app.state.ai_context,
                    mail_archive=request.app.state.ai_recall,
                )
            await automation.start()
            request.app.state.maintenance_lock.release()

    @app.get(f"{API_PREFIX}/campaigns")
    def campaigns(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        status: str = Query("", max_length=20),
        search: str = Query("", max_length=120),
        kind: str = Query("", max_length=40),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_campaigns(
            limit=limit, offset=offset, status=status, search=search, kind=kind
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def _imagery(request: Request) -> ImageCampaignEngine:
        """The image runner, wired to the same broker as everything else.

        Built per request rather than held on app.state, because it needs the
        workspace's credential resolver — and a long-lived engine holding one
        workspace's key would be the wrong shape the day there are two.
        """
        state = request.app.state
        workspace_id = _workspace_id(request)
        state.ai_broker.credential_resolver = state.ai_workspaces.credential_resolver(
            workspace_id
        )
        return ImageCampaignEngine(
            store=state.image_store,
            broker=state.ai_broker,
            settings_resolver=state.ai_workspaces.egress_settings,
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            workspace_id=workspace_id,
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-briefs", status_code=201)
    def add_image_brief(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        engine = _imagery(request)
        brief_id = engine.add_brief(
            campaign_id,
            brief=str(body.get("brief", "")),
            width=int(body.get("width") or 0),
            height=int(body.get("height") or 0),
            wanted=int(body.get("wanted") or 1),
        )
        return engine.store.get_brief(brief_id)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-briefs")
    def list_image_briefs(campaign_id: str, request: Request) -> dict[str, Any]:
        engine = _imagery(request)
        engine._require_own_kind(campaign_id, "listing briefs")
        return {"items": engine.store.list_briefs(campaign_id)}

    @app.post(f"{API_PREFIX}/image-briefs/{{brief_id}}/generate")
    def generate_images(brief_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        engine = _imagery(request)
        return engine.generate(
            brief_id,
            count=int(body.get("count") or 3),
            provider_id=str(body.get("provider_id", "")).strip(),
        ).to_dict()

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-queue")
    def image_review_queue(campaign_id: str, request: Request) -> dict[str, Any]:
        """What is waiting for a swipe."""
        engine = _imagery(request)
        return {"items": engine.review_queue(campaign_id)}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-assets")
    def list_image_assets(
        campaign_id: str,
        request: Request,
        status: str = Query("approved", max_length=20),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        """Pictures by status — the kept ones, by default.

        The review queue answers "what still needs a verdict". This answers
        "what survived one", which is what the video editor puts on a timeline.
        """
        engine = _imagery(request)
        engine._require_own_kind(campaign_id, "listing pictures")
        return {"items": engine.store.list_assets(campaign_id, status=status, limit=limit)}

    @app.get(f"{API_PREFIX}/image-assets/{{asset_id}}/file")
    def image_asset_file(asset_id: str, request: Request):
        """The picture itself.

        Served from disk rather than inlined into JSON: a review queue of fifty
        base64 blobs is a response nobody wants, and the browser caches a file.
        """
        asset = request.app.state.image_store.get_asset(asset_id)
        path = Path(str(asset.get("path") or ""))
        if not path.exists():
            raise HTTPException(404, detail={"error": "gone", "message": "This picture was discarded."})
        return FileResponse(path, media_type=str(asset.get("media_type") or "image/png"))

    @app.post(f"{API_PREFIX}/image-assets/{{asset_id}}/decide")
    def decide_image(asset_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Swipe right, swipe left, or refresh.

        One endpoint for all three because they are one decision with three
        outcomes, and because every one of them scores the generator.
        """
        engine = _imagery(request)
        decision = str(body.get("decision", "")).strip().lower()
        if decision == "approve":
            return {"asset": engine.approve(asset_id)}
        if decision == "reject":
            return {"asset": engine.reject(asset_id)}
        if decision == "regenerate":
            return {"round": engine.regenerate(asset_id).to_dict()}
        raise HTTPException(
            400,
            detail={
                "error": "unknown_decision",
                "message": "decision must be approve, reject or regenerate.",
            },
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-summary")
    def image_summary(campaign_id: str, request: Request) -> dict[str, Any]:
        return _imagery(request).summary(campaign_id)

    # ── the video editor ────────────────────────────────────────────────────

    def _video(request: Request) -> VideoEditorEngine:
        """The timeline runner.

        No broker: nothing here calls a model. Editing is arithmetic on a
        document, and the AI features that will sit on top of it — captions,
        cutout, reframe — each go through the broker on their own terms when
        they exist. Wiring one in now would be a dependency with no caller.
        """
        state = request.app.state
        return VideoEditorEngine(
            store=state.video_store,
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            asset_reader=state.image_store.get_asset,
            workspace_id=_workspace_id(request),
        )

    @app.get(f"{API_PREFIX}/video/presets")
    def video_presets() -> dict[str, Any]:
        """The canvas shapes and frame rates a project may declare."""
        return {
            "ticks_per_second": TICKS_PER_SECOND,
            "presets": [
                {"id": name, "width": size[0], "height": size[1]}
                for name, size in sorted(CANVAS_PRESETS.items())
            ],
            "frame_rates": sorted(FRAME_RATES),
            "operations": sorted(VIDEO_OPERATIONS),
        }

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects", status_code=201)
    def create_video_project(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _video(request).create_project(
            campaign_id,
            name=str(body.get("name") or "Untitled"),
            preset=str(body.get("preset") or "vertical"),
            fps=str(body.get("fps") or "30"),
            width=int(body.get("width") or 0),
            height=int(body.get("height") or 0),
        ).to_dict()

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects")
    def list_video_projects(campaign_id: str, request: Request) -> dict[str, Any]:
        return {"items": _video(request).list_projects(campaign_id)}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-summary")
    def video_summary(campaign_id: str, request: Request) -> dict[str, Any]:
        return _video(request).summary(campaign_id)

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}")
    def get_video_project(project_id: str, request: Request) -> dict[str, Any]:
        return _video(request).open_project(project_id).to_dict()

    @app.delete(f"{API_PREFIX}/video-projects/{{project_id}}")
    def delete_video_project(project_id: str, request: Request) -> dict[str, str]:
        _video(request).delete_project(project_id)
        return {"status": "deleted"}

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/edit")
    def edit_video_project(project_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """One edit, or several stored as one step of undo.

        A drag produces a stream of moves and undo should return to where the
        drag began, not to the middle of it — so the batch form exists and is
        the one the timeline UI uses.
        """
        engine = _video(request)
        operations = body.get("operations")
        if isinstance(operations, list) and operations:
            return engine.batch(project_id, operations).to_dict()
        return engine.edit(
            project_id,
            str(body.get("op") or body.get("operation") or ""),
            body.get("params") or {},
        ).to_dict()

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/undo")
    def undo_video_project(project_id: str, request: Request) -> dict[str, Any]:
        try:
            return _video(request).undo(project_id).to_dict()
        except LookupError as exc:
            raise HTTPException(409, detail={"error": "nothing_to_undo", "message": str(exc)})

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/redo")
    def redo_video_project(project_id: str, request: Request) -> dict[str, Any]:
        try:
            return _video(request).redo(project_id).to_dict()
        except LookupError as exc:
            raise HTTPException(409, detail={"error": "nothing_to_redo", "message": str(exc)})

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/history")
    def video_project_history(
        project_id: str, request: Request, limit: int = Query(50, ge=1, le=300)
    ) -> dict[str, Any]:
        return {"items": _video(request).history(project_id, limit=limit)}

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/manifest")
    def video_project_manifest(project_id: str, request: Request) -> dict[str, Any]:
        """What the browser needs to draw this project, and what is wrong with it."""
        return _video(request).manifest(project_id)

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/frame")
    def video_project_frame(
        project_id: str, request: Request, tick: int = Query(0, ge=0)
    ) -> dict[str, Any]:
        """The server's answer for one instant.

        The browser resolves frames itself for playback; this exists so the two
        can be compared, by a person or by a test, without reading either
        implementation.
        """
        return _video(request).frame(project_id, tick)

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/place-asset")
    def place_video_asset(project_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Put a generated picture on the timeline."""
        return _video(request).place_asset(
            project_id,
            asset_id=str(body.get("asset_id") or ""),
            track_id=str(body.get("track_id") or ""),
            start=int(body.get("start", -1)),
            duration=int(body.get("duration") or 0),
        ).to_dict()

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/renders", status_code=201)
    async def upload_video_render(
        project_id: str,
        request: Request,
        file: UploadFile = File(...),
        renderer: str = Form(""),
    ) -> dict[str, Any]:
        """The exported file, on its way back from the browser.

        Multipart rather than base64: an export is tens of megabytes and base64
        costs a third more for nothing. The gates run here, against the project
        the file claims to be a render of, because a check the browser runs on
        its own output is a check that cannot fail.
        """
        payload = await file.read()
        return _video(request).store_render(project_id, payload, renderer=renderer)

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/renders")
    def list_video_renders(project_id: str, request: Request) -> dict[str, Any]:
        return {"items": _video(request).renders(project_id)}

    @app.get(f"{API_PREFIX}/video-renders/{{render_id}}/file")
    def video_render_file(render_id: str, request: Request):
        """The exported video itself, served from disk."""
        render = request.app.state.video_store.get_render(render_id)
        path = Path(str(render.get("path") or ""))
        if not path.exists():
            raise HTTPException(
                404, detail={"error": "gone", "message": "This render is no longer on disk."}
            )
        return FileResponse(path, media_type=str(render.get("media_type") or "video/webm"))

    def _distribution(request: Request) -> DistributionEngine:
        state = request.app.state
        return DistributionEngine(
            store=state.distribution_store,
            publisher=LocalOutboxPublisher(state.distribution_store.outbox_dir),
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            asset_reader=state.image_store.get_asset,
            workspace_id=_workspace_id(request),
        )

    def _trends(request: Request) -> TrendWatcher:
        """The competitor watcher, with a client only if a key is configured.

        Without a key the watcher still reads what it has already collected —
        the stored picture is useful on its own, and refusing to show it because
        a key is missing would hide data the owner already paid quota for.
        """
        state = request.app.state
        key = os.getenv("OFFSETX_YOUTUBE_API_KEY", "").strip()
        client = None
        if key:
            client = YouTubeClient(key, logger=state.ai_egress_log.record)
        return TrendWatcher(
            database_path=state.trends_path,
            client=client,
            workspace_id=_workspace_id(request),
        )

    @app.get(f"{API_PREFIX}/trends")
    def trends_report(request: Request, window_hours: int = Query(72, ge=1, le=720)) -> dict[str, Any]:
        """What is rising across the watched channels."""
        watcher = _trends(request)
        try:
            return watcher.report(window_hours=window_hours)
        finally:
            watcher.close()

    def _pipeline(request: Request, *, angle: str = "") -> TrendPipeline:
        """The trend-to-post pipeline, with a writer backed by the broker.

        The data class is chosen by what is actually being sent. Topic terms and
        competitor video titles are public, so a public request goes to whichever
        model is cheapest and permitted. An owner angle is the owner's own
        positioning and is not public, so supplying one makes it campaign class
        and the tier rules narrow accordingly — without this module deciding
        anything, because the broker already knows what each tier may receive.
        """
        state = request.app.state
        workspace_id = _workspace_id(request)
        settings = state.ai_workspaces.egress_settings(workspace_id)
        state.ai_broker.credential_resolver = state.ai_workspaces.credential_resolver(
            workspace_id
        )
        data_class = DataClass.CAMPAIGN if angle.strip() else DataClass.PUBLIC

        def writer(kind: str, prompt: str) -> str:
            result = state.ai_broker.call(
                EgressRequest(
                    task_type=f"trend_{kind}",
                    data_class=data_class,
                    instructions=prompt,
                ),
                settings,
                system_prompt=(
                    "You write short, plain copy for a marketing team. No "
                    "preamble, no explanation — return only what was asked for."
                ),
            )
            return result.text

        return TrendPipeline(
            trends=_trends(request),
            images=_imagery(request),
            distribution=_distribution(request),
            writer=writer,
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            workspace_id=workspace_id,
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/pipeline/plan")
    def pipeline_plan(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Topic to candidates, stopping at the review queue.

        It stops there on purpose: the next step is a person looking at the
        pictures, and no version of this should skip it.
        """
        angle = str(body.get("angle", ""))
        pipeline = _pipeline(request, angle=angle)
        return pipeline.plan(
            distribution_campaign_id=campaign_id,
            image_campaign_id=str(body.get("image_campaign_id", "")),
            window_hours=int(body.get("window_hours") or 72),
            min_channels=int(body.get("min_channels") or 3),
            max_topics=int(body.get("max_topics") or 3),
            candidates=int(body.get("candidates") or 3),
            angle=angle,
        ).to_dict()

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/pipeline/draft")
    def pipeline_draft(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Kept pictures to draft posts, stopping before approval.

        A draft still needs the approval the distribution runner has always
        required before anything can be scheduled.
        """
        angle = str(body.get("angle", ""))
        pipeline = _pipeline(request, angle=angle)
        return pipeline.draft(
            distribution_campaign_id=campaign_id,
            image_campaign_id=str(body.get("image_campaign_id", "")),
            account_ids=[str(item) for item in (body.get("account_ids") or [])],
            angle=angle,
        ).to_dict()

    @app.get(f"{API_PREFIX}/trends/topics")
    def trends_topics(
        request: Request,
        window_hours: int = Query(72, ge=1, le=720),
        min_channels: int = Query(3, ge=2, le=50),
    ) -> dict[str, Any]:
        """What several watched channels are covering at once.

        A stronger signal than any single outlier: one channel running hot is a
        good week, several on one subject is an event.
        """
        watcher = _trends(request)
        try:
            return {
                "items": watcher.topics(
                    window_hours=window_hours, min_channels=min_channels
                )
            }
        finally:
            watcher.close()

    @app.get(f"{API_PREFIX}/trends/channels")
    def trends_channels(request: Request) -> dict[str, Any]:
        watcher = _trends(request)
        try:
            return {"items": watcher.watched()}
        finally:
            watcher.close()

    @app.post(f"{API_PREFIX}/trends/channels", status_code=201)
    def watch_channel(body: dict[str, Any], request: Request) -> dict[str, Any]:
        watcher = _trends(request)
        try:
            return watcher.watch(str(body.get("handle", "")))
        except YouTubeError as exc:
            raise HTTPException(
                422, detail={"error": "youtube", "message": str(exc)}
            ) from exc
        finally:
            watcher.close()

    @app.post(f"{API_PREFIX}/trends/sweep")
    def sweep_trends(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Read recent uploads for every watched channel.

        Uploads playlists, never search — see distribution/youtube.py for the
        quota arithmetic that makes that the only workable choice.
        """
        watcher = _trends(request)
        try:
            return watcher.sweep(
                per_channel=int(body.get("per_channel") or 10),
                limit=int(body.get("limit") or 0),
            ).to_dict()
        except YouTubeError as exc:
            raise HTTPException(
                422, detail={"error": "youtube", "message": str(exc)}
            ) from exc
        finally:
            watcher.close()

    @app.get(f"{API_PREFIX}/distribution/platforms")
    def distribution_platforms() -> dict[str, Any]:
        """What each platform permits, and what off_CRM refuses.

        Served rather than hard-coded in the UI, because the answer is the
        product: most of these cannot be posted to yet, and the screen should
        say which and why instead of offering a button that fails.
        """
        return {"items": list_distribution_platforms()}

    @app.get(f"{API_PREFIX}/distribution/accounts")
    def distribution_accounts(request: Request) -> dict[str, Any]:
        return {"items": _distribution(request).accounts()}

    @app.post(f"{API_PREFIX}/distribution/accounts", status_code=201)
    def connect_distribution_account(body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _distribution(request).connect_account(
            platform=str(body.get("platform", "")),
            handle=str(body.get("handle", "")),
            label=str(body.get("label", "")),
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/goals", status_code=201)
    def set_distribution_goal(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _distribution(request).set_goal(
            campaign_id,
            metric=str(body.get("metric", "views")),
            target=int(body.get("target") or 0),
            deadline=str(body.get("deadline", "")),
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/posts", status_code=201)
    def plan_distribution_post(campaign_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _distribution(request).plan_post(
            campaign_id,
            account_id=str(body.get("account_id", "")),
            caption=str(body.get("caption", "")),
            asset_id=str(body.get("asset_id", "")),
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/posts")
    def list_distribution_posts(campaign_id: str, request: Request, status: str = Query("", max_length=20)) -> dict[str, Any]:
        engine = _distribution(request)
        engine._require_own_kind(campaign_id, "listing posts")
        return {"items": engine.store.list_posts(campaign_id, status=status)}

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/approve")
    def approve_distribution_post(post_id: str, request: Request) -> dict[str, Any]:
        return _distribution(request).approve(post_id)

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/schedule")
    def schedule_distribution_post(post_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _distribution(request).schedule(post_id, at=str(body.get("at", "")))

    @app.post(f"{API_PREFIX}/distribution/publish-due")
    def publish_due_posts(request: Request) -> dict[str, Any]:
        return _distribution(request).publish_due().to_dict()

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/metrics")
    def record_post_metrics(post_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        return _distribution(request).record_metrics(
            post_id,
            views=int(body.get("views") or 0),
            likes=int(body.get("likes") or 0),
            comments=int(body.get("comments") or 0),
            shares=int(body.get("shares") or 0),
            source=str(body.get("source", "")),
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/progress")
    def distribution_progress(campaign_id: str, request: Request) -> dict[str, Any]:
        engine = _distribution(request)
        return {
            **engine.progress(campaign_id),
            "generators": engine.generator_performance(campaign_id),
        }

    @app.get(f"{API_PREFIX}/campaign-kinds")
    def campaign_kinds() -> dict[str, Any]:
        """What kinds of campaign exist, and which of them can actually run.

        Serves the unimplemented ones too, with what is missing from each. A
        picker that silently omits them looks like the feature was never
        planned; one that shows them greyed out with a reason says where the
        product is going.
        """
        return {"items": list_campaign_kinds()}

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
                kind=body.kind,
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
        """The run modes plus which ones are usable right now.

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
        verified     → a cheap model writes, deterministic checks judge, and
                       failures go back for repair before a trusted model reads it
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
                    "message": (
                        "Mode must be one of: "
                        + ", ".join(item.value for item in RunMode)
                        + "."
                    ),
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
            elif mode is RunMode.VERIFIED:
                # The rules come from the eval suite, so what production
                # enforces is exactly what the harness measures.
                suite_id = str(body.get("checks_suite", "")).strip()
                checks = checks_for(suite_id, _evals_path()) if suite_id else ()
                result = runner.run_verified(
                    egress,
                    settings,
                    system_prompt=system_prompt,
                    checks=checks,
                    max_rounds=int(body.get("max_rounds", 3)),
                    provider_id=str(body.get("provider_id", "")).strip(),
                    review=bool(body.get("review", True)),
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

    @app.post(f"{API_PREFIX}/ai/image")
    def ai_image(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Draw a picture from a prompt.

        Same gate as everything else: the prompt is text, so if it names a real
        person it is person data and the trust rules apply unchanged.
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        broker.credential_resolver = workspaces.credential_resolver(workspace_id)

        prompt = str(body.get("prompt", "")).strip()[:4000]
        if not prompt:
            raise HTTPException(
                400,
                detail={"error": "empty_prompt", "message": "Describe the picture you want."},
            )

        raw_class = str(body.get("data_class", "public")).strip().lower()
        if raw_class not in {"public", "person_public"}:
            raise HTTPException(
                400,
                detail={
                    "error": "invalid_data_class",
                    "message": "Image prompts run as 'public' or 'person_public'.",
                },
            )

        egress = EgressRequest(
            task_type="image_generation",
            data_class=DataClass(raw_class),
            instructions=prompt,
            task_tags=("image",),
        )
        try:
            result = broker.call_image(
                egress, settings, provider_id=str(body.get("provider_id", "")).strip()
            )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc
        return result.to_dict()

    # ── context layer: where a job is, and which templates earn replies ──

    def _context(request: Request) -> ContextLayer:
        return request.app.state.ai_context

    @app.get(f"{API_PREFIX}/ai/context")
    def ai_context_overview(request: Request) -> dict[str, Any]:
        """Everything the Memory screen needs in one call."""
        layer = _context(request)
        workspace_id = _workspace_id(request)
        return {
            "stats": layer.stats(workspace_id),
            "templates": [score.to_dict() for score in layer.scoreboard(workspace_id)],
            "tasks": [task.to_dict() for task in layer.open_tasks(workspace_id)],
            "reference": layer.reference_for_models(workspace_id),
        }

    @app.post(f"{API_PREFIX}/ai/context/templates")
    def ai_register_template(body: dict[str, Any], request: Request) -> dict[str, Any]:
        template_id = str(body.get("template_id", "")).strip()
        if not template_id:
            raise HTTPException(
                400, detail={"error": "missing_template", "message": "A template id is required."}
            )
        score = _context(request).register_template(
            workspace_id=_workspace_id(request),
            template_id=template_id,
            variant_id=str(body.get("variant_id", "")).strip(),
            label=str(body.get("label", "")),
            template_text=str(body.get("template_text", "")),
            parent_id=str(body.get("parent_id", "")).strip(),
        )
        return score.to_dict()

    @app.post(f"{API_PREFIX}/ai/context/templates/{{template_id}}/rewrite")
    def ai_rewrite_template(
        template_id: str, body: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        """Ask a model to improve a weak template.

        What leaves: the template text, two numbers, and optionally the winning
        template. No recipient, no name, no address — so this runs as public work
        and any permitted model can do it.
        """
        broker, workspaces, _ = _ai(request)
        layer = _context(request)
        workspace_id = _workspace_id(request)
        variant_id = str(body.get("variant_id", "")).strip()

        score = layer.score_for(workspace_id, template_id, variant_id)
        if score is None:
            raise HTTPException(404, "That template has no record yet.")
        if not score.template_text:
            raise HTTPException(
                400,
                detail={
                    "error": "no_template_text",
                    "message": "Save the template text first, so there is something to improve.",
                },
            )

        settings = workspaces.egress_settings(workspace_id)
        broker.credential_resolver = workspaces.credential_resolver(workspace_id)
        egress = layer.rewrite_request(
            score,
            winner=layer.winner(workspace_id) if body.get("use_winner", True) else None,
        )
        try:
            result = broker.call(egress, settings, system_prompt=AIChatService.DEFAULT_SYSTEM_PROMPT)
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc

        # Nothing goes live automatically. The owner approves the new wording.
        return {
            "current": score.to_dict(),
            "suggested_text": result.text,
            "written_by": result.provider_name,
            "model_id": result.model_id,
            "log_id": result.log_id,
            "needs_approval": True,
        }

    @app.post(f"{API_PREFIX}/ai/context/templates/{{template_id}}/approve")
    def ai_approve_rewrite(
        template_id: str, body: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        """Save an approved rewrite as a new variant to test against the old one."""
        layer = _context(request)
        workspace_id = _workspace_id(request)
        text = str(body.get("template_text", "")).strip()
        if not text:
            raise HTTPException(
                400, detail={"error": "empty_text", "message": "There is no wording to save."}
            )
        score = layer.register_template(
            workspace_id=workspace_id,
            template_id=template_id,
            variant_id=str(body.get("variant_id", "b")).strip() or "b",
            label=str(body.get("label", "Rewritten")),
            template_text=text,
            parent_id=str(body.get("parent_variant_id", "")).strip(),
        )
        return score.to_dict()

    @app.post(f"{API_PREFIX}/ai/context/tasks")
    def ai_start_task(body: dict[str, Any], request: Request) -> dict[str, Any]:
        task = _context(request).start_task(
            workspace_id=_workspace_id(request),
            kind=str(body.get("kind", "campaign")),
            title=str(body.get("title", "")),
            steps=[str(step) for step in (body.get("steps") or [])],
        )
        return task.to_dict()

    @app.post(f"{API_PREFIX}/ai/context/tasks/{{task_id}}/step")
    def ai_finish_step(task_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        task = _context(request).finish_step(
            task_id,
            int(body.get("step_index", 0)),
            note=str(body.get("note", "")),
            status=str(body.get("status", "done")),
        )
        if task is None:
            raise HTTPException(404, "No such job.")
        return task.to_dict()

    @app.post(f"{API_PREFIX}/ai/context/tasks/{{task_id}}/decision")
    def ai_record_decision(task_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        text = str(body.get("decision", "")).strip()
        if not text:
            raise HTTPException(
                400, detail={"error": "empty_decision", "message": "Write the decision down first."}
            )
        task = _context(request).record_decision(task_id, text)
        if task is None:
            raise HTTPException(404, "No such job.")
        return task.to_dict()

    # ── recall over sent mail ──────────────────────────────────────────────

    def _recall(request: Request) -> SentMailIndex:
        return request.app.state.ai_recall

    @app.get(f"{API_PREFIX}/ai/recall")
    def ai_recall_overview(request: Request) -> dict[str, Any]:
        index = _recall(request)
        workspace_id = _workspace_id(request)
        return {
            "stats": index.stats(workspace_id),
            "recent": [item.to_dict() for item in index.recent(workspace_id=workspace_id, limit=8)],
        }

    @app.post(f"{API_PREFIX}/ai/recall/search")
    def ai_recall_search(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Search past sent mail.

        Runs entirely on this machine — no provider is contacted and no key is
        used.  The rows returned are the redacted ones; there is no un-redacted
        copy for this endpoint to return.
        """
        query = str(body.get("query", "")).strip()
        results = _recall(request).search(
            query,
            workspace_id=_workspace_id(request),
            limit=min(20, max(1, int(body.get("limit", 5) or 5))),
            replied_only=bool(body.get("replied_only", False)),
        )
        return {
            "query": query,
            "results": [item.to_dict() for item in results],
            "sent_anywhere": False,
        }

    @app.post(f"{API_PREFIX}/ai/recall/rebuild")
    def ai_recall_rebuild(request: Request) -> dict[str, Any]:
        """Index everything already sent. Local work; nothing leaves."""
        index = _recall(request)
        result = index.rebuild(request.app.state.engine.store, workspace_id=_workspace_id(request))
        return {**result, "stats": index.stats(_workspace_id(request))}

    @app.post(f"{API_PREFIX}/ai/recall/preview")
    def ai_recall_preview(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Show exactly what a model would receive, before anything is sent.

        Built through the real payload builder and run through the real scanner,
        so this is the outbound bytes rather than a description of them.
        """
        index = _recall(request)
        snippets = index.search(
            str(body.get("query", "")).strip(),
            workspace_id=_workspace_id(request),
            limit=MAX_SNIPPETS_IN_PAYLOAD,
            replied_only=bool(body.get("replied_only", False)),
        )
        egress = index.recall_request(
            snippets, instructions=str(body.get("instructions", "")).strip()
        )
        policy = coerce_policy(body.get("data_policy"), default=DataPolicy.STANDARD)
        payload = build_payload(egress, policy)
        report = scan_payload(payload, policy=policy)
        return {
            "data_class": egress.data_class.value,
            "data_policy": policy.value,
            "used": [item.to_dict() for item in snippets],
            "payload": payload,
            "scan": report.to_dict(),
        }

    @app.post(f"{API_PREFIX}/ai/recall/forget")
    def ai_recall_forget(body: dict[str, Any], request: Request) -> dict[str, Any]:
        """Remove indexed mail. Redaction is not an answer to a deletion request."""
        index = _recall(request)
        contact_id = str(body.get("campaign_contact_id", "")).strip()
        message_id = str(body.get("message_id", "")).strip()
        if contact_id:
            return {"removed": index.forget_contact(contact_id)}
        if message_id:
            index.forget_message(message_id)
            return {"removed": 1}
        if body.get("everything"):
            return {"removed": index.clear(workspace_id=_workspace_id(request))}
        raise HTTPException(
            400,
            detail={
                "error": "nothing_named",
                "message": "Name a person, a message, or ask to clear everything.",
            },
        )

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

    @app.get(f"{API_PREFIX}/ai/failure-kinds")
    def ai_failure_kinds() -> dict[str, Any]:
        """Every failure kind, what off_CRM does about it, and the owner action.

        Served so the inspector can label a `failure_kind` from the egress log
        without hard-coding the taxonomy in the frontend.
        """
        return {"items": describe_failure_kinds()}

    @app.get(f"{API_PREFIX}/ai/cache/stats")
    def ai_cache_stats(request: Request) -> dict[str, Any]:
        """Measured, not assumed.

        The published 60-90% cache hit rates come from chat systems and do not
        apply to personalised outreach. This endpoint is how the owner finds out
        what it is actually worth here.
        """
        cache = request.app.state.ai_cache
        stats = cache.stats(workspace_id=_workspace_id(request))
        stats["cacheable_task_types"] = sorted(CACHEABLE_TASK_TYPES)
        stats["never_cached"] = NEVER_CACHE_TASK_TYPES
        return stats

    @app.post(f"{API_PREFIX}/ai/cache/clear")
    def ai_cache_clear(request: Request) -> dict[str, Any]:
        cleared = request.app.state.ai_cache.clear(
            workspace_id=_workspace_id(request)
        )
        return {"cleared": cleared}

    @app.get(f"{API_PREFIX}/ai/egress-log/stats")
    def ai_egress_stats(request: Request) -> dict[str, Any]:
        _, _, log = _ai(request)
        stats = log.stats(workspace_id=_workspace_id(request))
        # Where the audit trail lives is part of reading it. A log on a disk
        # that resets is worth less than the same log on a database that does
        # not, and the screen should not hide which one you are looking at.
        stats["backend"] = log.backend
        return stats

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
