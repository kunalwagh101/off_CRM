from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent.plan import MAX_PLAN_CHARS, PlanError, RunPlan
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
    def __init__(self, answers, *, after_call=None):
        self.answers = list(answers)
        self.after_call = after_call
        self.calls = []
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        self.calls.append(request.instructions)
        index = len(self.calls)
        if self.after_call is not None:
            self.after_call(index)
        return SimpleNamespace(
            text=self.answers.pop(0),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            tier="A",
            policy="full",
            data_class=request.data_class.value,
            duration_ms=1,
            payload_fields=["instructions"],
            attempts=[],
            rejected=[],
            log_id=f"egress-{index}",
        )


class _Page:
    def __init__(self):
        self.url = "https://example.test/work"

    async def snapshot(self):
        return Snapshot(
            url=self.url,
            title="Work",
            nodes=[Node(handle=1, role="button", name="Next", backend_id=1)],
        )

    async def click(self, handle, *, confirmed=False):
        return ActionResult(action="click", ok=True, url=self.url, detail="clicked")


def _run(trace, broker):
    return AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(enabled_provider_ids=("trusted",)),
        page=_Page(),
        trace=trace,
        planner_provider_id="trusted",
    )


def test_a_run_has_exactly_one_plan_md_in_its_run_directory(tmp_path):
    trace = Trace.open(tmp_path / "traces")
    agent = _run(
        trace,
        _Broker(['{"state":"done","reason":"done","result":"done"}']),
    )

    outcome = asyncio.run(agent.run("Review the record", step_budget=2))

    assert outcome.status == "completed"
    plans = list(trace.directory.glob("PLAN*.md"))
    assert plans == [trace.directory / "PLAN.md"]
    text = plans[0].read_text(encoding="utf-8")
    assert "Review the record" in text
    assert "- [ ]" in text


def test_owner_edit_to_plan_is_what_the_very_next_model_decision_sees(tmp_path):
    trace = Trace.open(tmp_path / "traces")

    def edit_after_first_call(index):
        if index == 1:
            (trace.directory / "PLAN.md").write_text(
                "# PLAN\n\n## Checklist\n- [ ] STOP AND RETURN THE CURRENT RESULT\n",
                encoding="utf-8",
            )

    broker = _Broker(
        [
            '{"state":"act","action":"click","args":{"handle":1},"reason":"next"}',
            '{"state":"done","reason":"owner changed the plan","result":"stopped"}',
        ],
        after_call=edit_after_first_call,
    )
    agent = _run(trace, broker)

    outcome = asyncio.run(agent.run("Review records", step_budget=3))

    assert outcome.status == "completed"
    assert "STOP AND RETURN THE CURRENT RESULT" not in broker.calls[0]
    assert "STOP AND RETURN THE CURRENT RESULT" in broker.calls[1]
    assert "OWNER-EDITABLE RUN PLAN — TRUSTED LOCAL INSTRUCTIONS" in broker.calls[1]


def test_missing_plan_mid_run_refuses_before_another_model_call(tmp_path):
    trace = Trace.open(tmp_path / "traces")

    def delete_after_first_call(index):
        if index == 1:
            (trace.directory / "PLAN.md").unlink()

    broker = _Broker(
        [
            '{"state":"act","action":"click","args":{"handle":1},"reason":"next"}',
            '{"state":"done","reason":"should never be asked","result":"bad"}',
        ],
        after_call=delete_after_first_call,
    )
    agent = _run(trace, broker)

    with pytest.raises(RunRefused, match="PLAN.md"):
        asyncio.run(agent.run("Review records", step_budget=3))

    assert len(broker.calls) == 1


def test_plan_is_never_cached_and_an_unsafe_plan_is_refused(tmp_path):
    run_dir = tmp_path / "run"
    plan = RunPlan(run_dir)
    plan.ensure("goal")
    first = plan.read()
    plan.path.write_text("# PLAN\n- [ ] changed", encoding="utf-8")
    assert plan.read() != first

    plan.path.write_text("x" * (MAX_PLAN_CHARS + 1), encoding="utf-8")
    with pytest.raises(PlanError, match="exceeds"):
        plan.read()


def test_managed_run_refuses_to_regenerate_a_deleted_plan(tmp_path):
    plan = RunPlan(tmp_path / "managed-run")
    plan.ensure("original goal")
    plan.path.write_text(
        "# PLAN\n\n## Checklist\n- [ ] OWNER EDIT THAT MUST NOT BE LOST\n",
        encoding="utf-8",
    )
    plan.path.unlink()

    with pytest.raises(PlanError, match="missing"):
        plan.ensure("original goal")

    assert not plan.path.exists()


def test_legacy_run_directory_gets_one_plan_without_overwriting_existing_edit(tmp_path):
    trace = Trace.open(tmp_path / "traces", run_id="legacy-run")
    plan = RunPlan(trace.directory)
    plan.ensure("legacy goal")
    plan.path.write_text("# PLAN\n- [ ] owner edit", encoding="utf-8")
    plan.ensure("different goal")
    assert plan.read() == "# PLAN\n- [ ] owner edit"
