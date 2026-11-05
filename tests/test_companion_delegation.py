"""F-04.01.03: bounded children get isolated prompts; parent gets results only."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.agent.delegation import ChildAssignment, delegate_once
from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = "f04-owner-token-" + "t" * 40
HEADERS = {"X-Offsetx-Token": TOKEN}


class EmptyMemory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


class RecordingBroker:
    def __init__(self):
        self.calls = []

    def with_credential_resolver(self, resolver):
        return self

    def call(self, request, settings, **kwargs):
        self.calls.append(request)
        return SimpleNamespace(
            text=f"Child result {len(self.calls)}", provider_name="fake",
            model_id="fake-model",
        )


def _registry(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    return CompanionRegistry(tmp_path, tools=tools, memory_backend=EmptyMemory())


def test_child_prompts_are_separate_and_parent_only_sees_child_results(tmp_path):
    registry = _registry(tmp_path)
    parent = registry.create(
        workspace_id="alpha", name="Director", instructions="Combine findings.",
    )
    one = registry.create(
        workspace_id="alpha", name="Scout", instructions="Scout private instruction.",
    )
    two = registry.create(
        workspace_id="alpha", name="Analyst", instructions="Analyst private instruction.",
    )
    broker = RecordingBroker()
    report = delegate_once(
        registry, parent_id=parent.id, workspace_id="alpha",
        assignments=[
            ChildAssignment(one.id, "Find a public example."),
            ChildAssignment(two.id, "Compare published figures."),
        ],
        broker=broker, settings=object(),
    )
    assert report["depth"] == 1
    assert len(report["children"]) == 2
    assert len(broker.calls) == 3
    assert "Scout private instruction" in broker.calls[0].instructions
    assert "Analyst private instruction" not in broker.calls[0].instructions
    assert "Analyst private instruction" in broker.calls[1].instructions
    assert "Scout private instruction" not in broker.calls[1].instructions
    assert broker.calls[2].instructions == "Combine findings."
    assert "Child result 1" in broker.calls[2].conversation[0]["content"]
    assert "Child result 2" in broker.calls[2].conversation[0]["content"]
    assert "Scout private instruction" not in broker.calls[2].conversation[0]["content"]
    assert "Analyst private instruction" not in broker.calls[2].conversation[0]["content"]


def test_unknown_foreign_disabled_or_excess_children_fail_before_provider(tmp_path):
    registry = _registry(tmp_path)
    parent = registry.create(workspace_id="w", name="Director", instructions="Review.")
    valid = registry.create(workspace_id="w", name="Scout", instructions="Search.")
    foreign = registry.create(workspace_id="other", name="Foreign", instructions="Private.")
    broker = RecordingBroker()
    invalid_sets = [
        [ChildAssignment(foreign.id, "Goal")],
        [ChildAssignment("does-not-exist", "Goal")],
        [ChildAssignment(valid.id, "Goal"), ChildAssignment(valid.id, "Goal")],
        [ChildAssignment(valid.id, "Goal")] * 4,
        [ChildAssignment(parent.id, "Goal")],
        [ChildAssignment(valid.id, " " * 10)],
    ]
    for items in invalid_sets:
        with pytest.raises(CompanionError):
            delegate_once(
                registry, parent_id=parent.id, assignments=items,
                workspace_id="w", broker=broker, settings=object(),
            )
    with pytest.raises(CompanionError, match="grandchildren"):
        delegate_once(registry, parent_id=parent.id,
                      assignments=[ChildAssignment(valid.id, "Goal")],
                      workspace_id="w", broker=broker, settings=object(), depth=1)
    registry.update(valid.id, workspace_id="w", enabled=False)
    with pytest.raises(CompanionError, match="disabled"):
        delegate_once(registry, parent_id=parent.id,
                      assignments=[ChildAssignment(valid.id, "Goal")],
                      workspace_id="w", broker=broker, settings=object())
    assert broker.calls == []


def test_existing_companion_api_owner_can_delegate_without_exposing_tools(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "none", host="127.0.0.1",
        api_token=TOKEN, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        registry = client.app.state.companions
        parent = registry.create(workspace_id="local", name="Director", instructions="Summarise.")
        scout = registry.create(workspace_id="local", name="Scout", instructions="Find facts.")
        broker = RecordingBroker()
        client.app.state.ai_broker = broker
        endpoint = f"/api/v1/companions/{parent.id}/delegate"
        data = {"assignments": [{"companion_id": scout.id, "goal": "Read public facts"}]}
        assert client.post(endpoint, json=data).status_code == 401
        response = client.post(endpoint, json=data, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json()["result"].startswith("Child result")
        assert len(broker.calls) == 2
        assert all(request.task_type == "ai_chat" for request in broker.calls)
        assert all(request.data_class.value == "campaign" for request in broker.calls)
