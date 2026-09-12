"""A resumed run does not do again what it already did.  `S-11.05.02`

`S-11.01.03` brings a killed run back with its facts. This is the other half of
that: a resumed run re-decides from the **live page**, and the page does not
remember that the message was already sent — the Send button is still sitting
there looking unpressed. Nothing in the browser can tell the agent it has
already done this. Only the trace can.

The rule is about **crossing the resume point**, not about repetition inside one
continuous run: within a single run the agent is entitled to click twice, and the
loop's own bookkeeping already governs that.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun, replay
from offsetx_apollo_builder.agent.run import EFFECTFUL_ACTIONS
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ACTIONS, ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


# ── which verbs can act on the world ────────────────────────────────────────


def test_every_effectful_verb_is_a_real_verb():
    for action in EFFECTFUL_ACTIONS:
        assert action in ACTIONS, action


def test_the_two_verbs_that_can_send_without_changing_the_url_are_covered():
    """`click` is the obvious one. `press` matters because Enter in a form is a
    submit, and it does not go through the gate that `click` does."""
    assert "click" in EFFECTFUL_ACTIONS
    assert "press" in EFFECTFUL_ACTIONS


def test_navigation_is_deliberately_not_blocked():
    """Navigating is how a resumed run gets back to where it was working.
    Blocking a repeat of it would make resuming useless — and that choice has a
    cost, written down where it is made: a URL whose GET has a side effect is
    not protected by this story."""
    assert "goto" not in EFFECTFUL_ACTIONS


def test_looking_is_never_blocked():
    for observing in ("read", "screenshot", "wait_for"):
        assert observing not in EFFECTFUL_ACTIONS


# ── harness ─────────────────────────────────────────────────────────────────


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
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        if not self.answers:
            raise AssertionError("the run asked for more decisions than the test scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Outbox:
    """Stands in for the world. Counts what actually left."""

    def __init__(self):
        self.sent: list[str] = []


class _Page:
    def __init__(self, outbox: _Outbox):
        self.url = "https://mail.example.test/compose"
        self.outbox = outbox

    async def snapshot(self):
        return Snapshot(url=self.url, title="Compose",
                        nodes=[Node(handle=4, role="button", name="Send message", backend_id=4),
                               Node(handle=5, role="link", name="Inbox", backend_id=5)])

    async def goto(self, url):
        self.url = url
        return ActionResult(action="goto", ok=True, url=url, detail=f"opened {url}")

    async def click(self, handle, *, confirmed=False):
        if handle == 4:
            self.outbox.sent.append("message")
        return ActionResult(action="click", ok=True, url=self.url, detail=f"clicked {handle}")

    async def press(self, key):
        if key == "Enter":
            self.outbox.sent.append("message")
        return ActionResult(action="press", ok=True, url=self.url, detail=f"pressed {key}")

    async def read(self, *, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url, detail="read",
                            text="Draft ready.")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url, detail="shot",
                            screenshot=b"\x89PNG\r\n\x1a\nx")


def _act(action, **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _done():
    return json.dumps({"state": "done", "reason": "sent", "result": "sent"})


def _agent(page, answers, trace):
    return AgentRun(
        broker=_Broker(answers),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=page, trace=trace, planner_provider_id="trusted",
    )


class _Killed(RuntimeError):
    """The process going away. Nothing gets to tidy up."""


def _send_then_die(root, outbox, *, verb="click", **args):
    """Send the message, then die before the run can finish."""
    page = _Page(outbox)
    trace = Trace.open(root)
    agent = _agent(page, [_act(verb, **args), _act("read")], trace)

    real = page.snapshot
    calls = {"n": 0}

    async def dying():
        calls["n"] += 1
        if calls["n"] > 2:
            raise _Killed("the process went away")
        return await real()

    page.snapshot = dying
    with pytest.raises(_Killed):
        asyncio.run(agent.run("send the message", step_budget=10))
    return trace


# ── the story ───────────────────────────────────────────────────────────────


def test_a_resumed_run_does_not_send_the_message_twice(tmp_path):
    """The whole point, and the reason the indicator is *duplicate side effects,
    target zero*."""
    root, outbox = tmp_path / "traces", _Outbox()
    trace = _send_then_die(root, outbox, verb="click", handle=4)
    assert outbox.sent == ["message"], "the fixture did not send once"

    reopened = Trace.open(root, run_id=trace.run_id)
    agent = _agent(_Page(outbox), [_act("click", handle=4), _done()], reopened)
    asyncio.run(agent.resume())

    assert outbox.sent == ["message"], f"the message was sent {len(outbox.sent)} times"
    refused = [s for s in Trace.open(root, run_id=trace.run_id).read()
               if s.kind == "duplicate_refused"]
    assert refused, "the duplicate was not recorded"
    assert "already performed before this run was resumed" in refused[0].detail


def test_pressing_enter_again_after_a_resume_does_not_submit_twice(tmp_path):
    """`press` matters because Enter in a form is a submit and does not go
    through the gate `click` does."""
    root, outbox = tmp_path / "traces", _Outbox()
    trace = _send_then_die(root, outbox, verb="press", key="Enter")
    assert outbox.sent == ["message"]

    agent = _agent(_Page(outbox), [_act("press", key="Enter"), _done()],
                   Trace.open(root, run_id=trace.run_id))
    asyncio.run(agent.resume())
    assert outbox.sent == ["message"]


def test_a_different_action_after_a_resume_is_allowed(tmp_path):
    """The guard must not turn a resumed run into a run that can do nothing."""
    root, outbox = tmp_path / "traces", _Outbox()
    trace = _send_then_die(root, outbox, verb="click", handle=4)

    page = _Page(outbox)
    agent = _agent(page, [_act("click", handle=5), _done()],
                   Trace.open(root, run_id=trace.run_id))
    outcome = asyncio.run(agent.resume())
    assert outcome.status in {"completed", "incomplete"}
    assert outbox.sent == ["message"], "clicking a different thing sent something"


def test_navigating_back_to_where_it_was_still_works(tmp_path):
    """If `goto` were blocked, a resumed run could not return to its work."""
    root, outbox = tmp_path / "traces", _Outbox()
    trace = _send_then_die(root, outbox, verb="click", handle=4)

    page = _Page(outbox)
    agent = _agent(page, [_act("goto", url="https://mail.example.test/compose"), _done()],
                   Trace.open(root, run_id=trace.run_id))
    outcome = asyncio.run(agent.resume())
    assert outcome.status in {"completed", "incomplete"}
    assert not [s for s in Trace.open(root, run_id=trace.run_id).read()
                if s.kind == "duplicate_refused"], "navigation was refused as a duplicate"


def test_within_one_run_the_guard_does_not_fire(tmp_path):
    """The rule is about crossing the resume point, not repetition inside one
    continuous run — the loop's own bookkeeping governs that."""
    outbox = _Outbox()
    page = _Page(outbox)
    trace = Trace.open(tmp_path / "traces")
    agent = _agent(page, [_act("click", handle=4), _act("click", handle=4), _done()], trace)
    asyncio.run(agent.run("send it twice on purpose", step_budget=10))

    assert not [s for s in trace.read() if s.kind == "duplicate_refused"]
    assert len(outbox.sent) == 2, "an uninterrupted run was blocked from repeating itself"


def test_the_inherited_set_comes_from_the_trace_and_not_from_memory(tmp_path):
    """A fresh process has nothing in memory. Replay is the only source."""
    root, outbox = tmp_path / "traces", _Outbox()
    trace = _send_then_die(root, outbox, verb="click", handle=4)
    state = replay(Trace.open(root, run_id=trace.run_id))
    assert any("click" in signature for signature in state.performed_signatures), (
        "the trace did not record what was performed"
    )
