"""S-06.03.06: operator-controlled migration of legacy automation settings.

No implicit send, no silent overwrite, secure archive, and reversible failure.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder import db_cli
from offsetx_apollo_builder.db.hosted import HostedStorage
from offsetx_apollo_builder.db.timer_import import TimerMigrationError, migrate_timers
from offsetx_apollo_builder.distribution.automation import ContentAutomationService
from offsetx_apollo_builder.outreach.automation import AutomationService


@pytest.fixture
def legacy(tmp_path):
    data = tmp_path / "legacy-data"
    data.mkdir()
    email = {
        "enabled": True,
        "mode": "gmail",
        "gmail_live_authorized": True,
        "interval_seconds": 900,
        "max_messages_per_campaign": 12,
    }
    content = {
        "enabled": True,
        "interval_seconds": 7200,
        "posts_per_day": 2.0,
        "pipelines": [{
            "distribution_campaign_id": "campaign-a",
            "image_campaign_id": "images-a",
            "account_ids": ["account-a"],
            "enabled": True,
        }],
    }
    (data / "automation.json").write_text(json.dumps(email), encoding="utf-8")
    (data / "content_automation.json").write_text(json.dumps(content), encoding="utf-8")
    return data


@pytest.fixture
def storage(tmp_path):
    connection = HostedStorage(str(tmp_path / "remote.db"), Fernet.generate_key().decode())
    yield connection
    connection.close()


def _email(path: Path, storage: HostedStorage):
    return AutomationService(
        path, hosted_storage=storage,
        engine_factory=lambda: None, mail_provider_factory=lambda *_: None,
        own_email_factory=lambda: "",
    )


def _content(path: Path, storage: HostedStorage):
    return ContentAutomationService(
        path, hosted_storage=storage,
        trends_factory=lambda: None, pipeline_factory=lambda _: None,
        distribution_factory=lambda: None,
    )


def test_import_preserves_archive_and_requires_reapproval_before_unattended_actions(
    legacy, storage, tmp_path
):
    archive = tmp_path / "external-archive"
    old = {p.name: p.read_bytes() for p in legacy.glob("*.json")}
    assert sorted(migrate_timers(storage, legacy, archive, import_settings=True)) == [
        "automation.json", "content_automation.json"
    ]
    assert not (legacy / "automation.json").exists()
    assert not (legacy / "content_automation.json").exists()
    for name, body in old.items():
        backed = archive / name
        assert backed.read_bytes() == body
        assert stat.S_IMODE(backed.stat().st_mode) == 0o600
    assert stat.S_IMODE(archive.stat().st_mode) == 0o700
    email = _email(legacy / "automation.json", storage).config()
    content = _content(legacy / "content_automation.json", storage).config()
    assert email["interval_seconds"] == 900
    assert email["max_messages_per_campaign"] == 12
    assert email["enabled"] is False
    assert email["gmail_live_authorized"] is False
    assert content["interval_seconds"] == 7200
    assert content["enabled"] is False
    assert content["pipelines"][0]["enabled"] is False


def test_skip_keeps_preexisting_hosted_state_and_preserves_legacy_archive(legacy, storage, tmp_path):
    with storage.exclusive():
        storage.write("timer.email", '{"interval_seconds": 3600, "enabled": false}')
    archive = tmp_path / "archive"
    assert len(migrate_timers(storage, legacy, archive, import_settings=False)) == 2
    assert _email(legacy / "automation.json", storage).config()["interval_seconds"] == 3600
    assert storage.read("timer.content") is None
    assert (archive / "automation.json").exists()
    assert not (legacy / "automation.json").exists()


def test_import_rejects_conflicting_hosted_values_without_touching_files(legacy, storage, tmp_path):
    storage.write("timer.email", '{"enabled": false, "interval_seconds": 1234}')
    with pytest.raises(TimerMigrationError, match="already"):
        migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)
    assert (legacy / "automation.json").exists()
    assert (legacy / "content_automation.json").exists()
    assert json.loads(storage.read("timer.email"))["interval_seconds"] == 1234


def test_malformed_json_rejected_before_mutating_hosted_or_removing_local(legacy, storage, tmp_path):
    (legacy / "content_automation.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(TimerMigrationError, match="invalid"):
        migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)
    assert storage.read("timer.email") is None
    assert (legacy / "automation.json").exists()
    assert (legacy / "content_automation.json").exists()


def test_partial_database_write_rolls_back_and_keeps_both_sources(legacy, storage, tmp_path, monkeypatch):
    original = storage.write
    def fail_second(name, body):
        if name == "timer.content":
            raise OSError("database unavailable")
        return original(name, body)
    monkeypatch.setattr(storage, "write", fail_second)
    with pytest.raises(OSError, match="database unavailable"):
        migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)
    assert storage.read("timer.email") is None
    assert storage.read("timer.content") is None
    assert (legacy / "automation.json").exists()
    assert (legacy / "content_automation.json").exists()
    assert (tmp_path / "archive" / "automation.json").exists()


def test_rejects_archives_inside_ephemeral_workspace(legacy, storage):
    with pytest.raises(TimerMigrationError, match="outside"):
        migrate_timers(storage, legacy, legacy / "backup", import_settings=True)
    assert (legacy / "automation.json").exists()


def test_rejects_symlink_sources_and_does_not_follow_them(legacy, storage, tmp_path):
    original = legacy / "automation.json"
    original.unlink()
    original.symlink_to(tmp_path / "unrelated-secret")
    with pytest.raises(TimerMigrationError, match="symbolic"):
        migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)


def test_existing_archive_never_overwritten_with_different_contents(legacy, storage, tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir(mode=0o700)
    (archive / "automation.json").write_text("other owner's data", encoding="utf-8")
    with pytest.raises(TimerMigrationError, match="archive"):
        migrate_timers(storage, legacy, archive, import_settings=True)
    assert (archive / "automation.json").read_text() == "other owner's data"
    assert (legacy / "automation.json").exists()


def test_operator_cli_requires_explicit_choice_and_archive_location(legacy, storage, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", storage.target)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", Fernet.generate_key().decode())
    assert db_cli.main([
        "import-timers", "--data-dir", str(legacy),
        "--archive-dir", str(tmp_path / "archive"),
    ]) == 2
    assert (legacy / "automation.json").exists()
    assert "--yes" in capsys.readouterr().err


def test_exclusive_migration_refuses_while_an_active_workspace_lock_is_held(
    legacy, storage, tmp_path
):
    from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock

    with WorkspaceLock(legacy):
        with pytest.raises(TimerMigrationError, match="busy"):
            migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)
    assert (legacy / "automation.json").exists()
    assert storage.read("timer.email") is None


def test_successful_cli_import_from_real_entrypoint_is_disabled(
    legacy, tmp_path, monkeypatch, capsys
):
    key = Fernet.generate_key().decode()
    target = str(tmp_path / "hosted.db")
    monkeypatch.setenv("OFFSETX_DATABASE_URL", target)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    assert db_cli.main([
        "import-timers", "--data-dir", str(legacy),
        "--archive-dir", str(tmp_path / "protected-archive"), "--yes",
    ]) == 0
    stdout = capsys.readouterr().out
    assert "disabled" in stdout
    reopened = HostedStorage(target, key)
    try:
        assert _email(legacy / "automation.json", reopened).config()["enabled"] is False
        assert _content(legacy / "content_automation.json", reopened).config()["enabled"] is False
    finally:
        reopened.close()


def test_retry_after_interruption_between_db_commit_and_cleanup(
    legacy, storage, tmp_path, monkeypatch
):
    original = Path.unlink
    interrupted = {"once": False}

    def crash_once(self, *args, **kwargs):
        if self.name == "automation.json" and not interrupted["once"]:
            interrupted["once"] = True
            raise OSError("simulated interruption after commit")
        return original(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", crash_once)
        with pytest.raises(OSError, match="simulated interruption"):
            migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)

    assert (legacy / "automation.json").exists()
    assert (tmp_path / "archive" / "automation.json").exists()
    assert storage.read("timer.email") is not None
    assert sorted(migrate_timers(storage, legacy, tmp_path / "archive", import_settings=True)) == [
        "automation.json", "content_automation.json"
    ]
    assert not (legacy / "automation.json").exists()


@pytest.mark.skipif(
    not os.getenv("OFF_CRM_TEST_POSTGRES_URL"),
    reason="requires disposable PostgreSQL provided by the isolated test runner",
)
def test_disposable_postgres_import_survives_new_connection(legacy, tmp_path):
    """Real PostgreSQL transaction, advisory locking and persisted documents."""
    import uuid
    import psycopg

    base_url = os.environ["OFF_CRM_TEST_POSTGRES_URL"]
    schema = f"timer_migration_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    suffix = "&" if "?" in base_url else "?"
    isolated = f"{base_url}{suffix}options=-csearch_path%3D{schema}"
    key = Fernet.generate_key().decode()
    try:
        storage = HostedStorage(isolated, key)
        try:
            migrated = migrate_timers(
                storage, legacy, tmp_path / "external-backup", import_settings=True
            )
            assert len(migrated) == 2
        finally:
            storage.close()
        reopened = HostedStorage(isolated, key)
        try:
            assert _email(legacy / "automation.json", reopened).config()["interval_seconds"] == 900
            assert _email(legacy / "automation.json", reopened).config()["enabled"] is False
            assert _content(legacy / "content_automation.json", reopened).config()["enabled"] is False
        finally:
            reopened.close()
    finally:
        with psycopg.connect(base_url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
