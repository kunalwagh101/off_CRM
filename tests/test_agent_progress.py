"""A run that stops making progress is stopped.  `S-11.01.02`

`S-11.01.01` stops the agent repeating one failing action. This stops the other
shape: several actions that each succeed and get nowhere — bouncing between two
pages, or clicking the same working button forever.

**The third acceptance criterion is the hard one and it is tested first.** The
story says a false positive here is worse than a wasted step, so the cases that
must *not* stop come before the cases that must. A detector that stops a run
filling in a long form is worse than no detector, because the run that dies is
the one that was working.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import (
    MAX_ARRIVALS_WITHOUT_PROGRESS,
    MAX_STEPS_WITHOUT_PROGRESS,
    made_progress,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace


# ── what counts as progress ─────────────────────────────────────────────────


def _progress(**overrides) -> bool:
    base = dict(facts_before=0, facts_after=0, url_after="https://a.test/x",
                visited={"https://a.test/x"}, signature="click(handle=1)",
                performed={"click(handle=1)"})
    base.update(overrides)
    return made_progress(**base)


def test_a_new_fact_is_progress():
    assert _progress(facts_after=1) is True


def test_a_page_the_run_has_not_visited_is_progress():
    assert _progress(url_after="https://a.test/y") is True


def test_a_page_the_run_has_already_visited_is_not_progress():
    """The distinction the story turns on. Bouncing between two pages is a
    different URL every step; it is still a cycle."""
    assert _progress(url_after="https://a.test/y",
                     visited={"https://a.test/x", "https://a.test/y"}) is False


def test_an_action_this_run_has_not_performed_is_progress():
    """The clause that keeps a form alive. Twelve fields is twelve signatures."""
    assert _progress(signature="type(handle=2,text='x')") is True


def test_doing_the_same_thing_again_on_the_same_page_is_not_progress():
    assert _progress() is False


def test_a_page_that_differs_only_by_tracking_is_not_a_new_page():
    """Otherwise a redirect that appends a campaign tag would read as progress
    forever, and the detector would never fire on the cycle it exists for."""
    assert _progress(url_after="https://a.test/x?utm_source=news") is False


# ── the harness ─────────────────────────────────────────────────────────────


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
        answer = self.answers.pop(0) if self.answers else _act("read")
        return SimpleNamespace(
            text=answer, provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Page:
    """A page that can be navigated between a few URLs."""

    def __init__(self, url="https://example.test/list"):
        self.url = url
        self.actions: list[str] = []

    async def snapshot(self):
        return Snapshot(url=self.url, title="Page",
                        nodes=[Node(handle=n, role="button", name=f"B{n}", backend_id=n)
                               for n in range(1, 15)])

    async def goto(self, url):
        self.actions.append(f"goto {url}")
        self.url = url
        return ActionResult(action="goto", ok=True, url=self.url, detail=f"opened {url}")

    async def click(self, handle, *, confirmed=False):
        self.actions.append(f"click {handle}")
        return ActionResult(action="click", ok=True, url=self.url, detail=f"clicked {handle}")

    async def type(self, handle, text, *, clear=True):
        self.actions.append(f"type {handle}")
        return ActionResult(action="type", ok=True, url=self.url, detail=f"typed into {handle}")

    async def read(self, *, limit=20_000):
        self.actions.append("read")
        return ActionResult(action="read", ok=True, url=self.url, detail="read",
                            text="Nothing new here.")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url,
                            detail="shot", screenshot=b"\x89PNG\r\n\x1a\nx")


def _act(action, **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _drive(page, answers, tmp_path, budget=40):
    trace = Trace.open(tmp_path / "trace")
    agent = AgentRun(
        broker=_Broker(answers),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=page, trace=trace, planner_provider_id="trusted",
    )
    return asyncio.run(agent.run("find the thing", step_budget=budget)), trace


# ── criterion 3 first: runs that must NOT be stopped ────────────────────────


def test_filling_a_long_form_is_never_called_stalled(tmp_path):
    """Fourteen successful steps on one page, no facts, no navigation — and every
    one of them different. This is the false positive the union definition of
    progress exists to prevent."""
    page = _Page()
    plan = [_act("type", handle=n, text=f"value {n}") for n in range(1, 14)]
    outcome, _ = _drive(page, plan, tmp_path)
    assert outcome.status not in {"stalled", "looping"}, (
        f"a run filling a form was stopped as {outcome.status}"
    )
    assert len([a for a in page.actions if a.startswith("type")]) == 13


def test_a_search_and_browse_pattern_is_never_called_looping(tmp_path):
    """list -> profile -> list -> profile -> list. The list is arrived at three
    times, which is the looping shape — but each profile is somewhere new, so
    the run is working."""
    page = _Page()
    plan = []
    for n in range(1, 4):
        plan.append(_act("goto", url=f"https://example.test/profile/{n}"))
        plan.append(_act("goto", url="https://example.test/list"))
    outcome, _ = _drive(page, plan, tmp_path)
    assert outcome.status not in {"stalled", "looping"}, (
        f"a working search-and-browse run was stopped as {outcome.status}"
    )


def test_progress_resets_the_counters(tmp_path):
    """Nine wasted steps then a real one must not leave the run one step from
    being called stalled for the rest of its life."""
    page = _Page()
    plan = [_act("click", handle=1)] * 9
    plan += [_act("goto", url="https://example.test/next")]
    plan += [_act("click", handle=1)] * 9
    outcome, _ = _drive(page, plan, tmp_path, budget=30)
    assert outcome.status not in {"stalled", "looping"}, outcome.message


# ── and now the runs that must be stopped ───────────────────────────────────


def test_clicking_the_same_working_button_forever_is_stalled(tmp_path):
    """Every action succeeds. Nothing is learned. `S-11.01.01` cannot catch this
    because nothing fails."""
    page = _Page()
    outcome, trace = _drive(page, [_act("click", handle=1)] * 30, tmp_path)

    assert outcome.status == "stalled", outcome.message
    assert "no new page" in outcome.message
    assert [s for s in trace.read() if s.kind == "stalled"]
    assert len(page.actions) <= MAX_STEPS_WITHOUT_PROGRESS + 2, (
        "the run kept spending budget after it had stopped progressing"
    )


def test_bouncing_between_two_pages_is_looping(tmp_path):
    """The cycle the story names. Two pages, back and forth, nothing gained."""
    page = _Page()
    plan = []
    for _ in range(8):
        plan.append(_act("goto", url="https://example.test/a"))
        plan.append(_act("goto", url="https://example.test/b"))
    outcome, trace = _drive(page, plan, tmp_path)

    assert outcome.status == "looping", outcome.message
    assert "https://example.test/" in outcome.message, "the trace does not name the cycle"
    assert [s for s in trace.read() if s.kind == "looping"]


def test_a_stopped_run_still_returns_what_it_found(tmp_path):
    """A run that found something and then went in circles should hand over what
    it found, not throw it away with the failure."""
    page = _Page()
    outcome, _ = _drive(page, [_act("click", handle=1)] * 30, tmp_path)
    assert outcome.status == "stalled"
    assert outcome.to_dict()["status"] == "stalled"
    assert outcome.actions > 0


def test_the_thresholds_are_ceilings_on_waste_not_on_work():
    assert MAX_STEPS_WITHOUT_PROGRESS >= 10, (
        "a shorter ceiling starts catching legitimate form filling"
    )
    assert MAX_ARRIVALS_WITHOUT_PROGRESS >= 3, "two arrivals is a detour, not a cycle"
    assert MAX_STEPS_WITHOUT_PROGRESS < 50, "a ceiling above the step budget never fires"


# ── against a real browser ──────────────────────────────────────────────────


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


@pytest.mark.skipif(not _browser(), reason="no Chrome, Edge, Brave or Chromium here")
def test_a_real_run_going_nowhere_is_stopped(tmp_path):
    """Against a real Chromium and the real `Page`, because the fake one proves
    the bookkeeping and not that the URLs a browser reports line up with it."""
    from offsetx_apollo_builder.browser.page import Page
    from offsetx_apollo_builder.browser.session import free_port, open_session

    document = "data:text/html,<button id=b>Go</button><p>Nothing here</p>"

    async def drive():
        with tempfile.TemporaryDirectory() as profile:
            flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
            session = await open_session(profile_dir=profile, port=free_port(),
                                         headless=True, extra_flags=flags)
            try:
                _, session_id = await session.new_tab()
                page = Page(connection=session.connection, session_id=session_id)
                await page.start()
                await page.goto(document)
                agent = AgentRun(
                    broker=_Broker([_act("scroll", down=1)] * 30),
                    settings=WorkspaceEgressSettings(
                        workspace_id="w", enabled_models={"trusted": ("planner",)}),
                    page=page, trace=Trace.open(tmp_path / "trace"),
                    planner_provider_id="trusted",
                )
                return await agent.run("find something", step_budget=30)
            finally:
                await session.close(quit_browser=True)

    outcome = asyncio.run(drive())
    assert outcome.status == "stalled", outcome.message
    assert outcome.actions <= MAX_STEPS_WITHOUT_PROGRESS + 2
