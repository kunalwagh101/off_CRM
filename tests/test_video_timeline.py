"""The timeline document and the edits that can be made to it.

The editor's core, and the part where being wrong is invisible until export. So
the tests are mostly about invariants rather than features:

- a track cannot show two things at once
- an edit either applies completely or leaves the document untouched
- a split is transparent — the resolved animation is identical either side of it
- keyframes travel with the material, not with the timeline
- the resolver Python runs and the resolver the browser runs give one answer

That last one is the conformance fixture, which is the only defence against a
preview that quietly stops matching its own export.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.video import edits
from offsetx_apollo_builder.video.timeline import (
    MIN_CLIP_TICKS,
    TICKS_PER_SECOND,
    ClipOverlap,
    Keyframe,
    Project,
    TimelineError,
    TrackLocked,
    frame_at,
    interpolate,
    new_project,
    seconds_to_ticks,
    snap_to_frame,
    ticks_per_frame,
)

FIXTURE = Path(__file__).parent / "fixtures" / "timeline_conformance.json"
SECOND = TICKS_PER_SECOND


@pytest.fixture()
def project() -> Project:
    """One video track, one audio track, one five-second still."""
    document = new_project(name="Test", preset="vertical", fps="30")
    return edits.add_clip(
        document,
        track_id=document.tracks[0].id,
        kind="image",
        start=0,
        duration=5 * SECOND,
        asset_id="asset-1",
    )


def only_clip(document: Project):
    return document.tracks[0].clips[0]


# ── time ────────────────────────────────────────────────────────────────────


def test_every_frame_rate_offered_divides_the_tick_rate_evenly_or_nearly():
    """The reason for 90kHz. A rate whose frames are not whole ticks means every
    cut lands between two representable instants."""
    for fps in ("24", "25", "30", "50", "60"):
        assert ticks_per_frame(fps) == int(ticks_per_frame(fps))
    # The 1001-denominator rates are exact at 29.97 and handled by snapping at
    # the others, which is the honest position rather than a claim of exactness.
    assert ticks_per_frame("29.97") == pytest.approx(3003)


def test_an_unknown_frame_rate_is_refused_rather_than_rounded():
    with pytest.raises(TimelineError, match="Unsupported frame rate"):
        new_project(fps="48")


def test_snapping_lands_on_a_frame_boundary():
    assert snap_to_frame(3100, "30") == 3000
    assert snap_to_frame(4600, "30") == 6000
    assert snap_to_frame(0, "30") == 0


def test_seconds_round_rather_than_truncate():
    """Truncation always shortens, so a clip built from seconds would come out
    a tick short every time."""
    assert seconds_to_ticks(1.0) == SECOND
    assert seconds_to_ticks(0.9999999) == SECOND


# ── invariants ──────────────────────────────────────────────────────────────


def test_two_clips_cannot_claim_the_same_tick_on_one_track(project):
    with pytest.raises(ClipOverlap):
        edits.add_clip(
            project,
            track_id=project.tracks[0].id,
            kind="image",
            start=2 * SECOND,
            duration=2 * SECOND,
        )


def test_the_same_two_clips_are_fine_on_different_tracks(project):
    document = edits.add_track(project, kind="video", name="Overlay")
    document = edits.add_clip(
        document,
        track_id=document.tracks[-1].id,
        kind="image",
        start=2 * SECOND,
        duration=2 * SECOND,
    )
    assert len(frame_at(document, 3 * SECOND).items) == 2


def test_a_refused_edit_leaves_the_document_exactly_as_it_was(project):
    before = project.to_dict()
    with pytest.raises(ClipOverlap):
        edits.add_clip(
            project, track_id=project.tracks[0].id, kind="image", start=0, duration=SECOND
        )
    assert project.to_dict() == before


def test_a_locked_track_refuses_edits_but_can_still_be_unlocked(project):
    locked = edits.set_track(project, track_id=project.tracks[0].id, locked=True)
    with pytest.raises(TrackLocked):
        edits.remove_clip(locked, clip_id=only_clip(locked).id)
    unlocked = edits.set_track(locked, track_id=locked.tracks[0].id, locked=False)
    assert edits.remove_clip(unlocked, clip_id=only_clip(unlocked).id).tracks[0].clips == []


def test_an_audio_clip_cannot_go_on_a_video_track(project):
    with pytest.raises(TimelineError, match="cannot go on"):
        edits.add_clip(
            project,
            track_id=project.tracks[0].id,
            kind="audio",
            start=6 * SECOND,
            duration=SECOND,
            source_duration=SECOND,
        )


def test_a_video_clip_must_declare_how_long_its_material_is(project):
    """Without it nothing can stop an edit reading past the end of the file."""
    with pytest.raises(TimelineError, match="source_duration"):
        edits.add_clip(
            project,
            track_id=project.tracks[0].id,
            kind="video",
            start=6 * SECOND,
            duration=SECOND,
            asset_id="clip-1",
        )


def test_a_clip_cannot_read_past_the_end_of_its_material(project):
    with pytest.raises(TimelineError, match="past the end of its source"):
        edits.add_clip(
            project,
            track_id=project.tracks[0].id,
            kind="video",
            start=6 * SECOND,
            duration=4 * SECOND,
            in_point=SECOND,
            source_duration=3 * SECOND,
            asset_id="clip-1",
        )


def test_a_clip_shorter_than_one_frame_is_refused(project):
    with pytest.raises(TimelineError, match="at least"):
        edits.add_clip(
            project,
            track_id=project.tracks[0].id,
            kind="image",
            start=6 * SECOND,
            duration=MIN_CLIP_TICKS - 1,
        )


def test_fades_longer_than_their_clip_are_refused(project):
    with pytest.raises(TimelineError, match="longer than the clip"):
        edits.set_fade(project, clip_id=only_clip(project).id, fade_in=4 * SECOND, fade_out=4 * SECOND)


def test_an_unknown_property_is_refused_rather_than_quietly_created(project):
    """A typo that created a new property would animate nothing and report
    success."""
    with pytest.raises(TimelineError, match="Unknown property"):
        edits.set_property(project, clip_id=only_clip(project).id, name="scael", value=2.0)


def test_an_unknown_edit_is_refused(project):
    with pytest.raises(TimelineError, match="Unknown edit"):
        edits.apply(project, "make_it_pop", {})


def test_a_missing_parameter_is_a_refusal_not_a_crash(project):
    with pytest.raises(TimelineError, match="add_clip"):
        edits.apply(project, "add_clip", {"track_id": project.tracks[0].id})


# ── the operations ──────────────────────────────────────────────────────────


def test_a_split_is_transparent_to_the_resolver(project):
    """The strongest property a split can have: cutting a clip changes nothing
    about what is on screen at any instant."""
    clip = only_clip(project).id
    animated = edits.add_keyframe(project, clip_id=clip, name="scale", at=0, value=1.0)
    animated = edits.add_keyframe(
        animated, clip_id=clip, name="scale", at=5 * SECOND, value=1.4, easing="ease_in_out"
    )
    ticks = range(0, 5 * SECOND, SECOND // 6)
    before = [frame_at(animated, tick).to_dict() for tick in ticks]
    after_split = edits.split_clip(animated, clip_id=clip, at=2 * SECOND)
    after = [frame_at(after_split, tick).to_dict() for tick in ticks]

    for one, two in zip(before, after):
        assert len(one["items"]) == len(two["items"])
        for left, right in zip(one["items"], two["items"]):
            assert left["properties"] == right["properties"]
            assert left["opacity"] == right["opacity"]


def test_a_split_is_transparent_through_a_non_linear_ease(project):
    """The case the linear test above cannot see.

    A sub-range of an ease-out curve is not itself an ease-out curve, so an
    earlier implementation that synthesised boundary keyframes and re-eased the
    halves changed the animation's shape between the samples. It passed the test
    above because that one happens to use a linear segment; splitting mid-ease
    visibly altered the zoom.
    """
    clip = only_clip(project).id
    for easing in ("ease_in", "ease_out", "ease_in_out"):
        animated = edits.add_keyframe(
            project, clip_id=clip, name="scale", at=0, value=0.5, easing=easing
        )
        animated = edits.add_keyframe(
            animated, clip_id=clip, name="scale", at=4 * SECOND, value=2.0
        )
        ticks = range(0, 5 * SECOND, SECOND // 12)
        before = [round(frame_at(animated, tick).items[0].properties["scale"], 9) for tick in ticks]
        for cut in (SECOND, 2 * SECOND, 3 * SECOND):
            split = edits.split_clip(animated, clip_id=clip, at=cut)
            after = [round(frame_at(split, tick).items[0].properties["scale"], 9) for tick in ticks]
            assert before == after, f"{easing} split at {cut}"


def test_a_trim_is_transparent_through_a_non_linear_ease(project):
    """Same property, the other operation that re-bases keyframes."""
    clip = only_clip(project).id
    animated = edits.add_keyframe(
        project, clip_id=clip, name="scale", at=0, value=0.5, easing="ease_out"
    )
    animated = edits.add_keyframe(animated, clip_id=clip, name="scale", at=4 * SECOND, value=2.0)
    trimmed = edits.trim_clip(animated, clip_id=clip, head=SECOND)
    for tick in range(SECOND, 5 * SECOND, SECOND // 12):
        original = frame_at(animated, tick).items[0].properties["scale"]
        moved = frame_at(trimmed, tick).items[0].properties["scale"]
        assert round(original, 9) == round(moved, 9), tick


def test_splitting_repeatedly_does_not_grow_the_keyframes(project):
    """Exactness must not cost an ever-growing document."""
    clip = only_clip(project).id
    animated = edits.add_keyframe(project, clip_id=clip, name="scale", at=0, value=1.0)
    animated = edits.add_keyframe(animated, clip_id=clip, name="scale", at=4 * SECOND, value=2.0)
    working = animated
    target = clip
    for cut in (SECOND, 2 * SECOND, 3 * SECOND):
        working = edits.split_clip(working, clip_id=target, at=cut)
        target = sorted(working.tracks[0].clips, key=lambda item: item.start)[-1].id
    for piece in working.tracks[0].clips:
        assert len(piece.keyframes.get("scale", [])) <= 3


def test_a_split_moves_the_second_half_of_the_material_with_it(project):
    """Wrong at 1x is invisible; wrong on a slowed clip is obvious."""
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="video",
        start=5 * SECOND,
        duration=4 * SECOND,
        in_point=SECOND,
        source_duration=20 * SECOND,
        speed=0.5,
        asset_id="clip-1",
    )
    clip = document.tracks[0].clips[1].id
    split = edits.split_clip(document, clip_id=clip, at=7 * SECOND)
    right = split.tracks[0].clips[2]
    # Two seconds of timeline at half speed consumed one second of material.
    assert right.in_point == SECOND + SECOND


def test_a_split_at_a_point_outside_the_clip_is_refused(project):
    with pytest.raises(TimelineError, match="nothing there to cut"):
        edits.split_clip(project, clip_id=only_clip(project).id, at=9 * SECOND)


def test_the_two_halves_of_a_split_do_not_share_their_properties(project):
    clip = only_clip(project).id
    split = edits.split_clip(project, clip_id=clip, at=2 * SECOND)
    left, right = split.tracks[0].clips
    changed = edits.set_property(split, clip_id=left.id, name="scale", value=2.0)
    assert changed.tracks[0].clips[0].properties["scale"] == 2.0
    assert "scale" not in changed.tracks[0].clips[1].properties


def test_trimming_the_head_moves_the_read_point_and_not_the_material(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="video",
        start=5 * SECOND,
        duration=4 * SECOND,
        source_duration=20 * SECOND,
        asset_id="clip-1",
    )
    clip = document.tracks[0].clips[1].id
    trimmed = edits.trim_clip(document, clip_id=clip, head=SECOND)
    after = trimmed.tracks[0].clips[1]
    assert after.start == 6 * SECOND
    assert after.duration == 3 * SECOND
    assert after.in_point == SECOND


def test_trimming_the_head_carries_the_animation_with_the_material(project):
    clip = only_clip(project).id
    document = edits.add_keyframe(project, clip_id=clip, name="scale", at=0, value=1.0)
    document = edits.add_keyframe(document, clip_id=clip, name="scale", at=5 * SECOND, value=2.0)
    before = frame_at(document, SECOND).items[0].properties["scale"]
    trimmed = edits.trim_clip(document, clip_id=clip, head=SECOND)
    # The clip now starts at one second, and its first frame is what its second
    # second used to be.
    assert frame_at(trimmed, SECOND).items[0].properties["scale"] == pytest.approx(before)


def test_ripple_delete_closes_the_gap_on_its_own_track_only(project):
    document = edits.add_clip(
        project, track_id=project.tracks[0].id, kind="image", start=5 * SECOND, duration=2 * SECOND
    )
    document = edits.add_clip(
        document,
        track_id=project.tracks[1].id,
        kind="audio",
        start=5 * SECOND,
        duration=2 * SECOND,
        source_duration=10 * SECOND,
        asset_id="music",
    )
    rippled = edits.ripple_delete(document, clip_id=only_clip(document).id)
    assert rippled.tracks[0].clips[0].start == 0
    # The audio did not ask to move. Rippling it would desynchronise a
    # voiceover from the pictures it was cut against.
    assert rippled.tracks[1].clips[0].start == 5 * SECOND


def test_plain_delete_leaves_the_gap(project):
    document = edits.add_clip(
        project, track_id=project.tracks[0].id, kind="image", start=5 * SECOND, duration=2 * SECOND
    )
    deleted = edits.remove_clip(document, clip_id=only_clip(document).id)
    assert deleted.tracks[0].clips[0].start == 5 * SECOND


def test_inserting_a_gap_in_the_middle_of_a_clip_is_refused(project):
    with pytest.raises(TimelineError, match="Split it first"):
        edits.insert_gap(project, track_id=project.tracks[0].id, at=2 * SECOND, duration=SECOND)


def test_speeding_a_clip_up_shortens_it_and_keeps_its_material(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="video",
        start=5 * SECOND,
        duration=4 * SECOND,
        source_duration=20 * SECOND,
        asset_id="clip-1",
    )
    clip = document.tracks[0].clips[1].id
    faster = edits.set_speed(document, clip_id=clip, speed=2.0)
    assert faster.tracks[0].clips[1].duration == 2 * SECOND
    # Same four seconds of material, played in two.
    assert frame_at(faster, 7 * SECOND - 1).items[0].source_time == pytest.approx(
        4 * SECOND, abs=4
    )


def test_keeping_the_duration_changes_how_much_material_is_used(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="video",
        start=5 * SECOND,
        duration=4 * SECOND,
        source_duration=20 * SECOND,
        asset_id="clip-1",
    )
    clip = document.tracks[0].clips[1].id
    faster = edits.set_speed(document, clip_id=clip, speed=2.0, keep_duration=True)
    assert faster.tracks[0].clips[1].duration == 4 * SECOND


def test_moving_a_clip_to_another_track_takes_it_off_the_first(project):
    document = edits.add_track(project, kind="video", name="Overlay")
    clip = only_clip(document).id
    moved = edits.move_clip(document, clip_id=clip, start=0, track_id=document.tracks[-1].id)
    assert moved.tracks[0].clips == []
    assert moved.tracks[-1].clips[0].id == clip


def test_a_project_keeps_at_least_one_track(project):
    document = edits.remove_track(project, track_id=project.tracks[1].id)
    with pytest.raises(TimelineError, match="at least one track"):
        edits.remove_track(document, track_id=document.tracks[0].id)


def test_reordering_tracks_reorders_what_draws_on_top(project):
    document = edits.add_track(project, kind="video", name="Overlay")
    document = edits.add_clip(
        document, track_id=document.tracks[-1].id, kind="solid", start=0, duration=SECOND
    )
    top_first = frame_at(document, 0).items[-1].kind
    swapped = edits.move_track(document, track_id=document.tracks[-1].id, index=0)
    assert top_first == "solid"
    assert frame_at(swapped, 0).items[-1].kind == "image"


def test_an_unknown_canvas_preset_is_refused(project):
    with pytest.raises(TimelineError, match="Unknown canvas preset"):
        edits.set_canvas(project, preset="cinemascope")


def test_changing_the_canvas_does_not_move_anything_on_the_timeline(project):
    resized = edits.set_canvas(project, preset="landscape")
    assert (resized.width, resized.height) == (1920, 1080)
    assert resized.tracks[0].clips[0].to_dict() == project.tracks[0].clips[0].to_dict()


# ── the resolver ────────────────────────────────────────────────────────────


def test_a_cut_is_not_a_one_frame_overlap(project):
    """Half-open intervals. A clip ending where the next begins is the ordinary
    result of a split, and both being live at the shared tick would double every
    cut in every project."""
    split = edits.split_clip(project, clip_id=only_clip(project).id, at=2 * SECOND)
    at_the_cut = frame_at(split, 2 * SECOND)
    assert len(at_the_cut.items) == 1
    assert at_the_cut.items[0].clip_id == split.tracks[0].clips[1].id


def test_nothing_is_live_one_tick_past_the_end(project):
    assert frame_at(project, 5 * SECOND - 1).items
    assert frame_at(project, 5 * SECOND).items == []


def test_interpolation_holds_outside_its_keyframes():
    frames = [Keyframe(at=1000, value=2.0), Keyframe(at=3000, value=6.0)]
    assert interpolate(frames, 0) == 2.0
    assert interpolate(frames, 2000) == 4.0
    assert interpolate(frames, 99999) == 6.0


def test_hold_easing_is_a_step_not_a_ramp():
    frames = [Keyframe(at=0, value=0.0, easing="hold"), Keyframe(at=100, value=1.0)]
    assert interpolate(frames, 99) == 0.0
    assert interpolate(frames, 100) == 1.0


def test_a_keyframe_outside_its_clip_is_refused(project):
    with pytest.raises(TimelineError, match="past the end of a clip"):
        edits.add_keyframe(
            project, clip_id=only_clip(project).id, name="scale", at=9 * SECOND, value=2.0
        )


def test_a_second_keyframe_at_one_instant_replaces_the_first(project):
    clip = only_clip(project).id
    document = edits.add_keyframe(project, clip_id=clip, name="scale", at=0, value=1.0)
    document = edits.add_keyframe(document, clip_id=clip, name="scale", at=0, value=2.0)
    assert document.tracks[0].clips[0].keyframes["scale"] == [Keyframe(at=0, value=2.0)]


def test_a_hidden_track_loses_its_picture_and_keeps_its_sound(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[1].id,
        kind="audio",
        start=0,
        duration=2 * SECOND,
        source_duration=10 * SECOND,
        asset_id="music",
    )
    hidden = edits.set_track(document, track_id=document.tracks[0].id, hidden=True)
    frame = frame_at(hidden, SECOND)
    picture = next(item for item in frame.items if item.kind == "image")
    sound = next(item for item in frame.items if item.kind == "audio")
    assert picture.opacity == 0.0
    assert sound.gain == 1.0


def test_muting_a_track_silences_it_without_hiding_it(project):
    muted = edits.set_track(project, track_id=project.tracks[0].id, muted=True)
    item = frame_at(muted, SECOND).items[0]
    assert item.gain == 0.0
    assert item.opacity == 1.0


def test_fades_reach_zero_at_the_edges_and_full_in_between(project):
    faded = edits.set_fade(
        project, clip_id=only_clip(project).id, fade_in=SECOND, fade_out=SECOND
    )
    assert frame_at(faded, 0).items[0].opacity == 0.0
    assert frame_at(faded, SECOND).items[0].opacity == 1.0
    assert frame_at(faded, 5 * SECOND - 1).items[0].opacity < 0.01


def test_the_document_survives_a_round_trip_through_json(project):
    document = edits.add_keyframe(
        project, clip_id=only_clip(project).id, name="x", at=0, value=-100.0, easing="ease_out"
    )
    document = edits.add_marker(document, at=SECOND, label="hook")
    again = Project.from_dict(json.loads(json.dumps(document.to_dict())))
    assert again.to_dict() == document.to_dict()


def test_a_document_from_a_newer_build_is_refused_rather_than_half_read(project):
    raw = project.to_dict()
    raw["version"] = 99
    with pytest.raises(TimelineError, match="newer version"):
        Project.from_dict(raw)


def test_the_assets_a_project_needs_are_listed_once_each_in_order(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="image",
        start=6 * SECOND,
        duration=SECOND,
        asset_id="asset-1",
    )
    document = edits.add_clip(
        document,
        track_id=project.tracks[0].id,
        kind="image",
        start=8 * SECOND,
        duration=SECOND,
        asset_id="asset-2",
    )
    assert document.asset_ids() == ["asset-1", "asset-2"]


# ── conformance with the browser ────────────────────────────────────────────


def test_the_conformance_fixture_still_describes_this_resolver():
    """The other half of ``frontend/src/video/resolve.test.ts``.

    Both suites assert against this one file, so whichever resolver moves, a
    test goes red. Regenerate it deliberately with
    ``python scripts/build_timeline_fixture.py`` and read the diff — a change
    here is a change to how every existing project plays back.
    """
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document = Project.from_dict(payload["document"])
    assert payload["ticks_per_second"] == TICKS_PER_SECOND
    assert len(payload["frames"]) >= 10
    for expected in payload["frames"]:
        assert frame_at(document, expected["tick"]).to_dict() == expected


def test_the_conformance_document_exercises_the_awkward_cases():
    """A fixture of one clip on one track would pass whatever either side did."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document = Project.from_dict(payload["document"])
    kinds = {clip.kind for track in document.tracks for clip in track.clips}
    easings = {
        frame.easing
        for track in document.tracks
        for clip in track.clips
        for frames in clip.keyframes.values()
        for frame in frames
    }
    assert {"image", "video", "text", "solid", "audio"} <= kinds
    assert len(easings) >= 4
    assert any(track.hidden for track in document.tracks)
    assert any(clip.speed != 1.0 for track in document.tracks for clip in track.clips)
