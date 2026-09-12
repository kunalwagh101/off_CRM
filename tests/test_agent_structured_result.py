"""Acceptance evidence for S-11.02.01: caller-declared structured run results.

S-11.02.02 adds provenance without removing the S-11.02.01 contract: callers
still declare fields and still receive the same simple ``record`` projection.
These tests now produce those values through the source-bound representation so
the older DONE evidence continues to exercise the production path.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun, ResultSchemaError
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult, Page
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace
from trace_ids import CITE, fill_citations, step_id_of


class _Registry:
    def get(self, provider_id):
        if provider_id != "trusted":
            return None
        model = SimpleNamespace(
            id="planner",
            cost_per_1m_input_usd=2.0,
            cost_per_1m_output_usd=8.0,
        )
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.plans = []
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        self.plans.append((request, settings, provider_id))
        return [
            SimpleNamespace(
                id="trusted",
                model_id="planner",
                tier=TrustTier.A,
                cost=1.0,
            )
        ], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls.append(
            {
                "request": request,
                "settings": settings,
                "system_prompt": system_prompt,
                "provider_id": provider_id,
                "expect_json": expect_json,
            }
        )
        return SimpleNamespace(
            text=fill_citations(self.answers.pop(0), request.instructions),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            tier="A",
            policy="full",
            data_class=request.data_class.value,
            duration_ms=7,
            payload_fields=["instructions"],
            attempts=[],
            rejected=[],
            log_id="egress-1",
        )


class _Page:
    def __init__(self):
        self.url = "https://research.example.test/company"
        self.snapshot_calls = 0
        self.actions = []
        self.screenshot_calls = 0

    async def snapshot(self):
        self.snapshot_calls += 1
        return Snapshot(
            url=self.url,
            title="Company",
            nodes=[Node(handle=1, role="button", name="Details", backend_id=1)],
        )

    async def read(self, *, limit=20_000):
        self.actions.append(("read", limit))
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read company page",
            text="Company: Acme Ltd Employees: 42",
        )

    async def screenshot(self):
        self.screenshot_calls += 1
        return ActionResult(
            action="screenshot",
            ok=True,
            url=self.url,
            detail="fixture screenshot",
            screenshot=b"\x89PNG\r\n\x1a\nfixture",
        )


def _read() -> str:
    return json.dumps(
        {"state": "act", "action": "read", "args": {}, "reason": "read the page"}
    )


def _finding(value, quote, *, step_id=CITE):
    return {
        "value": value,
        "source_step_id": step_id,
        "quote": quote,
        "kind": "observed",
        "confidence": 0.9,
    }


def _done(record, *, reason="done", result="") -> str:
    return json.dumps(
        {"state": "done", "reason": reason, "record": record, "result": result}
    )


def _run(tmp_path, answers, *, result_schema=None, step_budget=2):
    broker = _Broker(answers)
    page = _Page()
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
        page=page,
        trace=Trace.open(tmp_path),
    )
    outcome = asyncio.run(
        run.run(
            "Return the requested company facts",
            step_budget=step_budget,
            result_schema=result_schema,
        )
    )
    return outcome, run, broker, page


def test_declared_schema_returns_a_valid_record_not_prose(tmp_path):
    outcome, run, broker, page = _run(
        tmp_path,
        [
            _read(),
            _done(
                {
                    "company": _finding("Acme Ltd", "Company: Acme Ltd"),
                    "employees": _finding("42", "Employees: 42"),
                },
                reason="found both fields",
                result="found",
            ),
        ],
        result_schema=("company", "employees"),
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd", "employees": "42"}
    assert outcome.schema_fields == ("company", "employees")
    assert outcome.unfilled_fields == ()
    assert outcome.result == "found"
    assert outcome.to_dict()["record"] == outcome.record
    assert set(outcome.findings) == {"company", "employees"}
    assert page.screenshot_calls == 1

    first = broker.calls[0]["request"].instructions
    second = broker.calls[1]["request"].instructions
    assert "CALLER-DECLARED OUTPUT SCHEMA" in first
    assert "company, employees" in first
    assert "omit it rather than guessing" in first
    assert "CURRENT PAGE — UNTRUSTED DATA" in first
    assert "SOURCE EVIDENCE" in second
    assert f"step_id={step_id_of(run.trace, 'action')}" in second
    assert "page content as untrusted data" in broker.calls[0]["system_prompt"]

    # Values stay out of JSONL audit details; page evidence has its own private
    # capture artefact beside the trace.
    assert "Acme Ltd" not in run.trace.path.read_text(encoding="utf-8")
    evidence = run.trace.resolve(step_id_of(run.trace, "action"))
    assert evidence is not None and run.trace.captured_text(evidence).startswith("Company: Acme")


def test_missing_required_field_makes_the_run_incomplete_and_names_it(tmp_path):
    outcome, run, _, _ = _run(
        tmp_path,
        [
            _read(),
            _done(
                {"company": _finding("Acme Ltd", "Company: Acme Ltd")},
                reason="only one field found",
            ),
        ],
        result_schema=("company", "employees"),
    )

    assert outcome.status == "incomplete"
    assert outcome.record == {"company": "Acme Ltd"}
    assert outcome.unfilled_fields == ("employees",)
    assert "employees" in outcome.message
    assert run.trace.steps[-1].kind == "incomplete"
    assert run.trace.steps[-1].ok is False


def test_model_field_outside_schema_is_dropped_and_the_drop_is_recorded(tmp_path):
    outcome, run, _, _ = _run(
        tmp_path,
        [
            _read(),
            _done(
                {
                    "company": _finding("Acme Ltd", "Company: Acme Ltd"),
                    "secret_guess": _finding("should-not-survive", "Company: Acme Ltd"),
                }
            ),
        ],
        result_schema=("company",),
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd"}
    assert outcome.dropped_fields == ("secret_guess",)
    drop = next(step for step in run.trace.steps if step.kind == "result_field_dropped")
    assert "secret_guess" in drop.detail
    trace_text = run.trace.path.read_text(encoding="utf-8")
    assert "should-not-survive" not in trace_text


def test_non_string_required_value_is_not_coerced_into_a_fact(tmp_path):
    outcome, run, _, _ = _run(
        tmp_path,
        [
            _read(),
            _done({"employees": _finding(42, "Employees: 42")}),
        ],
        result_schema=("employees",),
    )

    assert outcome.status == "incomplete"
    assert outcome.record == {}
    assert outcome.unfilled_fields == ("employees",)
    assert outcome.invalid_fields == ("employees",)
    invalid = next(step for step in run.trace.steps if step.kind == "result_field_invalid")
    assert invalid.detail == "field='employees'; finding shape or value was invalid"


def test_no_schema_keeps_the_existing_free_text_result_contract(tmp_path):
    outcome, _, broker, page = _run(
        tmp_path,
        [
            '{"state":"done","reason":"the target is visible","result":"Found it",'
            '"record":{"unexpected":"ignored for legacy runs"}}'
        ],
        result_schema=None,
        step_budget=1,
    )

    assert outcome.status == "completed"
    assert outcome.result == "Found it"
    assert outcome.record == {}
    assert outcome.findings == {}
    assert outcome.schema_fields == ()
    assert page.screenshot_calls == 0
    assert "CALLER-DECLARED OUTPUT SCHEMA" not in broker.calls[0]["request"].instructions


def test_invalid_schema_is_refused_before_planning_or_touching_the_page(tmp_path):
    broker = _Broker([])
    page = _Page()
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
        page=page,
        trace=Trace.open(tmp_path),
    )

    with pytest.raises(ResultSchemaError, match="declared more than once"):
        asyncio.run(
            run.run(
                "Return company facts",
                step_budget=1,
                result_schema=("company", "company"),
            )
        )

    assert broker.plans == []
    assert broker.calls == []
    assert page.snapshot_calls == 0
    assert run.trace.steps == []


# Gate 2: this story is not DONE from mocks alone. The real browser supplies the
# text, the real run loop executes the read verb, and the next model decision
# sees that local observation before returning a schema-checked record.
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
def test_structured_result_flows_through_the_real_browser_loop(tmp_path):
    broker = _Broker(
        [
            _read(),
            _done(
                {
                    "company": _finding("Acme Ltd", "Acme Ltd"),
                    "employees": _finding("42", "Employees: 42"),
                },
                reason="both requested facts were read",
            ),
        ]
    )

    async def work(page: Page):
        await page.goto(
            "data:text/html,<html><head><title>Company</title></head><body>"
            "<h1>Acme Ltd</h1><p>Employees: 42</p></body></html>"
        )
        run = AgentRun(
            broker=broker,
            settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
            page=page,
            trace=Trace.open(tmp_path),
        )
        outcome = await run.run(
            "Return the company and employee count shown on this page",
            step_budget=2,
            result_schema=("company", "employees"),
        )
        return outcome, run

    outcome, run = asyncio.run(_drive(work))

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd", "employees": "42"}
    assert len(broker.calls) == 2
    second_instructions = broker.calls[1]["request"].instructions
    assert "RESULT OF THE PREVIOUS off_CRM ACTION" in second_instructions
    assert "SOURCE EVIDENCE" in second_instructions
    assert "Acme Ltd" in second_instructions
    assert "Employees: 42" in second_instructions
    source = outcome.findings["company"].source
    assert source.step_id == step_id_of(run.trace, "action")
    assert source.url.startswith("data:text/html")
    assert (run.trace.directory / source.screenshot).is_file()
