"""Workspace maintenance, request draining and recoverable service lifecycle."""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from ..ai import EgressBroker, EgressLog, ProviderRegistry, QuotaTracker, ResponseCache
from ..ai.context import ContextLayer
from ..ai.recall import SentMailIndex
from ..ai.workspace import WorkspaceAISettingsStore
from ..db import resolve_target as resolve_database_target
from ..db.connection import is_postgres_url
from ..distribution.store import DistributionStore
from ..imagery.store import ImageStore
from ..outreach.ai_chat import AIChatService
from ..outreach.backup import create_encrypted_backup, discard_restore_safety, restore_encrypted_backup, rollback_restored_backup, validate_encrypted_backup
from ..outreach.deliverability.service import EmailDeliveryService
from ..outreach.deliverability.store import DeliverabilityStore
from ..outreach.deliverability.unsubscribe import UnsubscribeService
from ..outreach.engine import OutreachEngine
from ..outreach.notion import NotionSettingsStore
from ..outreach.provider_profiles import ProviderProfileStore
from ..outreach.sales import SalesTracker
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock
from ..video.store import VideoStore
from .schemas import BackupExport

API_PREFIX = "/api/v1"
LOG = logging.getLogger(__name__)


class RecoveryGate:
    def __init__(self):
        self._condition = asyncio.Condition()
        self._active = 0
        self.maintenance = False
        self.failed = False
        self.operation = asyncio.Lock()

    async def enter_request(self):
        async with self._condition:
            if self.maintenance or self.failed:
                return False
            self._active += 1
            return True

    async def leave_request(self):
        async with self._condition:
            self._active -= 1
            self._condition.notify_all()

    async def begin_maintenance(self):
        async with self._condition:
            if self.maintenance or self.failed:
                raise RuntimeError("Workspace recovery is already active; inspect readiness before retrying")
            self.maintenance = True
            try:
                async with asyncio.timeout(60):
                    while self._active:
                        await self._condition.wait()
            except BaseException:
                self.maintenance = False
                raise

    async def end_maintenance(self):
        async with self._condition:
            if not self.failed:
                self.maintenance = False
            self._condition.notify_all()


class RecoveryMiddleware:
    """Count full ASGI lifetimes, including streamed bodies and background tasks."""
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        state, path = scope["app"].state, scope["path"]
        gate = getattr(state, "recovery_gate", None)
        if path == f"{API_PREFIX}/backups/restore":
            # Bound the multipart body before Starlette can spool it to disk.
            total, limit = 0, self.settings.backup_max_bytes + 64 * 1024
            oversized = False
            original_receive, original_send = receive, send
            async def bounded_send(message):
                if oversized:
                    if message["type"] == "http.response.start":
                        response = JSONResponse({"detail": "Backup exceeds the configured recovery upload limit"}, status_code=413)
                        await response(scope, original_receive, original_send)
                    return
                await original_send(message)
            send = bounded_send
            async def bounded_receive():
                nonlocal total, oversized
                message = await original_receive()
                total += len(message.get("body", b""))
                if total > limit:
                    oversized = True
                    from starlette.formparsers import MultiPartException
                    raise MultiPartException("Backup exceeds the configured recovery upload limit")
                return message
            receive = bounded_receive
        exempt = path in {"/health/live", "/health/ready", f"{API_PREFIX}/backups/restore", f"{API_PREFIX}/backups/export"}
        if gate is None or exempt:
            return await self.app(scope, receive, send)
        if not await gate.enter_request():
            return await JSONResponse({"detail": "Workspace maintenance is in progress. Retry after readiness returns."}, status_code=503, headers={"Retry-After": "5"})(scope, receive, send)
        try:
            try:
                lease = WorkspaceLock(self.settings.data_dir).__enter__()
            except WorkspaceBusy:
                return await JSONResponse({"detail": "Workspace recovery is in progress. Retry shortly."}, status_code=503)(scope, receive, send)
            try:
                return await self.app(scope, receive, send)
            finally:
                lease.__exit__()
        finally:
            await gate.leave_request()


def _close(object_: Any) -> None:
    close = getattr(object_, "close", None)
    if callable(close):
        close()


def _close_runtime(state: Any) -> None:
    # Order: stop users of the outreach store before closing the store itself.
    for name in (
        "ai_cache",
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
    settings.prepare()
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
        provider_factory=getattr(old_delivery, "provider_factory", None) or state.delivery_provider_factory,
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
        credential_resolver=state.ai_workspaces.credential_resolver("local"),
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
            "ai_cache",
        "ai_egress_log",
            "image_store",
            "distribution_store",
            "video_store",
        )
    }


def _sqlite_probe(path: Path) -> None:
    if not path.is_file():
        raise OSError("Required database is missing")
    connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=1)
    try:
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"PRAGMA user_version={version}")
        connection.rollback()
    finally:
        connection.close()


def _runtime_health(state, settings, *, include_maintenance=True):
    gate = getattr(state, "recovery_gate", None)
    if include_maintenance and gate and (gate.maintenance or gate.failed):
        return ["maintenance" if not gate.failed else "recovery_failed"]
    failures = []
    try:
        settings.verify_persistent_mount()
    except ValueError:
        failures.append("persistent_mount:missing")
    stores = {"outreach_db": state.engine.store, "ai_context": state.ai_context,
              "ai_recall": state.ai_recall, "ai_egress": state.ai_egress_log,
              "imagery": state.image_store, "distribution": state.distribution_store,
              "video": state.video_store}
    for name, store in stores.items():
        try:
            store.connection.execute("SELECT 1").fetchone()
            target = getattr(store, "target", None) or getattr(store, "path", None)
            if is_postgres_url(target):
                store.connection.execute("SELECT count(*) FROM information_schema.tables").fetchone()
            else:
                _sqlite_probe(Path(target))
        except Exception as exc:
            failures.append(f"{name}:{type(exc).__name__}")
    engine_store = state.engine.store
    for name in ("sales", "ai_chat"):
        if getattr(getattr(state, name, None), "store", None) is not engine_store:
            failures.append(f"{name}_store:stale")
    delivery = state.email_delivery
    if delivery.engine is not state.engine or delivery.store.outreach is not engine_store:
        failures.append("email_delivery:stale")
    if not settings.unsubscribe_secret:
        try:
            key = (settings.data_dir / "email_unsubscribe.key").read_bytes()
            if not hmac.compare_digest(key, state.engine.unsubscribe_service.secret):
                raise ValueError("Local signing key differs from the active service")
        except (OSError, ValueError) as exc:
            failures.append(f"unsubscribe_key:{type(exc).__name__}")
    for path in (settings.data_dir, settings.export_dir, state.image_store.assets_dir,
                 state.video_store.renders_dir, state.distribution_store.outbox_dir):
        try:
            if not path.is_dir():
                raise OSError("Required durable directory is missing")
            descriptor, name = tempfile.mkstemp(prefix=".offcrm-ready-", dir=path)
            try:
                os.write(descriptor, b"ready")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
                Path(name).unlink(missing_ok=True)
        except Exception as exc:
            failures.append(f"{path.name}:{type(exc).__name__}")
    if (settings.data_dir / "trends.db").exists():
        try:
            _sqlite_probe(settings.data_dir / "trends.db")
        except Exception as exc:
            failures.append(f"trends:{type(exc).__name__}")
    return failures


async def _bounded_upload(file, limit):
    content = bytearray()
    while chunk := await file.read(min(1024 * 1024, limit - len(content) + 1)):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "Backup exceeds the configured recovery upload limit")
    return bytes(content)


async def _finish_even_if_disconnected(operation):
    task = asyncio.create_task(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Thread work cannot be cancelled. Keep the ownership until the swap,
        # health check and commit/rollback decision have actually finished.
        await task
        raise


@asynccontextmanager
async def _maintenance(state):
    gate = state.recovery_gate
    try:
        await gate.begin_maintenance()
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(409, "Workspace could not drain. Wait for active operations and retry.") from exc
    try:
        await state.automation.stop()
        await state.content_automation.stop()
        try:
            lease = WorkspaceLock(state.settings.data_dir, exclusive=True).__enter__()
        except WorkspaceBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            yield
        finally:
            lease.__exit__()
    finally:
        if not gate.failed:
            await state.automation.start()
            await state.content_automation.start()
        await gate.end_maintenance()


def _require_local_backup(state):
    if any(is_postgres_url(store.target) for store in (state.ai_egress_log, state.video_store)):
        raise HTTPException(409, "This workspace uses PostgreSQL. Use coordinated database and asset recovery; local backup cannot capture remote stores.")


async def _restore(state, content, passphrase):
    settings = state.settings
    async with _maintenance(state):
        previous = _snapshot_runtime(state)
        result = None
        try:
            _close_runtime(state)
            result = await asyncio.to_thread(restore_encrypted_backup, content,
                database_path=settings.database_path, data_dir=settings.data_dir,
                passphrase=passphrase, max_bytes=settings.backup_max_bytes)
            _rebind_runtime(state, settings, previous=previous)
            failures = _runtime_health(state, settings, include_maintenance=False)
            # The restored automation files must also be parseable before resume.
            state.automation.config()
            state.content_automation.config()
            if failures:
                raise RuntimeError("Restored services failed readiness: " + ", ".join(failures))
            await asyncio.to_thread(discard_restore_safety, result)
            LOG.info("Workspace restore committed; schema=%s entries=%s", result["schema_version"], result["entries"])
            return {key: value for key, value in result.items() if key in {"restored", "schema_version", "entries", "excluded_rebuildable", "legacy_partial"}} | {"health": "ready"}
        except Exception as exc:
            LOG.exception("Workspace restore failed; recovering the previous generation")
            try:
                _close_runtime(state)
                if result is not None:
                    await asyncio.to_thread(rollback_restored_backup, result, database_path=settings.database_path, data_dir=settings.data_dir)
                _rebind_runtime(state, settings, previous=previous)
                failures = _runtime_health(state, settings, include_maintenance=False)
                if failures:
                    raise RuntimeError(", ".join(failures))
            except Exception:
                state.recovery_gate.failed = True
                LOG.exception("Workspace rollback failed; maintenance remains active")
                raise HTTPException(503, "Recovery could not restore service health. Keep the recovery files and restart the service to retry recovery; inspect the server log.") from exc
            raise HTTPException(422, "Restore was rejected; the previous workspace is available. Check the backup's compatibility and retry.") from exc


def install_runtime_routes(app, settings):
    app.add_middleware(RecoveryMiddleware, settings=settings)

    @app.get("/health/ready")
    async def ready(request: Request):
        gate = request.app.state.recovery_gate
        if not await gate.enter_request():
            raise HTTPException(503, {"status": "not_ready", "components": ["maintenance" if not gate.failed else "recovery_failed"]})
        try:
            failures = await asyncio.to_thread(_runtime_health, request.app.state, settings)
        finally:
            await gate.leave_request()
        if failures:
            raise HTTPException(503, {"status": "not_ready", "components": failures})
        return {"status": "ready"}

    @app.post(f"{API_PREFIX}/backups/export")
    async def export(body: BackupExport, request: Request):
        state, gate = request.app.state, request.app.state.recovery_gate
        _require_local_backup(state)
        if gate.operation.locked():
            raise HTTPException(409, "Another backup operation is running. Wait and retry.")
        async def operation():
            async with _maintenance(state):
                content = await asyncio.to_thread(create_encrypted_backup,
                    database_path=settings.database_path, data_dir=settings.data_dir,
                    passphrase=body.passphrase, max_bytes=settings.backup_max_bytes)
                return Response(content, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="off-crm-workspace.oxbackup"'})
        async with gate.operation:
            return await _finish_even_if_disconnected(operation())

    @app.post(f"{API_PREFIX}/backups/restore")
    async def restore(request: Request, file: UploadFile = File(...), passphrase: str = Form(..., min_length=12, max_length=500)):
        state, gate = request.app.state, request.app.state.recovery_gate
        _require_local_backup(state)
        if gate.operation.locked():
            raise HTTPException(409, "Another backup operation is running. Wait and retry.")
        async with gate.operation:
            content = await _bounded_upload(file, settings.backup_max_bytes)
            await asyncio.to_thread(validate_encrypted_backup, content, passphrase=passphrase, max_bytes=settings.backup_max_bytes)
            return await _finish_even_if_disconnected(_restore(state, content, passphrase))
