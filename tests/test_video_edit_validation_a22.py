"""A22: malformed nested video edits must fail before any durable timeline change."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )


@pytest.fixture()
def video_client(tmp_path):
    with TestClient(create_app(_settings(tmp_path)), raise_server_exceptions=False) as client:
        campaign = client.post(
            "/api/v1/campaigns", json={"name": "A22 video edits", "kind": "image"}
        )
        assert campaign.status_code == 201, campaign.text
        created = client.post(
            f"/api/v1/campaigns/{campaign.json()['id']}/video-projects",
            json={"name": "Before edit"},
        )
        assert created.status_code == 201, created.text
        yield client, created.json()["id"]


@pytest.mark.parametrize(
    "invalid",
    [
        {"operations": [{"op": "rename", "params": ["not", "a", "map"]}]},
        {"operations": [{"op": "rename", "params": {"name": "Must not run"}, "unknown": "EXTRA"}]},
        {
            "operations": [{"op": "rename", "params": {"name": "Batch wins silently"}}],
            "op": "rename", "params": {"name": "Ignored"},
        },
        {
            "operations": [
                {"op": "rename", "params": {"name": "Early edit"}},
                {"op": "rename", "params": ["invalid later step"]},
            ]
        },
        {"operations": [{"op": "rename", "params": {"name": "x" * 25000}}]},
        {"operations": [{"op": "rename", "params": {"name": "Safe"}, "operation": "rename"}]},
    ],
)
def test_A22_invalid_nested_video_edit_has_4xx_and_no_partial_commit(video_client, invalid):
    """A22: wrong nested types and conflicting fields never reach the edit engine."""
    client, project_id = video_client
    endpoint = f"/api/v1/video-projects/{project_id}"
    before = client.get(endpoint)
    assert before.status_code == 200
    response = client.post(f"{endpoint}/edit", json=invalid)
    assert 400 <= response.status_code < 500, response.text[:300]
    assert "traceback" not in response.text.lower()
    assert "must not run" not in response.text.lower()
    after = client.get(endpoint)
    assert after.status_code == 200
    assert after.json()["version"] == before.json()["version"]
    assert after.json()["document"] == before.json()["document"]


def test_A22_valid_single_and_batch_edits_remain_usable(video_client):
    """A22: a valid batch is one persisted undo step; single editing still works."""
    client, project_id = video_client
    endpoint = f"/api/v1/video-projects/{project_id}"
    single = client.post(f"{endpoint}/edit", json={"op": "rename", "params": {"name": "Single"}})
    assert single.status_code == 200, single.text
    assert single.json()["version"] == 1
    batch = client.post(f"{endpoint}/edit", json={
        "operations": [
            {"op": "rename", "params": {"name": "First"}},
            {"operation": "rename", "params": {"name": "Final"}},
        ]
    })
    assert batch.status_code == 200, batch.text
    assert batch.json()["version"] == 2
    assert batch.json()["document"]["name"] == "Final"
    reopened = client.get(endpoint)
    assert reopened.status_code == 200
    assert reopened.json()["document"]["name"] == "Final"
    undone = client.post(f"{endpoint}/undo")
    assert undone.status_code == 200
    assert undone.json()["document"]["name"] == "Single"


def test_A22_oversized_batch_is_refused_before_write(video_client):
    client, project_id = video_client
    endpoint = f"/api/v1/video-projects/{project_id}"
    response = client.post(f"{endpoint}/edit", json={
        "operations": [{"op": "rename", "params": {"name": "x"}}] * 501,
    })
    assert response.status_code == 422
    current = client.get(endpoint).json()
    assert current["version"] == 0
