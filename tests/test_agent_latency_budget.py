"""Cost and latency budgets per run.  `S-06.02.03`

Spend already has a hard host-side ceiling (`S-11.01.04`).  These cases pin the
missing half of this story: elapsed wall time is also a budget, is enforced by
host code rather than by the model, and survives process death/resume.

No test sleeps.  A fake wall clock makes the boundary deterministic and also
proves that time spent inside the model/browser counts toward the owner's
budget rather than only time between calls.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import RunRefused, replay
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


class _Clock:
    def __init__(self, now: float = 1_000.0):
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(
            id="planner",
            cost_per_1m_input_usd=0.0,
            cost_per_1m_output_usd=0.0,
        )
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers, clock: _Clock, delays=()):
        self.answers = list(answers)
        self.clock = clock
        self.delays = list(delays)
        self.registry = _Registry()
        self.calls = 0

    def plan(self, request, settings, *, provider_id=""):
        return [
            SimpleNamespace(
                id="trusted", model_id="planner", tier=TrustTier.A, cost=0.0
            )
        ], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls += 1
        if not self.answers:
            raise AssertionError("the run asked for more decisions than were scripted")
        delay = self.delays.pop(0) if self.delays else 0.0
        self.clock.advance(delay)
        return SimpleNamespace(
            text=self.answers.pop(0),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            tier="A",
            policy="full",
            data_class=request.data_class.value,
            duration_ms=int(delay * 1_000),
            payload_fields=["instructions"],
            attempts=[],
            rejected=[],
            log_id="latency-test",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            usage_source="provider",
        )


class _Page:
    url = "https://acme.test/about"

    def __init__(self, clock: _Clock, *, action_delay: float = 0.0):
        self.clock = clock
        self.action_delay = float(action_delay)
        self.read_calls = 0
        self.snapshot_calls = 0

    async def snapshot(self):
        self.snapshot_calls += 1
        return Snapshot(
            url=self.url,
            title="Acme",
            nodes=[Node(handle=1, role="heading", name="Acme")],
        )

    async def read(self, limit=20_000):
        self.read_calls += 1
        self.clock.advance(self.action_delay)
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read the page",
            text="Acme has 42 people",
            took_ms=int(self.action_delay * 1_000),
        )


def _act():
    return json.dumps(
        {"state": "act", "action": "read", "args": {}, "reason": "look"}
    )


def _done():
    return json.dumps({"state": "done", "reason": "found it", "result": "42"})


def _agent(trace, answers, clock, *, delays=(), action_delay=0.0):
    broker = _Broker(answers, clock, delays)
    page = _Page(clock, action_delay=action_delay)
    agent = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="w", enabled_models={"trusted": ("planner",)}
        ),
        page=page,
        trace=trace,
        planner_provider_id="trusted",
        clock=clock,
    )
    return agent, broker, page


def test_a_slow_model_crossing_the_latency_ceiling_never_executes_its_action(tmp_path):
    """The host can observe a blocking provider call only after it returns.
    Once it does, no browser side effect is allowed to start past the deadline."""
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    agent, broker, page = _agent(trace, [_act()], clock, delays=[3.0])

    outcome = asyncio.run(
        agent.run("find it", step_budget=5, latency_ceiling_seconds=2.0)
    )

    assert outcome.status == "over_latency"
    assert outcome.decisions == 1
    assert outcome.actions == 0
    assert broker.calls == 1
    assert page.read_calls == 0, "an action started after the latency ceiling"
    assert outcome.elapsed_seconds == pytest.approx(3.0)


def test_an_action_that_crosses_the_ceiling_is_the_last_action_started(tmp_path):
    """An in-flight browser call cannot be un-done.  The safe contract is that
    it is recorded, then the run stops before another model/browser call."""
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    agent, broker, page = _agent(
        trace, [_act(), _done()], clock, action_delay=3.0
    )

    outcome = asyncio.run(
        agent.run("find it", step_budget=5, latency_ceiling_seconds=2.0)
    )

    assert outcome.status == "over_latency"
    assert broker.calls == 1
    assert page.read_calls == 1
    assert outcome.actions == 1
    assert outcome.elapsed_seconds == pytest.approx(3.0)


def test_the_latency_stop_says_exactly_what_budget_was_exceeded(tmp_path):
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    agent, _, _ = _agent(trace, [_act()], clock, delays=[2.5])

    outcome = asyncio.run(
        agent.run("find it", step_budget=5, latency_ceiling_seconds=2.0)
    )

    stopped = next(step for step in trace.read() if step.kind == "over_latency")
    recorded = json.loads(trace.captured_text(stopped))
    assert recorded["ceiling_seconds"] == pytest.approx(2.0)
    assert recorded["elapsed_seconds"] == pytest.approx(2.5)
    assert recorded["overrun_seconds"] == pytest.approx(0.5)
    assert "latency ceiling" in outcome.message.lower()
    assert outcome.latency_headroom_seconds == pytest.approx(-0.5)


def test_the_latency_contract_is_durable_in_the_start_record(tmp_path):
    clock = _Clock(55.0)
    trace = Trace.open(tmp_path / "trace")
    agent, _, _ = _agent(trace, [_done()], clock)

    asyncio.run(agent.run("find it", step_budget=5, latency_ceiling_seconds=8.0))

    started = next(step for step in trace.read() if step.kind == "run_started")
    parameters = json.loads(trace.captured_text(started))
    assert parameters["latency_ceiling_seconds"] == pytest.approx(8.0)
    assert parameters["latency_started_at"] == pytest.approx(55.0)
    assert "latency_ceiling=8.000s" in started.detail


def test_a_resumed_run_keeps_the_original_clock_and_ceiling(tmp_path):
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    first, _, _ = _agent(trace, [_act()], clock, delays=[2.0])
    asyncio.run(first.run("find it", step_budget=5, latency_ceiling_seconds=1.0))

    state = replay(trace)
    assert state.latency_ceiling_seconds == pytest.approx(1.0)
    assert state.latency_started_at == pytest.approx(1_000.0)

    resumed, broker, page = _agent(trace, [_done()], clock)
    outcome = asyncio.run(resumed.resume())

    assert outcome.status == "over_latency"
    assert broker.calls == 0
    assert page.snapshot_calls == 0, "an expired run touched the page before stopping"


def test_raising_the_latency_ceiling_on_purpose_allows_resume(tmp_path):
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    first, _, _ = _agent(trace, [_act()], clock, delays=[2.0])
    asyncio.run(first.run("find it", step_budget=5, latency_ceiling_seconds=1.0))

    resumed, broker, _ = _agent(trace, [_done()], clock)
    outcome = asyncio.run(resumed.resume(latency_ceiling_seconds=10.0))

    assert outcome.status == "completed"
    assert broker.calls == 1
    assert outcome.latency_ceiling_seconds == pytest.approx(10.0)
    assert outcome.elapsed_seconds == pytest.approx(2.0)


def test_an_explicit_resume_budget_is_itself_durable(tmp_path):
    """A process dying after an owner raised a ceiling must not resurrect the
    old lower value on the next resume."""
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    first, _, _ = _agent(trace, [_act()], clock, delays=[2.0])
    asyncio.run(first.run("find it", step_budget=5, latency_ceiling_seconds=1.0))

    resumed, _, _ = _agent(trace, [_done()], clock)
    second = asyncio.run(resumed.resume(latency_ceiling_seconds=1.5))
    assert second.status == "over_latency"
    assert replay(trace).latency_ceiling_seconds == pytest.approx(1.5)


def test_no_latency_ceiling_preserves_existing_behavior(tmp_path):
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    agent, _, _ = _agent(trace, [_done()], clock, delays=[30.0])

    outcome = asyncio.run(agent.run("find it", step_budget=5))

    assert outcome.status == "completed"
    assert outcome.latency_ceiling_seconds == 0.0
    assert outcome.latency_headroom_seconds == 0.0
    assert outcome.elapsed_seconds == pytest.approx(30.0)


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan"), True])
def test_invalid_latency_budgets_are_refused_before_a_run_starts(tmp_path, bad):
    clock = _Clock()
    trace = Trace.open(tmp_path / "trace")
    agent, broker, page = _agent(trace, [_done()], clock)

    with pytest.raises(RunRefused, match="Latency budget"):
        asyncio.run(agent.run("find it", step_budget=5, latency_ceiling_seconds=bad))

    assert broker.calls == 0
    assert page.snapshot_calls == 0
