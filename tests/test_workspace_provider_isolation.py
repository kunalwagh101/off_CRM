from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai import (
    DataClass,
    EgressBroker,
    EgressRequest,
    ProviderRegistry,
    WorkspaceEgressSettings,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=ROOT,
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="0.0.0.0",
        workspace_logins={
            "alpha": ("alice", "a" * 20),
            "beta": ("bob", "b" * 20),
        },
        session_secret="s" * 48,
        session_hours=2,
        allowed_hosts=("testserver", "crm.test"),
    )


def _login(client: TestClient, username: str, value: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": value},
    )
    assert response.status_code == 200


def test_one_login_cannot_read_another_workspaces_provider_configuration(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    with TestClient(app, base_url="https://crm.test") as client:
        _login(client, "alice", "a" * 20)
        response = client.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "A" * 24},
        )
        assert response.status_code == 200

        client.post("/api/v1/auth/logout", json={})
        _login(client, "bob", "b" * 20)

        payload = client.get("/api/v1/ai/providers").json()
        row = next(item for item in payload["providers"] if item["id"] == "mistral")
        assert row["connected"] is False
        assert row["has_key"] is False

        spoofed = client.get(
            "/api/v1/ai/providers",
            headers={"X-Workspace-ID": "alpha", "X-Workspace": "alpha"},
        ).json()
        row = next(item for item in spoofed["providers"] if item["id"] == "mistral")
        assert row["connected"] is False
        assert row["has_key"] is False

        response = client.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "B" * 24},
        )
        assert response.status_code == 200

        store = app.state.ai_workspaces
        assert store.key_for("alpha", "mistral") == "A" * 24
        assert store.key_for("beta", "mistral") == "B" * 24


def test_concurrent_model_calls_use_the_callers_workspace_key(monkeypatch) -> None:
    from offsetx_apollo_builder.ai import broker as broker_module

    barrier = threading.Barrier(2)
    seen: list[str] = []
    lock = threading.Lock()

    class Provider:
        def __init__(self, value: str) -> None:
            self.value = value
            self.last_usage = None

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            return self.value

    def create_provider(config, environ):
        value = next(iter(environ.values()))
        with lock:
            seen.append(value)
        barrier.wait(timeout=5)
        return Provider(value)

    monkeypatch.setattr(broker_module, "create_provider", create_provider)

    values = {
        ("alpha", "mistral"): "A" * 24,
        ("beta", "mistral"): "B" * 24,
    }
    broker = EgressBroker(
        registry=ProviderRegistry(ROOT / "config" / "providers.yaml"),
        credential_resolver=lambda provider_id: "",
        workspace_credential_resolver=lambda workspace_id, provider_id: values[
            (workspace_id, provider_id)
        ],
    )
    request = EgressRequest(task_type="workspace-test", data_class=DataClass.PUBLIC)

    def run(workspace_id: str) -> str:
        return broker.call(
            request,
            WorkspaceEgressSettings(
                workspace_id=workspace_id,
                enabled_provider_ids=("mistral",),
            ),
            system_prompt="write",
        ).text

    with ThreadPoolExecutor(max_workers=2) as pool:
        alpha = pool.submit(run, "alpha")
        beta = pool.submit(run, "beta")
        assert alpha.result(timeout=10) == "A" * 24
        assert beta.result(timeout=10) == "B" * 24

    assert sorted(seen) == ["A" * 24, "B" * 24]
