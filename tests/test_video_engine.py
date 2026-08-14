"""The video editor runner: projects, undo, assets and the file that comes back.

Where the browser and the server meet. Three things are being protected:

**The kind gate.** A timeline belongs to an image campaign, and every entry
point checks it — the same rule the image and distribution runners already
apply to each other.

**Undo that survives the tab closing.** History is stored, not held in memory,
and a version pointer moves over it. That makes undo a lookup rather than an
inverse-operation problem: there is no "unsplit" that has to reconstruct what a
split destroyed.

**A render is checked against the project it claims to be of.** The browser
draws and encodes; the server decides whether what came back is the right shape
and the right length. A check the renderer runs on its own output is a check
that cannot fail.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.campaigns import WrongCampaignKind
from offsetx_apollo_builder.video.engine import DEFAULT_STILL_TICKS, VideoEditorEngine
from offsetx_apollo_builder.video.store import HISTORY_LIMIT, VideoStore
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND, TimelineError

CAMPAIGN = "campaign-1"
SECOND = TICKS_PER_SECOND
MUXED = Path(__file__).parent / "fixtures" / "muxed_sample.webm"


class _Assets:
    """Stands in for the image store, which is where generated pictures live."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "assets"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows: dict[str, dict] = {}

    def add(self, asset_id: str, *, status: str = "approved", on_disk: bool = True) -> str:
        path = self.dir / f"{asset_id}.png"
        if on_disk:
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        self.rows[asset_id] = {
            "id": asset_id,
            "status": status,
            "path": str(path) if on_disk else "",
            "width": 1024,
            "height": 1024,
            "media_type": "image/png",
            "model_id": "flux",
        }
        return asset_id

    def get(self, asset_id: str) -> dict:
        if asset_id not in self.rows:
            raise KeyError(f"Asset not found: {asset_id}")
        return self.rows[asset_id]


@pytest.fixture()
def assets(tmp_path: Path) -> _Assets:
    return _Assets(tmp_path)


@pytest.fixture()
def engine(tmp_path: Path, assets: _Assets):
    store = VideoStore(tmp_path / "video.db", renders_dir=tmp_path / "renders")
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
        asset_reader=assets.get,
    )
    try:
        yield runner
    finally:
        store.close()


def _project(engine: VideoEditorEngine):
    return engine.create_project(CAMPAIGN, name="Reel", preset="vertical", fps="30")


# ── the kind gate ───────────────────────────────────────────────────────────


def test_the_editor_refuses_a_campaign_that_is_not_an_image_campaign(tmp_path):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    runner = VideoEditorEngine(
        store=store, campaign_reader=lambda cid: {"id": cid, "kind": "email"}
    )
    try:
        for call in (
            lambda: runner.create_project(CAMPAIGN),
            lambda: runner.list_projects(CAMPAIGN),
            lambda: runner.summary(CAMPAIGN),
        ):
            with pytest.raises(WrongCampaignKind):
                call()
    finally:
        store.close()


def test_a_project_cannot_be_opened_through_a_campaign_of_another_kind(tmp_path, assets):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    kinds = {CAMPAIGN: "image"}
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": kinds[cid]},
        asset_reader=assets.get,
    )
    try:
        state = runner.create_project(CAMPAIGN)
        kinds[CAMPAIGN] = "distribution"
        with pytest.raises(WrongCampaignKind):
            runner.open_project(state.project.id)
    finally:
        store.close()


# ── projects and editing ────────────────────────────────────────────────────


def test_a_new_project_has_a_video_track_and_an_audio_track(engine):
    state = _project(engine)
    assert [track.kind for track in state.project.tracks] == ["video", "audio"]
    assert (state.project.width, state.project.height) == (1080, 1920)
    assert not state.can_undo and not state.can_redo


def test_an_edit_becomes_a_new_version_and_the_old_one_is_still_there(engine):
    state = _project(engine)
    track = state.project.tracks[0].id
    after = engine.edit(
        state.project.id,
        "add_clip",
        {"track_id": track, "kind": "image", "start": 0, "duration": 3 * SECOND},
    )
    assert after.record["version"] == 1
    assert after.can_undo and not after.can_redo
    assert engine.undo(state.project.id).project.tracks[0].clips == []


def test_a_refused_edit_does_not_consume_a_step_of_undo(engine):
    state = _project(engine)
    with pytest.raises(TimelineError):
        engine.edit(state.project.id, "add_clip", {"track_id": "nope", "kind": "image"})
    assert engine.open_project(state.project.id).record["version"] == 0


def test_undo_and_redo_walk_the_same_history(engine):
    state = _project(engine)
    track = state.project.tracks[0].id
    for index in range(3):
        engine.edit(
            state.project.id,
            "add_clip",
            {
                "track_id": track,
                "kind": "image",
                "start": index * 4 * SECOND,
                "duration": 3 * SECOND,
            },
        )
    assert len(engine.open_project(state.project.id).project.tracks[0].clips) == 3
    engine.undo(state.project.id)
    engine.undo(state.project.id)
    assert len(engine.open_project(state.project.id).project.tracks[0].clips) == 1
    engine.redo(state.project.id)
    assert len(engine.open_project(state.project.id).project.tracks[0].clips) == 2


def test_editing_after_an_undo_abandons_the_branch_that_was_undone(engine):
    """Otherwise redo restores something from a history that no longer follows
    from the current document."""
    state = _project(engine)
    track = state.project.tracks[0].id
    engine.edit(
        state.project.id,
        "add_clip",
        {"track_id": track, "kind": "image", "start": 0, "duration": 3 * SECOND},
    )
    engine.undo(state.project.id)
    engine.edit(state.project.id, "rename", {"name": "Different"})
    with pytest.raises(LookupError):
        engine.redo(state.project.id)


def test_undoing_past_the_beginning_says_so_rather_than_doing_nothing(engine):
    state = _project(engine)
    with pytest.raises(LookupError, match="undo"):
        engine.undo(state.project.id)


def test_a_batch_is_one_step_of_undo(engine):
    """A drag is a stream of moves, and undo should return to where it began."""
    state = _project(engine)
    track = state.project.tracks[0].id
    engine.edit(
        state.project.id,
        "add_clip",
        {"track_id": track, "kind": "image", "start": 0, "duration": 3 * SECOND},
    )
    clip = engine.open_project(state.project.id).project.tracks[0].clips[0].id
    engine.batch(
        state.project.id,
        [
            {"op": "move_clip", "params": {"clip_id": clip, "start": SECOND}},
            {"op": "move_clip", "params": {"clip_id": clip, "start": 2 * SECOND}},
            {"op": "move_clip", "params": {"clip_id": clip, "start": 4 * SECOND}},
        ],
    )
    assert engine.open_project(state.project.id).project.tracks[0].clips[0].start == 4 * SECOND
    engine.undo(state.project.id)
    assert engine.open_project(state.project.id).project.tracks[0].clips[0].start == 0


def test_a_batch_that_fails_halfway_stores_nothing(engine):
    state = _project(engine)
    track = state.project.tracks[0].id
    with pytest.raises(TimelineError):
        engine.batch(
            state.project.id,
            [
                {"op": "add_clip", "params": {"track_id": track, "kind": "image", "start": 0, "duration": 3 * SECOND}},
                {"op": "add_clip", "params": {"track_id": track, "kind": "image", "start": SECOND, "duration": 3 * SECOND}},
            ],
        )
    assert engine.open_project(state.project.id).record["version"] == 0


def test_history_is_capped_so_a_long_session_does_not_grow_forever(engine):
    state = _project(engine)
    for index in range(HISTORY_LIMIT + 20):
        engine.edit(state.project.id, "rename", {"name": f"Take {index}"})
    low, high = engine.store.version_bounds(state.project.id)
    assert high - low <= HISTORY_LIMIT
    assert engine.open_project(state.project.id).project.name == f"Take {HISTORY_LIMIT + 19}"


def test_the_history_records_what_each_edit_was(engine):
    state = _project(engine)
    engine.edit(state.project.id, "rename", {"name": "Second cut"})
    entries = engine.history(state.project.id)
    assert entries[0]["operation"] == "rename"
    assert entries[0]["params"]["name"] == "Second cut"


# ── generated pictures on the timeline ──────────────────────────────────────


def test_a_generated_picture_lands_on_the_timeline_with_its_real_size(engine, assets):
    state = _project(engine)
    assets.add("asset-1")
    after = engine.place_asset(state.project.id, asset_id="asset-1")
    clip = after.project.tracks[0].clips[0]
    assert clip.asset_id == "asset-1"
    assert clip.duration == DEFAULT_STILL_TICKS
    assert clip.style["source_width"] == 1024
    assert clip.label == "flux"


def test_two_pictures_land_end_to_end_rather_than_on_top_of_each_other(engine, assets):
    state = _project(engine)
    assets.add("asset-1")
    assets.add("asset-2")
    engine.place_asset(state.project.id, asset_id="asset-1")
    after = engine.place_asset(state.project.id, asset_id="asset-2")
    starts = [clip.start for clip in after.project.tracks[0].clips]
    assert starts == [0, DEFAULT_STILL_TICKS]


def test_a_rejected_picture_cannot_be_placed(engine, assets):
    """The swipe deletes the file, so a clip pointing at one is a hole that
    would not be noticed until export."""
    assets.add("asset-1", status="rejected", on_disk=False)
    state = _project(engine)
    with pytest.raises(TimelineError, match="rejected"):
        engine.place_asset(state.project.id, asset_id="asset-1")


# ── the manifest ────────────────────────────────────────────────────────────


def test_the_manifest_lists_what_the_browser_has_to_fetch(engine, assets):
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1")
    manifest = engine.manifest(state.project.id)
    assert manifest["renderable"]
    assert manifest["assets"] == [
        {
            "id": "asset-1",
            "available": True,
            "media_type": "image/png",
            "width": 1024,
            "height": 1024,
            "status": "approved",
        }
    ]
    assert manifest["frames"] == 150
    assert manifest["ticks_per_frame"] == 3000


def test_an_empty_timeline_is_not_renderable_and_says_why(engine):
    manifest = engine.manifest(_project(engine).project.id)
    assert not manifest["renderable"]
    assert "nothing to export" in manifest["warnings"][0]


def test_a_picture_swiped_away_after_it_was_placed_is_reported_before_the_export(engine, assets):
    """The alternative is rendering a black hole and handing back a file that
    looks finished."""
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1")
    Path(assets.rows["asset-1"]["path"]).unlink()
    manifest = engine.manifest(state.project.id)
    assert not manifest["renderable"]
    assert "discarded after it was placed" in manifest["warnings"][0]


def test_a_clip_pointing_at_an_asset_that_no_longer_exists_is_reported(engine, assets):
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1")
    assets.rows.pop("asset-1")
    assert "no longer exists" in engine.manifest(state.project.id)["warnings"][0]


# ── the file that comes back ────────────────────────────────────────────────


def _three_second_project(engine, assets):
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1", duration=3 * SECOND)
    return state.project.id


def test_an_export_that_matches_the_project_is_stored_as_ready(engine, assets):
    project_id = _three_second_project(engine, assets)
    result = engine.store_render(project_id, MUXED.read_bytes(), renderer="webcodecs/vp09")
    assert result["passed"], result["summary"]
    stored = engine.renders(project_id)[0]
    assert stored["status"] == "ready"
    assert stored["renderer"] == "webcodecs/vp09"
    assert stored["duration_ticks"] == 3 * SECOND
    assert Path(stored["path"]).exists()


def test_the_render_is_a_file_on_disk_and_the_row_points_at_it(engine, assets):
    project_id = _three_second_project(engine, assets)
    engine.store_render(project_id, MUXED.read_bytes())
    stored = engine.renders(project_id)[0]
    path = Path(stored["path"])
    assert path.suffix == ".webm"
    assert path.stat().st_size == stored["bytes"]
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_an_export_of_the_wrong_length_fails_its_gates_and_is_kept_anyway(engine, assets):
    """A gate result nobody can check the file against is an assertion, not
    evidence."""
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1", duration=10 * SECOND)
    result = engine.store_render(state.project.id, MUXED.read_bytes())
    assert not result["passed"]
    assert "duration_matches" in result["summary"]
    stored = engine.renders(state.project.id)[0]
    assert stored["status"] == "gate_failed"
    assert Path(stored["path"]).exists()


def test_the_same_export_twice_is_caught(engine, assets):
    project_id = _three_second_project(engine, assets)
    engine.store_render(project_id, MUXED.read_bytes())
    second = engine.store_render(project_id, MUXED.read_bytes())
    assert not second["passed"]
    assert "not_duplicate" in second["summary"]


def test_the_render_records_which_version_of_the_project_it_came_from(engine, assets):
    project_id = _three_second_project(engine, assets)
    engine.edit(project_id, "rename", {"name": "Final"})
    engine.store_render(project_id, MUXED.read_bytes())
    assert engine.renders(project_id)[0]["project_version"] == 2


def test_the_summary_reports_where_the_campaign_stands(engine, assets):
    project_id = _three_second_project(engine, assets)
    engine.store_render(project_id, MUXED.read_bytes())
    summary = engine.summary(CAMPAIGN)
    assert summary["projects"] == 1
    assert summary["renders"] == 1
    assert summary["renders_passed"] == 1
    assert summary["total_duration_seconds"] == 3.0


# ── through the API ─────────────────────────────────────────────────────────


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )


def test_the_whole_path_works_over_http(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        campaign = client.post(
            "/api/v1/campaigns", json={"name": "Reels", "kind": "image"}
        ).json()

        created = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-projects",
            json={"name": "Launch reel", "preset": "vertical", "fps": "30"},
        )
        assert created.status_code == 201
        project = created.json()
        track = project["document"]["tracks"][0]["id"]

        edited = client.post(
            f"/api/v1/video-projects/{project['id']}/edit",
            json={
                "op": "add_clip",
                "params": {
                    "track_id": track,
                    "kind": "solid",
                    "start": 0,
                    "duration": 3 * SECOND,
                    "style": {"colour": "#101014"},
                },
            },
        ).json()
        assert edited["version"] == 1
        assert edited["can_undo"] is True

        manifest = client.get(f"/api/v1/video-projects/{project['id']}/manifest").json()
        assert manifest["renderable"]
        assert manifest["duration_ticks"] == 3 * SECOND

        frame = client.get(
            f"/api/v1/video-projects/{project['id']}/frame", params={"tick": SECOND}
        ).json()
        assert frame["items"][0]["kind"] == "solid"

        upload = client.post(
            f"/api/v1/video-projects/{project['id']}/renders",
            files={"file": ("cut.webm", MUXED.read_bytes(), "video/webm")},
            data={"renderer": "webcodecs/vp09.00.10.08"},
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["passed"], upload.json()["summary"]

        render_id = upload.json()["render_id"]
        served = client.get(f"/api/v1/video-renders/{render_id}/file")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("video/webm")
        assert len(served.content) == len(MUXED.read_bytes())

        undone = client.post(f"/api/v1/video-projects/{project['id']}/undo").json()
        assert undone["document"]["tracks"][0]["clips"] == []
        assert client.post(f"/api/v1/video-projects/{project['id']}/undo").status_code == 409


def test_the_api_refuses_an_edit_it_does_not_know(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        campaign = client.post("/api/v1/campaigns", json={"name": "R", "kind": "image"}).json()
        project = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-projects", json={}
        ).json()
        refused = client.post(
            f"/api/v1/video-projects/{project['id']}/edit",
            json={"op": "enhance", "params": {}},
        )
        assert refused.status_code == 422
        assert "Unknown edit" in refused.json()["detail"]


def test_the_api_will_not_open_a_video_project_from_an_email_campaign(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        email = client.post("/api/v1/campaigns", json={"name": "Mail"}).json()
        refused = client.post(f"/api/v1/campaigns/{email['id']}/video-projects", json={})
        assert refused.status_code == 422
        assert "Email outreach" in refused.json()["detail"]


def test_the_presets_endpoint_names_what_a_project_may_declare(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        body = client.get("/api/v1/video/presets").json()
        assert body["ticks_per_second"] == TICKS_PER_SECOND
        assert {item["id"] for item in body["presets"]} >= {"vertical", "square", "landscape"}
        assert "30" in body["frame_rates"]
        assert "split_clip" in body["operations"]
