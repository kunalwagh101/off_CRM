"""Acceptance evidence for Audit WP1: durable customer state and safe recovery."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach import OutreachStore
from offsetx_apollo_builder.outreach.backup import (
    create_encrypted_backup,
    restore_encrypted_backup,
    validate_encrypted_backup,
)


PASSPHRASE = "synthetic-backup-passphrase"


def _settings(tmp_path: Path) -> AppSettings:
    data = tmp_path / "data"
    return AppSettings(
        project_root=tmp_path,
        database_path=data / "outreach.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=tmp_path / "frontend-dist",
        host="127.0.0.1",
        backup_max_bytes=64 * 1024 * 1024,
    )


def _sqlite(path: Path, value: str) -> None:
    import sqlite3

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS probe(value TEXT NOT NULL)")
        connection.execute("DELETE FROM probe")
        connection.execute("INSERT INTO probe(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_production_configuration_refuses_ephemeral_customer_state(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_PRODUCTION", "1")
    monkeypatch.setenv("OFFSETX_DATA_DIR", "/tmp/offcrm-customer-state")
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", "/tmp/offcrm-customer-state/outreach.db")
    with pytest.raises(ValueError, match="temporary"):
        AppSettings.from_env(tmp_path)

    blueprint = (Path(__file__).resolve().parents[1] / "render.yaml").read_text()
    assert "plan: free" not in blueprint
    assert "/tmp/offsetx" not in blueprint
    assert "mountPath: /var/lib/offcrm" in blueprint
    assert "numInstances: 1" in blueprint
    assert "OFFSETX_PRODUCTION" in blueprint


def test_failed_concurrent_transaction_cannot_rollback_another_writer(tmp_path):
    store = OutreachStore(tmp_path / "crm.db")
    store.initialize()
    store.connection.execute("CREATE TABLE wp1_tx(id TEXT PRIMARY KEY)")
    store.connection.commit()

    first_started = threading.Event()
    second_attempted = threading.Event()
    errors: list[BaseException] = []

    def first_writer() -> None:
        try:
            with store.transaction() as connection:
                connection.execute("INSERT INTO wp1_tx(id) VALUES ('first')")
                first_started.set()
                assert second_attempted.wait(2)
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    def second_writer() -> None:
        try:
            assert first_started.wait(2)
            second_attempted.set()
            with pytest.raises(RuntimeError):
                with store.transaction() as connection:
                    connection.execute("INSERT INTO wp1_tx(id) VALUES ('second')")
                    raise RuntimeError("synthetic failure")
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    a = threading.Thread(target=first_writer)
    b = threading.Thread(target=second_writer)
    a.start()
    b.start()
    a.join(5)
    b.join(5)
    assert not a.is_alive() and not b.is_alive()
    assert not errors
    rows = store.connection.execute("SELECT id FROM wp1_tx ORDER BY id").fetchall()
    assert [row[0] for row in rows] == ["first"]
    store.close()


def test_nested_transactions_use_savepoints_without_releasing_outer_ownership(tmp_path):
    store = OutreachStore(tmp_path / "crm.db")
    store.initialize()
    store.connection.execute("CREATE TABLE wp1_nested(id TEXT PRIMARY KEY)")
    store.connection.commit()
    with store.transaction() as outer:
        outer.execute("INSERT INTO wp1_nested(id) VALUES ('outer')")
        with pytest.raises(RuntimeError):
            with store.transaction() as inner:
                inner.execute("INSERT INTO wp1_nested(id) VALUES ('inner')")
                raise RuntimeError("rollback inner only")
        outer.execute("INSERT INTO wp1_nested(id) VALUES ('outer-2')")
    rows = store.connection.execute("SELECT id FROM wp1_nested ORDER BY id").fetchall()
    assert [row[0] for row in rows] == ["outer", "outer-2"]
    store.close()


def test_backup_contains_durable_stores_assets_and_unsubscribe_secret(tmp_path):
    source = tmp_path / "source"
    data = source / "data"
    database = data / "outreach.db"
    _sqlite(database, "crm")
    _sqlite(data / "ai_context.db", "context")
    _sqlite(data / "ai_recall.db", "recall")
    _sqlite(data / "imagery.db", "imagery")
    _sqlite(data / "distribution.db", "distribution")
    _sqlite(data / "video.db", "video")
    _sqlite(data / "ai_cache.db", "rebuildable")
    (data / "image_assets").mkdir(parents=True)
    (data / "image_assets" / "candidate.png").write_bytes(b"synthetic-image")
    (data / "video_renders").mkdir()
    (data / "video_renders" / "render.webm").write_bytes(b"synthetic-video")
    (data / "email_unsubscribe.key").write_bytes(os.urandom(32))
    (data / "automation.json").write_text('{"enabled": false}')

    expected = {
        relative: _sha(data / relative)
        for relative in (
            "ai_context.db",
            "ai_recall.db",
            "imagery.db",
            "distribution.db",
            "video.db",
            "image_assets/candidate.png",
            "video_renders/render.webm",
            "email_unsubscribe.key",
            "automation.json",
        )
    }
    content = create_encrypted_backup(
        database_path=database,
        data_dir=data,
        passphrase=PASSPHRASE,
        max_bytes=64 * 1024 * 1024,
    )
    manifest = validate_encrypted_backup(
        content, passphrase=PASSPHRASE, max_bytes=64 * 1024 * 1024
    )
    assert manifest["schema_version"] == 2
    assert "ai_cache.db" in manifest["excluded_rebuildable"]

    target = tmp_path / "target"
    result = restore_encrypted_backup(
        content,
        database_path=target / "data" / "outreach.db",
        data_dir=target / "data",
        passphrase=PASSPHRASE,
        max_bytes=64 * 1024 * 1024,
    )
    assert result["schema_version"] == 2
    for relative, digest in expected.items():
        if relative.endswith(".db"):
            # SQLite backup may change header counters; compare durable records.
            import sqlite3
            with sqlite3.connect(data / relative) as original, sqlite3.connect(target / "data" / relative) as restored:
                assert list(original.iterdump()) == list(restored.iterdump()), relative
        else:
            assert _sha(target / "data" / relative) == digest, relative
    assert not (target / "data" / "ai_cache.db").exists()


def test_backup_larger_than_general_upload_limit_remains_restorable(tmp_path):
    data = tmp_path / "data"
    database = data / "outreach.db"
    _sqlite(database, "crm")
    # Deliberately incompressible and above the application's 10 MiB general
    # upload limit. Backup/restore has its own bounded recovery limit.
    payload = os.urandom(11 * 1024 * 1024)
    (data / "large-evidence.bin").write_bytes(payload)
    content = create_encrypted_backup(
        database_path=database,
        data_dir=data,
        passphrase=PASSPHRASE,
        max_bytes=32 * 1024 * 1024,
    )
    assert len(content) > 10 * 1024 * 1024
    target = tmp_path / "restored"
    restore_encrypted_backup(
        content,
        database_path=target / "outreach.db",
        data_dir=target,
        passphrase=PASSPHRASE,
        max_bytes=32 * 1024 * 1024,
    )
    assert (target / "large-evidence.bin").read_bytes() == payload


def test_rejected_backup_does_not_break_existing_workspace(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        original_engine = app.state.engine
        campaign = original_engine.store.create_campaign(name="Before rejection", daily_send_limit=10)
        response = client.post(
            "/api/v1/backups/restore",
            files={"file": ("bad.oxbackup", b"not-a-backup", "application/octet-stream")},
            data={"passphrase": PASSPHRASE},
        )
        assert response.status_code == 422
        assert app.state.engine is original_engine
        assert app.state.engine.store.get_campaign(campaign)["name"] == "Before rejection"
        assert client.get("/health/ready").status_code == 200


def test_restore_rebinds_every_service_that_holds_the_outreach_store(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        original_id = app.state.engine.store.create_campaign(
            name="Included in backup", daily_send_limit=10
        )
        exported = client.post(
            "/api/v1/backups/export", json={"passphrase": PASSPHRASE}
        )
        assert exported.status_code == 200, exported.text
        app.state.engine.store.create_campaign(name="Created after backup", daily_send_limit=10)

        response = client.post(
            "/api/v1/backups/restore",
            files={
                "file": (
                    "workspace.oxbackup",
                    exported.content,
                    "application/octet-stream",
                )
            },
            data={"passphrase": PASSPHRASE},
        )
        assert response.status_code == 200, response.text
        assert response.json()["health"] == "ready"
        campaigns, total = app.state.engine.store.list_campaigns(limit=20)
        assert total == 1
        assert campaigns[0]["id"] == original_id
        assert app.state.sales.store is app.state.engine.store
        assert app.state.ai_chat.store is app.state.engine.store
        assert app.state.email_delivery.engine is app.state.engine
        assert app.state.email_delivery.store.outreach is app.state.engine.store
        assert client.get("/health/ready").status_code == 200


def test_readiness_fails_when_required_database_is_unavailable(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        app.state.engine.close()
        response = client.get("/health/ready")
        assert response.status_code == 503
        payload = response.json()
        assert "outreach_db" in json.dumps(payload)
