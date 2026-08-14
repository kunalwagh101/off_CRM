"""Timelines on Postgres, so an edit survives the machine it was made on.

The video store was written against SQLite and lands on a host whose filesystem
does not survive a restart — Render's free plan writes to `/tmp`, and an
instance that sleeps comes back empty. An hour of editing disappearing at that
point is not a storage detail, it is the work.

So the store goes through the same seam the egress log uses: an explicit target
wins, then `OFFSETX_DATABASE_URL`, then the local file. Nothing else changes.

**What this cannot fix, and says so:** the rendered files, the uploaded
recordings and the generated pictures are bytes on a disk. A database does not
hold them and pretending otherwise would be worse than the gap. The *document* —
the timeline, its history, its transcripts — is the part that took the work, and
it is the part this moves.

Every test here runs against both backends where that is meaningful, and the
Postgres half is skipped unless `OFF_CRM_TEST_POSTGRES_URL` is set:

    OFF_CRM_TEST_POSTGRES_URL="postgresql://postgres@/offcrm_test?host=/tmp&port=5433"
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from offsetx_apollo_builder.db import resolve_target
from offsetx_apollo_builder.video.engine import VideoEditorEngine
from offsetx_apollo_builder.video.store import SCHEMA, VideoStore
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND

POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])
needs_postgres = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set OFF_CRM_TEST_POSTGRES_URL to a postgresql:// URL to run these",
)

CAMPAIGN = "campaign-1"
SECOND = TICKS_PER_SECOND
TABLES = (
    "video_transcripts",
    "video_media",
    "video_renders",
    "video_history",
    "video_projects",
)


def wav(seconds: float = 3.0, *, rate: int = 16000) -> bytes:
    byte_rate = rate * 2
    body = b"\x00" * int(byte_rate * seconds)
    fmt = struct.pack("<HHIIHH", 1, 1, rate, byte_rate, 2, 16)
    chunks = (
        b"fmt " + struct.pack("<I", len(fmt)) + fmt
        + b"data" + struct.pack("<I", len(body)) + body
    )
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def open_store(backend: str, tmp_path: Path, *, fresh: bool = True) -> VideoStore:
    if backend == "sqlite":
        return VideoStore(tmp_path / "video.db", renders_dir=tmp_path / "renders")
    store = VideoStore(POSTGRES_URL, renders_dir=tmp_path / "renders")
    if fresh:
        for table in TABLES:
            store.connection.executescript(f"DROP TABLE IF EXISTS {table}")
        store.connection.executescript(SCHEMA)
    return store


@pytest.fixture(params=BACKENDS)
def backend(request) -> str:
    return request.param


def engine_for(store: VideoStore) -> VideoEditorEngine:
    return VideoEditorEngine(
        store=store, campaign_reader=lambda cid: {"id": cid, "kind": "image"}
    )


def test_the_schema_creates_cleanly_on_both_backends(backend, tmp_path):
    """The one that catches a keyword or a type SQLite tolerates and Postgres
    does not."""
    store = open_store(backend, tmp_path)
    try:
        assert store.connection.columns("video_projects") >= {
            "id", "campaign_id", "document", "version", "duration_ticks",
        }
        assert store.connection.columns("video_media") >= {"id", "sha256", "has_audio"}
        assert store.connection.columns("video_transcripts") >= {"media_id", "words_json"}
    finally:
        store.close()


def test_a_whole_edit_session_survives_a_cold_reopen(backend, tmp_path):
    """The point of the change: close everything, open it again, and the work is
    still there — including the undo history."""
    store = open_store(backend, tmp_path)
    engine = engine_for(store)
    state = engine.create_project(CAMPAIGN, name="Reel", preset="vertical", fps="30")
    project_id = state.project.id
    track = state.project.tracks[0].id
    for index in range(3):
        engine.edit(
            project_id,
            "add_clip",
            {
                "track_id": track,
                "kind": "solid",
                "start": index * 4 * SECOND,
                "duration": 3 * SECOND,
                "style": {"colour": "#2667ff"},
            },
        )
    clip = engine.open_project(project_id).project.tracks[0].clips[0].id
    engine.edit(project_id, "split_clip", {"clip_id": clip, "at": SECOND})
    engine.edit(project_id, "add_keyframe", {"clip_id": clip, "name": "scale", "at": 0, "value": 0.5})
    before = engine.open_project(project_id)
    store.close()

    reopened = open_store(backend, tmp_path, fresh=False)
    try:
        after = engine_for(reopened).open_project(project_id)
        assert after.project.to_dict() == before.project.to_dict()
        assert after.record["version"] == before.record["version"]
        assert after.can_undo
        assert len(reopened.history(project_id, limit=100)) == before.record["version"] + 1
    finally:
        reopened.close()


def test_undo_and_redo_still_walk_the_history_after_a_reopen(backend, tmp_path):
    store = open_store(backend, tmp_path)
    engine = engine_for(store)
    state = engine.create_project(CAMPAIGN, name="Reel")
    project_id = state.project.id
    track = state.project.tracks[0].id
    for index in range(3):
        engine.edit(
            project_id,
            "add_clip",
            {"track_id": track, "kind": "solid", "start": index * 4 * SECOND, "duration": 3 * SECOND},
        )
    store.close()

    reopened = open_store(backend, tmp_path, fresh=False)
    try:
        engine = engine_for(reopened)
        engine.undo(project_id)
        engine.undo(project_id)
        assert len(engine.open_project(project_id).project.tracks[0].clips) == 1
        engine.redo(project_id)
        assert len(engine.open_project(project_id).project.tracks[0].clips) == 2
    finally:
        reopened.close()


def test_media_and_transcripts_survive_too(backend, tmp_path):
    """A transcript is the expensive answer. Losing it means paying a provider
    twice for the same recording."""
    store = open_store(backend, tmp_path)
    engine = engine_for(store)
    media = engine.import_media(CAMPAIGN, wav(), name="voiceover.wav")
    store.store_transcript(
        media_id=media["id"],
        language="",
        provider_id="groq",
        model_id="whisper-large-v3",
        text="hello there",
        words=[{"word": "hello", "start": 0.0, "end": 0.4}],
    )
    store.close()

    reopened = open_store(backend, tmp_path, fresh=False)
    try:
        again = reopened.get_media(media["id"])
        assert again["name"] == "voiceover.wav"
        assert again["has_audio"] is True
        assert again["duration_ticks"] == 3 * SECOND
        transcript = reopened.get_transcript(media["id"])
        assert transcript is not None
        assert transcript["text"] == "hello there"
        assert transcript["words"][0]["word"] == "hello"
    finally:
        reopened.close()


def test_the_upsert_on_a_transcript_works_on_both_backends(backend, tmp_path):
    """``ON CONFLICT … DO UPDATE`` is the one piece of SQL here that is not
    plain, so it is checked rather than assumed."""
    store = open_store(backend, tmp_path)
    try:
        engine = engine_for(store)
        media = engine.import_media(CAMPAIGN, wav())
        for text in ("first pass", "second pass"):
            store.store_transcript(
                media_id=media["id"],
                language="",
                provider_id="groq",
                model_id="whisper-large-v3",
                text=text,
                words=[],
            )
        assert store.get_transcript(media["id"])["text"] == "second pass"
    finally:
        store.close()


def test_the_same_upload_twice_is_still_one_row(backend, tmp_path):
    """The unique index on the hash, which is what stops paying to transcribe
    the same recording twice."""
    store = open_store(backend, tmp_path)
    try:
        engine = engine_for(store)
        first = engine.import_media(CAMPAIGN, wav(), name="a.wav")
        second = engine.import_media(CAMPAIGN, wav(), name="b.wav")
        assert first["id"] == second["id"]
        assert len(store.list_media(CAMPAIGN)) == 1
    finally:
        store.close()


def test_history_is_trimmed_on_both_backends(backend, tmp_path):
    from offsetx_apollo_builder.video.store import HISTORY_LIMIT

    store = open_store(backend, tmp_path)
    try:
        engine = engine_for(store)
        state = engine.create_project(CAMPAIGN, name="Reel")
        for index in range(HISTORY_LIMIT + 5):
            engine.edit(state.project.id, "rename", {"name": f"Take {index}"})
        low, high = store.version_bounds(state.project.id)
        assert high - low <= HISTORY_LIMIT
    finally:
        store.close()


# ── the wiring, which is the part that actually moves it ────────────────────


def test_the_environment_can_move_timelines_without_touching_a_call_site(monkeypatch):
    """An explicit target still wins, so a test cannot be reached into."""
    monkeypatch.setenv("OFFSETX_DATABASE_URL", "postgresql://example/db")
    assert resolve_target(default="/data/video.db") == "postgresql://example/db"
    assert resolve_target("/tmp/explicit.db", default="/data/video.db") == "/tmp/explicit.db"
    monkeypatch.delenv("OFFSETX_DATABASE_URL")
    assert resolve_target(default="/data/video.db") == "/data/video.db"


def test_the_api_passes_the_video_store_through_the_seam():
    """Structural: a call site that passed its path directly would ignore
    OFFSETX_DATABASE_URL, and the failure would only show as work quietly lost
    on the next restart."""
    import ast
    import inspect

    from offsetx_apollo_builder.api import app as app_module

    tree = ast.parse(inspect.getsource(app_module))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "VideoStore"
    ]
    assert calls, "the API no longer constructs a VideoStore"
    for call in calls:
        target = call.args[0]
        assert isinstance(target, ast.Call) and getattr(target.func, "id", "") == (
            "resolve_database_target"
        ), "VideoStore must be given a resolved target, not a bare path"


@needs_postgres
def test_the_document_round_trips_through_postgres_json_unchanged(tmp_path):
    """Documents are stored as JSON text. A backend that re-encoded them — or a
    driver that handed back a dict instead of a string — would change what
    ``from_dict`` sees."""
    store = open_store("postgres", tmp_path)
    try:
        engine = engine_for(store)
        state = engine.create_project(CAMPAIGN, name="Ünïcode ✓ reel", preset="square")
        project_id = state.project.id
        track = state.project.tracks[0].id
        engine.edit(
            project_id,
            "add_clip",
            {
                "track_id": track,
                "kind": "text",
                "start": 0,
                "duration": 2 * SECOND,
                "text": "Ünïcode ✓ — em dash, \"quotes\", 'apostrophes'",
                "style": {"colour": "#ff0055", "size": 72},
            },
        )
        stored = store.get_project(project_id)
        assert isinstance(stored["document"], dict)
        assert stored["document"]["name"] == "Ünïcode ✓ reel"
        clip = stored["document"]["tracks"][0]["clips"][0]
        assert clip["text"].startswith("Ünïcode ✓ —")
        assert clip["style"] == {"colour": "#ff0055", "size": 72}
    finally:
        store.close()
