"""S-06.03.06: scheduled email/content settings must survive free-plan restarts.

The actual app must use the hosted documents when OFFSETX_DATABASE_URL is
configured, without silently falling back to the disposable JSON files.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.db.hosted import HostedStorage
from offsetx_apollo_builder.distribution.automation import ContentAutomationService
from offsetx_apollo_builder.outreach.automation import AutomationService


def _email(path: Path, storage: HostedStorage | None = None) -> AutomationService:
    return AutomationService(
        path, engine_factory=lambda: None,
        mail_provider_factory=lambda mode, authorised: None,
        own_email_factory=lambda: "",
        hosted_storage=storage,
    )


def _content(path: Path, storage: HostedStorage | None = None) -> ContentAutomationService:
    return ContentAutomationService(
        path, trends_factory=lambda: None,
        pipeline_factory=lambda angle: None,
        distribution_factory=lambda: None,
        hosted_storage=storage,
    )


def test_timer_config_survives_removed_data_dir_and_new_store_instance(tmp_path):
    key = Fernet.generate_key().decode("ascii")
    database = tmp_path / "durable" / "settings.db"
    database.parent.mkdir()
    local = tmp_path / "ephemeral"
    local.mkdir()
    first = HostedStorage(str(database), key)
    _email(local / "automation.json", first).update(
        {"interval_seconds": 900, "max_messages_per_campaign": 17}
    )
    _content(local / "content_automation.json", first).update(
        {"interval_seconds": 7200, "posts_per_day": 0.5}
    )
    assert not (local / "automation.json").exists()
    assert not (local / "content_automation.json").exists()
    first.close()
    shutil.rmtree(local)
    local.mkdir()
    reopened = HostedStorage(str(database), key)
    assert _email(local / "automation.json", reopened).config()["max_messages_per_campaign"] == 17
    assert _content(local / "content_automation.json", reopened).config()["interval_seconds"] == 7200
    assert _content(local / "content_automation.json", reopened).config()["posts_per_day"] == 0.5
    reopened.close()


def test_ambiguous_local_timer_file_is_not_silently_ignored(tmp_path):
    key = Fernet.generate_key().decode("ascii")
    storage = HostedStorage(str(tmp_path / "hosted.db"), key)
    local = tmp_path / "local"
    local.mkdir()
    (local / "automation.json").write_text('{"enabled":true}', encoding="utf-8")
    (local / "content_automation.json").write_text('{"enabled":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="timer settings|automation settings"):
        _email(local / "automation.json", storage)
    with pytest.raises(ValueError, match="timer settings|automation settings"):
        _content(local / "content_automation.json", storage)
    storage.close()


@pytest.mark.parametrize("service", ["email", "content"])
def test_hosted_write_error_does_not_report_success_or_write_local_file(tmp_path, monkeypatch, service):
    key = Fernet.generate_key().decode("ascii")
    storage = HostedStorage(str(tmp_path / "hosted.db"), key)
    local = tmp_path / "local"
    path = local / ("automation.json" if service == "email" else "content_automation.json")
    timer = _email(path, storage) if service == "email" else _content(path, storage)

    def fail_write(_name, _body):
        raise OSError("simulated database unavailable")

    monkeypatch.setattr(storage, "write", fail_write)
    with pytest.raises(OSError, match="simulated database unavailable"):
        timer.update({"interval_seconds": 4200})
    assert not path.exists()
    storage.close()


def test_local_timer_configs_keep_their_existing_file_contract(tmp_path):
    email = _email(tmp_path / "automation.json")
    content = _content(tmp_path / "content_automation.json")
    email.update({"interval_seconds": 600})
    content.update({"interval_seconds": 1800})
    assert email.path.exists() and content.path.exists()
    assert _email(email.path).config()["interval_seconds"] == 600
    assert _content(content.path).config()["interval_seconds"] == 1800


def test_real_app_uses_hosted_timer_settings_and_reports_them_as_hosted(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    database = tmp_path / "hosted.db"
    data = tmp_path / "local"
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(database))
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=data / "offsetx_outreach.db",
        data_dir=data, export_dir=data / "exports",
        frontend_dist=tmp_path / "missing-frontend",
        host="127.0.0.1",
        api_token="timer-storage-test-token-" + "t" * 30,
        allowed_hosts=("testserver",),
    )
    app = create_app(settings)
    with TestClient(app, headers={"X-Offsetx-Token": settings.api_token}) as client:
        app.state.automation.update({"interval_seconds": 1800})
        app.state.content_automation.update({"interval_seconds": 5400})
        response = client.get("/api/v1/storage/readiness")
        assert response.status_code == 200, response.text
        timers = [row for row in response.json()["stores"] if row["name"] == "Timers"]
        assert timers == [{"name": "Timers", "durability": "hosted_database"}]
        assert not (data / "automation.json").exists()
        assert not (data / "content_automation.json").exists()

    shutil.rmtree(data)
    app2 = create_app(settings)
    with TestClient(app2, headers={"X-Offsetx-Token": settings.api_token}):
        assert app2.state.automation.config()["interval_seconds"] == 1800
        assert app2.state.content_automation.config()["interval_seconds"] == 5400
