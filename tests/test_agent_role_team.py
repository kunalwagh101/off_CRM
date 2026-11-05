"""S-04.01.04: five role adapters use existing engines, not a second workflow."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.agent.role_team import (
    ROLE_INSTRUCTIONS, RoleEngines, execute_role, provision_roles, release_role_resources,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

OWNER = "agent-team-owner-" + "a" * 35
HEADERS = {"X-Offsetx-Token": OWNER}


class EmptyMemory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


def _registry(tmp_path):
    return CompanionRegistry(
        tmp_path, tools=ToolRegistry(tmp_path / "tools.db"),
        memory_backend=EmptyMemory(),
    )


def test_five_roles_are_idempotent_and_never_override_owner_customisations(tmp_path):
    registry = _registry(tmp_path)
    original = provision_roles(registry, workspace_id="team-a")
    assert {profile["name"] for profile in original} == set(ROLE_INSTRUCTIONS)
    assert all(profile["granted_tool_ids"] == [] for profile in original)
    scout_id = next(profile["id"] for profile in original if profile["name"] == "Scout")
    registry.update(scout_id, workspace_id="team-a", instructions="Owner custom role.")
    again = provision_roles(registry, workspace_id="team-a")
    assert {profile["id"] for profile in original} == {profile["id"] for profile in again}
    assert registry.require(scout_id, workspace_id="team-a").instructions == "Owner custom role."
    assert len(registry.list(workspace_id="team-b")) == 0


def test_scout_only_reads_existing_workspace_trends():
    called = []
    trends = SimpleNamespace(topics=lambda **kw: called.append(kw) or [{"topic": "public"}])
    result = execute_role("Scout", {}, engines=RoleEngines(trends=trends))
    assert result == {"role": "Scout", "status": "observed", "topics": [{"topic": "public"}]}
    assert called == [{"window_hours": 72, "min_channels": 3, "limit": 5}]


def test_role_resources_close_workspace_watchers_only():
    closed = []
    watcher = SimpleNamespace(close=lambda: closed.append("scout"))
    poster_watcher = SimpleNamespace(close=lambda: closed.append("poster"))
    release_role_resources("Scout", RoleEngines(trends=watcher))
    release_role_resources(
        "Poster",
        RoleEngines(pipeline=SimpleNamespace(trends=poster_watcher)),
    )
    release_role_resources("Director", RoleEngines(gtm=SimpleNamespace(close=lambda: closed.append("bad"))))
    assert closed == ["scout", "poster"]


def test_maker_reuses_existing_video_director_and_review_gated_assembler():
    called = []
    def assemble(campaign_id, *, topic):
        called.append((campaign_id, topic))
        return tuple(SimpleNamespace(to_dict=lambda i=i: {"object": i}) for i in range(3))
    result = execute_role(
        "Maker", {"campaign_id": "campaign", "topic": "Short public explainer"},
        engines=RoleEngines(video=SimpleNamespace(direct_and_assemble=assemble)),
    )
    assert result["status"] == "needs_review"
    assert result["project"] == {"object": 0}
    assert called == [("campaign", "Short public explainer")]


def test_poster_drafts_only_and_never_calls_approval_or_publish():
    called = []
    def draft(**kw):
        called.append(kw)
        return SimpleNamespace(to_dict=lambda: {"draft_ids": ["one"]})
    result = execute_role(
        "Poster",
        {"campaign_id": "dist", "image_campaign_id": "image", "account_ids": ["account"]},
        engines=RoleEngines(pipeline=SimpleNamespace(draft=draft)),
    )
    assert result["status"] == "drafts_only"
    assert result["drafts"]["draft_ids"] == ["one"]
    assert called == [{
        "distribution_campaign_id": "dist",
        "image_campaign_id": "image",
        "account_ids": ("account",), "limit": 5,
    }]


def test_analyst_reads_metrics_and_director_only_drafts_strategy():
    dist = SimpleNamespace(
        progress=lambda cid: {"campaign_id": cid, "views": 20},
        generator_performance=lambda cid: [{"provider": "test"}],
    )
    analyst = execute_role(
        "Analyst", {"campaign_id": "one"}, engines=RoleEngines(distribution=dist),
    )
    assert analyst["status"] == "read_only"
    assert analyst["progress"]["views"] == 20
    calls = []
    gtm = SimpleNamespace(draft_plan=lambda values: calls.append(values) or {"status": "draft"})
    director = execute_role(
        "Director", {"gtm_request": {"product_id": "p", "goal": "reach"}},
        engines=RoleEngines(gtm=gtm),
    )
    assert director["status"] == "draft_only"
    assert calls == [{"product_id": "p", "goal": "reach"}]


def test_no_role_can_invent_an_action_or_autopublish():
    for role, body in [
        ("Publisher", {"campaign_id": "one"}),
        ("Poster", {"campaign_id": "one", "account_ids": []}),
        ("Maker", {"campaign_id": "one", "topic": ""}),
        ("Analyst", {}),
        ("Director", {}),
    ]:
        with pytest.raises(CompanionError):
            execute_role(role, body, engines=RoleEngines())


def test_role_api_requires_owner_provision_and_denies_unauthenticated_access(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        path = "/api/v1/agent-team/execute"
        request = {"role": "Scout"}
        assert client.post(path, json=request).status_code == 401
        assert client.post(path, json=request, headers=HEADERS).status_code == 409
        provision = client.post("/api/v1/agent-team/provision", headers=HEADERS)
        assert provision.status_code == 200, provision.text
        assert len(provision.json()["items"]) == 5
        result = client.post(path, json=request, headers=HEADERS)
        assert result.status_code == 200, result.text
        assert result.json()["role"] == "Scout"
        assert result.json()["status"] == "observed"
        assert result.json()["topics"] == []
        second = client.post("/api/v1/agent-team/provision", headers=HEADERS)
        assert second.status_code == 200
        assert {item["id"] for item in provision.json()["items"]} == {
            item["id"] for item in second.json()["items"]
        }
