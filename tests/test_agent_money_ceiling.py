"""A run has a money ceiling, not only a step ceiling.  `S-11.01.04`

Two of this story's three criteria arrived with `S-06.01.03`: the pre-run
estimate, and per-step spend in the trace. What is here is the ceiling itself.

The property that matters is **the ceiling is never crossed, only approached**.
The check runs before the model is asked anything, so a run that stops has not
spent the money it was about to — which is also what makes stopping safe to
resume from. A ceiling enforced after the fact is a receipt, not a limit.

The second property, and the one easiest to get wrong: a ceiling that
disappears when a run is resumed is not a ceiling. Stop at the limit, resume,
spend without bound. That has its own test.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import (
    RunRefused,
    next_decision_cost,
    replay,
    would_cross_ceiling,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


# ── the rule on its own ─────────────────────────────────────────────────────


def test_no_ceiling_means_no_ceiling():
    """Zero is "uncapped", the same convention `QuotaLimits` uses."""
    assert not would_cross_ceiling(ceiling_usd=0.0, spent_usd=999.0, next_decision_usd=999.0)
    assert not would_cross_ceiling(ceiling_usd=-1.0, spent_usd=999.0, next_decision_usd=1.0)


def test_a_decision_that_fits_is_allowed():
    assert not would_cross_ceiling(ceiling_usd=1.0, spent_usd=0.5, next_decision_usd=0.4)


def test_a_decision_that_would_cross_is_refused_before_it_is_made():
    assert would_cross_ceiling(ceiling_usd=1.0, spent_usd=0.95, next_decision_usd=0.1)


def test_landing_exactly_on_the_ceiling_is_allowed():
    """The owner said "up to a dollar". A dollar is up to a dollar."""
    assert not would_cross_ceiling(ceiling_usd=1.0, spent_usd=0.9, next_decision_usd=0.1)


def test_the_next_decision_is_predicted_from_the_worst_so_far_not_the_average():
    """A ceiling is a promise. The average lags a trend, so a run whose pages
    keep growing would walk past the line while the average said it was fine."""
    assert next_decision_cost(observed=[0.001, 0.002, 0.020], estimated=0.005) == 0.020
    assert next_decision_cost(observed=[], estimated=0.005) == 0.005


def test_a_negative_estimate_cannot_buy_headroom():
    assert next_decision_cost(observed=[], estimated=-5.0) == 0.0


# ── through a real run ──────────────────────────────────────────────────────


#: Rates chosen so one *typical* decision — the size `estimate_run` assumes —
#: costs exactly five cents, and so does one real decision below. The estimate
#: and the actual therefore agree, which is what a correctly-priced model looks
#: like and what keeps the arithmetic in these tests doable in your head.
#:
#:     (3000 / 1e6) * 16.0  +  (100 / 1e6) * 20.0  =  0.048 + 0.002  =  0.05
PER_1M_IN, PER_1M_OUT = 16.0, 20.0
TOKENS_IN, TOKENS_OUT = 3_000, 100
COST_PER_DECISION = 0.05


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=PER_1M_IN,
                                cost_per_1m_output_usd=PER_1M_OUT)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    """Every decision costs exactly `COST_PER_DECISION`, so the arithmetic in
    these tests is something a reader can do in their head."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.registry = _Registry()
        self.calls = 0

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner",
                                tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls += 1
        if not self.answers:
            raise AssertionError("the run asked for more decisions than were scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
            tokens_in=TOKENS_IN, tokens_out=TOKENS_OUT, cost_usd=COST_PER_DECISION,
            usage_source="provider",
        )


class _Page:
    url = "https://acme.test/about"

    async def snapshot(self):
        return Snapshot(url=self.url, title="Acme",
                        nodes=[Node(handle=1, role="heading", name="Acme")])

    async def read(self, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url,
                            detail="read the page", text="Acme has 42 people")


def _act(action="read", **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "look"})


def _done(result="42"):
    return json.dumps({"state": "done", "reason": "found it", "result": result})


def _agent(trace, answers):
    return AgentRun(
        broker=_Broker(answers),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=_Page(), trace=trace, planner_provider_id="trusted",
    )


def test_a_run_stops_at_the_ceiling_with_the_right_status(tmp_path):
    """The acceptance criterion."""
    trace = Trace.open(tmp_path / "t")
    # Room for three decisions at $0.05; the fourth would cross $0.20.
    agent = _agent(trace, [_act(), _act(), _act(), _act(), _done()])
    outcome = asyncio.run(agent.run("find it", step_budget=20, spend_ceiling_usd=0.20))

    assert outcome.status == "over_budget"
    assert outcome.decisions == 4, "the run should use the ceiling, not stop early"
    assert outcome.spend_usd == pytest.approx(0.20)


def test_the_decision_that_would_cross_is_never_asked_for(tmp_path):
    """Not "stopped afterwards". The model is never called, so the money the
    ceiling was protecting is still there."""
    trace = Trace.open(tmp_path / "t")
    agent = _agent(trace, [_act(), _act(), _done()])
    outcome = asyncio.run(agent.run("find it", step_budget=20, spend_ceiling_usd=0.10))

    assert outcome.status == "over_budget"
    assert agent.broker.calls == 2, "a model was asked for a decision past the ceiling"
    assert outcome.spend_usd <= 0.10


def test_a_run_inside_its_ceiling_finishes_normally(tmp_path):
    """The check must not be a tax on every run that was never going to cross."""
    trace = Trace.open(tmp_path / "t")
    outcome = asyncio.run(
        _agent(trace, [_act(), _done()]).run("find it", step_budget=20,
                                             spend_ceiling_usd=10.0))
    assert outcome.status == "completed"
    assert outcome.headroom_usd == pytest.approx(10.0 - outcome.spend_usd)


def test_no_ceiling_behaves_exactly_as_before(tmp_path):
    trace = Trace.open(tmp_path / "t")
    outcome = asyncio.run(_agent(trace, [_act(), _done()]).run("find it", step_budget=20))
    assert outcome.status == "completed"
    assert outcome.spend_ceiling_usd == 0.0
    assert outcome.headroom_usd == 0.0


def test_a_ceiling_smaller_than_one_decision_stops_before_spending_anything(tmp_path):
    """The owner set a limit that cannot buy a single step. The honest response
    is to spend nothing, not to spend one and apologise."""
    trace = Trace.open(tmp_path / "t")
    agent = _agent(trace, [_done()])
    outcome = asyncio.run(agent.run("find it", step_budget=20, spend_ceiling_usd=0.000001))

    assert outcome.status == "over_budget"
    assert outcome.decisions == 0
    assert agent.broker.calls == 0
    assert outcome.spend_usd == 0.0


def test_what_it_gathered_before_the_ceiling_is_kept(tmp_path):
    """A run that found three facts and hit its limit on the fourth has still
    found three facts."""
    trace = Trace.open(tmp_path / "t")
    agent = _agent(trace, [_act(), _act(), _act()])
    outcome = asyncio.run(agent.run("find it", step_budget=20, spend_ceiling_usd=0.10))

    assert outcome.status == "over_budget"
    assert outcome.actions >= 1, "the work done before the ceiling was thrown away"


def test_the_trace_says_why_it_stopped_and_by_how_much(tmp_path):
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_act(), _act(), _done()]).run(
        "find it", step_budget=20, spend_ceiling_usd=0.10))

    stopped = next(step for step in trace.read() if step.kind == "over_budget")
    recorded = json.loads(trace.captured_text(stopped))
    assert recorded["ceiling_usd"] == pytest.approx(0.10)
    assert recorded["spent_usd"] == pytest.approx(0.10)
    assert recorded["projected_next_usd"] == pytest.approx(COST_PER_DECISION)


def test_the_ceiling_is_recorded_where_the_run_announces_itself(tmp_path):
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_done()]).run("find it", step_budget=5,
                                             spend_ceiling_usd=2.50))
    started = next(step for step in trace.read() if step.kind == "run_started")
    assert json.loads(trace.captured_text(started))["spend_ceiling_usd"] == 2.50
    assert "spend_ceiling=$2.5000" in started.detail


def test_a_projection_already_over_the_ceiling_is_said_up_front(tmp_path):
    """Worth knowing before the first page loads, not at the step it stops on."""
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_done()]).run("find it", step_budget=50,
                                             spend_ceiling_usd=0.0001))
    started = next(step for step in trace.read() if step.kind == "run_started")
    assert "WARNING" in started.detail
    assert "expected to stop short" in started.detail


# ── the ceiling has to survive a resume ─────────────────────────────────────


def test_a_resumed_run_keeps_the_ceiling_it_was_given(tmp_path):
    """The one that matters. Stop at the limit, resume, spend without bound is
    not a limit — it is a speed bump."""
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_act(), _act(), _done()]).run(
        "find it", step_budget=20, spend_ceiling_usd=0.10))

    assert replay(trace).spend_ceiling_usd == pytest.approx(0.10)

    resumed_agent = _agent(trace, [_done()])
    resumed = asyncio.run(resumed_agent.resume())

    assert resumed.status == "over_budget", "the ceiling evaporated on resume"
    assert resumed_agent.broker.calls == 0


def test_raising_the_ceiling_on_purpose_lets_the_run_carry_on(tmp_path):
    """Which is the whole point of it being resumable."""
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_act(), _act(), _done()]).run(
        "find it", step_budget=20, spend_ceiling_usd=0.10))

    resumed = asyncio.run(_agent(trace, [_done()]).resume(spend_ceiling_usd=5.0))
    assert resumed.status == "completed"


def test_a_resumed_run_counts_what_its_earlier_life_spent(tmp_path):
    """Otherwise the ceiling resets every time the process does, and a run
    killed and restarted ten times spends ten ceilings."""
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_act(), _act(), _done()]).run(
        "find it", step_budget=20, spend_ceiling_usd=0.10))
    spent_before = float(trace.summary()["estimated_cost_usd"])

    agent = _agent(trace, [_done()])
    asyncio.run(agent.resume(spend_ceiling_usd=0.12))

    assert agent.broker.calls == 0, "the resumed run got a fresh allowance"
    assert spent_before == pytest.approx(0.10)


def test_a_run_stopped_by_the_ceiling_is_not_treated_as_finished(tmp_path):
    """`over_budget` must stay out of the set `resume` refuses, or raising the
    ceiling would be impossible."""
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, [_act(), _done()]).run(
        "find it", step_budget=20, spend_ceiling_usd=0.05))

    try:
        asyncio.run(_agent(trace, [_done()]).resume(spend_ceiling_usd=9.0))
    except RunRefused as exc:  # pragma: no cover - this is the failure being guarded
        pytest.fail(f"a run stopped by its ceiling could not be resumed: {exc}")


# ── the known limit, specified rather than discovered ───────────────────────


class _UnpricedRegistry:
    """A registry with no rates for the model — a free model, a local one, or
    a price list that has not been updated."""

    def get(self, provider_id):
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=0.0,
                                cost_per_1m_output_usd=0.0)
        return SimpleNamespace(model=lambda model_id="": model)


def test_an_unpriced_model_costs_one_decision_of_headroom_and_no_more(tmp_path):
    """**The known limit, pinned.**

    The ceiling predicts the first decision from the pre-run estimate. If the
    model has no price list that estimate is zero, so the first decision goes
    through whatever the ceiling says — there is nothing to predict it with, and
    refusing every run on an unpriced model would make free and local models
    unusable.

    From the second decision on, the run has its own observed costs and the
    ceiling works normally. So the exposure is exactly one decision, and this
    test is what keeps it at one.
    """
    trace = Trace.open(tmp_path / "t")
    agent = _agent(trace, [_act(), _act(), _act(), _done()])
    agent.broker.registry = _UnpricedRegistry()

    outcome = asyncio.run(agent.run("find it", step_budget=20,
                                    spend_ceiling_usd=0.000001))

    assert outcome.status == "over_budget"
    assert agent.broker.calls == 1, (
        "an unpriced model should cost one decision of headroom, not more"
    )
    assert outcome.decisions == 1
