from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from offsetx_apollo_builder.agent.routines import (
    RoutineError,
    RoutineService,
    RoutineStore,
)


class Clock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _schedule(**changes):
    payload = {
        "name": "Watch docs",
        "goal": "Check the docs page for a new release note",
        "start_url": "https://example.com/docs",
        "trigger": "schedule",
        "interval_seconds": 60,
        "step_budget": 5,
        "result_schema": ["headline"],
    }
    payload.update(changes)
    return payload


def _event(**changes):
    payload = {
        "name": "React to import",
        "goal": "Check the public source after an import completes",
        "start_url": "https://example.com/source",
        "trigger": "event",
        "event_name": "import.completed",
        "step_budget": 5,
    }
    payload.update(changes)
    return payload


def test_attended_only_target_is_refused_before_persistence(tmp_path: Path) -> None:
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=lambda routine, trigger: {"status": "completed"},
    )

    with pytest.raises(RoutineError, match="attended-only"):
        service.create(
            _schedule(
                start_url="https://www.linkedin.com/in/example",
                name="Unsafe scheduled LinkedIn",
            )
        )

    assert service.store.list() == []
    assert not (tmp_path / "routines.json").exists()


def test_schedule_fires_only_when_due_and_reschedules_from_actual_fire_time(
    tmp_path: Path,
) -> None:
    clock = Clock()
    calls = []

    async def executor(routine, trigger):
        calls.append((routine.id, trigger.kind, trigger.fired_at))
        return {
            "status": "completed",
            "result": "A new release note appeared",
            "record": {"headline": "Release 2"},
        }

    notices = []
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=executor,
        notifier=lambda routine, result, trigger: notices.append((routine.id, result["status"])),
        clock=clock,
    )
    routine = service.create(_schedule())

    assert asyncio.run(service.run_due()) == []
    clock.now = routine.next_run_at
    result = asyncio.run(service.run_due())

    assert len(result) == 1
    assert result[0]["status"] == "completed"
    assert result[0]["notified"] is True
    assert len(calls) == 1
    assert notices == [(routine.id, "completed")]

    stored = service.store.get(routine.id)
    assert stored.run_count == 1
    assert stored.notify_count == 1
    assert stored.next_run_at == clock.now + 60


def test_completed_run_that_found_nothing_does_not_notify(tmp_path: Path) -> None:
    notified = []
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=lambda routine, trigger: {
            "status": "completed",
            "result": "",
            "record": {},
            "findings": {},
        },
        notifier=lambda *args: notified.append(args),
        clock=Clock(),
    )
    routine = service.create(_event())

    result = asyncio.run(service.fire_event("import.completed", event_id="evt-1"))

    assert result[0]["notified"] is False
    assert notified == []
    assert service.store.get(routine.id).notify_count == 0


def test_attention_status_notifies_even_without_findings(tmp_path: Path) -> None:
    notified = []
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=lambda routine, trigger: {
            "status": "needs_human",
            "result": "",
            "record": {},
        },
        notifier=lambda routine, result, trigger: notified.append(
            (routine.id, result["status"], trigger.kind)
        ),
        clock=Clock(),
    )
    routine = service.create(_event())

    result = asyncio.run(service.fire_event("import.completed", event_id="evt-2"))

    assert result[0]["notified"] is True
    assert notified == [(routine.id, "needs_human", "event")]


def test_event_delivery_is_deduplicated_durably_across_service_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "routines.json"
    calls = []

    service = RoutineService(
        RoutineStore(path),
        executor=lambda routine, trigger: calls.append(trigger.event_id)
        or {"status": "completed", "result": "useful"},
        clock=Clock(),
    )
    service.create(_event())
    assert len(asyncio.run(service.fire_event("import.completed", event_id="evt-3"))) == 1

    restarted = RoutineService(
        RoutineStore(path),
        executor=lambda routine, trigger: calls.append("duplicate")
        or {"status": "completed", "result": "wrong"},
        clock=Clock(),
    )
    assert asyncio.run(
        restarted.fire_event("import.completed", event_id="evt-3")
    ) == []
    assert calls == ["evt-3"]


def test_same_routine_cannot_overlap_itself(tmp_path: Path) -> None:
    path = tmp_path / "routines.json"
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def executor(routine, trigger):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {"status": "completed", "result": "done"}

    async def scenario():
        service = RoutineService(RoutineStore(path), executor=executor, clock=Clock())
        routine = service.create(_event())
        first = asyncio.create_task(
            service.fire_event("import.completed", event_id="evt-a")
        )
        await started.wait()
        second = await service.fire_event("import.completed", event_id="evt-b")
        release.set()
        first_result = await first
        return routine, first_result, second

    routine, first_result, second = asyncio.run(scenario())

    assert first_result[0]["status"] == "completed"
    assert second == [
        {
            "routine_id": routine.id,
            "status": "already_running",
            "notified": False,
        }
    ]
    assert calls == 1


def test_update_rechecks_unattended_policy_and_keeps_old_safe_definition(
    tmp_path: Path,
) -> None:
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=lambda routine, trigger: {"status": "completed"},
        clock=Clock(),
    )
    routine = service.create(_schedule())

    with pytest.raises(RoutineError, match="attended-only"):
        service.update(
            routine.id,
            {"start_url": "https://www.instagram.com/example"},
        )

    assert service.store.get(routine.id).start_url == "https://example.com/docs"


@pytest.mark.parametrize(
    "values, message",
    [
        (_schedule(interval_seconds=59), "interval"),
        (_event(event_name="bad event"), "Event name"),
        (_schedule(step_budget=0), "Step budget"),
        (_schedule(spend_ceiling_usd=-1), "Spend ceiling"),
        (_schedule(latency_ceiling_ms=-1), "Latency ceiling"),
        (_schedule(result_schema=["a", "a"]), "unique"),
    ],
)
def test_invalid_routine_definitions_fail_before_write(
    tmp_path: Path, values: dict, message: str
) -> None:
    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=lambda routine, trigger: {"status": "completed"},
    )
    with pytest.raises(RoutineError, match=message):
        service.create(values)
    assert service.store.list() == []


def test_execution_failure_is_persisted_and_notified(tmp_path: Path) -> None:
    notified = []

    def fail(routine, trigger):
        raise RuntimeError("provider temporarily unavailable")

    service = RoutineService(
        RoutineStore(tmp_path / "routines.json"),
        executor=fail,
        notifier=lambda routine, result, trigger: notified.append(result),
        clock=Clock(),
    )
    routine = service.create(_event())

    result = asyncio.run(service.fire_event("import.completed", event_id="evt-fail"))

    assert result[0]["status"] == "error"
    stored = service.store.get(routine.id)
    assert stored.last_status == "error"
    assert "provider temporarily unavailable" in stored.last_error
    assert notified[0]["status"] == "error"
