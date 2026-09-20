from __future__ import annotations

import asyncio
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.routines import (
    RoutineError,
    RoutineExecution,
    RoutineService,
    RoutineStore,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _event_routine(store: RoutineStore, *, workspace: str = "local", name: str = "watch"):
    return store.create(
        workspace_id=workspace,
        name=name,
        goal="Check whether the public changelog contains a new release.",
        target_url="https://example.com/changelog",
        trigger_type="event",
        event_name="source.changed",
        step_budget=5,
    )


def test_attended_only_domain_is_refused_when_routine_is_created(tmp_path):
    store = RoutineStore(tmp_path / "routines.db")

    with pytest.raises(RoutineError, match="unattended"):
        store.create(
            workspace_id="local",
            name="bad-linkedin-routine",
            goal="Read my LinkedIn feed.",
            target_url="https://www.linkedin.com/feed/",
            trigger_type="interval",
            interval_seconds=300,
        )

    assert store.list(workspace_id="local") == []


def test_safe_schedule_is_claimed_once_across_store_instances(tmp_path):
    path = tmp_path / "routines.db"
    first = RoutineStore(path)
    second = RoutineStore(path)
    routine = first.create(
        workspace_id="local",
        name="release-watch",
        goal="Check the public release page.",
        target_url="https://example.com/releases",
        trigger_type="interval",
        interval_seconds=60,
        now=100.0,
    )

    assert first.claim_due(now=159.9) == []
    claimed = first.claim_due(now=160.0)
    assert [item.id for item in claimed] == [routine.id]

    # The second worker sees the moved next_due_at, not the same occurrence.
    assert second.claim_due(now=160.0) == []
    assert [item.id for item in second.claim_due(now=220.0)] == [routine.id]


def test_event_id_is_deduplicated_and_empty_result_never_notifies(tmp_path):
    store = RoutineStore(tmp_path / "routines.db")
    _event_routine(store)
    calls = []

    async def runner(routine, payload):
        calls.append((routine.id, dict(payload)))
        return RoutineExecution(
            status="completed",
            useful=False,
            agent_run_id="run-empty",
            summary="",
        )

    service = RoutineService(store, runner=runner)
    first = asyncio.run(
        service.emit(
            "source.changed",
            workspace_id="local",
            payload={"url": "https://example.com/changelog"},
            event_id="evt-123",
        )
    )
    replay = asyncio.run(
        service.emit(
            "source.changed",
            workspace_id="local",
            payload={"url": "https://example.com/changelog"},
            event_id="evt-123",
        )
    )

    assert len(calls) == 1
    assert first[0]["status"] == "completed"
    assert first[0]["useful"] is False
    assert first[0]["notified"] is False
    assert replay[0]["status"] == "duplicate"
    assert store.notifications(workspace_id="local") == []

    runs = store.runs(workspace_id="local")
    assert len(runs) == 1
    assert runs[0]["useful"] == 0
    assert runs[0]["status"] == "completed"


def test_useful_result_creates_one_persistent_notification(tmp_path):
    store = RoutineStore(tmp_path / "routines.db")
    routine = _event_routine(store)

    async def runner(_routine, _payload):
        return RoutineExecution(
            status="completed",
            useful=True,
            agent_run_id="agent-run-1",
            summary="Version 2.0 was released.",
        )

    service = RoutineService(store, runner=runner)
    result = asyncio.run(
        service.emit(
            "source.changed",
            workspace_id="local",
            event_id="evt-useful",
        )
    )

    assert result[0]["notified"] is True
    notifications = store.notifications(workspace_id="local")
    assert len(notifications) == 1
    assert notifications[0]["routine_id"] == routine.id
    assert notifications[0]["summary"] == "Version 2.0 was released."


def test_event_only_fires_routines_from_the_authenticated_workspace(tmp_path):
    store = RoutineStore(tmp_path / "routines.db")
    alpha = _event_routine(store, workspace="alpha", name="alpha-watch")
    _event_routine(store, workspace="beta", name="beta-watch")
    seen = []

    async def runner(routine, _payload):
        seen.append(routine.workspace_id)
        return RoutineExecution(status="completed", useful=False)

    service = RoutineService(store, runner=runner)
    result = asyncio.run(
        service.emit(
            "source.changed",
            workspace_id="alpha",
            event_id="evt-alpha",
        )
    )

    assert seen == ["alpha"]
    assert [item["routine_id"] for item in result] == [alpha.id]
    assert store.runs(workspace_id="beta") == []


def test_workspace_browser_lease_expires_after_crash_and_cannot_be_stolen_early(tmp_path):
    first = RoutineStore(tmp_path / "routines.db")
    second = RoutineStore(tmp_path / "routines.db")

    assert first.acquire_workspace_lease(
        "alpha", "worker-a", now=100.0, lease_seconds=180
    )
    assert not second.acquire_workspace_lease(
        "alpha", "worker-b", now=101.0, lease_seconds=180
    )
    # Same owner renews.
    assert first.acquire_workspace_lease(
        "alpha", "worker-a", now=150.0, lease_seconds=180
    )
    assert not second.acquire_workspace_lease(
        "alpha", "worker-b", now=329.0, lease_seconds=180
    )
    # If worker-a died, its last heartbeat expires at t=330.
    assert second.acquire_workspace_lease(
        "alpha", "worker-b", now=330.0, lease_seconds=180
    )


def test_routine_api_refuses_attended_target_before_any_fire(tmp_path):
    token = "routine-admin-token-" + "z" * 32
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=token,
        allowed_hosts=("testserver",),
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/agent-routines",
            headers={"X-Offsetx-Token": token},
            json={
                "name": "unattended-linkedin",
                "goal": "Read my feed.",
                "target_url": "https://www.linkedin.com/feed/",
                "trigger_type": "interval",
                "interval_seconds": 300,
            },
        )
        assert response.status_code == 400
        assert "unattended" in response.json()["detail"].lower()

        listed = client.get(
            "/api/v1/agent-routines",
            headers={"X-Offsetx-Token": token},
        )
        assert listed.status_code == 200
        assert listed.json()["items"] == []


def test_event_api_records_no_notification_when_runner_found_nothing(tmp_path):
    token = "routine-event-token-" + "q" * 32
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=token,
        allowed_hosts=("testserver",),
    )

    with TestClient(create_app(settings)) as client:
        headers = {"X-Offsetx-Token": token}
        created = client.post(
            "/api/v1/agent-routines",
            headers=headers,
            json={
                "name": "public-event-watch",
                "goal": "Check the public changelog.",
                "target_url": "https://example.com/changelog",
                "trigger_type": "event",
                "event_name": "source.changed",
            },
        )
        assert created.status_code == 201

        calls = []

        async def empty_runner(routine, payload):
            calls.append((routine.id, payload))
            return RoutineExecution(
                status="completed",
                useful=False,
                agent_run_id="run-empty",
            )

        client.app.state.agent_routines.runner = empty_runner
        fired = client.post(
            "/api/v1/agent-routines/events/source.changed",
            headers=headers,
            json={"event_id": "evt-api-1", "payload": {"kind": "test"}},
        )
        assert fired.status_code == 200
        assert fired.json()["results"][0]["notified"] is False
        assert len(calls) == 1

        notifications = client.get(
            "/api/v1/agent-routine-notifications",
            headers=headers,
        )
        assert notifications.status_code == 200
        assert notifications.json()["items"] == []



def test_plain_no_updates_prose_cannot_become_a_notification():
    outcome = SimpleNamespace(
        status="completed",
        run_id="run-none",
        result="No updates found.",
        message="Goal completed.",
        record={},
        findings={},
        to_dict=lambda: {"status": "completed", "result": "No updates found."},
    )

    execution = RoutineExecution.from_agent_outcome(outcome)

    assert execution.useful is False
    assert execution.summary == ""


def test_verified_notification_field_is_the_only_real_run_output_that_notifies():
    outcome = SimpleNamespace(
        status="completed",
        run_id="run-useful",
        result="Model prose is not trusted for notification.",
        message="Goal completed.",
        record={"notification": "Version 2.0 is now public."},
        findings={"notification": object()},
        to_dict=lambda: {"status": "completed"},
    )

    execution = RoutineExecution.from_agent_outcome(outcome)

    assert execution.useful is True
    assert execution.summary == "Version 2.0 is now public."
