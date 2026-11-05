"""A05: real API sessions may not read, change or reuse another workspace's videos."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


TOKEN = "video-a05-admin-" + "x" * 40
HEADERS = {"X-Offsetx-Token": TOKEN}
SECRET_VIDEO = b"PRIVATE-ALPHA-VIDEO-DO-NOT-SEND"
SECRET_MEDIA = b"PRIVATE-ALPHA-AUDIO-DO-NOT-SEND"


@pytest.fixture
def two_video_workspaces(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token=TOKEN,
        session_secret="a05-video-owner-session-" + "s" * 36,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as install:
        for username, workspace in (("alpha-user", "alpha"), ("beta-user", "beta")):
            response = install.post(
                "/api/v1/workspaces", headers=HEADERS,
                json={
                    "username": username,
                    "workspace_id": workspace,
                    "password": username + "-safe-password-123",
                },
            )
            assert response.status_code == 201, response.text

        campaign = install.post(
            "/api/v1/campaigns", headers=HEADERS,
            json={"name": "Shared CRM campaign; private video content", "kind": "image"},
        )
        assert campaign.status_code == 201, campaign.text
        campaign_id = campaign.json()["id"]

        sessions = {}
        for username, workspace in (("alpha-user", "alpha"), ("beta-user", "beta")):
            session = TestClient(install.app, raise_server_exceptions=False)
            logged = session.post(
                "/api/v1/auth/login",
                json={"username": username, "password": username + "-safe-password-123"},
            )
            assert logged.status_code == 200, logged.text
            assert logged.json()["workspace_id"] == workspace
            sessions[workspace] = session

        alpha, beta = sessions["alpha"], sessions["beta"]
        projects = {}
        for workspace, client in (("alpha", alpha), ("beta", beta)):
            created = client.post(
                f"/api/v1/campaigns/{campaign_id}/video-projects",
                json={"name": workspace + " private timeline", "preset": "vertical"},
            )
            assert created.status_code == 201, created.text
            projects[workspace] = created.json()["id"]

        store = install.app.state.video_store
        media_id = store.store_media(
            campaign_id=campaign_id,
            name="alpha recorded voice",
            payload=SECRET_MEDIA,
            workspace_id="alpha",
            probe=SimpleNamespace(
                kind="audio", media_type="audio/webm", has_audio=True,
                duration_ticks=10_000, width=0, height=0, to_dict=lambda: {},
            ),
        )
        render_id = store.store_render(
            project_id=projects["alpha"], campaign_id=campaign_id,
            payload=SECRET_VIDEO, gate_report=None,
            status="ready", workspace_id="alpha",
        )
        yield alpha, beta, store, campaign_id, projects, media_id, render_id
        for client in sessions.values():
            client.close()


def test_A05_foreign_video_files_return_404_without_disclosing_bytes(two_video_workspaces):
    alpha, beta, _, _, _, media_id, render_id = two_video_workspaces
    for url, expected in (
        (f"/api/v1/video-media/{media_id}/file", SECRET_MEDIA),
        (f"/api/v1/video-renders/{render_id}/file", SECRET_VIDEO),
    ):
        owned = alpha.get(url)
        assert owned.status_code == 200, (url, owned.text)
        assert owned.content == expected
        foreign = beta.get(url)
        assert foreign.status_code == 404, (url, foreign.text)
        assert expected not in foreign.content
        assert b"alpha" not in foreign.content.lower()


def test_A05_foreign_video_project_cannot_be_read_edited_deleted_or_reviewed(two_video_workspaces):
    alpha, beta, store, _, projects, _, render_id = two_video_workspaces
    project_id = projects["alpha"]
    before = store.get_project(project_id)
    paths = [
        ("get", f"/api/v1/video-projects/{project_id}", None),
        ("get", f"/api/v1/video-projects/{project_id}/history", None),
        ("get", f"/api/v1/video-projects/{project_id}/renders", None),
        ("get", f"/api/v1/video-projects/{project_id}/manifest", None),
        ("get", f"/api/v1/video-projects/{project_id}/frame", None),
        ("get", f"/api/v1/video-projects/{project_id}/reviews", None),
        ("post", f"/api/v1/video-projects/{project_id}/undo", {}),
        ("post", f"/api/v1/video-projects/{project_id}/redo", {}),
        ("post", f"/api/v1/video-projects/{project_id}/queue", {"origin": "manual"}),
        ("delete", f"/api/v1/video-projects/{project_id}", None),
    ]
    for method, path, payload in paths:
        response = getattr(beta, method)(path, **({"json": payload} if payload is not None else {}))
        assert response.status_code == 404, (method, path, response.status_code, response.text)
    after = store.get_project(project_id)
    assert after["version"] == before["version"]
    assert after["document"] == before["document"]
    assert store.get_render(render_id)["project_id"] == project_id
    assert alpha.get(f"/api/v1/video-projects/{project_id}").status_code == 200


def test_A05_campaign_video_lists_and_counts_are_workspace_scoped(two_video_workspaces):
    alpha, beta, _, campaign_id, projects, media_id, _ = two_video_workspaces
    project_url = f"/api/v1/campaigns/{campaign_id}/video-projects"
    media_url = f"/api/v1/campaigns/{campaign_id}/video-media"
    for owner, session in (("alpha", alpha), ("beta", beta)):
        response = session.get(project_url)
        assert response.status_code == 200, response.text
        assert {item["id"] for item in response.json()["items"]} == {projects[owner]}
        summary = session.get(f"/api/v1/campaigns/{campaign_id}/video-summary")
        assert summary.status_code == 200, summary.text
        assert summary.json()["projects"] == 1

    assert {item["id"] for item in alpha.get(media_url).json()["items"]} == {media_id}
    assert beta.get(media_url).json()["items"] == []
    queued = alpha.post(f"/api/v1/video-projects/{projects['alpha']}/queue",
                        json={"origin": "manual"})
    assert queued.status_code == 201, queued.text
    waiting = beta.get(f"/api/v1/campaigns/{campaign_id}/video-queue")
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["items"] == []


def test_A05_foreign_audio_cannot_be_transcribed_or_placed_in_own_project(two_video_workspaces):
    alpha, beta, store, _, projects, media_id, _ = two_video_workspaces
    beta_project = projects["beta"]
    original = store.get_project(beta_project)
    transcribe = beta.post(f"/api/v1/video-media/{media_id}/transcribe", json={})
    assert transcribe.status_code == 404, transcribe.text
    place = beta.post(
        f"/api/v1/video-projects/{beta_project}/place-media",
        json={"media_id": media_id},
    )
    assert place.status_code == 404, place.text
    assert store.get_project(beta_project)["document"] == original["document"]
