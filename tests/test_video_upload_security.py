"""A15: byte-bounded media uploads through the real authenticated HTTP API.

These cases exercise the video endpoints, not the separate contact importer.
They also measure the number of bytes the endpoint asks UploadFile to read.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


TOKEN = "v" * 40
AUTH = {"Authorization": "Bearer " + TOKEN}


def _app(tmp_path: Path, max_bytes: int = 2048):
    return create_app(AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "no-frontend",
        api_token=TOKEN,
        allowed_hosts=("testserver",),
        max_upload_bytes=max_bytes,
    ))


def _targets(client: TestClient):
    campaign = client.post(
        "/api/v1/campaigns", headers=AUTH,
        json={"name": "Media limit regression", "kind": "image"},
    )
    assert campaign.status_code == 201, campaign.text
    cid = campaign.json()["id"]
    project = client.post(
        f"/api/v1/campaigns/{cid}/video-projects",
        headers=AUTH, json={"name": "Limit test", "preset": "vertical", "fps": "30"},
    )
    assert project.status_code == 201, project.text
    return (
        f"/api/v1/campaigns/{cid}/video-media",
        f"/api/v1/video-projects/{project.json()['id']}/renders",
    )


@pytest.mark.parametrize("target_index", [0, 1])
def test_a15_oversized_video_refused_before_codec_or_database_write(
    tmp_path, monkeypatch, target_index,
):
    """A15: a multi-part upload exceeding 2048 bytes cannot reach a video engine."""
    with TestClient(_app(tmp_path)) as client:
        target = _targets(client)[target_index]
        reads = []
        original_read = UploadFile.read

        async def measured_read(self, size=-1):
            reads.append(size)
            return await original_read(self, size)

        monkeypatch.setattr(UploadFile, "read", measured_read)
        for _ in range(2):
            res = client.post(
                target, headers=AUTH,
                files={"file": ("attack.wav", b"SENSITIVE_ATTACK_DATA" * 300, "audio/wav")},
            )
            assert res.status_code == 413, res.text
            assert "SENSITIVE_ATTACK_DATA" not in res.text
        # Neither endpoint may call read() with no size bound.
        assert reads == [2049, 2049]
        if target_index == 0:
            assert client.get(target, headers=AUTH).json()["items"] == []
        else:
            assert client.get(target, headers=AUTH).json()["items"] == []


@pytest.mark.parametrize("target_index", [0, 1])
def test_a15_empty_and_unauthenticated_upload_fail_closed(tmp_path, target_index):
    """No data is written for missing credentials or empty video payload."""
    with TestClient(_app(tmp_path)) as client:
        target = _targets(client)[target_index]
        unauthorized = client.post(
            target, files={"file": ("empty.webm", b"\x00" * 32, "video/webm")},
        )
        assert unauthorized.status_code == 401
        empty = client.post(
            target, headers=AUTH,
            files={"file": ("empty.webm", b"", "video/webm")},
        )
        assert empty.status_code == 400
        assert "empty" in empty.text.lower()


def test_a15_forged_small_content_length_does_not_override_real_byte_count(tmp_path):
    """A malicious multipart Content-Length claim is not a size authorization."""
    with TestClient(_app(tmp_path)) as client:
        target = _targets(client)[0]
        response = client.post(
            target,
            headers={**AUTH, "Content-Length": "8"},
            files={"file": ("large.webm", b"X" * 8192, "video/webm")},
        )
        assert response.status_code == 413, response.text


def test_a15_genuine_small_media_remains_accepted(tmp_path):
    """The size guard must not reject a valid WebM below its configured limit."""
    media = Path(__file__).parent / "fixtures" / "muxed_sample_audio.webm"
    blob = media.read_bytes()
    with TestClient(_app(tmp_path, max_bytes=max(1024, len(blob) + 32))) as client:
        target = _targets(client)[0]
        response = client.post(
            target, headers=AUTH,
            files={"file": ("voiceover.webm", blob, "video/webm")},
        )
        assert response.status_code == 201, response.text
        assert client.get(target, headers=AUTH).json()["items"]
