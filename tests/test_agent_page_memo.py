"""A page is read once per run.  `S-11.02.04`

The budget is the point. A run is capped at `MAX_RUN_STEPS`, and a step spent
re-reading a page the run has already read is a step not spent finding anything —
and the model pays for the same text twice on the way in.

Two things here are easy to get wrong and both are tested directly rather than
implied. **A URL that differs only by how somebody arrived is the same page**, so
tracking parameters are stripped. And **a page can change without its URL
changing** — "load more", a filter, a tab — so acting on a page forgets it,
because serving a stale capture is worse than reading again.
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
    MAX_CAPTURES,
    PAGE_CHANGING_ACTIONS,
    TRACKING_PARAMETERS,
    canonical_page_url,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ACTIONS, ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace


# ── the key a page is remembered under ──────────────────────────────────────


def test_a_url_that_differs_only_by_how_you_arrived_is_the_same_page():
    same = canonical_page_url("https://example.test/post?id=7")
    assert canonical_page_url("https://example.test/post?id=7&utm_source=news") == same
    assert canonical_page_url("https://EXAMPLE.test/post?utm_campaign=q3&id=7") == same
    assert canonical_page_url("https://example.test/post?id=7#comments") != same
    assert canonical_page_url("https://example.test/post?id=7&fbclid=abc") == same


def test_query_order_is_preserved_for_order_sensitive_servers():
    """Query order can affect signatures and repeated-key interpretation."""
    assert canonical_page_url("https://e.test/x?a=1&b=2") != canonical_page_url(
        "https://e.test/x?b=2&a=1"
    )


def test_a_parameter_that_changes_the_page_is_never_stripped():
    """The bias is one-directional on purpose: under-deduplicating costs a page
    read, over-deduplicating returns the **wrong text** from the memo. So `ref`,
    `id`, `page`, `q` and `source` — all real parameters on real sites — stay."""
    for parameter in ("ref", "id", "page", "q", "source", "sort", "lang", "v"):
        assert parameter not in TRACKING_PARAMETERS, parameter
        assert canonical_page_url(f"https://e.test/x?{parameter}=1") != canonical_page_url(
            "https://e.test/x"
        ), parameter


def test_a_url_with_no_host_is_left_alone():
    """`data:` and `about:` URLs are their own identity; normalising one could
    only lose information or collide it with a real page."""
    for url in ("data:text/html,<p>x</p>", "about:blank", ""):
        assert canonical_page_url(url) == url


def test_every_page_changing_verb_is_a_real_verb():
    """A typo here would silently stop a page being forgotten after it changed."""
    for action in PAGE_CHANGING_ACTIONS:
        assert action in ACTIONS, action
    assert "goto" not in PAGE_CHANGING_ACTIONS, (
        "goto changes the URL, so it lands on a different memo key anyway"
    )
    assert "read" not in PAGE_CHANGING_ACTIONS


# ── the memo, through the real loop ─────────────────────────────────────────


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
        self.calls = []
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls.append(request)
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="egress-1",
        )


class _Page:
    """Counts what it is actually asked to do."""

    def __init__(self, url="https://research.example.test/company?utm_source=news"):
        self.url = url
        self.reads = 0
        self.scrolls = 0
        self.body = "Company: Acme Ltd Employees: 42"

    async def snapshot(self):
        return Snapshot(url=self.url, title="Company",
                        nodes=[Node(handle=1, role="button", name="More", backend_id=1)])

    async def read(self, *, limit=20_000):
        self.reads += 1
        return ActionResult(action="read", ok=True, url=self.url,
                            detail="read the page", text=self.body)

    async def scroll(self, *, down=1):
        self.scrolls += 1
        self.body = "Company: Acme Ltd Employees: 42 Revenue: 9m"
        return ActionResult(action="scroll", ok=True, url=self.url, detail="scrolled")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url,
                            detail="fixture", screenshot=b"\x89PNG\r\n\x1a\nfixture")


def _act(action: str, **args) -> str:
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _done() -> str:
    return json.dumps({"state": "done", "reason": "finished", "result": "ok"})


def _settings():
    return WorkspaceEgressSettings(
        workspace_id="w", enabled_models={"trusted": ("planner",)},
    )


def _run(page, answers, tmp_path, **kwargs):
    broker = _Broker(answers)
    trace = Trace.open(tmp_path / "trace")
    agent = AgentRun(broker=broker, settings=_settings(), page=page, trace=trace,
                     planner_provider_id="trusted")
    outcome = asyncio.run(agent.run("find the employee count", step_budget=8, **kwargs))
    return outcome, broker, trace


def test_reading_the_same_page_twice_asks_the_page_once(tmp_path):
    """The story, in one assertion. Two reads decided, one read performed."""
    page = _Page()
    outcome, _, trace = _run(page, [_act("read"), _act("read"), _done()], tmp_path)

    assert page.reads == 1, f"the page was asked {page.reads} times"
    assert outcome.status == "completed"
    reused = [step for step in trace.read() if "reused the capture" in step.detail]
    assert len(reused) == 1, "the reuse was not recorded in the trace"


def test_the_reused_capture_carries_the_same_text(tmp_path):
    """A memo that answers with something other than what the page said would be
    worse than no memo."""
    page = _Page()
    # The trace this run wrote, not a fresh one: `Trace.open` starts a new run
    # id, so re-opening the root would read an empty directory.
    _, _, trace = _run(page, [_act("read"), _act("read"), _done()], tmp_path)
    reused = next(step for step in trace.read() if "reused the capture" in step.detail)
    assert f"({len(page.body)} characters)" in reused.detail


def test_acting_on_a_page_forgets_it(tmp_path):
    """A page can change while its URL does not. `scroll` here loads more, and
    the second read must see the new text rather than the memo."""
    page = _Page()
    _run(page, [_act("read"), _act("scroll", down=1), _act("read"), _done()], tmp_path)

    assert page.scrolls == 1
    assert page.reads == 2, "the memo served a page that had changed underneath it"


def test_a_different_page_is_read_on_its_own(tmp_path):
    """The memo must not answer for a page it has never seen."""
    page = _Page()

    async def drive():
        broker = _Broker([_act("read"), _act("read"), _done()])
        trace = Trace.open(tmp_path / "trace")
        agent = AgentRun(broker=broker, settings=_settings(), page=page, trace=trace,
                         planner_provider_id="trusted")
        original_read = page.read

        async def read_then_move(*, limit=20_000):
            answer = await original_read(limit=limit)
            page.url = "https://research.example.test/other"
            return answer

        page.read = read_then_move
        return await agent.run("find things", step_budget=8)

    asyncio.run(drive())
    assert page.reads == 2, "a second, different page was answered from the memo"


def test_the_memo_cannot_grow_without_bound():
    assert 0 < MAX_CAPTURES <= 64, (
        "the memo holds screenshots; it needs a ceiling that is not the step budget"
    )


# ── against a real browser ──────────────────────────────────────────────────


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


@pytest.mark.skipif(not _browser(), reason="no Chrome, Edge, Brave or Chromium here")
def test_a_real_page_is_read_once_through_the_real_loop(tmp_path):
    """The same property against a real Chromium and the real `Page`, because a
    fake page proves the loop's bookkeeping and not that it works on a browser.
    """
    from offsetx_apollo_builder.browser.page import Page
    from offsetx_apollo_builder.browser.session import free_port, open_session

    document = "data:text/html,<h1>Acme</h1><p>Employees: 42</p>"
    seen: list[str] = []

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

                original = page.read

                async def counted(*, limit=20_000):
                    seen.append(page.url)
                    return await original(limit=limit)

                page.read = counted
                broker = _Broker([_act("read"), _act("read"), _done()])
                agent = AgentRun(broker=broker, settings=_settings(), page=page,
                                 trace=Trace.open(tmp_path / "trace"),
                                 planner_provider_id="trusted")
                return await agent.run("read the page", step_budget=8)
            finally:
                await session.close(quit_browser=True)

    outcome = asyncio.run(drive())
    assert outcome.status == "completed"
    assert len(seen) == 1, f"the real page was read {len(seen)} times"
