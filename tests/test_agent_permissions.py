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
