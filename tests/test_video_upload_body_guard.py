"""A15 pre-parser video upload security: real HTTP and ASGI adversarial tests."""
from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import SpooledTemporaryFile as OriginalSpool

import pytest
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.datastructures import UploadFile

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.api.video_upload_guard import VideoUploadBodyGuard

TOKEN = "g" * 40
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def anyio_backend():
    """The ASGI guard uses asyncio and does not require a Trio runner."""
    return "asyncio"


def _settings(tmp_path: Path, max_bytes: int = 2048) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "absent",
        api_token=TOKEN,
        allowed_hosts=("testserver",),
        max_upload_bytes=max_bytes,
    )


def _targets(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/campaigns", headers=AUTH,
        json={"name": "Safe uploads", "kind": "image"},
    )
    assert response.status_code == 201, response.text
    campaign = response.json()["id"]
    project = client.post(
        f"/api/v1/campaigns/{campaign}/video-projects",
        headers=AUTH, json={"name": "Security QA"},
    )
    assert project.status_code == 201, project.text
    return (
        f"/api/v1/campaigns/{campaign}/video-media",
        f"/api/v1/video-projects/{project.json()['id']}/renders",
    )


@pytest.mark.parametrize("target_index", [0, 1])
def test_a15_preparser_rejects_giant_file_before_uploadfile_is_read(
    tmp_path, monkeypatch, target_index,
):
    """The multipart parser never reaches UploadFile.read for huge bodies."""
    with TestClient(create_app(_settings(tmp_path))) as client:
        path = _targets(client)[target_index]

        async def forbidden_read(self, size=-1):
            raise AssertionError("Starlette must not parse a rejected body")

        monkeypatch.setattr(UploadFile, "read", forbidden_read)
        for _ in range(2):
            response = client.post(
                path, headers=AUTH,
                files={"file": ("attack.webm", b"DO_NOT_LOG_SECRET" * 6000, "video/webm")},
            )
            assert response.status_code == 413, response.text
            assert "DO_NOT_LOG_SECRET" not in response.text
        assert client.get(path, headers=AUTH).json()["items"] == []


@pytest.mark.parametrize("target_index", [0, 1])
def test_a15_preparser_allows_normal_authenticated_uploads(tmp_path, target_index):
    """A valid small WebM still reaches the video engine or render gates."""
    media = Path(__file__).parent / "fixtures" / "muxed_sample_audio.webm"
    payload = media.read_bytes()
    with TestClient(create_app(_settings(tmp_path, max_bytes=len(payload) + 1024))) as client:
        path = _targets(client)[target_index]
        response = client.post(
            path, headers=AUTH, files={"file": ("clip.webm", payload, "video/webm")},
        )
        # The render may fail timeline codec gates but must not be size-rejected.
        assert response.status_code != 413, response.text
        if target_index == 0:
            assert response.status_code == 201, response.text


def test_a15_preparser_ignores_forged_small_content_length(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        path = _targets(client)[0]
        response = client.post(
            path, headers={**AUTH, "Content-Length": "8"},
            files={"file": ("large.webm", b"X" * 100000, "video/webm")},
        )
        assert response.status_code == 413, response.text


def test_a15_preparser_rejects_malformed_content_length(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        path = _targets(client)[0]
        response = client.post(
            path, headers={**AUTH, "Content-Length": "n/a"},
            files={"file": ("small.webm", b"X" * 100, "video/webm")},
        )
        assert response.status_code == 400, response.text


@pytest.mark.anyio
async def test_a15_chunked_body_stops_reading_at_the_ceiling():
    async def app(scope, receive, send):
        raise AssertionError("Request must never reach the application")

    guard = VideoUploadBodyGuard(app, max_file_bytes=2048, max_concurrent=1)
    scope = {"type": "http", "method": "POST",
             "path": "/api/v1/campaigns/a/video-media", "headers": []}
    count = 0

    async def receive():
        nonlocal count
        count += 1
        return {"type": "http.request", "body": b"Q" * 10000, "more_body": True}

    sent = []

    async def send(message):
        sent.append(message)

    await guard(scope, receive, send)
    assert count == 2  # Denied before reading the next unbounded chunk.
    assert next(x["status"] for x in sent if x["type"] == "http.response.start") == 413


@pytest.mark.anyio
async def test_a15_concurrent_upload_limit_releases_after_completion():
    entered, allow_finish = asyncio.Event(), asyncio.Event()

    async def app(scope, receive, send):
        await receive()
        entered.set()
        await allow_finish.wait()
        await JSONResponse({"ok": True})(scope, receive, send)

    guard = VideoUploadBodyGuard(app, max_file_bytes=2048, max_concurrent=1)
    scope = {"type": "http", "method": "POST",
             "path": "/api/v1/video-projects/p/renders", "headers": []}

    async def receive():
        return {"type": "http.request", "body": b"ok", "more_body": False}

    results = [[], [], []]

    async def send_one(message):
        results[0].append(message)

    async def send_two(message):
        results[1].append(message)

    async def send_three(message):
        results[2].append(message)

    first = asyncio.create_task(guard(scope, receive, send_one))
    await entered.wait()
    await guard(scope, receive, send_two)
    assert next(x["status"] for x in results[1] if x["type"] == "http.response.start") == 429
    allow_finish.set()
    await first
    await guard(scope, receive, send_three)
    assert next(x["status"] for x in results[2] if x["type"] == "http.response.start") == 200


@pytest.mark.anyio
async def test_a15_stalled_upload_returns_timeout_and_releases_capacity():
    called = 0

    async def app(scope, receive, send):
        nonlocal called
        called += 1

    guard = VideoUploadBodyGuard(
        app, max_file_bytes=2048, max_concurrent=1, idle_timeout_seconds=0.01,
    )
    scope = {"type": "http", "method": "POST",
             "path": "/api/v1/campaigns/a/video-media", "headers": []}

    async def never():
        await asyncio.Event().wait()

    messages = []

    async def send(message):
        messages.append(message)

    await guard(scope, never, send)
    assert next(x["status"] for x in messages if x["type"] == "http.response.start") == 408

    async def valid():
        return {"type": "http.request", "body": b"valid", "more_body": False}

    await guard(scope, valid, send)
    assert called == 1


@pytest.mark.anyio
async def test_a15_spooled_file_rolls_to_disk_and_closes_on_success(monkeypatch):
    import offsetx_apollo_builder.api.video_upload_guard as module

    opened = []

    def tracked(*args, **kwargs):
        obj = OriginalSpool(*args, **kwargs)
        opened.append(obj)
        return obj

    monkeypatch.setattr(module, "SpooledTemporaryFile", tracked)

    async def app(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        await JSONResponse({"ok": True})(scope, receive, send)

    guard = VideoUploadBodyGuard(app, max_file_bytes=1024 * 1024)
    scope = {"type": "http", "method": "POST",
             "path": "/api/v1/campaigns/a/video-media", "headers": []}

    async def receive():
        return {"type": "http.request", "body": b"Z" * (400 * 1024), "more_body": False}

    async def send(message):
        pass

    await guard(scope, receive, send)
    assert len(opened) == 1
    assert opened[0]._rolled and opened[0].closed


@pytest.mark.anyio
async def test_a15_disconnected_upload_cleans_temporary_file(monkeypatch):
    import offsetx_apollo_builder.api.video_upload_guard as module

    opened = []

    def tracked(*args, **kwargs):
        obj = OriginalSpool(*args, **kwargs)
        opened.append(obj)
        return obj

    monkeypatch.setattr(module, "SpooledTemporaryFile", tracked)

    async def app(scope, receive, send):
        raise AssertionError("Disconnected request must not reach the application")

    guard = VideoUploadBodyGuard(app, max_file_bytes=2048)
    scope = {"type": "http", "method": "POST",
             "path": "/api/v1/campaigns/a/video-media", "headers": []}
    iterator = iter([
        {"type": "http.request", "body": b"partial", "more_body": True},
        {"type": "http.disconnect"},
    ])

    async def receive():
        return next(iterator)

    async def send(message):
        pass

    await guard(scope, receive, send)
    assert opened and opened[0].closed
