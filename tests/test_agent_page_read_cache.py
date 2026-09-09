"""Acceptance evidence for S-11.02.04: one page read per run identity."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.read_cache import canonical_page_url
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult, Page
from offsetx_apollo_builder.browser.perceive import Snapshot
from offsetx_apollo_builder.browser.session import BrowserUnavailable, find_browser
from offsetx_apollo_builder.browser.trace import Trace


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
    def __init__(self, snapshot_urls=None):
        urls = list(snapshot_urls or ["https://research.example.test/company?id=10"])
        self.snapshot_urls = urls
        self.url = urls[0]
        self.snapshot_calls = 0
        self.read_calls = 0
        self.screenshot_calls = 0
        self.scroll_calls = 0

    async def snapshot(self):
        if self.snapshot_calls < len(self.snapshot_urls):
            self.url = self.snapshot_urls[self.snapshot_calls]
        self.snapshot_calls += 1
        return Snapshot(url=self.url, title="Fixture", nodes=[])

    async def read(self, *, limit=20_000):
        self.read_calls += 1
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read fixture page",
            text="Company: Acme Ltd\nEmployees: 42"[:limit],
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

    async def scroll(self, *, down=1):
        self.scroll_calls += 1
        return ActionResult(
            action="scroll",
            ok=True,
            url=self.url,
            detail=f"scrolled {down}",
        )


def _act(action, *, args=None):
    return json.dumps(
        {"state": "act", "action": action, "args": args or {}, "reason": action}
    )


def _done(record=None):
    body = {"state": "done", "reason": "complete"}
    if record is not None:
        body["record"] = record
    return json.dumps(body)


def _finding(value, quote, step_id):
    return {
        "value": value,
        "source_step_id": step_id,
        "quote": quote,
        "kind": "observed",
        "confidence": 0.9,
    }


def _run(tmp_path, answers, *, page=None, fields=None):
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
            "Read the page without repeating work",
            step_budget=len(answers),
            result_schema=fields,
        )
    )
    return outcome, run, broker, page


def test_tracking_parameters_are_removed_but_functional_state_is_preserved():
    left = canonical_page_url(
        "HTTPS://Example.COM/company?id=10&utm_source=linkedin&fbclid=abc#team"
    )
    right = canonical_page_url(
        "https://example.com/company?id=10&utm_source=email&fbclid=xyz#team"
    )
    different_record = canonical_page_url(
        "https://example.com/company?id=11&utm_source=email&fbclid=xyz#team"
    )
    generic_source = canonical_page_url(
        "https://example.com/company?id=10&source=internal#team"
    )

    assert left == right == "https://example.com/company?id=10#team"
    assert different_record != left
    assert generic_source.endswith("?id=10&source=internal#team")


def test_a_page_already_read_in_the_run_reuses_the_stored_capture(tmp_path):
    outcome, run, broker, page = _run(
        tmp_path,
        [_act("read"), _act("read"), _done()],
    )

    assert outcome.status == "completed"
    assert page.read_calls == 1
    assert outcome.actions == 1
    cache_hits = [step for step in run.trace.steps if step.kind == "read_cache_hit"]
    assert len(cache_hits) == 1
    assert "source_step_id=step-000002" in cache_hits[0].detail
    first_read = run.trace.resolve("step-000002")
    assert first_read is not None and first_read.capture
    assert "Acme Ltd" in run.trace.captured_text(first_read)
    assert "Acme Ltd" in broker.calls[2]


def test_tracking_only_url_variants_share_one_read(tmp_path):
    page = _Page(
        [
            "https://research.example.test/company?id=10&utm_source=linkedin",
            "https://research.example.test/company?id=10&utm_source=email&fbclid=abc",
        ]
    )
    outcome, run, _, page = _run(
        tmp_path,
        [_act("read"), _act("read"), _done()],
        page=page,
    )

    assert outcome.status == "completed"
    assert page.read_calls == 1
    assert any(step.kind == "read_cache_hit" for step in run.trace.steps)


def test_functional_query_change_is_a_different_page(tmp_path):
    page = _Page(
        [
            "https://research.example.test/company?id=10&utm_source=linkedin",
            "https://research.example.test/company?id=11&utm_source=email",
        ]
    )
    outcome, run, _, page = _run(
        tmp_path,
        [_act("read"), _act("read"), _done()],
        page=page,
    )

    assert outcome.status == "completed"
    assert page.read_calls == 2
    assert not any(step.kind == "read_cache_hit" for step in run.trace.steps)


def test_a_page_mutation_invalidates_that_pages_cached_read(tmp_path):
    page = _Page()
    outcome, _, _, page = _run(
        tmp_path,
        [_act("read"), _act("scroll", args={"down": 1}), _act("read"), _done()],
        page=page,
    )

    assert outcome.status == "completed"
    assert page.scroll_calls == 1
    assert page.read_calls == 2


def test_cached_structured_read_reuses_original_provenance_and_screenshot(tmp_path):
    page = _Page()
    outcome, run, broker, page = _run(
        tmp_path,
        [
            _act("read"),
            _act("read"),
            _done({"company": _finding("Acme Ltd", "Company: Acme Ltd", "step-000002")}),
        ],
        page=page,
        fields=("company",),
    )

    assert outcome.status == "completed"
    assert outcome.record == {"company": "Acme Ltd"}
    assert outcome.findings["company"].source.step_id == "step-000002"
    assert page.read_calls == 1
    assert page.screenshot_calls == 1
    assert "step_id=step-000002" in broker.calls[2]
    assert len([step for step in run.trace.steps if step.capture]) == 1


# The live gate proves that the second model read does not invoke Page.read on
# a real Chromium tab. Mocks alone could accidentally test only the helper.
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
def test_real_chromium_is_read_only_once_for_two_read_decisions(tmp_path):
    broker = _Broker([_act("read"), _act("read"), _done()])

    async def work(page: Page):
        await page.goto(
            "data:text/html,<html><body><h1>Acme Ltd</h1><p>One real page</p></body></html>"
        )
        real_read = page.read
        calls = 0

        async def counted_read(*, limit=20_000):
            nonlocal calls
            calls += 1
            return await real_read(limit=limit)

        page.read = counted_read
        run = AgentRun(
            broker=broker,
            settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
            page=page,
            trace=Trace.open(tmp_path),
        )
        outcome = await run.run(
            "Read this real page twice if necessary",
            step_budget=3,
        )
        return outcome, run, calls

    outcome, run, calls = asyncio.run(_drive(work))

    assert outcome.status == "completed"
    assert calls == 1
    assert any(step.kind == "read_cache_hit" for step in run.trace.steps)
    read_step = next(step for step in run.trace.steps if step.capture)
    assert "Acme Ltd" in run.trace.captured_text(read_step)
