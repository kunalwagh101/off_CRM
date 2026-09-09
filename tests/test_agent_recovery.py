"""A failed action is recovered from, not repeated.  `S-11.01.01`

Before this, a failure became an observation and the loop carried on with
nothing stopping the model choosing the same failing action again. It does
choose it again: the refusal comes back as text, the next decision is made from
the same page, and the same conclusion follows — until the step budget is gone
and the run reports nothing.

Three rules, and the third is the one that is easy to fake:

* the same verb with the same arguments is spent after it fails once;
* three failures in a row end the run as `stuck`, which is a different thing to
  tell the owner than `budget_exhausted`;
* a **timeout** is retried with backoff, because a timeout is *no answer yet* —
  and every other browser failure is an answer, so waiting only spends the wait.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import (
    MAX_CONSECUTIVE_FAILURES,
    MAX_TRANSIENT_RETRIES,
    TRANSIENT_BACKOFF_SECONDS,
    Decision,
    action_signature,
    is_transient,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.cdp import CDPTimeout
from offsetx_apollo_builder.browser.page import ActionRefused, ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


# ── what makes two attempts the same attempt ────────────────────────────────


def test_the_same_verb_and_arguments_are_one_attempt():
    first = Decision(state="act", action="click", args={"handle": 7}, reason="try the button")
    again = Decision(state="act", action="click", args={"handle": 7}, reason="different words")
    assert action_signature(first) == action_signature(again), (
        "rewording why it wants to click element 7 does not make it a new thing to try"
    )


def test_argument_order_does_not_make_a_second_attempt():
    left = Decision(state="act", action="type", args={"handle": 3, "text": "hi"}, reason="")
    right = Decision(state="act", action="type", args={"text": "hi", "handle": 3}, reason="")
    assert action_signature(left) == action_signature(right)


def test_a_different_argument_is_a_different_attempt():
    first = Decision(state="act", action="click", args={"handle": 7}, reason="")
    other = Decision(state="act", action="click", args={"handle": 8}, reason="")
    assert action_signature(first) != action_signature(other)


# ── which failures are worth waiting on ─────────────────────────────────────


def test_a_timeout_is_transient_and_a_refusal_is_not():
    assert is_transient(CDPTimeout("no reply")) is True
    assert is_transient(asyncio.TimeoutError()) is True
    assert is_transient(ActionRefused("that element has no shape on the page")) is False
    assert is_transient(ValueError("nonsense")) is False


def test_a_refusal_is_never_retried_even_if_it_subclasses_a_timeout():
    """`ActionRefused` is checked first on purpose. It is an *answer* — a stale
    handle, a refused domain — and a second attempt produces the same refusal
    having spent the wait."""
    class OddRefusal(ActionRefused, TimeoutError):
        pass

    assert is_transient(OddRefusal("refused")) is False


def test_the_backoff_is_bounded_and_increasing():
    assert len(TRANSIENT_BACKOFF_SECONDS) >= 1
    assert list(TRANSIENT_BACKOFF_SECONDS) == sorted(TRANSIENT_BACKOFF_SECONDS)
    assert sum(TRANSIENT_BACKOFF_SECONDS) < 10, "a run must not sit in backoff"
    assert 0 < MAX_TRANSIENT_RETRIES <= 5
    assert MAX_CONSECUTIVE_FAILURES >= 2, "one failure is noise, not a verdict"


# ── through the real loop ───────────────────────────────────────────────────


class _Registry:
    def get(self, provider_id):
        if provider_id != "trusted":
            return None
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=2.0,
                                cost_per_1m_output_usd=8.0)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls += 1
        answer = self.answers.pop(0) if self.answers else _act("read")
        return SimpleNamespace(
            text=answer, provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Page:
    def __init__(self, *, fail_with=None, fail_times=0):
        self.url = "https://example.test/page"
        self.fail_with = fail_with
        self.fail_times = fail_times
        self.attempts = 0

    async def snapshot(self):
        return Snapshot(url=self.url, title="Page",
                        nodes=[Node(handle=7, role="button", name="Go", backend_id=1)])

    async def click(self, handle, *, confirmed=False):
        self.attempts += 1
        if self.fail_with is not None and self.attempts <= self.fail_times:
            raise self.fail_with
        return ActionResult(action="click", ok=True, url=self.url, detail="clicked")

    async def read(self, *, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url,
                            detail="read", text="Nothing useful here.")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url,
                            detail="shot", screenshot=b"\x89PNG\r\n\x1a\nx")


def _act(action, **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _drive(page, answers, tmp_path, budget=10):
    broker = _Broker(answers)
    trace = Trace.open(tmp_path / "trace")
    agent = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="w", enabled_models={"trusted": ("planner",)}
        ),
        page=page, trace=trace, planner_provider_id="trusted",
    )
    outcome = asyncio.run(agent.run("press the button", step_budget=budget))
    return outcome, trace, page


def test_the_same_failing_action_reaches_the_browser_only_once(tmp_path):
    """The whole story. The model asks for the same click four times; the
    browser is asked once."""
    page = _Page(fail_with=ActionRefused("that element has no shape"), fail_times=99)
    outcome, trace, page = _drive(
        page, [_act("click", handle=7)] * 4, tmp_path,
    )
    assert page.attempts == 1, f"the browser was asked {page.attempts} times"
    assert outcome.status == "stuck"
    refusals = [s for s in trace.read() if "already failed in this run" in s.detail]
    assert refusals, "the repeat was not recorded"


def test_three_failures_in_a_row_stop_the_run(tmp_path):
    """`stuck` rather than `budget_exhausted`: a run out of budget may just need
    a bigger one, a stuck run needs the goal or the page looked at."""
    page = _Page(fail_with=ActionRefused("no shape"), fail_times=99)
    outcome, trace, _ = _drive(
        page,
        [_act("click", handle=7), _act("click", handle=8), _act("click", handle=9)],
        tmp_path,
        budget=20,
    )
    assert outcome.status == "stuck"
    assert "3 failed actions in a row" in outcome.message
    assert [s for s in trace.read() if s.kind == "stuck"]
    assert outcome.actions < 20, "the run kept spending budget after it was stuck"


def test_a_success_clears_the_failure_streak(tmp_path):
    """Two failures then a success must not leave the run one failure from
    stopping for the rest of its life."""
    page = _Page(fail_with=ActionRefused("no shape"), fail_times=2)
    outcome, _, page = _drive(
        page,
        [_act("click", handle=1), _act("click", handle=2), _act("click", handle=3),
         _act("click", handle=4), _act("click", handle=5)],
        tmp_path, budget=20,
    )
    assert page.attempts == 5
    assert outcome.status != "stuck", "the streak was not reset by the success"


def test_a_timeout_is_retried_with_backoff_and_recorded_as_a_retry(tmp_path):
    """A timeout is no answer yet, so it is worth asking again — and the trace
    must not read as though the agent tried three different things."""
    page = _Page(fail_with=CDPTimeout("no reply"), fail_times=2)
    outcome, trace, page = _drive(page, [_act("click", handle=7)], tmp_path)

    assert page.attempts == 3, "the timeout was not retried"
    retries = [s for s in trace.read() if s.kind == "retry"]
    assert len(retries) == 2, f"expected 2 retry steps, got {len(retries)}"
    assert all("retrying in" in s.detail for s in retries)
    assert outcome.status != "stuck"


def test_a_refusal_is_not_retried_at_all(tmp_path):
    """The mirror. Waiting cannot change a stale handle, so the wait is not spent."""
    page = _Page(fail_with=ActionRefused("stale handle"), fail_times=99)
    _, trace, page = _drive(page, [_act("click", handle=7)], tmp_path)
    assert page.attempts == 1
    assert [s for s in trace.read() if s.kind == "retry"] == []


def test_a_timeout_that_never_clears_still_ends_the_run(tmp_path):
    """Backoff must not become a way to spend a run doing nothing."""
    page = _Page(fail_with=CDPTimeout("never"), fail_times=999)
    outcome, trace, page = _drive(
        page,
        [_act("click", handle=1), _act("click", handle=2), _act("click", handle=3)],
        tmp_path, budget=20,
    )
    assert outcome.status == "stuck"
    assert page.attempts == 3 * (MAX_TRANSIENT_RETRIES + 1)
