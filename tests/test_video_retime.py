"""Time remapping: speed curves, freeze frames and reverse.

Three features that look separate in a menu and are one thing in the document —
how a clip's own offset maps to a position in its material. At a constant rate
that map is a multiplication, and every one of these makes it something else:

* a **speed curve** makes it the integral of a rate that varies
* a **freeze** is the same integral with the rate at zero
* **reverse** walks the same span from the far end

So they share one function, ``Clip.source_at``, and these tests are mostly about
that function being exactly right — because the browser has a second copy of it
and "exactly" is the only tolerance a conformance fixture can enforce.
"""
from __future__ import annotations

import pytest

from offsetx_apollo_builder.video import edits, presets
from offsetx_apollo_builder.video.timeline import (
    TICKS_PER_SECOND,
    Keyframe,
    Project,
    TimelineError,
    frame_at,
    new_project,
)

SECOND = TICKS_PER_SECOND


@pytest.fixture()
def project() -> Project:
    """One ten-second clip of footage with thirty seconds of material behind it."""
    document = new_project(name="Retime", preset="vertical", fps="30")
    return edits.add_clip(
        document,
        track_id=document.tracks[0].id,
        kind="video",
        start=0,
        duration=10 * SECOND,
        asset_id="footage-1",
        source_duration=30 * SECOND,
    )


def footage(document: Project):
    return document.tracks[0].clips[0]


# ── the integral ────────────────────────────────────────────────────────────


def test_a_constant_speed_is_still_a_multiplication(project):
    """The old behaviour has to survive exactly, or every existing project moves."""
    clip = footage(project)
    for offset in (0, 1, SECOND, 5 * SECOND, 10 * SECOND):
        assert clip.consumed(offset) == offset * 1.0
        assert clip.source_at(offset) == offset


def test_double_speed_reads_twice_as_much(project):
    document = edits.set_speed(project, clip_id=footage(project).id, speed=2.0, keep_duration=True)
    clip = footage(document)
    assert clip.source_at(3 * SECOND) == 6 * SECOND


def test_a_ramp_is_the_area_under_it_and_not_the_average_of_its_ends(project):
    """A speed going 0.5 → 2.0 over ten seconds consumes twelve and a half
    seconds of material — the area of the trapezoid, checkable by hand."""
    ramped = edits.apply_speed_curve(project, clip_id=footage(project).id, preset="ramp_up")
    curve = footage(ramped).speed_curve
    assert [(frame.at, frame.value) for frame in curve] == [(0, 0.5), (10 * SECOND, 2.0)]
    # (0.5 + 2.0) / 2 * 10s = 12.5s
    assert footage(ramped).consumed(10 * SECOND) == pytest.approx(12.5 * SECOND)


def test_halfway_through_a_ramp_is_not_halfway_through_the_material(project):
    """The point of a ramp. A linear rate means the position is quadratic, so
    the midpoint of the clip is *not* the midpoint of what it reads."""
    document = edits.apply_speed_curve(project, clip_id=footage(project).id, preset="ramp_up")
    clip = footage(document)
    total = clip.consumed(10 * SECOND)
    half = clip.consumed(5 * SECOND)
    assert half < total / 2, "a rising ramp reads less than half by halfway"
    # Speed at 5s is 1.25; area of the trapezoid 0→5s is (0.5 + 1.25)/2 * 5s.
    assert half == pytest.approx(4.375 * SECOND)


def test_a_held_section_consumes_nothing(project):
    """What a freeze inside a curve means: the clip runs and the material does
    not move."""
    clip = footage(project)
    document = edits.apply_speed_curve(project, clip_id=clip.id, preset="bullet")
    held = footage(document)
    frozen_start = held.consumed(int(0.35 * 10 * SECOND))
    frozen_end = held.consumed(int(0.55 * 10 * SECOND))
    assert frozen_start == pytest.approx(frozen_end, abs=1.0)


def test_the_speed_before_the_first_point_and_after_the_last_holds(project):
    """Extrapolating a *rate* past its last keyframe would send a clip off the
    end of its own material, which is exactly what nobody asked for."""
    clip = footage(project)
    clip.speed_curve = [Keyframe(at=2 * SECOND, value=2.0), Keyframe(at=4 * SECOND, value=2.0)]
    # Before the first point: 2s at 2.0.
    assert clip.consumed(2 * SECOND) == pytest.approx(4 * SECOND)
    # After the last: another 6s at 2.0, so 4 + 4 + 12 = 20s.
    assert clip.consumed(10 * SECOND) == pytest.approx(20 * SECOND)


# ── reverse ─────────────────────────────────────────────────────────────────


def test_reverse_starts_at_the_end_and_finishes_at_the_in_point(project):
    document = edits.reverse_clip(project, clip_id=footage(project).id, reversed=True)
    clip = footage(document)
    assert clip.source_at(0) == 10 * SECOND
    assert clip.source_at(10 * SECOND) == 0


def test_reverse_reads_the_same_span_as_forwards(project):
    """It is the same material in the other order, not different material."""
    forward = footage(project)
    document = edits.reverse_clip(project, clip_id=forward.id, reversed=True)
    backward = footage(document)
    assert forward.consumed(forward.duration) == backward.consumed(backward.duration)
    assert {forward.source_at(0), forward.source_at(10 * SECOND)} == {
        backward.source_at(0),
        backward.source_at(10 * SECOND),
    }


def test_reverse_respects_the_in_point(project):
    document = edits.trim_clip(project, clip_id=footage(project).id, head=2 * SECOND)
    document = edits.reverse_clip(document, clip_id=footage(document).id, reversed=True)
    clip = footage(document)
    assert clip.in_point == 2 * SECOND
    assert clip.source_at(clip.duration) == 2 * SECOND
    assert clip.source_at(0) == 2 * SECOND + clip.duration


def test_reverse_composes_with_a_curve(project):
    """Both at once, which the conformance fixture also carries."""
    document = edits.apply_speed_curve(project, clip_id=footage(project).id, preset="hero")
    document = edits.reverse_clip(document, clip_id=footage(document).id, reversed=True)
    clip = footage(document)
    total = clip.consumed(clip.duration)
    assert clip.source_at(0) == pytest.approx(total, abs=1)
    assert clip.source_at(clip.duration) == 0
    # And it still moves in one direction the whole way.
    times = [clip.source_at(at) for at in range(0, clip.duration + 1, SECOND)]
    assert times == sorted(times, reverse=True)


def test_reverse_toggles_when_nobody_says_which_way(project):
    document = edits.reverse_clip(project, clip_id=footage(project).id)
    assert footage(document).reversed is True
    document = edits.reverse_clip(document, clip_id=footage(document).id)
    assert footage(document).reversed is False


def test_only_footage_can_be_reversed(project):
    document = edits.add_clip(
        project,
        track_id=project.tracks[1].id,
        kind="audio",
        start=0,
        duration=SECOND,
        asset_id="music-1",
        source_duration=SECOND,
    )
    with pytest.raises(TimelineError, match="Only footage can be reversed"):
        edits.reverse_clip(document, clip_id=document.tracks[1].clips[0].id)


# ── freeze ──────────────────────────────────────────────────────────────────


def test_a_freeze_holds_one_instant_and_pushes_the_rest_along(project):
    document = edits.freeze_frame(
        project, clip_id=footage(project).id, at=4 * SECOND, duration=2 * SECOND
    )
    clips = document.tracks[0].clips
    assert len(clips) == 3, "cut, hold, carry on"
    left, held, right = clips
    assert (left.start, left.duration) == (0, 4 * SECOND)
    assert (held.start, held.duration) == (4 * SECOND, 2 * SECOND)
    assert (right.start, right.duration) == (6 * SECOND, 6 * SECOND)
    assert document.duration == 12 * SECOND, "the timeline got two seconds longer"


def test_the_frozen_piece_reads_one_instant_for_its_whole_length(project):
    document = edits.freeze_frame(project, clip_id=footage(project).id, at=4 * SECOND)
    held = document.tracks[0].clips[1]
    assert held.speed == 0.0
    assert held.in_point == 4 * SECOND
    assert {held.source_at(at) for at in range(0, held.duration, SECOND)} == {4 * SECOND}


def test_the_freeze_is_seamless_with_the_frame_before_it(project):
    """The whole point. The held frame has to be the frame the clip was on, or
    the video jumps at the moment it is meant to stop."""
    document = edits.freeze_frame(project, clip_id=footage(project).id, at=4 * SECOND)
    before = next(
        item for item in frame_at(document, 4 * SECOND - 1).items if item.kind == "video"
    )
    during = next(item for item in frame_at(document, 4 * SECOND).items if item.kind == "video")
    assert abs(during.source_time - before.source_time) <= 1


def test_the_frozen_piece_keeps_the_look_of_the_instant_it_froze(project):
    """A clip caught mid-zoom holds the size it was at, rather than snapping
    back to its defaults."""
    clip = footage(project)
    document = edits.add_keyframe(project, clip_id=clip.id, name="scale", at=0, value=1.0)
    document = edits.add_keyframe(
        document, clip_id=clip.id, name="scale", at=10 * SECOND, value=2.0
    )
    document = edits.freeze_frame(document, clip_id=clip.id, at=5 * SECOND)
    held = document.tracks[0].clips[1]
    assert held.property_at(0)["scale"] == pytest.approx(1.5, abs=0.01)


def test_a_freeze_outside_its_clip_is_refused(project):
    with pytest.raises(TimelineError, match="not inside clip"):
        edits.freeze_frame(project, clip_id=footage(project).id, at=20 * SECOND)


def test_only_footage_can_be_frozen(project):
    document = edits.add_clip(
        project, track_id=project.tracks[0].id, kind="image", start=11 * SECOND,
        duration=2 * SECOND, asset_id="still-1",
    )
    still = document.tracks[0].clips[1]
    with pytest.raises(TimelineError, match="already a held frame"):
        edits.freeze_frame(document, clip_id=still.id, at=12 * SECOND)


# ── what the validator refuses ──────────────────────────────────────────────


def _tight() -> Project:
    """Ten seconds of clip over ten and a half seconds of material.

    The margin matters: a `hero` curve averages exactly 1.10x, so it needs
    eleven seconds. Over eleven seconds of source it would fit precisely, and a
    test that passes on an exact tie proves nothing about the boundary.
    """
    document = new_project(name="Tight")
    return edits.add_clip(
        document,
        track_id=document.tracks[0].id,
        kind="video",
        start=0,
        duration=10 * SECOND,
        asset_id="footage-1",
        source_duration=int(10.5 * SECOND),
    )


def test_a_curve_that_reads_past_the_end_of_the_source_is_refused():
    """A hero ramp averages more than 1x, so a clip already using most of its
    material will not fit — and the message says so with the numbers."""
    document = _tight()
    with pytest.raises(TimelineError, match="past the end of its source"):
        edits.apply_speed_curve(document, clip_id=footage(document).id, preset="hero")


def test_the_same_curve_fits_when_it_is_allowed_to_change_the_length():
    """`keep_duration=False` solves for the length at which the curve consumes
    exactly what the clip consumed before."""
    document = _tight()
    before = footage(document).consumed(footage(document).duration)
    fitted = edits.apply_speed_curve(
        document, clip_id=footage(document).id, preset="hero", keep_duration=False
    )
    clip = footage(fitted)
    assert clip.speed_curve
    assert clip.duration < 10 * SECOND, "a curve needing more material has to run shorter"
    assert clip.consumed(clip.duration) == pytest.approx(before, rel=0.02)


def test_an_eased_speed_point_is_refused_and_says_why(project):
    """The integral of an eased rate is not a sum of trapezoids, and two
    languages agreeing on it to the tick is the whole contract."""
    from offsetx_apollo_builder.video.timeline import _validate_clip

    clip = footage(project)
    clip.speed_curve = [
        Keyframe(at=0, value=1.0, easing="ease_in"),
        Keyframe(at=10 * SECOND, value=2.0),
    ]
    with pytest.raises(TimelineError, match="cannot be eased"):
        _validate_clip(clip, project.tracks[0])


def test_a_speed_point_outside_its_clip_is_refused(project):
    from offsetx_apollo_builder.video.timeline import _validate_clip

    clip = footage(project)
    clip.speed_curve = [Keyframe(at=0, value=1.0), Keyframe(at=99 * SECOND, value=1.0)]
    with pytest.raises(TimelineError, match="outside a clip"):
        _validate_clip(clip, project.tracks[0])


def test_a_one_point_curve_is_a_constant_written_the_long_way(project):
    from offsetx_apollo_builder.video.timeline import _validate_clip

    clip = footage(project)
    clip.speed_curve = [Keyframe(at=0, value=2.0)]
    with pytest.raises(TimelineError, match="one point"):
        _validate_clip(clip, project.tracks[0])


def test_a_speed_between_zero_and_the_minimum_is_refused(project):
    with pytest.raises(TimelineError, match="0 \\(freeze\\)"):
        edits.set_speed(project, clip_id=footage(project).id, speed=0.01)


def test_zero_is_allowed_because_zero_means_freeze(project):
    document = edits.set_speed(project, clip_id=footage(project).id, speed=0.0)
    assert footage(document).speed == 0.0
    assert footage(document).source_at(5 * SECOND) == 0


def test_setting_one_rate_clears_a_curve_rather_than_arguing_with_it(project):
    document = edits.apply_speed_curve(project, clip_id=footage(project).id, preset="hero")
    assert footage(document).speed_curve
    document = edits.set_speed(document, clip_id=footage(document).id, speed=1.5)
    assert footage(document).speed_curve == []
    assert footage(document).speed == 1.5


# ── the presets ─────────────────────────────────────────────────────────────


def test_every_speed_preset_is_declared_and_none_is_a_fallback():
    with pytest.raises(presets.UnknownPreset, match="Unknown speed curve"):
        presets.speed_curve("dramatic")


def test_every_preset_starts_at_the_beginning_and_ends_at_the_end():
    """A curve that does not reach a clip's edges leaves the rate there implied,
    and implied is the thing this whole registry exists to avoid."""
    for name, preset in presets.SPEED_CURVES.items():
        assert preset.points[0][0] == 0.0, f"{name} does not start at 0"
        assert preset.points[-1][0] == 1.0, f"{name} does not end at 1"
        assert preset.family in presets.SPEED_FAMILIES


def test_every_preset_moves_at_all_and_none_is_frozen_end_to_end():
    for name, preset in presets.SPEED_CURVES.items():
        assert preset.average > 0, f"{name} consumes nothing at all"
        assert any(speed > 0 for _, speed in preset.points), name


def test_the_impact_presets_are_the_ones_that_actually_stop():
    """"Bullet time" is a hard stop in the middle of a move. If none of these
    reaches zero, the family is misnamed."""
    for name, preset in presets.SPEED_CURVES.items():
        stops = any(speed == 0 for _, speed in preset.points)
        assert stops == (preset.family == "impact"), f"{name} stops: {stops}"


def test_a_preset_scaled_to_a_clip_lands_on_whole_ticks():
    points = presets.speed_points_for("hero", 45_000)
    assert [item["at"] for item in points] == [0, 13500, 31500, 45000]
    assert all(item["easing"] == "linear" for item in points)


def test_a_preset_on_a_very_short_clip_still_produces_a_usable_curve():
    """Points that round onto the same tick collapse — a vertical jump in speed
    has no single area under it. What is left still has to be a curve."""
    for name in presets.SPEED_CURVES:
        points = presets.speed_points_for(name, 1500)
        assert len(points) >= 2, name
        assert [item["at"] for item in points] == sorted({item["at"] for item in points}), name


def test_the_catalogue_carries_the_speed_curves_for_anything_that_searches():
    catalogue = presets.catalogue()
    assert len(catalogue["speed_curves"]) == len(presets.SPEED_CURVES)
    assert set(catalogue["speed_families"]) == set(presets.SPEED_FAMILIES)
    entry = next(item for item in catalogue["speed_curves"] if item["id"] == "hero")
    assert entry["average"] > 1.0, "a hero ramp needs more material than it plays"


# ── the sound ───────────────────────────────────────────────────────────────


def test_a_retimed_clip_is_left_out_of_the_mix_and_the_plan_says_why():
    """Resampling sound is not playing it faster, it is deciding what to do
    about the pitch — and that is a feature that is not built. Playing the audio
    at one rate under a picture doing something else would drift further apart
    the longer the clip ran."""
    from offsetx_apollo_builder.video import mixdown

    document = new_project(name="Retime")
    document = edits.add_clip(
        document,
        track_id=document.tracks[0].id,
        kind="video",
        start=0,
        duration=10 * SECOND,
        asset_id="footage-1",
        source_duration=30 * SECOND,
    )
    plan = mixdown.plan(document)
    assert not plan.silent, "plain footage is in the mix"

    curved = edits.apply_speed_curve(document, clip_id=footage(document).id, preset="hero")
    plan = mixdown.plan(curved)
    assert plan.silent
    assert plan.excluded == [(footage(curved).id, "its speed changes over its own length")]

    backward = edits.reverse_clip(document, clip_id=footage(document).id, reversed=True)
    assert mixdown.plan(backward).excluded[0][1] == "it plays backwards"

    frozen = edits.set_speed(document, clip_id=footage(document).id, speed=0.0)
    assert mixdown.plan(frozen).excluded[0][1] == "it is frozen on one instant"
