"""A05: a shared CRM campaign does not grant access to another workspace's images.

Real HTTP API and two independently authenticated session cookies; all assets
and provider double are synthetic. The deliberately RED tests cannot make
external model/provider calls.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = "image-a05-admin-" + "x" * 40
ADMIN = {"X-Offsetx-Token": TOKEN}
ALPHA_BYTES = b"ALPHA_PRIVATE_IMAGE_BYTES_NO_NETWORK"
BETA_BYTES = b"BETA_PRIVATE_IMAGE_BYTES_NO_NETWORK"


@pytest.fixture
def two_image_workspaces(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token=TOKEN,
        session_secret="a05-image-cookie-secret-" + "s" * 36,
        allowed_hosts=("testserver",),
    )

    with TestClient(create_app(settings), raise_server_exceptions=False) as install:
        provider_calls = []

        class NoNetworkBroker:
            def with_credential_resolver(self, resolver):
                return self

            def call_image(self, *args, **kwargs):
                provider_calls.append(("call_image", args, kwargs))
                raise AssertionError("No provider call is allowed in workspace security tests")

        install.app.state.ai_broker = NoNetworkBroker()

        for username, workspace in (("alpha-user", "alpha"), ("beta-user", "beta")):
            created = install.post(
                "/api/v1/workspaces", headers=ADMIN,
                json={
                    "username": username, "workspace_id": workspace,
                    "password": username + "-safe-password-123",
                },
            )
            assert created.status_code == 201, created.text

        campaign = install.post(
            "/api/v1/campaigns", headers=ADMIN,
            json={"name": "One CRM campaign with separate image owners", "kind": "image"},
        )
        assert campaign.status_code == 201, campaign.text
        campaign_id = campaign.json()["id"]

        sessions = {}
        briefs = {}
        for username, workspace in (("alpha-user", "alpha"), ("beta-user", "beta")):
            client = TestClient(install.app, raise_server_exceptions=False)
            login = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": username + "-safe-password-123"},
            )
            assert login.status_code == 200, login.text
            assert login.json()["workspace_id"] == workspace
            brief = client.post(
                f"/api/v1/campaigns/{campaign_id}/image-briefs",
                json={"brief": f"Private {workspace} image product notes", "width": 16, "height": 9, "wanted": 1},
            )
            assert brief.status_code == 201, brief.text
            briefs[workspace] = brief.json()["id"]
            sessions[workspace] = client

        store = install.app.state.image_store
        assets = {}
        for workspace in ("alpha", "beta"):
            assets[workspace] = {}
            for status in ("pending", "approved"):
                assets[workspace][status] = store.store_asset(
                    brief_id=briefs[workspace],
                    campaign_id=campaign_id,
                    payload=ALPHA_BYTES if workspace == "alpha" else BETA_BYTES,
                    provider_id="synthetic",
                    model_id="synthetic-model",
                    gate_report=SimpleNamespace(
                        media_type="image/png", width=1280, height=720, to_dict=lambda: {},
                    ),
                    status=status,
                    workspace_id=workspace,
                )

        project = sessions["beta"].post(
            f"/api/v1/campaigns/{campaign_id}/video-projects",
            json={"name": "Private beta video", "preset": "vertical"},
        )
        assert project.status_code == 201, project.text

        yield (
            sessions["alpha"], sessions["beta"], install.app.state.image_store,
            campaign_id, briefs, assets, project.json()["id"], provider_calls,
        )
        for client in sessions.values():
            client.close()


def test_A05_image_download_rejects_foreign_workspace_without_file_bytes(two_image_workspaces):
    alpha, beta, _, _, _, assets, _, _ = two_image_workspaces
    for status in ("pending", "approved"):
        alpha_id = assets["alpha"][status]
        uri = f"/api/v1/image-assets/{alpha_id}/file"
        owned = alpha.get(uri)
        assert owned.status_code == 200, (status, owned.status_code, owned.text)
        assert owned.content == ALPHA_BYTES
        foreign = beta.get(uri)
        assert foreign.status_code == 404, (status, foreign.status_code, foreign.text)
        assert ALPHA_BYTES not in foreign.content
        assert b"alpha" not in foreign.content.lower()


def test_A05_image_campaign_briefs_assets_review_and_summary_are_workspace_scoped(two_image_workspaces):
    alpha, beta, _, campaign, briefs, assets, _, _ = two_image_workspaces
    for workspace, client in (("alpha", alpha), ("beta", beta)):
        b = client.get(f"/api/v1/campaigns/{campaign}/image-briefs")
        assert b.status_code == 200, b.text
        assert {item["id"] for item in b.json()["items"]} == {briefs[workspace]}
        for status in ("pending", "approved"):
            listed = client.get(
                f"/api/v1/campaigns/{campaign}/image-assets", params={"status": status}
            )
            assert listed.status_code == 200, listed.text
            assert {item["id"] for item in listed.json()["items"]} == {
                assets[workspace][status]
            }
        review = client.get(f"/api/v1/campaigns/{campaign}/image-queue")
        assert review.status_code == 200, review.text
        assert {item["id"] for item in review.json()["items"]} == {
            assets[workspace]["pending"]
        }
        summary = client.get(f"/api/v1/campaigns/{campaign}/image-summary")
        assert summary.status_code == 200, summary.text
        assert summary.json()["briefs"] == 1
        assert summary.json()["assets"]["pending"] == 1
        assert summary.json()["assets"]["approved"] == 1


def test_A05_foreign_image_brief_cannot_invoke_provider_even_when_id_known(two_image_workspaces):
    alpha, beta, store, _, briefs, assets, _, calls = two_image_workspaces
    before_brief = store.get_brief(briefs["alpha"])
    blocked = beta.post(
        f"/api/v1/image-briefs/{briefs['alpha']}/generate",
        json={"count": 1},
    )
    assert blocked.status_code == 404, blocked.text
    assert calls == []
    assert store.get_brief(briefs["alpha"]) == before_brief
    assert store.get_asset(assets["alpha"]["pending"])["status"] == "pending"


@pytest.mark.parametrize("decision", ["approve", "reject", "regenerate"])
def test_A05_foreign_image_decisions_cannot_change_status_or_remove_bytes(
    two_image_workspaces, decision,
):
    alpha, beta, store, _, _, assets, _, calls = two_image_workspaces
    owned_asset_id = assets["alpha"]["pending"]
    original = store.get_asset(owned_asset_id)
    file_path = Path(original["path"])
    assert file_path.read_bytes() == ALPHA_BYTES

    blocked = beta.post(
        f"/api/v1/image-assets/{owned_asset_id}/decide",
        json={"decision": decision},
    )
    assert blocked.status_code == 404, (decision, blocked.status_code, blocked.text)
    assert store.get_asset(owned_asset_id)["status"] == "pending"
    assert file_path.read_bytes() == ALPHA_BYTES
    assert calls == []

    if decision == "approve":
        approved = alpha.post(
            f"/api/v1/image-assets/{owned_asset_id}/decide",
            json={"decision": "approve"},
        )
        assert approved.status_code == 200, approved.text
        assert store.get_asset(owned_asset_id)["status"] == "approved"


def test_A05_video_cannot_place_foreign_image_but_can_place_own_approved_image(
    two_image_workspaces,
):
    _, beta, store, _, _, assets, beta_project, _ = two_image_workspaces
    foreign = beta.post(
        f"/api/v1/video-projects/{beta_project}/place-asset",
        json={"asset_id": assets["alpha"]["approved"]},
    )
    assert foreign.status_code == 404, foreign.text

    own = beta.post(
        f"/api/v1/video-projects/{beta_project}/place-asset",
        json={"asset_id": assets["beta"]["approved"]},
    )
    assert own.status_code == 200, own.text
    assert assets["alpha"]["approved"] != assets["beta"]["approved"]
