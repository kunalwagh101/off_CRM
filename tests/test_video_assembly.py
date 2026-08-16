"""The assembler: material in, finished timeline out.

The centre of the brief this editor exists for — *"CapCut, but it does it
automatically"* — and the stage whose acceptance criterion was written down
before it was built: **a topic goes to a finished, gate-passing video with zero
manual timeline edits.**

Three things are being protected.

**The duration is exact.** The export gate compares a rendered file against the
project's own length, so an assembly that lands 200 ticks short fails a gate for
a reason nobody could see. Every recipe at every length has to hit the target on
the tick.

**It is valid because it was built by the same functions a person's clicks are.**
Nothing here constructs a clip; if the assembler could produce an overlapping
timeline, so could a user, and the invariant would already be broken.

**It says what it settled for.** A brief the material cannot meet exactly is not
a failure. Silently producing something else is.
"""
from __future__ import annotations

import pytest

from offsetx_apollo_builder.video import assembly, edits, recipes
from offsetx_apollo_builder.video.timeline import (
    TICKS_PER_SECOND,
    MIN_CLIP_TICKS,
    Project,
    TimelineError,
)

SECOND = TICKS_PER_SECOND


def stills(count: int) -> list[assembly.Visual]:
    return [assembly.Visual(f"still-{n}", "image") for n in range(count)]


def brief(**overrides) -> assembly.AssemblyBrief:
    params = {
        "name": "Reel",
        "recipe": "hook_hold_payoff",
        "visuals": stills(4),
        "target_ticks": 15 * SECOND,
        "lines": ["Stop scrolling.", "Here is the thing.", "That is why."],
        "music": assembly.Sound("music-1", 60 * SECOND),
    }
    params.update(overrides)
    return assembly.AssemblyBrief(**params)


# ── the length has to be exactly right ──────────────────────────────────────


@pytest.mark.parametrize("name", sorted(recipes.RECIPES))
@pytest.mark.parametrize("seconds", [3, 7, 15, 30, 60, 90])
def test_every_recipe_at_every_length_lands_on_the_target(name, seconds):
    """The export gate checks a file against the project's own duration. An
    assembly a few ticks short fails it for a reason nobody could see."""
    report = assembly.assemble(brief(recipe=name, target_ticks=seconds * SECOND))
    assert report.project.duration == seconds * SECOND


def test_a_target_between_two_frames_is_snapped_and_said_so():
    """An exporter stops on a frame. A project that does not is one it cannot
    reproduce."""
    report = assembly.assemble(brief(target_ticks=15 * SECOND + 700))
    assert report.project.duration % 3000 == 0
    assert any("nearest whole frame" in note for note in report.notes)


def test_the_beats_are_laid_in_the_recipe_s_proportions():
    report = assembly.assemble(brief(target_ticks=100 * SECOND))
    recipe = recipes.recipe("hook_hold_payoff")
    for beat, row in zip(recipe.beats, report.beats):
        assert row["name"] == beat.name
        assert row["duration"] / (100 * SECOND) == pytest.approx(beat.share, abs=0.01)


def test_the_beats_meet_end_to_end_with_no_gap_and_no_overlap():
    report = assembly.assemble(brief(target_ticks=42 * SECOND))
    at = 0
    for row in report.beats:
        assert row["start"] == at
        at += row["duration"]
    assert at == report.project.duration


# ── the material decides how many cuts ──────────────────────────────────────


def test_one_picture_is_enough_to_make_a_video():
    report = assembly.assemble(brief(visuals=stills(1)))
    assert report.project.duration == 15 * SECOND
    assert all(clip.asset_id == "still-0" for clip in report.project.tracks[0].clips)


def test_more_pictures_mean_more_cuts():
    few = assembly.assemble(brief(visuals=stills(1), target_ticks=30 * SECOND))
    many = assembly.assemble(brief(visuals=stills(8), target_ticks=30 * SECOND))
    assert len(many.project.tracks[0].clips) > len(few.project.tracks[0].clips)


def test_footage_too_short_for_its_slot_is_slowed_down_to_fill_it():
    """Slow motion is what a short clip over a long beat *is*. The alternative
    is a gap, and a gap is a black frame nobody asked for."""
    report = assembly.assemble(
        brief(
            recipe="before_after",
            visuals=[assembly.Visual("tiny", "video", 2 * SECOND)],
            target_ticks=12 * SECOND,
        )
    )
    for clip in report.project.tracks[0].clips:
        assert clip.speed < 1.0, "a 2s clip over a 6s beat has to be slowed"
        # And it reads all of its material and none past the end.
        assert clip.consumed(clip.duration) <= clip.source_duration
        assert clip.consumed(clip.duration) == pytest.approx(clip.source_duration, rel=0.01)


def test_a_speed_rounded_to_four_places_never_reads_past_the_end():
    """The rate is stored to four decimal places, and rounding the last one
    upward makes a clip consume a handful of ticks the source does not have.
    Found by an assembly that refused itself."""
    for seconds in range(4, 60):
        report = assembly.assemble(
            brief(
                recipe="before_after",
                visuals=[assembly.Visual("tiny", "video", 2 * SECOND)],
                target_ticks=seconds * SECOND,
                lines=[],
            )
        )
        for clip in report.project.tracks[0].clips:
            assert clip.consumed(clip.duration) <= clip.source_duration, seconds


def test_a_beat_longer_than_its_footage_can_stretch_is_cut_more_often():
    """Ten times its own length is as far as one clip goes. Past that it needs a
    second cut, whatever the recipe wanted."""
    report = assembly.assemble(
        brief(
            recipe="before_after",
            visuals=[assembly.Visual("tiny", "video", SECOND)],
            target_ticks=60 * SECOND,
            lines=[],
        )
    )
    assert len(report.project.tracks[0].clips) > 6
    assert report.project.duration == 60 * SECOND


# ── the words ───────────────────────────────────────────────────────────────


def test_the_lines_are_laid_out_in_order_over_the_whole_thing():
    report = assembly.assemble(brief())
    text = [clip for track in report.project.tracks for clip in track.clips if clip.kind == "text"]
    assert [clip.text for clip in text] == [
        "Stop scrolling.",
        "Here is the thing.",
        "That is why.",
    ]
    assert [clip.start for clip in text] == sorted(clip.start for clip in text)


def test_the_words_get_the_style_their_beat_asked_for():
    report = assembly.assemble(brief())
    first = next(
        clip for track in report.project.tracks for clip in track.clips if clip.kind == "text"
    )
    # The hook beat declares `bold_block`, whose weight is 900.
    assert first.style.get("weight") == "900"


def test_a_video_with_no_words_is_still_a_video():
    report = assembly.assemble(brief(lines=[]))
    assert not any(
        clip.kind == "text" for track in report.project.tracks for clip in track.clips
    )
    assert report.project.duration == 15 * SECOND


def test_more_lines_than_beats_share_the_beats_out():
    report = assembly.assemble(brief(lines=[f"line {n}" for n in range(9)]))
    text = [clip for track in report.project.tracks for clip in track.clips if clip.kind == "text"]
    assert len(text) == 9
    assert [clip.text for clip in text] == [f"line {n}" for n in range(9)]


def test_lines_nobody_could_read_in_the_time_are_flagged():
    """The same reading speed the caption engine measures against. A line on
    screen for a twentieth of a second is technically a valid clip and is not a
    caption, and only whoever wrote it can decide which half to cut."""
    report = assembly.assemble(brief(target_ticks=4 * SECOND, lines=[f"line number {n}" for n in range(9)]))
    assert any("characters a second" in note for note in report.notes)


def test_lines_with_no_room_at_all_are_dropped_and_said_so():
    report = assembly.assemble(
        brief(target_ticks=3 * SECOND, lines=[f"l{n}" for n in range(200)])
    )
    assert any("No room for" in note for note in report.notes)


# ── the sound ───────────────────────────────────────────────────────────────


def test_music_runs_under_the_whole_thing_with_fades():
    report = assembly.assemble(brief())
    music = next(track for track in report.project.tracks if track.name == "Music")
    assert len(music.clips) == 1
    clip = music.clips[0]
    assert clip.start == 0
    assert clip.duration == 15 * SECOND
    assert clip.fade_in > 0 and clip.fade_out > 0


def test_music_sits_lower_when_there_is_a_voice_over_it():
    alone = assembly.assemble(brief())
    under = assembly.assemble(brief(voice=assembly.Sound("voice-1", 15 * SECOND)))
    loud = next(t for t in alone.project.tracks if t.name == "Music").clips[0]
    quiet = next(t for t in under.project.tracks if t.name == "Music").clips[0]
    assert quiet.properties["volume"] < loud.properties["volume"]


def test_music_shorter_than_the_video_is_not_looped_and_says_so():
    """A loop with an audible seam is worse than a fade, so this does not
    pretend to have solved it."""
    report = assembly.assemble(brief(music=assembly.Sound("music-1", 5 * SECOND)))
    music = next(track for track in report.project.tracks if track.name == "Music")
    assert music.clips[0].duration == 5 * SECOND
    assert any("tail is silent" in note for note in report.notes)


def test_a_voice_gets_its_own_track_so_the_music_can_stay_under_it():
    report = assembly.assemble(brief(voice=assembly.Sound("voice-1", 15 * SECOND)))
    names = [track.name for track in report.project.tracks]
    assert "Voice" in names and "Music" in names


def test_a_video_with_no_music_is_told_that_platforms_bury_those():
    report = assembly.assemble(brief(music=None))
    assert any("silent video" in note for note in report.notes)


# ── what it refuses ─────────────────────────────────────────────────────────


def test_an_assembly_with_nothing_to_show_is_refused():
    with pytest.raises(assembly.AssemblyRefused, match="nothing to show"):
        assembly.assemble(brief(visuals=[]))


def test_a_target_below_the_floor_is_refused_with_the_number():
    with pytest.raises(assembly.AssemblyRefused, match="below the"):
        assembly.assemble(brief(target_ticks=SECOND))


def test_a_target_past_the_ceiling_is_refused():
    with pytest.raises(assembly.AssemblyRefused, match="past the"):
        assembly.assemble(brief(target_ticks=9999 * SECOND))


def test_an_undeclared_recipe_is_refused_rather_than_defaulted():
    with pytest.raises(recipes.UnknownRecipe, match="Unknown recipe"):
        assembly.assemble(brief(recipe="viral"))


# ── it has to be reproducible ───────────────────────────────────────────────


def test_the_same_brief_and_seed_give_the_same_project_to_the_tick():
    """Without this the edit-diff below measures noise, and an owner who
    re-runs an assembly after changing one line cannot see what changed."""
    first = assembly.assemble(brief(seed=7))
    second = assembly.assemble(brief(seed=7))
    assert _shape(first.project) == _shape(second.project)


def test_a_different_seed_gives_a_different_arrangement():
    plain = assembly.assemble(brief(visuals=stills(6), seed=0))
    shuffled = assembly.assemble(brief(visuals=stills(6), seed=3))
    assert _shape(plain.project) != _shape(shuffled.project)


def test_seed_zero_keeps_the_order_the_material_arrived_in():
    """The order pictures come in is usually the order somebody put them in.
    Reordering it for no reason is something they have to undo first."""
    report = assembly.assemble(brief(visuals=stills(4), seed=0, lines=[]))
    used = [clip.asset_id for clip in report.project.tracks[0].clips]
    assert used[0] == "still-0"
    assert used[1] == "still-1"


def _shape(project: Project) -> list[tuple]:
    return [
        (track.name, clip.kind, clip.start, clip.duration, clip.asset_id, clip.text)
        for track in project.tracks
        for clip in track.clips
    ]


# ── the invariants hold, because it used the same functions ─────────────────


@pytest.mark.parametrize("name", sorted(recipes.RECIPES))
def test_nothing_it_builds_can_be_refused_by_the_editor(name):
    """The property that makes this safe. Every clip went through `edits`, so an
    assembled project is valid for the same reason a hand-made one is — and it
    survives a round trip through the document format."""
    report = assembly.assemble(
        brief(
            recipe=name,
            visuals=stills(3) + [assembly.Visual("clip-1", "video", 20 * SECOND)],
            target_ticks=25 * SECOND,
        )
    )
    restored = Project.from_dict(report.project.to_dict())
    assert restored.to_dict() == report.project.to_dict()
    for track in restored.tracks:
        ordered = sorted(track.clips, key=lambda clip: clip.start)
        for left, right in zip(ordered, ordered[1:]):
            assert left.end <= right.start, f"{name} overlapped on {track.name}"
        for clip in track.clips:
            assert clip.duration >= MIN_CLIP_TICKS
            if clip.source_duration:
                assert clip.in_point + clip.consumed(clip.duration) <= clip.source_duration


def test_an_assembled_project_can_still_be_edited_by_hand():
    """It is an ordinary document. If it were not, the owner could not fix it,
    which is the whole reason the editor was built before the assembler."""
    report = assembly.assemble(brief())
    clip = report.project.tracks[0].clips[0]
    changed = edits.set_property(report.project, clip_id=clip.id, name="scale", value=1.4)
    changed = edits.split_clip(changed, clip_id=clip.id, at=clip.start + clip.duration // 2)
    assert len(changed.tracks[0].clips) == len(report.project.tracks[0].clips) + 1


def test_transitions_land_on_beat_boundaries_and_nowhere_else():
    """The cuts inside a beat are meant to be hard — that is what makes a
    montage a montage."""
    report = assembly.assemble(brief(visuals=stills(6), target_ticks=30 * SECOND))
    boundaries = {row["clips"][-1] for row in report.beats[:-1]}
    base = report.project.tracks[0]
    assert base.transitions, "this recipe declares a transition"
    for item in base.transitions:
        assert item.from_clip_id in boundaries


def test_a_recipe_with_no_transition_gets_hard_cuts():
    report = assembly.assemble(brief(recipe="quick_list"))
    assert report.project.tracks[0].transitions == []


# ── measuring what the owner changed ────────────────────────────────────────


def test_an_untouched_project_differs_from_itself_in_nothing():
    report = assembly.assemble(brief())
    delta = assembly.difference(report.project, report.project)
    assert delta["added"] == delta["removed"] == delta["moved"] == []
    assert delta["kept_share"] == 1.0


def test_the_diff_names_what_moved_what_went_and_what_arrived():
    """The signal any later "learn from what gets edited" has to be built on. A
    person who accepts a cut says nothing; a person who moves it says something
    specific, and this is the only place that gets written down."""
    report = assembly.assemble(brief())
    before = report.project
    clips = before.tracks[0].clips

    after = edits.remove_clip(before, clip_id=clips[-1].id)
    after = edits.set_property(after, clip_id=clips[0].id, name="scale", value=1.6)
    after = edits.add_clip(
        after, track_id=before.tracks[0].id, kind="solid",
        start=before.duration, duration=2 * SECOND, style={"colour": "#000000"},
    )

    delta = assembly.difference(before, after)
    assert delta["removed"] == [clips[-1].id]
    assert len(delta["added"]) == 1
    assert clips[0].id in delta["restyled"]
    assert 0 < delta["kept_share"] < 1
    assert delta["duration_after"] > delta["duration_before"]


def test_the_diff_notices_retiming_which_is_the_thing_a_recipe_gets_wrong():
    report = assembly.assemble(
        brief(visuals=[assembly.Visual("clip-1", "video", 60 * SECOND)], lines=[])
    )
    clip = report.project.tracks[0].clips[0]
    # A curve the recipe did not already apply — the hook beat asks for
    # `ramp_up`, so re-applying that one would be a change of nothing.
    after = edits.apply_speed_curve(report.project, clip_id=clip.id, preset="bullet")
    delta = assembly.difference(report.project, after)
    assert delta["retimed"] == [clip.id]
    assert delta["moved"] == []


def test_the_diff_notices_rewritten_words():
    report = assembly.assemble(brief())
    text = next(
        clip for track in report.project.tracks for clip in track.clips if clip.kind == "text"
    )
    after = edits.set_text(report.project, clip_id=text.id, text="Actually, this.")
    assert assembly.difference(report.project, after)["retexted"] == [text.id]


# ── the recipes themselves ──────────────────────────────────────────────────


def test_every_recipe_s_beats_add_up_to_the_whole_thing():
    for name, recipe in recipes.RECIPES.items():
        assert recipe.shares == pytest.approx(1.0, abs=0.001), name


def test_every_recipe_names_only_presets_that_exist():
    """A recipe pointing at an animation nobody declared is a recipe that fails
    on the one video somebody actually wanted."""
    from offsetx_apollo_builder.video import presets

    for name, recipe in recipes.RECIPES.items():
        assert recipe.family in recipes.RECIPE_FAMILIES, name
        if recipe.transition:
            presets.transition(recipe.transition)
        for beat in recipe.beats:
            if beat.animation:
                presets.animation(beat.animation)
            if beat.speed:
                presets.speed_curve(beat.speed)
            presets.text_style(beat.text_style)


def test_every_recipe_has_a_shape_rather_than_one_long_beat():
    for name, recipe in recipes.RECIPES.items():
        assert len(recipe.beats) >= 2, f"{name} is not a structure"
        assert max(beat.share for beat in recipe.beats) < 0.85, f"{name} is one beat wearing a hat"


def test_the_catalogue_carries_every_recipe_for_anything_that_searches():
    catalogue = recipes.catalogue()
    assert len(catalogue["recipes"]) == len(recipes.RECIPES)
    assert set(catalogue["recipe_families"]) == set(recipes.RECIPE_FAMILIES)
    assert catalogue["limits"]["min_target_ticks"] == recipes.MIN_TARGET_TICKS
