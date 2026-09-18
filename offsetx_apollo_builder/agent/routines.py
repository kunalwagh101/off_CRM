"""Durable schedule/event triggers for bounded browser-agent runs.

S-06.01.04 owns *when* an AgentRun starts, not how a browser agent works.
The executor is injected so there remains exactly one execution engine:
AgentRun. This module persists trigger state, validates unattended safety at
creation time, deduplicates event deliveries, prevents overlapping executions,
and notifies only when a run produced something useful or needs attention.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from ..ai.workspace import atomic_json
from ..browser.policy import Refused, check_navigation

EVENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 31 * 24 * 60 * 60
MAX_EVENT_RECEIPTS = 500
ATTENTION_STATUSES = frozenset(
    {
        "error",
        "needs_human",
        "human_gate",
        "over_budget",
        "over_latency",
        "stuck",
        "looping",
        "stalled",
        "budget_exhausted",
        "incomplete",
    }
)


class RoutineError(ValueError):
    """A routine definition or trigger was refused before execution."""


@dataclass(frozen=True, slots=True)
class Routine:
    id: str
    name: str
    goal: str
    start_url: str
    trigger: str
    interval_seconds: int = 0
    event_name: str = ""
    enabled: bool = True
    step_budget: int = 10
    result_schema: tuple[str, ...] = ()
    spend_ceiling_usd: float = 0.0
    latency_ceiling_ms: int = 0
    created_at: str = ""
    updated_at: str = ""
    next_run_at: float = 0.0
    last_run_at: str = ""
    last_status: str = ""
    last_error: str = ""
    run_count: int = 0
    notify_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["result_schema"] = list(self.result_schema)
        payload["next_run_at_iso"] = (
            datetime.fromtimestamp(self.next_run_at, tz=timezone.utc).isoformat()
            if self.next_run_at
            else ""
        )
        return payload


@dataclass(frozen=True, slots=True)
class Trigger:
    kind: str
    fired_at: str
    event_name: str = ""
    event_id: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)


RoutineExecutor = Callable[[Routine, Trigger], Any]
RoutineNotifier = Callable[[Routine, Mapping[str, Any], Trigger], Any]


class AgentRunRoutineExecutor:
    """Adapt a routine to the existing AgentRun execution contract.

    `run_factory` owns browser/session/trace construction and returns an
    AgentRun instance. This adapter owns only the routine-specific inputs.
    """

    def __init__(self, run_factory: Callable[[Routine, Trigger], Any]) -> None:
        self.run_factory = run_factory

    async def __call__(self, routine: Routine, trigger: Trigger) -> Mapping[str, Any]:
        agent = self.run_factory(routine, trigger)
        if inspect.isawaitable(agent):
            agent = await agent
        page = getattr(agent, "page", None)
        if page is None or not hasattr(page, "goto"):
            raise RoutineError("Routine run factory did not return an AgentRun with a Page")
        await page.goto(routine.start_url)
        outcome = await agent.run(
            routine.goal,
            step_budget=routine.step_budget,
            result_schema=routine.result_schema or None,
            spend_ceiling_usd=routine.spend_ceiling_usd,
            latency_ceiling_ms=routine.latency_ceiling_ms,
        )
        if hasattr(outcome, "to_dict") and callable(outcome.to_dict):
            return outcome.to_dict()
        return dict(outcome or {})


def _now_iso(now: float | None = None) -> str:
    stamp = time.time() if now is None else float(now)
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()


def _clean_text(value: object, *, label: str, max_length: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise RoutineError(f"{label} is required")
    if len(text) > max_length:
        raise RoutineError(f"{label} must be at most {max_length} characters")
    return text


def _validate_definition(
    *,
    name: object,
    goal: object,
    start_url: object,
    trigger: object,
    interval_seconds: object = 0,
    event_name: object = "",
    step_budget: object = 10,
    result_schema: object = (),
    spend_ceiling_usd: object = 0.0,
    latency_ceiling_ms: object = 0,
) -> dict[str, Any]:
    cleaned_name = _clean_text(name, label="Routine name", max_length=160)
    cleaned_goal = _clean_text(goal, label="Routine goal", max_length=4_000)
    cleaned_url = _clean_text(start_url, label="Routine start URL", max_length=2_000)

    # This is the acceptance boundary: the exact browser policy used during a
    # run is applied *before persistence*. An attended-only target never becomes
    # a routine somebody can accidentally fire at 03:00.
    try:
        check_navigation(cleaned_url, unattended=True)
    except Refused as exc:
        raise RoutineError(str(exc)) from exc

    trigger_kind = str(trigger or "").strip().lower()
    if trigger_kind not in {"schedule", "event"}:
        raise RoutineError("Routine trigger must be 'schedule' or 'event'")

    interval = 0
    event = ""
    if trigger_kind == "schedule":
        if isinstance(interval_seconds, bool):
            raise RoutineError("Scheduled routine interval must be an integer")
        try:
            interval = int(interval_seconds)
        except (TypeError, ValueError) as exc:
            raise RoutineError("Scheduled routine interval must be an integer") from exc
        if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
            raise RoutineError(
                f"Scheduled routine interval must be between {MIN_INTERVAL_SECONDS} "
                f"and {MAX_INTERVAL_SECONDS} seconds"
            )
    else:
        event = str(event_name or "").strip()
        if not EVENT_NAME.fullmatch(event):
            raise RoutineError(
                "Event name must start with a letter or digit and contain only "
                "letters, digits, dot, dash, underscore or colon"
            )

    if isinstance(step_budget, bool):
        raise RoutineError("Step budget must be an integer")
    try:
        budget = int(step_budget)
    except (TypeError, ValueError) as exc:
        raise RoutineError("Step budget must be an integer") from exc
    if not 1 <= budget <= 50:
        raise RoutineError("Step budget must be between 1 and 50")

    try:
        spend = float(spend_ceiling_usd)
    except (TypeError, ValueError) as exc:
        raise RoutineError("Spend ceiling must be a non-negative number") from exc
    if spend < 0:
        raise RoutineError("Spend ceiling must be a non-negative number")

    if isinstance(latency_ceiling_ms, bool):
        raise RoutineError("Latency ceiling must be a non-negative integer")
    try:
        latency = int(latency_ceiling_ms)
    except (TypeError, ValueError) as exc:
        raise RoutineError("Latency ceiling must be a non-negative integer") from exc
    if latency < 0:
        raise RoutineError("Latency ceiling must be a non-negative integer")

    if isinstance(result_schema, str):
        fields = (result_schema.strip(),) if result_schema.strip() else ()
    else:
        try:
            fields = tuple(
                str(item).strip() for item in (result_schema or ()) if str(item).strip()
            )
        except TypeError as exc:
            raise RoutineError("Result schema must be a list of field names") from exc
    if len(fields) != len(set(fields)):
        raise RoutineError("Result schema field names must be unique")
    if len(fields) > 100:
        raise RoutineError("Result schema may contain at most 100 fields")

    return {
        "name": cleaned_name,
        "goal": cleaned_goal,
        "start_url": cleaned_url,
        "trigger": trigger_kind,
        "interval_seconds": interval,
        "event_name": event,
        "step_budget": budget,
        "result_schema": fields,
        "spend_ceiling_usd": spend,
        "latency_ceiling_ms": latency,
    }


class RoutineStore:
    """Atomic durable routine definitions plus bounded event receipts."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def _document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"routines": {}, "event_receipts": []}
        try:
            import json

            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise RoutineError("Routine store is unreadable or invalid JSON")
        if not isinstance(payload, dict):
            raise RoutineError("Routine store must contain a JSON object")
        payload.setdefault("routines", {})
        payload.setdefault("event_receipts", [])
        return payload

    @staticmethod
    def _from_dict(payload: Mapping[str, Any]) -> Routine:
        return Routine(
            id=str(payload["id"]),
            name=str(payload["name"]),
            goal=str(payload["goal"]),
            start_url=str(payload["start_url"]),
            trigger=str(payload["trigger"]),
            interval_seconds=int(payload.get("interval_seconds", 0) or 0),
            event_name=str(payload.get("event_name", "")),
            enabled=bool(payload.get("enabled", True)),
            step_budget=int(payload.get("step_budget", 10) or 10),
            result_schema=tuple(str(x) for x in payload.get("result_schema", ())),
            spend_ceiling_usd=float(payload.get("spend_ceiling_usd", 0.0) or 0.0),
            latency_ceiling_ms=int(payload.get("latency_ceiling_ms", 0) or 0),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            next_run_at=float(payload.get("next_run_at", 0.0) or 0.0),
            last_run_at=str(payload.get("last_run_at", "")),
            last_status=str(payload.get("last_status", "")),
            last_error=str(payload.get("last_error", "")),
            run_count=int(payload.get("run_count", 0) or 0),
            notify_count=int(payload.get("notify_count", 0) or 0),
        )

    def list(self) -> list[Routine]:
        with self._lock:
            doc = self._document()
            return [
                self._from_dict(value)
                for _, value in sorted(doc["routines"].items())
                if isinstance(value, dict)
            ]

    def get(self, routine_id: str) -> Routine:
        with self._lock:
            payload = self._document()["routines"].get(str(routine_id))
            if not isinstance(payload, dict):
                raise KeyError(f"Routine {routine_id!r} was not found")
            return self._from_dict(payload)

    def put(self, routine: Routine) -> Routine:
        with self._lock:
            doc = self._document()
            doc["routines"][routine.id] = routine.to_dict()
            doc["routines"][routine.id].pop("next_run_at_iso", None)
            atomic_json(self.path, doc)
            return routine

    def delete(self, routine_id: str) -> None:
        with self._lock:
            doc = self._document()
            if str(routine_id) not in doc["routines"]:
                raise KeyError(f"Routine {routine_id!r} was not found")
            del doc["routines"][str(routine_id)]
            atomic_json(self.path, doc)

    def remember_event(self, event_id: str) -> bool:
        """Return False for a duplicate event delivery, durably."""
        event = str(event_id or "").strip()
        if not event:
            return True
        with self._lock:
            doc = self._document()
            receipts = [str(item) for item in doc.get("event_receipts", [])]
            if event in receipts:
                return False
            receipts.append(event)
            doc["event_receipts"] = receipts[-MAX_EVENT_RECEIPTS:]
            atomic_json(self.path, doc)
            return True


class RoutineService:
    """Schedule/event dispatcher around one injected AgentRun executor."""

    def __init__(
        self,
        store: RoutineStore,
        *,
        executor: RoutineExecutor,
        notifier: RoutineNotifier | None = None,
        clock: Callable[[], float] = time.time,
        poll_seconds: float = 5.0,
    ) -> None:
        self.store = store
        self.executor = executor
        self.notifier = notifier
        self.clock = clock
        self.poll_seconds = max(0.1, float(poll_seconds))
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._in_flight: set[str] = set()
        self._flight_lock = threading.Lock()

    def create(self, values: Mapping[str, Any]) -> Routine:
        clean = _validate_definition(**dict(values))
        now = self.clock()
        routine = Routine(
            id="routine_" + uuid.uuid4().hex,
            enabled=bool(values.get("enabled", True)),
            created_at=_now_iso(now),
            updated_at=_now_iso(now),
            next_run_at=(now + clean["interval_seconds"])
            if clean["trigger"] == "schedule"
            else 0.0,
            **clean,
        )
        return self.store.put(routine)

    def update(self, routine_id: str, values: Mapping[str, Any]) -> Routine:
        current = self.store.get(routine_id)
        merged = current.to_dict()
        merged.update(dict(values))
        clean = _validate_definition(
            name=merged["name"],
            goal=merged["goal"],
            start_url=merged["start_url"],
            trigger=merged["trigger"],
            interval_seconds=merged.get("interval_seconds", 0),
            event_name=merged.get("event_name", ""),
            step_budget=merged.get("step_budget", 10),
            result_schema=merged.get("result_schema", ()),
            spend_ceiling_usd=merged.get("spend_ceiling_usd", 0.0),
            latency_ceiling_ms=merged.get("latency_ceiling_ms", 0),
        )
        now = self.clock()
        changed_trigger = (
            clean["trigger"] != current.trigger
            or clean["interval_seconds"] != current.interval_seconds
            or clean["event_name"] != current.event_name
        )
        next_run = current.next_run_at
        if clean["trigger"] == "event":
            next_run = 0.0
        elif changed_trigger or not next_run:
            next_run = now + clean["interval_seconds"]
        updated = replace(
            current,
            enabled=bool(merged.get("enabled", True)),
            updated_at=_now_iso(now),
            next_run_at=next_run,
            **clean,
        )
        return self.store.put(updated)

    def delete(self, routine_id: str) -> None:
        self.store.delete(routine_id)

    async def fire_event(
        self,
        event_name: str,
        *,
        event_id: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        name = str(event_name or "").strip()
        if not EVENT_NAME.fullmatch(name):
            raise RoutineError("Invalid event name")
        if event_id and not self.store.remember_event(event_id):
            return []
        trigger = Trigger(
            kind="event",
            event_name=name,
            event_id=str(event_id or ""),
            fired_at=_now_iso(self.clock()),
            payload=dict(payload or {}),
        )
        matches = [
            routine
            for routine in self.store.list()
            if routine.enabled and routine.trigger == "event" and routine.event_name == name
        ]
        return [await self._run(routine, trigger) for routine in matches]

    async def run_due(self) -> list[dict[str, Any]]:
        now = self.clock()
        due = [
            routine
            for routine in self.store.list()
            if routine.enabled
            and routine.trigger == "schedule"
            and routine.next_run_at
            and routine.next_run_at <= now
        ]
        results: list[dict[str, Any]] = []
        for routine in due:
            trigger = Trigger(kind="schedule", fired_at=_now_iso(now))
            results.append(await self._run(routine, trigger))
        return results

    async def _run(self, routine: Routine, trigger: Trigger) -> dict[str, Any]:
        with self._flight_lock:
            if routine.id in self._in_flight:
                return {
                    "routine_id": routine.id,
                    "status": "already_running",
                    "notified": False,
                }
            self._in_flight.add(routine.id)

        now = self.clock()
        try:
            # Policy is intentionally re-checked at fire time as defence in
            # depth in case rules became stricter after the routine was created.
            check_navigation(routine.start_url, unattended=True)
            raw = self.executor(routine, trigger)
            if inspect.isawaitable(raw):
                raw = await raw
            result = (
                raw.to_dict()
                if hasattr(raw, "to_dict") and callable(raw.to_dict)
                else dict(raw or {})
            )
            status = str(result.get("status") or "completed")
            notified = self._should_notify(result)
            if notified and self.notifier is not None:
                notice = self.notifier(routine, result, trigger)
                if inspect.isawaitable(notice):
                    await notice
            latest = self.store.get(routine.id)
            self.store.put(
                replace(
                    latest,
                    last_run_at=_now_iso(now),
                    last_status=status,
                    last_error="",
                    run_count=latest.run_count + 1,
                    notify_count=latest.notify_count + (1 if notified else 0),
                    next_run_at=(
                        now + latest.interval_seconds
                        if latest.trigger == "schedule"
                        else 0.0
                    ),
                )
            )
            return {
                "routine_id": routine.id,
                "status": status,
                "notified": notified,
                "result": result,
            }
        except Exception as exc:
            latest = self.store.get(routine.id)
            self.store.put(
                replace(
                    latest,
                    last_run_at=_now_iso(now),
                    last_status="error",
                    last_error=str(exc)[:1000],
                    run_count=latest.run_count + 1,
                    next_run_at=(
                        now + latest.interval_seconds
                        if latest.trigger == "schedule"
                        else 0.0
                    ),
                )
            )
            result = {"status": "error", "error": str(exc)[:1000]}
            if self.notifier is not None:
                notice = self.notifier(routine, result, trigger)
                if inspect.isawaitable(notice):
                    await notice
            return {
                "routine_id": routine.id,
                "status": "error",
                "notified": self.notifier is not None,
                "result": result,
            }
        finally:
            with self._flight_lock:
                self._in_flight.discard(routine.id)

    @staticmethod
    def _should_notify(result: Mapping[str, Any]) -> bool:
        status = str(result.get("status") or "").strip().lower()
        if status in ATTENTION_STATUSES:
            return True
        if result.get("record") or result.get("findings"):
            return True
        return bool(str(result.get("result") or "").strip())

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="offcrm-agent-routines")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_due()
            except Exception:
                # Individual execution errors are persisted by _run. A store-
                # level error is retried on the next poll instead of killing the
                # scheduler task forever.
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass
