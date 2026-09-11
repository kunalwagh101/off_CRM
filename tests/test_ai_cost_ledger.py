"""Cost estimated before a run and ledgered after.  `S-06.01.03`

Two acceptance criteria, and between them a defect that made the whole thing
theatre: every call was recorded against the owner's daily spend cap as costing
**$0.00**, so the cap could never be reached (`D-35`). The provider was telling
us the exact token counts in every response and the adapter was dropping them
(`D-36`).

So the tests here are mostly about one property: **there is one number.** What
the provider reported, what the ledger counted, what the run's trace recorded
and what the estimate was compared against all come from one measurement priced
by one function. Two places counting the same money is two places that disagree
about it, which is the shape of half the defect log.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent.run import (
    TYPICAL_DECISION_INPUT_CHARS,
    RunEstimate,
    estimate_run,
)
from offsetx_apollo_builder.ai.broker import CHARS_PER_TOKEN, measure
from offsetx_apollo_builder.ai.quota import QuotaLimits, QuotaTracker
from offsetx_apollo_builder.ai.registry import ModelEntry, price_tokens
from offsetx_apollo_builder.outreach.providers import read_usage

PRICED = ModelEntry(id="planner", cost_per_1m_input_usd=2.0, cost_per_1m_output_usd=8.0)
FREE = ModelEntry(id="local", cost_per_1m_input_usd=0.0, cost_per_1m_output_usd=0.0)


# ── reading what the provider actually said ─────────────────────────────────


@pytest.mark.parametrize("block, shape", [
    ({"input_tokens": 700, "output_tokens": 26, "total_tokens": 726}, "openai responses"),
    ({"input_tokens": 700, "output_tokens": 26}, "anthropic messages"),
    ({"prompt_tokens": 700, "completion_tokens": 26, "total_tokens": 726}, "chat completions"),
])
def test_every_provider_shape_is_read(block, shape):
    """Three APIs, two names for the same two numbers. `D-36` was that none of
    them were read at all."""
    assert read_usage({"usage": block}) == {"tokens_in": 700, "tokens_out": 26}, shape


def test_a_response_with_no_usage_block_reports_nothing_rather_than_zero():
    """Zeros would be indistinguishable from a free call, and the caller needs
    to know it is about to estimate."""
    assert read_usage({"choices": [{"text": "hello"}]}) == {}
    assert read_usage({"usage": "not a block"}) == {}
    assert read_usage({}) == {}


def test_half_a_usage_block_is_not_used():
    """One number and a guess is worse than two guesses, because it looks
    measured."""
    assert read_usage({"usage": {"prompt_tokens": 700}}) == {}
    assert read_usage({"usage": {"completion_tokens": 26}}) == {}


def test_a_negative_count_is_refused_rather_than_credited():
    assert read_usage({"usage": {"input_tokens": -5, "output_tokens": 26}}) == {}


# ── one measurement, one price ──────────────────────────────────────────────


def test_the_provider_receipt_is_preferred_over_our_guess():
    """Character counting is wrong — it varies by model and by language and it
    cannot see the tokens the provider adds itself."""
    tokens_in, tokens_out, cost, source = measure(
        PRICED,
        reported={"tokens_in": 700, "tokens_out": 26},
        sent="x" * 40_000,   # a guess from this would say 10,000 tokens
        received="y" * 800,
    )
    assert (tokens_in, tokens_out) == (700, 26)
    assert source == "provider"
    assert cost == pytest.approx(0.001608)


def test_a_guess_is_labelled_a_guess():
    """`usage_source` is the difference between "the bill was $2.40" and "we
    think the bill was $2.40", and the owner is entitled to know which."""
    *_, source = measure(PRICED, reported=None, sent="x" * 2_800, received="y" * 104)
    assert source == "estimated"


def test_the_guess_uses_the_documented_ratio_and_nothing_else():
    tokens_in, tokens_out, _, _ = measure(
        PRICED, reported=None, sent="x" * 4_000, received="y" * 400)
    assert tokens_in == 4_000 // CHARS_PER_TOKEN
    assert tokens_out == 400 // CHARS_PER_TOKEN


def test_a_model_with_no_price_list_costs_nothing_rather_than_crashing():
    _, _, cost, _ = measure(None, reported={"tokens_in": 700, "tokens_out": 26},
                            sent="", received="")
    assert cost == 0.0


def test_pricing_does_not_need_the_object_to_be_a_model():
    """`measure` is handed whatever the caller has. Requiring a method would
    put the burden on every object that could ever stand in for a model."""
    double = SimpleNamespace(cost_per_1m_input_usd=2.0, cost_per_1m_output_usd=8.0)
    _, _, cost, _ = measure(double, reported={"tokens_in": 700, "tokens_out": 26},
                            sent="", received="")
    assert cost == pytest.approx(PRICED.price(700, 26))


def test_the_model_method_and_the_function_are_the_same_arithmetic():
    """One implementation. The method is a convenience over it, not a copy."""
    assert PRICED.price(1_234, 567) == price_tokens(
        1_234, 567, per_1m_in=2.0, per_1m_out=8.0)


def test_a_free_model_costs_zero_and_that_is_an_answer():
    assert FREE.price(1_000_000, 1_000_000) == 0.0


# ── the cap that could never be reached ─────────────────────────────────────


def _tracker() -> QuotaTracker:
    return QuotaTracker(Path(tempfile.mkdtemp()) / "quota.json")


def test_the_daily_spend_cap_now_stops_something(tmp_path):
    """`D-35`. The cap, the check and the usage bar were all real; the number
    fed to them was a hardcoded zero, so 5,000 calls counted as $0.00."""
    tracker = _tracker()
    limits = QuotaLimits(max_spend_usd_per_day=1.00)
    _, _, cost, _ = measure(PRICED, reported={"tokens_in": 700, "tokens_out": 26},
                            sent="", received="")

    for _ in range(700):
        tracker.record("openai", spend_usd=cost)

    allowed, reason = tracker.check("openai", limits)
    assert not allowed, "the owner's daily spend cap still refuses nothing"
    assert "daily spend cap reached" in reason


def test_recording_zero_would_never_reach_the_cap(tmp_path):
    """The regression, stated as the thing that must not come back."""
    tracker = _tracker()
    limits = QuotaLimits(max_spend_usd_per_day=1.00)
    for _ in range(5_000):
        tracker.record("openai", spend_usd=0.0)
    assert tracker.check("openai", limits)[0] is True
    assert tracker.usage("openai", limits)["day_spend_usd"] == 0.0


# ── the estimate, before the first action ───────────────────────────────────


def test_an_estimate_is_produced_before_anything_runs():
    estimate = estimate_run(PRICED, step_budget=50)
    assert isinstance(estimate, RunEstimate)
    assert estimate.step_budget == 50
    assert estimate.projected_cost_usd > 0
    assert estimate.projected_cost_usd == pytest.approx(
        estimate.cost_per_decision_usd * 50)


def test_the_estimate_carries_its_own_basis():
    """A number with no basis cannot be argued with, and an estimate nobody can
    argue with is one nobody checks."""
    estimate = estimate_run(PRICED, step_budget=10)
    assert estimate.basis
    assert "not a ceiling" in estimate.basis
    assert str(TYPICAL_DECISION_INPUT_CHARS // CHARS_PER_TOKEN) in estimate.basis


def test_the_estimate_is_priced_by_the_same_function_as_the_bill():
    """Not approximately the same. The same."""
    estimate = estimate_run(PRICED, step_budget=1)
    _, _, cost, _ = measure(
        PRICED, reported=None,
        sent="x" * TYPICAL_DECISION_INPUT_CHARS, received="x" * 400)
    assert estimate.cost_per_decision_usd == cost


def test_a_free_model_estimates_zero_and_says_so_plainly():
    estimate = estimate_run(FREE, step_budget=50)
    assert estimate.projected_cost_usd == 0.0
    assert "$0.0000" in estimate.describe()


def test_an_estimate_with_no_model_does_not_invent_a_number():
    assert estimate_run(None, step_budget=50).projected_cost_usd == 0.0


# ── through a real run ──────────────────────────────────────────────────────


import asyncio  # noqa: E402

from offsetx_apollo_builder.agent import AgentRun  # noqa: E402
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings  # noqa: E402
from offsetx_apollo_builder.ai.tiers import TrustTier  # noqa: E402
from offsetx_apollo_builder.browser.page import ActionResult  # noqa: E402
from offsetx_apollo_builder.browser.perceive import Node, Snapshot  # noqa: E402
from offsetx_apollo_builder.browser.trace import Trace  # noqa: E402


class _Registry:
    def get(self, provider_id):
        return SimpleNamespace(model=lambda model_id="": PRICED)


class _Broker:
    """A broker that reports usage the way the real one now does."""

    def __init__(self, answers, *, reports_usage=True):
        self.answers = list(answers)
        self.registry = _Registry()
        self.reports_usage = reports_usage

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner",
                                tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        text = self.answers.pop(0)
        extra = {}
        if self.reports_usage:
            tokens_in, tokens_out, cost, source = measure(
                PRICED, reported={"tokens_in": 700, "tokens_out": 26},
                sent="", received="")
            extra = {"tokens_in": tokens_in, "tokens_out": tokens_out,
                     "cost_usd": cost, "usage_source": source}
        return SimpleNamespace(
            text=text, provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
            **extra,
        )


class _Page:
    url = "https://acme.test/about"

    async def snapshot(self):
        return Snapshot(url=self.url, title="Acme",
                        nodes=[Node(handle=1, role="heading", name="Acme")])

    async def read(self, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url,
                            detail="read the page", text="Acme has 42 people")


def _run(tmp_path, answers, *, reports_usage=True, budget=8):
    trace = Trace.open(tmp_path / "t")
    agent = AgentRun(
        broker=_Broker(answers, reports_usage=reports_usage),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=_Page(), trace=trace, planner_provider_id="trusted",
    )
    outcome = asyncio.run(agent.run("how big is Acme", step_budget=budget))
    return outcome, trace


def _done():
    return json.dumps({"state": "done", "reason": "found it", "result": "42"})


def test_the_estimate_is_recorded_before_the_first_action(tmp_path):
    """The criterion. A number produced afterwards is a bill, not an estimate."""
    _, trace = _run(tmp_path, [_done()])

    steps = list(trace.read())
    started = steps[0]
    assert started.kind == "run_started"
    recorded = json.loads(trace.captured_text(started))
    assert recorded["estimate"]["projected_cost_usd"] > 0
    assert recorded["estimate"]["step_budget"] == 8
    # And in the line a person reads, not only in the machine-readable half.
    assert "estimate=" in started.detail


def test_the_outcome_carries_the_estimate_and_what_was_actually_spent(tmp_path):
    outcome, _ = _run(tmp_path, [_done()])

    assert outcome.estimate is not None
    assert outcome.spend_usd > 0
    assert outcome.estimate_error == pytest.approx(
        outcome.spend_usd - outcome.estimate.projected_cost_usd)
    assert outcome.to_dict()["estimate"]["model_id"] == "planner"


def test_the_trace_total_is_the_sum_of_what_each_call_reported(tmp_path):
    """The second criterion. Not a total nobody can decompose: the run's figure
    has to be the provider's numbers added up, step by step."""
    outcome, trace = _run(tmp_path, [json.dumps(
        {"state": "act", "action": "read", "args": {}, "reason": "look"}), _done()])

    per_step = [step.estimated_cost_usd for step in trace.read()
                if step.estimated_cost_usd]
    assert len(per_step) == 2, "each decision should carry its own cost"
    assert all(cost == pytest.approx(PRICED.price(700, 26)) for cost in per_step)
    assert outcome.spend_usd == pytest.approx(sum(per_step))


def test_a_broker_that_reports_no_usage_still_produces_a_figure(tmp_path):
    """An older or third-party broker does not have to grow fields to be valid
    — it just gets the estimate rather than the receipt."""
    outcome, _ = _run(tmp_path, [_done()], reports_usage=False)
    assert outcome.spend_usd > 0


def test_the_estimate_scales_with_the_budget_the_owner_set(tmp_path):
    small, _ = _run(tmp_path / "a", [_done()], budget=4)
    large, _ = _run(tmp_path / "b", [_done()], budget=40)
    assert large.estimate.projected_cost_usd == pytest.approx(
        small.estimate.projected_cost_usd * 10)
