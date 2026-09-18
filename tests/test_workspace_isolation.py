"""Acceptance tests for S-06.01.01 workspace login/key/session isolation."""
from __future__ import annotations

import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai import (
    DataClass,
    EgressBroker,
    EgressRequest,
    ProviderRegistry,
    WorkspaceEgressSettings,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import WorkspaceSessionAuth
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.browser.identity import ConnectionStore, Reading, platform
from offsetx_apollo_builder.browser.vault import SessionVault

REPO_ROOT = Path(__file__).resolve().parents[1]
PASSPHRASE = "workspace-isolation-test-passphrase"


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=REPO_ROOT,
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="0.0.0.0",
        workspace_logins={
            "alpha": ("alice", "alpha-password-123"),
            "beta": ("bob", "beta-password-1234"),
        },
        session_secret="s" * 48,
        session_hours=2,
        allowed_hosts=("testserver", "crm.test"),
    )


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_signed_login_carries_one_workspace_and_tampering_breaks_signature() -> None:
    auth = WorkspaceSessionAuth(
        logins={
            "alpha": ("alice", "alpha-password-123"),
            "beta": ("bob", "beta-password-1234"),
        },
        session_secret="x" * 48,
        session_hours=1,
    )
    identity = auth.authenticate("alice", "alpha-password-123")
    assert identity is not None
    assert identity.workspace_id == "alpha"

    token = auth.issue(identity, now=1_000)
    verified = auth.verify(token, now=1_001)
    assert verified is not None
    assert verified.workspace_id == "alpha"

    encoded, signature = token.split(".", 1)
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    tampered_raw = raw.replace("\nalpha\n", "\nbeta\n", 1)
    tampered_encoded = (
        base64.urlsafe_b64encode(tampered_raw.encode()).rstrip(b"=").decode()
    )
    assert auth.verify(f"{tampered_encoded}.{signature}", now=1_001) is None


def test_workspace_config_rejects_duplicate_usernames(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.workspace_logins["beta"] = ("alice", "another-password-123")
    with pytest.raises(ValueError, match="configured more than once"):
        settings.validate()


def test_login_selects_workspace_server_side_and_headers_cannot_switch_it(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    with TestClient(app, base_url="https://crm.test") as client:
        alpha = _login(client, "alice", "alpha-password-123")
        assert alpha["workspace_id"] == "alpha"
        assert client.get("/api/v1/auth/session").json()["workspace_id"] == "alpha"

        connected = client.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "alpha-provider-key"},
        )
        assert connected.status_code == 200

        client.post("/api/v1/auth/logout", json={})
        beta = _login(client, "bob", "beta-password-1234")
        assert beta["workspace_id"] == "beta"

        beta_view = client.get("/api/v1/ai/providers").json()
        mistral = next(item for item in beta_view["providers"] if item["id"] == "mistral")
        assert mistral["connected"] is False
        assert mistral["has_key"] is False

        spoofed = client.get(
            "/api/v1/ai/providers",
            headers={"X-Workspace-ID": "alpha", "X-Workspace": "alpha"},
        ).json()
        mistral = next(item for item in spoofed["providers"] if item["id"] == "mistral")
        assert mistral["connected"] is False
        assert mistral["has_key"] is False

        connected = client.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "beta-provider-key"},
        )
        assert connected.status_code == 200

        store = app.state.ai_workspaces
        assert store.key_for("alpha", "mistral") == "alpha-provider-key"
        assert store.key_for("beta", "mistral") == "beta-provider-key"


def test_browser_connection_records_and_vault_material_are_workspace_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from offsetx_apollo_builder.browser import vault as vault_module

    store = ConnectionStore(tmp_path)
    linkedin = platform("linkedin")
    store.record("alpha", Reading("connected", "signed-in marker"), linkedin)
    assert store.get("alpha", "linkedin").state == "connected"
    assert store.get("beta", "linkedin").state == "unknown"

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    vault = SessionVault(tmp_path / "vault", passphrase=PASSPHRASE)
    vault.seal(
        "alpha",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "ALPHA", "domain": ".linkedin.com"}]},
    )
    vault.seal(
        "beta",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "BETA", "domain": ".linkedin.com"}]},
    )

    assert vault.unseal("alpha", "linkedin")["cookies"][0]["value"] == "ALPHA"
    assert vault.unseal("beta", "linkedin")["cookies"][0]["value"] == "BETA"
    assert vault.inspect("alpha", "linkedin").key_id != vault.inspect("beta", "linkedin").key_id


def test_concurrent_workspace_model_calls_never_swap_provider_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from offsetx_apollo_builder.ai import broker as broker_module

    barrier = threading.Barrier(2)
    created: list[str] = []
    created_lock = threading.Lock()

    class _Provider:
        def __init__(self, key: str) -> None:
            self.key = key
            self.last_usage = None

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            return self.key

    def fake_create_provider(config, environ):
        key = next(iter(environ.values()))
        with created_lock:
            created.append(key)
        barrier.wait(timeout=5)
        return _Provider(key)

    monkeypatch.setattr(broker_module, "create_provider", fake_create_provider)
    keys = {
        ("alpha", "mistral"): "alpha-provider-key",
        ("beta", "mistral"): "beta-provider-key",
    }
    broker = EgressBroker(
        registry=ProviderRegistry(REPO_ROOT / "config" / "providers.yaml"),
        credential_resolver=lambda provider_id: pytest.fail(
            "legacy resolver used despite workspace resolver"
        ),
        workspace_credential_resolver=lambda workspace_id, provider_id: keys[
            (workspace_id, provider_id)
        ],
    )
    request = EgressRequest(task_type="workspace-test", data_class=DataClass.PUBLIC)

    def run(workspace_id: str) -> str:
        settings = WorkspaceEgressSettings(
            workspace_id=workspace_id,
            enabled_provider_ids=("mistral",),
        )
        return broker.call(request, settings, system_prompt="write").text

    with ThreadPoolExecutor(max_workers=2) as pool:
        alpha_future = pool.submit(run, "alpha")
        beta_future = pool.submit(run, "beta")
        assert alpha_future.result(timeout=10) == "alpha-provider-key"
        assert beta_future.result(timeout=10) == "beta-provider-key"

    assert sorted(created) == ["alpha-provider-key", "beta-provider-key"]
