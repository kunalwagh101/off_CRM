from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent.companions import CompanionStore
from offsetx_apollo_builder.agent.run import AgentRun, RunRefused, replay
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Trace


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(
            id="planner",
            cost_per_1m_input_usd=1.0,
            cost_per_1m_output_usd=1.0,
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
                "settings": settings,
            }
        )
        return SimpleNamespace(
            text=self.answers.pop(0),
            provider_id="trusted",
            provider_name="Trusted",
            model_id="planner",
            duration_ms=1,
            usage_source="",
        )


class _Page:
    def __init__(self):
        self.url = "https://example.test"
        self.actions = []

    async def snapshot(self):
        return Snapshot(
            url=self.url,
            title="Example",
            nodes=[Node(handle=1, role="button", name="Continue", backend_id=1)],
        )

    async def click(self, handle, *, confirmed=False):
        self.actions.append(("click", handle))
        return ActionResult(
            action="click",
            ok=True,
            url=self.url,
            detail=f"clicked {handle}",
        )

    async def read(self, *, limit=20_000):
        self.actions.append(("read", limit))
        return ActionResult(
            action="read",
            ok=True,
            url=self.url,
            detail="read page",
            text="page text",
        )


def _runtime(tmp_path, *, tools=("read",), instructions="Use facts only.", scope="global"):
    store = CompanionStore(tmp_path / "companions.db")
    profile = store.create(
        workspace_id="local",
        name="Scout",
        instructions=instructions,
        memory_scope=scope,
        granted_tools=tools,
    )
    loaded_scopes = []

    def memory_loader(workspace_id, memory_scope):
        loaded_scopes.append((workspace_id, memory_scope))
        return "APPROVED MEMORY: carbon buyer prefers concise notes"

    runtime = store.runtime(
        profile.id,
        workspace_id="local",
        memory_loader=memory_loader,
    )
    return store, runtime, loaded_scopes


def test_companion_instructions_and_only_declared_memory_scope_reach_planner(tmp_path):
    store, runtime, loaded = _runtime(
        tmp_path,
        tools=("read",),
        instructions="Never click. Read evidence and summarise.",
        scope="campaign:acme",
    )
    broker = _Broker(
        ['{"state":"done","reason":"enough","result":"complete"}']
    )
    page = _Page()
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="local",
            enabled_provider_ids=("trusted",),
        ),
        page=page,
        trace=Trace.open(tmp_path / "trace"),
        companion=runtime,
    )

    outcome = asyncio.run(run.run("Inspect the page", step_budget=2))

    assert outcome.status == "completed"
    assert loaded == [("local", "campaign:acme")]
    assert len(broker.calls) == 1
    assert "Never click. Read evidence and summarise." in broker.calls[0]["system_prompt"]
    assert "Only these browser tools are granted: read." in broker.calls[0]["system_prompt"]
    prompt = broker.calls[0]["request"].instructions
    assert "scope=campaign:acme" in prompt
    assert "APPROVED MEMORY: carbon buyer prefers concise notes" in prompt
    assert page.actions == []
    store.close()


def test_ungranted_browser_tool_is_refused_before_page_action(tmp_path):
    store, runtime, _ = _runtime(tmp_path, tools=("read",))
    broker = _Broker(
        ['{"state":"act","action":"click","args":{"handle":1},"reason":"continue"}']
    )
    page = _Page()
    trace = Trace.open(tmp_path / "trace")
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="local",
            enabled_provider_ids=("trusted",),
        ),
        page=page,
        trace=trace,
        companion=runtime,
    )

    outcome = asyncio.run(run.run("Continue", step_budget=1))

    assert outcome.status == "refused"
    assert "not granted browser tool" in outcome.message
    assert page.actions == []
    assert any(step.kind == "decision" and not step.ok for step in trace.steps)
    store.close()


def test_companion_workspace_must_match_run_workspace(tmp_path):
    store = CompanionStore(tmp_path / "companions.db")
    profile = store.create(
        workspace_id="alpha",
        name="Scout",
        instructions="",
        memory_scope="global",
        granted_tools=("read",),
    )
    runtime = store.runtime(profile.id, workspace_id="alpha")
    broker = _Broker([])
    page = _Page()
    run = AgentRun(
        broker=broker,
        settings=WorkspaceEgressSettings(
            workspace_id="beta",
            enabled_provider_ids=("trusted",),
        ),
        page=page,
        trace=Trace.open(tmp_path / "trace"),
        companion=runtime,
    )

    with pytest.raises(RunRefused, match="cannot cross workspaces"):
        asyncio.run(run.run("Read", step_budget=1))

    assert broker.calls == []
    assert page.actions == []
    store.close()


def test_resume_refuses_missing_or_changed_companion_policy(tmp_path):
    store, runtime, _ = _runtime(tmp_path, tools=("read",))
    trace = Trace.open(tmp_path / "trace")
    first = AgentRun(
        broker=_Broker(
            ['{"state":"act","action":"read","args":{},"reason":"inspect"}']
        ),
        settings=WorkspaceEgressSettings(
            workspace_id="local",
            enabled_provider_ids=("trusted",),
        ),
        page=_Page(),
        trace=trace,
        companion=runtime,
    )
    first_outcome = asyncio.run(first.run("Read once", step_budget=1))
    assert first_outcome.status == "budget_exhausted"

    state = replay(trace)
    assert state.companion_id == runtime.profile.id
    assert state.companion_policy_hash

    no_companion_broker = _Broker([])
    resumed_without = AgentRun(
        broker=no_companion_broker,
        settings=WorkspaceEgressSettings(
            workspace_id="local",
            enabled_provider_ids=("trusted",),
        ),
        page=_Page(),
        trace=trace,
    )
    with pytest.raises(RunRefused, match="policy changed"):
        asyncio.run(
            resumed_without.run(
                state.goal,
                step_budget=state.steps_remaining or 1,
                resume_from=state,
            )
        )
    assert no_companion_broker.calls == []

    store.update(
        runtime.profile.id,
        workspace_id="local",
        granted_tools=("read", "click"),
    )
    changed = store.runtime(runtime.profile.id, workspace_id="local")
    changed_broker = _Broker([])
    resumed_changed = AgentRun(
        broker=changed_broker,
        settings=WorkspaceEgressSettings(
            workspace_id="local",
            enabled_provider_ids=("trusted",),
        ),
        page=_Page(),
        trace=trace,
        companion=changed,
    )
    with pytest.raises(RunRefused, match="policy changed"):
        asyncio.run(
            resumed_changed.run(
                state.goal,
                step_budget=state.steps_remaining or 1,
                resume_from=state,
            )
        )
    assert changed_broker.calls == []
    store.close()
