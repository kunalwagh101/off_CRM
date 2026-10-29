"""Bounded, secret-safe diagnostics for enabled in-process schedulers.

Separate from /health/ready, which answers whether the web API can serve
requests. This endpoint reports *operator intervention needed* without causing
a load balancer to restart an otherwise healthy web process.
"""
from __future__ import annotations

from typing import Any

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


def describe_operational_health(state: Any) -> dict[str, Any]:
    components = [
        _check_scheduler("automation", state.automation),
        _check_scheduler("content_automation", state.content_automation),
        _check_routines(state),
    ]
    degraded = any(row["state"] in {"degraded", "unknown"} for row in components)
    return {
        "status": "degraded" if degraded else "healthy",
        "alert_required": degraded,
        "components": components,
        # External offsetx-email-worker CLI is a separate process. No
        # heartbeat is stored yet; never claim this endpoint monitors it.
        "scope": "in_process_schedulers_only",
        "external_worker_monitoring": "not_instrumented",
    }
