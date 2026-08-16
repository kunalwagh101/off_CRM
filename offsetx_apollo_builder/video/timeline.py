"""The timeline document, and every edit that can be made to it.

This is the core of the video editor and it is deliberately the least exciting
file in it: no I/O, no dependencies, no rendering, no clock. A project is data,
an edit is a function from a project to a project, and a frame is a function of
a project and a time. Everything that can be wrong about an edit is wrong here,
where it can be tested, rather than in a canvas nobody can assert against.

---

**Time is an integer, and the unit is 1/90000 of a second.**

Seconds as floats are the standard way an editor rots: split a clip, trim it,
split again, and the boundaries drift until a cut lands half a frame early and
nobody can say which operation did it. Frames are exact but tie the document to
one frame rate, so changing a project from 30fps to 24fps would move every edit.

90kHz is the MPEG timebase and it is chosen for one arithmetic reason — every
frame boundary at every rate anyone uses is a whole number of ticks:

| Rate | Ticks per frame |
|---|---|
| 23.976 (24000/1001) | 3753.75 → not exact, snapped |
| 24 | 3750 |
| 25 | 3600 |
| 29.97 (30000/1001) | 3003 |
| 30 | 3000 |
| 50 | 1800 |
| 59.94 (60000/1001) | 1501.5 → not exact, snapped |
| 60 | 1500 |

The two that are not exact are the 1001-denominator rates at odd multiples, and
they are handled by snapping rather than by pretending. Everything else is exact
forever, which means a split at frame 100 is *the same tick* however many times
the project is saved, reloaded and re-split.

---

**Clips on a track never overlap.**

Not "should not" — cannot. Every operation that moves or resizes a clip checks
the whole track and refuses. An overlap has no defined answer: two clips both
claiming tick 500 means the renderer picks one, and which one it picks is an
implementation detail that will differ between the preview and the export. That
is the class of bug where the exported video does not match what was on screen,
which is the worst thing a video editor can do.

Overlap is allowed *between* tracks. That is what tracks are for.

---

**Keyframes are relative to the clip, not the timeline.**

A fade that starts 200ms into a clip has to still start 200ms into that clip
after the clip is dragged somewhere else. Absolute keyframe times are the
version of this that looks correct until the first time anyone moves anything.

---

**One resolver feeds the preview, the export and the tests.**

:func:`frame_at` answers "what is on screen at this tick" and nothing else
answers it. The browser draws what it returns, the exporter encodes what it
returns, and ``tests/test_video_timeline.py`` asserts on what it returns. A
second implementation of that question — one for preview, one for export — is
how a preview stops matching its own export, so the TypeScript side is held to
this one by a conformance fixture rather than by hope. See
``docs/architecture/VIDEO_EDITOR.md``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

#: Ticks in one second. The MPEG timebase, for the reason in the module
#: docstring: it is the smallest rate that divides evenly by every common frame
#: rate, so no ordinary edit ever lands between two representable instants.
TICKS_PER_SECOND = 90_000

#: The document format. Written into every serialised project so a future
#: change can migrate rather than guess.
DOCUMENT_VERSION = 1

#: Frame rates a project may declare. Default-deny, like every other registry
#: here: an unlisted rate is refused rather than accepted and rounded, because
#: rounding it silently would move every cut in the project.
FRAME_RATES: dict[str, float] = {
    "23.976": 24000 / 1001,
    "24": 24.0,
    "25": 25.0,
    "29.97": 30000 / 1001,
    "30": 30.0,
    "50": 50.0,
    "59.94": 60000 / 1001,
    "60": 60.0,
}

#: What a track may hold. A track is one kind all the way through — mixing
#: audio into a video track makes "which clip is on top" and "which clip is
#: audible" the same question, and they are not.
TRACK_KINDS = ("video", "audio")

#: What a clip may be. ``solid`` is a flat colour, which is how backgrounds,
#: title cards and letterboxing are made without needing an asset.
CLIP_KINDS = ("video", "image", "audio", "text", "solid")

#: Which clip kinds a track kind accepts.
TRACK_ACCEPTS: dict[str, tuple[str, ...]] = {
    "video": ("video", "image", "text", "solid"),
    "audio": ("audio",),
}

#: Clip kinds that have no inherent length, so a duration is whatever the editor
#: says it is. A picture is five seconds long because you dragged it that far.
UNBOUNDED_KINDS = ("image", "text", "solid")

#: Every animatable property, its default, and the range it is clamped to.
#: Unlisted names are refused: a typo in a property name that silently created a
#: new property would animate nothing and report success.
PROPERTY_SPEC: dict[str, tuple[float, float, float]] = {
    # name: (default, minimum, maximum)
    "x": (0.0, -20000.0, 20000.0),
    "y": (0.0, -20000.0, 20000.0),
    "scale": (1.0, 0.01, 50.0),
    "rotation": (0.0, -3600.0, 3600.0),
    "opacity": (1.0, 0.0, 1.0),
    "anchor_x": (0.5, 0.0, 1.0),
    "anchor_y": (0.5, 0.0, 1.0),
    "crop_left": (0.0, 0.0, 0.99),
    "crop_top": (0.0, 0.0, 0.99),
    "crop_right": (0.0, 0.0, 0.99),
    "crop_bottom": (0.0, 0.0, 0.99),
    "volume": (1.0, 0.0, 4.0),
    "brightness": (0.0, -1.0, 1.0),
    "contrast": (0.0, -1.0, 1.0),
    "saturation": (0.0, -1.0, 1.0),
    "blur": (0.0, 0.0, 100.0),
    "exposure": (0.0, -2.0, 2.0),
    "temperature": (0.0, -1.0, 1.0),
    "tint": (0.0, -1.0, 1.0),
    "vignette": (0.0, 0.0, 1.0),
    "sharpen": (0.0, 0.0, 2.0),
    "grain": (0.0, 0.0, 1.0),
    #: Flips are 0 or 1 rather than booleans so they animate like everything
    #: else and need no second code path in either resolver.
    "flip_x": (0.0, 0.0, 1.0),
    "flip_y": (0.0, 0.0, 1.0),
    "corner_radius": (0.0, 0.0, 1000.0),
    "border_width": (0.0, 0.0, 200.0),
    "shadow": (0.0, 0.0, 200.0),
    "letter_spacing": (0.0, -50.0, 200.0),
}

#: Blend modes a clip may declare. Not a property because it is a name, not a
#: number, and a half-interpolated blend mode is not a thing.
BLEND_MODES = (
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "hard-light", "soft-light", "difference",
    "exclusion", "hue", "saturation", "color", "luminosity",
)

#: How a value travels from one keyframe to the next. ``hold`` is a step, which
#: is the one people reach for when they want a thing to appear rather than
#: arrive.
EASINGS = ("linear", "hold", "ease_in", "ease_out", "ease_in_out")

#: Speed bounds. CapCut allows 0.1x to 100x and there is no reason to differ.
MIN_SPEED = 0.1
MAX_SPEED = 100.0

#: A clip shorter than this is a mistake — usually a drag that registered as a
#: resize. One frame at 60fps is 1500 ticks.
MIN_CLIP_TICKS = 1500


class TimelineError(ValueError):
    """Base for every refusal here.

    A ``ValueError`` so the API turns it into a 422 carrying the message, the
    same contract the campaign kinds use.
    """


class UnknownTrack(TimelineError):
    """No track by that id."""


class UnknownClip(TimelineError):
    """No clip by that id."""


class TrackLocked(TimelineError):
    """The track is locked. Locking exists to stop exactly this edit."""


class ClipOverlap(TimelineError):
    """Two clips on one track would claim the same tick."""


def seconds_to_ticks(seconds: float) -> int:
    """Round to the nearest tick. Never truncates — truncation always shortens."""
    return int(round(float(seconds) * TICKS_PER_SECOND))


def ticks_to_seconds(ticks: int) -> float:
    return int(ticks) / TICKS_PER_SECOND


def frame_rate(fps: str) -> float:
    key = str(fps).strip()
    if key not in FRAME_RATES:
        known = ", ".join(FRAME_RATES)
        raise TimelineError(f"Unsupported frame rate {fps!r}. Known rates: {known}.")
    return FRAME_RATES[key]


def ticks_per_frame(fps: str) -> float:
    return TICKS_PER_SECOND / frame_rate(fps)


def snap_to_frame(ticks: int, fps: str) -> int:
    """Move a tick to the nearest frame boundary for this project.

    Used at the edges of interaction — a mouse lands between frames and a cut
    that is not on a frame boundary is a cut the encoder has to invent. The
    document itself stores whatever it is given, so a project whose frame rate
    changes does not silently rewrite its own edits.
    """
    per = ticks_per_frame(fps)
    return int(round(round(int(ticks) / per) * per))


def _clamp(name: str, value: float) -> float:
    default, low, high = PROPERTY_SPEC[name]
    number = float(value)
    if number != number:  # NaN, which compares false against everything
        return default
    return max(low, min(high, number))


def _check_property(name: str) -> str:
    key = str(name or "").strip()
    if key not in PROPERTY_SPEC:
        known = ", ".join(sorted(PROPERTY_SPEC))
        raise TimelineError(f"Unknown property {name!r}. Animatable properties: {known}.")
    return key


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class Keyframe:
    """One value of one property, at one time inside its clip."""

    at: int
    value: float
    easing: str = "linear"

    def to_dict(self) -> dict[str, Any]:
        return {"at": int(self.at), "value": float(self.value), "easing": self.easing}

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Keyframe":
        easing = str(raw.get("easing") or "linear")
        if easing not in EASINGS:
            raise TimelineError(f"Unknown easing {easing!r}. Known: {', '.join(EASINGS)}.")
        return Keyframe(at=int(raw.get("at") or 0), value=float(raw.get("value") or 0.0), easing=easing)


@dataclass
class Clip:
    """One thing on one track, for one stretch of time.

    ``start`` and ``duration`` are where it sits on the timeline. ``in_point``
    and ``source_duration`` are where it reads from inside its own material.
    Keeping those two pairs separate is what makes trimming non-destructive:
    dragging the left edge changes where you *start reading*, and the material
    itself is never touched.
    """

    id: str
    kind: str
    start: int
    duration: int
    in_point: int = 0
    source_duration: int = 0
    asset_id: str = ""
    text: str = ""
    speed: float = 1.0
    #: Speed over the clip's own time, when it is not one number.
    #:
    #: ``at`` is ticks into the clip and ``value`` is the speed there; the curve
    #: is straight between points, which is what makes the amount of material
    #: consumed an exact sum of trapezoids rather than something two languages
    #: have to agree to approximate. Empty means ``speed`` governs throughout.
    speed_curve: list[Keyframe] = field(default_factory=list)
    #: Play the material backwards. Separate from a negative speed on purpose —
    #: a negative speed makes every other piece of arithmetic here signed for
    #: the sake of one flag.
    reversed: bool = False
    fade_in: int = 0
    fade_out: int = 0
    label: str = ""
    properties: dict[str, float] = field(default_factory=dict)
    keyframes: dict[str, list[Keyframe]] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)

    @property
    def end(self) -> int:
        return self.start + self.duration

    @property
    def retimed(self) -> bool:
        """Whether this clip does anything to time beyond running at one rate."""
        return bool(self.speed_curve) or self.reversed

    def consumed(self, offset: int) -> float:
        """How much source this clip has read by ``offset`` ticks into itself.

        The whole of time remapping is this one integral. At a constant speed it
        is ``offset * speed`` and nothing about the old behaviour changes; with
        a curve it is the area under the speed curve, which is a sum of
        trapezoids because the curve is straight between its points.
        """
        return _consumed(self.speed_curve, self.speed, max(0, min(offset, self.duration)))

    def source_at(self, offset: int) -> int:
        """Where in the material this clip is reading, ``offset`` ticks in.

        Reversed clips walk the same range from the far end: at offset 0 they
        are at the last instant they will ever read, and at the end of the clip
        they are back at the in-point.
        """
        if self.reversed:
            span = _consumed(self.speed_curve, self.speed, self.duration)
            return self.in_point + int(round(span - self.consumed(offset)))
        return self.in_point + int(round(self.consumed(offset)))

    def property_at(self, offset: int) -> dict[str, float]:
        """Every property, resolved at ``offset`` ticks into this clip."""
        values = {name: spec[0] for name, spec in PROPERTY_SPEC.items()}
        values.update({name: _clamp(name, value) for name, value in self.properties.items()})
        for name, frames in self.keyframes.items():
            if frames:
                values[name] = _clamp(name, interpolate(frames, offset))
        return values

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "start": int(self.start),
            "duration": int(self.duration),
            "in_point": int(self.in_point),
            "source_duration": int(self.source_duration),
            "asset_id": self.asset_id,
            "text": self.text,
            "speed": float(self.speed),
            "speed_curve": [frame.to_dict() for frame in self.speed_curve],
            "reversed": bool(self.reversed),
            "fade_in": int(self.fade_in),
            "fade_out": int(self.fade_out),
            "label": self.label,
            "properties": {name: float(value) for name, value in sorted(self.properties.items())},
            "keyframes": {
                name: [frame.to_dict() for frame in frames]
                for name, frames in sorted(self.keyframes.items())
            },
            "style": dict(self.style),
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Clip":
        keyframes: dict[str, list[Keyframe]] = {}
        for name, frames in (raw.get("keyframes") or {}).items():
            key = _check_property(name)
            keyframes[key] = sorted(
                (Keyframe.from_dict(item) for item in frames), key=lambda item: item.at
            )
        properties = {
            _check_property(name): _clamp(_check_property(name), value)
            for name, value in (raw.get("properties") or {}).items()
        }
        return Clip(
            id=str(raw.get("id") or _new_id("clip")),
            kind=str(raw.get("kind") or "video"),
            start=int(raw.get("start") or 0),
            duration=int(raw.get("duration") or 0),
            in_point=int(raw.get("in_point") or 0),
            source_duration=int(raw.get("source_duration") or 0),
            asset_id=str(raw.get("asset_id") or ""),
            text=str(raw.get("text") or ""),
            # A speed deliberately set to 0 is a freeze, not a missing value, so
            # this cannot use `or 1.0` the way the others use `or 0`.
            speed=float(raw["speed"]) if raw.get("speed") is not None else 1.0,
            speed_curve=[Keyframe.from_dict(item) for item in raw.get("speed_curve") or []],
            reversed=bool(raw.get("reversed")),
            fade_in=int(raw.get("fade_in") or 0),
            fade_out=int(raw.get("fade_out") or 0),
            label=str(raw.get("label") or ""),
            properties=properties,
            keyframes=keyframes,
            style=dict(raw.get("style") or {}),
        )


@dataclass(frozen=True)
class Transition:
    """A blend between two clips that meet at a cut.

    **Not a clip, and that is the whole design.** A dissolve needs both clips on
    screen at once, and the timeline's central rule is that clips on a track
    cannot overlap by a single tick. Relaxing that rule to allow transitions
    would reopen the worst bug class an editor has — two clips claiming one tick,
    with the preview and the export free to disagree about which wins.

    So the clips stay adjacent and untouched, and this object says *how long
    either side of their shared cut both should be drawn for*. The overlap is a
    property of the boundary, declared and bounded, rather than an accident of
    two clips' positions.
    """

    id: str
    from_clip_id: str
    to_clip_id: str
    preset: str = "dissolve"
    duration: int = 45_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_clip_id": self.from_clip_id,
            "to_clip_id": self.to_clip_id,
            "preset": self.preset,
            "duration": int(self.duration),
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Transition":
        return Transition(
            id=str(raw.get("id") or _new_id("xt")),
            from_clip_id=str(raw.get("from_clip_id") or ""),
            to_clip_id=str(raw.get("to_clip_id") or ""),
            preset=str(raw.get("preset") or "dissolve"),
            duration=int(raw.get("duration") or 45_000),
        )


@dataclass
class Track:
    """A lane. Order is z-order for video: later tracks draw on top."""

    id: str
    kind: str = "video"
    name: str = ""
    locked: bool = False
    muted: bool = False
    hidden: bool = False
    clips: list[Clip] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)

    @property
    def duration(self) -> int:
        return max((clip.end for clip in self.clips), default=0)

    def clip(self, clip_id: str) -> Clip:
        for item in self.clips:
            if item.id == clip_id:
                return item
        raise UnknownClip(f"No clip {clip_id!r} on track {self.id!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "locked": self.locked,
            "muted": self.muted,
            "hidden": self.hidden,
            "clips": [clip.to_dict() for clip in self.clips],
            "transitions": [item.to_dict() for item in self.transitions],
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Track":
        kind = str(raw.get("kind") or "video")
        if kind not in TRACK_KINDS:
            raise TimelineError(f"Unknown track kind {kind!r}. Known: {', '.join(TRACK_KINDS)}.")
        clips = sorted(
            (Clip.from_dict(item) for item in raw.get("clips") or []),
            key=lambda item: item.start,
        )
        return Track(
            id=str(raw.get("id") or _new_id("track")),
            kind=kind,
            name=str(raw.get("name") or ""),
            locked=bool(raw.get("locked")),
            muted=bool(raw.get("muted")),
            hidden=bool(raw.get("hidden")),
            clips=clips,
            transitions=[Transition.from_dict(item) for item in raw.get("transitions") or []],
        )


@dataclass
class Marker:
    """A named point on the timeline. Notes, beats, where the hook lands."""

    id: str
    at: int
    label: str = ""
    colour: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "at": int(self.at), "label": self.label, "colour": self.colour}


@dataclass
class Project:
    """The whole document.

    Everything about the video that is not a pixel: the canvas, the tracks, the
    clips, the markers. Serialises to JSON and back with no loss, because that
    round trip is what undo, autosave and the browser all rely on.
    """

    id: str = ""
    name: str = "Untitled"
    width: int = 1080
    height: int = 1920
    fps: str = "30"
    background: str = "#000000"
    tracks: list[Track] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)

    @property
    def duration(self) -> int:
        return max((track.duration for track in self.tracks), default=0)

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0

    def frame_count(self) -> int:
        per = ticks_per_frame(self.fps)
        return int(self.duration // per) if per else 0

    def track(self, track_id: str) -> Track:
        for item in self.tracks:
            if item.id == track_id:
                return item
        raise UnknownTrack(f"No track {track_id!r} in this project.")

    def find_clip(self, clip_id: str) -> tuple[Track, Clip]:
        for track in self.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return track, clip
        raise UnknownClip(f"No clip {clip_id!r} in this project.")

    def asset_ids(self) -> list[str]:
        """Every asset this project needs, once each, in timeline order."""
        seen: list[str] = []
        for clip in sorted(
            (clip for track in self.tracks for clip in track.clips),
            key=lambda item: item.start,
        ):
            if clip.asset_id and clip.asset_id not in seen:
                seen.append(clip.asset_id)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DOCUMENT_VERSION,
            "id": self.id,
            "name": self.name,
            "width": int(self.width),
            "height": int(self.height),
            "fps": self.fps,
            "background": self.background,
            "duration": self.duration,
            "tracks": [track.to_dict() for track in self.tracks],
            "markers": [marker.to_dict() for marker in self.markers],
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Project":
        version = int(raw.get("version") or DOCUMENT_VERSION)
        if version > DOCUMENT_VERSION:
            raise TimelineError(
                f"This project was written by a newer version of off_CRM "
                f"(document v{version}, this build reads v{DOCUMENT_VERSION}). "
                "Opening it would silently drop whatever the newer version added."
            )
        fps = str(raw.get("fps") or "30")
        frame_rate(fps)  # refuse an unknown rate at load, not at export
        project = Project(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or "Untitled"),
            width=max(1, int(raw.get("width") or 1080)),
            height=max(1, int(raw.get("height") or 1920)),
            fps=fps,
            background=str(raw.get("background") or "#000000"),
            tracks=[Track.from_dict(item) for item in raw.get("tracks") or []],
            markers=[
                Marker(
                    id=str(item.get("id") or _new_id("marker")),
                    at=int(item.get("at") or 0),
                    label=str(item.get("label") or ""),
                    colour=str(item.get("colour") or ""),
                )
                for item in raw.get("markers") or []
            ],
        )
        for track in project.tracks:
            _assert_no_overlap(track)
        return project


# ── canvas presets ──────────────────────────────────────────────────────────

#: The shapes people actually post. Named rather than free-form because the
#: aspect gate in ``gates.py`` checks the export against the project, and a
#: project whose size was typed by hand is the case where that check fires for
#: no reason.
PRESETS: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),   # Reels, Shorts, TikTok
    "square": (1080, 1080),     # feed
    "portrait": (1080, 1350),   # 4:5, the tallest a feed post may be
    "landscape": (1920, 1080),  # YouTube
    "wide": (2560, 1080),       # 21:9
    "classic": (1440, 1080),    # 4:3
}


def new_project(
    *,
    name: str = "Untitled",
    preset: str = "vertical",
    fps: str = "30",
    width: int = 0,
    height: int = 0,
) -> Project:
    """A project with one video track and one audio track, which is the minimum
    that can hold an edit."""
    if width and height:
        size = (max(1, int(width)), max(1, int(height)))
    else:
        key = str(preset or "vertical").strip().lower()
        if key not in PRESETS:
            known = ", ".join(sorted(PRESETS))
            raise TimelineError(f"Unknown canvas preset {preset!r}. Known: {known}.")
        size = PRESETS[key]
    frame_rate(fps)
    return Project(
        id=_new_id("vp"),
        name=str(name or "Untitled").strip()[:200] or "Untitled",
        width=size[0],
        height=size[1],
        fps=fps,
        tracks=[
            Track(id=_new_id("track"), kind="video", name="Video 1"),
            Track(id=_new_id("track"), kind="audio", name="Audio 1"),
        ],
    )


# ── keyframe resolution ─────────────────────────────────────────────────────


def _ease(easing: str, ratio: float) -> float:
    if easing == "hold":
        return 0.0
    if easing == "ease_in":
        return ratio * ratio
    if easing == "ease_out":
        return 1.0 - (1.0 - ratio) * (1.0 - ratio)
    if easing == "ease_in_out":
        if ratio < 0.5:
            return 2.0 * ratio * ratio
        return 1.0 - 2.0 * (1.0 - ratio) * (1.0 - ratio)
    return ratio


def _consumed(curve: Sequence[Keyframe], speed: float, offset: int) -> float:
    """The area under a speed curve from 0 to ``offset``.

    A speed curve says how fast the clip is reading at each instant, so the
    amount of material it has read by a given moment is the integral of it. The
    curve is straight between its points, which makes each piece a trapezoid —
    exact, and computable identically in two languages, which a bezier is not.

    Before the first point the first speed holds and after the last the last
    one does, matching :func:`interpolate` and for the same reason:
    extrapolating a *speed* past its last keyframe can send a clip off the end
    of its own material.
    """
    if not curve:
        return offset * speed
    points = sorted(curve, key=lambda frame: frame.at)
    total = 0.0
    # Anything before the first point runs at the first point's speed.
    head = min(offset, points[0].at)
    if head > 0:
        total += head * points[0].value
    for left, right in zip(points, points[1:]):
        if offset <= left.at:
            break
        span = right.at - left.at
        if span <= 0:
            continue
        if offset >= right.at:
            total += (left.value + right.value) / 2 * span
            continue
        # Part of a segment: the speed at the cut is on the straight line
        # between its ends, and the area is the trapezoid up to there.
        ratio = (offset - left.at) / span
        here = left.value + (right.value - left.value) * ratio
        total += (left.value + here) / 2 * (offset - left.at)
        break
    if offset > points[-1].at:
        total += (offset - points[-1].at) * points[-1].value
    return total


def interpolate(frames: Sequence[Keyframe], offset: int) -> float:
    """The value of an animated property at ``offset`` ticks into its clip.

    Before the first keyframe the first value holds, and after the last the last
    one does. Extrapolating instead would send a property somewhere nobody asked
    for, at the two moments — the head and the tail of a clip — that are most
    likely to be on screen during a trim.

    The easing on a keyframe governs the segment *leaving* it, which is the
    convention every editor uses: you set a keyframe and then say how it moves
    on from there.
    """
    if not frames:
        return 0.0
    ordered = sorted(frames, key=lambda item: item.at)
    if offset <= ordered[0].at:
        return float(ordered[0].value)
    if offset >= ordered[-1].at:
        return float(ordered[-1].value)
    for left, right in zip(ordered, ordered[1:]):
        if left.at <= offset <= right.at:
            span = right.at - left.at
            if span <= 0:
                return float(right.value)
            ratio = _ease(left.easing, (offset - left.at) / span)
            return float(left.value) + (float(right.value) - float(left.value)) * ratio
    return float(ordered[-1].value)


# ── the resolver: what is on screen at one tick ─────────────────────────────


@dataclass
class DrawItem:
    """One clip, resolved at one instant, ready to be drawn or encoded.

    Nothing here needs the project or the track: a renderer that is handed a
    list of these has everything it needs and no way to reach back for more,
    which is what keeps the browser and the exporter from diverging.
    """

    clip_id: str
    track_id: str
    kind: str
    z: int
    asset_id: str
    text: str
    #: Ticks into the source material. -1 when the clip has no material.
    source_time: int
    #: Ticks since the clip started, which is what keyframes are measured in.
    clip_time: int
    speed: float
    #: ``opacity`` with the fades already applied, so a renderer cannot forget.
    opacity: float
    #: ``volume`` with the fades already applied, and zero on a muted track.
    gain: float
    properties: dict[str, float]
    style: dict[str, Any]
    #: ``{"id","preset","progress","role"}`` while this clip is inside a
    #: transition, otherwise empty. ``progress`` runs 0 → 1 across the whole
    #: window for both sides, so the painter blends one number rather than
    #: reconciling two clocks.
    transition: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "track_id": self.track_id,
            "kind": self.kind,
            "z": self.z,
            "asset_id": self.asset_id,
            "text": self.text,
            "source_time": int(self.source_time),
            "clip_time": int(self.clip_time),
            "speed": round(float(self.speed), 6),
            "opacity": round(float(self.opacity), 6),
            "gain": round(float(self.gain), 6),
            "properties": {name: round(float(value), 6) for name, value in sorted(self.properties.items())},
            "style": dict(self.style),
            "transition": dict(self.transition),
        }


@dataclass
class Frame:
    """Everything visible and audible at one tick, bottom layer first."""

    tick: int
    items: list[DrawItem] = field(default_factory=list)

    @property
    def visible(self) -> list[DrawItem]:
        return [item for item in self.items if item.kind != "audio"]

    @property
    def audible(self) -> list[DrawItem]:
        return [item for item in self.items if item.gain > 0.0]

    def to_dict(self) -> dict[str, Any]:
        return {"tick": int(self.tick), "items": [item.to_dict() for item in self.items]}


def transition_window(track: "Track", item: Transition) -> tuple[int, int] | None:
    """The span both clips are drawn for, centred on their shared cut.

    Returns ``None`` when the two clips are not actually adjacent — a transition
    left behind by an edit that moved one of them. Silently rendering it
    somewhere near the old cut would put a dissolve in the middle of a clip.
    """
    left = next((clip for clip in track.clips if clip.id == item.from_clip_id), None)
    right = next((clip for clip in track.clips if clip.id == item.to_clip_id), None)
    if left is None or right is None or left.end != right.start:
        return None
    half = max(1, int(item.duration) // 2)
    return (max(0, left.end - half), left.end + half)


def _fade_factor(clip: Clip, offset: int) -> float:
    """How far into a fade this instant is, as a multiplier from 0 to 1.

    One fade governs both the picture and the sound of a clip. Separate video
    and audio fades are a real thing CapCut has, and they are not here yet —
    but a clip whose picture fades out while its audio stays at full is worse
    than either, so the single fade is applied to both until there are two.
    """
    factor = 1.0
    if clip.fade_in > 0 and offset < clip.fade_in:
        factor *= max(0.0, offset / clip.fade_in)
    tail = clip.duration - clip.fade_out
    if clip.fade_out > 0 and offset > tail:
        remaining = clip.duration - offset
        factor *= max(0.0, remaining / clip.fade_out)
    return max(0.0, min(1.0, factor))


def clip_gain(track: Track, clip: Clip, offset: int, volume: float | None = None) -> float:
    """How loud this clip is, ``offset`` ticks into itself.

    The only place this rule lives. The resolver needs it to tell the preview
    what it is hearing, and the mixdown planner needs it to build the export's
    gain envelope. Those two giving different answers would be a preview that
    lies about the file it is previewing, so they call the same function.

    ``volume`` is an escape hatch for a caller that has already resolved this
    clip's properties, so the resolver does not do that work twice.
    """
    if track.muted:
        return 0.0
    # A still or a caption on a video track makes no sound. Footage does, even
    # on a video track, because its audio travels inside the same file.
    if track.kind != "audio" and clip.kind != "video":
        return 0.0
    level = clip.property_at(offset)["volume"] if volume is None else volume
    return max(0.0, level * _fade_factor(clip, offset))


def frame_at(project: Project, tick: int) -> Frame:
    """What the viewer sees and hears at ``tick``.

    A clip is live when ``start <= tick < end``. The half-open interval is not a
    detail: a clip ending exactly where the next begins is the ordinary result of
    a split, and treating both as live at the shared tick would make every cut in
    every project a one-frame overlap.
    """
    moment = max(0, int(tick))
    items: list[DrawItem] = []
    for index, track in enumerate(project.tracks):
        # Which clips this instant asks for beyond their own bounds, and how far
        # through the blend it is. Computed once per track rather than per clip:
        # a transition is a property of a boundary, not of either side.
        extended: dict[str, dict[str, Any]] = {}
        for item in track.transitions:
            window = transition_window(track, item)
            if window is None:
                continue
            start, end = window
            if not (start <= moment < end):
                continue
            span = max(1, end - start)
            progress = min(1.0, max(0.0, (moment - start) / span))
            extended[item.from_clip_id] = {
                "id": item.id,
                "preset": item.preset,
                "progress": round(progress, 6),
                "role": "from",
                "partner": item.to_clip_id,
            }
            extended[item.to_clip_id] = {
                "id": item.id,
                "preset": item.preset,
                "progress": round(progress, 6),
                "role": "to",
                "partner": item.from_clip_id,
            }

        for clip in track.clips:
            crossing = extended.get(clip.id, {})
            if not (clip.start <= moment < clip.end) and not crossing:
                continue
            # A clip drawn outside its own bounds is held at its nearest frame —
            # the alternative is reading past the end of its material, which the
            # validator spent its whole existence preventing.
            offset = min(max(0, moment - clip.start), max(0, clip.duration - 1))
            resolved = clip.property_at(offset)
            fade = _fade_factor(clip, offset)
            has_source = clip.kind in ("video", "audio")
            source_time = clip.source_at(offset) if has_source else -1
            gain = clip_gain(track, clip, offset, volume=resolved["volume"])
            # Hiding a track takes away the picture, not the sound. The eye and
            # the speaker are two controls because a voiceover cut against
            # footage has to survive the footage being hidden to look at what is
            # underneath it.
            visible = 0.0 if track.hidden and track.kind == "video" else 1.0
            items.append(
                DrawItem(
                    clip_id=clip.id,
                    track_id=track.id,
                    kind=clip.kind,
                    z=index,
                    asset_id=clip.asset_id,
                    text=clip.text,
                    source_time=source_time,
                    clip_time=offset,
                    speed=clip.speed,
                    opacity=resolved["opacity"] * (fade if track.kind == "video" else 1.0) * visible,
                    gain=gain,
                    properties=resolved,
                    style=dict(clip.style),
                    transition=dict(crossing),
                )
            )
    items.sort(key=lambda item: (item.z, item.clip_id))
    return Frame(tick=moment, items=items)


# ── invariants ──────────────────────────────────────────────────────────────


def _assert_no_overlap(track: Track, *, ignore: str = "") -> None:
    ordered = sorted(
        (clip for clip in track.clips if clip.id != ignore), key=lambda item: item.start
    )
    for left, right in zip(ordered, ordered[1:]):
        if left.end > right.start:
            raise ClipOverlap(
                f"Clips {left.id!r} and {right.id!r} would both occupy track "
                f"{track.id!r} at tick {right.start}. Move one, or put it on "
                "another track — a track cannot show two things at once."
            )


def prune_transitions(track: Track) -> list[Transition]:
    """Drop transitions whose cut no longer exists.

    An edit that moves or deletes one side of a cut leaves a transition
    describing a boundary that is not there any more. Keeping it would mean a
    dissolve reappearing if the clips ever happened to line up again, which is
    the kind of ghost nobody can debug.
    """
    return [item for item in track.transitions if transition_window(track, item) is not None]


def _assert_transitions_fit(track: Track) -> None:
    """A clip must be long enough for the transitions at both its ends.

    Half a transition extends past each side of the cut, so a clip with one at
    each end gives up half of each. If those halves exceed the clip, the two
    transitions overlap *each other* inside it — and a frame belonging to two
    blends at once has no defined answer, which is the same objection as two
    clips claiming one tick.
    """
    consumed: dict[str, int] = {}
    for item in track.transitions:
        if transition_window(track, item) is None:
            continue
        half = max(1, int(item.duration) // 2)
        consumed[item.from_clip_id] = consumed.get(item.from_clip_id, 0) + half
        consumed[item.to_clip_id] = consumed.get(item.to_clip_id, 0) + half
    for clip in track.clips:
        used = consumed.get(clip.id, 0)
        if used > clip.duration:
            raise TimelineError(
                f"The transitions either side of clip {clip.id!r} need {used} "
                f"ticks of it and it is only {clip.duration} long. Shorten one of "
                "them, or make the clip longer — two blends cannot share a frame."
            )


def _assert_editable(track: Track) -> None:
    if track.locked:
        raise TrackLocked(
            f"Track {track.name or track.id!r} is locked. Unlock it to edit it."
        )


def _check_speed(value: float, what: str) -> None:
    """Zero is allowed and means *hold this instant* — a freeze frame.

    It is not a missing value and not an error: a frozen stretch inside a speed
    curve is what every "bullet time" preset is made of. Everything between zero
    and the minimum is refused, because a clip reading a hundredth of a tick per
    tick is a mistake rather than an intention.
    """
    if value == 0:
        return
    if not (MIN_SPEED <= value <= MAX_SPEED):
        raise TimelineError(
            f"{what} must be 0 (freeze) or between {MIN_SPEED} and {MAX_SPEED}; got {value}."
        )


def _validate_clip(clip: Clip, track: Track) -> None:
    if clip.kind not in CLIP_KINDS:
        raise TimelineError(f"Unknown clip kind {clip.kind!r}. Known: {', '.join(CLIP_KINDS)}.")
    if clip.kind not in TRACK_ACCEPTS[track.kind]:
        raise TimelineError(
            f"A {clip.kind} clip cannot go on a {track.kind} track. "
            f"{track.kind.title()} tracks hold: {', '.join(TRACK_ACCEPTS[track.kind])}."
        )
    if clip.start < 0:
        raise TimelineError("A clip cannot start before the beginning of the timeline.")
    if clip.duration < MIN_CLIP_TICKS:
        raise TimelineError(
            f"A clip must be at least {MIN_CLIP_TICKS} ticks "
            f"({ticks_to_seconds(MIN_CLIP_TICKS):.3f}s, one frame at 60fps). "
            f"This one is {clip.duration}."
        )
    _check_speed(clip.speed, "Speed")
    for frame in clip.speed_curve:
        _check_speed(frame.value, f"The speed at tick {frame.at}")
        if not (0 <= frame.at <= clip.duration):
            raise TimelineError(
                f"A speed point at tick {frame.at} is outside a clip {clip.duration} "
                "ticks long, so the clip would never reach it."
            )
        if frame.easing != "linear":
            raise TimelineError(
                f"A speed point cannot be eased ({frame.easing!r}). How much material "
                "a clip reads is the area under its speed curve, and that is only "
                "exact — in both the server and the browser — while the curve is "
                "straight between its points. Use more points instead."
            )
    if len(clip.speed_curve) == 1:
        raise TimelineError(
            "A speed curve of one point is a constant speed written the long way. "
            "Set `speed` instead, or give the curve a second point."
        )
    if clip.in_point < 0:
        raise TimelineError("A clip cannot start reading before the start of its source.")
    if clip.source_duration > 0:
        consumed = int(round(clip.consumed(clip.duration)))
        if clip.in_point + consumed > clip.source_duration:
            over = clip.in_point + consumed - clip.source_duration
            raise TimelineError(
                f"This clip would read {over} ticks past the end of its source "
                f"({clip.source_duration} ticks long). Shorten it, slow it down, "
                "or move its in-point back."
            )
    elif clip.kind not in UNBOUNDED_KINDS:
        raise TimelineError(
            f"A {clip.kind} clip needs a source_duration — how long the material "
            "actually is. Without it nothing can stop an edit reading past its end."
        )
    if clip.fade_in < 0 or clip.fade_out < 0:
        raise TimelineError("A fade cannot be negative.")
    if clip.fade_in + clip.fade_out > clip.duration:
        raise TimelineError(
            f"The fades ({clip.fade_in} + {clip.fade_out}) are longer than the clip "
            f"({clip.duration}), so it would never reach full strength."
        )
