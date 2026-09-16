"""Cost and latency budgets are one run contract.  `S-06.02.03`

The money half already exists (`S-11.01.04`) and is deliberately reused here.
This file pins the missing latency half and, importantly, the boundary semantics:
latency is the cumulative measured `took_ms` already written to the append-only
trace. A run never starts another unit of work once that recorded ceiling is
reached. An operation already in flight is allowed to finish rather than being
cancelled halfway through a possible side effect; if that operation crosses the
ceiling, the run stops before doing anything else and reports the overrun.

Zero means uncapped. A negative or boolean latency ceiling is invalid input.
The ceiling survives resume for the same reason the spend ceiling does: resume
continues one run, it does not mint a fresh allowance.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import (
    RunRefused,
    latency_ceiling_reached,
    replay,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(
            id="planner",
            cost_per_1m_input_usd=16.0,
            cost_per_1m_output_usd=20.0,
        )
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers, *, duration_ms=7, cost_usd=0.05):
        self.answers = list(answers)
        self.duration_ms = int(duration_ms)
        self.cost_usd = float(cost_usd)
        self.registry = _Registry()
        self.calls = 0

    def plan(self, request, settings, *, provider_id=""):
        return [
            SimpleNamespace(
                id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0
            )
        ], []

    def call(
        self,
        request,
        settings,
        *,
        system_prompt,
        provider_id="",
        expect_json=False,
    ):
        self.calls += 1
        if not self.answers:
            raise AssertionError("the run asked for more decisions than were scripted")
        return SimpleNamespace(
            text=self.answers.pop(0),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            tier="A",
            policy="full",
            data_class=request.data_class.value,
            duration_ms=self.duration_ms,
            payload_fields=["instructions"],
            attempts=[],
            rejected=[],
            log_id="e1",
            tokens_in=3_000,
            tokens_out=100,
            cost_usd=self.cost_usd,
            usage_source="provider",
        )


class _Page:
    url = "https://acme.test/about"

    def __init__(self, *, read_took_ms=0):
        self.read_took_ms = int(read_took_ms)
        self.reads = 0

    async def snapshot(self):
        return Snapshot(
            url=self.url,
            title="Acme",
            nodes=[Node(handle=1, role="heading", name="Acme")],
        )

    async def read(self, limit=20_000):
        self.reads += 1
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read the page",
            text="Acme has 42 people",
            took_ms=self.read_took_ms,
        )


def _act():
    return json.dumps(
        {"state": "act", "action": "read", "args": {}, "reason": "look"}
    )


def _done(result="42"):
    return json.dumps({"state": "done", "reason": "found it", "result": result})


def _agent(trace, answers, *, duration_ms=7, read_took_ms=0, cost_usd=0.05):
    broker = _Broker(answers, duration_ms=duration_ms, cost_usd=cost_usd)
    page = _Page(read_took_ms=read_took_ms)
    agent = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="w", enabled_models={"trusted": ("planner",)}
        ),
        page=page,
        trace=trace,
        planner_provider_id="trusted",
    )
    return agent, broker, page


def test_zero_latency_ceiling_is_uncapped():
    assert not latency_ceiling_reached(ceiling_ms=0, spent_ms=50_000)


def test_landing_on_latency_ceiling_means_no_new_work_starts():
    assert latency_ceiling_reached(ceiling_ms=50, spent_ms=50)
    assert latency_ceiling_reached(ceiling_ms=50, spent_ms=51)
    assert not latency_ceiling_reached(ceiling_ms=50, spent_ms=49)


def test_a_model_call_that_uses_the_remaining_latency_stops_before_the_action(tmp_path):
    trace = Trace.open(tmp_path / "t")
    agent, broker, page = _agent(trace, [_act(), _done()], duration_ms=7)

    outcome = asyncio.run(
        agent.run("find it", step_budget=10, latency_ceiling_ms=5)
    )

    assert outcome.status == "over_latency"
    assert broker.calls == 1
    assert page.reads == 0, "a browser action started after the latency ceiling"
    assert outcome.actions == 0
    assert outcome.latency_ms == 7
    assert outcome.latency_ceiling_ms == 5
    assert outcome.latency_overrun_ms == 2


def test_an_action_that_crosses_latency_stops_before_another_model_call(tmp_path):
    trace = Trace.open(tmp_path / "t")
    agent, broker, page = _agent(
        trace, [_act(), _done()], duration_ms=7, read_took_ms=5
    )

    outcome = asyncio.run(
        agent.run("find it", step_budget=10, latency_ceiling_ms=10)
    )

    assert outcome.status == "over_latency"
    assert broker.calls == 1, "a second decision started after the latency ceiling"
    assert page.reads == 1
    assert outcome.actions == 1
    assert outcome.latency_ms == 12
    assert outcome.latency_overrun_ms == 2


def test_latency_stop_is_traceable_with_limit_actual_and_overrun(tmp_path):
    trace = Trace.open(tmp_path / "t")
    agent, _, _ = _agent(trace, [_act()], duration_ms=9)

    asyncio.run(agent.run("find it", step_budget=10, latency_ceiling_ms=5))

    stopped = next(step for step in trace.read() if step.kind == "over_latency")
    recorded = json.loads(trace.captured_text(stopped))
    assert recorded == {
        "ceiling_ms": 5,
        "spent_ms": 9,
        "overrun_ms": 4,
        "decisions": 1,
        "actions": 0,
    }
    started = next(step for step in trace.read() if step.kind == "run_started")
    assert json.loads(trace.captured_text(started))["latency_ceiling_ms"] == 5
    assert "latency_ceiling=5ms" in started.detail


def test_latency_ceiling_survives_resume_and_counts_earlier_work(tmp_path):
    trace = Trace.open(tmp_path / "t")
    first, _, _ = _agent(trace, [_act()], duration_ms=7)
    first_outcome = asyncio.run(
        first.run("find it", step_budget=10, latency_ceiling_ms=5)
    )
    assert first_outcome.status == "over_latency"
    assert replay(trace).latency_ceiling_ms == 5

    resumed, resumed_broker, _ = _agent(trace, [_done()], duration_ms=7)
    same_limit = asyncio.run(resumed.resume())
    assert same_limit.status == "over_latency"
    assert resumed_broker.calls == 0, "resume silently minted a fresh latency budget"

    raised, raised_broker, _ = _agent(trace, [_done()], duration_ms=7)
    completed = asyncio.run(raised.resume(latency_ceiling_ms=100))
    assert completed.status == "completed"
    assert raised_broker.calls == 1
    assert completed.latency_ceiling_ms == 100
    assert completed.latency_ms == 14


def test_completed_run_reports_latency_headroom(tmp_path):
    trace = Trace.open(tmp_path / "t")
    agent, _, _ = _agent(trace, [_done()], duration_ms=7)

    outcome = asyncio.run(
        agent.run("find it", step_budget=10, latency_ceiling_ms=100)
    )

    assert outcome.status == "completed"
    assert outcome.latency_ms == 7
    assert outcome.latency_headroom_ms == 93
    assert outcome.latency_overrun_ms == 0
    payload = outcome.to_dict()
    assert payload["latency_ms"] == 7
    assert payload["latency_ceiling_ms"] == 100
    assert payload["latency_headroom_ms"] == 93
    assert payload["latency_overrun_ms"] == 0


def test_cost_ceiling_still_wins_before_any_model_call(tmp_path):
    """S-06.02.03 integrates the existing money ceiling; it does not replace it."""
    trace = Trace.open(tmp_path / "t")
    agent, broker, _ = _agent(trace, [_done()], duration_ms=7)

    outcome = asyncio.run(
        agent.run(
            "find it",
            step_budget=10,
            spend_ceiling_usd=0.000001,
            latency_ceiling_ms=100,
        )
    )

    assert outcome.status == "over_budget"
    assert broker.calls == 0
    assert outcome.latency_ms == 0


@pytest.mark.parametrize("bad", [-1, -0.1, True, False, "five"])
def test_invalid_latency_ceiling_is_refused_before_the_run_starts(tmp_path, bad):
    trace = Trace.open(tmp_path / "t")
    agent, broker, _ = _agent(trace, [_done()])

    with pytest.raises(RunRefused, match="Latency ceiling"):
        asyncio.run(agent.run("find it", step_budget=10, latency_ceiling_ms=bad))

    assert broker.calls == 0
    assert list(trace.read()) == []
