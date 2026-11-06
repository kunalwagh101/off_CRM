"""Content metadata survives a hosted app restart; media bytes remain separate."""

import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.distribution.trends import TrendWatcher


def settings_for(data, key):
    return AppSettings(
        project_root=Path.cwd(),
        database_path=data / "crm.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=data.parent / "missing",
        api_token="hosted-content-owner-" + "x" * 40,
        secrets_key=key,
        allowed_hosts=("testserver",),
    )


def configure(tmp_path, monkeypatch):
    target = tmp_path / "durable" / "hosted.db"
    target.parent.mkdir()
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(target))
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    return settings_for(tmp_path / "ephemeral", key)


def test_image_posting_and_trend_metadata_survive_removal_of_ephemeral_disk(
    tmp_path, monkeypatch
):
    settings = configure(tmp_path, monkeypatch)
    first = create_app(settings)
    with TestClient(first):
        routine = first.state.agent_routine_store.create(workspace_id="alpha", name="Evidence",
            goal="Read public evidence", target_url="https://example.com", trigger_type="event", event_name="evidence.ready")
        meeting = first.state.meeting_store.create(workspace_id="alpha", title="Supplier evidence")
        brief = first.state.image_store.create_brief(
            campaign_id="campaign",
            brief="A private illustration",
            workspace_id="alpha",
        )
        account = first.state.distribution_store.add_account(
            platform="linkedin",
            handle="alpha-team",
            workspace_id="alpha",
        )
        watcher = TrendWatcher(
            database_path=first.state.trends_path, workspace_id="alpha"
        )
        try:
            watcher.connection.execute(
                "INSERT INTO yt_channels(id,workspace_id,channel_id,title,created_at) VALUES(?,?,?,?,?)",
                (
                    "channel-a",
                    "alpha",
                    "source-a",
                    "Approved public source",
                    "2026-11-06",
                ),
            )
        finally:
            watcher.close()
    shutil.rmtree(settings.data_dir)
    second = create_app(settings)
    with TestClient(second):
        assert second.state.agent_routine_store.require(routine.id, workspace_id="alpha").name == "Evidence"
        assert second.state.meeting_store.require(meeting["id"], workspace_id="alpha")["title"] == "Supplier evidence"
        assert (
            second.state.image_store.get_brief(brief)["brief"]
            == "A private illustration"
        )
        assert (
            second.state.image_store.list_briefs("campaign", workspace_id="beta") == []
        )
        assert (
            second.state.distribution_store.get_account(account)["workspace_id"]
            == "alpha"
        )
        assert second.state.distribution_store.list_accounts(workspace_id="beta") == []
        watcher = TrendWatcher(
            database_path=second.state.trends_path, workspace_id="alpha"
        )
        try:
            assert watcher.watched()[0]["channel_id"] == "source-a"
        finally:
            watcher.close()
        for filename in ("imagery.db", "distribution.db", "trends.db", "agent_routines.db", "meeting_transcripts.db"):
            assert not (settings.data_dir / filename).exists()


@pytest.mark.parametrize("filename", ["imagery.db", "distribution.db", "trends.db", "agent_routines.db", "meeting_transcripts.db"])
def test_hosted_boot_refuses_to_hide_existing_local_content_files(
    tmp_path, monkeypatch, filename
):
    settings = configure(tmp_path, monkeypatch)
    settings.data_dir.mkdir()
    source = settings.data_dir / filename
    original = b"existing local content must not disappear"
    source.write_bytes(original)
    with pytest.raises(ValueError, match="content.*migration"):
        create_app(settings)
    assert source.read_bytes() == original
