"""Visitor AI routes use the real broker; test provider replies are explicit doubles."""
import json

from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.broker import EgressBroker
from offsetx_apollo_builder.api.app import create_app
from test_public_demo import settings


def login(client):
    return client.post("/api/v1/auth/login", json={
        "username": "visitor", "password": "Public-Demo-2026!",
    })


def test_visitors_can_use_ai_without_sharing_keys_or_chats(tmp_path, monkeypatch):
    app = create_app(settings(tmp_path, monkeypatch))
    with TestClient(app) as first:
        second = TestClient(app)
        assert login(first).status_code == 200
        assert login(second).status_code == 200
        ws1 = first.get("/api/v1/auth/session").json()["workspace_id"]
        ws2 = second.get("/api/v1/auth/session").json()["workspace_id"]
        assert ws1 != ws2 and ws1 != "local" and ws2 != "local"
        assert first.post("/api/v1/ai/providers/mistral/connect", json={
            "api_key": "test-only-first-visitor-key", "data_policy": "minimal",
        }).status_code == 200
        assert app.state.ai_workspaces.key_for(ws1, "mistral") == "test-only-first-visitor-key"
        assert not app.state.ai_workspaces.key_for(ws2, "mistral")
        assert all(not p["connected"] for p in second.get("/api/v1/ai/providers").json()["providers"])
        chat = first.post("/api/v1/ai/chats", json={"title": "My private visitor chat"})
        assert chat.status_code == 200
        assert second.get("/api/v1/ai/chats").json()["items"] == []
        project = first.post("/api/v1/ai/projects", json={"name": "My project"}).json()
        assert second.delete(f"/api/v1/ai/projects/{project['id']}").status_code == 404
        assert second.post("/api/v1/ai/providers/mistral/connect", json={
            "api_key": "test-only-second-visitor-key", "data_policy": "minimal",
        }).status_code == 200
        assert first.post("/api/v1/auth/logout", json={}).status_code == 200
        assert not app.state.ai_workspaces.key_for(ws1, "mistral")
        assert app.state.ai_workspaces.key_for(ws2, "mistral") == "test-only-second-visitor-key"
        assert first.get("/api/v1/ai/providers").status_code == 401


def test_demo_instruction_reaches_planner_and_each_worker_through_broker(tmp_path, monkeypatch):
    calls = []

    class TestProvider:
        def generate(self, *, system_prompt, user_prompt):
            calls.append(json.loads(user_prompt))
            if len(calls) == 1:
                return json.dumps({"steps": [
                    {"title": "Research", "instructions": "Summarise EU importer needs", "needs": "public"},
                    {"title": "Draft", "instructions": "Draft a short outreach email", "needs": "public"},
                ]})
            return "Test-only worker response"

    monkeypatch.setattr(EgressBroker, "_instantiate", lambda *args, **kwargs: TestProvider())
    with TestClient(create_app(settings(tmp_path, monkeypatch))) as client:
        login(client)
        assert client.post("/api/v1/ai/providers/mistral/connect", json={
            "api_key": "test-only-key", "data_policy": "minimal",
        }).status_code == 200
        response = client.post("/api/v1/ai/run", json={
            "mode": "orchestrated", "data_class": "public",
            "instructions": "Research EU importer needs, then draft an email.",
        })
        assert response.status_code == 200, response.text
        assert [step["title"] for step in response.json()["steps"]] == ["Research", "Draft"]
        assert len(calls) == 3
        assert client.get("/api/v1/ai/egress-log").json()["total"] == 3
        assert client.post("/api/v1/campaigns", json={"name": "Do not mutate sample CRM"}).status_code == 403


def test_demo_with_no_provider_reports_setup_instead_of_disabling_ai(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path, monkeypatch))) as client:
        login(client)
        modes = client.get("/api/v1/ai/modes")
        assert modes.status_code == 200
        assert modes.json()["connected_count"] == 0
        assert all(not mode["available"] for mode in modes.json()["modes"])
        assert client.post("/api/v1/ai/run", json={
            "mode": "orchestrated", "data_class": "public", "instructions": "Write a short email",
        }).status_code == 409
        assert client.post("/api/v1/ai/image", json={
            "prompt": "A cargo ship at a port", "data_class": "public",
        }).status_code == 409


def test_public_ai_routes_require_auth_and_cannot_open_other_integrations(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path, monkeypatch))) as client:
        assert client.get("/api/v1/ai/providers").status_code == 401
        assert client.post("/api/v1/ai/chats", json={"title": "x"}).status_code == 401
        login(client)
        assert client.post("/api/v1/ai/workspace/mailbox-unlock", json={}).status_code == 403
        assert client.post("/api/v1/ai/chats/x/browser-runs", json={}).status_code == 403


def test_egress_record_id_never_crosses_workspace_boundary(tmp_path):
    from test_ai_api import _settings

    with TestClient(create_app(_settings(tmp_path))) as client:
        log_id = client.app.state.ai_egress_log.record(
            workspace_id="another-visitor", provider_id="mistral", status="succeeded",
            payload={"instructions": "Other visitor private instructions"},
        )
        response = client.get(f"/api/v1/ai/egress-log/{log_id}")
        assert response.status_code == 404
        assert "Other visitor" not in response.text
