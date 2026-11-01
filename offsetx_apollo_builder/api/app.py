from __future__ import annotations

import re
import asyncio
import time

import hmac
import os
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager, nullcontext
from contextvars import ContextVar
from datetime import date
from dataclasses import replace
from functools import partial
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__
from ..observability import FailureMiddleware, FailureReporter, reported_reference, failure_message
from .video_upload_guard import VideoUploadBodyGuard
from . import public_demo
from ..agent.active_runs import ChatBrowserRuns
from ..agent.companions import CompanionError, CompanionRegistry
from ..agent.routines import (
    Routine,
    RoutineAgentExecutor,
    RoutineError,
    RoutineService,
    RoutineStore,
)
from ..ai.failures import describe_kinds as describe_failure_kinds
from ..campaigns import list_kinds as list_campaign_kinds
from ..competitor_teardown import CompetitorTeardownError, analyse_public_post
from ..distribution.automation import ContentAutomationService
from ..distribution.pacing import decide as pacing_decide
from ..distribution.pacing import platform_ceiling as pacing_ceiling
from ..distribution.engine import DistributionEngine
from ..distribution.platforms import list_platforms as list_distribution_platforms
from ..distribution.pipeline import TrendPipeline
from ..distribution.publishers import LocalOutboxPublisher
from ..distribution.trends import TrendWatcher
from ..distribution.youtube import YouTubeClient, YouTubeError
from ..distribution.store import DistributionStore
from ..gtm.service import PUBLISHED_COUNT_LIMIT, GtmService
from ..gtm.service import Readers as GtmReaders
from ..gtm.store import GtmStore
from ..gtm.strategy import ModelUnavailable, product_lines
from ..imagery.engine import ImageCampaignEngine
from ..imagery.store import ImageStore
from ..video.captions import MAX_CHARS as CAPTION_MAX_CHARS
from ..video.edits import OPERATIONS as VIDEO_OPERATIONS
from ..video.effects import catalogue as video_effects_catalogue
from ..video.presets import catalogue as video_preset_catalogue
from ..video.recipes import catalogue as video_recipe_catalogue
from ..video.engine import VideoEditorEngine
from ..video.director import build_prompt as video_direction_prompt
from ..video.store import VideoStore
from ..video.timeline import (
    BLEND_MODES,
    FRAME_RATES,
    PRESETS as CANVAS_PRESETS,
    TICKS_PER_SECOND,
)
from ..db import describe_target as describe_database_target
from ..db import resolve_target as resolve_database_target
from ..db import DatabaseError
from ..db.hosted import HostedStorage
from ..outreach.store_copy import check_local_crm
from ..outreach.contact_export import contact_list_csv, ContactExportError
from ..discovery import DiscoveryService
from ..locked_categories import LOCKED_CATEGORIES, DEFAULT_CATEGORY, normalize_category
from ..meetings import MeetingError, MeetingStore, MeetingTranscriber, MeetingTranscriptionError
from ..meetings.service import MAX_MEETING_CHUNK_BYTES
from ..privacy import (
    DELETE_CONFIRMATION,
    PrivacyError,
    PrivacyService,
    SubjectIdentity,
)
from ..io_utils import read_apollo_exclusion_ledgers, read_apollo_rejection_ledgers
from ..outreach.automation import AutomationService
from ..outreach.backup import recover_interrupted_restore, restore_pending
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock
from ..outreach.engine import OutreachEngine
from ..outreach.email_expert import route_for_category
from ..outreach.launch import launch_readiness
from ..outreach.relationships import CampaignRelationships, TaskConflictError
from ..outreach.relationship_ops import RelationshipOperations
from ..outreach.crm_insights import CRMInsights
from ..outreach.crm_operations import CRMOperations
from ..outreach.gmail import GmailMailProvider, LocalOutboxProvider
from ..outreach.deliverability.events import SnsVerifier
from ..outreach.deliverability.models import PermanentDeliveryError
from ..outreach.deliverability.service import EmailDeliveryService
from ..outreach.deliverability.ses import SesMailProvider
from ..outreach.deliverability.store import DeliverabilityStore
from ..outreach.deliverability.unsubscribe import UnsubscribeService
from ..outreach.models import ROUTES, ContactInput, utc_now
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
    default_evals_path,
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
    ToolRegistry,
)
from ..ai.context import ContextLayer
from ..ai.errors import AIModuleError
from ..ai.recall import MAX_SNIPPETS_IN_PAYLOAD, SentMailIndex
from ..ai.discovery import discover_models
from ..ai.workspace import ReasonRequired, WorkspaceAISettingsStore
from ..outreach.provider_profiles import (
    ProfileOwnedElsewhere,
    ProfileUnconfirmed,
    ProviderProfileStore,
)
from ..outreach.providers import ProviderError
from ..outreach.sales import SalesConflictError, SalesTracker
from .auth import LoginAttemptLimiter, SESSION_COOKIE, WorkspaceAuthError, WorkspaceAuthStore
from .config import AppSettings
from ..agent.permissions import AgentPermissionPolicy, ChatPermissionRegistry, PermissionErrorRule
from .storage_readiness import describe_storage_readiness
from .operational_health import describe_operational_health
from .email_delivery import build_email_delivery_router
from .production_runtime import TIMERS, RecoveryGate, install_runtime_routes
from .gtm import build_gtm_router, resolve_angle
from .schemas import (
    AutomationUpdate,
    AgentRoutineCreate,
    AgentPermissionUpdate,
    AttendedChatGrant,
    ReadOnlyChatBrowserRun,
    AgentRoutineUpdate,
    AgentRoutineEvent,
    CampaignCreate,
    CampaignClone,
    CampaignUpdate,
    ReplyTriageUpdate,
    FollowupTaskCreate,
    FollowupTaskUpdate,
    ContactCreate,
    ContactBulkAction,
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
    ProviderProfileConfirm,
    ProviderProfileUpsert,
    ReplySyncRequest,
    SendRequest,
    TemplateImport,
    MemoryApproval,
    MemoryCreate,
    MeetingCreate,
    NotionExportRequest,
    NotionSettingsUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
    AIChatCreateBody,
    AIChatMessageBody,
    AIChatMoveBody,
    AIChatRenameBody,
    AIImageBody,
    AIMailboxUnlockBody,
    AIPlanBody,
    AIProjectCreateBody,
    AIProviderConnectBody,
    AIProviderOverrideBody,
    AIProviderTrustBody,
    AIRecallForgetBody,
    AIRecallPreviewBody,
    AIRecallSearchBody,
    AIRunBody,
    AITaskDecisionBody,
    AITaskStartBody,
    AITaskStepBody,
    AITemplateApproveBody,
    AITemplateRegisterBody,
    AITemplateRewriteBody,
    AIWorkspaceUpdateBody,
    CompanionContextBody,
    CompanionCreateBody,
    CompanionMemoryBody,
    CompanionUpdateBody,
    CompetitorTeardownBody,
    ContentAutomationBody,
    StartPostingBody,
    DistributionAccountCreateBody,
    DistributionAccountUpdateBody,
    DistributionGoalBody,
    DistributionMetricsBody,
    DistributionPostBody,
    DistributionScheduleBody,
    ImageBriefCreateBody,
    ImageDecisionBody,
    ImageGenerateBody,
    PacingDecisionBody,
    PipelineDraftBody,
    PipelinePlanBody,
    PrivacyDeletionBody,
    PrivacySubjectBody,
    TrendSweepBody,
    TrendWatchBody,
    VideoAssembleBody,
    VideoCaptionsBody,
    VideoDecisionBody,
    VideoDirectBody,
    VideoEditBody,
    VideoPlaceAssetBody,
    VideoPlaceMediaBody,
    VideoProjectCreateBody,
    VideoQueueBody,
    VideoTranscribeBody,
)


API_PREFIX = "/api/v1"
LIVE_SEND_CONFIRMATION = "SEND LIVE EMAILS"

# Public API surface is a closed set. Tests enumerate every registered route and
# fail if a new /api endpoint becomes public merely because somebody edited the
# middleware condition. Health probes live outside /api and expose no customer
# data; the frontend shell/static assets also live outside this API boundary.
PUBLIC_API_PATHS: frozenset[str] = frozenset({
    f"{API_PREFIX}/meta",
    f"{API_PREFIX}/auth/session",
    f"{API_PREFIX}/auth/login",
    f"{API_PREFIX}/auth/logout",
    f"{API_PREFIX}/email-delivery/events/ses/sns",
})
PUBLIC_UNSUBSCRIBE_PREFIX = f"{API_PREFIX}/email/unsubscribe/"


def is_public_api_path(path: str) -> bool:
    """Closed public bootstrap/callback allowlist.

    Unsubscribe is the only parameterised public route. It accepts exactly one
    path segment after the prefix; nested/future routes do not inherit public
    access by sharing a string prefix.
    """
    if path in PUBLIC_API_PATHS:
        return True
    if not path.startswith(PUBLIC_UNSUBSCRIBE_PREFIX):
        return False
    token = path[len(PUBLIC_UNSUBSCRIBE_PREFIX):]
    return bool(token) and "/" not in token
#: The services `_close_runtime` closes, users of a store before the store.
#: Everything on app.state with a `close()` must be here — see
#: `test_every_open_service_is_closed_for_a_restore`.
RUNTIME_CLOSE_ORDER: tuple[str, ...] = (
    # Temporary browser approvals must die before the underlying stores close.
    "chat_browser_runs",
    "chat_permission_grants",
    "privacy",
    "ai_tools",
    "engine",
    "ai_cache",
    "ai_egress_log",
    "image_store",
    "distribution_store",
    "video_store",
    "gtm_store",
    "ai_context",
    "ai_recall",
    # Created once for the install, not per restore; each reopens its
    # connection on the next use after a close (S-06.03.02).
    "workspace_auth",
    "hosted_storage",
)
PUBLIC_HEALTH_PATHS: frozenset[str] = frozenset({
    "/health/live",
    "/health/ready",
})
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


#: How long start-up waits for another process — the email worker, mid-cycle —
#: to let go of the workspace before rolling back an interrupted restore.
RECOVERY_WAIT_SECONDS = 120.0


#: The workspace of the request being served: its login's, or `local` for the
#: install token. Missing and unsigned requests use "" (deny by default).
#: Only a deliberately scoped installation timer uses None. The engine is shared by every
#: request, so its product reader cannot be handed a caller — it reads one here
#: (D-125). Set by the security middleware, around the whole request.
_CALLER_WORKSPACE: ContextVar[str | None] = ContextVar("offcrm_caller_workspace", default="")


@contextmanager
def _install_content_scope() -> Iterator[None]:
    """Grant only an explicitly authorised content cycle install-wide product access."""
    marker = _CALLER_WORKSPACE.set(None)
    try:
        yield
    finally:
        _CALLER_WORKSPACE.reset(marker)


def _engine(request: Request) -> OutreachEngine:
    return request.app.state.engine


class _TimerScope:
    """Enough of a request for the per-request factories to work off a timer.

    `_trends`, `_imagery`, `_distribution` and `_pipeline` are built per request
    because they need the workspace's credential resolver. Every one of them
    reads only ``request.app.state`` and the workspace id, which is constant —
    so a timer needs an object with an ``.app`` and nothing else.

    The alternative is changing all four signatures and their thirty call sites
    to take an app, which lands in the same place and leaves two ways to build
    every engine while it is half done.
    """

    __slots__ = ("app",)

    def __init__(self, app: Any) -> None:
        self.app = app

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


def _privacy(request: Request) -> PrivacyService:
    return request.app.state.privacy


def _privacy_subject(body: Any, workspace_id: str) -> SubjectIdentity:
    # The caller resolves the workspace: `_workspace_id` closes over the
    # app's settings inside `create_app`, so a module-level helper cannot
    # call it — doing so was a NameError on every privacy route (D-103).
    subject_value = body.get("subject") if hasattr(body, "get") else None
    payload = (
        subject_value.model_dump()
        if hasattr(subject_value, "model_dump")
        else dict(subject_value or {})
    )
    supplied = str(payload.get("workspace_id") or "").strip()
    if supplied and supplied != workspace_id:
        raise HTTPException(
            status_code=403,
            detail="Privacy requests cannot cross the authenticated workspace boundary",
        )
    payload["workspace_id"] = workspace_id
    return SubjectIdentity.from_mapping(payload)


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


async def _read_video_upload(upload: UploadFile, *, max_bytes: int) -> bytes:
    """Limit the in-memory video payload before codec inspection or persistence.

    Reuse the configured upload ceiling used by contact/expert imports. Starlette
    has already spooled the multipart part by this point; request-stream and
    aggregate concurrency limits are a separate production-audit gate.
    """
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=(
            "Video upload exceeds the configured size limit. "
            "Reduce the file size or ask the operator to change OFFSETX_MAX_UPLOAD_BYTES."
        ))
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded video file is empty")
    return content


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
    public_demo.prepare(resolved)
    resolved.prepare()
    resolved.ensure_session_secret()
    # With OFFSETX_DATABASE_URL, keys, AI settings, the usage counters and the
    # logins live in that database, not in a data folder a free-plan deploy
    # wipes (S-06.03.02). The key is checked against what is stored before
    # anything is served: a start with keys it cannot read is refused here.
    hosted = HostedStorage.configured(resolved.secrets_key)
    if hosted is not None:
        hosted.check_secrets_key()
        # A data folder that still holds these stores is the owner's call,
        # never hidden in silence (D-210).
        hosted.check_local_folder(resolved.data_dir)
    # The CRM follows the database too, by the rule every hosted store uses
    # (S-06.03.03); a CRM file left from before is the owner's call, as above.
    crm = resolve_database_target(default=resolved.database_path)
    if hosted is not None:
        check_local_crm(hosted, resolved.database_path, crm)
    workspace_auth = WorkspaceAuthStore(
        resolved.data_dir / "workspace_auth.db",
        session_secret=resolved.session_secret,
        session_hours=resolved.session_hours,
        database_target=hosted.target if hosted is not None else None,
    )
    workspace_auth.bootstrap(
        username=resolved.demo_username,
        password=resolved.demo_password,
        workspace_id="public-demo" if resolved.public_demo else "local",
    )
    if resolved.public_demo:
        identity = workspace_auth.authenticate(resolved.demo_username, resolved.demo_password)
        if identity is None or identity.workspace_id != "public-demo":
            raise ValueError("Public demo login differs from stored sample account; use an empty dedicated data folder")
    login_limiter = LoginAttemptLimiter()
    loopback = resolved.host in {"127.0.0.1", "localhost", "::1"}

    # Refused here rather than per request, so a misconfiguration is a startup
    # failure instead of an API that quietly serves every contact to anyone who
    # can reach the port. Loopback is not an exemption: an unauthenticated local
    # API is readable by every other process and user on the machine, and by any
    # page that can rebind a hostname to 127.0.0.1.
    if not (resolved.api_token or workspace_auth.enabled or resolved.allow_unauthenticated):
        raise ValueError(
            "off_CRM will not start without authentication. Set "
            "OFFSETX_LOCAL_API_TOKEN, configure the demo login, or start through "
            "run_offsetx_web.py, which provisions a local token for you."
        )
    host_allowlist = resolved.host_allowlist()

    def valid_api_token(request: Request) -> bool:
        if not resolved.api_token:
            return False
        authorization = request.headers.get("authorization", "")
        supplied = request.headers.get("x-offsetx-token", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        return hmac.compare_digest(supplied, resolved.api_token)

    def session_identity(request: Request):
        token = request.cookies.get(SESSION_COOKIE, "")
        identity = workspace_auth.verify(token)
        if identity is not None and resolved.public_demo:
            return replace(identity, workspace_id=public_demo.workspace_for(token))
        return identity

    def _decided_by(request: Request) -> str:
        """Who a recorded decision is from, as the server knows it."""
        identity = session_identity(request)
        if identity is not None:
            return f"{identity.username} ({identity.workspace_id})"
        return "the install's API token" if valid_api_token(request) else "local"

    def _caller(request: Request) -> str | None:
        """The caller's workspace: its login's, `local` for the install token or
        a server run without auth, None for nobody."""
        identity = session_identity(request)
        if identity is not None:
            return identity.workspace_id
        if valid_api_token(request) or resolved.allow_unauthenticated:
            return "local"
        return None

    def security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), microphone=(self), display-capture=(self)"
            if loopback
            else "camera=(), geolocation=(), microphone=(), display-capture=()"
        )
        if not loopback:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' http://127.0.0.1:8766 http://localhost:8766; "
            "img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'"
        )
        return response

    def _attach_products(engine: OutreachEngine, owner: FastAPI) -> OutreachEngine:
        """Every engine's drafts read the product linked to their campaign.

        `S-12.01.02`. Attached here rather than passed to `OutreachEngine`, which
        stays free of anything product- or model-shaped. The store is looked up
        when a draft is written, not now: the engine built at startup exists
        before the product store does. `test_every_engine_is_built_with_products`
        fails if an `OutreachEngine(...)` in this file is ever built without
        this — such an engine would fill `{product_offer}` with a blank.
        """

        def reader(campaign_id: str) -> dict[str, Any] | None:
            store = owner.state.gtm_store
            linked = store.linked_workspace(campaign_id)
            if not linked:
                return None
            caller = _CALLER_WORKSPACE.get()
            # A timer acts for the install, and the link says whose product it
            # is. A request reads only its own workspace's: campaigns, drafts
            # and templates are install-wide, so reading through the link let
            # any login write another workspace's product into drafts it can
            # read (D-125).
            if caller is not None and caller != linked:
                raise PermissionError(
                    "This campaign is linked to another workspace's product, so its "
                    "drafts can only be written from that workspace's login. Ask the "
                    "install owner to unlink it, or use a campaign of your own."
                )
            return store.product_for_campaign(campaign_id, linked)

        engine.email_expert.product_reader = reader
        return engine

    def _open_runtime(app: FastAPI, previous: dict[str, Any]) -> None:
        """Build every service over the workspace on disk.

        Startup calls this, and so does a restore once the restored workspace
        is in place (`S-06.02.21`): one list of services, so a store added here
        is reopened after a restore without being listed twice. ``previous`` is
        the state being replaced; the few hooks set on it from outside — a
        discovery fetcher, a delivery provider — are carried across.
        """
        app.state.hosted_storage = hosted
        app.state.workspace_auth = workspace_auth
        # Both are built before the engine: sending writes through them.
        app.state.ai_context = ContextLayer(resolved.data_dir / "ai_context.db")
        app.state.ai_recall = SentMailIndex(resolved.data_dir / "ai_recall.db")
        app.state.engine = _attach_products(
            OutreachEngine(
                crm,
                template_counter=app.state.ai_context,
                mail_archive=app.state.ai_recall,
            ),
            app,
        )
        app.state.ai_tools = ToolRegistry(resolved.data_dir / "ai_tools.db")
        app.state.companions = CompanionRegistry(
            resolved.data_dir,
            tools=app.state.ai_tools,
            memory_backend=app.state.engine.store,
        )
        app.state.ai_chat = AIChatService(app.state.engine.store)
        # Reopening a restored runtime must revoke grants held by any old runs.
        old_runs = getattr(app.state, "chat_browser_runs", None)
        if old_runs is not None:
            old_runs.close()
        app.state.chat_browser_runs = ChatBrowserRuns()
        old_grants = getattr(app.state, "chat_permission_grants", None)
        if old_grants is not None:
            old_grants.close_all()
        # Attended grants are never restored from a database, backup or another process.
        app.state.chat_permission_grants = ChatPermissionRegistry()
        app.state.sales = SalesTracker(app.state.engine.store)
        app.state.campaign_locks = CampaignLocks()
        delivery_store = DeliverabilityStore(app.state.engine.store)
        unsubscribe = UnsubscribeService.from_path(
            delivery_store,
            resolved.data_dir / "email_unsubscribe.key",
            public_base_url=resolved.public_base_url,
            configured_secret=resolved.unsubscribe_secret,
        )

        def delivery_provider(job: dict[str, Any], identity: dict[str, Any] | None) -> Any:
            provider_type = str(job.get("provider_type", ""))
            if provider_type == "local":
                return LocalOutboxProvider(resolved.data_dir / "mail")
            if provider_type == "ses":
                if not identity:
                    raise PermanentDeliveryError("Amazon SES requires a sending identity")
                return SesMailProvider(
                    region=str(identity["aws_region"]),
                    configuration_set=str(identity["configuration_set"]),
                )
            if provider_type == "gmail":
                raise PermanentDeliveryError(
                    "Durable Gmail jobs are disabled. Use the confirmed Gmail send action for small outreach."
                )
            raise PermanentDeliveryError(f"Unknown email provider: {provider_type}")

        app.state.email_delivery = EmailDeliveryService(
            app.state.engine,
            unsubscribe=unsubscribe,
            provider_factory=delivery_provider,
        )
        app.state.engine.delivery_preflight = app.state.email_delivery.preflight
        app.state.engine.unsubscribe_service = unsubscribe
        app.state.sns_verifier = SnsVerifier()
        app.state.provider_profiles = ProviderProfileStore(resolved.data_dir)
        app.state.ai_registry = ProviderRegistry()
        app.state.ai_workspaces = WorkspaceAISettingsStore(
            resolved.data_dir, app.state.ai_registry, hosted=hosted
        )
        # Resolved rather than passed straight through, so OFFSETX_DATABASE_URL
        # can move the log off a disposable disk without every call site
        # learning about it. On a deployment whose filesystem does not survive
        # a restart, the audit trail is the one thing that must not live there.
        app.state.ai_egress_log = EgressLog(
            resolve_database_target(default=resolved.data_dir / "ai_egress.db")
        )
        app.state.ai_quota = QuotaTracker(resolved.data_dir, hosted=hosted)
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

        def routine_broker(workspace_id: str) -> EgressBroker:
            return app.state.ai_broker.with_credential_resolver(
                app.state.ai_workspaces.credential_resolver(workspace_id)
            )

        app.state.agent_routine_store = RoutineStore(
            resolved.data_dir / "agent_routines.db"
        )
        app.state.agent_routines = RoutineService(
            app.state.agent_routine_store,
            runner=RoutineAgentExecutor(
                data_dir=resolved.data_dir,
                workspaces=app.state.ai_workspaces,
                broker_factory=routine_broker,
            ),
        )

        app.state.meeting_store = MeetingStore(
            resolved.data_dir / "meeting_transcripts.db"
        )
        app.state.meeting_transcriber = MeetingTranscriber(
            store=app.state.meeting_store,
            workspaces=app.state.ai_workspaces,
            broker_factory=routine_broker,
        )
        app.state.image_store = ImageStore(
            resolved.data_dir / "imagery.db",
            assets_dir=resolved.data_dir / "image_assets",
        )
        app.state.distribution_store = DistributionStore(
            resolved.data_dir / "distribution.db",
            outbox_dir=resolved.data_dir / "post_outbox",
        )
        # Resolved rather than passed straight through, so OFFSETX_DATABASE_URL
        # can move timelines onto Postgres. On a host whose filesystem does not
        # survive a restart — Render's free plan writes to /tmp — an edit
        # history in SQLite is an hour of work that disappears when the instance
        # sleeps. The rendered files still need a real disk; the *document* does
        # not, and it is the part that took the work.
        app.state.video_store = VideoStore(
            resolve_database_target(default=resolved.data_dir / "video.db"),
            renders_dir=resolved.data_dir / "video_renders",
        )
        app.state.privacy = PrivacyService.for_local(
            app.state.engine.store,
            data_dir=resolved.data_dir,
            ai_context=app.state.ai_context,
            ai_recall=app.state.ai_recall,
            ai_egress=app.state.ai_egress_log,
            export_dir=resolved.export_dir,
            # Hosted logins are not in the data folder a path would read.
            workspace_accounts=workspace_auth if hosted is not None else None,
        )
        # The product and its plans are the owner's work, like a timeline, so
        # they follow OFFSETX_DATABASE_URL onto Postgres the same way.
        app.state.gtm_store = GtmStore(
            resolve_database_target(default=resolved.data_dir / "gtm.db")
        )
        app.state.trends_path = resolved.data_dir / "trends.db"
        app.state.notion = NotionSettingsStore(resolved.data_dir)
        app.state.discovery_fetcher_factory = None
        app.state.automation = AutomationService(
            resolved.data_dir / "automation.json",
            # The unattended sender records too, or overnight runs go unlogged.
            engine_factory=lambda: _attach_products(
                OutreachEngine(
                    crm,
                    template_counter=app.state.ai_context,
                    mail_archive=app.state.ai_recall,
                ),
                app,
            ),
            mail_provider_factory=lambda mode, authorized: _mail_provider(
                resolved,
                mode,
                LIVE_SEND_CONFIRMATION if authorized else "",
            ),
            own_email_factory=lambda: resolved.own_email,
        )
        # The content engine's own timer. Separate from the email one on
        # purpose: that service is email-shaped — a mail provider, an own
        # address, run_due — and BUILD_STATE's rule is that nothing built from
        # here may assume email.
        app.state.content_automation = ContentAutomationService(
            resolved.data_dir / "content_automation.json",
            trends_factory=lambda: _trends(_TimerScope(app)),
            pipeline_factory=lambda angle: _pipeline(_TimerScope(app), angle=angle),
            distribution_factory=lambda: _distribution(_TimerScope(app)),
            pacing_reader=lambda campaign_id: _pacing_inputs(app, campaign_id),
            angle_resolver=lambda campaign_id, declared: resolve_angle(
                app.state.gtm_store, None, campaign_id, declared
            ),
            timer_context=_install_content_scope,
            campaign_status=lambda campaign_id: str(
                _engine(_TimerScope(app)).store.get_campaign(campaign_id).get("status") or ""
            ),
        )
        if previous.get("discovery_fetcher_factory") is not None:
            app.state.discovery_fetcher_factory = previous["discovery_fetcher_factory"]
        old_delivery = previous.get("email_delivery")
        for hook in ("domain_checker", "provider_factory"):
            if old_delivery is not None and getattr(old_delivery, hook, None) is not None:
                setattr(app.state.email_delivery, hook, getattr(old_delivery, hook))

    def _close_runtime(app: FastAPI) -> None:
        """Close every service that holds a connection, users before stores.

        `test_every_open_service_is_closed_for_a_restore` fails if a service
        with a `close()` is added to startup and not here: one left open keeps
        writing into the workspace a restore has just moved aside.
        """
        for name in RUNTIME_CLOSE_ORDER:
            service = getattr(app.state, name, None)
            close = getattr(service, "close", None)
            if callable(close):
                close()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.prepare()
        app.state.settings = resolved
        resolved.verify_persistent_mount()
        app.state.recovery_gate = RecoveryGate()
        # A restore that stopped half way is rolled back before anything opens
        # the workspace, under the same lock every request takes (audit A03).
        # Only when there is one: taking it regardless meant a worker mid-cycle,
        # holding its shared lease, stopped the app starting at all (D-129).
        if restore_pending(resolved.data_dir):
            try:
                with WorkspaceLock(
                    resolved.data_dir, exclusive=True, wait_seconds=RECOVERY_WAIT_SECONDS
                ):
                    recover_interrupted_restore(
                        database_path=resolved.database_path, data_dir=resolved.data_dir
                    )
            except WorkspaceBusy as exc:
                raise WorkspaceBusy(
                    "An interrupted restore must be rolled back before off_CRM starts, and "
                    "another process — the email worker? — still holds the workspace. "
                    "Stop it, then start off_CRM again."
                ) from exc
        _open_runtime(app, {})
        if resolved.public_demo:
            public_demo.seed(app.state.engine)
        # Production is one instance per disk: SQLite state is not shared
        # between web instances, and the lock refuses a second one.
        lease = (
            WorkspaceLock(resolved.data_dir, instance=True)
            if resolved.production
            else nullcontext()
        )
        with lease:
            for name in TIMERS:
                if not resolved.public_demo:
                    await getattr(app.state, name).start()
            try:
                yield
            finally:
                for name in TIMERS:
                    await getattr(app.state, name).stop()
                _close_runtime(app)

    app = FastAPI(
        title="off_CRM",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    # Innermost ASGI guard: cap raw video multipart data BEFORE it is parsed.
    # This sits behind the API's authentication middleware; FailureMiddleware
    # remains outermost so unexpected failures are still reported.
    app.add_middleware(VideoUploadBodyGuard, max_file_bytes=resolved.max_upload_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8766",
            "http://localhost:8766",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Offsetx-Token"],
    )

    def _database_unreachable(exc: Exception, request: Request) -> JSONResponse:
        """The hosted database did not answer (S-06.03.02).

        A sentence and 503, not a bare 500. What failed and where goes to the
        server's log only: it names the database host, which is no business of
        every login, and readiness names the store for the owner.
        """
        request.state.failure_exception = exc
        request.state.public_failure_detail = (
            "off_CRM cannot reach its database right now. Try again in a minute; "
            "if it keeps failing, tell the install owner."
        )
        return security_headers(JSONResponse(status_code=503, content={"detail": (
            "off_CRM cannot reach its database right now. Try again in a minute; "
            "if it keeps failing, tell the install owner — the server's log says why."
        )}))

    def _request_caller(request: Request) -> str | None:
        """The caller, for an API request only. The health checks and the
        screens' files need no login, and asking the database whose a cookie is
        made being alive depend on it (D-209)."""
        if not request.url.path.startswith("/api/"):
            return None
        return _caller(request)

    @app.middleware("http")
    async def local_security(request: Request, call_next: Any):
        # DNS rebinding is what makes "it only listens on localhost" untrue: a
        # page can point a name it controls at 127.0.0.1 and reach this API with
        # the browser's cooperation. CORS does not prevent the *request* — it
        # only stops the attacker reading the reply — and a rebound name looks
        # same-origin anyway. An allowlist of names this server answers to does
        # prevent it, and it is one comparison.
        if resolved.allow_unauthenticated:
            # A test harness, not a deployment. The same flag that opts out of
            # authentication opts out of the host allowlist, because both checks
            # are about being reachable from somewhere real and a harness is not.
            # Both are covered by their own tests against a production-shaped
            # config, so nothing here goes unexercised.
            try:
                caller = _request_caller(request)
            except DatabaseError as exc:
                return _database_unreachable(exc, request)
            return await serve_as(caller, request, call_next)
        sent_host = (request.headers.get("host") or "").strip().lower()
        if sent_host.startswith("["):          # [::1]:8766  ->  ::1
            bare_host = sent_host[1:].split("]", 1)[0]
        else:                                  # 127.0.0.1:8766  ->  127.0.0.1
            bare_host = sent_host.split(":", 1)[0]
        # Health checks come from the platform with an internal host; refused,
        # every Render deploy timed out (D-148). They say only ready or not, so
        # a rebinding page learns nothing — and nothing else is exempt.
        platform_probe = request.method == "GET" and request.url.path in (
            "/health/live",
            "/health/ready",
        )
        if sent_host and bare_host not in host_allowlist and not platform_probe:
            return security_headers(
                JSONResponse(
                    status_code=421,
                    content={
                        "detail": (
                            f"This server does not answer to the host {bare_host!r}. "
                            "Set OFFSETX_ALLOWED_HOSTS if that name is legitimate."
                        )
                    },
                )
            )

        if resolved.public_demo and not public_demo.request_allowed(request.method, request.url.path):
            return security_headers(JSONResponse(status_code=403, content={"detail": (
                "The sample CRM is read-only. AI chat and orchestration are available; "
                "CRM changes, external sending and owner actions are disabled."
            )}))
        is_public = is_public_api_path(request.url.path)
        # No configuration clause any more. Whether auth is set up is decided at
        # startup above, so a request never re-decides it — that clause was the
        # fail-open: with nothing configured, every route served 200 to anyone.
        protected = request.url.path.startswith("/api/") and not is_public
        if resolved.allow_unauthenticated:
            protected = False
        # The session check reads the logins, which may be in the hosted
        # database: the route handlers' 503 does not cover the middleware, so a
        # signed-in browser got a bare 500 here during an outage (D-209).
        try:
            caller = _request_caller(request)
        except DatabaseError as exc:
            return _database_unreachable(exc, request)
        if protected and caller is None:
            return security_headers(
                JSONResponse(status_code=401, content={"detail": "CRM login required"})
            )
        return await serve_as(caller, request, call_next)

    async def serve_as(caller: str | None, request: Request, call_next: Any) -> Response:
        # "" rather than None for a request nobody signed: None means "not a
        # request", which the product reader treats as a timer acting for the
        # install. An anonymous request must never be mistaken for that.
        marker = _CALLER_WORKSPACE.set(caller or "")
        request.state.caller_workspace = caller or ""
        try:
            return security_headers(await call_next(request))
        finally:
            _CALLER_WORKSPACE.reset(marker)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic/FastAPI errors are client input failures, not server crashes.
        # Return bounded field/type information and never echo request bodies,
        # which may contain credentials or other sensitive material.
        errors: list[dict[str, Any]] = []
        for item in exc.errors()[:50]:
            location = [
                str(part)
                for part in item.get("loc", ())
                if str(part) not in {"body"}
            ]
            errors.append({
                "location": location,
                "message": str(item.get("msg") or "Invalid value")[:500],
                "type": str(item.get("type") or "validation_error")[:120],
            })
        # Screens show `detail` alone, so it names the first refused field: a
        # bare "Request validation failed" left the owner nothing to change
        # (D-150). Built from the same bounded messages, never from the body.
        detail = "Request validation failed"
        if errors:
            first = errors[0]
            field = " ".join(first["location"]).replace("_", " ").strip()
            detail = f"{field}: {first['message']}." if field else f"{first['message']}."
            if len(errors) > 1:
                detail += f" ({len(errors) - 1} more value(s) were refused too.)"
            detail += " Correct it and try again."
        return JSONResponse(
            status_code=422,
            content={
                "detail": detail,
                "errors": errors,
            },
        )

    @app.exception_handler(KeyError)
    async def not_found(_: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc).strip("'")})

    app.include_router(build_email_delivery_router())
    # A lambda so the workspace rule is looked up when a request arrives:
    # `_workspace_id` is defined further down this function, and whatever it
    # becomes, the GTM routes follow it.
    app.include_router(
        build_gtm_router(
            workspace_of=lambda request: _workspace_id(request),
            campaign_of=lambda request, campaign_id: _engine(request).store.get_campaign(
                campaign_id
            ),
            service_of=lambda request: _gtm(request),
        )
    )

    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, exc: ValueError) -> JSONResponse:
        # The reason is the product's error message — "Unknown campaign kind",
        # "Loss reason is required" — and the owner needs it to fix the input.
        # Replacing every one with a fixed sentence hid them all (D-107). What
        # S-06.02.02 guards against is a *credential* echoed back, so only a
        # message the credential scanner flags is withheld, and every message
        # is bounded.
        message = str(exc)[:500]
        if not message or not scan_payload(
            {"detail": message}, policy=DataPolicy.FULL, allow_addresses=True
        ).clean:
            message = "The supplied value is invalid for this operation."
        return JSONResponse(status_code=422, content={"detail": message})

    @app.exception_handler(DatabaseError)
    async def database_unavailable(request: Request, exc: DatabaseError) -> JSONResponse:
        return _database_unreachable(exc, request)

    @app.exception_handler(StarletteHTTPException)
    async def http_failure(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code >= 500:
            request.state.failure_exception = exc
            # Health's component/status shape is an operator contract. Other
            # HTTPException details may contain arbitrary upstream content.
            request.state.safe_failure_response = request.url.path == "/health/ready"
        reference = reported_reference(exc)
        if reference and exc.status_code < 500:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": f"The operation could not finish. Review the settings and retry; "
                         f"contact the install owner if it persists. Reference: {reference}", "error_id": reference},
                headers={**(exc.headers or {}), "X-Error-ID": reference},
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(NotionError)
    async def notion_failure(_: Request, exc: NotionError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ProviderFailure)
    async def provider_failure_classified(request: Request, exc: ProviderFailure) -> JSONResponse:
        """A failure the broker refused to work around.

        502 rather than 503: the upstream gave a definite answer and off_CRM
        chose not to route around it. The body carries the kind and what the
        owner has to do, because "try again later" is the wrong advice for a
        rejected key.
        """
        request.state.failure_exception = exc
        request.state.safe_failure_response = True
        return JSONResponse(status_code=502, content=exc.to_dict())

    @app.exception_handler(ProviderError)
    async def provider_failure(request: Request, exc: ProviderError) -> JSONResponse:
        request.state.failure_exception = exc
        reason = str(exc)
        if reason.startswith("No provider profile is set up for your workspace"):
            request.state.public_failure_detail = (
                "No provider profile is set up for your workspace. Generate with local templates instead."
            )
        elif 'Provider profiles to confirm' in reason:
            request.state.public_failure_detail = (
                'Open Settings, under "Provider profiles to confirm", and confirm your own profiles. '
                'Until then, generate with local templates.'
            )
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(SalesConflictError)
    async def stale_sales_card(_: Request, exc: SalesConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

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
            "bulk_mail_modes": ["local", "ses"],
            "live_bulk_confirmation": "QUEUE LIVE EMAILS",
            "live_send_confirmation": LIVE_SEND_CONFIRMATION,
        }

    @app.get(f"{API_PREFIX}/auth/session")
    def auth_session(request: Request) -> dict[str, Any]:
        identity = session_identity(request)
        token_authenticated = valid_api_token(request)
        return {
            "configured": workspace_auth.enabled,
            "authenticated": bool(identity) or token_authenticated or resolved.allow_unauthenticated,
            "username": identity.username if identity else "",
            "workspace_id": (
                identity.workspace_id
                if identity
                else ("local" if token_authenticated or resolved.allow_unauthenticated else "")
            ),
            "expires_at": identity.expires_at if identity else None,
            **({"public_demo": {
                "username": resolved.demo_username, "password": resolved.demo_password,
                "read_only": False, "crm_read_only": True,
            }} if resolved.public_demo else {}),
        }

    @app.post(f"{API_PREFIX}/auth/login")
    def auth_login(body: DemoLogin, request: Request) -> Response:
        if not workspace_auth.enabled:
            raise HTTPException(status_code=404, detail="Workspace login is not configured")
        client_key = request.client.host if request.client else "unknown"
        if not login_limiter.allowed(client_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again in five minutes."},
                headers={"Retry-After": "300"},
            )
        identity = workspace_auth.authenticate(body.username, body.password)
        if identity is None:
            login_limiter.failed(client_key)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        login_limiter.clear(client_key)
        token = workspace_auth.issue(identity)
        login_workspace = public_demo.workspace_for(token) if resolved.public_demo else identity.workspace_id
        response = JSONResponse(
            content={
                "authenticated": True,
                "username": identity.username,
                "workspace_id": login_workspace,
            }
        )
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=workspace_auth.session_seconds,
            httponly=True,
            secure=not loopback,
            samesite="strict",
            path="/",
        )
        return response

    @app.post(f"{API_PREFIX}/auth/logout")
    def auth_logout(request: Request) -> Response:
        # Deleting a cookie alone cannot revoke a stolen copy (audit A06).
        # Persist its digest before returning success; a storage outage must not
        # claim logout succeeded while a bearer token remains valid.
        identity = session_identity(request)
        workspace_auth.revoke(request.cookies.get(SESSION_COOKIE, ""))
        if resolved.public_demo and identity is not None:
            workspaces = request.app.state.ai_workspaces
            for provider_id in tuple(workspaces.raw(identity.workspace_id).get("providers") or {}):
                workspaces.disconnect_provider(identity.workspace_id, provider_id)
        response = JSONResponse(content={"authenticated": False})
        response.delete_cookie(
            SESSION_COOKIE,
            httponly=True,
            secure=not loopback,
            samesite="strict",
            path="/",
        )
        return response


    def require_workspace_admin(request: Request) -> None:
        if not valid_api_token(request):
            raise HTTPException(
                status_code=403,
                detail="Workspace administration requires the install API token",
            )

    @app.get(f"{API_PREFIX}/workspaces")
    def list_workspaces(request: Request) -> dict[str, Any]:
        require_workspace_admin(request)
        return {"items": workspace_auth.list_accounts()}

    @app.post(f"{API_PREFIX}/workspaces", status_code=201)
    def create_workspace(body: WorkspaceCreate, request: Request) -> dict[str, Any]:
        require_workspace_admin(request)
        # Workspace 'local' has install-owner privileges, beyond a normal
        # workspace login. It must never be granted by a mistaken name alone.
        if body.workspace_id == "local" and not body.confirm_install_owner:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A login in workspace 'local' acts as the install owner and "
                    "can administer all workspaces. Set confirm_install_owner=true "
                    "only when deliberately creating another install owner."
                ),
            )
        if body.workspace_id != "local" and body.confirm_install_owner:
            raise HTTPException(
                status_code=400,
                detail="Install owner confirmation is only valid for workspace 'local'",
            )
        try:
            identity = workspace_auth.create(
                username=body.username,
                workspace_id=body.workspace_id,
                password=body.password,
            )
        except WorkspaceAuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "username": identity.username,
            "workspace_id": identity.workspace_id,
            "enabled": True,
            "install_owner": identity.workspace_id == "local",
        }

    @app.patch(f"{API_PREFIX}/workspaces/{{username}}")
    def update_workspace(
        username: str, body: WorkspaceUpdate, request: Request
    ) -> dict[str, Any]:
        require_workspace_admin(request)
        if body.password is None and body.enabled is None:
            raise HTTPException(status_code=400, detail="No workspace change supplied")
        try:
            if body.password is not None:
                workspace_auth.set_password(username, body.password)
            if body.enabled is not None:
                workspace_auth.set_enabled(username, body.enabled)
        except WorkspaceAuthError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return next(
            item for item in workspace_auth.list_accounts()
            if item["username"] == username
        )

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
        # Read from the CRM the app opened, never assumed: this said
        # "local_sqlite" and the file's path on a server whose CRM was in
        # PostgreSQL, and the screens said "SQLite on this device" (D-226).
        crm_store = _engine(request).store
        # Where the database is — host, user, name — is the install owner's to
        # see, not every workspace login's, a client's included (finding 6).
        owner = _profile_scope(request) == ""
        kind = "PostgreSQL" if crm_store.backend == "postgres" else "SQLite file"
        return {
            "storage": "hosted_postgres" if crm_store.backend == "postgres" else "local_sqlite",
            # Where the CRM is, safe to show: a password is never in it.
            "database": describe_database_target(crm_store.target) if owner else kind,
            # The CRM's own file; empty when it has none, or for another login.
            "database_path": str(crm_store.path) if crm_store.path and owner else "",
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
            "provider_profiles": len(
                request.app.state.provider_profiles.list(owner=_profile_scope(request))
            ),
            "memory": _engine(request).store.memory_stats(),
            "automation": request.app.state.automation.status(),
        }

    def _profile_scope(request: Request) -> str:
        """"" for the install owner, who manages every profile; otherwise the
        caller's own workspace. Profiles were install-wide, so any login could
        re-point the owner's at its own server and receive the key (D-155)."""
        caller = _workspace_id(request)
        return "" if caller == "local" else caller

    def _confirm_options(label: str) -> list[str]:
        """Where confirming a profile saved before ownership was may put it,
        the suggestion first.

        The install owner ("local") always: confirming takes the profile's
        key, which proves it (D-185). And the client workspace its label
        names, if any — offered first, as the label says whom it was saved
        for. "default" (the old form's label), "local" and "" name the owner
        whatever a workspace is called: a client workspace given the id
        "default" received the owner's profile and key (D-190).
        """
        if label not in {"", "default", "local"}:
            clients = {str(account["workspace_id"]) for account in workspace_auth.list_accounts()}
            if label in clients:
                return [label, "local"]
        return ["local"]

    def _own_profile(request: Request, profile_id: str) -> tuple[str, bool]:
        scope = _profile_scope(request)
        found = request.app.state.provider_profiles.ownership(profile_id)
        # Another workspace's profile is "not found": existence is not leaked.
        # So is one saved before ownership was recorded — only the install
        # owner may claim it, since its label could name anyone (D-166).
        if found is None or (scope and found != (scope, True)):
            raise HTTPException(404, "Provider profile not found")
        return found

    @app.get(f"{API_PREFIX}/provider-profiles")
    def provider_profiles(
        request: Request,
        owner: str = Query("", max_length=100),
        mine: bool = Query(False),
    ) -> dict[str, Any]:
        store = request.app.state.provider_profiles
        scope = _profile_scope(request)
        if mine or scope:
            # What the caller's own drafts may use (D-165).
            items = store.list(owner=_workspace_id(request))
        else:
            # The install owner sees every profile and whose it is, strays
            # included, so one can be found, confirmed or removed — and, for
            # a stray, where Confirm will put it before it is pressed (D-190).
            items = store.list(owner=owner, include_unconfirmed=True)
            for item in items:
                if not item["owner_confirmed"]:
                    options = _confirm_options(str(item.get("owner", "")))
                    item["confirm_options"] = options
                    item["confirm_to"] = options[0]
        # Profiles saved before ownership was recorded wait for the install
        # owner, and the screens must be able to say so (D-177).
        waiting = 0 if scope else store.unconfirmed_count()
        return {"items": items, "total": len(items), "waiting": waiting}

    @app.post(f"{API_PREFIX}/provider-profiles", status_code=201)
    def save_provider_profile(
        body: ProviderProfileUpsert, request: Request
    ) -> dict[str, Any]:
        payload = body.model_dump(exclude={"api_key", "api_key_env", "owner"})
        store = request.app.state.provider_profiles
        # Whose a profile is, is the server's call: the caller's own
        # workspace, "local" for the install owner (D-165, D-166). Checked in
        # the store's own write, not before it (D-182).
        scope = _profile_scope(request)
        try:
            if scope:
                # A client edits only its own; a new one gets a fresh id.
                return store.upsert(
                    payload, owner=scope, api_key=body.api_key, must_own=bool(payload.get("id"))
                )
            # The owner editing a client's profile leaves it the client's.
            return store.upsert(
                payload, owner=_workspace_id(request), api_key=body.api_key, keep_owner=True
            )
        except KeyError as exc:
            raise HTTPException(404, "Provider profile not found") from exc
        except ProfileUnconfirmed as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post(f"{API_PREFIX}/provider-profiles/{{profile_id}}/confirm")
    def confirm_provider_profile(
        profile_id: str, request: Request, body: ProviderProfileConfirm | None = None
    ) -> dict[str, Any]:
        """The install owner settles a profile saved before ownership was
        recorded, by typing the key it holds. Until then it is in no
        workspace's chain (D-166, D-185).

        It goes where the pressed button names, if `_confirm_options` offers
        that: the page may be older than a workspace made since (D-194).
        Never the caller's own workspace by virtue of calling: a cookie could
        name the caller (D-181).
        """
        require_install_owner(request)
        try:
            return request.app.state.provider_profiles.confirm(
                profile_id,
                caller="local",
                options_for=_confirm_options,
                api_key=body.api_key if body else "",
                expect=body.confirm_to if body else "",
            )
        except KeyError as exc:
            raise HTTPException(404, "Provider profile not found") from exc
        except ProfileOwnedElsewhere as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post(f"{API_PREFIX}/provider-profiles/{{profile_id}}/test")
    def test_provider_profile(
        profile_id: str,
        body: ProviderHealthRequest,
        request: Request,
    ) -> dict[str, Any]:
        _own_profile(request, profile_id)
        result = request.app.state.provider_profiles.health(
            profile_id, probe=body.live_probe
        )
        if result["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @app.post(f"{API_PREFIX}/provider-profiles/{{profile_id}}/delete")
    def delete_provider_profile(profile_id: str, request: Request) -> dict[str, bool]:
        _own_profile(request, profile_id)
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
            limit=limit,
            offset=offset,
            profile_id=profile_id,
            status=status,
            # A client reads its own calls; the install owner every
            # workspace's. Any login read them all, prompts included (D-168).
            workspace_id=_profile_scope(request),
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/companions")
    def list_companions(request: Request) -> dict[str, Any]:
        workspace_id = _workspace_id(request)
        return {
            "items": [
                item.to_dict()
                for item in request.app.state.companions.list(
                    workspace_id=workspace_id
                )
            ]
        }

    @app.post(f"{API_PREFIX}/companions", status_code=201)
    def create_companion(body: CompanionCreateBody, request: Request) -> dict[str, Any]:
        try:
            profile = request.app.state.companions.create(
                workspace_id=_workspace_id(request),
                name=str(body.get("name") or ""),
                instructions=str(body.get("instructions") or ""),
                granted_tool_ids=body.get("granted_tool_ids") or (),
                memory_scope=str(body.get("memory_scope") or ""),
            )
        except CompanionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return profile.to_dict()

    @app.get(f"{API_PREFIX}/companions/{{companion_id}}")
    def get_companion(companion_id: str, request: Request) -> dict[str, Any]:
        profile = request.app.state.companions.get(
            companion_id, workspace_id=_workspace_id(request)
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Companion not found")
        return profile.to_dict()

    @app.patch(f"{API_PREFIX}/companions/{{companion_id}}")
    def update_companion(
        companion_id: str, body: CompanionUpdateBody, request: Request
    ) -> dict[str, Any]:
        try:
            profile = request.app.state.companions.update(
                companion_id,
                workspace_id=_workspace_id(request),
                name=body["name"] if "name" in body else None,
                instructions=body["instructions"] if "instructions" in body else None,
                granted_tool_ids=(
                    body["granted_tool_ids"]
                    if "granted_tool_ids" in body
                    else None
                ),
                memory_scope=(
                    body["memory_scope"] if "memory_scope" in body else None
                ),
                enabled=body["enabled"] if "enabled" in body else None,
            )
        except CompanionError as exc:
            status = 404 if "does not exist" in str(exc) else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return profile.to_dict()

    @app.delete(f"{API_PREFIX}/companions/{{companion_id}}")
    def delete_companion(companion_id: str, request: Request) -> dict[str, str]:
        deleted = request.app.state.companions.delete(
            companion_id, workspace_id=_workspace_id(request)
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Companion not found")
        return {"status": "deleted"}

    @app.post(f"{API_PREFIX}/companions/{{companion_id}}/context")
    def companion_context(
        companion_id: str, body: CompanionContextBody, request: Request
    ) -> dict[str, Any]:
        limit = body.get("memory_limit", 8)
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise HTTPException(
                status_code=400, detail="memory_limit must be an integer"
            )
        try:
            return request.app.state.companions.start(
                companion_id,
                workspace_id=_workspace_id(request),
                memory_query=str(body.get("memory_query") or ""),
                memory_limit=limit,
            ).to_dict()
        except CompanionError as exc:
            status = 404 if "does not exist" in str(exc) else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/companions/{{companion_id}}/memory", status_code=201)
    def companion_memory(
        companion_id: str, body: CompanionMemoryBody, request: Request
    ) -> dict[str, str]:
        approved = body.get("approved", False)
        if not isinstance(approved, bool):
            raise HTTPException(status_code=400, detail="approved must be true or false")
        tags = body.get("tags") or []
        if not isinstance(tags, list):
            raise HTTPException(status_code=400, detail="tags must be a list")
        try:
            memory_id = request.app.state.companions.remember(
                companion_id,
                workspace_id=_workspace_id(request),
                content=str(body.get("content") or ""),
                kind=str(body.get("kind") or "companion_fact"),
                tags=[str(item) for item in tags],
                approved=approved,
            )
        except CompanionError as exc:
            status = 404 if "does not exist" in str(exc) else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": memory_id}

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

    @app.get(f"{API_PREFIX}/agent-permissions")
    def get_agent_permissions(
        request: Request, workspace_id: str = Query("", max_length=64)
    ) -> dict[str, Any]:
        caller = _workspace_id(request)
        target = workspace_id or caller
        if target != caller and not valid_api_token(request):
            raise HTTPException(403, "Cannot inspect another workspace's rules")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", target):
            raise HTTPException(400, "Invalid workspace")
        try:
            return AgentPermissionPolicy.from_mapping(
                request.app.state.ai_workspaces.raw_permissions(target).get("agent_permissions", {})
            ).to_dict()
        except (PermissionErrorRule, ValueError, OSError) as exc:
            raise HTTPException(503, "Stored agent permissions unavailable; stop routines and check storage") from exc

    @app.put(f"{API_PREFIX}/agent-permissions")
    def set_agent_permissions(
        body: AgentPermissionUpdate, request: Request,
        workspace_id: str = Query("", max_length=64),
    ) -> dict[str, Any]:
        require_workspace_admin(request)
        target = workspace_id or "local"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", target):
            raise HTTPException(400, "Invalid workspace")
        if target != "local" and target not in {
            item["workspace_id"] for item in workspace_auth.list_accounts()
        }:
            raise HTTPException(404, "Workspace not found")
        try:
            policy = AgentPermissionPolicy.from_mapping(body.model_dump())
        except PermissionErrorRule as exc:
            raise HTTPException(400, str(exc)) from exc
        try:
            # Do not overwrite a damaged settings document with a blank one.
            request.app.state.ai_workspaces.raw_permissions(target)
            request.app.state.ai_workspaces.save(
                target, {"agent_permissions": policy.to_dict()}, strict=True
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(503, "Workspace settings unavailable; check storage before editing") from exc
        return policy.to_dict()

    @app.get(f"{API_PREFIX}/agent-routines")
    def list_agent_routines(request: Request) -> dict[str, Any]:
        items = request.app.state.agent_routine_store.list(
            workspace_id=_workspace_id(request)
        )
        return {"items": [item.to_dict() for item in items]}

    @app.post(f"{API_PREFIX}/agent-routines", status_code=201)
    def create_agent_routine(
        body: AgentRoutineCreate, request: Request
    ) -> dict[str, Any]:
        try:
            routine = request.app.state.agent_routine_store.create(
                workspace_id=_workspace_id(request),
                name=body.name,
                goal=body.goal,
                target_url=body.target_url,
                trigger_type=body.trigger_type,
                interval_seconds=body.interval_seconds,
                event_name=body.event_name,
                step_budget=body.step_budget,
                enabled=body.enabled,
            )
        except RoutineError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return routine.to_dict()

    @app.patch(f"{API_PREFIX}/agent-routines/{{routine_id}}")
    def update_agent_routine(
        routine_id: str, body: AgentRoutineUpdate, request: Request
    ) -> dict[str, Any]:
        try:
            return request.app.state.agent_routine_store.set_enabled(
                routine_id,
                body.enabled,
                workspace_id=_workspace_id(request),
            ).to_dict()
        except RoutineError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete(f"{API_PREFIX}/agent-routines/{{routine_id}}")
    def delete_agent_routine(routine_id: str, request: Request) -> dict[str, bool]:
        deleted = request.app.state.agent_routine_store.delete(
            routine_id, workspace_id=_workspace_id(request)
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Routine not found")
        return {"deleted": True}

    @app.post(f"{API_PREFIX}/agent-routines/events/{{event_name}}")
    async def emit_agent_routine_event(
        event_name: str, body: AgentRoutineEvent, request: Request
    ) -> dict[str, Any]:
        try:
            results = await request.app.state.agent_routines.emit(
                event_name,
                workspace_id=_workspace_id(request),
                payload=body.payload,
                event_id=body.event_id,
            )
        except RoutineError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"results": results, "total": len(results)}

    @app.get(f"{API_PREFIX}/agent-routine-runs")
    def agent_routine_runs(
        request: Request,
        routine_id: str = Query("", max_length=64),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = request.app.state.agent_routine_store.runs(
            workspace_id=_workspace_id(request),
            routine_id=routine_id,
            limit=limit,
        )
        return {"items": items, "total": len(items), "scheduler_error": (
            request.app.state.agent_routines.last_error if _workspace_id(request) == "local" else ""
        )}

    @app.get(f"{API_PREFIX}/operations/health")
    def operations_health(request: Request) -> dict[str, Any]:
        """Owner-only operational signal, separate from router/liveness probes."""
        require_install_owner(request)
        return describe_operational_health(request.app.state)

    @app.get(f"{API_PREFIX}/agent-routine-status")
    def agent_routine_status(request: Request) -> dict[str, Any]:
        # Run history may be the store that failed. Its scheduler's diagnosis
        # must remain readable without querying that same store again.
        require_install_owner(request)
        service = request.app.state.agent_routines
        return {"running": bool(service._task and not service._task.done()), "last_error": service.last_error}

    @app.get(f"{API_PREFIX}/agent-routine-notifications")
    def agent_routine_notifications(
        request: Request,
        unread_only: bool = Query(False),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        items = request.app.state.agent_routine_store.notifications(
            workspace_id=_workspace_id(request),
            unread_only=unread_only,
            limit=limit,
        )
        return {"items": items, "total": len(items)}

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
        return {"results": results, "total": len(results), "last_error": request.app.state.automation.last_error}

    @app.get(f"{API_PREFIX}/content-automation")
    def content_automation_status(request: Request) -> dict[str, Any]:
        """What the content engine is set to do unattended, and what it last did."""
        return request.app.state.content_automation.status()

    @app.patch(f"{API_PREFIX}/content-automation")
    def update_content_automation(body: ContentAutomationBody, request: Request) -> dict[str, Any]:
        """Declare which campaign pairs run, and how often.

        Deliberately not a typed model: ``pipelines`` is a list of pairs the
        owner writes down, and the service normalises it and drops half-declared
        entries itself. One place decides what a legal pipeline is, rather than
        that rule living in a schema and again in the service.
        """
        # The timer runs on the owner's keys and egress policy, as `local`, for
        # every campaign it is given (D-125).
        require_install_owner(request)
        return request.app.state.content_automation.update(
            body.model_dump(exclude_unset=True)
        )

    @app.post(f"{API_PREFIX}/content-automation/run")
    def run_content_automation(request: Request) -> dict[str, Any]:
        """Run one cycle now, whether or not the timer is enabled.

        The same code the timer runs — there is no separate manual path, so a
        cycle that works here works unattended. So it runs as the timer does,
        for the install, which is why only the owner may start it (D-125).
        """
        require_install_owner(request)
        with _install_content_scope():
            results = request.app.state.content_automation.run_once()
        return {"results": results, "total": len(results)}

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
        broker = state.ai_broker.with_credential_resolver(
            state.ai_workspaces.credential_resolver(workspace_id)
        )
        return ImageCampaignEngine(
            store=state.image_store,
            broker=broker,
            settings_resolver=state.ai_workspaces.egress_settings,
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            workspace_id=workspace_id,
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/image-briefs", status_code=201)
    def add_image_brief(campaign_id: str, body: ImageBriefCreateBody, request: Request) -> dict[str, Any]:
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
    def generate_images(brief_id: str, body: ImageGenerateBody, request: Request) -> dict[str, Any]:
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
    def decide_image(asset_id: str, body: ImageDecisionBody, request: Request) -> dict[str, Any]:
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
        """The timeline runner, with the one model call captions need.

        Editing itself calls nothing — it is arithmetic on a document. The
        transcriber is a closure over the broker rather than an import, so the
        editor owns no transport and no provider knowledge, the same rule the
        image runner follows.

        **The data class is `campaign`, and that is a decision.** A voiceover
        recorded for a marketing video is the owner's own material, not public,
        so the tier rules narrow for it. It is deliberately not `internal` or
        `mailbox`: the broker refuses those as audio outright, because the
        pre-flight scan that protects every other path cannot read a waveform.
        """
        state = request.app.state
        workspace_id = _workspace_id(request)
        broker = state.ai_broker.with_credential_resolver(
            state.ai_workspaces.credential_resolver(workspace_id)
        )
        settings = state.ai_workspaces.egress_settings(workspace_id)

        def transcriber(**kwargs: Any) -> Any:
            return broker.call_transcript(
                EgressRequest(
                    task_type="video_transcription",
                    data_class=DataClass.CAMPAIGN,
                    instructions="",
                ),
                settings,
                **kwargs,
            )

        def video_director(**kwargs: Any) -> Any:
            """Classify campaign product/style before any provider receives it.

            A public trend topic is not owner material. Only the product and
            typed house style increase the data class and enter campaign fields.
            The system prompt is always the code-authored recipe contract.
            """
            campaign_id = str(kwargs.get("campaign_id") or "").strip()
            product = (
                state.gtm_store.product_for_campaign(campaign_id, workspace_id)
                if campaign_id else None
            )
            style = str(kwargs.get("owner_style") or "").strip()
            lines = product_lines(product, style) if product else (
                [f"Owner notes: {style}"] if style else []
            )
            owner_material = bool(product or style)
            return broker.call(
                EgressRequest(
                    task_type="video_direction",
                    data_class=DataClass.CAMPAIGN if owner_material else DataClass.PUBLIC,
                    # Instructions have no owner text; topic is public research.
                    public_text=str(kwargs.get("topic") or ""),
                    positioning_line=str(product.get("one_liner") or "") if product else "",
                    campaign_notes="\n".join(lines),
                ),
                settings,
                system_prompt=video_direction_prompt(),
                expect_json=True,
            )

        return VideoEditorEngine(
            store=state.video_store,
            campaign_reader=lambda cid: _engine(request).store.get_campaign(cid),
            asset_reader=state.image_store.get_asset,
            # Approved only. An assembly drawing on pictures nobody reviewed
            # would put unseen output on a timeline, which is the one thing the
            # swipe queue exists to stop.
            campaign_asset_reader=lambda cid: state.image_store.list_assets(
                cid, status="approved", limit=200
            ),
            transcriber=transcriber,
            director=video_director,
            workspace_id=workspace_id,
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
            "blend_modes": list(BLEND_MODES),
            # The whole preset space in one response. It is data, so the picker
            # in the UI and anything that later *searches* the space read the
            # same list rather than each keeping their own copy.
            **video_preset_catalogue(),
        }

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects", status_code=201)
    def create_video_project(campaign_id: str, body: VideoProjectCreateBody, request: Request) -> dict[str, Any]:
        return _video(request).create_project(
            campaign_id,
            name=str(body.get("name") or "Untitled"),
            preset=str(body.get("preset") or "vertical"),
            fps=str(body.get("fps") or "30"),
            width=int(body.get("width") or 0),
            height=int(body.get("height") or 0),
        ).to_dict()

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects/assemble", status_code=201)
    def assemble_video_project(
        campaign_id: str, body: VideoAssembleBody, request: Request
    ) -> dict[str, Any]:
        """A recipe and a length in, a finished timeline out.

        The one endpoint the "CapCut, but it does it automatically" line in the
        brief actually names. Nothing here builds a document: it picks a
        declared recipe, hands the campaign's own material to the assembler, and
        stores what comes back — so an assembled project is valid for the same
        reason a hand-made one is.

        ``notes`` is the half worth reading. A brief the material could not meet
        exactly is not a failure, and it must not be silent either.
        """
        state, report = _video(request).assemble(
            campaign_id,
            recipe=str(body.get("recipe") or ""),
            target_ticks=int(body.get("target_ticks") or 0),
            name=str(body.get("name") or ""),
            lines=list(body.get("lines") or []),
            asset_ids=list(body["asset_ids"]) if body.get("asset_ids") is not None else None,
            media_ids=list(body["media_ids"]) if body.get("media_ids") is not None else None,
            music_id=str(body.get("music_id") or ""),
            voice_id=str(body.get("voice_id") or ""),
            preset=str(body.get("preset") or "vertical"),
            fps=str(body.get("fps") or "30"),
            seed=int(body.get("seed") or 0),
        )
        return {**state.to_dict(), "beats": report.beats, "notes": report.notes}

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects/direct", status_code=201)
    def direct_video_project(
        campaign_id: str, body: VideoDirectBody, request: Request
    ) -> dict[str, Any]:
        """A topic in, a finished project out. The whole loop in one call.

        The model chooses the shape and writes the words; the assembler does
        everything else. Its reply is checked against the recipe registry before
        a single clip is laid, which is what makes a topic scraped off somebody
        else's website safe to pass in — the worst a hostile one achieves is a
        video in a different one of the declared shapes.
        """
        try:
            state, report, direction = _video(request).direct_and_assemble(
                campaign_id,
                topic=str(body.get("topic") or ""),
                style=str(body.get("style") or ""),
                target_ticks=int(body.get("target_ticks") or 0),
                name=str(body.get("name") or ""),
                asset_ids=list(body["asset_ids"]) if body.get("asset_ids") is not None else None,
                media_ids=list(body["media_ids"]) if body.get("media_ids") is not None else None,
                music_id=str(body.get("music_id") or ""),
                voice_id=str(body.get("voice_id") or ""),
                preset=str(body.get("preset") or "vertical"),
                fps=str(body.get("fps") or "30"),
                seed=int(body.get("seed") or 0),
            )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            # The first thing anyone hits is "no provider connected", and it
            # already carries the sentence that says what to do. Letting it out
            # as a 500 would replace that with a stack trace.
            raise _ai_error(exc) from exc
        return {
            **state.to_dict(),
            "beats": report.beats,
            "notes": report.notes,
            "direction": direction.to_dict(),
        }

    @app.post(
        f"{API_PREFIX}/campaigns/{{campaign_id}}/video-projects/competitor-teardown",
        status_code=201,
    )
    def competitor_teardown_video_project(
        campaign_id: str, body: CompetitorTeardownBody, request: Request
    ) -> dict[str, Any]:
        """Public structural facts -> declared recipe -> our material -> review queue."""
        try:
            teardown = analyse_public_post(dict(body.get("facts") or {}))
        except CompetitorTeardownError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state, report = _video(request).assemble_from_competitor_teardown(
            campaign_id,
            teardown,
            name=str(body.get("name") or ""),
            asset_ids=list(body["asset_ids"]) if body.get("asset_ids") is not None else None,
            media_ids=list(body["media_ids"]) if body.get("media_ids") is not None else None,
            music_id=str(body.get("music_id") or ""),
            voice_id=str(body.get("voice_id") or ""),
            preset=str(body.get("preset") or "vertical"),
            fps=str(body.get("fps") or "30"),
            seed=int(body.get("seed") or 0),
        )
        return {
            **state.to_dict(),
            "beats": report.beats,
            "notes": report.notes,
            "teardown": teardown.to_dict(),
        }

    @app.get(f"{API_PREFIX}/video/effects")
    def video_effects() -> dict[str, Any]:
        """Every pixel operation and every declared look.

        Two lists, because they are two different things to pick from: a
        primitive is an operation with parameters, and a look is an ordered
        stack of them that somebody named. A clip's effect stack may reference
        either, which is what lets an orchestrator compose something the
        catalogue does not contain yet without being able to invent an operation
        the renderer cannot run.
        """
        return video_effects_catalogue()

    @app.get(f"{API_PREFIX}/video/recipes")
    def video_recipes() -> dict[str, Any]:
        """Every assembly shape that exists, as data.

        The same arrangement as the preset catalogue: the picker in the UI and
        anything that later *searches* the space read one list, so a recipe
        added here is immediately choosable and immediately scoreable.
        """
        return video_recipe_catalogue()

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
    def edit_video_project(project_id: str, body: VideoEditBody, request: Request) -> dict[str, Any]:
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
    def place_video_asset(project_id: str, body: VideoPlaceAssetBody, request: Request) -> dict[str, Any]:
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
        payload = await _read_video_upload(file, max_bytes=_settings(request).max_upload_bytes)
        return _video(request).store_render(project_id, payload, renderer=renderer)

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/renders")
    def list_video_renders(project_id: str, request: Request) -> dict[str, Any]:
        return {"items": _video(request).renders(project_id)}

    # ── push, ignore, edit ──────────────────────────────────────────────────

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-queue")
    def video_review_queue(campaign_id: str, request: Request) -> dict[str, Any]:
        """Finished pieces waiting for a verdict, oldest first.

        Every row carries whether it can be pushed and, when it cannot, the one
        sentence saying why — so the page never renders a dead button with no
        explanation next to it.
        """
        return {"items": _video(request).review_queue(campaign_id)}

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/queue", status_code=201)
    def queue_video_for_review(
        project_id: str, body: VideoQueueBody, request: Request
    ) -> dict[str, Any]:
        """Send a hand-built project to the queue.

        Assembled and directed projects arrive there by themselves; this is for
        one somebody cut by hand and has decided is finished.
        """
        review = _video(request).queue_for_review(
            project_id, origin=str(body.get("origin") or "manual")
        )
        return {key: value for key, value in review.items() if key != "baseline"}

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/decide")
    def decide_video(project_id: str, body: VideoDecisionBody, request: Request) -> dict[str, Any]:
        """Push or ignore.

        One endpoint for both because they are one decision with two outcomes,
        and because each of them measures the same thing: how much of what the
        machine produced was still there when the owner answered.

        *Edit* is not here, and that is on purpose. Editing is the operations
        this API already has; it changes the project, not the verdict. The owner
        still has to come back and say push or ignore, and the diff between the
        two is what makes the edit worth anything.
        """
        engine = _video(request)
        decision = str(body.get("decision", "")).strip().lower()
        note = str(body.get("note", ""))
        if decision == "push":
            review = engine.push(project_id, note=note)
        elif decision == "ignore":
            review = engine.ignore(project_id, note=note)
        else:
            raise HTTPException(
                400,
                detail={
                    "error": "unknown_decision",
                    "message": "decision must be push or ignore.",
                },
            )
        return {key: value for key, value in review.items() if key != "baseline"}

    @app.get(f"{API_PREFIX}/video-projects/{{project_id}}/reviews")
    def video_project_reviews(project_id: str, request: Request) -> dict[str, Any]:
        return {"items": _video(request).reviews(project_id)}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-approved")
    def approved_videos(campaign_id: str, request: Request) -> dict[str, Any]:
        """Files the owner pushed — what a distribution post can point at.

        The same question ``/image-assets?status=approved`` answers for
        pictures, and the answer has the same shape, which is why the publisher
        needed nothing new to carry a video.
        """
        return {"items": _video(request).pushed(campaign_id)}

    # ── imported material and captions ──────────────────────────────────────

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-media", status_code=201)
    async def import_video_media(
        campaign_id: str,
        request: Request,
        file: UploadFile = File(...),
        name: str = Form(""),
    ) -> dict[str, Any]:
        """A voiceover or a clip, on its way in.

        Nothing in off_CRM generates speech, so captions need audio from
        somewhere and this is it. The header is read before anything is stored:
        a file that does not declare its own length is refused, because a clip
        whose source duration is a guess cannot be stopped from reading past its
        own end.
        """
        payload = await _read_video_upload(file, max_bytes=_settings(request).max_upload_bytes)
        return _video(request).import_media(
            campaign_id, payload, name=name or (file.filename or "")
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/video-media")
    def list_video_media(campaign_id: str, request: Request) -> dict[str, Any]:
        return {"items": _video(request).media(campaign_id)}

    @app.get(f"{API_PREFIX}/video-media/{{media_id}}/file")
    def video_media_file(media_id: str, request: Request):
        media = request.app.state.video_store.get_media(media_id)
        path = Path(str(media.get("path") or ""))
        if not path.exists():
            raise HTTPException(
                404, detail={"error": "gone", "message": "That media is no longer on disk."}
            )
        return FileResponse(path, media_type=str(media.get("media_type") or "video/webm"))

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/place-media")
    def place_video_media(project_id: str, body: VideoPlaceMediaBody, request: Request) -> dict[str, Any]:
        return _video(request).place_media(
            project_id,
            media_id=str(body.get("media_id") or ""),
            track_id=str(body.get("track_id") or ""),
            start=int(body.get("start", -1)),
            duration=int(body.get("duration") or 0),
        ).to_dict()

    @app.post(f"{API_PREFIX}/video-media/{{media_id}}/transcribe")
    def transcribe_video_media(
        media_id: str, body: VideoTranscribeBody, request: Request
    ) -> dict[str, Any]:
        """Words and timings for one file, reusing what is already stored."""
        try:
            return _video(request).transcribe(
                media_id,
                language=str(body.get("language") or ""),
                refresh=bool(body.get("refresh")),
            )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc

    @app.post(f"{API_PREFIX}/video-projects/{{project_id}}/captions")
    def add_video_captions(
        project_id: str, body: VideoCaptionsBody, request: Request
    ) -> dict[str, Any]:
        """Caption one clip.

        The captions come back as ordinary text clips on a captions track, so
        every edit in the editor already works on them. A transcript is a guess
        about what was said and it goes out under the owner's name — the person
        reads it before anything is published, which is the same judgement the
        swipe and the post approval already are.
        """
        try:
            return _video(request).add_captions(
                project_id,
                clip_id=str(body.get("clip_id") or ""),
                language=str(body.get("language") or ""),
                style=body.get("style") or None,
                max_chars=int(body.get("max_chars") or CAPTION_MAX_CHARS),
                refresh=bool(body.get("refresh")),
            )
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            # A refusal by the trust rules is a normal, explainable outcome, and
            # the owner should read it as one rather than as a crashed editor.
            raise _ai_error(exc) from exc

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

    def _publishable_asset(request: Request, asset_id: str) -> dict[str, Any]:
        """Resolve what a post points at — a picture or a finished video.

        The distribution engine wants one callable that turns an id into a row
        with a ``path`` on it, and both stores already produce exactly that. So
        a video needs no second publisher, no media-type branch and no new
        column: it is an asset, and the thing that publishes assets keeps doing
        what it does.

        Pictures are tried first because there are far more of them, and the ids
        are UUIDs from two different tables, so a collision is not a thing that
        happens.
        """
        state = request.app.state
        try:
            return dict(state.image_store.get_asset(asset_id))
        except KeyError:
            pass
        render = dict(state.video_store.get_render(asset_id))
        if str(render.get("status")) != "ready":
            # A file that failed its gates is kept for the report, not for
            # posting. Publishing one would put an export the checks rejected in
            # front of an audience.
            raise KeyError(
                f"That video did not pass its checks and cannot be posted: {asset_id}"
            )
        # ``generator_performance`` groups published posts by the thing that made
        # the file. A render carries no provider or model, and leaving those
        # blank would file every video under one nameless bucket next to the
        # picture generators. Naming the renderer is the honest answer: it is
        # what produced these bytes.
        render["provider_id"] = "video"
        render["model_id"] = str(render.get("renderer") or "browser")
        return render

    def _distribution(request: Request) -> DistributionEngine:
        state = request.app.state
        return DistributionEngine(
            store=state.distribution_store,
            publisher=LocalOutboxPublisher(state.distribution_store.outbox_dir),
            campaign_reader=lambda cid: _posting_campaign(request, cid),
            asset_reader=lambda asset_id: _owned_post_asset(request, asset_id),
            workspace_id=_workspace_id(request),
        )

    def _owned_post_asset(request: Request, asset_id: str) -> dict[str, Any]:
        asset = _publishable_asset(request, asset_id)
        if asset.get("workspace_id") != _workspace_id(request) or not Path(str(asset.get("path") or "")).is_file():
            raise KeyError("Post attachment not found. Review it on Image review or Video editor.")
        return asset

    def _posting_campaign(request: Request, campaign_id: str) -> dict[str, Any]:
        campaign = _engine(request).store.get_campaign(campaign_id)
        if _workspace_id(request) == "local":
            config = request.app.state.content_automation.config()
            pair = next((row for row in config["pipelines"] if row["distribution_campaign_id"] == campaign_id), None)
            if pair is not None and (not config["enabled"] or pair.get("enabled") is False or pair.get("posts_per_day") == 0):
                if campaign["status"] == "active":
                    return {**campaign, "status": "paused"}
        return campaign

    def _pacing_inputs(app_ref: Any, campaign_id: str, *, workspace_id: str = "local") -> dict[str, Any]:
        """What the pacing controller needs, read from the stores it must not know about.

        The controller is arithmetic over four numbers — target, deadline,
        measured views, platform ceiling. Fetching them here keeps
        ``distribution/pacing.py`` free of any storage knowledge, so it stays
        testable with plain dictionaries.
        """
        store = app_ref.state.distribution_store
        goals = store.list_goals(campaign_id)
        # The newest: `set_goal` adds a row rather than replacing one, so the
        # first row is the goal as it was, not as it is (D-84).
        views_goal = next(
            (goal for goal in reversed(goals) if str(goal.get("metric") or "views") == "views"),
            None,
        )
        accounts = [row for row in store.list_accounts(workspace_id=workspace_id) if row["enabled"]]
        config = app_ref.state.content_automation.config()
        pair = next((row for row in config["pipelines"] if row["distribution_campaign_id"] == campaign_id), None) if workspace_id == "local" else None
        if pair is not None:
            selected = set(pair["account_ids"])
            accounts = [row for row in accounts if row["id"] in selected]
        platform_ids = {str(account.get("platform") or "") for account in accounts}
        platforms = [
            platform
            for platform in list_distribution_platforms()
            if platform.get("id") in platform_ids
        ]
        ceiling, source = pacing_ceiling(platforms, accounts=max(1, len(accounts)))
        # The owner's own ceiling for this campaign is the sum of the caps on
        # the accounts it can post to. Summed rather than taken as the smallest,
        # because the rate is a campaign-wide number and three handles capped at
        # two a day really can carry six posts between them. An account with no
        # cap contributes nothing, and if none of them has one the total is zero
        # — which the pacer reads as "no cap set", not as "no posting".
        capped = [int(item.get("daily_cap") or 0) for item in accounts if item.get("enabled")]
        owner_cap = float(sum(capped)) if capped and all(capped) else 0.0
        return {
            "goal_target": int(views_goal.get("target") or 0) if views_goal else 0,
            "goal_deadline": str(views_goal.get("deadline") or "") if views_goal else "",
            "metrics": store.latest_metrics(campaign_id),
            "ceiling": ceiling,
            "ceiling_source": source,
            "owner_cap": owner_cap,
        }

    def _pacing_decision(app_ref: Any, campaign_id: str, *, workspace_id: str = "local") -> Any:
        """What the pacer says for one campaign now — the Posting screen's number.

        One function for the pacing endpoint and the GTM review, so the review
        can never quote a different decision than the screen shows.
        """
        inputs = _pacing_inputs(app_ref, campaign_id, workspace_id=workspace_id)
        config = app_ref.state.content_automation.config()
        pair = next((row for row in config["pipelines"] if row["distribution_campaign_id"] == campaign_id), {}) if workspace_id == "local" else {}
        return pacing_decide(
            goal_target=int(inputs["goal_target"]),
            goal_deadline=str(inputs["goal_deadline"]),
            metrics=inputs["metrics"],
            current_per_day=float(pair.get("posts_per_day", config.get("posts_per_day") or 0.0)),
            ceiling=float(inputs["ceiling"]),
            ceiling_source=str(inputs["ceiling_source"]),
            owner_cap=float(inputs["owner_cap"]),
            candidates_per_topic=int(config.get("candidates") or 3),
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
        broker = state.ai_broker.with_credential_resolver(
            state.ai_workspaces.credential_resolver(workspace_id)
        )
        data_class = DataClass.CAMPAIGN if angle.strip() else DataClass.PUBLIC

        def writer(kind: str, prompt: str) -> str:
            result = broker.call(
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
    def pipeline_plan(campaign_id: str, body: PipelinePlanBody, request: Request) -> dict[str, Any]:
        """Topic to candidates, stopping at the review queue.

        It stops there on purpose: the next step is a person looking at the
        pictures, and no version of this should skip it.
        """
        # Resolved before `_pipeline` chooses its data class from it.  `S-12.01.02`
        angle = resolve_angle(
            request.app.state.gtm_store,
            _workspace_id(request),
            campaign_id,
            str(body.get("angle", "")),
        )
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
    def pipeline_draft(campaign_id: str, body: PipelineDraftBody, request: Request) -> dict[str, Any]:
        """Kept pictures to draft posts, stopping before approval.

        A draft still needs the approval the distribution runner has always
        required before anything can be scheduled.
        """
        # Resolved before `_pipeline` chooses its data class from it.  `S-12.01.02`
        angle = resolve_angle(
            request.app.state.gtm_store,
            _workspace_id(request),
            campaign_id,
            str(body.get("angle", "")),
        )
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
    def watch_channel(body: TrendWatchBody, request: Request) -> dict[str, Any]:
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
    def sweep_trends(body: TrendSweepBody, request: Request) -> dict[str, Any]:
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
    def connect_distribution_account(body: DistributionAccountCreateBody, request: Request) -> dict[str, Any]:
        return _distribution(request).connect_account(
            platform=str(body.get("platform", "")),
            handle=str(body.get("handle", "")),
            label=str(body.get("label", "")),
            daily_cap=int(body.get("daily_cap") or 0),
        )

    @app.patch(f"{API_PREFIX}/distribution/accounts/{{account_id}}")
    def set_distribution_account(
        account_id: str, body: DistributionAccountUpdateBody, request: Request
    ) -> dict[str, Any]:
        """The owner's own limit on one handle, in posts per day.

        Zero means no cap, which is not the same as zero posts: with no cap the
        platform's published limit is still what binds. Nothing here invents a
        default — a cap this endpoint made up would be a number the owner never
        chose being enforced as though they had.
        """
        changes: dict[str, Any] = {}
        if "daily_cap" in body:
            changes["daily_cap"] = int(body.get("daily_cap") or 0)
        if "label" in body:
            changes["label"] = str(body.get("label") or "")
        if "enabled" in body:
            changes["enabled"] = 1 if body.get("enabled") else 0
        return _distribution(request).set_account(account_id, **changes)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/pacing")
    def pacing_suggestion(campaign_id: str, request: Request) -> dict[str, Any]:
        """What the ideal posting rate would be, right now, and why.

        Read-only. It never changes the rate — that is the owner's press of a
        button, and it lives at ``/content-automation/pace``.
        """
        _distribution(request)._require_own_kind(campaign_id, "reading the pacing")
        config = request.app.state.content_automation.config()
        pending = {}
        if _workspace_id(request) == "local":
            pending = config["pending_paces"].get(campaign_id) or {}
            if not pending and config["pending_pace"].get("distribution_campaign_id") == campaign_id:
                pending = config["pending_pace"]
        return {
            "campaign_id": campaign_id,
            "mode": config.get("pace_mode"),
            "pending": pending,
            **_pacing_decision(request.app, campaign_id, workspace_id=_workspace_id(request)).to_dict(),
        }

    @app.post(f"{API_PREFIX}/content-automation/pace")
    def decide_pacing(body: PacingDecisionBody, request: Request) -> dict[str, Any]:
        """Take the machine's suggestion, or turn it down.

        Two words rather than a rate, because this endpoint is not "set the
        rate" — that is a `PATCH` on the automation. This is the owner
        answering something the machine asked, and it should read that way.
        """
        service = request.app.state.content_automation
        require_install_owner(request)
        decision = str(body.get("decision", "")).strip().lower()
        if decision == "accept":
            return service.accept_pace(campaign_id=body.campaign_id, suggestion_id=body.suggestion_id)
        if decision == "dismiss":
            return service.dismiss_pace(campaign_id=body.campaign_id, suggestion_id=body.suggestion_id)
        raise HTTPException(
            400,
            detail={"error": "unknown_decision", "message": "decision must be accept or dismiss."},
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/goals", status_code=201)
    def set_distribution_goal(campaign_id: str, body: DistributionGoalBody, request: Request) -> dict[str, Any]:
        return _distribution(request).set_goal(
            campaign_id,
            metric=str(body.get("metric", "views")),
            target=int(body.get("target") or 0),
            deadline=str(body.get("deadline", "")),
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/posts", status_code=201)
    def plan_distribution_post(campaign_id: str, body: DistributionPostBody, request: Request) -> dict[str, Any]:
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
        posts = engine.store.list_posts(campaign_id, status=status, workspace_id=_workspace_id(request))
        for post in posts:
            if post["asset_id"]:
                try:
                    _, media_type = _post_media(request, post)
                except KeyError:
                    post["media_error"] = "This attachment is unavailable. Review it on Image review or Video editor before approving."
                else:
                    post["media_kind"] = "video" if media_type.startswith("video/") else "image"
                    post["media_url"] = f"/posts/{post['id']}/media"
        return {"items": posts}

    def _post_media(request: Request, post: dict[str, Any]) -> tuple[dict[str, Any], str]:
        asset = _owned_post_asset(request, str(post["asset_id"]))
        media_type = str(asset.get("media_type") or ("video/webm" if asset.get("provider_id") == "video" else "image/png"))
        if not media_type.startswith(("image/", "video/")):
            raise KeyError("Post attachment cannot be previewed")
        return asset, media_type

    @app.get(f"{API_PREFIX}/posts/{{post_id}}/media")
    def distribution_post_media(post_id: str, request: Request):
        post = _distribution(request)._own_post(post_id)
        asset, media_type = _post_media(request, post)
        return FileResponse(Path(asset["path"]), media_type=media_type)

    @app.post(f"{API_PREFIX}/gtm/plans/{{plan_id}}/start-posting")
    def start_plan_posting(plan_id: str, body: StartPostingBody, request: Request) -> dict[str, Any]:
        require_install_owner(request)
        state = request.app.state
        root_id = state.gtm_store.get_plan(plan_id, "local")["root_id"]
        with state.campaign_locks.hold(f"gtm-plan:{root_id}"):
            plan = state.gtm_store.get_plan(plan_id, "local")
            if plan["status"] != "applied":
                raise HTTPException(409, "Apply the current plan before starting its posting pair.")
            pair = next((row for row in state.content_automation.config()["pipelines"] if row.get("plan_id") == plan_id), None)
            if pair is None:
                raise HTTPException(409, "This plan has no declared posting and image pair. Apply a plan with both channels.")
            links = state.gtm_store.line_links(plan["root_id"], "local")
            if any(links.get(kind) != pair[key] for kind, key in (("distribution", "distribution_campaign_id"), ("image", "image_campaign_id"))):
                raise HTTPException(409, "The posting pair no longer matches this plan. Review and apply its current version.")
            if pair.get("posts_per_day", 0) <= 0:
                raise HTTPException(409, "Set a posting rate greater than zero before starting.")
            accounts = {row["id"]: row for row in state.distribution_store.list_accounts(workspace_id="local")}
            for account_id in body.account_ids:
                if account_id not in accounts or not accounts[account_id]["enabled"]:
                    raise HTTPException(404, "Connected posting account not found.")
            original = {}
            for kind, key in (("distribution", "distribution_campaign_id"), ("image", "image_campaign_id")):
                campaign = state.engine.store.get_campaign(pair[key])
                if campaign["kind"] != kind or campaign["status"] == "archived":
                    raise HTTPException(409, "Review or unarchive the plan's campaigns before starting.")
                original[pair[key]] = campaign["status"]
            try:
                for campaign_id in original:
                    state.engine.store.update_campaign(campaign_id, {"status": "active"})
                return state.content_automation.activate_pipeline(pair["distribution_campaign_id"], body.account_ids)
            except Exception:
                for campaign_id, status in original.items():
                    state.engine.store.update_campaign(campaign_id, {"status": status})
                raise

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/skip")
    def skip_distribution_post(post_id: str, request: Request) -> dict[str, Any]:
        return _distribution(request).skip(post_id)

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/schedule-next")
    def schedule_next_plan_post(post_id: str, request: Request) -> dict[str, Any]:
        require_install_owner(request)
        engine = _distribution(request)
        post = engine._own_post(post_id)
        config = request.app.state.content_automation.config()
        pair = next((row for row in config["pipelines"] if row["distribution_campaign_id"] == post["campaign_id"]), None)
        if pair is None:
            raise HTTPException(409, "Apply and start this plan's posting pair before scheduling its posts.")
        return engine.schedule_next(post_id, posts_per_day=float(pair.get("posts_per_day", config["posts_per_day"])))

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/approve")
    def approve_distribution_post(post_id: str, request: Request) -> dict[str, Any]:
        return _distribution(request).approve(post_id)

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/schedule")
    def schedule_distribution_post(post_id: str, body: DistributionScheduleBody, request: Request) -> dict[str, Any]:
        return _distribution(request).schedule(post_id, at=str(body.get("at", "")))

    @app.post(f"{API_PREFIX}/distribution/publish-due")
    def publish_due_posts(request: Request) -> dict[str, Any]:
        return _distribution(request).publish_due().to_dict()

    @app.post(f"{API_PREFIX}/posts/{{post_id}}/metrics")
    def record_post_metrics(post_id: str, body: DistributionMetricsBody, request: Request) -> dict[str, Any]:
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

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/clone", status_code=201)
    def clone_campaign_endpoint(
        campaign_id: str,
        body: CampaignClone,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            with request.app.state.campaign_locks.hold(campaign_id):
                return engine.store.clone_campaign_settings(campaign_id, name=body.name)

        return _idempotent(engine, f"clone_campaign:{campaign_id}", idempotency_key, operation)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/performance")
    def campaign_performance_endpoint(campaign_id: str, request: Request) -> dict[str, Any]:
        store = _engine(request).store
        # A campaign can receive a reply while these aggregate queries run.
        # Use one consistent DB snapshot instead of mixing counts from before
        # and after that reply; no writer or sender is called from this route.
        with store.transaction():
            if store.backend == "postgres":
                store.connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
            return store.campaign_performance(campaign_id)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/summary")
    def campaign_summary(campaign_id: str, request: Request) -> dict[str, Any]:
        return _engine(request).store.campaign_summary(campaign_id)

    @app.get(f"{API_PREFIX}/crm/quality")
    def crm_data_quality(
        request: Request,
        issue: str = Query("all", pattern="^(all|missing_email|missing_company|missing_title|not_in_campaign|sales_overlap)$"),
        search: str = Query("", max_length=100),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMOperations(_engine(request).store, _sales(request)).contact_quality(
            issue=issue, search=search, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/compare")
    def crm_campaign_comparison(
        request: Request,
        search: str = Query("", max_length=100),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMOperations(_engine(request).store, _sales(request)).campaign_comparison(
            search=search, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/followup-performance")
    def crm_followup_performance(
        request: Request,
        campaign_id: str = Query("", max_length=160),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMOperations(_engine(request).store, _sales(request)).followup_performance(
            campaign_id=campaign_id, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/search")
    def crm_unified_search(
        request: Request,
        query: str = Query(min_length=2, max_length=100),
        kind: str = Query("contacts", pattern="^(contacts|leads)$"),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        """Search CRM fields only; never provider message contents."""
        return CRMInsights(_engine(request).store, _sales(request)).search(
            query, kind=kind, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/accounts")
    def crm_accounts(
        request: Request,
        search: str = Query("", max_length=100),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMInsights(_engine(request).store, _sales(request)).accounts(
            search=search, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/account")
    def crm_account_detail(
        request: Request,
        company_key: str = Query(min_length=1, max_length=200),
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMInsights(_engine(request).store, _sales(request)).account(
            company_key, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/crm/attribution")
    def crm_revenue_attribution(
        request: Request,
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CRMInsights(_engine(request).store, _sales(request)).revenue_attribution(
            limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/actions")
    def campaign_action_center(
        campaign_id: str, request: Request,
        action_type: str = Query("all", pattern="^(all|overdue_task|reply_review|sales_attention)$"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return RelationshipOperations(
            _engine(request).store, _sales(request)
        ).action_center(campaign_id, action_type=action_type, limit=limit, offset=offset)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/{{campaign_contact_id}}/overview")
    def relationship_overview(
        campaign_id: str, campaign_contact_id: str, request: Request,
    ) -> dict[str, Any]:
        return RelationshipOperations(
            _engine(request).store, _sales(request)
        ).contact_360(campaign_id, campaign_contact_id)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/{{campaign_contact_id}}/promote", status_code=200)
    def promote_contact_reply(
        campaign_id: str, campaign_contact_id: str, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            with request.app.state.campaign_locks.hold(campaign_id):
                return RelationshipOperations(engine.store, _sales(request)).promote_reply(
                    campaign_id, campaign_contact_id,
                )

        return _idempotent(
            engine, f"sales_promote:{campaign_id}:{campaign_contact_id}",
            idempotency_key, operation,
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/replies/inbox")
    def reply_inbox(
        campaign_id: str, request: Request,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        review_status: str = Query("all", pattern="^(all|unreviewed|triaged)$"),
        outcome: str = Query("", pattern="^(|positive|neutral|negative|meeting|not_interested|wrong_person)$"),
    ) -> dict[str, Any]:
        return CampaignRelationships(_engine(request).store).inbox(
            campaign_id, limit=limit, offset=offset,
            review_status=review_status, outcome=outcome,
        )

    @app.patch(f"{API_PREFIX}/campaigns/{{campaign_id}}/replies/{{campaign_contact_id}}/triage")
    def triage_reply(
        campaign_id: str, campaign_contact_id: str,
        body: ReplyTriageUpdate, request: Request,
    ) -> dict[str, Any]:
        with request.app.state.campaign_locks.hold(campaign_id):
            return CampaignRelationships(_engine(request).store).triage(
                campaign_id, campaign_contact_id,
                review_status=body.review_status, outcome=body.outcome,
                note=body.note,
            )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/{{campaign_contact_id}}/messages")
    def contact_messages(
        campaign_id: str, campaign_contact_id: str, request: Request,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return CampaignRelationships(_engine(request).store).conversation(
            campaign_id, campaign_contact_id, limit=limit, offset=offset,
        )

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/followups")
    def followup_tasks(
        campaign_id: str, request: Request,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        status: str = Query("open", pattern="^(open|done|all)$"),
        overdue_only: bool = Query(False),
    ) -> dict[str, Any]:
        return CampaignRelationships(_engine(request).store).list_tasks(
            campaign_id, limit=limit, offset=offset,
            status=status, overdue_only=overdue_only,
        )

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/followups", status_code=201)
    def create_followup(
        campaign_id: str, body: FollowupTaskCreate, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)

        def operation() -> dict[str, Any]:
            with request.app.state.campaign_locks.hold(campaign_id):
                return CampaignRelationships(engine.store).create_task(
                    campaign_id, **body.model_dump()
                )

        return _idempotent(
            engine, f"followup_create:{campaign_id}", idempotency_key, operation
        )

    @app.patch(f"{API_PREFIX}/campaigns/{{campaign_id}}/followups/{{task_id}}")
    def update_followup(
        campaign_id: str, task_id: str,
        body: FollowupTaskUpdate, request: Request,
    ) -> dict[str, Any]:
        try:
            with request.app.state.campaign_locks.hold(campaign_id):
                return CampaignRelationships(_engine(request).store).update_task(
                    campaign_id, task_id, **body.model_dump(exclude_unset=True)
                )
        except TaskConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/launch-readiness")
    def campaign_launch_readiness(campaign_id: str, request: Request) -> dict[str, Any]:
        return launch_readiness(_engine(request).store, campaign_id)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/manual")
    def manual_contact(
        campaign_id: str,
        body: ContactCreate,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        engine = _engine(request)
        category = normalize_category(body.category or DEFAULT_CATEGORY, default=DEFAULT_CATEGORY)

        def operation() -> dict[str, Any]:
            with request.app.state.campaign_locks.hold(campaign_id):
                return engine.store.create_manual_campaign_contact(
                    campaign_id,
                    ContactInput(
                        full_name=body.full_name,
                        email=body.email,
                        company=body.company,
                        title=body.title,
                        category=category,
                        route=route_for_category(category),
                        public_hook=body.public_hook,
                        hook_source=body.hook_source,
                        recipient_timezone=body.recipient_timezone,
                        source_ref="manual",
                    ),
                )

        return _idempotent(engine, f"manual_contact:{campaign_id}", idempotency_key, operation)

    @app.post(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/bulk")
    def bulk_contacts(
        campaign_id: str, body: ContactBulkAction, request: Request
    ) -> dict[str, Any]:
        with request.app.state.campaign_locks.hold(campaign_id):
            return _engine(request).store.bulk_update_campaign_contacts(
                campaign_id, body.contact_ids, body.action
            )

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
        selected_only: bool = Query(False),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_campaign_contacts(
            campaign_id,
            limit=limit,
            offset=offset,
            search=search,
            status=status,
            category=category,
            variant_id=variant_id,
            selected_only=selected_only,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/facets")
    def contact_facets(campaign_id: str, request: Request) -> dict[str, list[str]]:
        return _engine(request).store.campaign_contact_facets(campaign_id)

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/contacts/download")
    def download_contacts(
        campaign_id: str,
        request: Request,
        search: str = Query("", max_length=120),
        status: str = Query("", max_length=40),
        category: str = Query("", max_length=120),
        variant_id: str = Query("", max_length=20),
        selected_only: bool = Query(False),
    ) -> Response:
        try:
            with request.app.state.campaign_locks.hold(campaign_id):
                store = _engine(request).store
                # Export every page from one database snapshot, including when
                # a different process edits this campaign at the same time.
                with store.transaction():
                    if store.backend == "postgres":
                        store.connection.execute(
                            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                        )
                    content = contact_list_csv(
                        store,
                        campaign_id,
                        search=search,
                        status=status,
                        category=category,
                        variant_id=variant_id,
                        selected_only=selected_only,
                    )
        except ContactExportError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="offcrm-filtered-contacts.csv"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

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
        return {"items": _ai_chat(request).list_projects(workspace_id=_workspace_id(request))}

    @app.post(f"{API_PREFIX}/ai/projects")
    def ai_create_project(body: AIProjectCreateBody, request: Request) -> dict[str, Any]:
        return _ai_chat(request).create_project(
            str(body.get("name", "")), workspace_id=_workspace_id(request),
        )

    @app.delete(f"{API_PREFIX}/ai/projects/{{project_id}}")
    def ai_delete_project(project_id: str, request: Request) -> dict[str, Any]:
        deleted = _ai_chat(request).delete_project(
            project_id, workspace_id=_workspace_id(request),
        )
        if not deleted:
            raise HTTPException(404, "Project not found")
        return {"deleted": project_id}

    @app.get(f"{API_PREFIX}/ai/chats")
    def ai_list_chats(request: Request, project_id: str = Query("", max_length=64), limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
        chats = _ai_chat(request).list_chats(
            workspace_id=_workspace_id(request), project_id=project_id or None, limit=limit,
        )
        return {"items": chats}

    @app.post(f"{API_PREFIX}/ai/chats")
    def ai_create_chat(body: AIChatCreateBody, request: Request) -> dict[str, Any]:
        try:
            return _ai_chat(request).create_chat(
                title=str(body.get("title", "New chat")),
                project_id=body.get("project_id"), workspace_id=_workspace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(404, "Project not found") from exc

    def require_own_chat(request: Request, chat_id: str) -> str:
        workspace = _workspace_id(request)
        if _ai_chat(request).get_chat(chat_id, workspace_id=workspace) is None:
            raise HTTPException(404, "Chat not found")
        return workspace

    @app.get(f"{API_PREFIX}/ai/chats/{{chat_id}}/permissions")
    def ai_chat_permissions(chat_id: str, request: Request) -> dict[str, Any]:
        workspace = require_own_chat(request, chat_id)
        grants = request.app.state.chat_permission_grants.get(workspace, chat_id)
        return {"granted_tools": grants.granted_tools if grants else []}

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/permissions")
    def ai_approve_chat_permission(
        chat_id: str, body: AttendedChatGrant, request: Request,
    ) -> dict[str, Any]:
        # A model response or workspace member cannot self-authorise a browser tool.
        require_install_owner(request)
        workspace = require_own_chat(request, chat_id)
        try:
            policy = AgentPermissionPolicy.from_mapping(
                request.app.state.ai_workspaces.raw_permissions(workspace).get(
                    "agent_permissions", {}
                )
            )
        except (PermissionErrorRule, ValueError, OSError) as exc:
            raise HTTPException(503, "Cannot check current browser permissions") from exc
        mode = policy.decide(body.tool)
        if mode == "deny":
            raise HTTPException(403, "Owner policy denies this browser tool")
        if mode != "ask":
            raise HTTPException(409, "This browser tool does not require temporary approval")
        try:
            grants = request.app.state.chat_permission_grants.grant(workspace, chat_id, body.tool)
        except PermissionErrorRule as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"granted_tools": grants.granted_tools}

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/browser-runs")
    async def ai_chat_read_only_browser_run(
        chat_id: str, body: ReadOnlyChatBrowserRun, request: Request,
    ) -> dict[str, Any]:
        """Owner-initiated and read-oriented only. No live watch/cancel UI yet."""
        from ..browser.policy import Refused, check_navigation, host_of

        require_install_owner(request)
        workspace = require_own_chat(request, chat_id)
        try:
            parts = urlsplit(body.target_url)
            hostname = parts.hostname
            username = parts.username
            password = parts.password
        except ValueError as exc:
            raise HTTPException(400, "Choose a valid public HTTP(S) URL") from exc
        if (
            parts.scheme not in {"https", "http"} or not hostname
            or username is not None or password is not None
        ):
            raise HTTPException(400, "Choose a public HTTP(S) URL without embedded credentials")
        try:
            # No live watch or cancel UI: enforce unattended host policy.
            check_navigation(body.target_url, unattended=True)
        except (Refused, ValueError) as exc:
            raise HTTPException(400, "Choose a public site, not a local or private address") from exc
        try:
            from ..agent.permissions import read_only_chat_policy
            workspace_policy = AgentPermissionPolicy.from_mapping(
                request.app.state.ai_workspaces.raw_permissions(workspace).get(
                    "agent_permissions", {}
                )
            )
            policy = read_only_chat_policy(workspace_policy)
        except (PermissionErrorRule, ValueError, OSError) as exc:
            raise HTTPException(503, "Current browser permissions are unavailable") from exc
        grants = request.app.state.chat_permission_grants.get(workspace, chat_id)
        navigation = policy.decide("goto", grants=grants)
        if navigation == "deny":
            raise HTTPException(403, "Owner policy refuses browser navigation")
        if navigation != "allow":
            raise HTTPException(409, "Approve the goto tool for this chat before starting")
        store = request.app.state.agent_routine_store
        lease_owner = f"attended-chat:{uuid.uuid4().hex}"
        if not store.acquire_workspace_lease(workspace, lease_owner, lease_seconds=180):
            raise HTTPException(409, "Another browser run is using this workspace")
        start = time.time()
        routine = Routine(
            id=chat_id, workspace_id=workspace, name="Attended chat reading",
            goal=body.goal, target_url=body.target_url,
            target_host=host_of(body.target_url), trigger_type="event",
            interval_seconds=0, event_name="", step_budget=body.step_budget,
            enabled=True, next_due_at=0.0,
            created_at=start, updated_at=start,
        )
        registry = request.app.state.chat_browser_runs
        task = asyncio.create_task(
            request.app.state.agent_routines.runner(
                routine, {}, attended=True, chat_permissions=grants,
            ),
            name=f"chat-browser-{chat_id[:8]}",
        )
        run_id = ""
        try:
            run_id = registry.register(workspace, chat_id, task)
            execution = await asyncio.wait_for(task, timeout=115.0)
        except asyncio.CancelledError:
            # A concurrent owner cancellation is not an application error.
            # The actual runner's finally block terminates the container.
            return {
                "status": "cancelled", "agent_run_id": run_id,
                "summary": "The browser run was cancelled.", "result": {},
            }
        except asyncio.TimeoutError as exc:
            ref = failure_message(exc, operation="attended_chat_browser", workspace=workspace)
            raise HTTPException(503, f"Browser reading timed out. {ref}") from exc
        except ValueError as exc:
            task.cancel()
            raise HTTPException(409, "A browser run is already active for this chat") from exc
        except Exception as exc:
            ref = failure_message(exc, operation="attended_chat_browser", workspace=workspace)
            raise HTTPException(503, f"Browser reading failed. {ref}") from exc
        finally:
            if run_id:
                registry.finish(workspace, chat_id, run_id)
            store.release_workspace_lease(workspace, lease_owner)
        return {
            "status": execution.status,
            "agent_run_id": execution.agent_run_id,
            "summary": execution.summary,
            "result": execution.result,
        }

    @app.get(f"{API_PREFIX}/ai/chats/{{chat_id}}/browser-runs")
    def ai_chat_active_browser_run(chat_id: str, request: Request) -> dict[str, Any]:
        require_install_owner(request)
        workspace = require_own_chat(request, chat_id)
        record = request.app.state.chat_browser_runs.active(workspace, chat_id)
        return record if record is not None else {"active": False}

    @app.delete(f"{API_PREFIX}/ai/chats/{{chat_id}}/browser-runs/{{run_id}}", status_code=202)
    def ai_cancel_chat_browser_run(
        chat_id: str, run_id: str, request: Request,
    ) -> dict[str, str]:
        require_install_owner(request)
        workspace = require_own_chat(request, chat_id)
        accepted = request.app.state.chat_browser_runs.cancel(workspace, chat_id, run_id)
        if not accepted:
            raise HTTPException(404, "No matching active browser run")
        return {"status": "cancellation_requested", "run_id": run_id}

    @app.delete(f"{API_PREFIX}/ai/chats/{{chat_id}}/permissions")
    def ai_close_chat_permissions(chat_id: str, request: Request) -> dict[str, Any]:
        require_install_owner(request)
        workspace = require_own_chat(request, chat_id)
        request.app.state.chat_permission_grants.revoke_chat(workspace, chat_id)
        return {"closed": chat_id}

    @app.delete(f"{API_PREFIX}/ai/chats/{{chat_id}}")
    def ai_delete_chat(chat_id: str, request: Request) -> dict[str, Any]:
        workspace = require_own_chat(request, chat_id)
        request.app.state.chat_browser_runs.revoke_chat(workspace, chat_id)
        _ai_chat(request).delete_chat(chat_id, workspace_id=workspace)
        request.app.state.chat_permission_grants.revoke_chat(workspace, chat_id)
        return {"deleted": chat_id}

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/move")
    def ai_move_chat(chat_id: str, body: AIChatMoveBody, request: Request) -> dict[str, Any]:
        workspace = require_own_chat(request, chat_id)
        result = _ai_chat(request).move_chat(
            chat_id, body.get("project_id"), workspace_id=workspace,
        )
        if not result:
            raise HTTPException(404, "Chat or project not found")
        return result

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/rename")
    def ai_rename_chat(chat_id: str, body: AIChatRenameBody, request: Request) -> dict[str, Any]:
        workspace = require_own_chat(request, chat_id)
        result = _ai_chat(request).rename_chat(
            chat_id, str(body.get("title", "")), workspace_id=workspace,
        )
        if not result:
            raise HTTPException(404, "Chat not found")
        return result

    @app.get(f"{API_PREFIX}/ai/chats/{{chat_id}}/messages")
    def ai_list_messages(chat_id: str, request: Request) -> dict[str, Any]:
        workspace = require_own_chat(request, chat_id)
        return {"items": _ai_chat(request).list_messages(chat_id, workspace_id=workspace)}

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
        if isinstance(exc, ReasonRequired):
            return HTTPException(400, detail={"error": "reason_required", "message": str(exc)})
        if isinstance(exc, ValueError):
            return HTTPException(400, detail={"error": "invalid_request", "message": str(exc)})
        return HTTPException(500, detail={"error": "ai_error", "message": str(exc)})

    def _workspace_id(request: Request) -> str:
        # A timer acts for the install, as the API token does. It has no cookies
        # to read a login from; asking for them crashed every timed run of the
        # content engine (D-109).
        if isinstance(request, _TimerScope):
            return "local"
        caller = _caller(request)
        if caller is None:
            raise HTTPException(status_code=401, detail="CRM login required")
        return caller

    def require_install_owner(request: Request) -> None:
        # The owner is the install's own workspace, `local`: the install token,
        # the demo login bootstrapped into `local`, or a server run without
        # auth. Not the token alone, as `require_workspace_admin` is — a demo
        # login has no token (none is made when a login is configured), and on
        # Render's free plan a backup is how that owner keeps data (D-124).
        if valid_api_token(request) or _workspace_id(request) == "local":
            return
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the install owner can do this: it covers every workspace. "
                "Sign in with the owner's login or use the install API token."
            ),
        )


    @app.get(f"{API_PREFIX}/storage/readiness")
    def get_storage_readiness(request: Request) -> dict[str, Any]:
        """An owner-only, read-only summary. Never disclose URLs, paths or keys."""
        require_install_owner(request)
        return describe_storage_readiness(resolved)

    def _require_local_capture_origin(request: Request) -> None:
        """Meeting audio is accepted only from this machine's own browser.

        A hosted deployment receiving the bytes would violate S-07.01.03 before
        the transcription provider was even called. Loopback binding plus a
        loopback browser Origin makes the local boundary explicit and testable.
        """
        if not loopback:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Meeting capture is local-only. Run off_CRM on localhost so "
                    "raw audio goes only from this machine to the declared "
                    "transcription provider."
                ),
            )
        origin = str(request.headers.get("origin") or "").strip()
        try:
            origin_host = (urlsplit(origin).hostname or "").lower()
        except ValueError:
            origin_host = ""
        if origin_host not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(
                status_code=403,
                detail="Meeting capture requires a localhost browser origin",
            )

    def _meeting_transcription_choices(request: Request) -> list[dict[str, Any]]:
        workspace_id = _workspace_id(request)
        state = request.app.state
        description = state.ai_workspaces.describe(workspace_id)
        settings = state.ai_workspaces.egress_settings(workspace_id)
        broker = state.ai_broker.with_credential_resolver(
            state.ai_workspaces.credential_resolver(workspace_id)
        )
        choices: list[dict[str, Any]] = []
        for provider in description["providers"]:
            if not (
                provider.get("connected")
                and provider.get("enabled")
                and provider.get("has_key")
            ):
                continue
            for model in provider.get("available_models") or []:
                if str(model.get("kind") or "chat") != "transcribe":
                    continue
                candidate_settings = replace(
                    settings,
                    enabled_models={
                        **settings.enabled_models,
                        str(provider["id"]): (str(model["id"]),),
                    },
                )
                try:
                    candidates, _ = broker.plan(
                        EgressRequest(
                            task_type="meeting_transcription",
                            data_class=DataClass.CAMPAIGN,
                            instructions="Transcribe meeting audio.",
                            task_tags=("transcribe", "meeting"),
                        ),
                        candidate_settings,
                        provider_id=str(provider["id"]),
                        kind="transcribe",
                    )
                except (PolicyViolation, NoPermittedProvider, RegistryError):
                    candidates = []
                if not candidates:
                    continue
                choices.append({
                    "provider_id": str(provider["id"]),
                    "provider_name": str(provider["name"]),
                    "flag": str(provider.get("flag") or ""),
                    "model_id": str(model["id"]),
                    "tier": str(model.get("tier") or provider.get("effective_tier") or ""),
                })
        return choices

    @app.get(f"{API_PREFIX}/meetings/capabilities")
    def meeting_capabilities(request: Request) -> dict[str, Any]:
        return {
            "local_server": loopback,
            "requires_local_browser": True,
            "max_chunk_bytes": MAX_MEETING_CHUNK_BYTES,
            "chunk_seconds": 30,
            "providers": _meeting_transcription_choices(request),
        }

    @app.get(f"{API_PREFIX}/meetings")
    def meetings(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        items = request.app.state.meeting_store.list(
            workspace_id=_workspace_id(request),
            limit=limit,
        )
        return {"items": items, "total": len(items)}

    @app.get(f"{API_PREFIX}/meetings/{{meeting_id}}")
    def meeting(meeting_id: str, request: Request) -> dict[str, Any]:
        workspace_id = _workspace_id(request)
        try:
            item = request.app.state.meeting_store.require(
                meeting_id, workspace_id=workspace_id
            )
            item["chunks"] = request.app.state.meeting_store.chunks(
                meeting_id, workspace_id=workspace_id
            )
            return item
        except MeetingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/meetings", status_code=201)
    def create_meeting(body: MeetingCreate, request: Request) -> dict[str, Any]:
        _require_local_capture_origin(request)
        try:
            return request.app.state.meeting_store.create(
                workspace_id=_workspace_id(request),
                title=body.title,
                provider_id=body.provider_id,
                model_id=body.model_id,
                language=body.language,
            )
        except MeetingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/meetings/{{meeting_id}}/chunks")
    async def transcribe_meeting_chunk(
        meeting_id: str,
        request: Request,
        file: UploadFile = File(...),
        sequence: int = Form(..., ge=0),
        provider_id: str = Form("", max_length=80),
        model_id: str = Form("", max_length=240),
        language: str = Form("", max_length=32),
    ) -> dict[str, Any]:
        # Guard before reading a single audio byte from the request.
        _require_local_capture_origin(request)
        workspace_id = _workspace_id(request)
        try:
            request.app.state.meeting_store.require(
                meeting_id, workspace_id=workspace_id
            )
        except MeetingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        content = await file.read(MAX_MEETING_CHUNK_BYTES + 1)
        if len(content) > MAX_MEETING_CHUNK_BYTES:
            raise HTTPException(status_code=413, detail="Meeting audio chunk is too large")
        try:
            return await run_in_threadpool(
                request.app.state.meeting_transcriber.transcribe_chunk,
                workspace_id=workspace_id,
                meeting_id=meeting_id,
                sequence=sequence,
                audio=content,
                media_type=str(file.content_type or "audio/webm"),
                provider_id=provider_id,
                model_id=model_id,
                language=language,
            )
        except (MeetingTranscriptionError, MeetingError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (EgressBlocked, PolicyViolation, NoPermittedProvider, RegistryError) as exc:
            raise _ai_error(exc) from exc

    @app.post(f"{API_PREFIX}/meetings/{{meeting_id}}/complete")
    def complete_meeting(meeting_id: str, request: Request) -> dict[str, Any]:
        _require_local_capture_origin(request)
        try:
            return request.app.state.meeting_store.complete(
                meeting_id, workspace_id=_workspace_id(request)
            )
        except MeetingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete(f"{API_PREFIX}/meetings/{{meeting_id}}")
    def delete_meeting(meeting_id: str, request: Request) -> dict[str, bool]:
        deleted = request.app.state.meeting_store.delete(
            meeting_id, workspace_id=_workspace_id(request)
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return {"deleted": True}

    def _gtm(request: Request) -> GtmService:
        """The strategy brain for this request's workspace.  `E-12`

        ``ask`` is the one model call it makes, built the way the video
        director's is, with three differences that are the point of it:

        - **Campaign class.** The product is the owner's material; tier C and D
          may not see it, and the broker already knows what each tier may receive.
        - **The product in classified fields** — one-liner as the positioning
          line, the rest as campaign notes — so each provider's data policy
          decides how much of it leaves (DD-41). The system prompt is code-only.
        - **Every broker refusal becomes ``ModelUnavailable``**, so "no model
          connected" gives the owner the rules plan and the reason, never a 500.
          Anything that is not a broker refusal still surfaces: a bug should not
          be disguised as a missing key.
        """
        state = request.app.state
        workspace_id = _workspace_id(request)
        settings = state.ai_workspaces.egress_settings(workspace_id)

        def ask(
            *,
            system_prompt: str,
            task_type: str,
            positioning_line: str,
            campaign_notes: str,
            instructions: str,
            template_text: str = "",
        ) -> Any:
            # A copy bound to this workspace's keys. Setting the resolver on the
            # shared broker let two workspaces' requests race for one key (D-106).
            broker = state.ai_broker.with_credential_resolver(
                state.ai_workspaces.credential_resolver(workspace_id)
            )
            try:
                return broker.call(
                    EgressRequest(
                        task_type=task_type,
                        data_class=DataClass.CAMPAIGN,
                        instructions=instructions,
                        positioning_line=positioning_line,
                        campaign_notes=campaign_notes,
                        template_text=template_text,
                    ),
                    settings,
                    system_prompt=system_prompt,
                    expect_json=True,
                )
            except AIModuleError as exc:
                raise ModelUnavailable(str(exc)) from exc

        return GtmService(
            state.gtm_store,
            workspace_id=workspace_id,
            identities=lambda: state.email_delivery.store.list_identities(),
            accounts=lambda: state.distribution_store.list_accounts(workspace_id=workspace_id),
            apollo_ready=lambda: bool(os.getenv("APOLLO_API_KEY", "").strip()),
            ask=ask,
            # The legacy expert_chunks table has no workspace_id. Until it is
            # tenant-scoped, do not offer the install owner's imported corpus
            # to another workspace's model calls.
            expert_search=(
                (lambda query: state.engine.store.search_expert_chunks(query, limit=4))
                if workspace_id == "local" else None
            ),
            winning_reference=lambda: state.ai_context.reference_for_models(workspace_id),
            # Apply goes through the engine's own campaign creation, the same
            # call `POST /campaigns` makes, so a plan's campaign is exactly the
            # campaign a person could have made by hand.
            create_campaign=lambda **values: _engine(request).create_campaign(**values),
            update_campaign=lambda campaign_id, changes: _engine(request).store.update_campaign(
                campaign_id, changes
            ),
            set_goal=lambda **values: state.distribution_store.set_goal(
                workspace_id=workspace_id, **values
            ),
            goals_of=lambda campaign_id: state.distribution_store.list_goals(campaign_id),
            lock=lambda key: state.campaign_locks.hold(key),
            # What a review measures — each the same reader the screen for
            # that fact uses, so the review and the screen cannot disagree.
            register_posting=state.content_automation.register_pipeline if workspace_id == "local" else None,
            readers=GtmReaders(
                campaign=lambda campaign_id: _engine(request).store.get_campaign(campaign_id),
                email_summary=lambda campaign_id: _engine(request).store.campaign_summary(
                    campaign_id
                ),
                health=lambda campaign_id: state.email_delivery.store.health(campaign_id),
                weak_templates=lambda: len(state.ai_context.weak_templates(workspace_id)),
                published=lambda campaign_id: len(
                    state.distribution_store.list_posts(
                        campaign_id, status="published", limit=PUBLISHED_COUNT_LIMIT
                    )
                ),
                pacing=lambda campaign_id: _pacing_decision(request.app, campaign_id, workspace_id=_workspace_id(request)).to_dict(),
            ),
        )

    @app.post(f"{API_PREFIX}/ai/chats/{{chat_id}}/messages")
    def ai_send_message(chat_id: str, body: AIChatMessageBody, request: Request) -> dict[str, Any]:
        """Send a chat turn through the egress broker.

        ``data_class`` decides which providers may answer. ``public`` is for
        code and general questions and lets restricted-tier models help;
        ``campaign`` is the default and keeps the conversation on trusted tiers.
        """
        workspace_id = require_own_chat(request, chat_id)
        broker, workspaces, _ = _ai(request)
        settings = workspaces.egress_settings(workspace_id)
        broker = broker.with_credential_resolver(
            workspaces.credential_resolver(workspace_id)
        )

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

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/balance")
    def ai_provider_balance(provider_id: str, request: Request) -> dict[str, Any]:
        """Explicit, key-scoped vendor usage check; no model call or payload."""
        from ..ai import provider_usage

        broker, workspaces, _ = _ai(request)
        entry = broker.registry.get(provider_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Unknown AI provider")
        if entry.usage_report != "balance_endpoint":
            reason = (
                "Provider reports limits in response headers; balance is not "
                "available through this screen yet"
                if entry.usage_report == "rate_limit_headers"
                else "Provider does not report a supported remaining balance"
            )
            return {"provider_id": provider_id, "supported": False,
                    "usage_report": entry.usage_report, "reason": reason}
        key = workspaces.key_for(_workspace_id(request), provider_id)
        if not key:
            raise HTTPException(
                status_code=409,
                detail="Connect this provider in your workspace before checking its balance",
            )
        try:
            return {"supported": True, **provider_usage.fetch_provider_balance(provider_id, key)}
        except provider_usage.UsageReportError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/connect")
    def ai_connect_provider(
        provider_id: str, body: AIProviderConnectBody, request: Request
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
        # Shown with the owner's trust, not config's default: the list is
        # where models are chosen, so it must match what the router does.
        override = workspaces.egress_settings(workspace_id).overrides.get(provider_id)
        if override is not None:
            registry = request.app.state.ai_registry
            for model in result.models:
                if model.known:
                    model.tier = registry.resolve(
                        provider_id, model_id=model.id, override=override
                    ).tier.value
        return result.to_dict()

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/override")
    def ai_override_provider(
        provider_id: str, body: AIProviderOverrideBody, request: Request
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
                # The login, never the request's own claim (D-152): the body
                # still accepts `decided_by` so older clients are not refused,
                # and it is ignored.
                decided_by=_decided_by(request),
            )
        except (RegistryError, ValueError) as exc:
            raise _ai_error(exc) from exc

    @app.post(f"{API_PREFIX}/ai/providers/{{provider_id}}/trust")
    def ai_provider_trust(
        provider_id: str, body: AIProviderTrustBody, request: Request
    ) -> dict[str, Any]:
        """Raise or lower trust for a provider or one of its models (S-06.02.33)."""
        _, workspaces, _ = _ai(request)
        try:
            workspaces.set_trust(
                _workspace_id(request),
                provider_id,
                tier=body.tier,
                model_id=body.model_id,
                reason=body.reason,
                decided_by=_decided_by(request),
            )
        except (RegistryError, ValueError) as exc:
            raise _ai_error(exc) from exc
        return {"status": "saved", "provider_id": provider_id}

    @app.post(f"{API_PREFIX}/ai/workspace")
    def ai_update_workspace(body: AIWorkspaceUpdateBody, request: Request) -> dict[str, Any]:
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
    def ai_mailbox_unlock(body: AIMailboxUnlockBody, request: Request) -> dict[str, Any]:
        _, workspaces, _ = _ai(request)
        try:
            workspaces.unlock_mailbox(_workspace_id(request), str(body.get("phrase", "")))
        except ValueError as exc:
            raise HTTPException(400, detail={"error": "bad_phrase", "message": str(exc)}) from exc
        return workspaces.describe(_workspace_id(request))

    @app.post(f"{API_PREFIX}/ai/plan")
    def ai_plan(body: AIPlanBody, request: Request) -> dict[str, Any]:
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
    def ai_run(body: AIRunBody, request: Request) -> dict[str, Any]:
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
        broker = broker.with_credential_resolver(
            workspaces.credential_resolver(workspace_id)
        )

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
                checks = checks_for(suite_id, default_evals_path()) if suite_id else ()
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
    def ai_image(body: AIImageBody, request: Request) -> dict[str, Any]:
        """Draw a picture from a prompt.

        Same gate as everything else: the prompt is text, so if it names a real
        person it is person data and the trust rules apply unchanged.
        """
        broker, workspaces, _ = _ai(request)
        workspace_id = _workspace_id(request)
        settings = workspaces.egress_settings(workspace_id)
        broker = broker.with_credential_resolver(
            workspaces.credential_resolver(workspace_id)
        )

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
    def ai_register_template(body: AITemplateRegisterBody, request: Request) -> dict[str, Any]:
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
        template_id: str, body: AITemplateRewriteBody, request: Request
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
        broker = broker.with_credential_resolver(
            workspaces.credential_resolver(workspace_id)
        )
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
        template_id: str, body: AITemplateApproveBody, request: Request
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
    def ai_start_task(body: AITaskStartBody, request: Request) -> dict[str, Any]:
        task = _context(request).start_task(
            workspace_id=_workspace_id(request),
            kind=str(body.get("kind", "campaign")),
            title=str(body.get("title", "")),
            steps=[str(step) for step in (body.get("steps") or [])],
        )
        return task.to_dict()

    @app.post(f"{API_PREFIX}/ai/context/tasks/{{task_id}}/step")
    def ai_finish_step(task_id: str, body: AITaskStepBody, request: Request) -> dict[str, Any]:
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
    def ai_record_decision(task_id: str, body: AITaskDecisionBody, request: Request) -> dict[str, Any]:
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
    def ai_recall_search(body: AIRecallSearchBody, request: Request) -> dict[str, Any]:
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
    def ai_recall_preview(body: AIRecallPreviewBody, request: Request) -> dict[str, Any]:
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
    def ai_recall_forget(body: AIRecallForgetBody, request: Request) -> dict[str, Any]:
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
        if record is None or record["workspace_id"] != _workspace_id(request):
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

    @app.post(f"{API_PREFIX}/privacy/subject-access")
    def privacy_subject_access(
        body: PrivacySubjectBody, request: Request
    ) -> dict[str, Any]:
        """Inventory one verified subject across every registered personal-data store."""
        try:
            subject = _privacy_subject(body, _workspace_id(request))
            return _privacy(request).access(subject)
        except PrivacyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/privacy/deletion-preview", status_code=201)
    def privacy_deletion_preview(
        body: PrivacySubjectBody, request: Request
    ) -> dict[str, Any]:
        """Create the exact inventory that a later confirmed deletion will execute."""
        try:
            subject = _privacy_subject(body, _workspace_id(request))
            return _privacy(request).preview(subject)
        except PrivacyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(f"{API_PREFIX}/privacy/deletions/{{request_id}}")
    def privacy_delete_subject(
        request_id: str,
        body: PrivacyDeletionBody,
        request: Request,
    ) -> dict[str, Any]:
        """Execute/retry one previewed deletion. Never invent confirmation."""
        try:
            subject = _privacy_subject(body, _workspace_id(request))
            return _privacy(request).delete(
                request_id,
                subject,
                confirmation=str(body.get("confirmation") or ""),
            )
        except PrivacyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(f"{API_PREFIX}/privacy/deletion-confirmation")
    def privacy_deletion_confirmation() -> dict[str, str]:
        """Expose the destructive confirmation phrase without weakening the gate."""
        return {"confirmation": DELETE_CONFIRMATION}

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
                workspace_id = _workspace_id(request)
                provider = request.app.state.provider_profiles.router(
                    # The caller's own profiles, the install owner included:
                    # "every workspace's" put a client's planted profile in
                    # the owner's chain (D-155, D-165).
                    owner=workspace_id,
                    profile_ids=body.provider_profile_ids,
                    strategy=body.fallback_strategy,
                    audit_callback=partial(
                        engine.store.record_provider_call, workspace_id=workspace_id
                    ),
                    may_confirm=not _profile_scope(request),
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
    def queue(
        campaign_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=200),
        offset: int = Query(0, ge=0),
        view: str = Query("all", pattern="^(all|ready|approval|replied)$"),
    ) -> dict[str, Any]:
        return _engine(request).store.send_queue_view(
            campaign_id, now=utc_now(), limit=limit, offset=offset, view=view
        )

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

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/events/types")
    def event_type_facets(campaign_id: str, request: Request) -> dict[str, Any]:
        items = _engine(request).store.event_types(campaign_id)
        return {"items": items, "total": len(items)}

    @app.get(f"{API_PREFIX}/campaigns/{{campaign_id}}/events")
    def events(
        campaign_id: str,
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        event_type: str = Query("", max_length=100),
    ) -> dict[str, Any]:
        items, total = _engine(request).store.list_events(
            campaign_id, limit=limit, offset=offset, event_type=event_type
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

    # Before the frontend: a mount at "/" answers every path it is given, so a
    # route added after it — /health/ready, Render's health check — was a 404
    # in the built image and in no test, because tests run without a build.
    install_runtime_routes(
        app,
        resolved,
        open_runtime=_open_runtime,
        close_runtime=_close_runtime,
        require_owner=require_install_owner,
    )

    if resolved.frontend_dist.exists():
        app.mount("/", StaticFiles(directory=resolved.frontend_dist, html=True), name="frontend")

    app.add_middleware(FailureMiddleware, reporter=FailureReporter(resolved.data_dir))
    return app
