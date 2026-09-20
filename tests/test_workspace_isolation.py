from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import WorkspaceAuthStore
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.browser.vault import SessionVault


SESSION_SECRET = "workspace-session-secret-" + "x" * 32
ADMIN_TOKEN = "workspace-admin-token-" + "y" * 32


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=ADMIN_TOKEN,
        session_secret=SESSION_SECRET,
        allowed_hosts=("testserver",),
    )


def test_two_workspace_logins_resolve_to_different_workspace_ids(tmp_path):
    auth = WorkspaceAuthStore(
        tmp_path / "auth.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )
    alice = auth.create(
        username="alice",
        workspace_id="alpha",
        password="alice-password-123",
    )
    bob = auth.create(
        username="bob",
        workspace_id="beta",
        password="bob-password-456",
    )

    alice_login = auth.authenticate("alice", "alice-password-123")
    bob_login = auth.authenticate("bob", "bob-password-456")
    assert alice_login is not None and alice_login.workspace_id == "alpha"
    assert bob_login is not None and bob_login.workspace_id == "beta"
    assert auth.verify(auth.issue(alice)).workspace_id == "alpha"
    assert auth.verify(auth.issue(bob)).workspace_id == "beta"


def test_password_rotation_invalidates_existing_workspace_sessions(tmp_path):
    auth = WorkspaceAuthStore(
        tmp_path / "auth.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )
    identity = auth.create(
        username="alice",
        workspace_id="alpha",
        password="alice-password-123",
    )
    old_cookie = auth.issue(identity)
    assert auth.verify(old_cookie) is not None

    auth.set_password("alice", "alice-new-password-789")

    assert auth.verify(old_cookie) is None
    assert auth.authenticate("alice", "alice-password-123") is None
    assert auth.authenticate("alice", "alice-new-password-789") is not None


def test_provider_keys_are_encrypted_and_workspace_isolated(tmp_path):
    store = WorkspaceAISettingsStore(tmp_path / "ai", ProviderRegistry())
    store.set_key("alpha", "mistral", "ALPHA-PROVIDER-SECRET")
    store.set_key("beta", "mistral", "BETA-PROVIDER-SECRET")

    assert store.key_for("alpha", "mistral") == "ALPHA-PROVIDER-SECRET"
    assert store.key_for("beta", "mistral") == "BETA-PROVIDER-SECRET"
    assert store.key_for("alpha", "openai") == ""

    raw = b"".join(
        path.read_bytes()
        for path in (tmp_path / "ai").rglob("*")
        if path.is_file()
    )
    assert b"ALPHA-PROVIDER-SECRET" not in raw
    assert b"BETA-PROVIDER-SECRET" not in raw


def test_browser_sessions_are_workspace_isolated_for_the_same_platform(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    vault = SessionVault(
        tmp_path / "vault",
        passphrase="workspace-vault-passphrase-long-enough",
    )
    vault.seal(
        "alpha",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "ALPHA-COOKIE", "domain": ".linkedin.com"}]},
    )
    vault.seal(
        "beta",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "BETA-COOKIE", "domain": ".linkedin.com"}]},
    )

    assert vault.unseal("alpha", "linkedin")["cookies"][0]["value"] == "ALPHA-COOKIE"
    assert vault.unseal("beta", "linkedin")["cookies"][0]["value"] == "BETA-COOKIE"
    assert vault.inspect("alpha", "linkedin").key_id != vault.inspect("beta", "linkedin").key_id


def test_authenticated_workspace_selects_only_its_provider_keys(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as admin:
        headers = {"X-Offsetx-Token": ADMIN_TOKEN}
        for username, workspace, password in (
            ("alice", "alpha", "alice-password-123"),
            ("bob", "beta", "bob-password-456"),
        ):
            response = admin.post(
                "/api/v1/workspaces",
                headers=headers,
                json={
                    "username": username,
                    "workspace_id": workspace,
                    "password": password,
                },
            )
            assert response.status_code == 201

        alice = TestClient(admin.app)
        login = alice.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "alice-password-123"},
        )
        assert login.status_code == 200
        assert login.json()["workspace_id"] == "alpha"
        connected = alice.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "ALPHA-KEY", "model_id": "mistral-small-latest"},
        )
        assert connected.status_code == 200
        assert connected.json()["workspace"] == "alpha"

        bob = TestClient(admin.app)
        login = bob.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "bob-password-456"},
        )
        assert login.status_code == 200
        assert login.json()["workspace_id"] == "beta"
        providers = bob.get("/api/v1/ai/providers")
        assert providers.status_code == 200
        assert providers.json()["workspace_id"] == "beta"
        mistral = next(item for item in providers.json()["providers"] if item["id"] == "mistral")
        assert mistral["has_key"] is False

        # The install-level API token is backward-compatible and deliberately
        # remains the local workspace rather than impersonating a team member.
        local = admin.get("/api/v1/auth/session", headers=headers)
        assert local.status_code == 200
        assert local.json()["workspace_id"] == "local"


def test_workspace_admin_routes_are_not_available_to_a_workspace_session(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = {"X-Offsetx-Token": ADMIN_TOKEN}
        assert client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={
                "username": "alice",
                "workspace_id": "alpha",
                "password": "alice-password-123",
            },
        ).status_code == 201

        assert client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "alice-password-123"},
        ).status_code == 200

        response = client.post(
            "/api/v1/workspaces",
            json={
                "username": "mallory",
                "workspace_id": "mallory",
                "password": "mallory-password-123",
            },
        )
        assert response.status_code == 403
