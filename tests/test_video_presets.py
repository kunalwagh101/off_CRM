"""Transitions, animations and styles — the registry, and the edits that use it.

Two things are being protected.

**The invariant survives transitions.** A dissolve needs both clips on screen at
once, and clips on a track cannot overlap by a tick. The way out was *not* to
relax that rule — it is the one that stops the preview and the export
disagreeing about which clip wins. Instead the clips stay adjacent and a
declared object says how far either side of their shared cut both are drawn.
Every test about pruning, fitting and dangling transitions is about keeping that
distinction real.

**Presets are data.** 46 transitions over 9 families, 32 animations over 3, and
an animation applied is *ordinary keyframes* — so it survives a split, travels
with a trim and resolves identically in both languages, because all of that
already works and none of it was rebuilt.
"""
from __future__ import annotations

import pytest

from offsetx_apollo_builder.video import edits, presets
from offsetx_apollo_builder.video.presets import UnknownPreset
from offsetx_apollo_builder.video.timeline import (
    BLEND_MODES,
    TICKS_PER_SECOND,
    Project,
    TimelineError,
    frame_at,
    new_project,
    transition_window,
)

SECOND = TICKS_PER_SECOND


@pytest.fixture()
def two_clips() -> Project:
    """Two three-second clips meeting at a cut at 3s."""
    project = new_project(name="Cuts", preset="vertical", fps="30")
    track = project.tracks[0].id
    project = edits.add_clip(project, track_id=track, kind="solid", start=0, duration=3 * SECOND)
    project = edits.add_clip(
        project, track_id=track, kind="solid", start=3 * SECOND, duration=3 * SECOND
    )
    return project


def clips(project: Project):
    return sorted(project.tracks[0].clips, key=lambda item: item.start)


# ── the registry ────────────────────────────────────────────────────────────


def test_the_presets_are_many_and_the_families_are_few():
    """The whole architecture argument, as a number."""
    assert len(presets.TRANSITIONS) >= 40
    assert len(presets.TRANSITION_FAMILIES) == 9
    assert len(presets.ANIMATIONS) >= 30
    assert len(presets.ANIMATION_FAMILIES) == 3


def test_every_transition_names_a_family_the_painter_implements():
    for preset in presets.TRANSITIONS.values():
        assert preset.family in presets.TRANSITION_FAMILIES, preset.id


def test_every_animation_moves_a_property_the_timeline_knows():
    from offsetx_apollo_builder.video.timeline import PROPERTY_SPEC

    for preset in presets.ANIMATIONS.values():
        assert preset.family in presets.ANIMATION_FAMILIES, preset.id
        assert preset.moves, preset.id
        for name in preset.moves:
            assert name in PROPERTY_SPEC, f"{preset.id} moves unknown property {name}"


def test_an_unlisted_preset_is_refused_rather_than_substituted():
    """A timeline that quietly fell back to a dissolve would export something
    nobody chose."""
    with pytest.raises(UnknownPreset, match="Unknown transition"):
        presets.transition("teleport")
    with pytest.raises(UnknownPreset, match="Unknown animation"):
        presets.animation("moonwalk")
    with pytest.raises(UnknownPreset, match="Unknown text style"):
        presets.text_style("comic sans deluxe")


def test_the_catalogue_carries_everything_a_picker_needs():
    catalogue = presets.catalogue()
    assert len(catalogue["transitions"]) == len(presets.TRANSITIONS)
    assert len(catalogue["animations"]) == len(presets.ANIMATIONS)
    assert catalogue["text_styles"]
    assert catalogue["limits"]["default_transition_ticks"] > 0


# ── transitions on the timeline ─────────────────────────────────────────────


def test_a_transition_needs_two_clips(two_clips):
    last = clips(two_clips)[-1].id
    with pytest.raises(TimelineError, match="no clip after"):
        edits.add_transition(two_clips, clip_id=last, side="after")


def test_a_transition_needs_the_clips_to_actually_meet(two_clips):
    first = clips(two_clips)[0].id
    moved = edits.move_clip(two_clips, clip_id=clips(two_clips)[1].id, start=4 * SECOND)
    with pytest.raises(TimelineError, match="do not meet"):
        edits.add_transition(moved, clip_id=first, side="after")


def test_a_transition_draws_both_clips_across_the_cut(two_clips):
    first = clips(two_clips)[0].id
    with_transition = edits.add_transition(
        two_clips, clip_id=first, preset="dissolve", duration=SECOND
    )
    # The cut is at 3s and the window is half a second either side.
    assert len(frame_at(with_transition, int(2.4 * SECOND)).items) == 1
    middle = frame_at(with_transition, 3 * SECOND)
    assert len(middle.items) == 2
    assert {item.transition["role"] for item in middle.items} == {"from", "to"}
    assert len(frame_at(with_transition, int(3.6 * SECOND)).items) == 1


def test_both_sides_share_one_progress(two_clips):
    """Two clocks are how the halves end up disagreeing about the middle."""
    with_transition = edits.add_transition(
        two_clips, clip_id=clips(two_clips)[0].id, preset="wipe_left", duration=SECOND
    )
    for tick in range(int(2.5 * SECOND), int(3.5 * SECOND), 3000):
        items = frame_at(with_transition, tick).items
        assert len({item.transition["progress"] for item in items}) == 1


def test_progress_runs_from_zero_to_one_across_the_window(two_clips):
    with_transition = edits.add_transition(
        two_clips, clip_id=clips(two_clips)[0].id, duration=SECOND
    )
    start = frame_at(with_transition, int(2.5 * SECOND)).items[0].transition["progress"]
    middle = frame_at(with_transition, 3 * SECOND).items[0].transition["progress"]
    end = frame_at(with_transition, int(3.5 * SECOND) - 1).items[0].transition["progress"]
    assert start == pytest.approx(0.0, abs=0.001)
    assert middle == pytest.approx(0.5, abs=0.001)
    assert end == pytest.approx(1.0, abs=0.001)


def test_a_clip_drawn_past_its_end_stays_inside_its_own_material(two_clips):
    """Otherwise it reads past the end of its source — the thing the validator
    exists to prevent."""
    with_transition = edits.add_transition(
        two_clips, clip_id=clips(two_clips)[0].id, duration=SECOND
    )
    first = clips(with_transition)[0]
    late = frame_at(with_transition, int(3.4 * SECOND))
    outgoing = next(item for item in late.items if item.clip_id == first.id)
    assert outgoing.clip_time < first.duration


def test_the_clips_themselves_still_do_not_overlap(two_clips):
    """The invariant is intact: only the *drawing* extends."""
    with_transition = edits.add_transition(
        two_clips, clip_id=clips(two_clips)[0].id, duration=SECOND
    )
    left, right = clips(with_transition)
    assert left.start + left.duration == right.start


def test_one_transition_per_cut(two_clips):
    """Two blends over the same frames has no defined answer."""
    first = clips(two_clips)[0].id
    once = edits.add_transition(two_clips, clip_id=first, preset="dissolve")
    twice = edits.add_transition(once, clip_id=first, preset="glitch")
    assert len(twice.tracks[0].transitions) == 1
    assert twice.tracks[0].transitions[0].preset == "glitch"


def test_two_transitions_cannot_share_a_frame_of_one_short_clip():
    """Half of each transition extends into the clip between them. If the two
    halves exceed it, they overlap *each other* inside it — and a frame
    belonging to two blends has no defined answer, which is the same objection
    as two clips claiming one tick.

    (The maximum transition is two seconds, so this needs genuinely short clips
    rather than a long transition — an earlier version of this test asked for a
    five-second blend, got a clamped two-second one, and proved nothing.)
    """
    project = new_project(fps="30")
    track = project.tracks[0].id
    for index in range(3):
        project = edits.add_clip(
            project, track_id=track, kind="solid", start=index * SECOND, duration=SECOND
        )
    first, middle, _ = clips(project)
    # Each 2s transition takes 1s from the middle clip, and it is only 1s long.
    with_one = edits.add_transition(project, clip_id=first.id, duration=2 * SECOND)
    with pytest.raises(TimelineError, match="cannot share a frame"):
        edits.add_transition(with_one, clip_id=middle.id, duration=2 * SECOND, side="after")


def test_a_transition_duration_is_bounded(two_clips):
    first = clips(two_clips)[0].id
    short = edits.add_transition(two_clips, clip_id=first, duration=1)
    assert short.tracks[0].transitions[0].duration == presets.MIN_TRANSITION_TICKS
    long = edits.add_transition(two_clips, clip_id=first, duration=100 * SECOND)
    assert long.tracks[0].transitions[0].duration == presets.MAX_TRANSITION_TICKS


def test_moving_a_clip_takes_its_transition_with_it(two_clips):
    """A transition describes a cut. Destroy the cut and it goes, rather than
    lingering as a ghost that reappears if the clips ever line up again."""
    first, second = clips(two_clips)
    with_transition = edits.add_transition(two_clips, clip_id=first.id, duration=SECOND)
    assert with_transition.tracks[0].transitions
    moved = edits.move_clip(with_transition, clip_id=second.id, start=5 * SECOND)
    assert moved.tracks[0].transitions == []


def test_deleting_a_clip_takes_its_transition_with_it(two_clips):
    first = clips(two_clips)[0]
    with_transition = edits.add_transition(two_clips, clip_id=first.id, duration=SECOND)
    assert edits.remove_clip(with_transition, clip_id=first.id).tracks[0].transitions == []


def test_splitting_across_a_cut_keeps_the_transition_on_the_real_boundary(two_clips):
    first = clips(two_clips)[0]
    with_transition = edits.add_transition(two_clips, clip_id=first.id, duration=SECOND)
    # Splitting the *second* clip leaves the original cut untouched.
    second = clips(with_transition)[1]
    split = edits.split_clip(with_transition, clip_id=second.id, at=int(4.5 * SECOND))
    assert len(split.tracks[0].transitions) == 1
    assert transition_window(split.tracks[0], split.tracks[0].transitions[0]) is not None


def test_a_transition_can_be_retimed_and_restyled(two_clips):
    with_transition = edits.add_transition(two_clips, clip_id=clips(two_clips)[0].id)
    item = with_transition.tracks[0].transitions[0]
    changed = edits.set_transition(
        with_transition, transition_id=item.id, preset="glitch_rgb", duration=SECOND
    )
    assert changed.tracks[0].transitions[0].preset == "glitch_rgb"
    assert changed.tracks[0].transitions[0].duration == SECOND


def test_a_transition_can_be_removed(two_clips):
    with_transition = edits.add_transition(two_clips, clip_id=clips(two_clips)[0].id)
    item = with_transition.tracks[0].transitions[0]
    assert edits.remove_transition(with_transition, transition_id=item.id).tracks[0].transitions == []


def test_apply_to_all_covers_every_cut(two_clips):
    track = two_clips.tracks[0].id
    project = edits.add_clip(two_clips, track_id=track, kind="solid", start=6 * SECOND, duration=3 * SECOND)
    everywhere = edits.apply_transition_to_all(project, track_id=track, preset="dissolve", duration=SECOND)
    assert len(everywhere.tracks[0].transitions) == 2


def test_apply_to_all_skips_a_cut_it_cannot_take_rather_than_failing(two_clips):
    """Asking for 'all' and getting nothing because one clip was short is not
    what anyone means by all."""
    track = two_clips.tracks[0].id
    project = edits.add_clip(
        two_clips, track_id=track, kind="solid", start=6 * SECOND, duration=3 * SECOND
    )
    everywhere = edits.apply_transition_to_all(
        project, track_id=track, preset="dissolve", duration=5 * SECOND
    )
    assert len(everywhere.tracks[0].transitions) >= 1


def test_a_transition_survives_a_document_round_trip(two_clips):
    with_transition = edits.add_transition(
        two_clips, clip_id=clips(two_clips)[0].id, preset="whip_left", duration=SECOND
    )
    again = Project.from_dict(with_transition.to_dict())
    assert again.to_dict() == with_transition.to_dict()
    assert again.tracks[0].transitions[0].preset == "whip_left"


# ── animations ──────────────────────────────────────────────────────────────


def test_an_animation_becomes_ordinary_keyframes(two_clips):
    """Not a new kind of object: everything that already works on keyframes then
    works on animations for free."""
    clip = clips(two_clips)[0].id
    animated = edits.apply_animation(two_clips, clip_id=clip, preset="fade_in", duration=SECOND)
    keyframes = clips(animated)[0].keyframes
    assert "opacity" in keyframes
    assert frame_at(animated, 0).items[0].opacity == pytest.approx(0.0)
    assert frame_at(animated, SECOND).items[0].opacity == pytest.approx(1.0)


def test_an_out_animation_runs_at_the_tail(two_clips):
    clip = clips(two_clips)[0].id
    animated = edits.apply_animation(two_clips, clip_id=clip, preset="fade_out", duration=SECOND)
    assert frame_at(animated, SECOND).items[0].opacity == pytest.approx(1.0)
    assert frame_at(animated, 3 * SECOND - 1).items[0].opacity < 0.01


def test_a_loop_animation_ends_where_it_started(two_clips):
    """Or a repeat jumps."""
    clip = clips(two_clips)[0].id
    animated = edits.apply_animation(two_clips, clip_id=clip, preset="pulse")
    first = frame_at(animated, 0).items[0].properties["scale"]
    last = frame_at(animated, 3 * SECOND - 1).items[0].properties["scale"]
    assert first == pytest.approx(last, abs=0.05)


def test_an_animation_survives_a_split_like_any_other_keyframes(two_clips):
    clip = clips(two_clips)[0].id
    animated = edits.apply_animation(two_clips, clip_id=clip, preset="zoom_in", duration=2 * SECOND)
    before = [
        round(frame_at(animated, tick).items[0].properties["scale"], 6)
        for tick in range(0, 3 * SECOND, 9000)
    ]
    split = edits.split_clip(animated, clip_id=clip, at=SECOND)
    after = [
        round(frame_at(split, tick).items[0].properties["scale"], 6)
        for tick in range(0, 3 * SECOND, 9000)
    ]
    assert before == after


def test_an_animation_never_keyframes_past_its_clip(two_clips):
    clip = clips(two_clips)[0]
    animated = edits.apply_animation(
        two_clips, clip_id=clip.id, preset="slide_in_left", duration=10 * SECOND
    )
    for frames in clips(animated)[0].keyframes.values():
        for frame in frames:
            assert frame.at <= clip.duration


def test_the_applied_animation_is_recorded_on_the_clip(two_clips):
    animated = edits.apply_animation(two_clips, clip_id=clips(two_clips)[0].id, preset="pop_in")
    assert clips(animated)[0].style["animation"] == "pop_in"


# ── styles, blend modes, copied attributes ──────────────────────────────────


def test_a_text_style_is_applied_by_name():
    project = new_project(fps="30")
    project = edits.add_clip(
        project, track_id=project.tracks[0].id, kind="text", start=0, duration=2 * SECOND, text="Hi"
    )
    clip = project.tracks[0].clips[0].id
    styled = edits.apply_text_style(project, clip_id=clip, style="neon")
    assert styled.tracks[0].clips[0].style["glow"] == 24
    assert styled.tracks[0].clips[0].style["preset"] == "neon"


def test_a_text_style_is_refused_on_a_clip_that_is_not_text(two_clips):
    with pytest.raises(TimelineError, match="not a text clip"):
        edits.apply_text_style(two_clips, clip_id=clips(two_clips)[0].id, style="neon")


def test_every_blend_mode_is_accepted_and_an_invented_one_is_not(two_clips):
    clip = clips(two_clips)[0].id
    for mode in BLEND_MODES:
        assert edits.set_blend_mode(two_clips, clip_id=clip, mode=mode)
    with pytest.raises(TimelineError, match="Unknown blend mode"):
        edits.set_blend_mode(two_clips, clip_id=clip, mode="rainbow")


def test_attributes_can_be_pasted_onto_other_clips(two_clips):
    first, second = clips(two_clips)
    styled = edits.set_property(two_clips, clip_id=first.id, name="saturation", value=0.5)
    styled = edits.set_blend_mode(styled, clip_id=first.id, mode="screen")
    pasted = edits.copy_attributes(styled, from_clip_id=first.id, to_clip_ids=[second.id])
    target = clips(pasted)[1]
    assert target.properties["saturation"] == 0.5
    assert target.style["blend"] == "screen"


def test_keyframes_are_not_pasted_unless_asked_for(two_clips):
    """They are measured against the source clip's length, and pasting them onto
    a clip of a different length puts the animation somewhere nobody chose."""
    first, second = clips(two_clips)
    animated = edits.apply_animation(two_clips, clip_id=first.id, preset="fade_in")
    pasted = edits.copy_attributes(animated, from_clip_id=first.id, to_clip_ids=[second.id])
    assert clips(pasted)[1].keyframes == {}
    asked = edits.copy_attributes(
        animated, from_clip_id=first.id, to_clip_ids=[second.id], keyframes=True
    )
    assert "opacity" in clips(asked)[1].keyframes


# ── the new properties ──────────────────────────────────────────────────────


def test_the_expanded_colour_and_transform_properties_animate(two_clips):
    clip = clips(two_clips)[0].id
    project = two_clips
    for name in ("exposure", "temperature", "tint", "vignette", "sharpen", "grain", "flip_x"):
        project = edits.set_property(project, clip_id=clip, name=name, value=0.5)
    resolved = frame_at(project, SECOND).items[0].properties
    for name in ("exposure", "temperature", "tint", "vignette", "sharpen", "grain"):
        assert resolved[name] == 0.5
    assert resolved["flip_x"] == 0.5


def test_a_flip_is_a_number_so_it_keyframes_like_anything_else(two_clips):
    clip = clips(two_clips)[0].id
    flipped = edits.add_keyframe(two_clips, clip_id=clip, name="flip_x", at=0, value=0.0)
    flipped = edits.add_keyframe(flipped, clip_id=clip, name="flip_x", at=SECOND, value=1.0, easing="hold")
    assert frame_at(flipped, 0).items[0].properties["flip_x"] == 0.0
    assert frame_at(flipped, SECOND).items[0].properties["flip_x"] == 1.0
