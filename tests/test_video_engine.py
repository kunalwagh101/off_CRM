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
            "source": "image",
            "media_type": "image/png",
            "width": 1024,
            "height": 1024,
            "duration_ticks": 0,
            "has_audio": False,
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


# ── assembly ────────────────────────────────────────────────────────────────


def test_an_assembled_project_is_renderable_with_nobody_touching_it(engine, assets):
    """Stage 5's acceptance criterion, written down before it was built: a topic
    goes to a finished, gate-passing video with zero manual timeline edits."""
    for index in range(4):
        assets.add(f"asset-{index}")
    state, report = engine.assemble(
        CAMPAIGN,
        recipe="hook_hold_payoff",
        target_ticks=15 * SECOND,
        asset_ids=[f"asset-{index}" for index in range(4)],
        lines=["Stop scrolling.", "Here is why.", "That is the point."],
    )
    manifest = engine.manifest(state.project.id)
    assert manifest["renderable"], manifest["warnings"]
    assert manifest["duration_ticks"] == 15 * SECOND
    assert manifest["frames"] == 450
    assert report.beats and len(report.beats) == 3


def test_an_assembly_is_stored_like_any_other_project_and_can_be_edited(engine, assets):
    """It is an ordinary document from the moment it exists. If it were not, the
    owner could not fix it — which is why the editor came before the assembler."""
    assets.add("asset-1")
    state, _ = engine.assemble(
        CAMPAIGN, recipe="quick_list", target_ticks=9 * SECOND, asset_ids=["asset-1"]
    )
    assert state.project.id in [item["id"] for item in engine.list_projects(CAMPAIGN)]
    clip = state.project.tracks[0].clips[0]
    after = engine.edit(state.project.id, "set_property", {"clip_id": clip.id, "name": "scale", "value": 1.3})
    assert after.can_undo


def test_an_assembly_uses_every_approved_picture_when_told_nothing(engine, assets, tmp_path):
    """The zero-input path: a recipe and a length, and it finds its own material."""
    for index in range(3):
        assets.add(f"asset-{index}")
    assets.add("rejected-one", status="rejected")
    engine.campaign_asset_reader = lambda cid: [
        row for row in assets.rows.values() if row["status"] == "approved"
    ]
    state, _ = engine.assemble(CAMPAIGN, recipe="three_points", target_ticks=20 * SECOND)
    used = {clip.asset_id for clip in state.project.tracks[0].clips}
    assert used == {"asset-0", "asset-1", "asset-2"}
    assert "rejected-one" not in used


def test_an_assembly_refuses_a_campaign_that_is_not_an_image_campaign(tmp_path):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    runner = VideoEditorEngine(
        store=store, campaign_reader=lambda cid: {"id": cid, "kind": "email"}
    )
    try:
        with pytest.raises(WrongCampaignKind):
            runner.assemble(CAMPAIGN, recipe="quick_list", target_ticks=9 * SECOND)
    finally:
        store.close()


def test_assembling_over_http_returns_the_beats_and_the_notes(tmp_path):
    """The half of the response worth reading: what it settled for."""
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as client:
        campaign = client.post(
            "/api/v1/campaigns", json={"name": "Assembly", "kind": "image"}
        ).json()
        catalogue = client.get("/api/v1/video/recipes").json()
        assert catalogue["recipes"], "the recipe space is served as data"

        response = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-projects/assemble",
            json={"recipe": "quick_list", "target_ticks": 9 * SECOND, "asset_ids": []},
        )
        # No pictures at all is a refusal with a sentence, not a stack trace.
        # 422 is what this API already maps a TimelineError to, and an
        # AssemblyRefused is one.
        assert response.status_code == 422
        assert "nothing to show" in str(response.json())


def test_a_topic_goes_all_the_way_to_a_renderable_project(engine, assets):
    """The whole loop in one call: the model picks the shape and writes the
    words, the assembler does the rest, and nobody touches a timeline."""
    for index in range(3):
        assets.add(f"asset-{index}")
    engine.director = lambda **kwargs: type(
        "R",
        (),
        {
            "text": '{"recipe": "three_points", "seconds": 20, '
            '"lines": ["First.", "Second.", "Third."], "rationale": "Listy topic."}',
            "provider_id": "nvidia",
            "model_id": "llama-3.1",
        },
    )()

    state, report, direction = engine.direct_and_assemble(
        CAMPAIGN, topic="three things nobody tells you about changelogs",
        asset_ids=[f"asset-{index}" for index in range(3)],
    )
    assert direction.recipe == "three_points"
    assert direction.model_id == "llama-3.1"
    assert engine.manifest(state.project.id)["renderable"]
    assert state.project.duration == 20 * SECOND
    assert len(report.beats) == 5
    # The name comes from the topic when nobody gave one.
    assert "changelogs" in state.project.name


def test_a_shape_the_model_invented_stops_before_a_clip_is_laid(engine, assets):
    """The refusal has to happen at the boundary, not halfway through building
    a document nobody can review."""
    assets.add("asset-1")
    engine.director = lambda **_: '{"recipe": "make_it_pop", "lines": [], "seconds": 15}'
    with pytest.raises(TimelineError, match="not a shape that exists"):
        engine.direct_and_assemble(CAMPAIGN, topic="anything", asset_ids=["asset-1"])
    assert engine.list_projects(CAMPAIGN) == [], "nothing was stored"


def test_directing_without_a_model_says_what_to_do_instead(engine, assets):
    assets.add("asset-1")
    with pytest.raises(TimelineError, match="without a model to ask"):
        engine.direct_and_assemble(CAMPAIGN, topic="anything", asset_ids=["asset-1"])


def test_the_model_s_notes_come_before_the_assembler_s(engine, assets):
    """An owner reading why a video looks like it does wants "it chose a
    montage" before "the music was short"."""
    assets.add("asset-1")
    engine.director = lambda **_: '{"recipe": "quick_list", "seconds": 900, "lines": []}'
    _, report, direction = engine.direct_and_assemble(
        CAMPAIGN, topic="anything", asset_ids=["asset-1"]
    )
    assert direction.notes, "600s is past the ceiling"
    assert report.notes[0] == direction.notes[0]


def test_a_pinned_length_reaches_the_director(engine, assets):
    assets.add("asset-1")
    engine.director = lambda **_: '{"recipe": "quick_list", "seconds": 90, "lines": []}'
    state, _, direction = engine.direct_and_assemble(
        CAMPAIGN, topic="anything", asset_ids=["asset-1"], target_ticks=12 * SECOND
    )
    assert direction.target_ticks == 12 * SECOND
    assert state.project.duration == 12 * SECOND


def test_directing_with_no_provider_connected_says_what_to_do(tmp_path):
    """The first thing anyone hits. The broker already carries the sentence;
    letting it out as a 500 would replace it with a stack trace."""
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as client:
        campaign = client.post(
            "/api/v1/campaigns", json={"name": "Loop", "kind": "image"}
        ).json()
        response = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-projects/direct",
            json={"topic": "why nobody reads changelogs"},
        )
        assert response.status_code == 409
        assert "no_permitted_provider" in str(response.json())
        assert "Connectors" in str(response.json())


# ── what the export should sound like ───────────────────────────────────────


def _with_music(engine, assets, *, duration: int = 3 * SECOND, volume: float | None = None) -> str:
    """A still with a music bed under it."""
    state = _project(engine)
    project_id = state.project.id
    assets.add("asset-1")
    engine.place_asset(project_id, asset_id="asset-1", duration=duration)
    engine.edit(
        project_id,
        "add_clip",
        {
            "track_id": state.project.tracks[1].id,
            "kind": "audio",
            "start": 0,
            "duration": duration,
            "asset_id": "media-1",
            "source_duration": 30 * SECOND,
        },
    )
    if volume is not None:
        clip = engine.open_project(project_id).project.tracks[1].clips[0]
        engine.edit(
            project_id, "set_property", {"clip_id": clip.id, "name": "volume", "value": volume}
        )
    return project_id


def test_the_manifest_says_what_the_export_should_sound_like(engine, assets):
    """The browser mixes the audio, so the server states the answer it should
    arrive at — the same arrangement as the frame resolver."""
    mix = engine.manifest(_with_music(engine, assets))["mix"]
    assert mix["silent"] is False
    assert mix["asset_ids"] == ["media-1"]
    assert mix["sample_rate"] == 48_000
    assert mix["clips"][0]["envelope"] == [[0, 1.0], [3 * SECOND, 1.0]]


def test_the_manifest_says_when_a_project_would_export_silent(engine, assets):
    """A note rather than a warning: a silent video is a bad idea, not an
    impossible one, and ``renderable`` is what decides whether the button works."""
    state = _project(engine)
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1")
    manifest = engine.manifest(state.project.id)
    assert manifest["mix"]["silent"] is True
    assert "will be silent" in manifest["mix"]["notes"][0]
    assert manifest["renderable"], "a silent timeline still exports"


def test_the_manifest_warns_before_the_render_that_a_mix_would_clip(engine, assets):
    project_id = _with_music(engine, assets)
    engine.edit(project_id, "add_track", {"kind": "audio", "name": "Voice"})
    engine.edit(
        project_id,
        "add_clip",
        {
            "track_id": engine.open_project(project_id).project.tracks[-1].id,
            "kind": "audio",
            "start": 0,
            "duration": SECOND,
            "asset_id": "media-2",
            "source_duration": SECOND,
        },
    )
    mix = engine.manifest(project_id)["mix"]
    assert mix["headroom"] == pytest.approx(2.0)
    assert any("distort" in note for note in mix["notes"])


def test_the_manifest_says_which_clips_will_play_without_their_sound(engine, assets):
    """A retimed clip is silent on purpose, and "on purpose" has to be visible
    before the render rather than discovered in the file."""
    project_id = _with_music(engine, assets)
    engine.edit(
        project_id,
        "add_clip",
        {
            "track_id": engine.open_project(project_id).project.tracks[0].id,
            "kind": "video",
            "start": 4 * SECOND,
            "duration": 3 * SECOND,
            "asset_id": "media-2",
            "source_duration": 30 * SECOND,
        },
    )
    clip = engine.open_project(project_id).project.tracks[0].clips[-1]
    engine.edit(project_id, "apply_speed_curve", {"clip_id": clip.id, "preset": "hero"})

    mix = engine.manifest(project_id)["mix"]
    assert mix["excluded"] == [[clip.id, "its speed changes over its own length"]]
    assert any("without its sound" in note for note in mix["notes"])
    assert clip.id not in [item["clip_id"] for item in mix["clips"]]


def test_a_project_that_makes_a_sound_must_come_back_with_one(engine, assets):
    """The export gate's other half. ``muxed_sample.webm`` has no audio track and
    this timeline says it should — which is exactly the file a browser that could
    not encode Opus hands back, looking entirely finished."""
    result = engine.store_render(_with_music(engine, assets), MUXED.read_bytes())
    assert not result["passed"]
    assert "has_audio_track" in result["summary"]


def test_a_project_whose_sound_is_turned_all_the_way_down_is_not_asked_for_one(engine, assets):
    """The planner and the gate have to agree: a clip below silence is not in the
    mix, so the file is not required to carry it."""
    project_id = _with_music(engine, assets, volume=0.0)
    assert engine.manifest(project_id)["mix"]["silent"] is True
    result = engine.store_render(project_id, MUXED.read_bytes())
    assert result["passed"], result["summary"]


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
