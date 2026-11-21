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
    ("post", "/api/v1/backups/export", {}),
    ("post", "/api/v1/backups/restore", {}),
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
        "/api/v1/backups/export", "/api/v1/backups/restore",
    ):
        assert is_unscoped_crm_api_path(protected), protected
    for independent in (
        "/api/v1/auth/session", "/api/v1/agent-permissions",
        "/api/v1/memory", "/api/v1/ai/chats", "/api/v1/ai/providers",
        "/api/v1/image-assets/image-private/file",
        "/api/v1/video-projects/project-private",
        "/api/v1/campaigns/campaign-fixture/image-briefs",
        "/api/v1/campaigns/campaign-fixture/video-projects",
        "/api/v1/campaigns-public", "/health/live",
    ):
        assert not is_unscoped_crm_api_path(independent), independent



def test_D451_entire_live_api_route_inventory_has_a_tenancy_decision(sessions):
    """A05/D-451: a new route must not bypass the temporary shared-CRM barrier.

    Fail closed for any new API family until its storage and workspace
    ownership have been reviewed. This inspects *registered* FastAPI routes,
    including routes provided by included routers, not just @app decorators.
    """
    from fastapi.routing import APIRoute
    from offsetx_apollo_builder.api.app import (
        is_unscoped_crm_api_path, is_workspace_scoped_media_path,
    )

    owner, _, _, _ = sessions
    scoped_roots = {
        "/auth", "/workspaces", "/settings", "/provider-profiles",
        "/companion-tools", "/companions", "/companion-skills",
        "/memory", "/agent-permissions", "/operations", "/video",
        "/campaign-kinds", "/storage", "/meetings", "/meta",
    }
    # One-click unsubscribe is a deliberate public, signed-token capability;
    # do not put it behind workspace login or D-451's CRM middleware.
    token_capability_roots = {"/email/unsubscribe"}
    scoped_ai_roots = {
        "/ai/projects", "/ai/chats", "/ai/providers", "/ai/workspace",
        "/ai/modes", "/ai/image", "/ai/egress-log", "/ai/failure-kinds",
        "/ai/cache",
    }

    def root_matches(path, root):
        return path == root or path.startswith(root + "/")

    unclassified = []
    guarded = []
    for route in owner.app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        path = route.path
        if is_unscoped_crm_api_path(path):
            guarded.append(path)
            continue
        if is_workspace_scoped_media_path(path):
            continue
        relative = path[len("/api/v1"):]
        if any(root_matches(relative, root) for root in scoped_roots):
            continue
        if any(root_matches(relative, root) for root in token_capability_roots):
            continue
        if any(root_matches(relative, root) for root in scoped_ai_roots):
            continue
        unclassified.append(path)
    assert guarded, "The live inventory missed all D-451 CRM routes"
    assert not unclassified, (
        "A new API route needs an explicit workspace ownership/guard review: "
        + ", ".join(sorted(set(unclassified)))
    )


def test_D451_every_registered_shared_crm_get_is_blocked_over_real_http(sessions):
    """A05: non-owner cookies cannot read any declared shared-CRM GET route."""
    from fastapi.routing import APIRoute
    from offsetx_apollo_builder.api.app import is_unscoped_crm_api_path
    import re

    owner, _, alice, bob = sessions
    tested = []
    for route in owner.app.routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods:
            continue
        path = route.path
        if not is_unscoped_crm_api_path(path):
            continue
        # A synthetic ID reaches the authentication middleware without
        # selecting a real user's row or making external API calls.
        synthetic_path = re.sub(r"\{[^{}]+\}", "unowned-probe-id", path)
        response = (alice if len(tested) % 2 == 0 else bob).get(synthetic_path)
        assert response.status_code == 403, (
            "Shared-CRM GET route escaped workspace containment",
            path, response.status_code,
        )
        tested.append(path)
    assert len(tested) >= 30, "Live shared-CRM route matrix unexpectedly shrank"


def test_D451_every_registered_shared_crm_mutation_is_denied_before_parsing(sessions):
    """A05: all live shared-CRM mutation routes fail closed for other workspaces.

    Query the application's actual route table, including mounted routers.
    The dummy IDs and invalid bodies must be rejected in middleware before
    reaching any worker, provider, database mutation or action handler.
    """
    from fastapi.routing import APIRoute
    from offsetx_apollo_builder.api.app import is_unscoped_crm_api_path
    import re

    owner, _, alice, bob = sessions
    writes = []
    allowed_verbs = {"POST", "PATCH", "PUT", "DELETE"}
    for route in owner.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not is_unscoped_crm_api_path(route.path):
            continue
        for method in sorted(set(route.methods) & allowed_verbs):
            path = re.sub(r"\{[^{}]+\}", "unowned-probe-id", route.path)
            client = (alice, bob)[len(writes) % 2]
            response = client.request(
                method, path, json={"malicious_field": "untrusted-input"},
            )
            assert response.status_code == 403, (
                "Unscoped CRM mutation reached a handler", method,
                route.path, response.status_code,
            )
            writes.append((method, route.path))
    assert len(writes) >= 40, "The mutation route inventory unexpectedly shrank"
