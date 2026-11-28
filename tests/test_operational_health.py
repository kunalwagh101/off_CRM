"""F-06.02: owner-only operational health, distinct from web liveness/readiness."""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = "qa-operational-health-" + "h" * 40
API = "/api/v1/operations/health"
AUTH = {"X-Offsetx-Token": TOKEN}


def settings(tmp_path):
    data = tmp_path / "data"
    return AppSettings(
        project_root=Path.cwd(), database_path=data/"crm.db",
        data_dir=data, export_dir=data/"exports",
        frontend_dist=tmp_path/"missing", api_token=TOKEN,
        allowed_hosts=("testserver",),
    )


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    monkeypatch.delenv("OFFSETX_SECRETS_KEY", raising=False)


class Stopped:
    def done(self):
        return True


def _get(client):
    return client.get(API, headers=AUTH)


def test_operator_health_requires_install_owner(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.get(API).status_code == 401
        assert client.get(API, headers={"X-Offsetx-Token": "wrong"}).status_code == 401
        created = client.post("/api/v1/workspaces", headers=AUTH, json={
            "username":"regular", "workspace_id":"regular-team",
            "password":"long-secret-regular-password",
        })
        assert created.status_code == 201, created.text
        member = TestClient(client.app)
        assert member.post("/api/v1/auth/login", json={
            "username":"regular", "password":"long-secret-regular-password",
        }).status_code == 200
        denied = member.get(API)
        assert denied.status_code == 403
        assert "components" not in denied.text
        assert _get(client).status_code == 200


def test_disabled_optional_automations_do_not_mark_web_unhealthy(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        monkeypatch.setattr(client.app.state.automation, "config", lambda: {"enabled":False})
        monkeypatch.setattr(client.app.state.content_automation, "config", lambda: {"enabled":False})
        response = _get(client)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["alert_required"] is False
        assert all(row["state"] == "disabled" for row in body["components"])
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize("component", ["automation", "content_automation"])
def test_enabled_stopped_scheduler_is_degraded_without_breaking_readiness(
    tmp_path, monkeypatch, component
):
    with TestClient(create_app(settings(tmp_path))) as client:
        service = getattr(client.app.state, component)
        monkeypatch.setattr(service, "config", lambda: {"enabled":True})
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(service, "_task", Stopped())
            result = _get(client)
        assert result.status_code == 200
        body = result.json()
        row = next(x for x in body["components"] if x["name"] == component)
        assert row["state"] == "degraded"
        assert row["code"] == "scheduler_not_running"
        assert body["status"] == "degraded"
        assert body["alert_required"] is True
        assert client.get("/health/ready").status_code == 200


def test_enabled_agent_routine_scheduler_stopped_is_degraded(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        store = client.app.state.agent_routine_store
        with store.connection() as conn:
            conn.execute(
                """INSERT INTO agent_routines
                (id, workspace_id, name, goal, target_url, target_host,
                 trigger_type, interval_seconds, event_name, step_budget,
                 enabled, next_due_at, created_at, updated_at)
                 VALUES ('routine-1','local','Check','Check page','https://example.org',
                 'example.org','interval',60,'',2,1,0,0,0)"""
            )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(client.app.state.agent_routines, "_task", Stopped())
            body = _get(client).json()
        row = next(x for x in body["components"] if x["name"] == "agent_routines")
        assert row["state"] == "degraded"
        assert row["code"] == "scheduler_not_running"
        assert body["alert_required"]


def test_failure_messages_never_leak_secrets_or_fs_paths(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        secret = "sk-secret-ops-private-token"
        service = client.app.state.automation
        monkeypatch.setattr(service, "config", lambda: {"enabled":True})
        service.last_error = f"Connection failed: {secret} at /private/user/customer.json"
        response = _get(client)
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert "scheduler_error" in [x["code"] for x in response.json()["components"]]
        assert secret not in response.text
        assert "/private/user" not in response.text
        assert TOKEN not in response.text


def test_config_failure_reports_unknown_not_false_success(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        def broken():
            raise RuntimeError("sensitive-private-path-and-password")
        monkeypatch.setattr(client.app.state.automation, "config", broken)
        response = _get(client)
        assert response.status_code == 200, response.text
        body = response.json()
        row = next(x for x in body["components"] if x["name"] == "automation")
        assert row["state"] == "unknown"
        assert row["code"] == "inspection_failed"
        assert row["error_id"].startswith("E-")
        assert "sensitive-private" not in response.text
        assert body["alert_required"] is True


def _worker(client):
    body = _get(client).json()
    return next(x for x in body["components"] if x["name"] == "external_email_worker"), body


def test_expected_worker_missing_stale_and_recent_progress(tmp_path):
    from datetime import timedelta
    from offsetx_apollo_builder.outreach.models import utc_now

    config = settings(tmp_path)
    config.email_worker_expected = True
    with TestClient(create_app(config)) as client:
        row, body = _worker(client)
        assert row["code"] == "worker_progress_missing" and body["alert_required"]
        assert client.get("/health/ready").status_code == 200
        store = client.app.state.email_delivery.store
        store.record_worker_progress(now=utc_now() - timedelta(minutes=5))
        row, body = _worker(client)
        assert row["code"] == "worker_progress_stale" and body["alert_required"]
        store.record_worker_progress(now=utc_now())
        row, _ = _worker(client)
        assert row["state"] == "healthy" and row["code"] == "recent_worker_progress"
    with TestClient(create_app(config)) as client:
        row, _ = _worker(client)
        assert row["code"] == "recent_worker_progress"


def test_worker_inspection_failure_has_safe_reference(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path))) as client:
        def broken(**_):
            raise RuntimeError("SECRET_WORKER_DB_VALUE")
        monkeypatch.setattr(client.app.state.email_delivery.store, "worker_progress_snapshot", broken)
        row, body = _worker(client)
        assert row["state"] == "unknown" and row["error_id"].startswith("E-")
        assert body["alert_required"] and "SECRET_WORKER_DB_VALUE" not in str(body)
        assert client.get("/health/ready").status_code == 200
