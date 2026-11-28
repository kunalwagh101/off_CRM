"""Bounded, secret-safe diagnostics for enabled in-process schedulers.

Separate from /health/ready, which answers whether the web API can serve
requests. This endpoint reports *operator intervention needed* without causing
a load balancer to restart an otherwise healthy web process.
"""
from __future__ import annotations

from typing import Any

from ..outreach.models import parse_datetime, to_utc_iso, utc_now

from ..observability import report_failure


def _check_scheduler(name: str, service: Any) -> dict[str, str]:
    try:
        config = service.config()
        enabled = config.get("enabled")
        if type(enabled) is not bool:
            raise ValueError("Scheduler enabled configuration is not a boolean")
        if not enabled:
            return {"name": name, "state": "disabled", "code": "not_configured"}
        if service.last_error:
            return {"name": name, "state": "degraded", "code": "scheduler_error"}
        task = getattr(service, "_task", None)
        if task is None or task.done():
            return {"name": name, "state": "degraded", "code": "scheduler_not_running"}
        return {"name": name, "state": "healthy", "code": "running"}
    except Exception as exc:
        # Log the details through the secret-safe failure reporter, and return
        # the exact reference. Never serialize exception text into this API.
        reference = report_failure(exc, operation="health.operational.scheduler")
        return {"name": name, "state": "unknown",
                "code": "inspection_failed", "error_id": reference}


def _check_routines(state: Any) -> dict[str, str]:
    try:
        # Query every workspace, never assume only the install owner's routines
        # count. The store uses SQLite and includes a busy timeout.
        with state.agent_routine_store.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM agent_routines WHERE enabled = 1"
            ).fetchone()
        enabled = int(row[0]) > 0
        if not enabled:
            return {"name": "agent_routines", "state": "disabled",
                    "code": "no_enabled_routines"}
        scheduler = state.agent_routines
        if scheduler.last_error:
            return {"name": "agent_routines", "state": "degraded",
                    "code": "scheduler_error"}
        task = getattr(scheduler, "_task", None)
        if task is None or task.done():
            return {"name": "agent_routines", "state": "degraded",
                    "code": "scheduler_not_running"}
        return {"name": "agent_routines", "state": "healthy", "code": "running"}
    except Exception as exc:
        reference = report_failure(exc, operation="health.operational.routines")
        return {"name": "agent_routines", "state": "unknown",
                "code": "inspection_failed", "error_id": reference}


# Two minutes allows twice the worker's maximum idle poll. Recent progress
# is historical evidence, not proof of liveness.
WORKER_STALE_SECONDS = 120


def _check_external_email_worker(state: Any) -> dict[str, Any]:
    name = "external_email_worker"
    try:
        now = utc_now()
        expected = state.settings.email_worker_expected
        snapshot = state.email_delivery.store.worker_progress_snapshot(now=now)
        latest = parse_datetime(snapshot["last_progress_at"])
        oldest = parse_datetime(snapshot["oldest_due_at"])
        age = (now - latest).total_seconds() if latest else None
        if age is not None and age < -5:
            raise ValueError("Worker progress timestamp is in the future")
        details = {
            "name": name, "expected": expected,
            "last_progress_at": to_utc_iso(latest) if latest else None,
            "due_queued_jobs": int(snapshot["due_jobs"]),
            "oldest_due_age_seconds": max(0, int((now - oldest).total_seconds())) if oldest else None,
            "expired_claims": int(snapshot["expired_claims"]),
        }
        if details["expired_claims"]:
            return {**details, "state": "degraded", "code": "expired_delivery_claims"}
        if age is not None and age <= WORKER_STALE_SECONDS:
            return {**details, "state": "healthy", "code": "recent_worker_progress"}
        if expected:
            return {**details, "state": "degraded",
                    "code": "worker_progress_stale" if latest else "worker_progress_missing"}
        return {**details, "state": "disabled", "code": "worker_not_required"}
    except Exception as exc:
        reference = report_failure(exc, operation="health.operational.email_worker")
        return {"name": name, "state": "unknown", "code": "inspection_failed", "error_id": reference}


def describe_operational_health(state: Any) -> dict[str, Any]:
    components = [
        _check_scheduler("automation", state.automation),
        _check_scheduler("content_automation", state.content_automation),
        _check_routines(state),
        _check_external_email_worker(state),
    ]
    degraded = any(row["state"] in {"degraded", "unknown"} for row in components)
    return {
        "status": "degraded" if degraded else "healthy",
        "alert_required": degraded,
        "components": components,
        "scope": "schedulers_and_external_worker_progress",
        "external_worker_monitoring": "shared_crm_progress",
    }
