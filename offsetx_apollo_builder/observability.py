"""Bounded failure records, without exception messages, arguments or locals.

A traceback's source line or exception text can contain a customer's prompt
or credentials. Record frame locations and exception types instead. The error
reference joins the safe record to what the user saw.
"""
from __future__ import annotations

import contextvars
import functools
import inspect
import json
import os
import re
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .data_paths import data_dir as default_data_dir
from .db.connection import DatabaseError

_LOCK = threading.RLock()
_PACKAGE = Path(__file__).resolve().parent
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,95}\Z")
_REFERENCE = re.compile(r"E-[A-F0-9]{24}\Z")
_WORKSPACE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_REPORTER: contextvars.ContextVar[FailureReporter | None] = contextvars.ContextVar(
    "offcrm_failure_reporter", default=None
)
_BOUNDARY: contextvars.ContextVar[dict | None] = contextvars.ContextVar("offcrm_failure_boundary", default=None)
_REQUEST: contextvars.ContextVar[dict | None] = contextvars.ContextVar("offcrm_failure_request", default=None)


def request_route(scope: dict) -> str:
    declared = getattr(scope.get("route"), "path", None)
    if declared:
        return declared
    from starlette.routing import Match
    for candidate in getattr(scope.get("app"), "routes", ()):
        matched, _ = candidate.matches(scope)
        if matched == Match.FULL:
            return getattr(candidate, "path", "unmatched")
    return "unmatched"


def reported_reference(exc: BaseException | None) -> str:
    boundary = _BOUNDARY.get()
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ReportedFailure):
            return exc.reference if _REFERENCE.fullmatch(exc.reference) else ""
        if boundary is not None:
            reference = boundary.get(id(exc), "")
            propagated = getattr(exc, "_offcrm_failure", None)
            if not reference and propagated and propagated[0] is boundary.get("token"):
                reference = propagated[1]
            if isinstance(reference, str) and _REFERENCE.fullmatch(reference):
                return reference
        exc = exc.__cause__
    return ""


@contextmanager
def failure_scope():
    """Release handled failures after each cycle; transfer only escaping IDs."""
    parent = _BOUNDARY.get()
    marker = _BOUNDARY.set({"token": object()})
    try:
        yield
    except BaseException as exc:
        reference = reported_reference(exc)
        if reference and parent is not None:
            exc._offcrm_failure = (parent.get("token"), reference)
        raise
    finally:
        _BOUNDARY.reset(marker)


def _identifier(value: str, default: str = "") -> str:
    return value if _IDENTIFIER.fullmatch(value) else default


class ReportedFailure(RuntimeError):
    """An already recorded failure crossing another execution boundary."""
    def __init__(self, reference: str) -> None:
        super().__init__(f"The operation failed. Reference: {reference}")
        self.reference = reference


def _traceback(exc: BaseException | None) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen and len(seen) < 8:
        seen.add(id(exc))
        frames.append({"exception": _identifier(type(exc).__name__, "Exception")})
        trace = exc.__traceback__
        while trace is not None and len(frames) < 32:
            code = trace.tb_frame.f_code
            try:
                location = str(Path(code.co_filename).resolve().relative_to(_PACKAGE))
            except ValueError:
                location = "external"
            frames.append({
                "file": location, "line": trace.tb_lineno,
                "function": _identifier(code.co_name, "function"),
            })
            trace = trace.tb_next
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    return frames


class FailureReporter:
    def __init__(
        self, data_dir: Path | str | None = None, *, hosted: bool | None = None,
        max_bytes: int = 1024 * 1024, backup_count: int = 3,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir(Path.cwd())
        self.hosted = bool(os.getenv("RENDER")) if hosted is None else hosted
        if max_bytes < 1024 or not 1 <= backup_count <= 10:
            raise ValueError("Log size must be at least 1024 bytes with 1 to 10 retained files.")
        self.max_bytes, self.backup_count = max_bytes, backup_count
        self.last_reference = ""

    def _write(self, record: dict[str, Any]) -> None:
        # The record contains only allowed metadata. Never redact serialized
        # JSON: a short password can match an ID, key or even its delimiters.
        line = json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
        with _LOCK:
            workspace_lease = rotation_lease = None
            try:
                if not self.hosted:
                    from .outreach.backup import restore_pending
                    from .outreach.workspace_lock import WorkspaceLock
                    workspace_lease = WorkspaceLock(self.data_dir)
                    workspace_lease.__enter__()
                    if restore_pending(self.data_dir):
                        raise OSError("Recovery is pending")
                    folder = self.data_dir / "logs"
                    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                    rotation_lease = WorkspaceLock(folder / "failures", exclusive=True, wait_seconds=1)
                    rotation_lease.__enter__()
                    path = folder / "failures.jsonl"
                    encoded = line.encode("utf-8")
                    if len(encoded) <= self.max_bytes:
                        if path.exists() and path.stat().st_size + len(encoded) > self.max_bytes:
                            for number in range(self.backup_count, 0, -1):
                                source = path if number == 1 else folder / f"failures.jsonl.{number - 1}"
                                destination = folder / f"failures.jsonl.{number}"
                                if source.exists():
                                    os.replace(source, destination)
                        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
                        try:
                            view = memoryview(encoded)
                            while view:
                                written = os.write(fd, view)
                                if not written:
                                    raise OSError("Log write made no progress")
                                view = view[written:]
                        finally:
                            os.close(fd)
            except (OSError, ValueError, RuntimeError):
                # The stdout sink remains available when a local disk is full.
                pass
            finally:
                if rotation_lease is not None and rotation_lease.fd is not None:
                    rotation_lease.__exit__(None, None, None)
                if workspace_lease is not None and workspace_lease.fd is not None:
                    workspace_lease.__exit__(None, None, None)
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except (OSError, ValueError):
                # Failure of both sinks cannot be repaired by another log call.
                pass

    def failure(
        self, exc: BaseException | None, *, operation: str,
        route: str = "", workspace: str = "", error_id: str = "",
    ) -> str:
        with _LOCK:
            previous = reported_reference(exc)
            boundary = _BOUNDARY.get()
            if previous:
                self.last_reference = previous
                return previous
            request = _REQUEST.get()
            if request is not None:
                route = route or request_route(request)
                workspace = workspace or request.get("state", {}).get("caller_workspace", "")
            elif not workspace:
                workspace = "local"
            reference = error_id if _REFERENCE.fullmatch(error_id) else f"E-{uuid.uuid4().hex[:24].upper()}"
            record = {
                "event": "failure", "time": datetime.now(timezone.utc).isoformat(),
                "error_id": reference, "operation": _identifier(operation, "operation"),
                "route": route, "workspace": workspace if _WORKSPACE.fullmatch(workspace) else "",
                "exception": _identifier(type(exc).__name__, "Exception") if exc else "HTTPFailure",
                "traceback": _traceback(exc),
            }
            self._write(record)
            self.last_reference = reference
            if exc is not None and boundary is not None:
                boundary[id(exc)] = reference
                # Retain the exception to prevent object-id reuse in the cycle.
                boundary.setdefault("exceptions", []).append(exc)
            return reference

    def access(self, *, method: str, route: str, status: int, elapsed: float) -> None:
        self._write({
            "event": "access", "time": datetime.now(timezone.utc).isoformat(),
            "method": _identifier(method, "HTTP"), "route": route,
            "status": status, "elapsed_ms": round(elapsed * 1000, 2),
        })


def report_failure(
    exc: BaseException | None, *, operation: str, data_dir: Path | str | None = None,
    workspace: str = "",
) -> str:
    active = _REPORTER.get()
    reporter = active or FailureReporter(data_dir)
    if data_dir is not None and Path(data_dir) != reporter.data_dir:
        reporter = FailureReporter(data_dir)
    reference = reporter.failure(exc, operation=operation, workspace=workspace)
    if active is not None:
        active.last_reference = reference
    return reference


def failure_message(
    exc: BaseException, *, operation: str, data_dir: Path | str | None = None,
    workspace: str = "",
) -> str:
    reference = report_failure(exc, operation=operation, data_dir=data_dir, workspace=workspace)
    # Exact fixed reasons can retain useful advice without echoing any free text.
    reason = "The provider quota was exceeded." if exc.args == ("quota exceeded",) else "The operation failed."
    if operation == "offsetx-artifacts" and str(exc).startswith("No agent trace at "):
        reason = "No agent trace was found. Pass --run-dir pointing at a verified run directory."
    if isinstance(exc, DatabaseError):
        if str(exc).startswith("Could not connect"):
            reason = "Could not connect to the database. Check its availability and connection settings."
        elif "must be a SQLite file path or a postgresql:// URL" in str(exc):
            reason = "The database target must be a SQLite file path or a postgresql:// URL."
    from .db.hosted import HostedStorageError
    if isinstance(exc, HostedStorageError):
        # These commands are fixed operator choices, never interpolate a path
        # or provider response from the original exception.
        reason = ("Hosted storage needs an owner decision. Review the local data; use "
                  "offsetx-db import-crm --yes to import the CRM or offsetx-db import-crm --skip "
                  "to leave it aside. For settings use offsetx-db import-local --yes or "
                  "offsetx-db import-local --skip.")
        if str(exc).startswith("The database was already told"):
            reason = "The database was already told what to do with local data; nothing was changed."
    from .outreach.store_copy import CrmCopyError
    if isinstance(exc, CrmCopyError):
        if "do not reconcile" in str(exc):
            reason = "The copy's counts do not reconcile. Keep the source and investigate before retrying."
        elif "already holds" in str(exc):
            reason = ("The destination already holds a CRM. Check whether it is the earlier copy; "
                      "use offsetx-db import-crm --skip only after confirming its data.")
    return f"{reason} Check the settings; quote this reference to the install owner if it persists. Reference: {reference}"


def failure_summary(results: Any) -> str:
    """Expose inner-job references without echoing arbitrary result content."""
    references: set[str] = set()
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"error", "detail", "details", "reason", "failed", "warnings", "results"}:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str):
            references.update(re.findall(r"\bE-[A-F0-9]{24}\b", value))
    collect(results)
    if not references:
        return ""
    return ("Some operations could not finish. Review the settings and failed items before retrying; "
            "quote these references to the install owner: " + ", ".join(sorted(references)))


def traced_command(command: str) -> Callable:
    """Cover unexpected exits without changing a command's existing exit code."""
    def decorate(main: Callable) -> Callable:
        @functools.wraps(main)
        def run(*args: Any, **kwargs: Any) -> int:
            reporter = FailureReporter()
            marker = _REPORTER.set(reporter)
            boundary_marker = _BOUNDARY.set({"token": object()})
            try:
                result = main(*args, **kwargs)
                if result and result != 130:
                    # A handled refusal may return nonzero without raising.
                    if reporter.last_reference:
                        print(f"The command failed. Reference: {reporter.last_reference}", file=sys.stderr)
                    else:
                        print(failure_message(RuntimeError(), operation=command), file=sys.stderr)
                return result
            except SystemExit as exc:
                if exc.code not in (0, None, 130):
                    print(failure_message(exc, operation=command), file=sys.stderr)
                raise
            except Exception as exc:
                print(failure_message(exc, operation=command), file=sys.stderr)
                return 1
            finally:
                _REPORTER.reset(marker)
                _BOUNDARY.reset(boundary_marker)
        return run
    return decorate


def failure_boundary(main: Callable) -> Callable:
    """Deduplicate propagation within a cycle, never across separate cycles."""
    if inspect.iscoroutinefunction(main):
        @functools.wraps(main)
        async def async_run(*args: Any, **kwargs: Any) -> Any:
            with failure_scope():
                try:
                    return await main(*args, **kwargs)
                except Exception as exc:
                    workspace = getattr(args[1], "workspace_id", "") if len(args) > 1 else ""
                    report_failure(exc, operation=main.__name__, workspace=workspace)
                    raise
        return async_run
    @functools.wraps(main)
    def run(*args: Any, **kwargs: Any) -> Any:
        with failure_scope():
            try:
                return main(*args, **kwargs)
            except Exception as exc:
                data_root = getattr(args[0], "path", None) if args else None
                owner = args[0] if args else None
                workspace = getattr(owner, "workspace_id", "") or getattr(getattr(owner, "engine", None), "workspace_id", "")
                report_failure(exc, operation=main.__name__, workspace=workspace,
                               data_dir=data_root.parent if isinstance(data_root, Path) else None)
                raise
    return run


class FailureMiddleware:
    """ASGI boundary covers both security middleware and endpoint failures.

    Only 5xx bodies are buffered (bounded); streaming successful bodies pass
    through untouched. A post-header failure is logged with the request ID
    already sent to the client and is never retried or replaced by fake success.
    """
    def __init__(self, app: Any, *, reporter: FailureReporter) -> None:
        self.app, self.reporter = app, reporter

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        marker = _REPORTER.set(self.reporter)
        boundary_marker = _BOUNDARY.set({"token": object()})
        request_marker = _REQUEST.set(scope if scope["type"] == "http" else None)
        if scope["type"] != "http":
            _BOUNDARY.reset(boundary_marker)
            boundary_marker = _BOUNDARY.set(None)
            failed_event = None
            async def lifecycle_send(message: dict) -> None:
                nonlocal failed_event
                if message["type"] in {"lifespan.startup.failed", "lifespan.shutdown.failed"}:
                    # Starlette sends a formatted traceback before re-raising.
                    # Hold it until the exception is classified, never forward it.
                    failed_event = message["type"]
                else:
                    await send(message)
            try:
                await self.app(scope, receive, lifecycle_send)
                if failed_event:
                    reference = report_failure(None, operation="application.lifecycle")
                    await send({"type": failed_event, "message": str(ReportedFailure(reference))})
            except Exception as exc:
                reference = report_failure(exc, operation="application.lifecycle")
                if failed_event:
                    await send({"type": failed_event, "message": str(ReportedFailure(reference))})
                from .outreach.workspace_lock import WorkspaceBusy
                if isinstance(exc, WorkspaceBusy):
                    # A fixed operator instruction, and part of the recovery
                    # startup contract; do not turn a lease refusal into a bug.
                    raise
                raise ReportedFailure(reference) from None
            finally:
                _REPORTER.reset(marker)
                _BOUNDARY.reset(boundary_marker)
                _REQUEST.reset(request_marker)
            return
        reference = f"E-{uuid.uuid4().hex[:24].upper()}"
        started = False
        status = 500
        start: dict | None = None
        body = bytearray()
        begin = time.monotonic()

        def route() -> str:
            # The unmatched raw path and query are attacker-controlled data.
            return request_route(scope)

        async def failure_response(exc: BaseException | None = None) -> None:
            nonlocal started
            reference_id = self.reporter.failure(
                exc or scope.get("state", {}).get("failure_exception"),
                operation="http.request", route=route(),
                workspace=scope.get("state", {}).get("caller_workspace", ""), error_id=reference,
            )
            reason = scope.get("state", {}).get("public_failure_detail") or "The request could not finish. Check the settings; contact the install owner if it persists."
            detail = f"{reason} Reference: {reference_id}"
            payload: dict[str, Any] = {"detail": detail, "error_id": reference_id}
            if scope.get("state", {}).get("safe_failure_response"):
                try:
                    payload = json.loads(body)
                    if isinstance(payload.get("detail"), dict):
                        payload["detail"]["message"] = detail
                    else:
                        payload["detail"] = detail
                    payload["error_id"] = reference_id
                    if "message" in payload:
                        payload["message"] = detail
                except (ValueError, AttributeError, TypeError):
                    payload = {"detail": detail, "error_id": reference_id}
            content = json.dumps(payload).encode("utf-8")
            headers = [(key, value) for key, value in (start or {}).get("headers", [])
                       if key.lower() not in {b"content-length", b"content-type", b"x-error-id", b"x-request-id"}]
            headers.extend([(b"content-type", b"application/json"),
                            (b"content-length", str(len(content)).encode()),
                            (b"x-error-id", reference_id.encode()), (b"x-request-id", reference.encode())])
            started = True
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": content})

        async def capture(message: dict) -> None:
            nonlocal start, status, started
            if message["type"] == "http.response.start":
                start, status = message, message["status"]
                if status < 500:
                    started = True
                    message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", reference.encode())]}
                    await send(message)
            elif message["type"] == "http.response.body" and status >= 500:
                if len(body) < 65536:
                    body.extend(message.get("body", b"")[:65536 - len(body)])
                if not message.get("more_body", False):
                    await failure_response()
            else:
                await send(message)

        try:
            await self.app(scope, receive, capture)
            if status < 500:
                self.reporter.access(method=scope.get("method", "HTTP"), route=route(),
                                     status=status, elapsed=time.monotonic() - begin)
        except Exception as exc:
            if started:
                stream_reference = self.reporter.failure(exc, operation="http.stream", route=route(), error_id=reference)
                raise ReportedFailure(stream_reference) from None
            status = 500
            await failure_response(exc)
        finally:
            _REPORTER.reset(marker)
            _BOUNDARY.reset(boundary_marker)
            _REQUEST.reset(request_marker)
