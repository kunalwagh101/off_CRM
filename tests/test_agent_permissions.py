"""F-06.01.02: workspace-wide and per-tool policies with temporary chat grants."""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.permissions import (
    AgentPermissionPolicy, ChatPermissionGrants, PermissionErrorRule,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = "agent-permission-testing-token-" + "p" * 36
API = "/api/v1/agent-permissions"
HEADERS = {"X-Offsetx-Token": TOKEN}


def _settings(tmp_path):
    return AppSettings(
        project_root=Path.cwd(), database_path=tmp_path/"crm.db",
        data_dir=tmp_path/"data", export_dir=tmp_path/"data"/"exports",
        frontend_dist=tmp_path/"missing", api_token=TOKEN,
        allowed_hosts=("testserver",),
    )


def test_policy_precedence_and_defaults():
    p = AgentPermissionPolicy()
    assert p.decide("click") == "allow"
    p = AgentPermissionPolicy(global_mode="ask", tool_rules={"read": "allow", "click": "deny"})
    assert p.decide("read") == "allow"
    assert p.decide("click") == "deny"
    assert p.decide("scroll") == "ask"
    p = AgentPermissionPolicy(global_mode="deny", tool_rules={"click": "allow"})
    assert p.decide("click") == "deny"


@pytest.mark.parametrize("bad", [
    {"global_mode": "anything"}, {"global_mode": True},
    {"global_mode": "allow", "tool_rules": {"evaluate": "allow"}},
    {"global_mode": "allow", "tool_rules": {"read": "auto"}},
    {"global_mode": "allow", "tool_rules": {"read": True}},
    {"global_mode": "allow", "tool_rules": ["read"]},
])
def test_invalid_policy_rejected_before_persistence(bad):
    with pytest.raises(PermissionErrorRule):
        AgentPermissionPolicy.from_mapping(bad)


def test_chat_grants_expire_and_cannot_override_explicit_deny():
    p = AgentPermissionPolicy(global_mode="ask", tool_rules={"type": "deny"})
    grants = ChatPermissionGrants(chat_id="abc")
    grants.grant("click")
    assert p.decide("click", grants=grants) == "allow"
    assert p.decide("type", grants=grants) == "deny"
    assert p.decide("scroll", grants=grants) == "ask"
    grants.close()
    assert p.decide("click", grants=grants) == "ask"
    with pytest.raises(PermissionErrorRule):
        grants.grant("click")


def test_api_auth_workspace_update_and_restart(tmp_path):
    settings=_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get(API).status_code == 401
        before=client.get(API,headers=HEADERS)
        assert before.status_code == 200 and before.json()["global_mode"]=="allow"
        new=client.put(API,headers=HEADERS,json={"global_mode":"ask","tool_rules":{"click":"deny","read":"allow"}})
        assert new.status_code==200,new.text
        assert new.json()["tool_rules"]["click"]=="deny"
        bad=client.put(API,headers=HEADERS,json={"global_mode":"allow","tool_rules":{"evaluate":"allow"}})
        assert bad.status_code==400
        still=client.get(API,headers=HEADERS).json()
        assert still["global_mode"]=="ask" and still["tool_rules"]["click"]=="deny"
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(API,headers=HEADERS).json()["global_mode"]=="ask"
        assert restarted.get(API,headers=HEADERS).json()["tool_rules"]["read"]=="allow"


def test_non_owner_workspace_can_view_but_cannot_change_install_global_permissions(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        created=client.post("/api/v1/workspaces",headers=HEADERS,json={
            "username":"worker","workspace_id":"worker-space","password":"long-worker-pass-123"
        })
        assert created.status_code==201,created.text
        member=TestClient(client.app)
        logged=member.post("/api/v1/auth/login",json={
            "username":"worker","password":"long-worker-pass-123"
        })
        assert logged.status_code==200
        # Workspace member can inspect their own effective policy, not modify
        # an install-wide policy without the install API token.
        assert member.get(API).status_code==200
        assert member.put(API,json={"global_mode":"deny","tool_rules":{}}).status_code==403
        assert client.get(API,headers=HEADERS).json()["global_mode"]=="allow"


@pytest.mark.parametrize("mode,expected", [
    ("deny", "permission_denied"), ("ask", "needs_permission"),
])
def test_unattended_routine_refuses_goto_before_browser_launch(tmp_path, mode, expected, monkeypatch):
    """An initial Page.goto happens outside AgentRun and cannot bypass policy."""
    import asyncio
    from types import SimpleNamespace
    from offsetx_apollo_builder.agent.routines import RoutineAgentExecutor
    import offsetx_apollo_builder.agent.routines as routines

    def forbidden_browser(*args, **kwargs):
        raise AssertionError("Browser must not start before owner grants navigation")

    monkeypatch.setattr(routines, "free_port", forbidden_browser)
    workspaces = SimpleNamespace(raw=lambda ws: {
        "agent_permissions": {"global_mode": mode, "tool_rules": {}}
    })
    executor = RoutineAgentExecutor(
        data_dir=tmp_path, workspaces=workspaces,
        broker_factory=lambda workspace: forbidden_browser(),
    )
    routine = SimpleNamespace(
        workspace_id="local", goal="Check lead", target_url="https://example.org/",
        target_host="example.org", step_budget=2,
    )
    result = asyncio.run(executor(routine, {}))
    assert result.status == expected
    assert result.useful is False


def test_corrupt_saved_settings_fail_closed_for_owner_reads_and_updates(tmp_path):
    """A broken settings document must never be shown as allow or overwritten."""
    with TestClient(create_app(_settings(tmp_path))) as client:
        stored = client.put(
            API, headers=HEADERS,
            json={"global_mode": "deny", "tool_rules": {}},
        )
        assert stored.status_code == 200, stored.text

        path = client.app.state.ai_workspaces.settings_path
        damaged = '{"private_settings":'
        path.write_text(damaged, encoding="utf-8")

        with pytest.raises(ValueError):
            client.app.state.ai_workspaces.raw_permissions("local")
        fetched = client.get(API, headers=HEADERS)
        assert fetched.status_code == 503
        changed = client.put(
            API, headers=HEADERS,
            json={"global_mode": "allow", "tool_rules": {}},
        )
        assert changed.status_code == 503
        assert path.read_text(encoding="utf-8") == damaged

def test_permission_update_refuses_corruption_between_validation_and_write(tmp_path, monkeypatch):
    """Preflight alone is not enough: a write must re-check under its lock."""
    with TestClient(create_app(_settings(tmp_path))) as client:
        saved = client.put(
            API, headers=HEADERS,
            json={"global_mode": "deny", "tool_rules": {}},
        )
        assert saved.status_code == 200, saved.text
        store = client.app.state.ai_workspaces
        original_read = store.raw_permissions
        damaged = '{"broken":'

        def corrupted_after_preflight(workspace_id):
            result = original_read(workspace_id)
            store.settings_path.write_text(damaged, encoding="utf-8")
            return result

        monkeypatch.setattr(store, "raw_permissions", corrupted_after_preflight)
        changed = client.put(
            API, headers=HEADERS,
            json={"global_mode": "allow", "tool_rules": {}},
        )
        assert changed.status_code == 503, changed.text
        assert store.settings_path.read_text(encoding="utf-8") == damaged
