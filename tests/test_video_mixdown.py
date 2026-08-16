"""The gain envelope the exporter hands to the browser.

Everything off_CRM has exported so far is silent, and this is the arithmetic
that stops being true. The interesting property is not "does it produce an
envelope" — it is that the envelope is *the same curve the preview plays*, and
that it says so in as few points as it honestly can.

So the tests are mostly two questions:

- does the envelope, read back, agree with the resolver at arbitrary instants
- and is it as short as the shape allows, because a hundred points describing a
  straight line is a hundred chances to be slightly wrong in a browser
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.video import edits, mixdown
from offsetx_apollo_builder.video.timeline import (
    TICKS_PER_SECOND,
    Project,
    clip_gain,
    frame_at,
    new_project,
)

SECOND = TICKS_PER_SECOND
FIXTURE = Path(__file__).parent / "fixtures" / "timeline_conformance.json"


@pytest.fixture()
def project() -> Project:
    """One video track, one audio track, and five seconds of music."""
    document = new_project(name="Mix", preset="vertical", fps="30")
    return edits.add_clip(
        document,
        track_id=document.tracks[1].id,
        kind="audio",
        start=0,
        duration=5 * SECOND,
        asset_id="music-1",
        source_duration=30 * SECOND,
    )


def audio_track(document: Project):
    return document.tracks[1]


def only_audio(document: Project):
    return document.tracks[1].clips[0]


# ── the shape ───────────────────────────────────────────────────────────────


def test_a_clip_at_a_constant_volume_is_two_points(project):
    """The whole point of an envelope: a flat gain does not need a grid."""
    envelope = mixdown.envelope_for(audio_track(project), only_audio(project))
    assert envelope == [(0, 1.0), (5 * SECOND, 1.0)]


def test_a_linear_fade_is_still_only_its_corners(project):
    """A fade over a flat volume is a straight line, and a straight line has two
    ends. Sampled at 100Hz it is a hundred points; kept, it is three."""
    document = edits.set_fade(project, clip_id=only_audio(project).id, fade_in=SECOND)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    assert envelope == [(0, 0.0), (SECOND, 1.0), (5 * SECOND, 1.0)]


def test_a_fade_out_reaches_exactly_zero_at_the_cut(project):
    """Read one tick early it would end at a hundredth of full volume, and the
    listener would hear the tail chopped rather than faded."""
    document = edits.set_fade(project, clip_id=only_audio(project).id, fade_out=SECOND)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    assert envelope[-1] == (5 * SECOND, 0.0)
    assert envelope[-2] == (4 * SECOND, 1.0)


def test_linear_volume_keyframes_keep_one_point_each_and_no_more(project):
    clip = only_audio(project)
    document = edits.add_keyframe(project, clip_id=clip.id, name="volume", at=0, value=0.2)
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=2 * SECOND, value=1.0)
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=5 * SECOND, value=0.5)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    assert envelope == [(0, 0.2), (2 * SECOND, 1.0), (5 * SECOND, 0.5)]


def test_an_eased_ramp_is_sampled_because_it_is_not_a_line(project):
    clip = only_audio(project)
    document = edits.add_keyframe(
        project, clip_id=clip.id, name="volume", at=0, value=0.0, easing="ease_in_out"
    )
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=2 * SECOND, value=1.0)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    curved = [point for point in envelope if 0 < point[0] < 2 * SECOND]
    assert curved, "an ease with no intermediate points is a straight line"
    # It still has to be a summary rather than the raw grid.
    assert len(envelope) < 2 * SECOND // mixdown.ENVELOPE_STEP


def test_a_fade_over_a_ramp_is_sampled_because_the_product_curves(project):
    """Linear times linear is a parabola. The one case where a fade genuinely
    needs more than its corners."""
    clip = only_audio(project)
    document = edits.add_keyframe(project, clip_id=clip.id, name="volume", at=0, value=0.0)
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=5 * SECOND, value=1.0)
    document = edits.set_fade(document, clip_id=clip.id, fade_in=2 * SECOND)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    inside = [point for point in envelope if 0 < point[0] < 2 * SECOND]
    assert len(inside) >= 2, "a parabola cannot be two points"


def test_an_eased_hold_between_two_equal_values_is_not_sampled(project):
    """Nothing moves, so however it is eased there is no curve to describe."""
    clip = only_audio(project)
    document = edits.add_keyframe(
        project, clip_id=clip.id, name="volume", at=0, value=0.8, easing="ease_in"
    )
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=3 * SECOND, value=0.8)
    envelope = mixdown.envelope_for(audio_track(document), only_audio(document))
    assert envelope == [(0, 0.8), (5 * SECOND, 0.8)]


# ── it has to agree with what the preview plays ─────────────────────────────


@pytest.mark.parametrize("easing", ["linear", "ease_in", "ease_out", "ease_in_out"])
def test_the_envelope_matches_the_resolver_all_the_way_along(project, easing):
    """The property that matters. Read the envelope back the way WebAudio will
    read it and compare against the same resolver the preview uses."""
    clip = only_audio(project)
    document = edits.add_keyframe(
        project, clip_id=clip.id, name="volume", at=0, value=0.1, easing=easing
    )
    document = edits.add_keyframe(
        document, clip_id=clip.id, name="volume", at=3 * SECOND, value=1.4, easing="linear"
    )
    document = edits.set_fade(document, clip_id=clip.id, fade_in=SECOND, fade_out=SECOND)

    track, resolved = audio_track(document), only_audio(document)
    envelope = mixdown.envelope_for(track, resolved)
    item = mixdown.MixClip(
        clip_id=resolved.id,
        asset_id=resolved.asset_id,
        kind=resolved.kind,
        start=resolved.start,
        duration=resolved.duration,
        in_point=resolved.in_point,
        speed=resolved.speed,
        envelope=envelope,
    )
    for at in range(0, resolved.duration + 1, SECOND // 20):
        truth = clip_gain(track, resolved, at)
        assert item.gain_at(at) == pytest.approx(truth, abs=2e-3), f"drifted at {at}"


def test_the_envelope_agrees_with_the_frame_the_preview_draws(project):
    """One step further out: not the gain helper, the whole resolver."""
    clip = only_audio(project)
    document = edits.set_fade(project, clip_id=clip.id, fade_in=SECOND, fade_out=2 * SECOND)
    plan = mixdown.plan(document)
    item = plan.clips[0]
    for tick in range(0, document.duration, SECOND // 10):
        drawn = next(
            entry for entry in frame_at(document, tick).items if entry.clip_id == item.clip_id
        )
        assert item.gain_at(tick - item.start) == pytest.approx(drawn.gain, abs=2e-3)


# ── what goes in the plan and what does not ─────────────────────────────────


def test_a_muted_track_contributes_nothing(project):
    document = edits.set_track(project, track_id=audio_track(project).id, muted=True)
    assert mixdown.plan(document).silent
    assert mixdown.plan(document).asset_ids == []


def test_a_clip_held_at_zero_volume_is_dropped_rather_than_decoded(project):
    document = edits.set_property(project, clip_id=only_audio(project).id, name="volume", value=0.0)
    assert mixdown.plan(document).silent


def test_a_still_makes_no_sound_however_loud_you_set_it(project):
    """A picture clip has a volume property like everything else, and it has to
    stay meaningless — otherwise the mixer tries to decode a PNG."""
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="image",
        start=0,
        duration=3 * SECOND,
        asset_id="still-1",
    )
    document = edits.set_property(
        document, clip_id=document.tracks[0].clips[0].id, name="volume", value=4.0
    )
    plan = mixdown.plan(document)
    assert [item.asset_id for item in plan.clips] == ["music-1"]


def test_footage_on_a_video_track_is_in_the_mix(project):
    """The reason `audible_clips` looks at video tracks at all: a clip's sound
    lives inside the same file as its picture, and the picture being unfinished
    is no reason to export it silent."""
    document = edits.add_clip(
        project,
        track_id=project.tracks[0].id,
        kind="video",
        start=0,
        duration=3 * SECOND,
        asset_id="footage-1",
        source_duration=10 * SECOND,
    )
    plan = mixdown.plan(document)
    assert sorted(plan.asset_ids) == ["footage-1", "music-1"]
    assert {item.kind for item in plan.clips} == {"audio", "video"}


def test_a_clip_with_no_asset_is_not_something_to_fetch(project):
    document = edits.add_clip(
        project,
        track_id=audio_track(project).id,
        kind="audio",
        start=6 * SECOND,
        duration=SECOND,
        source_duration=SECOND,
    )
    assert mixdown.plan(document).asset_ids == ["music-1"]


def test_one_asset_used_twice_is_fetched_once(project):
    document = edits.duplicate_clip(project, clip_id=only_audio(project).id, start=6 * SECOND)
    plan = mixdown.plan(document)
    assert len(plan.clips) == 2
    assert plan.asset_ids == ["music-1"]


def test_the_plan_carries_the_read_point_and_the_speed(project):
    """Without these the browser plays the right file from the wrong place."""
    document = edits.trim_clip(project, clip_id=only_audio(project).id, head=SECOND)
    document = edits.set_speed(document, clip_id=only_audio(document).id, speed=2.0)
    item = mixdown.plan(document).clips[0]
    assert item.in_point == SECOND
    assert item.speed == 2.0


def test_the_clips_come_out_in_the_order_they_are_heard(project):
    document = edits.duplicate_clip(project, clip_id=only_audio(project).id, start=20 * SECOND)
    document = edits.duplicate_clip(document, clip_id=only_audio(document).id, start=10 * SECOND)
    starts = [item.start for item in mixdown.plan(document).clips]
    assert starts == sorted(starts)


def test_a_project_with_no_sound_is_silent_not_empty(project):
    """A slideshow with no music is a real export, and the muxer needs to be
    told to leave the audio track out rather than write an empty one."""
    document = new_project(name="Slides")
    document = edits.add_clip(
        document,
        track_id=document.tracks[0].id,
        kind="image",
        start=0,
        duration=2 * SECOND,
        asset_id="still-1",
    )
    plan = mixdown.plan(document)
    assert plan.silent
    assert plan.to_dict()["silent"] is True


# ── clipping ────────────────────────────────────────────────────────────────


def test_one_clip_at_full_volume_has_no_clipping(project):
    assert mixdown.headroom(mixdown.plan(project)) == pytest.approx(1.0)


def test_two_clips_at_once_sum_and_the_plan_says_so(project):
    document = edits.add_track(project, kind="audio", name="Voice")
    document = edits.add_clip(
        document,
        track_id=document.tracks[-1].id,
        kind="audio",
        start=SECOND,
        duration=SECOND,
        asset_id="voice-1",
        source_duration=SECOND,
    )
    assert mixdown.headroom(mixdown.plan(document)) == pytest.approx(2.0)
    assert mixdown.plan(document).to_dict()["headroom"] == pytest.approx(2.0)


def test_a_crossfade_is_measured_in_its_middle_and_not_at_its_edges(project):
    """The reason headroom looks at envelope points rather than clip boundaries:
    two clips fading through each other are loudest where neither starts nor
    ends."""
    document = edits.set_fade(project, clip_id=only_audio(project).id, fade_out=2 * SECOND)
    document = edits.add_track(document, kind="audio", name="Second")
    document = edits.add_clip(
        document,
        track_id=document.tracks[-1].id,
        kind="audio",
        start=3 * SECOND,
        duration=4 * SECOND,
        asset_id="music-2",
        source_duration=30 * SECOND,
    )
    document = edits.set_fade(
        document, clip_id=document.tracks[-1].clips[0].id, fade_in=2 * SECOND
    )
    peak = mixdown.headroom(mixdown.plan(document))
    # An equal-power crossfade would hold 1.0; these are equal-gain, so the two
    # linear ramps cross at half each and sum back to exactly one.
    assert peak == pytest.approx(1.0, abs=0.02)


def test_nothing_playing_has_no_headroom_rather_than_an_error():
    assert mixdown.headroom(mixdown.MixPlan()) == 0.0


# ── the wire format ─────────────────────────────────────────────────────────


def test_the_plan_serialises_to_something_the_browser_can_read(project):
    document = edits.set_fade(project, clip_id=only_audio(project).id, fade_in=SECOND)
    raw = mixdown.plan(document).to_dict()
    assert raw["sample_rate"] == 48_000
    assert raw["channels"] == 2
    assert raw["duration_seconds"] == pytest.approx(5.0)
    assert raw["asset_ids"] == ["music-1"]
    entry = raw["clips"][0]
    assert entry["envelope"][0] == [0, 0.0]
    assert entry["envelope"][-1][0] == entry["duration"]
    assert all(len(point) == 2 for point in entry["envelope"])


def test_the_conformance_fixture_still_describes_this_planner():
    """The other half of ``frontend/src/video/mixdown.test.ts``.

    The mix is planned twice — here and in the browser — for the same reason the
    frame is, and drifts the same silent way. Regenerate the fixture with
    ``python scripts/build_timeline_fixture.py`` and read the diff: a change
    here is a change to what every existing project sounds like.
    """
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document = Project.from_dict(payload["document"])
    assert mixdown.plan(document).to_dict() == payload["mix"]


def test_the_conformance_mix_exercises_more_than_a_flat_clip():
    """A fixture of one clip at one volume would pass whatever either side did."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mix = payload["mix"]
    kinds = {item["kind"] for item in mix["clips"]}
    assert kinds == {"audio", "video"}, "footage has to be in the mix, not just music"
    assert any(len(item["envelope"]) > 10 for item in mix["clips"]), "nothing curves"
    assert any(item["speed"] != 1.0 for item in mix["clips"])
    assert mix["headroom"] > 1.0, "the fixture should catch the clipping case too"


def test_every_envelope_starts_at_zero_and_ends_at_the_clip_length(project):
    """The browser must never have to guess what happens at an edge."""
    clip = only_audio(project)
    document = edits.add_keyframe(
        project, clip_id=clip.id, name="volume", at=SECOND, value=0.3, easing="ease_out"
    )
    document = edits.add_keyframe(document, clip_id=clip.id, name="volume", at=4 * SECOND, value=1.0)
    document = edits.set_fade(document, clip_id=clip.id, fade_in=SECOND, fade_out=SECOND)
    for item in mixdown.plan(document).clips:
        assert item.envelope[0][0] == 0
        assert item.envelope[-1][0] == item.duration
        ats = [at for at, _ in item.envelope]
        assert ats == sorted(set(ats)), "an envelope must move forwards and not repeat"
