"""Workspace maintenance, request draining and recoverable service lifecycle.

`S-06.02.21` (audit WP1, findings A01–A04 and A17). Ported from
`integration/main-consolidation`, where it was built and proven; the one change
is that the list of services to close and reopen is not kept here. The app owns
that list — `open_runtime` builds every service the way startup does, and
`close_runtime` closes every one that holds a connection — so a store added to
startup is reopened after a restore without anyone remembering to add it twice.
The restore this replaced kept both lists by hand — the files to back up and
the services to reopen — and the first had already missed the newer stores,
with a stale-WAL restore that lost data (D-114).
"""
from __future__ import annotations

import asyncio
import hmac
import logging
from ..observability import report_failure
import os
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from ..db.connection import is_postgres_url
from ..outreach.backup import (
    create_encrypted_backup,
    discard_restore_safety,
    restore_encrypted_backup,
    rollback_restored_backup,
    validate_encrypted_backup,
)
from ..outreach.workspace_lock import WorkspaceBusy, WorkspaceLock
from .schemas import BackupExport

API_PREFIX = "/api/v1"
LOG = logging.getLogger(__name__)

#: `open_runtime(app, previous)` builds every service; `previous` is the state
#: being replaced, so a hook injected into it (a test's fake provider, a tuned
#: broker) can be carried across. `close_runtime(app)` closes them.
OpenRuntime = Callable[[Any, dict[str, Any]], None]
CloseRuntime = Callable[[Any], None]


class RecoveryGate:
    #: How long a backup or restore waits for requests already in flight.
    DRAIN_SECONDS = 60.0

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
                # `wait_for`, not `asyncio.timeout`: that is Python 3.11+, and on
                # the 3.10 the package supports every backup answered 500 (D-128).
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: not self._active), self.DRAIN_SECONDS
                )
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
                        response = JSONResponse(
                            {"detail": "Backup exceeds the configured recovery upload limit"},
                            status_code=413,
                        )
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
        exempt = path in {
            "/health/live",
            "/health/ready",
            f"{API_PREFIX}/backups/restore",
            f"{API_PREFIX}/backups/export",
        }
        if gate is None or exempt:
            return await self.app(scope, receive, send)
        if not await gate.enter_request():
            return await JSONResponse(
                {"detail": "Workspace maintenance is in progress. Retry after readiness returns."},
                status_code=503,
                headers={"Retry-After": "5"},
            )(scope, receive, send)
        try:
            try:
                lease = WorkspaceLock(self.settings.data_dir).__enter__()
            except WorkspaceBusy:
                return await JSONResponse(
                    {"detail": "Workspace recovery is in progress. Retry shortly."}, status_code=503
                )(scope, receive, send)
            try:
                return await self.app(scope, receive, send)
            finally:
                lease.__exit__()
        finally:
            await gate.leave_request()


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


def runtime_health(state: Any, settings: Any, *, include_maintenance: bool = True) -> list[str]:
    """Every reason the workspace is not ready; empty means ready (audit A17)."""
    gate = getattr(state, "recovery_gate", None)
    if include_maintenance and gate and (gate.maintenance or gate.failed):
        return ["maintenance" if not gate.failed else "recovery_failed"]
    failures: list[str] = []
    try:
        settings.verify_persistent_mount()
    except ValueError:
        failures.append("persistent_mount:missing")
    stores = {
        "outreach_db": state.engine.store,
        "ai_context": state.ai_context,
        "ai_recall": state.ai_recall,
        "ai_egress": state.ai_egress_log,
        "imagery": state.image_store,
        "distribution": state.distribution_store,
        "video": state.video_store,
        "gtm": state.gtm_store,
    }
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
    try:
        state.ai_tools.connection().execute("SELECT 1").fetchone()
    except Exception as exc:
        failures.append(f"ai_tools:{type(exc).__name__}")
    # The keys, AI settings and logins, when OFFSETX_DATABASE_URL holds them:
    # unreachable, no workspace can use a provider or sign in (S-06.03.02).
    hosted = getattr(state, "hosted_storage", None)
    if hosted is not None:
        try:
            hosted.probe()
        except Exception as exc:
            failures.append(f"hosted_storage:{type(exc).__name__}")
    # Services built on the CRM store must be on the live one, not a store a
    # restore closed — the shape of audit A03, reproduced on main in September.
    engine_store = state.engine.store
    for name in ("sales", "ai_chat"):
        if getattr(getattr(state, name, None), "store", None) is not engine_store:
            failures.append(f"{name}_store:stale")
    delivery = state.email_delivery
    if delivery.engine is not state.engine or delivery.store.outreach is not engine_store:
        failures.append("email_delivery:stale")
    if getattr(state.companions, "tools", None) is not state.ai_tools:
        failures.append("companions:stale")
    if not settings.unsubscribe_secret:
        try:
            key = (settings.data_dir / "email_unsubscribe.key").read_bytes()
            if not hmac.compare_digest(key, state.engine.unsubscribe_service.secret):
                raise ValueError("Local signing key differs from the active service")
        except (OSError, ValueError) as exc:
            failures.append(f"unsubscribe_key:{type(exc).__name__}")
    if settings.api_token_from_file:
        try:
            token = (settings.data_dir / settings.TOKEN_FILENAME).read_text(encoding="utf-8").strip()
            if not token.isascii() or not hmac.compare_digest(token, settings.api_token):
                raise ValueError("Local API token differs from the active service")
        except (OSError, ValueError) as exc:
            failures.append(f"local_api_token:{type(exc).__name__}")
    for path in (
        settings.data_dir,
        settings.export_dir,
        state.image_store.assets_dir,
        state.video_store.renders_dir,
        state.distribution_store.outbox_dir,
    ):
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


#: Every timer that writes to the workspace. Each is stopped before a backup or
#: a restore and started again after, on whatever object holds the name then.
TIMERS = ("automation", "content_automation", "agent_routines")


#: How long a backup or restore waits for the timers' runs in flight. Past it,
#: the operation is refused and the timers carry on (D-133).
TIMER_STOP_SECONDS = 30.0


async def _stop_timers(state) -> bool:
    """Stop every timer; False if one is still mid-run when the bound passes.

    `asyncio.wait`, not `wait_for`: cancelling a `stop()` would cancel the
    timer's own loop through the task it awaits.
    """
    stops = [asyncio.ensure_future(getattr(state, name).stop()) for name in TIMERS]
    _, pending = await asyncio.wait(stops, timeout=TIMER_STOP_SECONDS)
    return not pending


async def _start_timers(state) -> None:
    for name in TIMERS:
        await getattr(state, name).start()


@asynccontextmanager
async def _maintenance(state):
    gate = state.recovery_gate
    # The timers first, within a bound, while requests still flow. Stopped
    # after the gate closed, one long run — a routine waiting half an hour for
    # a browser lease — held every request at 503 (D-133).
    if not await _stop_timers(state):
        if not gate.failed:
            await _start_timers(state)
        raise HTTPException(
            409, "A scheduled job is still running. Wait for it to finish, then retry."
        )
    try:
        await gate.begin_maintenance()
    # On 3.10 `asyncio.TimeoutError` is not the builtin `TimeoutError` yet.
    except (RuntimeError, TimeoutError, asyncio.TimeoutError) as exc:
        if not gate.failed:
            await _start_timers(state)
        raise HTTPException(409, "Workspace could not drain. Wait for active operations and retry.") from exc
    try:
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
            await _start_timers(state)
        await gate.end_maintenance()


def _require_local_backup(state):
    # The keys, settings and logins in a hosted database are outside the data
    # folder too, whatever its address names (S-06.03.02).
    if getattr(state, "hosted_storage", None) is not None or any(
        is_postgres_url(getattr(store, "target", ""))
        for store in (state.engine.store, state.ai_egress_log, state.video_store, state.gtm_store)
    ):
        raise HTTPException(
            409,
            "This workspace uses PostgreSQL. Use coordinated database and asset recovery; "
            "local backup cannot capture remote stores.",
        )


def _rebind_runtime(state: Any, settings: Any, *, previous: dict[str, Any], reopen: Callable[[dict[str, Any]], None]) -> None:
    """Reopen every service over the workspace now on disk.

    The token file came back with the workspace, so authentication is reloaded
    from it first. Its own function, with the signature it had on the branch it
    came from, so a test can make reopening fail and watch the rollback.
    """
    settings.reload_local_api_token()
    settings.prepare()
    reopen(previous)


def _snapshot(state: Any) -> dict[str, Any]:
    return dict(vars(state).get("_state", {}))


async def _restore(app, content, passphrase, *, open_runtime: OpenRuntime, close_runtime: CloseRuntime):
    state = app.state
    settings = state.settings

    def reopen(previous: dict[str, Any]) -> None:
        open_runtime(app, previous)

    async with _maintenance(state):
        previous = _snapshot(state)
        result = None
        try:
            close_runtime(app)
            result = await asyncio.to_thread(
                restore_encrypted_backup,
                content,
                database_path=settings.database_path,
                data_dir=settings.data_dir,
                passphrase=passphrase,
                max_bytes=settings.backup_max_bytes,
            )
            _rebind_runtime(state, settings, previous=previous, reopen=reopen)
            failures = runtime_health(state, settings, include_maintenance=False)
            # The restored automation files must also be parseable before resume.
            state.automation.config()
            state.content_automation.config()
            if failures:
                raise RuntimeError("Restored services failed readiness: " + ", ".join(failures))
            await asyncio.to_thread(discard_restore_safety, result)
            LOG.info(
                "Workspace restore committed; schema=%s entries=%s",
                result["schema_version"],
                result["entries"],
            )
            kept = {"restored", "schema_version", "entries", "excluded_rebuildable", "legacy_partial"}
            return {key: value for key, value in result.items() if key in kept} | {"health": "ready"}
        except Exception as exc:
            report_failure(exc, operation="workspace.restore", data_dir=settings.data_dir)
            try:
                close_runtime(app)
                if result is not None:
                    await asyncio.to_thread(
                        rollback_restored_backup,
                        result,
                        database_path=settings.database_path,
                        data_dir=settings.data_dir,
                    )
                _rebind_runtime(state, settings, previous=previous, reopen=reopen)
                failures = runtime_health(state, settings, include_maintenance=False)
                if failures:
                    raise RuntimeError(", ".join(failures))
            except Exception as rollback_error:
                state.recovery_gate.failed = True
                report_failure(rollback_error, operation="workspace.rollback", data_dir=settings.data_dir)
                raise HTTPException(
                    503,
                    "Recovery could not restore service health. Keep the recovery files and restart "
                    "the service to retry recovery; inspect the server log.",
                ) from exc
            raise HTTPException(
                422,
                "Restore was rejected; the previous workspace is available. Check the backup's "
                "compatibility and retry.",
            ) from exc


def install_runtime_routes(
    app,
    settings,
    *,
    open_runtime: OpenRuntime,
    close_runtime: CloseRuntime,
    require_owner: Callable[[Request], None],
):
    """`require_owner` refuses anyone but the install owner. A backup is every
    workspace at once — each login, provider key, the install token and the
    key that signs every session — so being signed in is not enough (D-124)."""
    app.add_middleware(RecoveryMiddleware, settings=settings)

    @app.get("/health/ready")
    async def ready(request: Request):
        gate = request.app.state.recovery_gate
        if not await gate.enter_request():
            raise HTTPException(
                503,
                {"status": "not_ready", "components": ["maintenance" if not gate.failed else "recovery_failed"]},
            )
        try:
            failures = await asyncio.to_thread(runtime_health, request.app.state, settings)
        finally:
            await gate.leave_request()
        if failures:
            raise HTTPException(503, {"status": "not_ready", "components": failures})
        return {"status": "ready"}

    @app.post(f"{API_PREFIX}/backups/export")
    async def export(body: BackupExport, request: Request):
        require_owner(request)
        state, gate = request.app.state, request.app.state.recovery_gate
        _require_local_backup(state)
        if gate.operation.locked():
            raise HTTPException(409, "Another backup operation is running. Wait and retry.")

        async def operation():
            async with _maintenance(state):
                content = await asyncio.to_thread(
                    create_encrypted_backup,
                    database_path=settings.database_path,
                    data_dir=settings.data_dir,
                    passphrase=body.passphrase,
                    max_bytes=settings.backup_max_bytes,
                )
                return Response(
                    content,
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="off-crm-workspace.oxbackup"'},
                )

        async with gate.operation:
            return await _finish_even_if_disconnected(operation())

    @app.post(f"{API_PREFIX}/backups/restore")
    async def restore(
        request: Request,
        file: UploadFile = File(...),
        passphrase: str = Form(..., min_length=12, max_length=500),
    ):
        require_owner(request)
        state, gate = request.app.state, request.app.state.recovery_gate
        _require_local_backup(state)
        if gate.operation.locked():
            raise HTTPException(409, "Another backup operation is running. Wait and retry.")
        async with gate.operation:
            content = await _bounded_upload(file, settings.backup_max_bytes)
            await asyncio.to_thread(
                validate_encrypted_backup,
                content,
                passphrase=passphrase,
                max_bytes=settings.backup_max_bytes,
            )
            return await _finish_even_if_disconnected(
                _restore(request.app, content, passphrase, open_runtime=open_runtime, close_runtime=close_runtime)
            )
