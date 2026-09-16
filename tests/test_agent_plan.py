"""Acceptance evidence for S-02.02.02: PLAN.md is the run's source of truth."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent.plan import MAX_PLAN_BYTES, PLAN_FILENAME, PlanError, RunPlan
from offsetx_apollo_builder.agent.run import AgentRun, RunRefused
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


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
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
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
                "system_prompt": system_prompt,
                "provider_id": provider_id,
                "expect_json": expect_json,
            }
        )
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
            log_id="egress-plan-test",
        )


class _Page:
    def __init__(self, *, after_click=None):
        self.url = "https://crm.example.test/leads"
        self.after_click = after_click
        self.clicks = 0

    async def snapshot(self):
        return Snapshot(
            url=self.url,
            title="Leads",
            nodes=[Node(handle=1, role="button", name="Next", backend_id=1)],
        )

    async def click(self, handle, *, confirmed=False):
        self.clicks += 1
        if self.after_click is not None:
            self.after_click()
        return ActionResult(
            action="click",
            ok=True,
            url=self.url,
            detail=f"clicked {handle}",
        )


def _settings():
    return WorkspaceEgressSettings(enabled_provider_ids=("trusted",))


def test_run_start_creates_exactly_one_plan_md_and_returns_its_name(tmp_path):
    broker = _Broker(
        ['{"state":"done","reason":"complete","result":"ok"}']
    )
    trace = Trace.open(tmp_path)
    run = AgentRun(broker=broker, settings=_settings(), page=_Page(), trace=trace)

    outcome = asyncio.run(run.run("Review the current lead", step_budget=2))

    assert outcome.status == "completed"
    assert outcome.plan_file == PLAN_FILENAME
    plans = list(trace.directory.glob("PLAN*.md"))
    assert plans == [trace.directory / PLAN_FILENAME]
    markdown = plans[0].read_text(encoding="utf-8")
    assert "# Goal" in markdown
    assert "Review the current lead" in markdown
    assert "## Checklist" in markdown
    assert broker.calls[0]["request"].instructions.count("OWNER PLAN") == 1
    assert markdown in broker.calls[0]["request"].instructions


def test_owner_edit_is_the_plan_seen_by_the_very_next_model_decision(tmp_path):
    broker = _Broker(
        [
            '{"state":"act","action":"click","args":{"handle":1},"reason":"continue"}',
            '{"state":"done","reason":"owner changed the goal","result":"stopped"}',
        ]
    )
    trace = Trace.open(tmp_path)
    plan = RunPlan(trace.directory)
    edited = (
        "# Goal\n\nStop the research now.\n\n"
        "## Checklist\n\n"
        "- [x] Enough evidence is collected.\n"
        "- [ ] Do not open another lead.\n"
    )

    def owner_saves_plan():
        plan.replace(edited)

    run = AgentRun(
        broker=broker,
        settings=_settings(),
        page=_Page(after_click=owner_saves_plan),
        trace=trace,
    )

    outcome = asyncio.run(run.run("Review leads", step_budget=3))

    assert outcome.status == "completed"
    assert len(broker.calls) == 2
    first = broker.calls[0]["request"].instructions
    second = broker.calls[1]["request"].instructions
    assert "Review leads" in first
    assert "Stop the research now." not in first
    assert "Stop the research now." in second
    # The original run-start goal is no longer a competing live instruction.
    assert "Review leads" not in second
    assert "OWNER GOAL" not in second
    assert second.index("OWNER PLAN") < second.index("CURRENT PAGE")
    assert any(
        step.kind == "plan_seen" and "owner edit observed" in step.detail
        for step in trace.steps
    )
    # Trace records the version, not the potentially sensitive owner-authored plan.
    assert all("Stop the research now" not in step.detail for step in trace.steps)


def test_plan_checklist_is_readable_for_a_ui_without_a_second_state_store(tmp_path):
    plan = RunPlan.open(tmp_path, goal="Qualify accounts")
    snapshot = plan.replace(
        "# Goal\n\nQualify accounts\n\n"
        "## Checklist\n\n"
        "- [x] Check sector\n"
        "- [ ] Check employee count\n"
        "ordinary paragraph\n"
    )

    assert snapshot.checklist == (
        {"done": True, "text": "Check sector"},
        {"done": False, "text": "Check employee count"},
    )
    assert snapshot.to_dict()["markdown"] == plan.path.read_text(encoding="utf-8")


def test_plan_md_symlink_is_refused_before_any_model_call(tmp_path):
    trace = Trace.open(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET LOCAL MATERIAL", encoding="utf-8")
    plan_path = trace.directory / PLAN_FILENAME
    try:
        plan_path.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available to this test process")

    broker = _Broker([])
    run = AgentRun(broker=broker, settings=_settings(), page=_Page(), trace=trace)

    with pytest.raises(RunRefused, match="PLAN.md is unsafe"):
        asyncio.run(run.run("Review leads", step_budget=2))

    assert broker.calls == []
    assert "TOP SECRET LOCAL MATERIAL" not in trace.render()


def test_plan_size_is_bounded_and_atomic_replace_leaves_no_temp_file(tmp_path):
    plan = RunPlan.open(tmp_path, goal="Review leads")

    with pytest.raises(PlanError, match="too large"):
        plan.replace("x" * (MAX_PLAN_BYTES + 1))

    before = plan.snapshot().markdown
    assert before
    assert not list(Path(tmp_path).glob(".PLAN.*.tmp"))

    saved = plan.replace("# Goal\n\nNarrowed scope\n")
    assert saved.markdown == "# Goal\n\nNarrowed scope\n"
    assert not list(Path(tmp_path).glob(".PLAN.*.tmp"))
