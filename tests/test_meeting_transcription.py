from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from offsetx_apollo_builder.ai.broker import TranscriptResult, TranscriptWord
from offsetx_apollo_builder.ai.tiers import DataClass, TrustTier, tier_permits_class
from offsetx_apollo_builder.api.app import MAX_MEETING_AUDIO_BYTES, create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.meeting import MeetingError, MeetingStore


API = "/api/v1"


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )


def _result(audio_bytes: int) -> TranscriptResult:
    return TranscriptResult(
        text="Hello team. Revenue is up.",
        words=[
            TranscriptWord(word="Hello", start=0.0, end=0.3),
            TranscriptWord(word="team.", start=0.3, end=0.7),
            TranscriptWord(word="Revenue", start=0.8, end=1.2),
            TranscriptWord(word="is", start=1.2, end=1.3),
            TranscriptWord(word="up.", start=1.3, end=1.6),
        ],
        language="en",
        provider_id="private-stt",
        provider_name="Private STT",
        model_id="whisper-private",
        tier="A",
        policy="standard",
        duration_ms=41,
        audio_bytes=audio_bytes,
        log_id="egress-1",
    )


async def _request(
    tmp_path: Path,
    *,
    peer: str = "127.0.0.1",
    base_url: str = "http://127.0.0.1",
    headers: dict[str, str] | None = None,
    patch_broker=None,
):
    app = create_app(_settings(tmp_path))
    async with app.router.lifespan_context(app):
        if patch_broker is not None:
            app.state.ai_broker.call_transcript = patch_broker
        transport = httpx.ASGITransport(app=app, client=(peer, 43123))
        async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
            return await client.post(
                f"{API}/meetings/transcribe",
                headers=headers,
                files={"file": ("meeting.webm", b"webm-audio", "audio/webm;codecs=opus")},
                data={"title": "Monday product call", "language": "en"},
            )


def test_meeting_data_class_is_tier_a_only():
    assert tier_permits_class(TrustTier.A, DataClass.MEETING)
    assert not tier_permits_class(TrustTier.B, DataClass.MEETING)
    assert not tier_permits_class(TrustTier.C, DataClass.MEETING)
    assert not tier_permits_class(TrustTier.D, DataClass.MEETING)


def test_loopback_upload_uses_meeting_class_and_never_stores_raw_audio(tmp_path):
    seen: dict[str, object] = {}

    def transcribe(request, settings, **kwargs):
        seen["data_class"] = request.data_class
        seen["task_type"] = request.task_type
        seen["audio"] = kwargs["audio"]
        seen["media_type"] = kwargs["media_type"]
        return _result(len(kwargs["audio"]))

    response = asyncio.run(_request(tmp_path, patch_broker=transcribe))
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "Monday product call"
    assert payload["transcript"] == "Hello team. Revenue is up."
    assert payload["provider_id"] == "private-stt"
    assert payload["model_id"] == "whisper-private"
    assert payload["word_count"] == 5

    assert seen == {
        "data_class": DataClass.MEETING,
        "task_type": "meeting_transcription",
        "audio": b"webm-audio",
        "media_type": "audio/webm",
    }

    meeting_dir = tmp_path / "data" / "meetings"
    files = list(meeting_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    stored = files[0].read_text(encoding="utf-8")
    assert "Hello team" in stored
    assert "webm-audio" not in stored
    assert not list(meeting_dir.glob("*.webm"))
    assert not list(meeting_dir.glob("*.ogg"))
    assert not list(meeting_dir.glob("*.wav"))
    assert not list(meeting_dir.glob("*.mp4"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions are not meaningful on Windows")
def test_meeting_transcript_file_is_private(tmp_path):
    store = MeetingStore(tmp_path / "meetings")
    record = store.save_transcript(
        title="Private call",
        transcript="Sensitive discussion",
        words=[{"word": "Sensitive", "start": 0, "end": 1}],
        language="en",
        provider_id="p",
        provider_name="Provider",
        model_id="m",
        duration_ms=5,
        audio_bytes=123,
        log_id="l",
    )
    path = tmp_path / "meetings" / f"{record.id}.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "meetings").stat().st_mode & 0o777 == 0o700


def test_remote_peer_is_refused_before_provider_or_audio_processing(tmp_path):
    called = False

    def transcribe(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be reached")

    response = asyncio.run(
        _request(tmp_path, peer="203.0.113.9", patch_broker=transcribe)
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "meeting_capture_local_only"
    assert called is False
    assert not (tmp_path / "data" / "meetings").exists() or not list(
        (tmp_path / "data" / "meetings").glob("*.json")
    )


def test_remote_host_is_refused_even_from_a_loopback_peer(tmp_path):
    response = asyncio.run(
        _request(tmp_path, peer="127.0.0.1", base_url="http://crm.example")
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "meeting_capture_local_only"


def test_declared_oversized_recording_is_rejected_before_provider(tmp_path):
    called = False

    def transcribe(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be reached")

    response = asyncio.run(
        _request(
            tmp_path,
            headers={"Content-Length": str(MAX_MEETING_AUDIO_BYTES + 2 * 1024 * 1024)},
            patch_broker=transcribe,
        )
    )
    assert response.status_code == 413
    assert called is False


def test_unsupported_audio_type_is_refused(tmp_path):
    async def scenario():
        app = create_app(_settings(tmp_path))
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1"
            ) as client:
                return await client.post(
                    f"{API}/meetings/transcribe",
                    files={"file": ("meeting.txt", b"not audio", "text/plain")},
                )

    response = asyncio.run(scenario())
    assert response.status_code == 415


def test_saved_meeting_can_be_listed_and_read_but_not_path_traversed(tmp_path):
    store = MeetingStore(tmp_path / "meetings")
    record = store.save_transcript(
        title="Review",
        transcript="One two",
        words=[
            {"word": "One", "start": 0, "end": 0.4},
            {"word": "two", "start": 0.4, "end": 0.8},
        ],
        language="en",
        provider_id="p",
        provider_name="Provider",
        model_id="m",
        duration_ms=8,
        audio_bytes=50,
        log_id="log",
    )
    summary = store.list()
    assert summary[0]["id"] == record.id
    assert "transcript" not in summary[0]
    assert store.get(record.id).transcript == "One two"
    with pytest.raises(MeetingError):
        store.get("../../secrets")


def test_raw_audio_never_appears_in_the_saved_json_shape(tmp_path):
    store = MeetingStore(tmp_path / "meetings")
    record = store.save_transcript(
        title="Audit",
        transcript="Transcript only",
        words=[{"word": "Transcript", "start": 0, "end": 1}],
        language="en",
        provider_id="p",
        provider_name="Provider",
        model_id="m",
        duration_ms=1,
        audio_bytes=999,
        log_id="log",
    )
    raw = json.loads((tmp_path / "meetings" / f"{record.id}.json").read_text())
    assert set(raw) == {
        "id",
        "title",
        "created_at",
        "language",
        "provider_id",
        "provider_name",
        "model_id",
        "duration_ms",
        "audio_bytes",
        "word_count",
        "log_id",
        "transcript",
        "words",
    }
