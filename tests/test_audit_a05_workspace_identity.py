"""A05 audit: individual workspace sessions must enforce their authority at the API."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


ADMIN_TOKEN = "audit-admin-" + "x" * 36


@pytest.fixture()
def sessions(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token=ADMIN_TOKEN,
        session_secret="audit-session-" + "s" * 36,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as owner:
        admin = {"X-Offsetx-Token": ADMIN_TOKEN}
        for username, workspace in (("alice", "alpha"), ("bob", "beta")):
            created = owner.post(
                "/api/v1/workspaces",
                headers=admin,
                json={
                    "username": username,
                    "workspace_id": workspace,
                    "password": username + "-safe-password-123",
                },
            )
            assert created.status_code == 201, created.text
        alice, bob = TestClient(owner.app), TestClient(owner.app)
        for client, username, workspace in (
            (alice, "alice", "alpha"),
            (bob, "bob", "beta"),
        ):
            logged_in = client.post(
                "/api/v1/auth/login",
                json={
                    "username": username,
                    "password": username + "-safe-password-123",
                },
            )
            assert logged_in.status_code == 200, logged_in.text
            assert logged_in.json()["workspace_id"] == workspace
        yield owner, admin, alice, bob
        alice.close()
        bob.close()


def test_A05_workspace_identity_cannot_be_replaced_by_a_query_or_header(sessions):
    """A05: another workspace's rules are not readable by a signed-in peer."""
    owner, admin, alice, bob = sessions
    assert alice.get("/api/v1/auth/session").json()["workspace_id"] == "alpha"
    assert bob.get("/api/v1/auth/session").json()["workspace_id"] == "beta"
    assert alice.get("/api/v1/agent-permissions").status_code == 200
    assert bob.get("/api/v1/agent-permissions").status_code == 200

    for headers in ({}, {"X-Workspace-Id": "beta"}, {"X-Offsetx-Workspace": "beta"}):
        denied = alice.get("/api/v1/agent-permissions?workspace_id=beta", headers=headers)
        assert denied.status_code == 403, denied.text
    assert owner.get(
        "/api/v1/agent-permissions?workspace_id=beta", headers=admin
    ).status_code == 200


def test_A05_workspace_login_cannot_administer_other_users(sessions):
    """A05: workspace cookies cannot list, create or disable user accounts."""
    owner, admin, alice, _ = sessions
    assert alice.get("/api/v1/workspaces").status_code == 403
    denied_create = alice.post(
        "/api/v1/workspaces",
        json={
            "username": "mallory",
            "workspace_id": "mallory",
            "password": "mallory-safe-password-123",
        },
    )
    assert denied_create.status_code == 403, denied_create.text
    denied_update = alice.patch("/api/v1/workspaces/bob", json={"enabled": False})
    assert denied_update.status_code == 403, denied_update.text

    accounts = owner.get("/api/v1/workspaces", headers=admin)
    assert accounts.status_code == 200
    assert {item["username"] for item in accounts.json()["items"]} == {"alice", "bob"}
    assert all(item["enabled"] for item in accounts.json()["items"])


def test_A05_disabling_one_user_revokes_its_cookie_without_affecting_others(sessions):
    """A05: account revocation must affect existing sessions, not just new logins."""
    owner, admin, alice, bob = sessions
    assert alice.get("/api/v1/dashboard").status_code == 403
    assert bob.get("/api/v1/dashboard").status_code == 403
    disabled = owner.patch(
        "/api/v1/workspaces/alice", headers=admin, json={"enabled": False}
    )
    assert disabled.status_code == 200, disabled.text
    assert alice.get("/api/v1/dashboard").status_code == 401
    assert bob.get("/api/v1/dashboard").status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/dashboard", None),
    ("get", "/api/v1/campaigns", None),
    ("get", "/api/v1/campaigns/guessed-cross-workspace-id", None),
    ("get", "/api/v1/crm/search?q=other-company", None),
    ("get", "/api/v1/sales/board", None),
    ("get", "/api/v1/templates", None),
    ("get", "/api/v1/research/graph", None),
    ("get", "/api/v1/campaigns/guessed-cross-workspace-id/export", None),
    ("post", "/api/v1/campaigns", {"name": "Should not exist"}),
    ("post", "/api/v1/campaigns/guessed-cross-workspace-id/send", {}),
    ("post", "/api/v1/ai/recall/search", {"query": "other-company"}),
    ("post", "/api/v1/privacy/subject-access", {"email": "other@example.com"}),
])
def test_D451_legacy_shared_crm_refuses_non_owner_workspaces(sessions, method, path, body):
    """Until migration/cutover, unscoped CRM routes may not expose any customer."""
    owner, admin, alice, bob = sessions
    # The only install owner with shared legacy CRM authority is the install
    # API token. The workspace logins cannot claim any unowned CRM records.
    client = alice if "search" not in path else bob
    response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == 403, (method, path, response.text)
    assert "workspace" in response.json()["detail"].lower()
    assert owner.get("/api/v1/dashboard", headers=admin).status_code == 200


def test_D451_explicitly_isolated_workspace_features_remain_usable(sessions):
    owner, admin, alice, bob = sessions
    for client in (alice, bob):
        assert client.get("/api/v1/auth/session").status_code == 200
        assert client.get("/api/v1/agent-permissions").status_code == 200
        assert client.get("/api/v1/ai/egress-log").status_code == 200
    assert owner.get("/api/v1/campaigns", headers=admin).status_code == 200



def test_D451_known_unscoped_routes_cannot_escape_by_suffix():
    from offsetx_apollo_builder.api.app import is_unscoped_crm_api_path
    for protected in (
        "/api/v1/campaigns", "/api/v1/campaigns/private-id/export",
        "/api/v1/crm/accounts", "/api/v1/sales/leads/private-id",
        "/api/v1/privacy/deletions/request-id", "/api/v1/ai/recall/rebuild",
        "/api/v1/email-delivery/jobs", "/api/v1/agent-team/execute",
    ):
        assert is_unscoped_crm_api_path(protected), protected
    for independent in (
        "/api/v1/auth/session", "/api/v1/agent-permissions",
        "/api/v1/memory", "/api/v1/ai/chats", "/api/v1/ai/providers",
        "/api/v1/campaigns-public", "/health/live",
    ):
        assert not is_unscoped_crm_api_path(independent), independent
