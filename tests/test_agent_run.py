"""Acceptance evidence for S-02.02.01: a bounded browser run loop.

The tests deliberately use the real EgressBroker with only its transport
instantiation replaced by a deterministic provider. That keeps routing,
classification, payload construction and scanning in the path while avoiding a
network/API-key dependency. The Gate 2 test then drives real Chromium through
the production Page object.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass

import pytest

from offsetx_apollo_builder.agent.run import RunRefused, parse_decision, run_goal
from offsetx_apollo_builder.ai.broker import EgressBroker, WorkspaceEgressSettings
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.browser.page import ACTIONS, ActionResult, Page
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace


@dataclass
class FakeSnapshot:
    url: str = "https://example.com/"
    text: str = "Example page"

    def render(self) -> str:
        return self.text


class FakePage:
    def __init__(self, *, action_result: ActionResult | None = None) -> None:
        self.url = "https://example.com/"
        self.actions: list[tuple[str, object]] = []
        self.action_result = action_result

    async def snapshot(self) -> FakeSnapshot:
        return FakeSnapshot(url=self.url, text="heading Example\nbutton Continue [1]")

    async def back(self) -> ActionResult:
        self.actions.append(("back", None))
        return self.action_result or ActionResult(
            action="back", ok=True, url=self.url, detail="went back", took_ms=1
        )

    async def click(self, handle: int) -> ActionResult:
        self.actions.append(("click", handle))
        return self.action_result or ActionResult(
            action="click", ok=True, url=self.url, detail=f"clicked {handle}", took_ms=1
        )


class QueueProvider:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if not self.answers:
            raise AssertionError("the run asked for one decision too many")
        return self.answers.pop(0)


def broker_with_answers(monkeypatch, answers: list[str]) -> tuple[EgressBroker, QueueProvider]:
    registry = ProviderRegistry()
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda _provider_id: "test-key-never-used",
        timeout_seconds=5,
    )
    provider = QueueProvider(answers)
    monkeypatch.setattr(broker, "_instantiate", lambda _candidate: provider)
    return broker, provider


def settings() -> WorkspaceEgressSettings:
    # Browser snapshots are INTERNAL, so choose an A-tier provider. The test
    # fails if the run quietly reclassifies the page as public to widen routing.
    return WorkspaceEgressSettings(
        workspace_id="local",
        enabled_provider_ids=("mistral",),
        enabled_models={"mistral": ("mistral-large-latest",)},
    )


def decision(action: str, args: dict | None = None, reason: str = "continue") -> str:
    return json.dumps(
        {"status": "act", "action": action, "args": args or {}, "reason": reason}
    )


def test_step_budget_stops_before_one_extra_decision_or_action(tmp_path, monkeypatch):
    """The budget is host-enforced. An endlessly-acting model gets exactly N
    actions and N provider calls, never N+1."""
    broker, provider = broker_with_answers(
        monkeypatch,
        [decision("back"), decision("back")],
    )
    page = FakePage()
    trace = Trace.open(tmp_path, run_id="budget")

    result = asyncio.run(
        run_goal(
            goal="Keep moving until stopped",
            step_budget=2,
            page=page,
            broker=broker,
            settings=settings(),
            trace=trace,
        )
    )

    assert result.status == "budget_exhausted"
    assert result.steps_used == 2
    assert result.last_action == "back"
    assert "2/2" in result.reason
    assert provider.calls == 2
    assert page.actions == [("back", None), ("back", None)]
    assert trace.steps[-1].kind == "stop"


def test_every_decision_goes_through_broker_and_trace_records_model_and_cost(
    tmp_path, monkeypatch
):
    broker, provider = broker_with_answers(
        monkeypatch,
        [decision("back", reason="one step"), json.dumps({"status": "done", "reason": "finished"})],
    )
    page = FakePage()
    trace = Trace.open(tmp_path, run_id="audit")

    result = asyncio.run(
        run_goal(
            goal="Take one safe step and finish",
            step_budget=3,
            page=page,
            broker=broker,
            settings=settings(),
            trace=trace,
        )
    )

    assert result.status == "completed"
    assert result.steps_used == 1
    assert provider.calls == 2
    decisions = [step for step in trace.steps if step.kind == "decision"]
    assert len(decisions) == 2
    assert all(step.provider_id == "mistral" for step in decisions)
    assert all(step.model_id == "mistral-large-latest" for step in decisions)
    assert all(step.tokens_in > 0 and step.tokens_out > 0 for step in decisions)
    assert all(step.estimated_cost_usd is not None for step in decisions)
    assert sum(step.estimated_cost_usd or 0 for step in decisions) > 0

    persisted = trace.path.read_text(encoding="utf-8")
    assert '"estimated_cost_usd"' in persisted
    reopened = Trace.open(tmp_path, run_id="audit")
    assert reopened.summary()["estimated_cost_usd"] > 0


def test_browser_decisions_are_classified_internal(tmp_path, monkeypatch):
    broker, provider = broker_with_answers(
        monkeypatch,
        [json.dumps({"status": "done", "reason": "nothing needed"})],
    )
    seen: list[DataClass] = []
    original = broker.call

    def capture(request, workspace_settings, **kwargs):
        seen.append(request.data_class)
        return original(request, workspace_settings, **kwargs)

    monkeypatch.setattr(broker, "call", capture)
    result = asyncio.run(
        run_goal(
            goal="Inspect this logged-in page",
            step_budget=1,
            page=FakePage(),
            broker=broker,
            settings=settings(),
            trace=Trace.open(tmp_path, run_id="classification"),
        )
    )

    assert result.status == "completed"
    assert provider.calls == 1
    assert seen == [DataClass.INTERNAL]


def test_model_cannot_create_an_eleventh_browser_verb():
    assert len(ACTIONS) == 10
    with pytest.raises(RunRefused, match="closed browser vocabulary"):
        parse_decision(
            json.dumps(
                {
                    "status": "act",
                    "action": "evaluate",
                    "args": {"javascript": "document.cookie"},
                }
            )
        )


def test_model_cannot_confirm_its_own_consequential_click():
    with pytest.raises(RunRefused, match="forbidden argument"):
        parse_decision(
            json.dumps(
                {
                    "status": "act",
                    "action": "click",
                    "args": {"handle": 1, "confirmed": True},
                }
            )
        )


def test_existing_page_confirmation_boundary_stops_the_run(tmp_path, monkeypatch):
    broker, provider = broker_with_answers(monkeypatch, [decision("click", {"handle": 1})])
    page = FakePage(
        action_result=ActionResult(
            action="click",
            ok=False,
            url="https://example.com/",
            detail="clicking 'Send' sends or changes something. Confirm it first.",
            needs_confirmation=True,
        )
    )
    trace = Trace.open(tmp_path, run_id="confirmation")

    result = asyncio.run(
        run_goal(
            goal="Submit the form",
            step_budget=5,
            page=page,
            broker=broker,
            settings=settings(),
            trace=trace,
        )
    )

    assert result.status == "needs_confirmation"
    assert result.steps_used == 1
    assert provider.calls == 1
    assert page.actions == [("click", 1)]


def _browser_path() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


REAL_BROWSER = _browser_path()
needs_browser = pytest.mark.skipif(
    not REAL_BROWSER, reason="no Chrome, Edge, Brave or Chromium on this machine"
)

LIVE_PAGE = (
    "data:text/html,<html><head><title>Run Loop Gate 2</title></head>"
    "<body><h1 id=done>Real Chromium reached this page</h1></body></html>"
)


@needs_browser
def test_real_chromium_executes_the_bounded_decision(tmp_path, monkeypatch):
    """Gate 2: a decision obtained through the real broker path changes a real
    Chromium tab, then the hard one-step budget stops before another decision."""
    from offsetx_apollo_builder.browser.session import free_port, open_session

    broker, provider = broker_with_answers(
        monkeypatch,
        [decision("goto", {"url": LIVE_PAGE}, reason="open the requested page")],
    )

    async def work():
        profile = str(tmp_path / "profile")
        os.makedirs(profile, exist_ok=True)
        flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
        session = await open_session(
            profile_dir=profile,
            port=free_port(),
            headless=True,
            extra_flags=flags,
        )
        try:
            _, session_id = await session.new_tab()
            page = Page(connection=session.connection, session_id=session_id)
            await page.start()
            trace = Trace.open(tmp_path / "traces", run_id="live")
            result = await run_goal(
                goal="Open the Gate 2 page",
                step_budget=1,
                page=page,
                broker=broker,
                settings=settings(),
                trace=trace,
            )
            snapshot = await page.snapshot()
            return result, snapshot, trace
        finally:
            await session.close(quit_browser=True)

    result, snapshot, trace = asyncio.run(work())
    assert result.status == "budget_exhausted"
    assert result.steps_used == 1
    assert provider.calls == 1
    assert snapshot.title == "Run Loop Gate 2"
    assert "Real Chromium reached this page" in snapshot.render()
    assert any(step.kind == "action" and "opened Run Loop Gate 2" in step.detail for step in trace.steps)
