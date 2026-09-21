"""Meeting transcription through the single governed AI egress broker."""
from __future__ import annotations

from typing import Any, Callable

from ..ai import DataClass, EgressBroker, EgressRequest
from ..ai.broker import TranscriptResult
from ..ai.workspace import WorkspaceAISettingsStore
from .store import MeetingError, MeetingStore, audio_digest

MAX_MEETING_CHUNK_BYTES = 8 * 1024 * 1024
ALLOWED_MEETING_AUDIO_TYPES = frozenset({
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
})


class MeetingTranscriptionError(ValueError):
    """Meeting audio cannot safely be sent to the declared provider."""


class MeetingTranscriber:
    def __init__(
        self,
        *,
        store: MeetingStore,
        workspaces: WorkspaceAISettingsStore,
        broker_factory: Callable[[str], EgressBroker],
    ) -> None:
        self.store = store
        self.workspaces = workspaces
        self.broker_factory = broker_factory

    @staticmethod
    def normalize_media_type(value: str) -> str:
        media_type = str(value or "").split(";", 1)[0].strip().lower()
        if media_type not in ALLOWED_MEETING_AUDIO_TYPES:
            raise MeetingTranscriptionError(
                "Meeting chunks must be WebM, Ogg, MP4, MPEG or WAV audio"
            )
        return media_type

    def transcribe_chunk(
        self,
        *,
        workspace_id: str,
        meeting_id: str,
        sequence: int,
        audio: bytes,
        media_type: str,
        provider_id: str = "",
        model_id: str = "",
        language: str = "",
    ) -> dict[str, Any]:
        if not audio:
            raise MeetingTranscriptionError("Meeting audio chunk is empty")
        if len(audio) > MAX_MEETING_CHUNK_BYTES:
            raise MeetingTranscriptionError(
                f"Meeting audio chunk exceeds {MAX_MEETING_CHUNK_BYTES} bytes"
            )
        normalized_type = self.normalize_media_type(media_type)
        meeting = self.store.require(meeting_id, workspace_id=workspace_id)
        declared_provider = str(meeting.get("provider_id") or "").strip()
        declared_model = str(meeting.get("model_id") or "").strip()
        if not declared_provider or not declared_model:
            raise MeetingTranscriptionError(
                "Meeting has no declared transcription provider/model"
            )
        supplied_provider = str(provider_id or "").strip()
        supplied_model = str(model_id or "").strip()
        if supplied_provider and supplied_provider != declared_provider:
            raise MeetingTranscriptionError(
                "A meeting chunk cannot change the declared transcription provider"
            )
        if supplied_model and supplied_model != declared_model:
            raise MeetingTranscriptionError(
                "A meeting chunk cannot change the declared transcription model"
            )
        digest = audio_digest(audio)
        state, chunk = self.store.claim_chunk(
            meeting_id=meeting_id,
            workspace_id=workspace_id,
            sequence=sequence,
            sha256=digest,
            audio_bytes=len(audio),
        )
        if state == "cached":
            meeting = self.store.require(meeting_id, workspace_id=workspace_id)
            return {
                "cached": True,
                "meeting": meeting,
                "chunk": {
                    "sequence": sequence,
                    "transcript": str(chunk.get("transcript") or ""),
                    "provider_id": str(chunk.get("provider_id") or ""),
                    "model_id": str(chunk.get("model_id") or ""),
                    "language": str(chunk.get("language") or ""),
                    "audio_bytes": int(chunk.get("audio_bytes") or 0),
                    "log_id": str(chunk.get("log_id") or ""),
                },
            }

        try:
            settings = self.workspaces.egress_settings(workspace_id)
            settings.enabled_models = {
                **settings.enabled_models,
                declared_provider: (declared_model,),
            }
            broker = self.broker_factory(workspace_id)
            result: TranscriptResult = broker.call_transcript(
                EgressRequest(
                    task_type="meeting_transcription",
                    data_class=DataClass.CAMPAIGN,
                    instructions=(
                        "Transcribe this meeting audio accurately. Preserve names, "
                        "decisions and action items as spoken. Do not invent missing words."
                    ),
                    task_tags=("transcribe", "meeting"),
                ),
                settings,
                audio=audio,
                media_type=normalized_type,
                filename=f"meeting-{meeting_id}-chunk-{sequence}.webm",
                language=str(language or "").strip()[:32],
                provider_id=declared_provider,
            )
            words = [item.to_dict() for item in result.words]
            meeting = self.store.complete_chunk(
                str(chunk["id"]),
                workspace_id=workspace_id,
                transcript=result.text,
                words=words,
                provider_id=result.provider_id,
                model_id=result.model_id,
                language=result.language,
                log_id=result.log_id,
            )
            return {
                "cached": False,
                "meeting": meeting,
                "chunk": {
                    "sequence": sequence,
                    "transcript": result.text,
                    "words": words,
                    "provider_id": result.provider_id,
                    "provider_name": result.provider_name,
                    "model_id": result.model_id,
                    "language": result.language,
                    "audio_bytes": result.audio_bytes,
                    "log_id": result.log_id,
                },
            }
        except Exception as exc:
            self.store.fail_chunk(
                str(chunk["id"]),
                workspace_id=workspace_id,
                error=str(exc),
            )
            raise
