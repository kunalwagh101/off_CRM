"""Durable meeting transcript metadata. Raw audio never enters this store."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from ..outreach.models import to_utc_iso


class MeetingError(ValueError):
    """A meeting or transcript chunk violates the local capture contract."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('recording','completed','failed')),
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    audio_bytes INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_meetings_workspace_started
    ON meetings(workspace_id, started_at DESC);

CREATE TABLE IF NOT EXISTS meeting_chunks (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing','completed','failed')),
    transcript TEXT NOT NULL DEFAULT '',
    words_json TEXT NOT NULL DEFAULT '[]',
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    audio_bytes INTEGER NOT NULL DEFAULT 0,
    log_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(meeting_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_meeting_chunks_meeting
    ON meeting_chunks(meeting_id, sequence);
"""


def audio_digest(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()


class MeetingStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def _workspace(value: str) -> str:
        workspace = str(value or "").strip().lower()
        if not workspace or len(workspace) > 64:
            raise MeetingError("workspace_id is invalid")
        return workspace

    @staticmethod
    def _title(value: str) -> str:
        title = " ".join(str(value or "").split())
        if not title:
            raise MeetingError("Meeting title is required")
        if len(title) > 200:
            raise MeetingError("Meeting title may be at most 200 characters")
        return title

    def create(
        self,
        *,
        workspace_id: str,
        title: str,
        provider_id: str = "",
        model_id: str = "",
        language: str = "",
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        now = to_utc_iso()
        meeting_id = uuid.uuid4().hex
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO meetings(
                    id, workspace_id, title, status, provider_id, model_id,
                    language, started_at, created_at, updated_at
                ) VALUES(?,?,?,'recording',?,?,?,?,?,?)
                """,
                (
                    meeting_id,
                    workspace,
                    self._title(title),
                    str(provider_id or "").strip(),
                    str(model_id or "").strip(),
                    str(language or "").strip()[:32],
                    now,
                    now,
                    now,
                ),
            )
        return self.require(meeting_id, workspace_id=workspace)

    def require(self, meeting_id: str, *, workspace_id: str) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM meetings WHERE id = ? AND workspace_id = ?",
                (str(meeting_id), self._workspace(workspace_id)),
            ).fetchone()
        if row is None:
            raise MeetingError("Meeting not found in this workspace")
        return dict(row)

    def list(self, *, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM meetings
                WHERE workspace_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (self._workspace(workspace_id), max(1, min(int(limit), 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    def chunks(self, meeting_id: str, *, workspace_id: str) -> list[dict[str, Any]]:
        self.require(meeting_id, workspace_id=workspace_id)
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, meeting_id, workspace_id, sequence, sha256, status,
                       transcript, words_json, provider_id, model_id, language,
                       audio_bytes, log_id, error, created_at, updated_at
                FROM meeting_chunks
                WHERE meeting_id = ? AND workspace_id = ?
                ORDER BY sequence
                """,
                (str(meeting_id), self._workspace(workspace_id)),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["words"] = json.loads(str(item.pop("words_json") or "[]"))
            except json.JSONDecodeError:
                item["words"] = []
            items.append(item)
        return items

    def claim_chunk(
        self,
        *,
        meeting_id: str,
        workspace_id: str,
        sequence: int,
        sha256: str,
        audio_bytes: int,
    ) -> tuple[str, dict[str, Any]]:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise MeetingError("Chunk sequence must be a non-negative integer")
        if audio_bytes <= 0:
            raise MeetingError("Meeting audio chunk is empty")
        workspace = self._workspace(workspace_id)
        now = to_utc_iso()
        conn = self.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            meeting = conn.execute(
                "SELECT status FROM meetings WHERE id = ? AND workspace_id = ?",
                (str(meeting_id), workspace),
            ).fetchone()
            if meeting is None:
                raise MeetingError("Meeting not found in this workspace")
            if str(meeting["status"]) != "recording":
                raise MeetingError("Meeting is no longer recording")

            existing = conn.execute(
                """
                SELECT * FROM meeting_chunks
                WHERE meeting_id = ? AND workspace_id = ? AND sequence = ?
                """,
                (str(meeting_id), workspace, sequence),
            ).fetchone()
            if existing is not None:
                row = dict(existing)
                if str(row["sha256"]) != str(sha256):
                    raise MeetingError(
                        "That chunk sequence was already used for different audio"
                    )
                if str(row["status"]) == "completed":
                    conn.commit()
                    return "cached", row
                if str(row["status"]) == "processing":
                    raise MeetingError(
                        "That chunk is already being transcribed; it will not be sent twice"
                    )
                conn.execute(
                    """
                    UPDATE meeting_chunks
                    SET status = 'processing', error = '', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, str(row["id"])),
                )
                row["status"] = "processing"
                row["error"] = ""
                conn.commit()
                return "claimed", row

            row = {
                "id": uuid.uuid4().hex,
                "meeting_id": str(meeting_id),
                "workspace_id": workspace,
                "sequence": sequence,
                "sha256": str(sha256),
                "status": "processing",
                "audio_bytes": int(audio_bytes),
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT INTO meeting_chunks(
                    id, meeting_id, workspace_id, sequence, sha256, status,
                    audio_bytes, created_at, updated_at
                ) VALUES(?,?,?,?,?,'processing',?,?,?)
                """,
                (
                    row["id"],
                    row["meeting_id"],
                    row["workspace_id"],
                    row["sequence"],
                    row["sha256"],
                    row["audio_bytes"],
                    now,
                    now,
                ),
            )
            conn.commit()
            return "claimed", row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def complete_chunk(
        self,
        chunk_id: str,
        *,
        workspace_id: str,
        transcript: str,
        words: list[dict[str, Any]],
        provider_id: str,
        model_id: str,
        language: str,
        log_id: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        now = to_utc_iso()
        text = str(transcript or "").strip()
        conn = self.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT meeting_id FROM meeting_chunks
                WHERE id = ? AND workspace_id = ? AND status = 'processing'
                """,
                (str(chunk_id), workspace),
            ).fetchone()
            if row is None:
                raise MeetingError("Transcript chunk is not claimable")
            meeting_id = str(row["meeting_id"])
            conn.execute(
                """
                UPDATE meeting_chunks
                SET status='completed', transcript=?, words_json=?,
                    provider_id=?, model_id=?, language=?, log_id=?,
                    error='', updated_at=?
                WHERE id=? AND workspace_id=?
                """,
                (
                    text,
                    json.dumps(words, ensure_ascii=False, separators=(",", ":")),
                    str(provider_id or ""),
                    str(model_id or ""),
                    str(language or "")[:32],
                    str(log_id or ""),
                    now,
                    str(chunk_id),
                    workspace,
                ),
            )
            completed = conn.execute(
                """
                SELECT transcript, audio_bytes, provider_id, model_id, language
                FROM meeting_chunks
                WHERE meeting_id=? AND workspace_id=? AND status='completed'
                ORDER BY sequence
                """,
                (meeting_id, workspace),
            ).fetchall()
            joined = "\n".join(
                str(item["transcript"]).strip()
                for item in completed
                if str(item["transcript"]).strip()
            )
            audio_bytes = sum(int(item["audio_bytes"]) for item in completed)
            provider = next(
                (str(item["provider_id"]) for item in completed if item["provider_id"]),
                "",
            )
            model = next(
                (str(item["model_id"]) for item in completed if item["model_id"]),
                "",
            )
            detected_language = next(
                (str(item["language"]) for item in completed if item["language"]),
                "",
            )
            conn.execute(
                """
                UPDATE meetings
                SET transcript=?, chunk_count=?, audio_bytes=?,
                    provider_id=?, model_id=?, language=?, updated_at=?
                WHERE id=? AND workspace_id=?
                """,
                (
                    joined,
                    len(completed),
                    audio_bytes,
                    provider,
                    model,
                    detected_language,
                    now,
                    meeting_id,
                    workspace,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.require(meeting_id, workspace_id=workspace)

    def fail_chunk(self, chunk_id: str, *, workspace_id: str, error: str) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE meeting_chunks
                SET status='failed', error=?, updated_at=?
                WHERE id=? AND workspace_id=?
                """,
                (
                    str(error or "")[:1000],
                    to_utc_iso(),
                    str(chunk_id),
                    self._workspace(workspace_id),
                ),
            )

    def complete(self, meeting_id: str, *, workspace_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        now = to_utc_iso()
        with self.connection() as conn:
            pending = conn.execute(
                """
                SELECT COUNT(*) AS n FROM meeting_chunks
                WHERE meeting_id=? AND workspace_id=? AND status='processing'
                """,
                (str(meeting_id), workspace),
            ).fetchone()
            if pending and int(pending["n"]) > 0:
                raise MeetingError("Meeting still has a transcription chunk in progress")
            cursor = conn.execute(
                """
                UPDATE meetings
                SET status='completed', ended_at=?, updated_at=?
                WHERE id=? AND workspace_id=? AND status='recording'
                """,
                (now, now, str(meeting_id), workspace),
            )
        if cursor.rowcount != 1:
            meeting = self.require(meeting_id, workspace_id=workspace)
            if meeting["status"] != "completed":
                raise MeetingError("Meeting could not be completed")
        return self.require(meeting_id, workspace_id=workspace)

    def delete(self, meeting_id: str, *, workspace_id: str) -> bool:
        workspace = self._workspace(workspace_id)
        conn = self.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM meeting_chunks WHERE meeting_id=? AND workspace_id=?",
                (str(meeting_id), workspace),
            )
            cursor = conn.execute(
                "DELETE FROM meetings WHERE id=? AND workspace_id=?",
                (str(meeting_id), workspace),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
