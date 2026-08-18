"""Every edit that can be made to a timeline, as a pure function.

One operation, one function, one name. The name is what the browser sends and
what the history stores, so an edit is a thing that can be listed, replayed and
argued with after the fact rather than a mutation that happened somewhere in a
component.

**Default-deny, like every other registry here.** :data:`OPERATIONS` is the
complete set, and :func:`apply` refuses a name that is not in it. An editor that
accepted an unknown operation and did nothing would report success for an edit
that never happened, and the user would find out at export.

**Every operation copies before it changes anything.** The copy goes through
``to_dict`` → ``from_dict``, which is slower than mutating in place and is worth
it twice over: an edit that produces a document that cannot be serialised fails
on the spot instead of at save time, and an operation that would leave two clips
overlapping cannot half-apply — the original is still intact when it raises.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from . import effects as fx
from . import presets
from .timeline import (
    BLEND_MODES,
    EASINGS,
    MIN_CLIP_TICKS,
    PRESETS,
    TRACK_KINDS,
    Clip,
    Keyframe,
    Marker,
    Project,
    TimelineError,
    Track,
    _assert_editable,
    _assert_no_overlap,
    _check_property,
    _clamp,
    _new_id,
    _validate_clip,
    frame_rate,
    interpolate,
    Transition,
    _assert_transitions_fit,
    prune_transitions,
)


#: How long a freeze lasts when nobody says. Two seconds is long enough to read
#: as deliberate and short enough that nobody has to trim it.
DEFAULT_FREEZE_TICKS = 180_000


def _copy(project: Project) -> Project:
    return Project.from_dict(project.to_dict())


def _commit(project: Project, track: Track) -> Project:
    """Re-sort and re-check one track after it has been changed."""
    track.clips.sort(key=lambda clip: clip.start)
    _assert_no_overlap(track)
    # A transition describes a cut. An edit that moved either side has destroyed
    # that cut, so the transition goes with it rather than lingering as a ghost
    # that reappears if the clips ever line up again.
    track.transitions = prune_transitions(track)
    _assert_transitions_fit(track)
    return project


def _easing_at(frames: list[Keyframe], offset: int) -> str:
    """The easing governing the segment that ``offset`` falls inside."""
    easing = frames[0].easing
    for frame in frames:
        if frame.at <= offset:
            easing = frame.easing
    return easing


def _resample_keyframes(frames: list[Keyframe], *, start: int, end: int) -> list[Keyframe]:
    """The animation of a sub-range of a clip, re-based to start at zero.

    This is what makes splitting and trimming keep an animation continuous. Cut
    a clip in the middle of a zoom and the two halves have to carry on from
    exactly where the cut was — a naive shift leaves the second half restarting
    from its first keyframe's value, which shows up as a jump at every cut, on
    the frame the viewer is most likely to be looking at.

    **The keyframes are shifted, not rebuilt.** An earlier version synthesised a
    keyframe at each boundary from the interpolated value, which is exact for a
    linear segment and wrong for every other kind: a sub-range of an ease-out
    curve is not itself an ease-out curve, so re-easing the halves changed the
    shape between the samples. Splitting a clip mid-ease visibly altered the
    animation, and the test that should have caught it happened to use a linear
    segment.

    Shifting every keyframe by ``start`` reproduces the original curve exactly,
    because the curve is defined by the same control points measured from a new
    origin. Keyframes outside the range are then dropped **except** the nearest
    one on each side, which are the two that anchor the interpolation at the
    boundaries. Exact, and bounded — a clip split fifty times does not carry
    fifty times the keyframes.
    """
    if not frames:
        return []
    ordered = sorted(frames, key=lambda item: item.at)
    inside = [frame for frame in ordered if start <= frame.at <= end]
    before = [frame for frame in ordered if frame.at < start]
    after = [frame for frame in ordered if frame.at > end]

    kept = list(inside)
    if before:
        kept.insert(0, before[-1])
    if after:
        kept.append(after[0])
    if not kept:
        kept = [ordered[0]]

    return [
        Keyframe(frame.at - start, frame.value, frame.easing)
        for frame in sorted(kept, key=lambda item: item.at)
    ]


def _resample_clip_keyframes(
    clip: Clip, *, start: int, end: int
) -> dict[str, list[Keyframe]]:
    return {
        name: _resample_keyframes(frames, start=start, end=end)
        for name, frames in clip.keyframes.items()
        if frames
    }


def _scale_keyframes(clip: Clip, *, factor: float) -> dict[str, list[Keyframe]]:
    """Stretch or squeeze an animation to a clip's new length.

    Used when speed changes the clip's duration: the animation was drawn against
    the clip, so it has to travel with it or a zoom keyed to the last frame ends
    up somewhere in the middle.
    """
    if factor == 1.0:
        return {name: list(frames) for name, frames in clip.keyframes.items()}
    return {
        name: [
            Keyframe(max(0, int(round(frame.at * factor))), frame.value, frame.easing)
            for frame in frames
        ]
        for name, frames in clip.keyframes.items()
    }


# ── tracks ──────────────────────────────────────────────────────────────────


def add_track(project: Project, *, kind: str = "video", name: str = "", index: int = -1) -> Project:
    if kind not in TRACK_KINDS:
        raise TimelineError(f"Unknown track kind {kind!r}. Known: {', '.join(TRACK_KINDS)}.")
    result = _copy(project)
    existing = sum(1 for track in result.tracks if track.kind == kind)
    track = Track(id=_new_id("track"), kind=kind, name=name or f"{kind.title()} {existing + 1}")
    if index < 0 or index >= len(result.tracks):
        result.tracks.append(track)
    else:
        result.tracks.insert(index, track)
    return result


def remove_track(project: Project, *, track_id: str) -> Project:
    result = _copy(project)
    track = result.track(track_id)
    _assert_editable(track)
    if len(result.tracks) <= 1:
        raise TimelineError("A project needs at least one track.")
    result.tracks = [item for item in result.tracks if item.id != track_id]
    return result


def move_track(project: Project, *, track_id: str, index: int) -> Project:
    """Reorder a track, which for video tracks means reordering what draws on top."""
    result = _copy(project)
    track = result.track(track_id)
    result.tracks = [item for item in result.tracks if item.id != track_id]
    position = max(0, min(len(result.tracks), int(index)))
    result.tracks.insert(position, track)
    return result


def set_track(
    project: Project,
    *,
    track_id: str,
    name: str | None = None,
    locked: bool | None = None,
    muted: bool | None = None,
    hidden: bool | None = None,
) -> Project:
    """Rename, lock, mute or hide.

    Locking is checked by every other operation, so it is deliberately the one
    thing that can be changed *on* a locked track — otherwise a lock could never
    be undone.
    """
    result = _copy(project)
    track = result.track(track_id)
    if name is not None:
        track.name = str(name)[:80]
    if locked is not None:
        track.locked = bool(locked)
    if muted is not None:
        track.muted = bool(muted)
    if hidden is not None:
        track.hidden = bool(hidden)
    return result


# ── clips ───────────────────────────────────────────────────────────────────


def add_clip(
    project: Project,
    *,
    track_id: str,
    kind: str,
    start: int,
    duration: int,
    asset_id: str = "",
    source_duration: int = 0,
    in_point: int = 0,
    text: str = "",
    label: str = "",
    speed: float = 1.0,
    style: Mapping[str, Any] | None = None,
    properties: Mapping[str, float] | None = None,
) -> Project:
    result = _copy(project)
    track = result.track(track_id)
    _assert_editable(track)
    clip = Clip(
        id=_new_id("clip"),
        kind=str(kind),
        start=max(0, int(start)),
        duration=int(duration),
        in_point=max(0, int(in_point)),
        source_duration=max(0, int(source_duration)),
        asset_id=str(asset_id or ""),
        text=str(text or ""),
        label=str(label or "")[:120],
        # `float(speed or 1.0)` would turn a speed deliberately set to 0 — a
        # freeze — back into normal playback, silently. The same shape of bug
        # once restarted a paused campaign.
        speed=1.0 if speed is None else float(speed),
        style=dict(style or {}),
        properties={
            _check_property(name): _clamp(_check_property(name), value)
            for name, value in (properties or {}).items()
        },
    )
    _validate_clip(clip, track)
    track.clips.append(clip)
    return _commit(result, track)


def remove_clip(project: Project, *, clip_id: str) -> Project:
    """Delete a clip and leave a gap. See :func:`ripple_delete` for the other one."""
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    track.clips = [item for item in track.clips if item.id != clip_id]
    return _commit(result, track)


def ripple_delete(project: Project, *, clip_id: str) -> Project:
    """Delete a clip and close the gap behind it.

    Only on its own track. Rippling every track is how a "helpful" edit silently
    desynchronises a voiceover from the pictures it was cut against — the other
    tracks did not ask to move.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    span = clip.duration
    at = clip.start
    track.clips = [item for item in track.clips if item.id != clip_id]
    for item in track.clips:
        if item.start >= at:
            item.start -= span
    return _commit(result, track)


def insert_gap(project: Project, *, track_id: str, at: int, duration: int) -> Project:
    """Push everything from ``at`` onwards later, to make room."""
    result = _copy(project)
    track = result.track(track_id)
    _assert_editable(track)
    span = int(duration)
    if span <= 0:
        raise TimelineError("A gap must be longer than nothing.")
    for clip in track.clips:
        if clip.start >= int(at):
            clip.start += span
        elif clip.end > int(at):
            raise TimelineError(
                f"Tick {at} is in the middle of clip {clip.id!r}. Split it first, "
                "or insert the gap at a cut."
            )
    return _commit(result, track)


def move_clip(project: Project, *, clip_id: str, start: int, track_id: str = "") -> Project:
    """Drag a clip, possibly to another track."""
    result = _copy(project)
    source, clip = result.find_clip(clip_id)
    _assert_editable(source)
    target = result.track(track_id) if track_id and track_id != source.id else source
    if target is not source:
        _assert_editable(target)
    moved = Clip(**{**clip.__dict__, "start": max(0, int(start))})
    _validate_clip(moved, target)
    source.clips = [item for item in source.clips if item.id != clip_id]
    target.clips.append(moved)
    if target is not source:
        _commit(result, source)
    return _commit(result, target)


def split_clip(project: Project, *, clip_id: str, at: int) -> Project:
    """Cut one clip into two at ``at``.

    The right-hand piece keeps reading from where the left one stopped, scaled by
    the clip's speed. Getting that wrong is invisible at 1× and obvious the first
    time anyone splits a slowed-down clip.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    point = int(at)
    if not (clip.start < point < clip.end):
        raise TimelineError(
            f"Tick {point} is not inside clip {clip_id!r} "
            f"({clip.start}–{clip.end}). There is nothing there to cut."
        )
    left_span = point - clip.start
    right_span = clip.end - point

    # Fresh containers on both halves: they both outlive the split, and sharing
    # a dict would make setting a property on one change the other.
    left = Clip(
        **{
            **clip.__dict__,
            "duration": left_span,
            "properties": dict(clip.properties),
            "style": dict(clip.style),
            "keyframes": _resample_clip_keyframes(clip, start=0, end=left_span),
        }
    )
    right = Clip(
        **{
            **clip.__dict__,
            "id": _new_id("clip"),
            "start": point,
            "duration": right_span,
            "in_point": clip.in_point + int(round(left_span * clip.speed)),
            "properties": dict(clip.properties),
            "style": dict(clip.style),
            "keyframes": _resample_clip_keyframes(clip, start=left_span, end=clip.duration),
        }
    )
    # A fade belongs to the edge it was set on. The head fade stays with the left
    # piece and the tail fade with the right, or a split in the middle of a clip
    # would give both halves both fades and dip the picture at the cut.
    left.fade_out = 0
    right.fade_in = 0
    left.fade_in = min(clip.fade_in, left_span)
    right.fade_out = min(clip.fade_out, right_span)

    _validate_clip(left, track)
    _validate_clip(right, track)
    track.clips = [item for item in track.clips if item.id != clip_id]
    track.clips.extend((left, right))
    return _commit(result, track)


def trim_clip(project: Project, *, clip_id: str, head: int = 0, tail: int = 0) -> Project:
    """Drag an edge. Positive shortens, negative lengthens.

    Trimming the head moves the in-point with it, which is the whole reason
    ``start`` and ``in_point`` are separate fields: the clip moves on the
    timeline and reads from further into its material, and the material is never
    touched.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    head_ticks, tail_ticks = int(head), int(tail)
    trimmed = Clip(
        **{
            **clip.__dict__,
            "start": clip.start + head_ticks,
            "duration": clip.duration - head_ticks - tail_ticks,
            "in_point": clip.in_point + int(round(head_ticks * clip.speed)),
            "properties": dict(clip.properties),
            "style": dict(clip.style),
            # Keyframes are anchored to the material, so trimming the head moves
            # them with it. Leaving them where they were would slide the whole
            # animation later by however much was trimmed.
            "keyframes": _resample_clip_keyframes(
                clip, start=head_ticks, end=clip.duration - tail_ticks
            ),
        }
    )
    if trimmed.start < 0:
        raise TimelineError("Trimming that far would push the clip before the timeline starts.")
    trimmed.fade_in = min(clip.fade_in, trimmed.duration)
    trimmed.fade_out = min(clip.fade_out, max(0, trimmed.duration - trimmed.fade_in))
    _validate_clip(trimmed, track)
    track.clips = [trimmed if item.id == clip_id else item for item in track.clips]
    return _commit(result, track)


def duplicate_clip(project: Project, *, clip_id: str, start: int = -1) -> Project:
    """Copy a clip, landing after the original unless told otherwise."""
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    copy = Clip(
        **{
            **clip.__dict__,
            "id": _new_id("clip"),
            "start": clip.end if int(start) < 0 else max(0, int(start)),
            "keyframes": {name: list(frames) for name, frames in clip.keyframes.items()},
            "properties": dict(clip.properties),
            "style": dict(clip.style),
        }
    )
    _validate_clip(copy, track)
    track.clips.append(copy)
    return _commit(result, track)


def set_speed(project: Project, *, clip_id: str, speed: float, keep_duration: bool = False) -> Project:
    """Change how fast a clip plays.

    By default the clip's *material* is held and its length on the timeline
    changes — playing the same footage at 2× takes half as long. With
    ``keep_duration`` the length is held and the material consumed changes
    instead, which is what you want when a clip has to fit a slot.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    rate = float(speed)
    # One rate replaces a curve rather than arguing with it. A clip cannot be at
    # 2x *and* on a hero ramp, and keeping the curve silently would make the
    # number in the box a lie. A rate of 0 is a freeze, which has no length to
    # solve for, so it always keeps the clip's own.
    if keep_duration or clip.source_duration <= 0 or rate == 0:
        changed = Clip(
            **{**clip.__dict__, "speed": rate, "speed_curve": [], "properties": dict(clip.properties)}
        )
    else:
        consumed = int(round(clip.consumed(clip.duration)))
        span = max(1, int(round(consumed / rate)))
        changed = Clip(
            **{
                **clip.__dict__,
                "speed": rate,
                "speed_curve": [],
                "duration": span,
                "properties": dict(clip.properties),
                "keyframes": _scale_keyframes(clip, factor=span / clip.duration if clip.duration else 1.0),
            }
        )
    changed.fade_in = min(changed.fade_in, changed.duration)
    changed.fade_out = min(changed.fade_out, max(0, changed.duration - changed.fade_in))
    _validate_clip(changed, track)
    track.clips = [changed if item.id == clip_id else item for item in track.clips]
    return _commit(result, track)


def apply_speed_curve(
    project: Project, *, clip_id: str, preset: str, keep_duration: bool = True
) -> Project:
    """Give a clip a speed that changes over its own length.

    The clip keeps its slot on the timeline and reads a different amount of
    material — which is the whole point, and also the thing that can fail: a
    ``hero`` ramp averages more than 1×, so a clip already reading to the end of
    its source will not fit. The validator says so with the numbers rather than
    letting it read past the end.

    With ``keep_duration=False`` the clip is stretched or squeezed so it consumes
    exactly what it consumed before, which is how to put a curve on a clip that
    is already using all the material it has.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind not in ("video", "audio"):
        raise TimelineError(
            f"A {clip.kind} clip has no material to read at a rate, so a speed "
            "curve would do nothing to it."
        )

    before = clip.consumed(clip.duration)
    points = [Keyframe.from_dict(item) for item in presets.speed_points_for(preset, clip.duration)]
    changed = Clip(**{**clip.__dict__, "speed": 1.0, "speed_curve": points})

    if not keep_duration and clip.source_duration > 0 and before > 0:
        # Solve for the length at which this curve consumes what the clip used
        # to. The curve is defined on fractions of the clip, so its average rate
        # is the same whatever the length — which makes this a division and not
        # a search.
        average = presets.speed_curve(preset).average
        span = max(MIN_CLIP_TICKS, int(round(before / average))) if average > 0 else clip.duration
        points = [Keyframe.from_dict(item) for item in presets.speed_points_for(preset, span)]
        changed = Clip(
            **{
                **clip.__dict__,
                "speed": 1.0,
                "speed_curve": points,
                "duration": span,
                "properties": dict(clip.properties),
                "keyframes": _scale_keyframes(clip, factor=span / clip.duration if clip.duration else 1.0),
            }
        )
        changed.fade_in = min(changed.fade_in, changed.duration)
        changed.fade_out = min(changed.fade_out, max(0, changed.duration - changed.fade_in))

    _validate_clip(changed, track)
    track.clips = [changed if item.id == clip_id else item for item in track.clips]
    return _commit(result, track)


def clear_speed_curve(project: Project, *, clip_id: str) -> Project:
    """Back to one rate. The clip keeps its slot and its `speed`."""
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    changed = Clip(**{**clip.__dict__, "speed_curve": []})
    _validate_clip(changed, track)
    track.clips = [changed if item.id == clip_id else item for item in track.clips]
    return result


def reverse_clip(project: Project, *, clip_id: str, reversed: bool | None = None) -> Project:
    """Play the material backwards. Called with no argument it toggles.

    Only the reading direction changes: the clip keeps its slot, its length and
    its speed curve, and reads the same span of material from the far end. That
    is why this is a flag rather than a negative speed — a negative speed would
    make every other piece of arithmetic in the timeline signed for the sake of
    one clip.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind != "video":
        raise TimelineError(
            f"Only footage can be reversed; this is a {clip.kind} clip. Reversing "
            "a still would change nothing, and reversing sound needs a resampler "
            "that is not built."
        )
    changed = Clip(**{**clip.__dict__, "reversed": (not clip.reversed) if reversed is None else bool(reversed)})
    _validate_clip(changed, track)
    track.clips = [changed if item.id == clip_id else item for item in track.clips]
    return result


def freeze_frame(project: Project, *, clip_id: str, at: int, duration: int = DEFAULT_FREEZE_TICKS) -> Project:
    """Hold one instant of a clip, pushing everything after it along.

    Three edits in a coat: cut the clip at ``at``, open a gap there, and drop in
    a piece that reads one instant of the same material forever. That last part
    is a clip at speed 0 — a freeze is not a separate concept, it is what a
    speed of zero means, which is also why a frozen stretch can appear in the
    middle of a speed curve.

    The frozen piece inherits the resolved properties of the instant it froze,
    so a clip caught mid-zoom holds the size it was at rather than snapping
    back to its defaults.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind != "video":
        raise TimelineError(
            f"Only footage can be frozen; this is a {clip.kind} clip. A still is "
            "already a held frame."
        )
    moment = int(at)
    if not (clip.start < moment < clip.end):
        raise TimelineError(
            f"Tick {moment} is not inside clip {clip_id!r} ({clip.start}–{clip.end}). "
            "A freeze has to be somewhere the clip actually plays."
        )
    span = max(MIN_CLIP_TICKS, int(duration))
    offset = moment - clip.start
    held = clip.source_at(offset)
    properties = clip.property_at(offset)

    result = split_clip(result, clip_id=clip_id, at=moment)
    result = insert_gap(result, track_id=track.id, at=moment, duration=span)
    result = add_clip(
        result,
        track_id=track.id,
        kind="video",
        start=moment,
        duration=span,
        asset_id=clip.asset_id,
        source_duration=clip.source_duration,
        in_point=held,
        label=clip.label,
        speed=0.0,
        style=dict(clip.style),
        properties=properties,
    )
    return result


def set_fade(project: Project, *, clip_id: str, fade_in: int | None = None, fade_out: int | None = None) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    changed = Clip(
        **{
            **clip.__dict__,
            "fade_in": clip.fade_in if fade_in is None else max(0, int(fade_in)),
            "fade_out": clip.fade_out if fade_out is None else max(0, int(fade_out)),
        }
    )
    _validate_clip(changed, track)
    track.clips = [changed if item.id == clip_id else item for item in track.clips]
    return result


def set_text(project: Project, *, clip_id: str, text: str) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind != "text":
        raise TimelineError(f"Clip {clip_id!r} is a {clip.kind} clip, not a text clip.")
    clip.text = str(text)[:2000]
    return result


def set_style(project: Project, *, clip_id: str, style: Mapping[str, Any], merge: bool = True) -> Project:
    """Font, colour, stroke, blend mode — anything the renderer reads but the
    timeline does not reason about.

    Kept as a free-form mapping on purpose. Every field the *timeline* has to
    understand is a real field with a validator; style is the part only the
    painter reads, and inventing a schema for it here would mean editing this
    module every time the browser learns a new text effect.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    clip.style = {**clip.style, **dict(style)} if merge else dict(style)
    return result


def set_property(project: Project, *, clip_id: str, name: str, value: float) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    key = _check_property(name)
    clip.properties[key] = _clamp(key, value)
    return result


def set_properties(project: Project, *, clip_id: str, values: Mapping[str, float]) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    for name, value in values.items():
        key = _check_property(name)
        clip.properties[key] = _clamp(key, value)
    return result


def reset_properties(project: Project, *, clip_id: str) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    clip.properties = {}
    clip.keyframes = {}
    return result


# ── keyframes ───────────────────────────────────────────────────────────────


def add_keyframe(
    project: Project,
    *,
    clip_id: str,
    name: str,
    at: int,
    value: float,
    easing: str = "linear",
) -> Project:
    """Set a value at a moment inside the clip.

    ``at`` is measured from the start of the clip, not the timeline, so the
    animation travels with the clip when it is moved. A keyframe at a time that
    already has one replaces it — clicking the same spot twice is a correction,
    not a request for two values at one instant.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    key = _check_property(name)
    offset = max(0, int(at))
    if offset > clip.duration:
        raise TimelineError(
            f"Tick {offset} is past the end of a clip {clip.duration} ticks long. "
            "A keyframe outside its clip would never be reached."
        )
    frame = Keyframe(at=offset, value=_clamp(key, value), easing=str(easing))
    if frame.easing not in ("linear", "hold", "ease_in", "ease_out", "ease_in_out"):
        raise TimelineError(f"Unknown easing {easing!r}.")
    frames = [item for item in clip.keyframes.get(key, []) if item.at != offset]
    frames.append(frame)
    clip.keyframes[key] = sorted(frames, key=lambda item: item.at)
    return result


def remove_keyframe(project: Project, *, clip_id: str, name: str, at: int) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    key = _check_property(name)
    frames = [item for item in clip.keyframes.get(key, []) if item.at != int(at)]
    if frames:
        clip.keyframes[key] = frames
    else:
        clip.keyframes.pop(key, None)
    return result


def clear_keyframes(project: Project, *, clip_id: str, name: str = "") -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if name:
        clip.keyframes.pop(_check_property(name), None)
    else:
        clip.keyframes = {}
    return result


# ── transitions ─────────────────────────────────────────────────────────────


def add_transition(
    project: Project,
    *,
    clip_id: str,
    preset: str = "dissolve",
    duration: int = presets.DEFAULT_TRANSITION_TICKS,
    side: str = "after",
) -> Project:
    """Blend this clip into the one next to it.

    Addressed by *one* clip and a side rather than by two, because that is how
    it is used: you select a clip and put a transition on its end. Naming both
    sides would make the caller find the neighbour, and the caller finding the
    wrong neighbour is a dissolve in the wrong place.
    """
    spec = presets.transition(preset)
    span = max(
        presets.MIN_TRANSITION_TICKS,
        min(int(duration), presets.MAX_TRANSITION_TICKS),
    )
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)

    ordered = sorted(track.clips, key=lambda item: item.start)
    position = next(index for index, item in enumerate(ordered) if item.id == clip_id)
    if str(side) == "before":
        left = ordered[position - 1] if position > 0 else None
        right = clip
    else:
        left = clip
        right = ordered[position + 1] if position + 1 < len(ordered) else None

    if left is None or right is None:
        raise TimelineError(
            f"There is no clip {'before' if side == 'before' else 'after'} "
            f"{clip_id!r} to blend into. A transition needs two clips."
        )
    if left.end != right.start:
        raise TimelineError(
            "Those two clips do not meet — there is a gap between them. A "
            "transition blends across a cut, so close the gap first."
        )

    # One transition per cut. Adding a second would mean two blends over the
    # same frames, which has no defined answer.
    track.transitions = [
        item
        for item in track.transitions
        if not (item.from_clip_id == left.id and item.to_clip_id == right.id)
    ]
    track.transitions.append(
        Transition(
            id=_new_id("xt"),
            from_clip_id=left.id,
            to_clip_id=right.id,
            preset=spec.id,
            duration=span,
        )
    )
    return _commit(result, track)


def set_transition(
    project: Project,
    *,
    transition_id: str,
    preset: str = "",
    duration: int = 0,
) -> Project:
    result = _copy(project)
    for track in result.tracks:
        for index, item in enumerate(track.transitions):
            if item.id != transition_id:
                continue
            track.transitions[index] = Transition(
                id=item.id,
                from_clip_id=item.from_clip_id,
                to_clip_id=item.to_clip_id,
                preset=presets.transition(preset).id if preset else item.preset,
                duration=(
                    max(
                        presets.MIN_TRANSITION_TICKS,
                        min(int(duration), presets.MAX_TRANSITION_TICKS),
                    )
                    if duration
                    else item.duration
                ),
            )
            return _commit(result, track)
    raise TimelineError(f"No transition {transition_id!r} in this project.")


def remove_transition(project: Project, *, transition_id: str) -> Project:
    result = _copy(project)
    for track in result.tracks:
        if any(item.id == transition_id for item in track.transitions):
            track.transitions = [item for item in track.transitions if item.id != transition_id]
            return result
    raise TimelineError(f"No transition {transition_id!r} in this project.")


def apply_transition_to_all(
    project: Project,
    *,
    track_id: str,
    preset: str = "dissolve",
    duration: int = presets.DEFAULT_TRANSITION_TICKS,
) -> Project:
    """Put the same transition on every cut in a track.

    Cuts that cannot take one — because a clip is too short for the halves at
    both its ends — are skipped rather than failing the whole operation. Asking
    for "all" and getting nothing because one clip was short is not what anyone
    means by all.
    """
    result = project
    working = _copy(project)
    ordered = sorted(working.track(track_id).clips, key=lambda item: item.start)
    for left, right in zip(ordered, ordered[1:]):
        if left.end != right.start:
            continue
        try:
            result = add_transition(
                result, clip_id=left.id, preset=preset, duration=duration, side="after"
            )
        except TimelineError:
            continue
    return result


# ── animations and styles, from the preset registry ─────────────────────────


def apply_animation(
    project: Project,
    *,
    clip_id: str,
    preset: str,
    duration: int = presets.DEFAULT_ANIMATION_TICKS,
) -> Project:
    """Turn a named animation into ordinary keyframes on this clip.

    Deliberately not a new kind of object. Once applied there is nothing special
    about an animated clip — it survives a split, travels with a trim and
    resolves identically in both languages, because it *is* keyframes and all of
    that already works.
    """
    spec = presets.animation(preset)
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)

    window = max(1, min(int(duration), clip.duration))
    plan = presets.keyframes_for(spec, window=window, clip_duration=clip.duration)
    for name, points in plan.items():
        key = _check_property(name)
        existing = {frame.at: frame for frame in clip.keyframes.get(key, [])}
        for at, value, easing in points:
            offset = max(0, min(int(at), clip.duration))
            existing[offset] = Keyframe(offset, _clamp(key, value), easing)
        clip.keyframes[key] = sorted(existing.values(), key=lambda frame: frame.at)
    clip.style = {**clip.style, "animation": spec.id}
    return result


def apply_text_style(project: Project, *, clip_id: str, style: str) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind != "text":
        raise TimelineError(f"Clip {clip_id!r} is a {clip.kind} clip, not a text clip.")
    clip.style = {**clip.style, **presets.text_style(style), "preset": style}
    return result


def set_blend_mode(project: Project, *, clip_id: str, mode: str) -> Project:
    """How this clip mixes with what is under it.

    A name rather than a number, so it lives in style and not in the property
    set — half of a blend mode is not a blend mode, and there is nothing to
    interpolate.
    """
    key = str(mode or "normal").strip().lower()
    if key not in BLEND_MODES:
        raise TimelineError(
            f"Unknown blend mode {mode!r}. Known: {', '.join(BLEND_MODES)}."
        )
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    clip.style = {**clip.style, "blend": key}
    return result


def copy_attributes(
    project: Project,
    *,
    from_clip_id: str,
    to_clip_ids: list[str],
    properties: bool = True,
    keyframes: bool = False,
    style: bool = True,
    effects: bool = True,
) -> Project:
    """Paste one clip's look onto others.

    Keyframes are **off by default**: they are measured against the source
    clip's length, and pasting them onto a clip of a different length puts the
    animation somewhere nobody chose. Asking for them explicitly is the point at
    which the caller has thought about that.

    Effects are **on** by default, and are *replaced* rather than merged. A
    stack is an ordered thing; merging two of them produces an order neither
    clip had, which is the one result nobody asked for.
    """
    result = _copy(project)
    _, source = result.find_clip(from_clip_id)
    for target_id in to_clip_ids:
        track, clip = result.find_clip(target_id)
        _assert_editable(track)
        if properties:
            clip.properties = dict(source.properties)
        if style:
            clip.style = {**clip.style, **source.style}
        if keyframes:
            clip.keyframes = {
                name: [
                    Keyframe(min(frame.at, clip.duration), frame.value, frame.easing)
                    for frame in frames
                ]
                for name, frames in source.keyframes.items()
            }
        if effects and clip.kind != "audio":
            clip.effects = [dict(item) for item in source.effects]
    return result


# ── markers and the canvas ──────────────────────────────────────────────────


def add_marker(project: Project, *, at: int, label: str = "", colour: str = "") -> Project:
    result = _copy(project)
    result.markers.append(
        Marker(id=_new_id("marker"), at=max(0, int(at)), label=str(label)[:120], colour=str(colour)[:20])
    )
    result.markers.sort(key=lambda marker: marker.at)
    return result


def remove_marker(project: Project, *, marker_id: str) -> Project:
    result = _copy(project)
    result.markers = [marker for marker in result.markers if marker.id != marker_id]
    return result


def set_canvas(
    project: Project,
    *,
    preset: str = "",
    width: int = 0,
    height: int = 0,
    fps: str = "",
    background: str = "",
) -> Project:
    """Change the shape of the video.

    Nothing inside the timeline moves. Reframing every clip to suit a new aspect
    ratio is a real feature — CapCut calls it auto-reframe — and it is a model
    call, not a resize; doing a crude version of it here would produce subjects
    sliced down the middle and call it done.
    """
    result = _copy(project)
    if preset:
        key = str(preset).strip().lower()
        if key not in PRESETS:
            raise TimelineError(f"Unknown canvas preset {preset!r}. Known: {', '.join(sorted(PRESETS))}.")
        result.width, result.height = PRESETS[key]
    if width and height:
        result.width, result.height = max(1, int(width)), max(1, int(height))
    if fps:
        frame_rate(fps)
        result.fps = str(fps)
    if background:
        result.background = str(background)[:32]
    return result


def rename(project: Project, *, name: str) -> Project:
    result = _copy(project)
    result.name = str(name).strip()[:200] or result.name
    return result


#: Every operation, by the name the API and the history use. Adding a function
#: above without adding it here means it cannot be called, which is the right
#: default for an editor whose whole contract is that the document is valid.
# ── effects ─────────────────────────────────────────────────────────────────
#
# A clip's effect stack is a list, and the list is ordered. Every operation here
# is therefore about *position* as much as about content — which is why there is
# a `move_effect` and no `set_effects`: replacing the whole list wholesale is how
# a UI loses an order the person deliberately arranged.


def _effect_stack(clip: Clip) -> list[dict[str, Any]]:
    return [dict(item) for item in clip.effects]


def _at(stack: list[dict[str, Any]], index: int, *, what: str) -> int:
    if not stack:
        raise TimelineError(f"This clip has no effects, so there is nothing to {what}.")
    position = int(index)
    if position < 0 or position >= len(stack):
        raise TimelineError(
            f"There is no effect {position} on this clip — it has {len(stack)}, "
            f"numbered 0 to {len(stack) - 1}."
        )
    return position


def add_effect(
    project: Project,
    *,
    clip_id: str,
    preset: str = "",
    primitive: str = "",
    amount: float = 1.0,
    params: Mapping[str, Any] | None = None,
    index: int = -1,
) -> Project:
    """Put a look, or one bare pixel operation, onto a clip.

    ``index`` is where in the stack it goes; the default appends, which is what
    "add a filter" means. Inserting matters because the order is the look — a
    vignette before a blur is blurred, and a vignette after one is not.

    The name is checked here against :mod:`effects`, so an id nobody declared
    never reaches a document. That is the same boundary a transition preset is
    checked at, and for the same reason: a stored name that resolves to nothing
    is a picture that silently loses a step.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    if clip.kind == "audio":
        raise TimelineError(
            "An audio clip has no picture to filter. Effects are pixel "
            "operations; for sound, use volume, fades and keyframes."
        )
    try:
        entry = fx.normalise(
            {"preset": preset, "primitive": primitive, "amount": amount, "params": params or {}}
        )
    except (fx.UnknownEffect, fx.UnknownPrimitive, ValueError) as exc:
        raise TimelineError(str(exc)) from exc

    stack = _effect_stack(clip)
    position = len(stack) if int(index) < 0 else max(0, min(len(stack), int(index)))
    stack.insert(position, entry)
    clip.effects = stack
    # Resolve the whole stack, not just the new entry: the ceiling is on the
    # clip, and a preset that costs five passes can only be caught in context.
    try:
        fx.resolve_stack(stack)
    except ValueError as exc:
        raise TimelineError(str(exc)) from exc
    return _commit(result, track)


def remove_effect(project: Project, *, clip_id: str, index: int) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    stack = _effect_stack(clip)
    stack.pop(_at(stack, index, what="remove"))
    clip.effects = stack
    return _commit(result, track)


def move_effect(project: Project, *, clip_id: str, index: int, to: int) -> Project:
    """Reorder the stack. The one edit that changes nothing but the result."""
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    stack = _effect_stack(clip)
    position = _at(stack, index, what="move")
    target = max(0, min(len(stack) - 1, int(to)))
    stack.insert(target, stack.pop(position))
    clip.effects = stack
    return _commit(result, track)


def set_effect(
    project: Project,
    *,
    clip_id: str,
    index: int,
    amount: float | None = None,
    params: Mapping[str, Any] | None = None,
) -> Project:
    """Dial one entry: its strength, or the parameters that shape it.

    ``params`` merges rather than replaces, so turning one knob does not silently
    reset the others.
    """
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    stack = _effect_stack(clip)
    position = _at(stack, index, what="change")
    entry = dict(stack[position])
    if amount is not None:
        entry["amount"] = float(amount)
    if params is not None:
        entry["params"] = {**dict(entry.get("params") or {}), **dict(params)}
    try:
        stack[position] = fx.normalise(entry)
    except (fx.UnknownEffect, fx.UnknownPrimitive, ValueError) as exc:
        raise TimelineError(str(exc)) from exc
    clip.effects = stack
    return _commit(result, track)


def clear_effects(project: Project, *, clip_id: str) -> Project:
    result = _copy(project)
    track, clip = result.find_clip(clip_id)
    _assert_editable(track)
    clip.effects = []
    return _commit(result, track)


def apply_effect_to_all(
    project: Project,
    *,
    preset: str = "",
    primitive: str = "",
    amount: float = 1.0,
    params: Mapping[str, Any] | None = None,
    track_id: str = "",
    replace: bool = False,
) -> Project:
    """The "apply to all clips" button, which every editor has and every editor
    needs, because grading one clip of twelve is worse than grading none.

    ``replace`` clears each clip's stack first. Without it the look is appended,
    so pressing it twice stacks two copies — which is occasionally what someone
    wants and never what they expect, hence the flag rather than a guess.
    """
    result = project
    targets = [track for track in project.tracks if track.kind == "video"]
    if track_id:
        targets = [track for track in targets if track.id == track_id]
        if not targets:
            raise TimelineError(f"No video track {track_id!r} to apply an effect to.")
    clip_ids = [
        clip.id for track in targets if not track.locked
        for clip in track.clips if clip.kind != "audio"
    ]
    if not clip_ids:
        raise TimelineError("There are no editable picture clips to apply that to.")
    for clip_id in clip_ids:
        if replace:
            result = clear_effects(result, clip_id=clip_id)
        result = add_effect(
            result, clip_id=clip_id, preset=preset, primitive=primitive,
            amount=amount, params=params,
        )
    return result


OPERATIONS: dict[str, Callable[..., Project]] = {
    "add_track": add_track,
    "remove_track": remove_track,
    "move_track": move_track,
    "set_track": set_track,
    "add_clip": add_clip,
    "remove_clip": remove_clip,
    "ripple_delete": ripple_delete,
    "insert_gap": insert_gap,
    "move_clip": move_clip,
    "split_clip": split_clip,
    "trim_clip": trim_clip,
    "duplicate_clip": duplicate_clip,
    "set_speed": set_speed,
    "apply_speed_curve": apply_speed_curve,
    "clear_speed_curve": clear_speed_curve,
    "reverse_clip": reverse_clip,
    "freeze_frame": freeze_frame,
    "set_fade": set_fade,
    "set_text": set_text,
    "set_style": set_style,
    "set_property": set_property,
    "set_properties": set_properties,
    "reset_properties": reset_properties,
    "add_keyframe": add_keyframe,
    "remove_keyframe": remove_keyframe,
    "clear_keyframes": clear_keyframes,
    "add_transition": add_transition,
    "set_transition": set_transition,
    "remove_transition": remove_transition,
    "apply_transition_to_all": apply_transition_to_all,
    "apply_animation": apply_animation,
    "apply_text_style": apply_text_style,
    "set_blend_mode": set_blend_mode,
    "add_effect": add_effect,
    "remove_effect": remove_effect,
    "move_effect": move_effect,
    "set_effect": set_effect,
    "clear_effects": clear_effects,
    "apply_effect_to_all": apply_effect_to_all,
    "copy_attributes": copy_attributes,
    "add_marker": add_marker,
    "remove_marker": remove_marker,
    "set_canvas": set_canvas,
    "rename": rename,
}


def apply(project: Project, operation: str, params: Mapping[str, Any] | None = None) -> Project:
    """Run one named operation. Refuses anything not in :data:`OPERATIONS`."""
    name = str(operation or "").strip()
    if name not in OPERATIONS:
        known = ", ".join(sorted(OPERATIONS))
        raise TimelineError(f"Unknown edit {operation!r}. Known edits: {known}.")
    arguments = {str(key): value for key, value in (params or {}).items()}
    try:
        return OPERATIONS[name](project, **arguments)
    except TypeError as exc:
        # A wrong or missing parameter is the caller's mistake, not a crash.
        raise TimelineError(f"{name}: {exc}") from exc
