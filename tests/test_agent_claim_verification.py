"""Acceptance evidence for S-11.02.03: unsupported browser claims are refused."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult, Page
from offsetx_apollo_builder.browser.perceive import Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace
from trace_ids import CITE, fill_citations, step_id_of


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
            text=fill_citations(self.answers.pop(0), request.instructions),
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
    def __init__(self, text: str, *, cut: bool = False):
        self.url = "https://research.example.test/company"
        self.text = text
        self.cut = cut

    async def snapshot(self):
        return Snapshot(url=self.url, title="Fixture", nodes=[])

    async def read(self, *, limit=20_000):
        text = self.text[:limit]
        if self.cut and not text.rstrip().endswith("… (cut)"):
            text += "\n… (cut)"
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail=f"read {min(len(self.text), limit)} characters" + (" (cut)" if self.cut else ""),
            text=text,
        )

    async def screenshot(self):
        return ActionResult(
            action="screenshot",
            ok=True,
            url=self.url,
            detail="fixture screenshot",
            screenshot=b"\x89PNG\r\n\x1a\nfixture",
        )


def _finding(
    value: str,
    quote: str,
    *,
    step_id: str = CITE,
    kind: str = "observed",
    inputs: tuple[str, ...] = (),
    confidence: float = 0.99,
):
    item = {
        "value": value,
        "source_step_id": step_id,
        "quote": quote,
        "kind": kind,
        "confidence": confidence,
    }
    if inputs:
        item["inputs"] = list(inputs)
    return item


def _read() -> str:
    return json.dumps(
        {"state": "act", "action": "read", "args": {}, "reason": "read evidence"}
    )


def _done(record) -> str:
    return json.dumps({"state": "done", "reason": "done", "record": record})


def _run(tmp_path, *, text, record, fields, cut=False):
    broker = _Broker([_read(), _done(record)])
    page = _Page(text, cut=cut)
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
        page=page,
        trace=Trace.open(tmp_path),
    )
    outcome = asyncio.run(
        run.run(
            "Return the requested facts",
            step_budget=2,
            result_schema=fields,
        )
    )
    return outcome, run, broker


def test_supported_fact_survives_case_and_whitespace_normalisation(tmp_path):
    outcome, run, _ = _run(
        tmp_path,
        text="Company:\nACME    LTD\nEmployees: 42",
        record={"company": _finding("acme ltd", "ACME LTD")},
        fields=("company",),
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "acme ltd"}
    assert outcome.unsupported_fields == ()
    assert not any(step.kind == "result_field_unsupported" for step in run.trace.steps)


def test_number_inside_a_larger_number_is_refused_even_at_high_confidence(tmp_path):
    outcome, run, _ = _run(
        tmp_path,
        text="Employees: 420",
        record={
            "employees": _finding(
                "42",
                "Employees: 420",
                confidence=1.0,
            )
        },
        fields=("employees",),
    )

    assert outcome.status == "incomplete"
    assert outcome.record == {}
    assert outcome.unsupported_fields == ("employees",)
    assert "Unsupported by the cited captured page: employees." in outcome.message
    step = next(step for step in run.trace.steps if step.kind == "result_field_unsupported")
    assert step.ok is False
    assert "employees" in step.detail


def test_immediate_negation_is_not_erased_by_normalisation(tmp_path):
    outcome, _, _ = _run(
        tmp_path,
        text="The company is not profitable this year.",
        record={
            "profitability": _finding(
                "profitable",
                "The company is not profitable this year.",
            )
        },
        fields=("profitability",),
    )

    assert outcome.status == "incomplete"
    assert outcome.unsupported_fields == ("profitability",)


def test_an_unrelated_quote_cannot_borrow_a_value_from_elsewhere_on_the_page(tmp_path):
    outcome, _, _ = _run(
        tmp_path,
        text="Phone: +1 555 0100. Headquarters: Mumbai.",
        record={
            "headquarters": _finding(
                "Mumbai",
                "Phone: +1 555 0100",
            )
        },
        fields=("headquarters",),
    )

    assert outcome.status == "incomplete"
    assert outcome.unsupported_fields == ("headquarters",)


def test_missing_support_in_a_truncated_capture_is_reported_as_inconclusive(tmp_path):
    outcome, run, _ = _run(
        tmp_path,
        text="Company: Acme Ltd",
        cut=True,
        record={
            "phone": _finding(
                "+1 555 0199",
                "Phone: +1 555 0199",
            )
        },
        fields=("phone",),
    )

    assert outcome.status == "incomplete"
    assert outcome.unsupported_fields == ()
    assert outcome.truncated_fields == ("phone",)
    assert "absence in the capture is not treated as invention" in outcome.message
    assert any(step.kind == "result_field_unverified_truncated" for step in run.trace.steps)


def test_derived_finding_is_allowed_only_from_individually_verified_inputs(tmp_path):
    outcome, _, _ = _run(
        tmp_path,
        text="India offices: 10\nEurope offices: 5",
        record={
            "india_offices": _finding("10", "India offices: 10"),
            "europe_offices": _finding("5", "Europe offices: 5"),
            "total_offices": _finding(
                "15",
                "India offices: 10\nEurope offices: 5",
                kind="derived",
                inputs=("india_offices", "europe_offices"),
            ),
        },
        fields=("india_offices", "europe_offices", "total_offices"),
    )

    assert outcome.status == "completed"
    assert outcome.record == {
        "india_offices": "10",
        "europe_offices": "5",
        "total_offices": "15",
    }
    assert outcome.findings["total_offices"].kind == "derived"
    assert outcome.findings["total_offices"].inputs == (
        "india_offices",
        "europe_offices",
    )


def test_derived_finding_with_an_unverified_input_is_refused(tmp_path):
    outcome, run, _ = _run(
        tmp_path,
        text="India offices: 10",
        record={
            "total_offices": _finding(
                "15",
                "India offices: 10",
                kind="derived",
                inputs=("india_offices",),
            )
        },
        fields=("india_offices", "total_offices"),
    )

    assert outcome.status == "incomplete"
    assert outcome.record == {}
    assert outcome.derived_unverified_fields == ("total_offices",)
    assert any(step.kind == "result_field_derived_unverified" for step in run.trace.steps)


# Gate 2 — a real Chromium read must be the source of the evidence that rejects
# the model claim. A mock-only verifier is not enough for autonomous browsing.
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
def test_real_chromium_page_refuses_a_plausible_but_unsupported_number(tmp_path):
    broker = _Broker(
        [
            _read(),
            _done(
                {
                    "employees": _finding(
                        "42",
                        "Employees: 420",
                        confidence=1.0,
                    )
                }
            ),
        ]
    )

    async def work(page: Page):
        await page.goto(
            "data:text/html,<html><body><h1>Acme Ltd</h1><p>Employees: 420</p></body></html>"
        )
        run = AgentRun(
            broker=broker,
            settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
            page=page,
            trace=Trace.open(tmp_path),
        )
        outcome = await run.run(
            "Return the employee count shown on the page",
            step_budget=2,
            result_schema=("employees",),
        )
        return outcome, run

    outcome, run = asyncio.run(_drive(work))

    assert outcome.status == "incomplete"
    assert outcome.record == {}
    assert outcome.unsupported_fields == ("employees",)
    evidence = run.trace.resolve(step_id_of(run.trace, "action"))
    assert evidence is not None
    assert "Employees: 420" in run.trace.captured_text(evidence)
    assert any(step.kind == "result_field_unsupported" for step in run.trace.steps)
