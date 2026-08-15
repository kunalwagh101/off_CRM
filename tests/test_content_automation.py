"""The timer that turns the content parts into an engine.

Every piece of the pipeline worked before this and none of them ran on their
own. That is the whole subject: a campaign that only advances when somebody
presses a button is a set of buttons.

Three properties are protected here, and they are the ones that matter when
nobody is watching:

**Nothing undeclared runs.** The pipeline needs two campaigns at once and the
schema does not say which pairs with which. Guessing would post from the wrong
brand, so a half-declared pair is dropped and enabling with none declared is
refused outright.

**A failing step does not cost the cycle.** A quota error at the sweep must not
stop posts a person already approved from going out.

**The human gates stay shut.** This service drives the machine either side of
the swipe and the approval and stops at both.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from offsetx_apollo_builder.distribution.automation import (
    DEFAULT_CONTENT_AUTOMATION,
    STEPS,
    ContentAutomationService,
)

PAIR = {
    "distribution_campaign_id": "dist-1",
    "image_campaign_id": "img-1",
    "angle": "we move freight",
    "account_ids": ["acct-1"],
}


class _Result:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class _Watcher:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[int] = []
        self.closed = False

    def sweep(self, *, per_channel: int = 10):
        self.calls.append(per_channel)
        if self.fail:
            raise RuntimeError("quota exceeded")
        return _Result(
            {"channels_swept": 4, "videos_seen": 120, "videos_new": 9, "units_spent": 5, "skipped": []}
        )

    def close(self):
        self.closed = True


class _Pipeline:
    def __init__(self, *, fail_plan: bool = False, fail_draft: bool = False):
        self.fail_plan = fail_plan
        self.fail_draft = fail_draft
        self.planned: list[dict[str, Any]] = []
        self.drafted: list[dict[str, Any]] = []

    def plan(self, **kwargs):
        self.planned.append(kwargs)
        if self.fail_plan:
            raise RuntimeError("no topics service")
        return _Result(
            {"topics_found": 3, "topics_planned": 2, "topics_skipped": 1, "candidates": 6, "planned": []}
        )

    def draft(self, **kwargs):
        self.drafted.append(kwargs)
        if self.fail_draft:
            raise RuntimeError("no writer")
        return _Result(
            {"assets_considered": 5, "posts_created": 2, "posts": [], "skipped": [{"why": "no account"}]}
        )


class _Distribution:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def publish_due(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("outbox unwritable")
        return _Result({"published": 2, "failed": 0, "skipped": 1, "details": []})


@pytest.fixture()
def parts():
    return {"watcher": _Watcher(), "pipeline": _Pipeline(), "distribution": _Distribution()}


@pytest.fixture()
def service(tmp_path: Path, parts):
    return ContentAutomationService(
        tmp_path / "content_automation.json",
        trends_factory=lambda: parts["watcher"],
        pipeline_factory=lambda angle: parts["pipeline"],
        distribution_factory=lambda: parts["distribution"],
    )


def steps_of(results: list[dict[str, Any]]) -> list[str]:
    return [row["step"] for row in results]


# ── configuration ───────────────────────────────────────────────────────────


def test_it_is_off_and_declares_nothing_until_told_otherwise(service):
    """The correct default for a machine that posts under your name."""
    config = service.config()
    assert config["enabled"] is False
    assert config["pipelines"] == []


def test_enabling_with_nothing_declared_is_refused(service):
    with pytest.raises(ValueError, match="Nothing is declared to run"):
        service.update({"enabled": True})


def test_a_half_declared_pair_is_dropped_rather_than_guessed_at(service):
    """Running it would mean inventing the missing campaign."""
    saved = service.update(
        {
            "pipelines": [
                {"distribution_campaign_id": "dist-1"},
                {"image_campaign_id": "img-1"},
                PAIR,
            ]
        }
    )
    assert len(saved["pipelines"]) == 1
    assert saved["pipelines"][0]["distribution_campaign_id"] == "dist-1"


def test_settings_survive_a_restart(service, tmp_path, parts):
    service.update({"pipelines": [PAIR], "enabled": True, "interval_seconds": 900})
    again = ContentAutomationService(
        tmp_path / "content_automation.json",
        trends_factory=lambda: parts["watcher"],
        pipeline_factory=lambda angle: parts["pipeline"],
        distribution_factory=lambda: parts["distribution"],
    )
    config = again.config()
    assert config["enabled"] is True
    assert config["interval_seconds"] == 900
    assert config["pipelines"] == [PAIR]


def test_a_corrupt_settings_file_starts_nothing(service):
    """Half-parsed values must not start an unattended poster."""
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text("{not json", encoding="utf-8")
    config = service.config()
    assert config["enabled"] is False
    assert config["pipelines"] == []
    assert "invalid" in service.last_error


def test_the_interval_cannot_be_set_to_hammer_a_quota(service):
    service.update({"pipelines": [PAIR], "interval_seconds": 5})
    assert service.config()["interval_seconds"] == 300
    service.update({"interval_seconds": 10**9})
    assert service.config()["interval_seconds"] == 86400


def test_counts_are_bounded(service):
    service.update(
        {"pipelines": [PAIR], "per_channel": 900, "max_topics": 99, "candidates": 99}
    )
    config = service.config()
    assert (config["per_channel"], config["max_topics"], config["candidates"]) == (50, 10, 8)


# ── one cycle ───────────────────────────────────────────────────────────────


def test_a_cycle_runs_the_pipeline_in_its_own_order(service, parts):
    """Sweep before plan, plan before draft: you cannot plan against topics you
    have not swept, or draft from pictures nobody kept."""
    service.update({"pipelines": [PAIR]})
    results = service.run_once()
    assert steps_of(results) == ["sweep", "plan", "draft", "publish_due"]
    assert all(row["status"] == "ok" for row in results), results


def test_the_declared_pair_is_what_gets_planned(service, parts):
    service.update({"pipelines": [PAIR]})
    service.run_once()
    planned = parts["pipeline"].planned[0]
    assert planned["distribution_campaign_id"] == "dist-1"
    assert planned["image_campaign_id"] == "img-1"
    assert planned["angle"] == "we move freight"
    drafted = parts["pipeline"].drafted[0]
    assert drafted["account_ids"] == ["acct-1"]


def test_two_pipelines_both_run(service, parts):
    second = {**PAIR, "distribution_campaign_id": "dist-2", "image_campaign_id": "img-2"}
    service.update({"pipelines": [PAIR, second]})
    results = service.run_once()
    assert steps_of(results) == ["sweep", "plan", "draft", "plan", "draft", "publish_due"]
    assert {row["distribution_campaign_id"] for row in results if "distribution_campaign_id" in row} == {
        "dist-1",
        "dist-2",
    }


def test_a_failing_sweep_does_not_stop_approved_posts_going_out(tmp_path):
    """The property the whole cycle design exists for."""
    parts = {
        "watcher": _Watcher(fail=True),
        "pipeline": _Pipeline(),
        "distribution": _Distribution(),
    }
    service = ContentAutomationService(
        tmp_path / "c.json",
        trends_factory=lambda: parts["watcher"],
        pipeline_factory=lambda angle: parts["pipeline"],
        distribution_factory=lambda: parts["distribution"],
    )
    service.update({"pipelines": [PAIR]})
    results = service.run_once()
    sweep = next(row for row in results if row["step"] == "sweep")
    publish = next(row for row in results if row["step"] == "publish_due")
    assert sweep["status"] == "failed"
    assert "quota" in sweep["error"]
    assert publish["status"] == "ok"
    assert parts["distribution"].calls == 1


def test_a_failing_plan_does_not_stop_the_other_pipeline(tmp_path):
    parts = {
        "watcher": _Watcher(),
        "pipeline": _Pipeline(fail_plan=True),
        "distribution": _Distribution(),
    }
    service = ContentAutomationService(
        tmp_path / "c.json",
        trends_factory=lambda: parts["watcher"],
        pipeline_factory=lambda angle: parts["pipeline"],
        distribution_factory=lambda: parts["distribution"],
    )
    service.update({"pipelines": [PAIR, {**PAIR, "distribution_campaign_id": "dist-2"}]})
    results = service.run_once()
    assert [row["status"] for row in results if row["step"] == "plan"] == ["failed", "failed"]
    assert next(row for row in results if row["step"] == "publish_due")["status"] == "ok"


def test_the_watcher_is_closed_even_when_the_sweep_fails(tmp_path):
    parts = {
        "watcher": _Watcher(fail=True),
        "pipeline": _Pipeline(),
        "distribution": _Distribution(),
    }
    service = ContentAutomationService(
        tmp_path / "c.json",
        trends_factory=lambda: parts["watcher"],
        pipeline_factory=lambda angle: parts["pipeline"],
        distribution_factory=lambda: parts["distribution"],
    )
    service.update({"pipelines": [PAIR]})
    service.run_once()
    assert parts["watcher"].closed


def test_a_step_that_is_switched_off_says_so(service, parts):
    """Rather than silently doing less than the report appears to show."""
    service.update({"pipelines": [PAIR], "sweep": False, "publish_due": False})
    results = service.run_once()
    assert next(row for row in results if row["step"] == "sweep")["status"] == "skipped"
    assert next(row for row in results if row["step"] == "publish_due")["status"] == "skipped"
    assert parts["watcher"].calls == []
    assert parts["distribution"].calls == 0


def test_switching_off_planning_still_drafts_what_was_already_kept(service, parts):
    service.update({"pipelines": [PAIR], "plan": False})
    results = service.run_once()
    assert "plan" not in steps_of(results)
    assert "draft" in steps_of(results)
    assert parts["pipeline"].planned == []


def test_the_run_is_reported_for_the_status_panel(service):
    service.update({"pipelines": [PAIR]})
    service.run_once()
    status = service.status()
    assert status["last_run_at"]
    assert status["last_error"] == ""
    assert steps_of(status["last_results"]) == ["sweep", "plan", "draft", "publish_due"]


def test_two_cycles_cannot_overlap(service):
    """Two sweeps at once spend quota twice for one answer."""
    service.update({"pipelines": [PAIR]})
    assert service._run_lock.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match="already running"):
            service.run_once()
    finally:
        service._run_lock.release()


def test_the_counts_from_each_step_reach_the_report(service):
    service.update({"pipelines": [PAIR]})
    results = service.run_once()
    sweep = next(row for row in results if row["step"] == "sweep")
    plan = next(row for row in results if row["step"] == "plan")
    draft = next(row for row in results if row["step"] == "draft")
    publish = next(row for row in results if row["step"] == "publish_due")
    assert (sweep["channels_swept"], sweep["videos_new"], sweep["units_spent"]) == (4, 9, 5)
    assert (plan["topics_found"], plan["topics_planned"], plan["candidates"]) == (3, 2, 6)
    assert (draft["assets_considered"], draft["posts_created"], draft["skipped"]) == (5, 2, 1)
    assert (publish["published"], publish["failed"], publish["skipped"]) == (2, 0, 1)


# ── the loop ────────────────────────────────────────────────────────────────


def test_the_loop_waits_before_it_runs(service, parts):
    """Never run-then-wait: a restart loop would become a burst of sweeps
    against a quota."""

    async def scenario():
        service.update({"pipelines": [PAIR], "enabled": True})
        await service.start()
        await asyncio.sleep(0.05)
        await service.stop()

    asyncio.run(scenario())
    assert parts["watcher"].calls == []


def test_a_disabled_service_never_runs_a_cycle(service, parts, monkeypatch):
    async def scenario():
        service.update({"pipelines": [PAIR], "enabled": False})
        monkeypatch.setattr(
            "offsetx_apollo_builder.distribution.automation.ContentAutomationService.config",
            lambda self: {**service._normalise({"pipelines": [PAIR], "enabled": False}), "interval_seconds": 0},
        )
        await service.start()
        await asyncio.sleep(0.05)
        await service.stop()

    asyncio.run(scenario())
    assert parts["watcher"].calls == []
    assert parts["distribution"].calls == 0


def test_the_loop_runs_a_cycle_once_the_interval_elapses(service, parts, monkeypatch):
    monkeypatch.setattr(
        "offsetx_apollo_builder.distribution.automation.ContentAutomationService.config",
        lambda self: {**self._normalise({"pipelines": [PAIR], "enabled": True}), "interval_seconds": 0},
    )

    async def scenario():
        await service.start()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if parts["distribution"].calls:
                break
        await service.stop()

    asyncio.run(scenario())
    assert parts["watcher"].calls
    assert parts["distribution"].calls >= 1


def test_stopping_is_clean_and_repeatable(service):
    async def scenario():
        service.update({"pipelines": [PAIR], "enabled": True})
        await service.start()
        await service.start()  # idempotent
        await service.stop()
        await service.stop()

    asyncio.run(scenario())
    assert service.status()["running"] is False


# ── the shape of the thing ──────────────────────────────────────────────────


def test_the_steps_are_the_four_the_pipeline_actually_has():
    assert STEPS == ("sweep", "plan", "draft", "publish_due")
    for step in STEPS:
        assert DEFAULT_CONTENT_AUTOMATION[step] is True


def test_this_service_owns_no_transport():
    """Structural: it knows the order of the work and nothing about trends,
    posting, or providers. A module that could reach a provider directly would
    inherit none of the egress protections."""
    import ast
    import inspect

    from offsetx_apollo_builder.distribution import automation

    tree = ast.parse(inspect.getsource(automation))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    for banned in ("requests", "httpx", "urllib", "socket"):
        assert not any(banned in name for name in imported), f"{banned} reached this module"


# ── through the API ─────────────────────────────────────────────────────────


def test_the_engine_can_be_declared_and_run_over_http(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/v1/content-automation").json()
        assert status["enabled"] is False
        assert status["pipelines"] == []
        assert status["running"] is True  # the timer is up, just idle

        # Enabling with nothing declared is refused, which is the whole point.
        refused = client.patch("/api/v1/content-automation", json={"enabled": True})
        assert refused.status_code == 422
        assert "Nothing is declared to run" in refused.json()["detail"]

        distribution = client.post(
            "/api/v1/campaigns", json={"name": "Reach", "kind": "distribution"}
        ).json()
        image = client.post("/api/v1/campaigns", json={"name": "Pics", "kind": "image"}).json()

        saved = client.patch(
            "/api/v1/content-automation",
            json={
                "enabled": True,
                "interval_seconds": 1800,
                "pipelines": [
                    {
                        "distribution_campaign_id": distribution["id"],
                        "image_campaign_id": image["id"],
                        "angle": "we move freight",
                    }
                ],
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["enabled"] is True
        assert body["interval_seconds"] == 1800
        assert len(body["pipelines"]) == 1

        # One cycle, for real, against the app's own factories. No YouTube key
        # is configured, so the sweep reports its failure and the cycle carries
        # on — which is exactly the designed behaviour.
        ran = client.post("/api/v1/content-automation/run")
        assert ran.status_code == 200, ran.text
        results = ran.json()["results"]
        assert [row["step"] for row in results] == ["sweep", "plan", "draft", "publish_due"]
        assert next(row for row in results if row["step"] == "publish_due")["status"] == "ok"

        after = client.get("/api/v1/content-automation").json()
        assert after["last_run_at"]
        assert len(after["last_results"]) == 4


def test_the_timer_starts_and_stops_with_the_app(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    application = create_app(settings)
    with TestClient(application) as client:
        assert client.get("/api/v1/content-automation").json()["running"] is True
    # After the lifespan closes, the task is gone rather than orphaned.
    assert application.state.content_automation._task is None
