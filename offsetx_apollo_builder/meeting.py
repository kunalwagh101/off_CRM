"""Local meeting transcripts for S-07.01.03.

Raw meeting audio is intentionally *not* a stored entity. The browser holds the
recording until Stop, sends it once to a loopback off_CRM process, and that
process passes the bytes directly to the already-declared transcription
provider. What survives locally is the useful result: transcript, word timings
and enough provider metadata to audit where the recording went.

One JSON file per meeting is deliberate. These records are append-once,
human-readable, small compared with audio, and do not need relational joins.
Atomic replacement plus private permissions gives the durability this slice
needs without creating a database migration for a document-shaped object.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

MEETING_ID = re.compile(r"^meeting_[0-9a-f]{24}$")
MAX_TITLE_CHARS = 200
MAX_TRANSCRIPT_CHARS = 2_000_000


class MeetingError(ValueError):
    """A meeting record is invalid or cannot be addressed safely."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _private(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _clean_title(value: object) -> str:
    title = " ".join(str(value or "").split()).strip()
    if len(title) > MAX_TITLE_CHARS:
        raise MeetingError(f"Meeting title exceeds {MAX_TITLE_CHARS} characters.")
    return title or "Untitled meeting"


@dataclass(frozen=True, slots=True)
class MeetingRecord:
    id: str
    title: str
    created_at: str
    transcript: str
    words: tuple[dict[str, Any], ...]
    language: str
    provider_id: str
    provider_name: str
    model_id: str
    duration_ms: int
    audio_bytes: int
    log_id: str

    def to_dict(self, *, include_transcript: bool = True) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "language": self.language,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "duration_ms": self.duration_ms,
            "audio_bytes": self.audio_bytes,
            "word_count": len(self.words),
            "log_id": self.log_id,
        }
        if include_transcript:
            item["transcript"] = self.transcript
            item["words"] = [dict(word) for word in self.words]
        return item

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeetingRecord":
        identifier = str(raw.get("id") or "")
        if not MEETING_ID.fullmatch(identifier):
            raise MeetingError("Meeting record has an invalid id.")
        transcript = str(raw.get("transcript") or "")
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            raise MeetingError("Meeting transcript exceeds the local safety limit.")
        words_raw = raw.get("words") or []
        if not isinstance(words_raw, list):
            raise MeetingError("Meeting words must be a list.")
        words: list[dict[str, Any]] = []
        for word in words_raw:
            if not isinstance(word, Mapping):
                raise MeetingError("Meeting word timing is malformed.")
            text = str(word.get("word") or "").strip()
            try:
                start = float(word.get("start"))
                end = float(word.get("end"))
            except (TypeError, ValueError) as exc:
                raise MeetingError("Meeting word timing is malformed.") from exc
            if not text or start < 0 or end < start:
                raise MeetingError("Meeting word timing is malformed.")
            words.append({"word": text, "start": round(start, 3), "end": round(end, 3)})
        return cls(
            id=identifier,
            title=_clean_title(raw.get("title")),
            created_at=str(raw.get("created_at") or ""),
            transcript=transcript,
            words=tuple(words),
            language=str(raw.get("language") or ""),
            provider_id=str(raw.get("provider_id") or ""),
            provider_name=str(raw.get("provider_name") or ""),
            model_id=str(raw.get("model_id") or ""),
            duration_ms=max(0, int(raw.get("duration_ms") or 0)),
            audio_bytes=max(0, int(raw.get("audio_bytes") or 0)),
            log_id=str(raw.get("log_id") or ""),
        )


class MeetingStore:
    """Private append-once transcript records. Raw audio never enters this API."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        _private(self.root, 0o700)

    def _path(self, meeting_id: str) -> Path:
        if not MEETING_ID.fullmatch(str(meeting_id or "")):
            raise MeetingError("Invalid meeting id.")
        return self.root / f"{meeting_id}.json"

    def save_transcript(
        self,
        *,
        title: str,
        transcript: str,
        words: Sequence[Mapping[str, Any]],
        language: str,
        provider_id: str,
        provider_name: str,
        model_id: str,
        duration_ms: int,
        audio_bytes: int,
        log_id: str,
    ) -> MeetingRecord:
        text = str(transcript or "").strip()
        if not text:
            raise MeetingError("The transcription provider returned no transcript.")
        if len(text) > MAX_TRANSCRIPT_CHARS:
            raise MeetingError("Meeting transcript exceeds the local safety limit.")
        record = MeetingRecord.from_dict(
            {
                "id": f"meeting_{uuid.uuid4().hex[:24]}",
                "title": _clean_title(title),
                "created_at": _now(),
                "transcript": text,
                "words": [dict(word) for word in words],
                "language": language,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model_id": model_id,
                "duration_ms": duration_ms,
                "audio_bytes": audio_bytes,
                "log_id": log_id,
            }
        )
        path = self._path(record.id)
        temporary = path.with_suffix(".json.tmp")
        payload = json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"))
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            _private(temporary, 0o600)
            os.replace(temporary, path)
            _private(path, 0o600)
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass
        return record

    def get(self, meeting_id: str) -> MeetingRecord:
        path = self._path(meeting_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(meeting_id) from exc
        except (OSError, ValueError) as exc:
            raise MeetingError(f"Meeting record {meeting_id} cannot be read safely.") from exc
        if not isinstance(raw, Mapping):
            raise MeetingError(f"Meeting record {meeting_id} is malformed.")
        return MeetingRecord.from_dict(raw)

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        items: list[MeetingRecord] = []
        for path in self.root.glob("meeting_*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, Mapping):
                    items.append(MeetingRecord.from_dict(raw))
            except (OSError, ValueError, MeetingError):
                # One damaged record must not make every other transcript
                # disappear. Direct access to the damaged id still fails loudly.
                continue
        items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return [item.to_dict(include_transcript=False) for item in items[:limit]]
