from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.backup import (
    create_encrypted_backup,
    restore_encrypted_backup,
)
from offsetx_apollo_builder.outreach.provider_profiles import ProviderProfileStore


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )


def test_provider_profile_secret_is_encrypted_and_never_returned(tmp_path):
    store = ProviderProfileStore(tmp_path)
    profile = store.upsert(
        {
            "id": "primary",
            "owner": "Kunal",
            "name": "Primary provider",
            "provider_type": "openai",
            "model": "test-model",
            "priority": 10,
        },
        api_key="super-secret-provider-key",
    )

    assert profile["credential_source"] == "encrypted_local"
    assert "api_key" not in profile
    assert "super-secret-provider-key" not in store.profile_path.read_text(encoding="utf-8")
    assert b"super-secret-provider-key" not in store.secret_path.read_bytes()
    assert store.key_path.stat().st_mode & 0o077 == 0


def test_encrypted_backup_round_trip_restores_database_and_local_controls(tmp_path):
    database = tmp_path / "outreach.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
    connection.execute("INSERT INTO sample VALUES ('before')")
    connection.commit()
    connection.close()
    (data_dir / "automation.json").write_text('{"enabled": true}', encoding="utf-8")

    backup = create_encrypted_backup(
        database_path=database,
        data_dir=data_dir,
        passphrase="correct horse battery staple",
    )
    connection = sqlite3.connect(database)
    connection.execute("UPDATE sample SET value = 'after'")
    connection.commit()
    connection.close()
    (data_dir / "automation.json").write_text('{"enabled": false}', encoding="utf-8")

    result = restore_encrypted_backup(
        backup,
        database_path=database,
        data_dir=data_dir,
        passphrase="correct horse battery staple",
    )

    connection = sqlite3.connect(database)
    value = connection.execute("SELECT value FROM sample").fetchone()[0]
    connection.close()
    assert value == "before"
    assert json.loads((data_dir / "automation.json").read_text())["enabled"] is True
    assert result["restored"] is True
    safety_copy = Path(result["safety_copy"])
    assert safety_copy.is_dir()
    connection = sqlite3.connect(safety_copy / "outreach.db")
    assert connection.execute("SELECT value FROM sample").fetchone()[0] == "after"
    connection.close()


def test_provider_automation_and_backup_api(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        saved = client.post(
            "/api/v1/provider-profiles",
            json={
                "id": "primary",
                "owner": "Kunal",
                "name": "Primary OpenAI",
                "provider_type": "openai",
                "model": "test-model",
                "api_key": "test-secret",
                "priority": 10,
            },
        )
        assert saved.status_code == 201
        assert saved.json()["credential_source"] == "encrypted_local"
        assert "api_key" not in saved.json()
        assert client.post(
            "/api/v1/provider-profiles/primary/test", json={"live_probe": False}
        ).json()["status"] == "configured"

        automation = client.patch(
            "/api/v1/automation",
            json={
                "enabled": True,
                "mode": "local",
                "interval_seconds": 3600,
                "max_messages_per_campaign": 5,
                "sync_replies_first": True,
            },
        )
        assert automation.status_code == 200
        assert automation.json()["enabled"] is True
        assert automation.json()["mode"] == "local"
        assert client.post("/api/v1/automation/run", json={}).status_code == 200

        exported = client.post(
            "/api/v1/backups/export",
            json={"passphrase": "correct horse battery staple"},
        )
        assert exported.status_code == 200
        assert exported.content.startswith(b"OFFSETXBACKUP1")
        status = client.get("/api/v1/settings/status").json()
        assert status["provider_profiles"] == 1
        assert status["automation"]["enabled"] is True


def test_web_api_rejects_local_command_provider_profiles(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/provider-profiles",
            json={
                "name": "unsafe command",
                "provider_type": "local_command",
                "extra": {"command": ["python", "-c", "print('unsafe')"]},
            },
        )

    assert response.status_code == 422


def test_automated_gmail_requires_exact_confirmation(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        payload = {
            "enabled": True,
            "mode": "gmail",
            "interval_seconds": 300,
            "max_messages_per_campaign": 5,
            "sync_replies_first": True,
        }
        rejected = client.patch("/api/v1/automation", json=payload)
        accepted = client.patch(
            "/api/v1/automation",
            json={**payload, "gmail_confirmation": "ENABLE AUTOMATED GMAIL"},
        )

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["gmail_live_authorized"] is True
