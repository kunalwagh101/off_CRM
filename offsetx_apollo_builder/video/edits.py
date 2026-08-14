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

from .timeline import (
    EASINGS,
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
)


def _copy(project: Project) -> Project:
    return Project.from_dict(project.to_dict())


def _commit(project: Project, track: Track) -> Project:
    """Re-sort and re-check one track after it has been changed."""
    track.clips.sort(key=lambda clip: clip.start)
    _assert_no_overlap(track)
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

    A boundary keyframe is only synthesised when the boundary falls *between*
    two real ones. Outside that range the value is already constant, so adding
    one would make every trim grow the keyframe list for no change in output.
    """
    if not frames:
        return []
    ordered = sorted(frames, key=lambda item: item.at)
    first, last = ordered[0].at, ordered[-1].at
    span = end - start
    kept: dict[int, Keyframe] = {}
    for frame in ordered:
        if start <= frame.at <= end:
            kept[frame.at - start] = Keyframe(frame.at - start, frame.value, frame.easing)
    if first < start < last and 0 not in kept:
        kept[0] = Keyframe(0, interpolate(ordered, start), _easing_at(ordered, start))
    if first < end < last and span not in kept:
        kept[span] = Keyframe(span, interpolate(ordered, end), _easing_at(ordered, end))
    if not kept:
        # The whole range sits outside every keyframe, so the value is held.
        # One keyframe carrying that value says the same thing in less space.
        kept[0] = Keyframe(0, interpolate(ordered, start), ordered[0].easing)
    return sorted(kept.values(), key=lambda item: item.at)


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
        speed=float(speed or 1.0),
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
    return result


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
    if keep_duration or clip.source_duration <= 0:
        changed = Clip(**{**clip.__dict__, "speed": rate, "properties": dict(clip.properties)})
    else:
        consumed = int(round(clip.duration * clip.speed))
        span = max(1, int(round(consumed / rate)))
        changed = Clip(
            **{
                **clip.__dict__,
                "speed": rate,
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
    "set_fade": set_fade,
    "set_text": set_text,
    "set_style": set_style,
    "set_property": set_property,
    "set_properties": set_properties,
    "reset_properties": reset_properties,
    "add_keyframe": add_keyframe,
    "remove_keyframe": remove_keyframe,
    "clear_keyframes": clear_keyframes,
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
