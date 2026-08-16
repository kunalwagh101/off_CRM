"""Material in, finished timeline out.

The centre of the brief this editor was built for: *"CapCut, but it does it
automatically."* Given some pictures, some footage, a piece of music and the
words, this produces a whole project — cut, animated, captioned, scored — that
the export gates accept without anybody touching the timeline.

---

**What it is not.** It is not a model. `recipes.py` explains why in full; the
short version is that a model which emits a timeline emits invalid ones, and
every invariant this project enforces would become a suggestion. A model picks
the recipe and writes the words. This does the arithmetic.

**Everything goes through :mod:`edits`.** Not one clip is constructed directly.
An assembled project is valid for exactly the same reason a hand-made one is —
it was built by the same functions, and they refuse the same things. That costs
a copy of the document per operation and buys the property the whole feature
rests on.

**It is reproducible.** The same brief and the same seed produce the same
project, to the tick. That matters twice over: an owner who re-runs an assembly
after changing one line gets a diff they can read, and :func:`difference` can
then measure what the owner changed — which is the signal any later "learn from
what gets edited" has to be built on.

**The duration is exact.** The export gate checks a rendered file against the
project's length, so a target of thirty seconds has to produce a project of
exactly thirty seconds — snapped to a whole frame, with the last beat absorbing
whatever the shares round away. A timeline that is 29.97s because the fractions
did not add up is a timeline whose export fails a gate for no reason anyone can
see.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from . import edits, recipes
from .captions import READABLE_CPS
from .timeline import (
    MAX_SPEED,
    MIN_CLIP_TICKS,
    MIN_SPEED,
    TICKS_PER_SECOND,
    Project,
    TimelineError,
    new_project,
    ticks_per_frame,
)

#: How much of a still's own slot a fade takes at each end, when the recipe asks
#: for no transition and a hard cut would be too hard.
MUSIC_FADE_TICKS = 45_000


@dataclass
class Visual:
    """A picture or a piece of footage the assembler may use.

    ``source_ticks`` is how long the material actually is — zero for a still,
    which can be held for any length. It is the number that decides whether a
    clip can fill the slot it is given, so it is required rather than inferred.
    """

    asset_id: str
    kind: str = "image"
    source_ticks: int = 0
    width: int = 0
    height: int = 0

    @property
    def unbounded(self) -> bool:
        return self.kind == "image"

    @property
    def longest_slot(self) -> int:
        """The longest stretch one clip of this can fill.

        A still can be held forever. Footage runs out, but it can be slowed
        down: at the slowest speed the timeline allows it covers ten times its
        own length, and past that it needs a second cut.
        """
        if self.unbounded:
            return MAX_TARGET_TICKS
        return int(self.source_ticks / MIN_SPEED)


@dataclass
class Sound:
    """A piece of audio: music under the whole thing, or a voice over it."""

    asset_id: str
    source_ticks: int


MAX_TARGET_TICKS = recipes.MAX_TARGET_TICKS


@dataclass
class AssemblyBrief:
    """Everything the assembler is allowed to use, and what it is aiming at."""

    name: str
    recipe: str
    visuals: list[Visual]
    target_ticks: int
    lines: list[str] = field(default_factory=list)
    music: Sound | None = None
    voice: Sound | None = None
    preset: str = "vertical"
    fps: str = "30"
    #: The same seed and the same brief give the same project, to the tick.
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "recipe": self.recipe,
            "target_ticks": self.target_ticks,
            "visuals": [
                {
                    "asset_id": item.asset_id,
                    "kind": item.kind,
                    "source_ticks": item.source_ticks,
                }
                for item in self.visuals
            ],
            "lines": list(self.lines),
            "music": self.music.asset_id if self.music else "",
            "voice": self.voice.asset_id if self.voice else "",
            "preset": self.preset,
            "fps": self.fps,
            "seed": self.seed,
        }


@dataclass
class AssemblyReport:
    """The project, and an account of what the assembler had to settle for."""

    project: Project
    #: One row per beat: where it landed, what went in it, what was applied.
    beats: list[dict[str, Any]] = field(default_factory=list)
    #: Compromises, in words. A brief that could not be met exactly is not a
    #: failure — but it must not be silent either.
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "duration_ticks": self.project.duration,
            "beats": list(self.beats),
            "notes": list(self.notes),
        }


class AssemblyRefused(TimelineError):
    """The brief cannot be built. Said with the numbers, never approximated."""


# ── dividing time ───────────────────────────────────────────────────────────


def _split(total: int, parts: int) -> list[int]:
    """``total`` divided into ``parts``, summing to exactly ``total``.

    The remainder goes to the last part rather than being spread, because a
    beat's *shape* matters more than a few ticks and the alternative is every
    part being a different length for no reason a viewer could name.
    """
    if parts <= 1:
        return [total]
    each = total // parts
    spans = [each] * parts
    spans[-1] = total - each * (parts - 1)
    return spans


def _beat_spans(total: int, recipe: recipes.Recipe) -> list[int]:
    """The target divided among the beats, in their declared proportions."""
    shares = [beat.share for beat in recipe.beats]
    weight = sum(shares) or 1.0
    spans = [int(total * share / weight) for share in shares]
    # Whatever the rounding lost goes to the last beat, so the sum is exact.
    spans[-1] = total - sum(spans[:-1])
    return spans


def _snap(ticks: int, fps: str) -> int:
    """The nearest whole frame, at or above the minimum.

    The export gate compares a rendered file's length against the project's, and
    a project whose length is not a whole number of frames is one the exporter
    cannot hit — it would fail a gate for a reason nobody could see.
    """
    per = ticks_per_frame(fps)
    frames = max(1, int(round(ticks / per)))
    return int(round(frames * per))


# ── the assembler ───────────────────────────────────────────────────────────


def assemble(brief: AssemblyBrief) -> AssemblyReport:
    """Build the whole project.

    Refuses rather than approximating: a brief with no pictures, or a target
    this material cannot cover, comes back as a sentence with the numbers in it.
    """
    recipe = recipes.recipe(brief.recipe)
    if not brief.visuals:
        raise AssemblyRefused(
            "There is nothing to show. An assembly needs at least one picture or "
            "one piece of footage; the words and the music go over something."
        )
    if brief.target_ticks < recipes.MIN_TARGET_TICKS:
        raise AssemblyRefused(
            f"A target of {brief.target_ticks / TICKS_PER_SECOND:.2f}s is below the "
            f"{recipes.MIN_TARGET_TICKS / TICKS_PER_SECOND:.0f}s floor. Below it the "
            "beats round away to nothing and the shape stops being a shape."
        )
    if brief.target_ticks > recipes.MAX_TARGET_TICKS:
        raise AssemblyRefused(
            f"A target of {brief.target_ticks / TICKS_PER_SECOND:.0f}s is past the "
            f"{recipes.MAX_TARGET_TICKS / TICKS_PER_SECOND:.0f}s ceiling."
        )

    total = _snap(brief.target_ticks, brief.fps)
    notes: list[str] = []
    if total != brief.target_ticks:
        notes.append(
            f"Rounded to {total / TICKS_PER_SECOND:.3f}s, the nearest whole frame at "
            f"{brief.fps}fps. An export cannot stop between two frames."
        )

    project = new_project(name=brief.name, preset=brief.preset, fps=brief.fps)
    base = project.tracks[0]
    music_track = project.tracks[1]
    project = edits.set_track(project, track_id=base.id, name="Base")
    project = edits.set_track(project, track_id=music_track.id, name="Music")
    project = edits.add_track(project, kind="video", name="Text")
    text_track = project.tracks[-1]

    dice = random.Random(brief.seed)
    pool = list(brief.visuals)
    # A stable rotation rather than a shuffle: the order material arrives in is
    # usually the order somebody put it in, and an assembly that reorders it for
    # no reason is one they have to undo before they can start.
    if brief.seed:
        dice.shuffle(pool)

    spans = _beat_spans(total, recipe)
    lines = _assign_lines(brief.lines, len(recipe.beats))
    cursor = 0
    index = 0
    report_beats: list[dict[str, Any]] = []

    for beat, span in zip(recipe.beats, spans):
        project, count, index = _lay_beat(
            project,
            beat=beat,
            span=span,
            start=cursor,
            pool=pool,
            index=index,
            track_id=base.id,
            notes=notes,
        )
        clip_ids = [clip.id for clip in project.track(base.id).clips][-count:]
        project = _decorate(project, beat, clip_ids, _kinds_of(project, clip_ids), notes)
        project = _lay_lines(
            project,
            track_id=text_track.id,
            lines=lines[len(report_beats)],
            start=cursor,
            span=span,
            style=beat.text_style,
            notes=notes,
        )
        report_beats.append(
            {
                "name": beat.name,
                "start": cursor,
                "duration": span,
                "clips": clip_ids,
                "animation": beat.animation,
                "speed": beat.speed,
                "lines": list(lines[len(report_beats)]),
            }
        )
        cursor += span

    project = _join_beats(project, base.id, recipe, report_beats, notes)
    project = _lay_sound(project, music_track.id, brief, recipe, total, notes)

    if project.duration != total:
        # Nothing should be able to do this, and if something does it has to be
        # loud: an export gated on the project's own length would fail with no
        # explanation anyone could act on.
        raise AssemblyRefused(
            f"Assembly produced {project.duration} ticks against a target of {total}. "
            "This is a bug in the assembler, not in the brief."
        )
    return AssemblyReport(project=project, beats=report_beats, notes=notes)


def _kinds_of(project: Project, clip_ids: list[str]) -> dict[str, str]:
    """Which kind each of these clips turned out to be."""
    kinds: dict[str, str] = {}
    for track in project.tracks:
        for clip in track.clips:
            if clip.id in clip_ids:
                kinds[clip.id] = clip.kind
    return kinds


def _assign_lines(lines: list[str], beats: int) -> list[list[str]]:
    """Spread the words over the beats, in order.

    Round-robin rather than one-per-beat: a script with two lines and five beats
    should put them at the start and the middle, not leave three beats holding
    nothing while the last two share everything.
    """
    buckets: list[list[str]] = [[] for _ in range(beats)]
    if not lines:
        return buckets
    for position, line in enumerate(lines):
        buckets[int(position * beats / len(lines))].append(line)
    return buckets


def _lay_beat(
    project: Project,
    *,
    beat: recipes.Beat,
    span: int,
    start: int,
    pool: list[Visual],
    index: int,
    track_id: str,
    notes: list[str],
) -> tuple[Project, int, int]:
    """Fill one beat with clips. Returns the project, how many it took, and
    where the pool has got to."""
    count = _clip_count(beat, span, pool, index, notes)
    spans = _split(span, count)
    at = start
    for slot in spans:
        visual = pool[index % len(pool)]
        index += 1
        speed = _speed_for(visual, slot)
        params: dict[str, Any] = {
            "track_id": track_id,
            "kind": visual.kind,
            "start": at,
            "duration": slot,
            "asset_id": visual.asset_id,
            "style": {
                "fit": "cover",
                "source_width": visual.width,
                "source_height": visual.height,
            },
        }
        if not visual.unbounded:
            params["source_duration"] = visual.source_ticks
            params["speed"] = speed
        project = edits.add_clip(project, **params)
        at += slot
    return project, count, index


def _clip_count(
    beat: recipes.Beat, span: int, pool: list[Visual], index: int, notes: list[str]
) -> int:
    """How many cuts this beat gets.

    The recipe asks for a range; the material decides inside it. A beat longer
    than one piece of footage can stretch to needs more cuts whatever the recipe
    wanted, and a beat too short to hold that many needs fewer.
    """
    count = max(beat.min_clips, min(beat.max_clips, len(pool)))
    count = max(1, min(count, span // MIN_CLIP_TICKS or 1))

    # Grow until every slot is one its material can actually fill. Bounded by
    # the beat's own length, which is what makes this terminate.
    ceiling = max(1, span // MIN_CLIP_TICKS)
    while count < ceiling:
        # The *longest* slot, not the average: `_split` gives the remainder to
        # the last one, so checking the average lets a clip through that the
        # last slot would then be too long for.
        slot = max(_split(span, count))
        if all(
            pool[(index + step) % len(pool)].longest_slot >= slot for step in range(count)
        ):
            break
        count += 1

    slot = max(_split(span, count))
    short = [
        pool[(index + step) % len(pool)]
        for step in range(count)
        if pool[(index + step) % len(pool)].longest_slot < slot
    ]
    if short:
        notes.append(
            f"The {beat.name} beat is {span / TICKS_PER_SECOND:.2f}s and its footage "
            f"cannot stretch that far even at {MIN_SPEED}x. It is cut "
            f"{count} times and the shortest piece still falls short — trim the beat "
            "or give it more material."
        )
    return count


def _speed_for(visual: Visual, slot: int) -> float:
    """How fast a clip must read to fill its slot exactly.

    Slower than 1 stretches short material over a long slot, which is what slow
    motion is. Faster than 1 is never chosen here: speeding footage up to fill a
    slot means throwing material away, and the assembler has no way to know
    which part mattered.
    """
    if visual.unbounded or slot <= 0:
        return 1.0
    rate = visual.source_ticks / slot
    if rate >= 1.0:
        return 1.0
    # Rounded *down*, never to nearest. The rate is stored to four places, and
    # rounding the last one upward makes the clip consume a handful of ticks
    # more than the source has — a real refusal, from a number that was only
    # ever an approximation of "exactly fills the slot".
    return max(MIN_SPEED, min(MAX_SPEED, math.floor(rate * 10_000) / 10_000))


def _decorate(
    project: Project,
    beat: recipes.Beat,
    clip_ids: list[str],
    kinds: dict[str, str],
    notes: list[str],
) -> Project:
    """Animations and speed curves, where they fit.

    A speed curve consumes more material than a flat rate — that is the whole
    point of one — so it is applied only where there is material to spare. A
    clip already reading to the end of its source keeps its flat rate rather
    than being refused, because a beat losing its animation is worse than a beat
    losing its curve.
    """
    for clip_id in clip_ids:
        if beat.animation:
            try:
                project = edits.apply_animation(project, clip_id=clip_id, preset=beat.animation)
            except TimelineError as exc:
                notes.append(f"No {beat.animation} on {clip_id}: {exc}")
        if beat.speed and kinds.get(clip_id) == "video":
            try:
                project = edits.apply_speed_curve(project, clip_id=clip_id, preset=beat.speed)
            except TimelineError:
                notes.append(
                    f"The {beat.name} beat asked for a {beat.speed} curve and {clip_id} "
                    "has no material to spare for one. It plays at a flat rate."
                )
    return project


def _lay_lines(
    project: Project,
    *,
    track_id: str,
    lines: list[str],
    start: int,
    span: int,
    style: str,
    notes: list[str],
) -> Project:
    """Put this beat's words on the text track, sharing the beat between them."""
    if not lines:
        return project
    spans = _split(span, len(lines))
    at = start
    for line, slot in zip(lines, spans):
        if slot < MIN_CLIP_TICKS:
            notes.append(f"No room for {line!r}: {len(lines)} lines in one beat is too many.")
            at += slot
            continue
        # The same reading speed the caption engine measures against, because a
        # line nobody can read is the same problem whether a model transcribed
        # it or a person typed it. Reported rather than fixed: the fix is fewer
        # words or a longer beat, and only whoever wrote them can pick.
        pace = len(line) / (slot / TICKS_PER_SECOND)
        if pace > READABLE_CPS:
            notes.append(
                f"{line!r} is on screen for {slot / TICKS_PER_SECOND:.2f}s — "
                f"{pace:.0f} characters a second against a readable {READABLE_CPS}. "
                "Fewer words, or a longer beat."
            )
        project = edits.add_clip(
            project,
            track_id=track_id,
            kind="text",
            start=at,
            duration=slot,
            text=line,
        )
        clip_id = project.track(track_id).clips[-1].id
        project = edits.apply_text_style(project, clip_id=clip_id, style=style)
        at += slot
    return project


def _join_beats(
    project: Project,
    track_id: str,
    recipe: recipes.Recipe,
    beats: list[dict[str, Any]],
    notes: list[str],
) -> Project:
    """Put the recipe's transition on every beat boundary that can take one.

    Boundaries only — the cuts *inside* a beat are meant to be hard, which is
    what makes a montage a montage. A boundary where the halves do not fit
    inside their clips is skipped rather than shortened, because a transition
    that quietly became a tenth of its length is worse than a clean cut.
    """
    if not recipe.transition:
        return project
    skipped = 0
    for earlier in beats[:-1]:
        if not earlier["clips"]:
            continue
        try:
            project = edits.add_transition(
                project,
                clip_id=earlier["clips"][-1],
                preset=recipe.transition,
                duration=recipe.transition_ticks,
                side="after",
            )
        except TimelineError:
            skipped += 1
    if skipped:
        notes.append(
            f"{skipped} beat boundary(s) took a hard cut instead of a "
            f"{recipe.transition}: the clips either side are too short to give it room."
        )
    return project


def _lay_sound(
    project: Project,
    music_track_id: str,
    brief: AssemblyBrief,
    recipe: recipes.Recipe,
    total: int,
    notes: list[str],
) -> Project:
    """Music under the whole thing, and a voice over it if there is one."""
    if brief.voice:
        project = edits.add_track(project, kind="audio", name="Voice")
        voice_track = project.tracks[-1]
        span = min(total, brief.voice.source_ticks)
        if span < total:
            notes.append(
                f"The voiceover is {span / TICKS_PER_SECOND:.2f}s against a "
                f"{total / TICKS_PER_SECOND:.2f}s video, so the tail plays without it."
            )
        project = edits.add_clip(
            project,
            track_id=voice_track.id,
            kind="audio",
            start=0,
            duration=max(MIN_CLIP_TICKS, span),
            asset_id=brief.voice.asset_id,
            source_duration=brief.voice.source_ticks,
        )

    if not brief.music:
        notes.append(
            "There is no music. Most platforms bury a silent video, and the "
            "export will say so too."
        )
        return project

    span = min(total, brief.music.source_ticks)
    if span < total:
        notes.append(
            f"The music is {span / TICKS_PER_SECOND:.2f}s against a "
            f"{total / TICKS_PER_SECOND:.2f}s video, so the tail is silent. Looping "
            "is not built — a loop with an audible seam is worse than a fade."
        )
    project = edits.add_clip(
        project,
        track_id=music_track_id,
        kind="audio",
        start=0,
        duration=max(MIN_CLIP_TICKS, span),
        asset_id=brief.music.asset_id,
        source_duration=brief.music.source_ticks,
    )
    clip_id = project.track(music_track_id).clips[-1].id
    gain = recipe.music_gain if brief.voice else recipe.music_gain_alone
    project = edits.set_property(project, clip_id=clip_id, name="volume", value=gain)
    fade = min(MUSIC_FADE_TICKS, span // 4)
    if fade > 0:
        project = edits.set_fade(project, clip_id=clip_id, fade_in=fade, fade_out=fade)
    return project


# ── what the owner changed ──────────────────────────────────────────────────


def difference(before: Project, after: Project) -> dict[str, Any]:
    """What changed between an assembled project and the edited one.

    The measurement the whole idea of an assembler that improves rests on. A
    person who accepts a cut is saying nothing; a person who moves it is saying
    something specific, and this is the only place that gets written down.

    Deliberately coarse. It counts what was added, removed, retimed and
    restyled — not a per-property delta, which would drown the signal in
    somebody nudging a slider by a hundredth.
    """
    old = {clip.id: clip for track in before.tracks for clip in track.clips}
    new = {clip.id: clip for track in after.tracks for clip in track.clips}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    moved: list[str] = []
    retimed: list[str] = []
    restyled: list[str] = []
    retexted: list[str] = []

    for clip_id in sorted(set(old) & set(new)):
        was, now = old[clip_id], new[clip_id]
        if was.start != now.start or was.duration != now.duration:
            moved.append(clip_id)
        if (
            was.speed != now.speed
            or was.reversed != now.reversed
            or [(f.at, f.value) for f in was.speed_curve]
            != [(f.at, f.value) for f in now.speed_curve]
        ):
            retimed.append(clip_id)
        if was.style != now.style or was.properties != now.properties:
            restyled.append(clip_id)
        if was.text != now.text:
            retexted.append(clip_id)

    kept = len(set(old) & set(new)) - len(moved) - len(removed)
    return {
        "added": added,
        "removed": removed,
        "moved": moved,
        "retimed": retimed,
        "restyled": restyled,
        "retexted": retexted,
        "duration_before": before.duration,
        "duration_after": after.duration,
        "untouched": max(0, kept),
        # One number for "how much of what it made survived", which is the thing
        # a scoreboard would actually track.
        "kept_share": round(max(0, kept) / len(old), 4) if old else 0.0,
    }
