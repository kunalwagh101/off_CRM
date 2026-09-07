"""Production reliability retrofit for the FastAPI application.

This module owns the audit-WP1 boundaries that cut across several existing
services: maintenance draining, complete restore/rebind and truthful readiness.
It wraps the existing ``create_app`` rather than duplicating the application.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from ..ai import EgressBroker, EgressLog, ProviderRegistry, QuotaTracker, ResponseCache
from ..ai.context import ContextLayer
from ..ai.recall import SentMailIndex
from ..ai.workspace import WorkspaceAISettingsStore
from ..db import resolve_target as resolve_database_target
from ..distribution.store import DistributionStore
from ..imagery.store import ImageStore
from ..outreach.ai_chat import AIChatService
from ..outreach.backup import (
    create_encrypted_backup,
    discard_restore_safety,
    restore_encrypted_backup,
    rollback_restored_backup,
    validate_encrypted_backup,
)
from ..outreach.deliverability.service import EmailDeliveryService
from ..outreach.deliverability.store import DeliverabilityStore
from ..outreach.deliverability.unsubscribe import UnsubscribeService
from ..outreach.engine import OutreachEngine
from ..outreach.notion import NotionSettingsStore
from ..outreach.provider_profiles import ProviderProfileStore
from ..outreach.sales import SalesTracker
from ..video.store import VideoStore
from .schemas import BackupExport


API_PREFIX = "/api/v1"
_CHUNK = 1024 * 1024


class RecoveryGate:
    """Drain active requests and reject new work during a workspace swap."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active = 0
        self.maintenance = False

    async def enter_request(self) -> bool:
        async with self._condition:
            if self.maintenance:
                return False
            self._active += 1
            return True

    async def leave_request(self) -> None:
        async with self._condition:
            self._active = max(0, self._active - 1)
            self._condition.notify_all()

    async def begin_maintenance(self) -> None:
        async with self._condition:
            if self.maintenance:
                raise RuntimeError("Maintenance is already running")
            self.maintenance = True
            while self._active:
                await self._condition.wait()

    async def end_maintenance(self) -> None:
        async with self._condition:
            self.maintenance = False
            self._condition.notify_all()


def _remove_route(app: Any, path: str, method: str) -> None:
    method = method.upper()
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and method in (getattr(route, "methods", None) or set())
        )
    ]


def _close(object_: Any) -> None:
    close = getattr(object_, "close", None)
    if callable(close):
        close()


def _close_runtime(state: Any) -> None:
    # Order: stop users of the outreach store before closing the store itself.
    for name in (
        "ai_egress_log",
        "image_store",
        "distribution_store",
        "video_store",
        "ai_context",
        "ai_recall",
        "engine",
    ):
        object_ = getattr(state, name, None)
        if object_ is not None:
            _close(object_)


def _rebind_runtime(state: Any, settings: Any, *, previous: dict[str, Any]) -> None:
    """Recreate every live object whose durable backing may have been replaced."""
    state.ai_context = ContextLayer(settings.data_dir / "ai_context.db")
    state.ai_recall = SentMailIndex(settings.data_dir / "ai_recall.db")
    state.engine = OutreachEngine(
        settings.database_path,
        template_counter=state.ai_context,
        mail_archive=state.ai_recall,
    )
    state.ai_chat = AIChatService(state.engine.store)
    state.sales = SalesTracker(state.engine.store)

    delivery_store = DeliverabilityStore(state.engine.store)
    unsubscribe = UnsubscribeService.from_path(
        delivery_store,
        settings.data_dir / "email_unsubscribe.key",
        public_base_url=settings.public_base_url,
        configured_secret=settings.unsubscribe_secret,
    )
    old_delivery = previous.get("email_delivery")
    state.email_delivery = EmailDeliveryService(
        state.engine,
        unsubscribe=unsubscribe,
        domain_checker=getattr(old_delivery, "domain_checker", None),
        provider_factory=getattr(old_delivery, "provider_factory", None),
    )
    state.engine.delivery_preflight = state.email_delivery.preflight
    state.engine.unsubscribe_service = unsubscribe

    # Registry/config objects are cheap to recreate and may themselves read
    # files restored under the durable root.
    state.provider_profiles = ProviderProfileStore(settings.data_dir)
    state.ai_registry = ProviderRegistry()
    state.ai_workspaces = WorkspaceAISettingsStore(settings.data_dir, state.ai_registry)
    state.ai_egress_log = EgressLog(
        resolve_database_target(default=settings.data_dir / "ai_egress.db")
    )
    state.ai_quota = QuotaTracker(settings.data_dir)
    state.ai_cache = ResponseCache(settings.data_dir / "ai_cache.db")
    old_broker = previous.get("ai_broker")
    state.ai_broker = EgressBroker(
        registry=state.ai_registry,
        credential_resolver=getattr(old_broker, "credential_resolver", lambda _provider: ""),
        quota=state.ai_quota,
        logger=state.ai_egress_log.record,
        cache=state.ai_cache,
        timeout_seconds=int(getattr(old_broker, "timeout_seconds", 60)),
        failure_threshold=int(getattr(old_broker, "failure_threshold", 2)),
        cooldown_seconds=int(getattr(old_broker, "cooldown_seconds", 60)),
        max_retries=int(getattr(old_broker, "max_retries", 2)),
        deadline_seconds=float(getattr(old_broker, "deadline_seconds", 120.0)),
    )

    state.image_store = ImageStore(
        settings.data_dir / "imagery.db",
        assets_dir=settings.data_dir / "image_assets",
    )
    state.distribution_store = DistributionStore(
        settings.data_dir / "distribution.db",
        outbox_dir=settings.data_dir / "post_outbox",
    )
    state.video_store = VideoStore(
        resolve_database_target(default=settings.data_dir / "video.db"),
        renders_dir=settings.data_dir / "video_renders",
    )
    state.trends_path = settings.data_dir / "trends.db"
    state.notion = NotionSettingsStore(settings.data_dir)


def _snapshot_runtime(state: Any) -> dict[str, Any]:
    return {
        name: getattr(state, name, None)
        for name in (
            "engine",
            "email_delivery",
            "ai_broker",
            "ai_context",
            "ai_recall",
            "ai_egress_log",
            "image_store",
            "distribution_store",
            "video_store",
        )
    }


def _sqlite_probe(path: Path) -> None:
    if not path.exists():
        return
    connection = sqlite3.connect(f"file:{path}?mode=rw", uri=True, timeout=1)
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()


def _runtime_health(
    state: Any,
    settings: Any,
    *,
    include_maintenance: bool = True,
) -> list[str]:
    failures: list[str] = []
    gate = getattr(state, "recovery_gate", None)
    if include_maintenance and gate is not None and gate.maintenance:
        failures.append("maintenance")

    try:
        state.engine.store.connection.execute("SELECT 1").fetchone()
    except Exception as exc:
        failures.append(f"outreach_db:{type(exc).__name__}")

    # The audit caught a restore where these services still pointed to the old,
    # closed store. Treat that as not-ready even if the replacement database
    # itself answers SELECT 1.
    engine_store = getattr(getattr(state, "engine", None), "store", None)
    if getattr(getattr(state, "sales", None), "store", None) is not engine_store:
        failures.append("sales_store:stale")
    if getattr(getattr(state, "ai_chat", None), "store", None) is not engine_store:
        failures.append("ai_chat_store:stale")
    delivery = getattr(state, "email_delivery", None)
    if getattr(delivery, "engine", None) is not getattr(state, "engine", None):
        failures.append("email_delivery_engine:stale")
    if getattr(getattr(delivery, "store", None), "outreach", None) is not engine_store:
        failures.append("email_delivery_store:stale")

    # Read/write the durable root, not merely SELECT 1 from one database. A
    # mounted disk that vanished or became read-only must make readiness red.
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".offcrm-ready-", dir=settings.data_dir)
        try:
            os.write(fd, b"ready")
            os.fsync(fd)
        finally:
            os.close(fd)
            Path(name).unlink(missing_ok=True)
    except Exception as exc:
        failures.append(f"durable_root:{type(exc).__name__}")

    # Existing durable sqlite stores are all probed. Optional stores that have
    # never been created are not readiness dependencies yet.
    for name in (
        "ai_context.db",
        "ai_recall.db",
        "ai_egress.db",
        "imagery.db",
        "distribution.db",
        "trends.db",
        "video.db",
    ):
        try:
            _sqlite_probe(settings.data_dir / name)
        except Exception as exc:
            failures.append(f"{name}:{type(exc).__name__}")
    return failures


async def _bounded_upload(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(min(_CHUNK, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="Backup exceeds the backup upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def harden_create_app(original_create_app: Callable[..., Any]) -> Callable[..., Any]:
    """Return ``create_app`` with WP1 production reliability boundaries added."""

    def create_app(settings: Any = None) -> Any:
        app = original_create_app(settings)
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def reliable_lifespan(application: Any) -> AsyncIterator[None]:
            async with original_lifespan(application):
                application.state.recovery_gate = RecoveryGate()
                yield

        app.router.lifespan_context = reliable_lifespan

        @app.middleware("http")
        async def recovery_request_gate(request: Request, call_next: Any) -> Response:
            gate = getattr(request.app.state, "recovery_gate", None)
            if gate is None or request.url.path in {
                "/health/live",
                "/health/ready",
                f"{API_PREFIX}/backups/restore",
            }:
                return await call_next(request)
            if not await gate.enter_request():
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Workspace maintenance is in progress"},
                    headers={"Retry-After": "5"},
                )
            try:
                return await call_next(request)
            finally:
                await gate.leave_request()

        _remove_route(app, "/health/ready", "GET")

        @app.get("/health/ready")
        def reliable_ready(request: Request) -> dict[str, Any]:
            failures = _runtime_health(request.app.state, request.app.state.settings)
            if failures:
                raise HTTPException(
                    status_code=503,
                    detail={"status": "not_ready", "components": failures},
                )
            return {"status": "ready"}

        _remove_route(app, f"{API_PREFIX}/backups/export", "POST")

        @app.post(f"{API_PREFIX}/backups/export")
        def complete_backup(body: BackupExport, request: Request) -> Response:
            resolved = request.app.state.settings
            content = create_encrypted_backup(
                database_path=resolved.database_path,
                data_dir=resolved.data_dir,
                passphrase=body.passphrase,
                max_bytes=resolved.backup_max_bytes,
            )
            return Response(
                content=content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": 'attachment; filename="off-crm-workspace.oxbackup"'},
            )

        _remove_route(app, f"{API_PREFIX}/backups/restore", "POST")

        @app.post(f"{API_PREFIX}/backups/restore")
        async def safe_restore(
            request: Request,
            file: UploadFile = File(...),
            passphrase: str = Form(..., min_length=12, max_length=500),
        ) -> dict[str, Any]:
            resolved = request.app.state.settings
            content = await _bounded_upload(file, resolved.backup_max_bytes)

            # A bad archive must not be able to take the live product down.
            manifest = await asyncio.to_thread(
                validate_encrypted_backup,
                content,
                passphrase=passphrase,
                max_bytes=resolved.backup_max_bytes,
            )

            gate: RecoveryGate = request.app.state.recovery_gate
            try:
                await gate.begin_maintenance()
            except RuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

            state = request.app.state
            automation = state.automation
            content_automation = state.content_automation
            previous = _snapshot_runtime(state)
            result: dict[str, Any] | None = None
            try:
                await automation.stop()
                await content_automation.stop()
                _close_runtime(state)
                for suffix in ("-wal", "-shm"):
                    Path(str(resolved.database_path) + suffix).unlink(missing_ok=True)
                result = await asyncio.to_thread(
                    restore_encrypted_backup,
                    content,
                    database_path=resolved.database_path,
                    data_dir=resolved.data_dir,
                    passphrase=passphrase,
                    max_bytes=resolved.backup_max_bytes,
                )
                _rebind_runtime(state, resolved, previous=previous)
                failures = _runtime_health(
                    state,
                    resolved,
                    include_maintenance=False,
                )
                if failures:
                    raise RuntimeError("Restored runtime is unhealthy: " + ", ".join(failures))
                await automation.start()
                await content_automation.start()
                discard_restore_safety(result)
                return {
                    **result,
                    "manifest_schema": int(manifest.get("schema_version") or 1),
                    "health": "ready",
                }
            except Exception as exc:
                # If replacement started, put the old bytes back, then rebuild
                # the service graph from them before allowing another request.
                try:
                    _close_runtime(state)
                except Exception:
                    pass
                if result is not None:
                    await asyncio.to_thread(
                        rollback_restored_backup,
                        result,
                        database_path=resolved.database_path,
                        data_dir=resolved.data_dir,
                    )
                try:
                    _rebind_runtime(state, resolved, previous=previous)
                    await automation.start()
                    await content_automation.start()
                except Exception as recovery_exc:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Restore failed and automatic rollback could not return the runtime to health: "
                            + str(recovery_exc)[:500]
                        ),
                    ) from exc
                raise HTTPException(
                    status_code=422 if result is None else 500,
                    detail="Restore failed; the previous workspace was recovered: " + str(exc)[:500],
                ) from exc
            finally:
                await gate.end_maintenance()

        return app

    create_app.__name__ = getattr(original_create_app, "__name__", "create_app")
    create_app.__doc__ = original_create_app.__doc__
    return create_app
