"""Acceptance evidence for S-11.02.02: every returned fact carries its source."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult, Page
from offsetx_apollo_builder.browser.perceive import Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Step, Trace, TraceIntegrityError


class _Registry:
    def get(self, provider_id):
        if provider_id != "trusted":
            return None
        model = SimpleNamespace(
            id="planner",
            cost_per_1m_input_usd=1.0,
            cost_per_1m_output_usd=2.0,
        )
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [
            SimpleNamespace(
                id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0
            )
        ], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls.append(request.instructions)
        return SimpleNamespace(
            text=self.answers.pop(0),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            tier="A",
            policy="full",
            data_class=request.data_class.value,
            duration_ms=3,
            payload_fields=["instructions"],
            attempts=[],
            rejected=[],
            log_id="egress-1",
        )


class _Page:
    def __init__(self):
        self.url = "https://research.example.test/a"
        self.pages = {
            "https://research.example.test/a": "Company: Acme Ltd",
            "https://research.example.test/b": "Employees: 42",
        }

    async def snapshot(self):
        return Snapshot(url=self.url, title="Fixture", nodes=[])

    async def read(self, *, limit=20_000):
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read fixture page",
            text=self.pages[self.url][:limit],
        )

    async def screenshot(self):
        return ActionResult(
            action="screenshot",
            ok=True,
            url=self.url,
            detail="fixture screenshot",
            screenshot=b"\x89PNG\r\n\x1a\nfixture",
        )

    async def goto(self, url):
        self.url = str(url)
        return ActionResult(action="goto", ok=True, url=self.url, detail="navigated")


def _finding(value, quote, step_id):
    return {
        "value": value,
        "source_step_id": step_id,
        "quote": quote,
        "kind": "observed",
        "confidence": 0.8,
    }


def _act(action, *, args=None, record=None):
    body = {"state": "act", "action": action, "args": args or {}, "reason": action}
    if record is not None:
        body["record"] = record
    return json.dumps(body)


def _done(record=None):
    body = {"state": "done", "reason": "complete"}
    if record is not None:
        body["record"] = record
    return json.dumps(body)


def _run(tmp_path, answers, *, fields, budget=None, page=None):
    broker = _Broker(answers)
    page = page or _Page()
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
        page=page,
        trace=Trace.open(tmp_path),
    )
    outcome = asyncio.run(
        run.run(
            "Return the requested facts",
            step_budget=budget or len(answers),
            result_schema=fields,
        )
    )
    return outcome, run, broker


def test_trace_step_ids_are_stable_and_legacy_lines_get_deterministic_ids(tmp_path):
    trace = Trace.open(tmp_path, run_id="run_legacy")
    trace.path.write_text(
        '{"at":"2026-09-06T00:00:00+00:00","kind":"read","url":"https://a.test"}\n'
        '{"at":"2026-09-06T00:00:01+00:00","kind":"click","url":"https://a.test"}\n',
        encoding="utf-8",
    )

    reopened = Trace.open(tmp_path, run_id="run_legacy")
    assert [step.step_id for step in reopened.steps] == ["step-000000", "step-000001"]
    added = reopened.append(Step(kind="read", url="https://b.test"))
    assert added.step_id == "step-000002"

    again = Trace.open(tmp_path, run_id="run_legacy")
    assert [step.step_id for step in again.steps] == [
        "step-000000",
        "step-000001",
        "step-000002",
    ]
    assert again.resolve("step-000002").url == "https://b.test"


def test_page_evidence_is_private_and_not_embedded_in_the_jsonl(tmp_path):
    trace = Trace.open(tmp_path)
    step = trace.append(
        Step(kind="action", url="https://a.test", detail="read 18 characters"),
        screenshot=b"\x89PNG\r\n\x1a\nprivate",
        captured_text="private customer page text",
    )

    assert step.step_id == "step-000000"
    assert step.screenshot == "0000.png"
    assert step.capture == "0000.txt"
    assert trace.captured_text(step) == "private customer page text"
    assert "private customer page text" not in trace.path.read_text(encoding="utf-8")
    assert oct((trace.directory / step.screenshot).stat().st_mode)[-3:] == "600"
    assert oct((trace.directory / step.capture).stat().st_mode)[-3:] == "600"

    hostile = Step(kind="action", capture="../outside.txt")
    with pytest.raises(TraceIntegrityError, match="not local"):
        trace.captured_text(hostile)


def test_returned_finding_resolves_url_time_step_and_screenshot_from_trace(tmp_path):
    outcome, run, broker = _run(
        tmp_path,
        [
            _act("read"),
            _done({"company": _finding("Acme Ltd", "Company: Acme Ltd", "step-000002")}),
        ],
        fields=("company",),
        budget=2,
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd"}
    finding = outcome.findings["company"]
    assert finding.field == "company"
    assert finding.value == "Acme Ltd"
    assert finding.source.url == "https://research.example.test/a"
    assert finding.source.step_id == "step-000002"
    assert finding.source.screenshot == "0002.png"
    assert finding.source.quote == "Company: Acme Ltd"
    parsed = datetime.fromisoformat(finding.source.captured_at)
    assert parsed.tzinfo is not None
    assert (run.trace.directory / finding.source.screenshot).is_file()
    assert "SOURCE EVIDENCE" in broker.calls[1]
    assert "step_id=step-000002" in broker.calls[1]


def test_an_unresolvable_source_is_refused_instead_of_returned(tmp_path):
    invented = "THIS-VALUE-MUST-NOT-SURVIVE"
    outcome, run, _ = _run(
        tmp_path,
        [
            _done(
                {
                    "company": _finding(
                        invented,
                        "invented quote",
                        "step-999999",
                    )
                }
            )
        ],
        fields=("company",),
        budget=1,
    )

    assert outcome.status == "incomplete"
    assert outcome.record == {}
    assert outcome.findings == {}
    assert outcome.unfilled_fields == ("company",)
    assert outcome.unsourced_fields == ("company",)
    assert any(step.kind == "result_field_unsourced" for step in run.trace.steps)
    assert invented not in run.trace.path.read_text(encoding="utf-8")


def test_a_sourced_fact_survives_navigation_without_relying_on_model_memory(tmp_path):
    answers = [
        _act("read"),
        _act(
            "goto",
            args={"url": "https://research.example.test/b"},
            record={"company": _finding("Acme Ltd", "Company: Acme Ltd", "step-000002")},
        ),
        _act("read"),
        _done({"employees": _finding("42", "Employees: 42", "step-000006")}),
    ]
    outcome, _, broker = _run(
        tmp_path,
        answers,
        fields=("company", "employees"),
        budget=4,
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd", "employees": "42"}
    assert outcome.findings["company"].source.url.endswith("/a")
    assert outcome.findings["employees"].source.url.endswith("/b")
    assert "Already saved with resolvable provenance: company" in broker.calls[2]
    assert "Still required: employees" in broker.calls[2]


# Gate 2 — a real Chromium must actually produce the evidence files and the
# source metadata. A passing mock is not enough for E-11.
def _browser_path() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


REAL_BROWSER = _browser_path()
needs_browser = pytest.mark.skipif(
    not REAL_BROWSER, reason="no Chrome, Edge, Brave or Chromium on this machine"
)


async def _drive(work):
    from offsetx_apollo_builder.browser.session import free_port, open_session

    with tempfile.TemporaryDirectory() as profile:
        is_root = getattr(os, "geteuid", lambda: 1)() == 0
        flags = ("--no-sandbox",) if is_root else ()
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
            return await work(page)
        finally:
            await session.close(quit_browser=True)


@needs_browser
def test_provenance_is_bound_to_real_chromium_evidence(tmp_path):
    broker = _Broker(
        [
            _act("read"),
            _done({"company": _finding("Acme Ltd", "Acme Ltd", "step-000002")}),
        ]
    )

    async def work(page: Page):
        await page.goto(
            "data:text/html,<html><body><h1>Acme Ltd</h1><p>Evidence page</p></body></html>"
        )
        run = AgentRun(
            broker=broker,
            settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
            page=page,
            trace=Trace.open(tmp_path),
        )
        outcome = await run.run(
            "Return the company shown on the page",
            step_budget=2,
            result_schema=("company",),
        )
        return outcome, run

    outcome, run = asyncio.run(_drive(work))

    assert outcome.status == "completed"
    finding = outcome.findings["company"]
    step = run.trace.resolve(finding.source.step_id)
    assert step is not None
    assert step.url.startswith("data:text/html")
    assert finding.source.url == step.url
    assert finding.source.captured_at == step.at
    assert finding.source.screenshot == step.screenshot
    assert (run.trace.directory / step.screenshot).read_bytes().startswith(b"\x89PNG")
    assert "Acme Ltd" in run.trace.captured_text(step)
