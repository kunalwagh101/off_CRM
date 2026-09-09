"""Interactions between run plans, cached evidence and failed-action recovery."""

import asyncio

import pytest

from offsetx_apollo_builder.agent import AgentRun, RunPlan
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.browser.page import ActionRefused, ActionResult
from offsetx_apollo_builder.browser.trace import Trace
from test_agent_page_read_cache import _Broker, _Page, _act, _done, _finding, _run


@pytest.mark.parametrize("suffixes", [("#team", "#accounts"), ("?id=1&id=2", "?id=2&id=1")])
def test_application_route_and_ordered_query_changes_require_new_evidence(tmp_path, suffixes):
    page = _Page(["https://example.test/app" + suffix for suffix in suffixes])
    outcome, _, _, page = _run(tmp_path, [_act("read"), _act("read"), _done()], page=page)
    assert outcome.status == "completed"
    assert page.read_calls == 2


@pytest.mark.parametrize("action,args", [("goto", {"url": "https://example.test/app"}), ("wait_for", {"text": "Updated"})])
def test_reload_and_wait_discard_evidence_from_before_the_change(tmp_path, action, args):
    class ChangingPage(_Page):
        updated = False

        async def goto(self, url):
            self.url = url
            self.updated = True
            return ActionResult(action="goto", ok=True, url=url)

        async def wait_for(self, text, *, timeout):
            self.updated = True
            return ActionResult(action="wait_for", ok=True, url=self.url)

        async def read(self, *, limit=20_000):
            result = await super().read(limit=limit)
            result.text = "Updated" if self.updated else "Original"
            return result

    page = ChangingPage(["https://example.test/app"])
    outcome, run, broker, page = _run(
        tmp_path, [_act("read"), _act(action, args=args), _act("read"), _done()], page=page,
    )
    assert outcome.status == "completed"
    assert page.read_calls == 2
    assert "Updated" in broker.calls[-1]
    assert [run.trace.captured_text(step) for step in run.trace.steps if step.capture] == ["Original", "Updated"]


def test_successful_cached_read_resets_the_failure_streak(tmp_path):
    class FailingScreenshotPage(_Page):
        async def screenshot(self):
            self.screenshot_calls += 1
            raise ActionRefused("Screenshot unavailable")

    page = FailingScreenshotPage()
    answers = [_act("read"), _act("screenshot"), _act("read"), _act("screenshot"), _act("read"), _act("screenshot"), _done()]
    outcome, _, _, page = _run(tmp_path, answers, page=page)
    assert outcome.status == "completed"
    assert page.read_calls == 1
    assert page.screenshot_calls == 1  # The same failed action is never reissued.


def test_owner_edit_does_not_replace_the_cached_evidence_source(tmp_path):
    trace = Trace.open(tmp_path)
    plan = RunPlan(trace.directory)

    class EditingPage(_Page):
        async def snapshot(self):
            if self.snapshot_calls == 1:
                plan.replace("# Goal\n\nReturn the company from the existing evidence.\n")
            return await super().snapshot()

    page = EditingPage()
    broker = _Broker([_act("read"), _act("read"), _done({"company": _finding("Acme Ltd", "Company: Acme Ltd", "step-000002")})])
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)), page=page, trace=trace)
    outcome = asyncio.run(run.run("Original owner goal", step_budget=3, result_schema=("company",)))
    assert outcome.record == {"company": "Acme Ltd"}
    assert outcome.findings["company"].source.step_id == next(step.step_id for step in trace.steps if step.capture)
    assert page.read_calls == 1
    assert "Original owner goal" not in broker.calls[-1]
    assert "Return the company from the existing evidence" in broker.calls[-1]
    assert any(step.kind == "plan_seen" for step in trace.steps)


def test_partially_failed_mutation_cannot_leave_a_stale_capture(tmp_path):
    class PartiallyChangedPage(_Page):
        async def scroll(self, *, down=1):
            raise ActionRefused("The page changed, but scrolling did not finish")

    outcome, _, _, page = _run(
        tmp_path, [_act("read"), _act("scroll", args={"down": 1}), _act("read"), _done()], page=PartiallyChangedPage(),
    )
    assert outcome.status == "completed"
    assert page.read_calls == 2
