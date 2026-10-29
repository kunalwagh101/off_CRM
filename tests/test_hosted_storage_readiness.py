"""F-06.03: owner-only, truth-preserving hosted storage readiness report.

RED first: this endpoint does not yet exist. Do not declare a hosted database
production-safe when other stores and media still live on disposable disks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


OWNER_TOKEN = "storage-readiness-owner-" + "x" * 40
API = "/api/v1/storage/readiness"


def _settings(data: Path, *, secrets_key: str = "") -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=data / "offsetx_outreach.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=data.parent / "frontend-missing",
        host="127.0.0.1",
        api_token=OWNER_TOKEN,
        allowed_hosts=("testserver",),
        secrets_key=secrets_key,
    )


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    monkeypatch.delenv("OFFSETX_SECRETS_KEY", raising=False)


def _get(client: TestClient):
    return client.get(API, headers={"X-Offsetx-Token": OWNER_TOKEN})


def test_readiness_requires_owner_credentials(tmp_path, isolated):
    with TestClient(create_app(_settings(tmp_path / "local"))) as client:
        denied = client.get(API)
        assert denied.status_code == 401
        denied = client.get(API, headers={"X-Offsetx-Token": "invalid"})
        assert denied.status_code == 401
        assert _get(client).status_code == 200


def test_local_file_store_report_marks_unmounted_storage_unverified(tmp_path, isolated):
    with TestClient(create_app(_settings(tmp_path / "local"))) as client:
        response = _get(client)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["database"]["kind"] == "local"
        assert data["files"]["durability"] == "unverified"
        assert data["production"]["status"] == "blocked"
        assert "ephemeral_customer_files" in data["production"]["blockers"]
        names = [thing["name"] for thing in data["stores"]]
        assert len(names) == len(set(names))
        assert "CRM" in names
        assert "Media and outboxes" in names
        media = next(thing for thing in data["stores"] if thing["name"] == "Media and outboxes")
        assert media["durability"] == "unverified_file"


def test_hosted_database_does_not_make_undeclared_stores_durable(tmp_path, isolated, monkeypatch):
    database = tmp_path / "remote_db" / "hosted.sqlite3"
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(database))
    secret = Fernet.generate_key().decode()
    with TestClient(create_app(_settings(tmp_path / "local", secrets_key=secret))) as client:
        response = _get(client)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["database"]["kind"] == "hosted"
        assert body["production"]["status"] == "blocked"
        assert "hosted_production_not_supported" in body["production"]["blockers"]
        assert "ephemeral_customer_files" in body["production"]["blockers"]
        by_name = {thing["name"]: thing for thing in body["stores"]}
        assert by_name["CRM"]["durability"] == "hosted_database"
        assert by_name["AI settings and trust"]["durability"] == "hosted_database"
        assert by_name["Provider keys"]["durability"] == "hosted_database"
        assert by_name["Media and outboxes"]["durability"] == "unverified_file"
        assert by_name["Agent routines"]["durability"] == "unverified_file"
        assert by_name["Response cache"]["durability"] == "unverified_file"


def test_report_omits_url_keys_paths_and_customer_content(tmp_path, isolated, monkeypatch):
    path = tmp_path / "private-customer-connection" / "db.sqlite3"
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(path))
    key = Fernet.generate_key().decode()
    with TestClient(create_app(_settings(tmp_path / "private-customer-data", secrets_key=key))) as client:
        body = _get(client).text
        assert "private-customer-connection" not in body
        assert "private-customer-data" not in body
        assert str(path) not in body
        assert key not in body
        assert OWNER_TOKEN not in body
        assert "OFFSETX_DATABASE_URL" in body  # Public setting name is actionable.


def test_report_has_distinct_actionable_non_secret_next_steps(tmp_path, isolated):
    with TestClient(create_app(_settings(tmp_path / "local"))) as client:
        result = _get(client).json()
        actions = result["actions"]
        assert isinstance(actions, list) and len(actions) > 0
        assert all(isinstance(action, str) and action for action in actions)
        assert any("OFFSETX_PERSISTENT_MOUNT" in action for action in actions)
        json.dumps(result)


def test_non_owner_workspace_cannot_view_global_storage_inventory(tmp_path, isolated):
    with TestClient(create_app(_settings(tmp_path / "local"))) as owner:
        created = owner.post(
            "/api/v1/workspaces",
            headers={"X-Offsetx-Token": OWNER_TOKEN},
            json={
                "username": "regular-team-member",
                "workspace_id": "member-workspace",
                "password": "a-long-member-password-123",
            },
        )
        assert created.status_code == 201, created.text
        member = TestClient(owner.app)
        login = member.post(
            "/api/v1/auth/login",
            json={"username": "regular-team-member", "password": "a-long-member-password-123"},
        )
        assert login.status_code == 200, login.text
        denied = member.get(API)
        assert denied.status_code == 403, denied.text
        assert "stores" not in denied.text


def test_root_filesystem_mount_does_not_claim_data_durability(tmp_path, isolated):
    settings = _settings(tmp_path / "local")
    settings.persistent_mount = Path("/")  # Mountpoint, not a customer disk.
    with TestClient(create_app(settings)) as client:
        result = _get(client)
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["files"]["durability"] == "unverified"
        assert body["production"]["status"] == "blocked"
        assert "ephemeral_customer_files" in body["production"]["blockers"]
