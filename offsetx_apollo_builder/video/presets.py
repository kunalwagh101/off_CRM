"""Transitions, animations and text styles — as data, not as code.

This file is the argument in `CAPCUT_TOOL_INVENTORY.md` made concrete.

CapCut has ~150 transitions and ~120 clip animations. Written as 270 functions
they are 270 units of work and, worse, **270 things an orchestrator cannot
search**. Written as a registry over a handful of families they are one code
change per *family* and one row per preset — and a row can be scored, ranked,
A/B tested and picked by a bandit, because it is data.

```
9 transition families (code)   →  46 transition presets (rows)
6 animation shapes   (code)    →  32 animation presets  (rows)
1 text renderer      (code)    →  12 text styles        (rows)
```

**Default-deny, like every other registry here.** An unlisted preset id is
refused rather than rendered as something arbitrary. A timeline that silently
fell back to a dissolve when asked for a preset the renderer did not know would
export something nobody chose.

**The timeline validates the name; the browser implements the family.** Nothing
in this file knows how to draw. It declares what exists and what parameters each
one carries, which is exactly the split that lets the picture change without the
document changing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# ── transitions ─────────────────────────────────────────────────────────────

#: The families the browser painter implements. Adding a family is a code
#: change in `frontend/src/video/transitions.ts`; adding a *preset* is a row
#: below and nothing else.
TRANSITION_FAMILIES = (
    "dissolve",   # cross-fade on opacity
    "wipe",       # a hard edge travels across
    "slide",      # the incoming clip moves in over the outgoing one
    "push",       # both move together, as if on a strip
    "zoom",       # one scales into or out of the other
    "spin",       # rotation with the cross-fade
    "blur",       # both blur towards the midpoint
    "flash",      # a colour flare covers the cut
    "glitch",     # displacement and channel offset over the cut
)

#: The shortest and longest a transition may be. Under ~6 frames nobody sees
#: it; over two seconds it stops reading as a cut and starts reading as a
#: mistake.
MIN_TRANSITION_TICKS = 9_000     # 0.1s
MAX_TRANSITION_TICKS = 180_000   # 2.0s
DEFAULT_TRANSITION_TICKS = 45_000  # 0.5s


@dataclass(frozen=True)
class TransitionPreset:
    """One named transition. ``family`` decides the code path, ``params`` the look."""

    id: str
    label: str
    family: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "family": self.family, "params": dict(self.params)}


def _t(id: str, label: str, family: str, **params: Any) -> TransitionPreset:
    return TransitionPreset(id=id, label=label, family=family, params=params)


TRANSITIONS: dict[str, TransitionPreset] = {
    preset.id: preset
    for preset in (
        # dissolve
        _t("dissolve", "Dissolve", "dissolve"),
        _t("dissolve_soft", "Soft dissolve", "dissolve", curve="ease_in_out"),
        _t("dip_to_black", "Dip to black", "flash", colour="#000000"),
        _t("dip_to_white", "Dip to white", "flash", colour="#ffffff"),
        # wipe — one family, eight directions
        _t("wipe_left", "Wipe left", "wipe", direction="left"),
        _t("wipe_right", "Wipe right", "wipe", direction="right"),
        _t("wipe_up", "Wipe up", "wipe", direction="up"),
        _t("wipe_down", "Wipe down", "wipe", direction="down"),
        _t("wipe_soft_left", "Soft wipe left", "wipe", direction="left", softness=0.15),
        _t("wipe_soft_right", "Soft wipe right", "wipe", direction="right", softness=0.15),
        _t("wipe_diagonal", "Diagonal wipe", "wipe", direction="diagonal"),
        _t("wipe_barn", "Barn door", "wipe", direction="barn"),
        _t("wipe_iris", "Iris", "wipe", direction="iris"),
        _t("wipe_clock", "Clock", "wipe", direction="clock"),
        # slide
        _t("slide_left", "Slide left", "slide", direction="left"),
        _t("slide_right", "Slide right", "slide", direction="right"),
        _t("slide_up", "Slide up", "slide", direction="up"),
        _t("slide_down", "Slide down", "slide", direction="down"),
        # push
        _t("push_left", "Push left", "push", direction="left"),
        _t("push_right", "Push right", "push", direction="right"),
        _t("push_up", "Push up", "push", direction="up"),
        _t("push_down", "Push down", "push", direction="down"),
        # zoom
        _t("zoom_in", "Zoom in", "zoom", direction="in"),
        _t("zoom_out", "Zoom out", "zoom", direction="out"),
        _t("zoom_blur", "Zoom blur", "zoom", direction="in", blur=24.0),
        _t("whip_left", "Whip left", "zoom", direction="in", blur=40.0, shift="left"),
        _t("whip_right", "Whip right", "zoom", direction="in", blur=40.0, shift="right"),
        # spin
        _t("spin", "Spin", "spin", turns=1.0),
        _t("spin_half", "Half spin", "spin", turns=0.5),
        _t("spin_blur", "Spin blur", "spin", turns=1.0, blur=20.0),
        # blur
        _t("blur_soft", "Soft blur", "blur", radius=18.0),
        _t("blur_hard", "Hard blur", "blur", radius=48.0),
        # flash
        _t("flash_white", "White flash", "flash", colour="#ffffff"),
        _t("flash_black", "Black flash", "flash", colour="#000000"),
        _t("flash_warm", "Warm flare", "flash", colour="#ffd9a0"),
        _t("light_leak", "Light leak", "flash", colour="#ff9a3c", softness=0.5),
        # glitch
        _t("glitch", "Glitch", "glitch", amount=1.0),
        _t("glitch_soft", "Soft glitch", "glitch", amount=0.5),
        _t("glitch_rgb", "RGB split", "glitch", amount=0.7, channels=True),
        _t("glitch_slice", "Slice", "glitch", amount=1.0, slices=12),
        # a few more directions, because a preset costs a row
        _t("wipe_left_soft_wide", "Wide soft wipe", "wipe", direction="left", softness=0.35),
        _t("slide_diagonal", "Slide diagonal", "slide", direction="diagonal"),
        _t("push_diagonal", "Push diagonal", "push", direction="diagonal"),
        _t("zoom_spin", "Zoom spin", "spin", turns=0.75, scale=1.4),
        _t("dissolve_grain", "Grain dissolve", "dissolve", grain=0.4),
        _t("flash_glitch", "Glitch flash", "glitch", amount=1.2, flash="#ffffff"),
    )
}


# ── clip animations ─────────────────────────────────────────────────────────

#: Animation families, by *when* they run. An `in` animation plays over the head
#: of a clip, an `out` over its tail, a `loop` across the whole thing.
ANIMATION_FAMILIES = ("in", "out", "loop")

DEFAULT_ANIMATION_TICKS = 45_000  # 0.5s


@dataclass(frozen=True)
class AnimationPreset:
    """One named animation, expressed as property values to travel between.

    Deliberately *not* a new concept in the resolver. An animation is keyframes,
    and this project already has keyframes that survive a split, travel with a
    trim and interpolate identically in both languages. Inventing a parallel
    animation system would mean inventing all of that again.
    """

    id: str
    label: str
    family: str
    #: property → (value at the start of the window, value at the end)
    moves: dict[str, tuple[float, float]]
    easing: str = "ease_out"
    #: Loop animations repeat this many times across the clip.
    cycles: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "moves": {name: list(pair) for name, pair in self.moves.items()},
            "easing": self.easing,
            "cycles": self.cycles,
        }


def _a(id: str, label: str, family: str, easing: str = "ease_out", cycles: int = 0, **moves: Any) -> AnimationPreset:
    return AnimationPreset(
        id=id,
        label=label,
        family=family,
        moves={name: (float(pair[0]), float(pair[1])) for name, pair in moves.items()},
        easing=easing,
        cycles=cycles,
    )


ANIMATIONS: dict[str, AnimationPreset] = {
    preset.id: preset
    for preset in (
        # in
        _a("fade_in", "Fade in", "in", opacity=(0.0, 1.0)),
        _a("zoom_in", "Zoom in", "in", scale=(0.6, 1.0)),
        _a("zoom_out_in", "Zoom out in", "in", scale=(1.5, 1.0)),
        _a("slide_in_left", "Slide in left", "in", x=(-900.0, 0.0)),
        _a("slide_in_right", "Slide in right", "in", x=(900.0, 0.0)),
        _a("slide_in_up", "Slide in up", "in", y=(900.0, 0.0)),
        _a("slide_in_down", "Slide in down", "in", y=(-900.0, 0.0)),
        _a("spin_in", "Spin in", "in", rotation=(-180.0, 0.0), scale=(0.4, 1.0)),
        _a("blur_in", "Blur in", "in", blur=(30.0, 0.0)),
        _a("pop_in", "Pop in", "in", easing="ease_out", scale=(0.2, 1.0), opacity=(0.0, 1.0)),
        _a("drift_in", "Drift in", "in", easing="linear", scale=(1.08, 1.0), opacity=(0.0, 1.0)),
        _a("rise_in", "Rise in", "in", y=(160.0, 0.0), opacity=(0.0, 1.0)),
        # out
        _a("fade_out", "Fade out", "out", easing="ease_in", opacity=(1.0, 0.0)),
        _a("zoom_out", "Zoom out", "out", easing="ease_in", scale=(1.0, 0.6)),
        _a("zoom_in_out", "Zoom in out", "out", easing="ease_in", scale=(1.0, 1.5)),
        _a("slide_out_left", "Slide out left", "out", easing="ease_in", x=(0.0, -900.0)),
        _a("slide_out_right", "Slide out right", "out", easing="ease_in", x=(0.0, 900.0)),
        _a("slide_out_up", "Slide out up", "out", easing="ease_in", y=(0.0, -900.0)),
        _a("slide_out_down", "Slide out down", "out", easing="ease_in", y=(0.0, 900.0)),
        _a("spin_out", "Spin out", "out", easing="ease_in", rotation=(0.0, 180.0), scale=(1.0, 0.4)),
        _a("blur_out", "Blur out", "out", easing="ease_in", blur=(0.0, 30.0)),
        _a("pop_out", "Pop out", "out", easing="ease_in", scale=(1.0, 0.2), opacity=(1.0, 0.0)),
        _a("sink_out", "Sink out", "out", easing="ease_in", y=(0.0, 160.0), opacity=(1.0, 0.0)),
        _a("drift_out", "Drift out", "out", easing="linear", scale=(1.0, 1.08), opacity=(1.0, 0.0)),
        # loop
        _a("pulse", "Pulse", "loop", easing="ease_in_out", cycles=4, scale=(1.0, 1.08)),
        _a("heartbeat", "Heartbeat", "loop", easing="ease_out", cycles=8, scale=(1.0, 1.12)),
        _a("sway", "Sway", "loop", easing="ease_in_out", cycles=3, rotation=(-3.0, 3.0)),
        _a("float", "Float", "loop", easing="ease_in_out", cycles=3, y=(-18.0, 18.0)),
        _a("shake", "Shake", "loop", easing="linear", cycles=16, x=(-9.0, 9.0)),
        _a("breathe", "Breathe", "loop", easing="ease_in_out", cycles=2, scale=(1.0, 1.04)),
        _a("wobble", "Wobble", "loop", easing="ease_in_out", cycles=6, rotation=(-1.5, 1.5)),
        _a("throb", "Throb", "loop", easing="ease_in_out", cycles=6, opacity=(1.0, 0.75)),
    )
}


# ── text styles ─────────────────────────────────────────────────────────────

#: Named text looks. Style is renderer data — the timeline never reasons about
#: a font — so these are whole style dictionaries rather than a schema.
TEXT_STYLES: dict[str, dict[str, Any]] = {
    "clean": {"size": 72, "weight": "700", "colour": "#ffffff", "stroke": 0, "shadow": 6},
    "caption": {"size": 72, "weight": "800", "colour": "#ffffff", "stroke": 8, "stroke_colour": "#000000"},
    "bold_block": {"size": 84, "weight": "900", "colour": "#ffffff", "background": "#101014"},
    "highlight": {"size": 76, "weight": "800", "colour": "#101014", "background": "#ffd60a"},
    "neon": {"size": 80, "weight": "800", "colour": "#e9fbff", "glow": 24, "glow_colour": "#22d3ee"},
    "outline": {"size": 80, "weight": "900", "colour": "transparent", "stroke": 5, "stroke_colour": "#ffffff"},
    "gradient_warm": {"size": 82, "weight": "900", "gradient": ["#ff9a3c", "#ff3c7d"], "stroke": 3},
    "gradient_cool": {"size": 82, "weight": "900", "gradient": ["#38bdf8", "#818cf8"], "stroke": 3},
    "serif_quiet": {"size": 68, "weight": "500", "font": "Georgia, serif", "colour": "#f5f5f4"},
    "mono_tag": {"size": 48, "weight": "600", "font": "ui-monospace, monospace", "colour": "#a3e635", "letter_spacing": 2},
    "shadow_soft": {"size": 76, "weight": "700", "colour": "#ffffff", "shadow": 18, "shadow_colour": "#000000"},
    "ticker": {"size": 44, "weight": "700", "colour": "#101014", "background": "#ffffff", "letter_spacing": 1},
}


# ── speed curves ────────────────────────────────────────────────────────────

SPEED_FAMILIES = ("ramp", "hero", "impact", "loop")


@dataclass(frozen=True)
class SpeedPreset:
    """A shape for how fast a clip reads, over its own length.

    ``points`` are ``(where, speed)`` with *where* as a fraction of the clip, so
    one preset fits a clip of any length. They become real keyframes in
    :func:`speed_points_for`, which is the only place a fraction meets a
    duration.

    A speed of 0 is a freeze, and it is the whole point of the impact presets:
    what everybody means by "bullet time" is a hard stop in the middle of a
    move, and a curve that can hold at zero says so without needing a second
    feature to say it.
    """

    id: str
    label: str
    family: str
    points: tuple[tuple[float, float], ...]
    note: str = ""

    @property
    def average(self) -> float:
        """How much material this consumes per tick of timeline, on average.

        The area under the curve over its own length — which is exactly what
        decides whether a clip still fits inside its source. Reported so a UI
        can say "this needs 1.8× the material" before an edit is refused for
        precisely that.
        """
        total = 0.0
        for (left_at, left_speed), (right_at, right_speed) in zip(self.points, self.points[1:]):
            total += (left_speed + right_speed) / 2 * (right_at - left_at)
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "points": [[round(at, 4), round(speed, 4)] for at, speed in self.points],
            "average": round(self.average, 4),
            "note": self.note,
        }


def _s(id: str, label: str, family: str, note: str, *points: tuple[float, float]) -> SpeedPreset:
    return SpeedPreset(id=id, label=label, family=family, points=tuple(points), note=note)


SPEED_CURVES: dict[str, SpeedPreset] = {
    preset.id: preset
    for preset in (
        # ramp — one direction, the plainest thing a curve can do
        _s("ramp_up", "Ramp up", "ramp", "Slow into fast.", (0.0, 0.5), (1.0, 2.0)),
        _s("ramp_down", "Ramp down", "ramp", "Fast into slow.", (0.0, 2.0), (1.0, 0.5)),
        _s("ease_in_fast", "Ease in fast", "ramp", "Holds, then runs.",
           (0.0, 0.4), (0.6, 0.5), (1.0, 3.0)),
        _s("ease_out_slow", "Ease out slow", "ramp", "Runs, then settles.",
           (0.0, 3.0), (0.4, 0.5), (1.0, 0.4)),
        # hero — fast in, slow through the thing worth seeing, fast out
        _s("hero", "Hero", "hero", "Fast, slow on the subject, fast.",
           (0.0, 2.5), (0.3, 0.5), (0.7, 0.5), (1.0, 2.5)),
        _s("hero_soft", "Hero soft", "hero", "The same shape, less extreme.",
           (0.0, 1.6), (0.3, 0.7), (0.7, 0.7), (1.0, 1.6)),
        _s("reveal", "Reveal", "hero", "Slow open, then away.",
           (0.0, 0.4), (0.35, 0.4), (1.0, 2.5)),
        # impact — a stop in the middle, which is what "bullet time" means
        _s("bullet", "Bullet", "impact", "Runs in, freezes, runs out.",
           (0.0, 3.0), (0.35, 0.0), (0.55, 0.0), (1.0, 3.0)),
        _s("stutter", "Stutter", "impact", "Three hard stops.",
           (0.0, 2.0), (0.2, 0.0), (0.3, 2.0), (0.45, 0.0), (0.55, 2.0), (0.7, 0.0), (1.0, 2.0)),
        _s("punch", "Punch", "impact", "One beat, held near the end.",
           (0.0, 1.4), (0.7, 1.4), (0.78, 0.0), (0.86, 0.0), (1.0, 2.2)),
        # loop — a rate that comes back to where it started
        _s("pulse", "Pulse", "loop", "Speeds up and back, twice.",
           (0.0, 1.0), (0.25, 2.0), (0.5, 1.0), (0.75, 2.0), (1.0, 1.0)),
        _s("breathe", "Breathe", "loop", "One slow swell.",
           (0.0, 1.0), (0.5, 0.45), (1.0, 1.0)),
    )
}


# ── lookups, default-deny ───────────────────────────────────────────────────


class UnknownPreset(ValueError):
    """A preset nobody declared. Never rendered as something arbitrary."""


def speed_curve(preset_id: str) -> SpeedPreset:
    key = str(preset_id or "").strip()
    if key not in SPEED_CURVES:
        raise UnknownPreset(
            f"Unknown speed curve {preset_id!r}. A clip that quietly fell back to "
            "one flat rate would export something nobody chose. Known: "
            f"{', '.join(sorted(SPEED_CURVES))}."
        )
    return SPEED_CURVES[key]


def speed_points_for(preset_id: str, duration: int) -> list[dict[str, Any]]:
    """A preset's points as real keyframes on a clip of this length.

    The only place a fraction meets a duration. Points land on whole ticks and
    two that round to the same tick collapse — a vertical jump in speed has no
    single area under it, and this is where that becomes representable if it is
    allowed to.
    """
    preset = speed_curve(preset_id)
    span = max(1, int(duration))
    seen: dict[int, float] = {}
    for at, value in preset.points:
        seen[max(0, min(span, int(round(at * span))))] = float(value)
    return [{"at": at, "value": seen[at], "easing": "linear"} for at in sorted(seen)]


def transition(preset_id: str) -> TransitionPreset:
    key = str(preset_id or "").strip()
    if key not in TRANSITIONS:
        raise UnknownPreset(
            f"Unknown transition {preset_id!r}. A timeline that quietly fell back "
            "to a dissolve would export something nobody chose. Known: "
            f"{', '.join(sorted(TRANSITIONS))}."
        )
    return TRANSITIONS[key]


def animation(preset_id: str) -> AnimationPreset:
    key = str(preset_id or "").strip()
    if key not in ANIMATIONS:
        raise UnknownPreset(
            f"Unknown animation {preset_id!r}. Known: {', '.join(sorted(ANIMATIONS))}."
        )
    return ANIMATIONS[key]


def text_style(name: str) -> dict[str, Any]:
    key = str(name or "").strip()
    if key not in TEXT_STYLES:
        raise UnknownPreset(
            f"Unknown text style {name!r}. Known: {', '.join(sorted(TEXT_STYLES))}."
        )
    return dict(TEXT_STYLES[key])


def catalogue() -> dict[str, Any]:
    """Everything declared, for the UI and for anything that searches the space."""
    return {
        "transitions": [item.to_dict() for item in TRANSITIONS.values()],
        "transition_families": list(TRANSITION_FAMILIES),
        "animations": [item.to_dict() for item in ANIMATIONS.values()],
        "animation_families": list(ANIMATION_FAMILIES),
        "text_styles": {name: dict(style) for name, style in TEXT_STYLES.items()},
        "speed_curves": [item.to_dict() for item in SPEED_CURVES.values()],
        "speed_families": list(SPEED_FAMILIES),
        "limits": {
            "min_transition_ticks": MIN_TRANSITION_TICKS,
            "max_transition_ticks": MAX_TRANSITION_TICKS,
            "default_transition_ticks": DEFAULT_TRANSITION_TICKS,
            "default_animation_ticks": DEFAULT_ANIMATION_TICKS,
        },
    }


def keyframes_for(
    preset: AnimationPreset, *, window: int, clip_duration: int
) -> dict[str, list[tuple[int, float, str]]]:
    """An animation turned into (at, value, easing) triples per property.

    This is where a preset stops being data and becomes the same keyframes
    anyone could have set by hand — which is the point. Once applied there is
    nothing special about an animated clip, so every existing edit still works
    on it.
    """
    span = max(1, min(int(window), int(clip_duration)))
    out: dict[str, list[tuple[int, float, str]]] = {}

    for name, (start_value, end_value) in preset.moves.items():
        points: list[tuple[int, float, str]] = []
        if preset.family == "in":
            points = [(0, start_value, preset.easing), (span, end_value, "linear")]
        elif preset.family == "out":
            tail = max(0, int(clip_duration) - span)
            points = [(tail, start_value, preset.easing), (int(clip_duration), end_value, "linear")]
        else:
            # A loop travels out and back, `cycles` times across the whole clip,
            # so it ends where it started and a repeat does not jump.
            cycles = max(1, preset.cycles)
            step = max(1, int(clip_duration) // (cycles * 2))
            at = 0
            toggle = False
            while at <= int(clip_duration):
                points.append((at, end_value if toggle else start_value, preset.easing))
                toggle = not toggle
                at += step
            if points[-1][0] < int(clip_duration):
                points.append((int(clip_duration), start_value, preset.easing))
        out[name] = points
    return out
