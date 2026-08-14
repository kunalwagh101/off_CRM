"""Storage for video projects: the document, its history, and what was rendered.

Its own database, for the reason the image store gives: a timeline shares no
foreign key with the CRM, so neither has to know about the other.

**Three tables, and the second one is undo.**

``video_projects`` holds the current document and a version number.
``video_history`` holds every version that has ever existed, which makes undo a
pointer move rather than an inverse-operation problem — there is no "unsplit"
that has to reconstruct what a split destroyed, because the document before the
split is still there. It also survives a reload, so closing the tab does not
throw away an hour of edits the way an in-memory undo stack does.

``video_renders`` is the exported file. Same shape as an image asset: bytes on
disk at 0600, a row holding the path and the hash. A hundred-megabyte MP4 in a
database column would bloat every backup and every query that did not want it.

**The history is capped.** Every keystroke on a text clip is an edit, and an
uncapped history would grow without bound for a document nobody is done with.
The cap is deep enough that no one reaches the end of it in a session, and the
oldest versions are dropped rather than the newest.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db import Database, open_database

SCHEMA = """
CREATE TABLE IF NOT EXISTS video_projects (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    fps TEXT NOT NULL DEFAULT '30',
    duration_ticks INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 0,
    document TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_video_projects_campaign
    ON video_projects(campaign_id, updated_at);

CREATE TABLE IF NOT EXISTS video_history (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    operation TEXT NOT NULL DEFAULT '',
    params TEXT NOT NULL DEFAULT '{}',
    document TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_video_history
    ON video_history(project_id, version);

CREATE TABLE IF NOT EXISTS video_renders (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT 'local',
    path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    media_type TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    duration_ticks INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    renderer TEXT NOT NULL DEFAULT '',
    gate_json TEXT NOT NULL DEFAULT '{}',
    project_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_video_renders_project
    ON video_renders(project_id, created_at);

CREATE TABLE IF NOT EXISTS video_media (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    media_type TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    duration_ticks INTEGER NOT NULL DEFAULT 0,
    has_audio INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    probe_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_video_media_campaign
    ON video_media(campaign_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_video_media_hash
    ON video_media(workspace_id, campaign_id, sha256);

CREATE TABLE IF NOT EXISTS video_transcripts (
    id TEXT PRIMARY KEY,
    media_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    language TEXT NOT NULL DEFAULT '',
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    words_json TEXT NOT NULL DEFAULT '[]',
    log_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_video_transcript
    ON video_transcripts(media_id, language);
"""

#: How many versions of a document are kept. Deep enough that undo never runs
#: out inside a working session; shallow enough that a project edited for a
#: month is still a few megabytes of history.
HISTORY_LIMIT = 300

#: A render either cleared the gates or it did not. There is no "approved" here
#: — approval is the swipe, and it happens on the asset the render becomes.
RENDER_STATUSES = ("ready", "gate_failed")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class VideoStore:
    """Projects, their history, and the files they exported to."""

    def __init__(self, database_path: Path | str | None = None, *, renders_dir: Path | str) -> None:
        self.target = database_path
        self.renders_dir = Path(renders_dir)
        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self._connection: Database | None = None

    @property
    def connection(self) -> Database:
        if self._connection is None:
            database = open_database(self.target)
            database.executescript(SCHEMA)
            self._connection = database
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ── projects ────────────────────────────────────────────────────────────

    def create_project(
        self,
        *,
        project_id: str,
        campaign_id: str,
        document: dict[str, Any],
        workspace_id: str = "local",
    ) -> dict[str, Any]:
        now = _now()
        self.connection.execute(
            "INSERT INTO video_projects(id, campaign_id, workspace_id, name, width,"
            " height, fps, duration_ticks, version, document, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,0,?,?,?)",
            (
                project_id,
                campaign_id,
                workspace_id,
                str(document.get("name") or ""),
                int(document.get("width") or 0),
                int(document.get("height") or 0),
                str(document.get("fps") or "30"),
                int(document.get("duration") or 0),
                json.dumps(document),
                now,
                now,
            ),
        )
        self._write_history(project_id, 0, "create", {}, document)
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM video_projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Video project not found: {project_id}")
        item = dict(row)
        item["document"] = _safe_json(item.get("document"))
        return item

    def list_projects(self, campaign_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """The list view, deliberately without the documents.

        A project list that carried every timeline would be megabytes to render
        a page of names.
        """
        rows = self.connection.execute(
            "SELECT id, campaign_id, workspace_id, name, width, height, fps,"
            " duration_ticks, version, created_at, updated_at FROM video_projects"
            " WHERE campaign_id = ? ORDER BY updated_at DESC LIMIT ?",
            (campaign_id, max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_version(
        self,
        *,
        project_id: str,
        document: dict[str, Any],
        operation: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Store the result of one edit as the next version.

        Anything that had been undone is dropped first. Keeping it would mean a
        redo could jump onto a branch that no longer follows from the current
        document — the classic editor bug where redo restores something from a
        history that was abandoned three edits ago.
        """
        current = self.get_project(project_id)
        version = int(current["version"]) + 1
        self.connection.execute(
            "DELETE FROM video_history WHERE project_id = ? AND version >= ?",
            (project_id, version),
        )
        self._write_history(project_id, version, operation, params, document)
        self._set_current(project_id, version, document)
        self._trim_history(project_id)
        return self.get_project(project_id)

    def move_version(self, *, project_id: str, delta: int) -> dict[str, Any]:
        """Undo or redo by moving the pointer, without destroying anything."""
        current = self.get_project(project_id)
        target = int(current["version"]) + int(delta)
        row = self.connection.execute(
            "SELECT document FROM video_history WHERE project_id = ? AND version = ?",
            (project_id, target),
        ).fetchone()
        if not row:
            direction = "undo" if delta < 0 else "redo"
            raise LookupError(f"Nothing to {direction}.")
        document = _safe_json(row["document"])
        self._set_current(project_id, target, document)
        return self.get_project(project_id)

    def history(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT version, operation, params, created_at FROM video_history"
            " WHERE project_id = ? ORDER BY version DESC LIMIT ?",
            (project_id, max(1, int(limit))),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["params"] = _safe_json(item.get("params"))
            items.append(item)
        return items

    def version_bounds(self, project_id: str) -> tuple[int, int]:
        row = self.connection.execute(
            "SELECT MIN(version) AS low, MAX(version) AS high FROM video_history"
            " WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not row or row["high"] is None:
            return (0, 0)
        return (int(row["low"]), int(row["high"]))

    def delete_project(self, project_id: str) -> None:
        self.connection.execute("DELETE FROM video_history WHERE project_id = ?", (project_id,))
        self.connection.execute("DELETE FROM video_projects WHERE id = ?", (project_id,))

    def _set_current(self, project_id: str, version: int, document: dict[str, Any]) -> None:
        self.connection.execute(
            "UPDATE video_projects SET version = ?, document = ?, name = ?, width = ?,"
            " height = ?, fps = ?, duration_ticks = ?, updated_at = ? WHERE id = ?",
            (
                int(version),
                json.dumps(document),
                str(document.get("name") or ""),
                int(document.get("width") or 0),
                int(document.get("height") or 0),
                str(document.get("fps") or "30"),
                int(document.get("duration") or 0),
                _now(),
                project_id,
            ),
        )

    def _write_history(
        self,
        project_id: str,
        version: int,
        operation: str,
        params: dict[str, Any],
        document: dict[str, Any],
    ) -> None:
        self.connection.execute(
            "INSERT INTO video_history(id, project_id, version, operation, params,"
            " document, created_at) VALUES(?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                project_id,
                int(version),
                str(operation)[:60],
                json.dumps(params, default=str)[:4000],
                json.dumps(document),
                _now(),
            ),
        )

    def _trim_history(self, project_id: str) -> None:
        low, high = self.version_bounds(project_id)
        floor = high - HISTORY_LIMIT
        if floor > low:
            self.connection.execute(
                "DELETE FROM video_history WHERE project_id = ? AND version < ?",
                (project_id, floor),
            )

    # ── renders ─────────────────────────────────────────────────────────────

    def store_render(
        self,
        *,
        project_id: str,
        campaign_id: str,
        payload: bytes,
        gate_report: Any,
        status: str,
        renderer: str = "",
        project_version: int = 0,
        workspace_id: str = "local",
    ) -> str:
        """Write the exported file to disk and the record to the database.

        The file is written first, for the reason the image store gives: a row
        pointing at a file that is not there is a broken download, and a file
        with no row is a stray byte the next sweep can clean up.

        A render that failed its gates is stored anyway. Deleting it would leave
        a report saying the duration was wrong with no file to check that
        against, and the whole point of a gate is to be arguable afterwards.
        """
        if status not in RENDER_STATUSES:
            raise ValueError(f"Unknown render status: {status}")
        render_id = str(uuid.uuid4())
        digest = hashlib.sha256(payload).hexdigest()
        probe = getattr(gate_report, "probe", None)
        media_type = getattr(probe, "media_type", "") or "video/webm"
        suffix = {"video/mp4": ".mp4", "video/webm": ".webm"}.get(media_type, ".bin")

        folder = self.renders_dir / project_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{render_id}{suffix}"
        path.write_bytes(payload)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        self.connection.execute(
            "INSERT INTO video_renders(id, project_id, campaign_id, workspace_id, path,"
            " sha256, media_type, width, height, duration_ticks, bytes, status,"
            " renderer, gate_json, project_version, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                render_id,
                project_id,
                campaign_id,
                workspace_id,
                str(path),
                digest,
                media_type,
                int(getattr(probe, "width", 0) or 0),
                int(getattr(probe, "height", 0) or 0),
                int(getattr(probe, "duration_ticks", 0) or 0),
                len(payload),
                status,
                str(renderer)[:60],
                json.dumps(gate_report.to_dict() if gate_report else {}),
                int(project_version),
                _now(),
            ),
        )
        return render_id

    def get_render(self, render_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM video_renders WHERE id = ?", (render_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Render not found: {render_id}")
        item = dict(row)
        item["gates"] = _safe_json(item.pop("gate_json", "{}"))
        return item

    def list_renders(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM video_renders WHERE project_id = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (project_id, max(1, int(limit))),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["gates"] = _safe_json(item.pop("gate_json", "{}"))
            items.append(item)
        return items

    def render_hashes(self, project_id: str) -> set[str]:
        rows = self.connection.execute(
            "SELECT sha256 FROM video_renders WHERE project_id = ?", (project_id,)
        ).fetchall()
        return {str(row["sha256"]) for row in rows if row["sha256"]}


    # ── imported media ──────────────────────────────────────────────────────

    def store_media(
        self,
        *,
        campaign_id: str,
        name: str,
        payload: bytes,
        probe: Any,
        workspace_id: str = "local",
    ) -> str:
        """Keep an uploaded recording or clip, and describe it from its header.

        Same shape as a picture: bytes on disk at 0600, a row holding the path
        and the hash. The hash is unique per campaign, so uploading the same
        file twice returns the row that already exists rather than paying to
        transcribe it again.
        """
        digest = hashlib.sha256(payload).hexdigest()
        existing = self.connection.execute(
            "SELECT id FROM video_media WHERE workspace_id = ? AND campaign_id = ?"
            " AND sha256 = ?",
            (workspace_id, campaign_id, digest),
        ).fetchone()
        if existing:
            return str(existing["id"])

        media_id = str(uuid.uuid4())
        media_type = str(getattr(probe, "media_type", "") or "")
        suffix = {
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "audio/mp4": ".m4a",
            "audio/webm": ".weba",
            "audio/wav": ".wav",
        }.get(media_type, ".bin")

        folder = self.renders_dir / "media" / (campaign_id or "loose")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{media_id}{suffix}"
        path.write_bytes(payload)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        self.connection.execute(
            "INSERT INTO video_media(id, campaign_id, workspace_id, name, kind, path,"
            " sha256, media_type, width, height, duration_ticks, has_audio, bytes,"
            " probe_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                media_id,
                campaign_id,
                workspace_id,
                str(name or "")[:200],
                str(getattr(probe, "kind", "") or ""),
                str(path),
                digest,
                media_type,
                int(getattr(probe, "width", 0) or 0),
                int(getattr(probe, "height", 0) or 0),
                int(getattr(probe, "duration_ticks", 0) or 0),
                1 if getattr(probe, "has_audio", False) else 0,
                len(payload),
                json.dumps(probe.to_dict() if probe else {}),
                _now(),
            ),
        )
        return media_id

    def get_media(self, media_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM video_media WHERE id = ?", (media_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Media not found: {media_id}")
        item = dict(row)
        item["probe"] = _safe_json(item.pop("probe_json", "{}"))
        item["has_audio"] = bool(item.get("has_audio"))
        return item

    def list_media(self, campaign_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM video_media WHERE campaign_id = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (campaign_id, max(1, int(limit))),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["probe"] = _safe_json(item.pop("probe_json", "{}"))
            item["has_audio"] = bool(item.get("has_audio"))
            items.append(item)
        return items

    # ── transcripts ─────────────────────────────────────────────────────────

    def store_transcript(
        self,
        *,
        media_id: str,
        language: str,
        provider_id: str,
        model_id: str,
        text: str,
        words: list[dict[str, Any]],
        log_id: str = "",
        workspace_id: str = "local",
    ) -> str:
        """Keep a transcript so the same audio is never paid for twice.

        Not the response cache: that one is keyed on a payload and deliberately
        refuses anything whose output is a message. This is a fact about a
        specific file that cannot change unless the file does, which is exactly
        the case where storing an answer is safe.
        """
        transcript_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO video_transcripts(id, media_id, workspace_id, language,"
            " provider_id, model_id, text, words_json, log_id, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(media_id, language) DO UPDATE SET"
            " provider_id = excluded.provider_id, model_id = excluded.model_id,"
            " text = excluded.text, words_json = excluded.words_json,"
            " log_id = excluded.log_id, created_at = excluded.created_at",
            (
                transcript_id,
                media_id,
                workspace_id,
                str(language or ""),
                provider_id,
                model_id,
                str(text or "")[:200_000],
                json.dumps(words),
                log_id,
                _now(),
            ),
        )
        return transcript_id

    def get_transcript(self, media_id: str, *, language: str = "") -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM video_transcripts WHERE media_id = ? AND language = ?",
            (media_id, str(language or "")),
        ).fetchone()
        if not row:
            # A transcript taken without a language hint answers for any
            # request that did not ask for a specific one.
            row = self.connection.execute(
                "SELECT * FROM video_transcripts WHERE media_id = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (media_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["words"] = _safe_json(item.pop("words_json", "[]")) or []
        return item


def _safe_json(value: Any) -> Any:
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return {}
