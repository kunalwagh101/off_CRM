from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def settings(tmp_path, monkeypatch):
    for key in ("OFFSETX_DATABASE_URL", "OFFSETX_SECRETS_KEY", "OFFSETX_LOCAL_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OFFSETX_PUBLIC_DEMO", "1")
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "public-demo"))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(tmp_path / "public-demo" / "crm.db"))
    monkeypatch.setenv("OFFSETX_DEMO_USERNAME", "visitor")
    monkeypatch.setenv("OFFSETX_DEMO_PASSWORD", "Public-Demo-2026!")
    monkeypatch.setenv("OFFSETX_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("OFFSETX_ALLOWED_HOSTS", "testserver")
    return AppSettings.from_env(Path.cwd())


def test_public_hint_login_sample_data_and_logout(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    with TestClient(create_app(config)) as client:
        session = client.get("/api/v1/auth/session").json()
        assert session["public_demo"] == {
            "username": "visitor", "password": "Public-Demo-2026!", "read_only": False, "crm_read_only": True,
        }
        assert config.session_secret not in str(session)
        assert client.get("/api/v1/dashboard").status_code == 401
        login = client.post("/api/v1/auth/login", json={
            "username": "visitor", "password": "Public-Demo-2026!",
        })
        assert login.status_code == 200
        assert login.json()["workspace_id"].startswith("demo-")
        campaigns = client.get("/api/v1/campaigns").json()["items"]
        assert len(campaigns) == 1 and campaigns[0]["status"] == "paused"
        contacts = client.get(f"/api/v1/campaigns/{campaigns[0]['id']}/contacts").json()
        assert contacts["total"] == 3
        assert client.get("/api/v1/operations/health").status_code == 403
        assert client.post("/api/v1/auth/logout", json={}).status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 401
    with TestClient(create_app(config)) as restarted:
        restarted.post("/api/v1/auth/login", json={
            "username": "visitor", "password": "Public-Demo-2026!",
        })
        assert len(restarted.get("/api/v1/campaigns").json()["items"]) == 1


def test_public_demo_refuses_mutations_before_validation_even_anonymous(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path, monkeypatch))) as client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            for path in ("/api/v1/campaigns", "/api/v1/ai/workspace/mailbox-unlock", "/api/v1/workspaces",
                         "/api/v1/provider-profiles", "/api/v1/email-delivery/events/ses/sns"):
                response = client.request(method, path, content=b"invalid-json")
                assert response.status_code == 403, (method, path, response.text)
                assert "read-only" in response.json()["detail"]
        assert client.get("/api/v1/notion/databases").status_code == 403


def test_public_demo_refuses_existing_private_folder(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    config.data_dir.mkdir(parents=True)
    (config.data_dir / "private.txt").write_text("customer data")
    with pytest.raises(ValueError, match="empty dedicated"):
        create_app(config)
    assert not (config.data_dir / "workspace_auth.db").exists()


def test_private_login_never_advertises_its_password(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_PUBLIC_DEMO", "0")
    config = AppSettings.from_env(Path.cwd())
    with TestClient(create_app(config)) as client:
        response = client.get("/api/v1/auth/session")
        assert "public_demo" not in response.json()
        assert config.demo_password not in response.text


def test_public_demo_rejects_shared_database_before_connecting(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", "postgresql://private:secret@invalid/private")
    with pytest.raises(ValueError, match="dedicated"):
        create_app(config)


@pytest.mark.parametrize("field", ["database_path", "export_dir", "gmail_token"])
def test_public_demo_refuses_paths_outside_dedicated_root(tmp_path, monkeypatch, field):
    config = settings(tmp_path, monkeypatch)
    setattr(config, field, tmp_path / "private.db")
    with pytest.raises(ValueError, match="dedicated"):
        create_app(config)


def test_signed_in_visitor_cannot_write_or_become_owner(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    with TestClient(create_app(config)) as client:
        client.post("/api/v1/auth/login", json={
            "username": "visitor", "password": "Public-Demo-2026!",
        })
        assert client.get("/api/v1/auth/session").json()["workspace_id"].startswith("demo-")
        for route in client.app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/") or path in {"/api/v1/auth/login", "/api/v1/auth/logout"}:
                continue
            import re
            path = re.sub(r"\{[^}]+\}", "example", path)
            for method in (getattr(route, "methods", set()) or set()) - {"GET", "HEAD", "OPTIONS"}:
                from offsetx_apollo_builder.api.public_demo import request_allowed
                if not request_allowed(method, path):
                    assert client.request(method, path, content=b"{}").status_code == 403, (method, path)
        for name in ("automation", "content_automation", "agent_routines"):
            service = getattr(client.app.state, name)
            assert service._task is None


def test_changed_public_password_refuses_to_advertise_stale_login(tmp_path, monkeypatch):
    config = settings(tmp_path, monkeypatch)
    with TestClient(create_app(config)):
        pass
    config.demo_password = "New-Public-Demo-2026!"
    with pytest.raises(ValueError, match="differs from stored"):
        create_app(config)
