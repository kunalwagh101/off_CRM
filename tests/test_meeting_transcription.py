from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.broker import (
    TranscriptResult,
    TranscriptWord,
    WorkspaceEgressSettings,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.meetings.service import (
    MeetingTranscriber,
    MeetingTranscriptionError,
)
from offsetx_apollo_builder.meetings.store import MeetingError, MeetingStore


TOKEN = "meeting-test-token-" + "m" * 32


class _Workspaces:
    def egress_settings(self, workspace_id: str) -> WorkspaceEgressSettings:
        return WorkspaceEgressSettings(
            workspace_id=workspace_id,
            enabled_provider_ids=("whisper",),
        )


class _Broker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def call_transcript(self, request, settings, **kwargs):
        self.calls.append(
            {
                "workspace_id": settings.workspace_id,
                "audio": bytes(kwargs["audio"]),
                "media_type": kwargs["media_type"],
                "provider_id": kwargs["provider_id"],
                "filename": kwargs["filename"],
            }
        )
        return TranscriptResult(
            text="Alice agreed to send the proposal.",
            words=[
                TranscriptWord("Alice", 0.0, 0.4),
                TranscriptWord("agreed", 0.5, 0.9),
            ],
            language="en",
            provider_id=str(kwargs.get("provider_id") or "whisper"),
            provider_name="Declared Whisper",
            model_id="whisper-1",
            tier="A",
            policy="full",
            duration_ms=25,
            audio_bytes=len(kwargs["audio"]),
            log_id="egress-meeting-1",
        )


def _settings(tmp_path: Path, *, host: str = "127.0.0.1") -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host=host,
        api_token=TOKEN,
        allowed_hosts=("testserver",),
    )


def test_raw_audio_is_never_persisted_and_duplicate_chunk_is_not_resent(tmp_path):
    store = MeetingStore(tmp_path / "meeting_transcripts.db")
    broker = _Broker()
    service = MeetingTranscriber(
        store=store,
        workspaces=_Workspaces(),
        broker_factory=lambda _workspace_id: broker,
    )
    meeting = store.create(
        workspace_id="alpha",
        title="Customer call",
        provider_id="whisper",
        model_id="whisper-1",
        language="en",
    )
    raw_audio = b"RAW-MEETING-AUDIO-DO-NOT-PERSIST-" + b"x" * 128

    first = service.transcribe_chunk(
        workspace_id="alpha",
        meeting_id=meeting["id"],
        sequence=0,
        audio=raw_audio,
        media_type="audio/webm",
        provider_id="whisper",
        model_id="whisper-1",
        language="en",
    )
    second = service.transcribe_chunk(
        workspace_id="alpha",
        meeting_id=meeting["id"],
        sequence=0,
        audio=raw_audio,
        media_type="audio/webm",
        provider_id="whisper",
        model_id="whisper-1",
        language="en",
    )

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(broker.calls) == 1
    assert broker.calls[0]["audio"] == raw_audio

    database_bytes = (tmp_path / "meeting_transcripts.db").read_bytes()
    assert raw_audio not in database_bytes
    assert b"RAW-MEETING-AUDIO-DO-NOT-PERSIST" not in database_bytes
    assert b"Alice agreed to send the proposal" in database_bytes


def test_chunk_sequence_cannot_be_reused_for_different_audio(tmp_path):
    store = MeetingStore(tmp_path / "meeting_transcripts.db")
    broker = _Broker()
    service = MeetingTranscriber(
        store=store,
        workspaces=_Workspaces(),
        broker_factory=lambda _workspace_id: broker,
    )
    meeting = store.create(
        workspace_id="alpha",
        title="Call",
        provider_id="whisper",
        model_id="whisper-1",
    )

    service.transcribe_chunk(
        workspace_id="alpha",
        meeting_id=meeting["id"],
        sequence=0,
        audio=b"first audio",
        media_type="audio/webm",
    )
    with pytest.raises(MeetingError, match="already used for different audio"):
        service.transcribe_chunk(
            workspace_id="alpha",
            meeting_id=meeting["id"],
            sequence=0,
            audio=b"different audio",
            media_type="audio/webm",
        )
    assert len(broker.calls) == 1


def test_meeting_transcript_is_workspace_isolated(tmp_path):
    store = MeetingStore(tmp_path / "meeting_transcripts.db")
    meeting = store.create(workspace_id="alpha", title="Alpha confidential call")

    assert store.require(meeting["id"], workspace_id="alpha")["title"] == "Alpha confidential call"
    with pytest.raises(MeetingError, match="not found"):
        store.require(meeting["id"], workspace_id="beta")
    assert store.list(workspace_id="beta") == []


@pytest.mark.parametrize("media_type", ["text/plain", "video/mp4", "application/octet-stream"])
def test_non_audio_chunk_types_are_refused_before_provider_call(tmp_path, media_type):
    store = MeetingStore(tmp_path / "meeting_transcripts.db")
    broker = _Broker()
    service = MeetingTranscriber(
        store=store,
        workspaces=_Workspaces(),
        broker_factory=lambda _workspace_id: broker,
    )
    meeting = store.create(workspace_id="alpha", title="Call")

    with pytest.raises(MeetingTranscriptionError):
        service.transcribe_chunk(
            workspace_id="alpha",
            meeting_id=meeting["id"],
            sequence=0,
            audio=b"not audio",
            media_type=media_type,
        )
    assert broker.calls == []


def test_meeting_mutation_api_requires_loopback_browser_origin(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        auth = {"X-Offsetx-Token": TOKEN}

        remote = client.post(
            "/api/v1/meetings",
            headers={**auth, "Origin": "https://crm.example.com"},
            json={
                "title": "Remote capture must fail",
                "provider_id": "whisper",
                "model_id": "whisper-1",
            },
        )
        assert remote.status_code == 403
        assert "localhost" in remote.json()["detail"].lower()

        local = client.post(
            "/api/v1/meetings",
            headers={**auth, "Origin": "http://localhost:5173"},
            json={
                "title": "Local capture",
                "provider_id": "whisper",
                "model_id": "whisper-1",
            },
        )
        assert local.status_code == 201
        meeting_id = local.json()["id"]

        # Read access is authenticated but does not need raw-audio origin
        # permission because it returns derived transcript metadata only.
        readback = client.get(f"/api/v1/meetings/{meeting_id}", headers=auth)
        assert readback.status_code == 200
        assert readback.json()["title"] == "Local capture"


def test_hosted_backend_refuses_meeting_capture_even_with_local_origin(tmp_path):
    settings = _settings(tmp_path, host="0.0.0.0")
    settings.allowed_hosts = ("testserver",)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/meetings",
            headers={
                "X-Offsetx-Token": TOKEN,
                "Origin": "http://localhost:5173",
            },
            json={
                "title": "Must stay local",
                "provider_id": "whisper",
                "model_id": "whisper-1",
            },
        )
        assert response.status_code == 403
        assert "local-only" in response.json()["detail"].lower()


def test_frontend_capture_uses_local_mic_system_audio_and_media_recorder():
    source = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "pages"
        / "Meetings.tsx"
    ).read_text(encoding="utf-8")

    for marker in (
        "navigator.mediaDevices.getDisplayMedia",
        "navigator.mediaDevices.getUserMedia",
        "createMediaStreamDestination",
        "new MediaRecorder",
        "api.upload",
        'form.append("provider_id"',
        'form.append("model_id"',
        'Raw audio was not stored',
    ):
        assert marker in source, marker

    # No browser persistence API is allowed for raw audio.
    assert "localStorage" not in source
    assert "indexedDB" not in source
    assert "FileSystem" not in source



def test_encrypted_backup_restores_meeting_transcript_state(tmp_path):
    settings = _settings(tmp_path)
    headers = {"X-Offsetx-Token": TOKEN}
    passphrase = "meeting-backup-passphrase"

    with TestClient(create_app(settings)) as client:
        meeting = client.app.state.meeting_store.create(
            workspace_id="local",
            title="Durable meeting transcript",
        )

        backup = client.post(
            "/api/v1/backups/export",
            headers=headers,
            json={"passphrase": passphrase},
        )
        assert backup.status_code == 200

        assert client.app.state.meeting_store.delete(
            meeting["id"], workspace_id="local"
        )

        restored = client.post(
            "/api/v1/backups/restore",
            headers=headers,
            files={
                "file": (
                    "meeting.oxbackup",
                    backup.content,
                    "application/octet-stream",
                )
            },
            data={"passphrase": passphrase},
        )
        assert restored.status_code == 200
        assert client.app.state.meeting_store.require(
            meeting["id"], workspace_id="local"
        )["title"] == "Durable meeting transcript"



def test_chunk_cannot_redirect_audio_to_a_different_provider(tmp_path):
    store = MeetingStore(tmp_path / "meeting_transcripts.db")
    broker = _Broker()
    service = MeetingTranscriber(
        store=store,
        workspaces=_Workspaces(),
        broker_factory=lambda _workspace_id: broker,
    )
    meeting = store.create(
        workspace_id="alpha",
        title="Provider-bound call",
        provider_id="whisper",
        model_id="whisper-1",
    )

    with pytest.raises(MeetingTranscriptionError, match="cannot change"):
        service.transcribe_chunk(
            workspace_id="alpha",
            meeting_id=meeting["id"],
            sequence=0,
            audio=b"private meeting audio",
            media_type="audio/webm",
            provider_id="other-provider",
            model_id="other-model",
        )

    assert broker.calls == []
    assert store.chunks(meeting["id"], workspace_id="alpha") == []
