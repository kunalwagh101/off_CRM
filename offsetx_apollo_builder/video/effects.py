"""Effects and filters — 48 primitives in code, a catalogue of looks as data.

The same argument `presets.py` makes about transitions, made about the part of
an editor that is by far the largest. CapCut ships something like eight hundred
filters and effects. Written as eight hundred implementations they are eight
hundred units of work and, worse, **eight hundred things an orchestrator cannot
search**. Written as a registry over a small set of pixel operations they are
one code change per *operation* and one row per look.

```
48 primitives (GLSL, in the browser)  →  the code
124 presets   (rows, in this file)    →  the data
```

**A preset is an ordered stack, not a single knob.** A film look is a tone
curve, then a grade, then a grain, then a vignette — in that order, because
these do not commute. So a preset is a list of `(primitive, params)` and the
renderer runs it as a chain of full-screen passes.

**Every preset gets a strength slider for free.** Each parameter declares the
value at which its primitive does *nothing* — its ``neutral``. Applying a preset
at `amount` interpolates every scaling parameter from neutral toward the
preset's value, so `amount=0` is a guaranteed no-op and `amount=0.5` is half the
look. Colours and structural choices (which way a mirror folds, how many
kaleidoscope segments) do not interpolate and say so by declaring no neutral —
half a fold is not a fold.

**Default-deny, like every other registry here.** An unlisted primitive or
preset id is refused by name. Nothing falls back to "no effect", because a
timeline that silently dropped a look would export something nobody chose, and
it would look like it worked.

**The server resolves; the browser executes.** A resolved chain is flat: names
and numbers, no lookups. That is deliberately the opposite of how transitions
work, where the browser fetches the catalogue and resolves a preset itself — a
transition preset is one row, and an effect preset is a stack drawn from a
catalogue too large to ship in order to draw one clip.

**How many presets is honest.** The primitives are the complete set; adding the
eight-hundredth look is one row in `EFFECTS` and no code anywhere. What is *in*
this file is a curated catalogue of looks that were each chosen, not a cartesian
product of parameters with generated names. A permuted eight hundred would score
better on a feature map and be worth less than the hundred-odd here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# ── the parameter model ─────────────────────────────────────────────────────

#: A parameter is `(default, minimum, maximum, neutral)`.
#:
#: ``neutral`` is the value at which this parameter's primitive does nothing,
#: and it is what makes a strength slider work: applying at `amount` moves every
#: parameter from its neutral toward the preset's value. ``None`` means the
#: parameter does not interpolate — colours, and structural choices where a
#: half-way value is not a smaller version of the thing but a different thing.
NumberSpec = tuple[float, float, float, float | None]

#: Colour parameters are hex strings, validated but never interpolated.
COLOUR = "colour"


class UnknownPrimitive(ValueError):
    """A pixel operation nobody implemented."""


class UnknownEffect(ValueError):
    """A look nobody declared."""


@dataclass(frozen=True)
class Primitive:
    """One pixel operation the browser knows how to run.

    ``passes`` is how many full-screen draws it costs. Everything is one except
    the separable blurs, which are two — horizontal then vertical — because a
    two-dimensional gaussian done properly is two one-dimensional ones and doing
    it in a single pass costs the square of the samples for the same picture.
    """

    id: str
    label: str
    group: str
    note: str
    numbers: dict[str, NumberSpec] = field(default_factory=dict)
    colours: dict[str, str] = field(default_factory=dict)
    passes: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "note": self.note,
            "passes": self.passes,
            "numbers": {
                name: {
                    "default": spec[0],
                    "min": spec[1],
                    "max": spec[2],
                    "neutral": spec[3],
                    "scales": spec[3] is not None,
                }
                for name, spec in self.numbers.items()
            },
            "colours": dict(self.colours),
        }


def _p(
    id: str,
    label: str,
    group: str,
    note: str,
    *,
    passes: int = 1,
    colours: Mapping[str, str] | None = None,
    **numbers: NumberSpec,
) -> Primitive:
    return Primitive(
        id=id,
        label=label,
        group=group,
        note=note,
        numbers=dict(numbers),
        colours=dict(colours or {}),
        passes=passes,
    )


# ── the primitives ──────────────────────────────────────────────────────────
#
# Adding one of these is a code change in `frontend/src/video/shaders/`. Adding
# a *preset* below is a row and nothing else. That ratio is the whole design.

PRIMITIVES: dict[str, Primitive] = {
    item.id: item
    for item in (
        # ── tone and colour ─────────────────────────────────────────────────
        _p("exposure", "Exposure", "tone",
           "Stops of light, multiplied in linear space so highlights roll rather than clip.",
           stops=(0.0, -4.0, 4.0, 0.0)),
        _p("contrast", "Contrast", "tone",
           "Pushes away from a pivot. The pivot matters: around 0.5 it darkens shadows, "
           "around 0.18 it protects them.",
           amount=(0.2, -1.0, 2.0, 0.0), pivot=(0.5, 0.0, 1.0, None)),
        _p("saturation", "Saturation", "tone",
           "Mixes toward luma. Below zero desaturates, above one oversaturates.",
           amount=(0.2, -1.0, 2.0, 0.0)),
        _p("vibrance", "Vibrance", "tone",
           "Saturation weighted by how unsaturated a pixel already is, so skin survives it.",
           amount=(0.3, -1.0, 1.0, 0.0)),
        _p("temperature", "Temperature", "tone",
           "Warm and cool as a red/blue rebalance, not a hue rotation.",
           amount=(0.0, -1.0, 1.0, 0.0)),
        _p("tint", "Tint", "tone",
           "The other axis: green against magenta.",
           amount=(0.0, -1.0, 1.0, 0.0)),
        _p("hue_rotate", "Hue rotate", "tone",
           "Rotates every hue by the same angle.",
           degrees=(0.0, -180.0, 180.0, 0.0)),
        _p("levels", "Levels", "tone",
           "Black point, white point and gamma — the three that fix a flat log-ish source.",
           black=(0.0, 0.0, 0.9, 0.0), white=(1.0, 0.1, 1.0, 1.0), gamma=(1.0, 0.1, 4.0, 1.0)),
        _p("curve_s", "Filmic curve", "tone",
           "An S-curve through the midtones. Contrast that keeps its ends.",
           amount=(0.4, -1.0, 1.0, 0.0)),
        _p("fade", "Fade", "tone",
           "Lifts the blacks. The single move that makes digital read as film stock.",
           amount=(0.2, 0.0, 1.0, 0.0)),
        _p("bleach_bypass", "Bleach bypass", "tone",
           "Retains the silver: contrast up, saturation down, highlights blown.",
           amount=(0.6, 0.0, 1.0, 0.0)),
        _p("duotone", "Duotone", "tone",
           "Maps luminance between two colours. Everything in between is a blend of them.",
           amount=(1.0, 0.0, 1.0, 0.0),
           colours={"dark": "#101820", "light": "#f5e6c8"}),
        _p("split_tone", "Split tone", "tone",
           "One colour into the shadows, another into the highlights, meeting at balance.",
           amount=(0.5, 0.0, 1.0, 0.0), balance=(0.5, 0.0, 1.0, None),
           colours={"shadow": "#1b3a5c", "highlight": "#ffd9a0"}),
        _p("posterize", "Posterize", "tone",
           "Quantises each channel. Low counts are a poster; high counts are a subtle "
           "banding. The neutral is 256 and not 64 for an exact reason: an 8-bit "
           "channel quantised to 64 levels is off by about one step, so a preset "
           "containing a posterize would not be quite a no-op at strength zero — "
           "which is the one promise the strength slider makes.",
           levels=(8.0, 2.0, 256.0, 256.0)),
        _p("threshold", "Threshold", "tone",
           "Everything above the level goes white, everything below black.",
           level=(0.5, 0.0, 1.0, None), softness=(0.05, 0.0, 0.5, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("invert", "Invert", "tone",
           "Negative. Every channel subtracted from one, mixed back by amount.",
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("sepia", "Sepia", "tone",
           "The brown wash, as the standard channel matrix rather than as a tint.",
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("grayscale", "Black and white", "tone",
           "Luma weights, with a channel mixer so a red filter can darken a sky.",
           amount=(1.0, 0.0, 1.0, 0.0), red=(0.2126, 0.0, 2.0, None),
           green=(0.7152, 0.0, 2.0, None), blue=(0.0722, 0.0, 2.0, None)),

        # ── focus ───────────────────────────────────────────────────────────
        _p("blur", "Blur", "focus",
           "A separable gaussian: horizontal, then vertical.",
           radius=(8.0, 0.0, 200.0, 0.0), passes=2),
        _p("directional_blur", "Directional blur", "focus",
           "Smears along one angle. Motion, without a motion vector.",
           radius=(12.0, 0.0, 200.0, 0.0), angle=(0.0, -180.0, 180.0, None)),
        _p("radial_blur", "Radial blur", "focus",
           "Smears outward from a point. The zoom-punch look.",
           amount=(0.15, 0.0, 1.0, 0.0), centre_x=(0.5, 0.0, 1.0, None),
           centre_y=(0.5, 0.0, 1.0, None)),
        _p("sharpen", "Sharpen", "focus",
           "Unsharp mask: the picture minus a blurred copy of itself, added back.",
           amount=(0.5, 0.0, 3.0, 0.0), radius=(1.5, 0.5, 8.0, None)),
        _p("bloom", "Bloom", "focus",
           "Everything above the threshold blurs and adds back. Light bleeding.",
           threshold=(0.7, 0.0, 1.0, None), radius=(24.0, 1.0, 200.0, None),
           intensity=(0.6, 0.0, 3.0, 0.0), passes=3),
        _p("soft_focus", "Soft focus", "focus",
           "A blurred copy mixed back over the sharp one. Bloom without the threshold.",
           radius=(18.0, 1.0, 200.0, None), amount=(0.4, 0.0, 1.0, 0.0), passes=3),
        _p("tilt_shift", "Tilt shift", "focus",
           "Blur everywhere except a band. A miniature, or an eye-line.",
           radius=(20.0, 1.0, 200.0, None), focus=(0.5, 0.0, 1.0, None),
           width=(0.25, 0.02, 1.0, None), amount=(1.0, 0.0, 1.0, 0.0), passes=3),

        # ── distortion ──────────────────────────────────────────────────────
        _p("pixelate", "Pixelate", "distort",
           "Snaps to a grid. The size is in output pixels, so it reads the same at any canvas.",
           size=(12.0, 1.0, 200.0, 1.0)),
        _p("chromatic_aberration", "Chromatic aberration", "distort",
           "Channels drift apart with distance from the centre, the way a cheap lens does.",
           amount=(0.004, 0.0, 0.08, 0.0)),
        _p("lens_distortion", "Lens distortion", "distort",
           "Barrel below zero, pincushion above.",
           amount=(0.2, -1.0, 1.0, 0.0)),
        _p("rgb_split", "RGB split", "distort",
           "A flat channel offset along one angle. Unlike aberration it does not fall off.",
           amount=(0.006, 0.0, 0.1, 0.0), angle=(0.0, -180.0, 180.0, None)),
        _p("displace", "Displace", "distort",
           "Pushes pixels around by a noise field. The base of every glitch.",
           amount=(0.02, 0.0, 0.3, 0.0), scale=(6.0, 0.5, 60.0, None),
           speed=(1.0, 0.0, 20.0, None)),
        _p("wave", "Wave", "distort",
           "A sine warp. Axis 0 ripples horizontally, 1 vertically.",
           amplitude=(0.02, 0.0, 0.3, 0.0), frequency=(6.0, 0.5, 40.0, None),
           speed=(1.0, 0.0, 20.0, None), axis=(0.0, 0.0, 1.0, None)),
        _p("swirl", "Swirl", "distort",
           "Rotates by an amount that falls off with radius.",
           amount=(1.0, -6.0, 6.0, 0.0), radius=(0.5, 0.05, 1.5, None),
           centre_x=(0.5, 0.0, 1.0, None), centre_y=(0.5, 0.0, 1.0, None)),
        _p("kaleidoscope", "Kaleidoscope", "distort",
           "Folds one wedge around a centre. Segments do not interpolate — three is not "
           "half of six, it is a different picture.",
           segments=(6.0, 2.0, 24.0, None), angle=(0.0, -180.0, 180.0, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("mirror", "Mirror", "distort",
           "Folds one half onto the other. Axis 0 is left–right, 1 is top–bottom.",
           axis=(0.0, 0.0, 1.0, None), side=(0.0, 0.0, 1.0, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("punch", "Punch in", "distort",
           "Scales about a point in pixel space, after everything upstream.",
           scale=(1.15, 0.2, 6.0, 1.0), centre_x=(0.5, 0.0, 1.0, None),
           centre_y=(0.5, 0.0, 1.0, None)),

        # ── texture ─────────────────────────────────────────────────────────
        _p("grain", "Film grain", "texture",
           "Noise that changes every frame, seeded by the frame number rather than by "
           "chance — a re-export has to produce the same file.",
           amount=(0.15, 0.0, 1.0, 0.0), size=(1.0, 0.3, 8.0, None)),
        _p("noise", "Static noise", "texture",
           "The same field every frame. Reads as texture rather than as movement.",
           amount=(0.15, 0.0, 1.0, 0.0), size=(1.0, 0.3, 8.0, None)),
        _p("scanlines", "Scanlines", "texture",
           "Dark horizontal bands. A count rather than a spacing, so it survives a resize.",
           count=(240.0, 10.0, 2000.0, None), amount=(0.3, 0.0, 1.0, 0.0),
           speed=(0.0, 0.0, 20.0, None)),
        _p("halftone", "Halftone", "texture",
           "Dots on a rotated grid, sized by luminance. Print, badly.",
           size=(6.0, 2.0, 60.0, None), angle=(15.0, -180.0, 180.0, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("dither", "Dither", "texture",
           "An ordered 4×4 Bayer matrix before quantisation. Banding, on purpose.",
           levels=(4.0, 2.0, 32.0, None), amount=(1.0, 0.0, 1.0, 0.0)),

        # ── shape, matte and key ────────────────────────────────────────────
        _p("vignette", "Vignette", "shape",
           "Darkens toward the corners. Radius is where it starts, softness how far it takes.",
           amount=(0.4, 0.0, 1.0, 0.0), radius=(0.75, 0.1, 1.5, None),
           softness=(0.45, 0.01, 1.5, None), colours={"colour": "#000000"}),
        _p("rounded_frame", "Rounded frame", "shape",
           "Corner radius and a border, in output pixels.",
           radius=(24.0, 0.0, 400.0, 0.0), border=(0.0, 0.0, 200.0, 0.0),
           colours={"border_colour": "#ffffff"}),
        _p("drop_shadow", "Drop shadow", "shape",
           "The alpha of the layer, blurred, offset and drawn underneath it.",
           radius=(18.0, 0.0, 200.0, 0.0), offset_x=(0.0, -400.0, 400.0, None),
           offset_y=(12.0, -400.0, 400.0, None), opacity=(0.5, 0.0, 1.0, 0.0),
           colours={"colour": "#000000"}, passes=3),
        _p("chroma_key", "Chroma key", "shape",
           "Removes one colour. Tolerance is how far a pixel may be and still go; spill "
           "pulls the key colour back out of what is left, which is the half people skip.",
           tolerance=(0.35, 0.0, 1.0, None), softness=(0.1, 0.0, 0.5, None),
           spill=(0.5, 0.0, 1.0, None), amount=(1.0, 0.0, 1.0, 0.0),
           colours={"colour": "#00ff00"}),
        _p("luma_key", "Luma key", "shape",
           "Removes by brightness instead of by hue. Invert flips which end goes.",
           threshold=(0.15, 0.0, 1.0, None), softness=(0.1, 0.0, 0.5, None),
           invert=(0.0, 0.0, 1.0, None), amount=(1.0, 0.0, 1.0, 0.0)),
        _p("mask_linear", "Linear mask", "shape",
           "A straight edge. Everything on one side of it is hidden.",
           angle=(0.0, -180.0, 180.0, None), position=(0.5, -0.5, 1.5, None),
           softness=(0.1, 0.0, 1.0, None), invert=(0.0, 0.0, 1.0, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("mask_radial", "Radial mask", "shape",
           "A circle. Everything outside it is hidden, or inside it when inverted.",
           centre_x=(0.5, 0.0, 1.0, None), centre_y=(0.5, 0.0, 1.0, None),
           radius=(0.4, 0.01, 2.0, None), softness=(0.15, 0.0, 1.0, None),
           aspect=(1.0, 0.1, 10.0, None), invert=(0.0, 0.0, 1.0, None),
           amount=(1.0, 0.0, 1.0, 0.0)),
        _p("edge", "Edge detect", "shape",
           "Sobel. Mixed back over the picture, or shown on its own at full amount.",
           amount=(1.0, 0.0, 1.0, 0.0), thickness=(1.0, 0.5, 6.0, None),
           blend=(1.0, 0.0, 1.0, None)),
    )
}

#: The groups a primitive can belong to, for a UI that has to put forty things
#: somewhere.
PRIMITIVE_GROUPS = ("tone", "focus", "distort", "texture", "shape")


def primitive(primitive_id: str) -> Primitive:
    key = str(primitive_id or "").strip()
    if key not in PRIMITIVES:
        known = ", ".join(sorted(PRIMITIVES))
        raise UnknownPrimitive(f"Unknown effect primitive {primitive_id!r}. Known: {known}.")
    return PRIMITIVES[key]


# ── a look is an ordered stack of primitives ────────────────────────────────


@dataclass(frozen=True)
class Step:
    """One primitive in a preset, with the parameters that define this look."""

    primitive: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"primitive": self.primitive, "params": dict(self.params)}


@dataclass(frozen=True)
class Effect:
    """One named look. ``steps`` run in order, and the order is part of the look."""

    id: str
    label: str
    pack: str
    note: str
    steps: tuple[Step, ...] = ()

    @property
    def passes(self) -> int:
        """What this look costs, in full-screen draws."""
        return sum(PRIMITIVES[step.primitive].passes for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "pack": self.pack,
            "note": self.note,
            "passes": self.passes,
            "primitives": [step.primitive for step in self.steps],
            "steps": [step.to_dict() for step in self.steps],
        }


def _s(primitive_id: str, **params: Any) -> Step:
    return Step(primitive=primitive_id, params=params)


def _e(id: str, label: str, pack: str, note: str, *steps: Step) -> Effect:
    return Effect(id=id, label=label, pack=pack, note=note, steps=tuple(steps))


#: The packs a look belongs to. A flat list of a hundred names is unusable; the
#: pack is how a person and an orchestrator both narrow it.
EFFECT_PACKS = (
    "film",      # stock emulations and filmic grades
    "cine",      # the graded, deliberate looks
    "mono",      # black and white
    "vintage",   # old media, warmly
    "damage",    # old media, badly
    "pop",       # bright, saturated, social
    "neon",      # night, cyber, colour-lit
    "dream",     # soft, hazy, romantic
    "print",     # halftone, posterised, screen-printed
    "utility",   # keys, masks, focus and repair — tools rather than looks
)


#: Written as separate tuples per pack purely so this file stays readable; they
#: are merged into one flat registry at the bottom.
_FILM_TO_VINTAGE: tuple[Effect, ...] = (
        # ── film ────────────────────────────────────────────────────────────
        _e("film_neutral", "Film neutral", "film",
           "The baseline stock: a gentle S, lifted blacks and the finest grain.",
           _s("curve_s", amount=0.25), _s("fade", amount=0.12), _s("grain", amount=0.08, size=1.0)),
        _e("film_warm", "Film warm", "film", "Neutral, pushed toward tungsten.",
           _s("curve_s", amount=0.28), _s("temperature", amount=0.22),
           _s("fade", amount=0.14), _s("grain", amount=0.1)),
        _e("film_cool", "Film cool", "film", "Neutral, pushed toward daylight-at-dusk.",
           _s("curve_s", amount=0.28), _s("temperature", amount=-0.22),
           _s("fade", amount=0.14), _s("grain", amount=0.1)),
        _e("kodachrome", "Kodachrome", "film",
           "Saturated reds, deep blacks, almost no grain. The slide-film look.",
           _s("contrast", amount=0.3, pivot=0.45), _s("vibrance", amount=0.4),
           _s("split_tone", amount=0.25, balance=0.55, shadow="#12202e", highlight="#ffe0b0"),
           _s("grain", amount=0.05)),
        _e("portra", "Portra", "film", "Soft contrast, warm skin, creamy highlights.",
           _s("curve_s", amount=0.18), _s("temperature", amount=0.15),
           _s("saturation", amount=-0.08), _s("fade", amount=0.18),
           _s("grain", amount=0.09)),
        _e("cinestill", "Cinestill", "film",
           "Tungsten stock shot in daylight, with the halation that made it famous.",
           _s("temperature", amount=-0.25), _s("bloom", threshold=0.68, radius=30.0, intensity=0.9),
           _s("fade", amount=0.16), _s("grain", amount=0.12)),
        _e("ektar", "Ektar", "film", "The punchy one: clean, cold and very saturated.",
           _s("contrast", amount=0.35), _s("vibrance", amount=0.5),
           _s("temperature", amount=-0.12), _s("grain", amount=0.04)),
        _e("superia", "Superia", "film", "Consumer stock: green midtones and loud grain.",
           _s("tint", amount=-0.18), _s("curve_s", amount=0.3),
           _s("saturation", amount=0.15), _s("grain", amount=0.2, size=1.4)),
        _e("film_expired", "Expired stock", "film",
           "Colour that has drifted, contrast that has not survived.",
           _s("temperature", amount=0.3), _s("tint", amount=0.22),
           _s("fade", amount=0.35), _s("saturation", amount=-0.25),
           _s("grain", amount=0.24, size=1.6)),
        _e("film_push", "Pushed two stops", "film",
           "Underexposed and developed hard. Grain first, detail second.",
           _s("exposure", stops=0.5), _s("contrast", amount=0.45, pivot=0.42),
           _s("grain", amount=0.35, size=1.3), _s("fade", amount=0.1)),
        _e("super8", "Super 8", "film", "Small gauge: warm, soft, heavy grain, dark corners.",
           _s("temperature", amount=0.28), _s("soft_focus", radius=8.0, amount=0.3),
           _s("grain", amount=0.3, size=2.0), _s("vignette", amount=0.45, radius=0.6)),
        _e("technicolor", "Three-strip", "film",
           "Primaries separated to the point of being a costume decision.",
           _s("saturation", amount=0.55), _s("contrast", amount=0.3),
           _s("split_tone", amount=0.3, balance=0.5, shadow="#0d1f3d", highlight="#ffcf7a")),
        _e("film_bleach", "Bleach bypass", "film",
           "Silver retained: the war-film look, contrast up and colour drained.",
           _s("bleach_bypass", amount=0.7), _s("grain", amount=0.12)),
        _e("film_halation", "Halation", "film", "Just the red bleed around the highlights.",
           _s("bloom", threshold=0.72, radius=26.0, intensity=0.8),
           _s("temperature", amount=0.1)),
        _e("film_dust", "Dust and scratch", "film", "Grain, dirt and a soft edge.",
           _s("grain", amount=0.28, size=1.8), _s("noise", amount=0.08, size=3.0),
           _s("vignette", amount=0.3)),
        _e("film_flat", "Flat log", "film",
           "Deliberately ungraded — lifted, desaturated, waiting for a grade.",
           _s("fade", amount=0.3), _s("saturation", amount=-0.3), _s("contrast", amount=-0.25)),

        # ── cine ────────────────────────────────────────────────────────────
        _e("teal_orange", "Teal and orange", "cine",
           "The blockbuster grade: skin warm, everything behind it cold.",
           _s("split_tone", amount=0.55, balance=0.5, shadow="#12444f", highlight="#ff9c52"),
           _s("contrast", amount=0.22), _s("vibrance", amount=0.2)),
        _e("noir", "Noir", "cine", "Hard mono with a heavy edge and a deep vignette.",
           _s("grayscale", amount=1.0), _s("contrast", amount=0.55, pivot=0.45),
           _s("vignette", amount=0.6, radius=0.62), _s("grain", amount=0.14)),
        _e("moonlight", "Moonlight", "cine", "Night that is blue rather than dark.",
           _s("exposure", stops=-0.4), _s("temperature", amount=-0.5),
           _s("split_tone", amount=0.4, balance=0.4, shadow="#0a1a3a", highlight="#9ec6ff"),
           _s("fade", amount=0.12)),
        _e("golden_hour", "Golden hour", "cine", "Low warm sun and a soft bloom.",
           _s("temperature", amount=0.4), _s("bloom", threshold=0.65, radius=28.0, intensity=0.5),
           _s("split_tone", amount=0.35, balance=0.6, shadow="#3a2410", highlight="#ffc472")),
        _e("desert", "Desert", "cine", "Dust, heat and yellow-green shadows.",
           _s("temperature", amount=0.3), _s("tint", amount=-0.15),
           _s("contrast", amount=0.25), _s("saturation", amount=-0.12),
           _s("vignette", amount=0.3)),
        _e("nordic", "Nordic", "cine", "Cold, desaturated, low contrast. Everything is January.",
           _s("temperature", amount=-0.35), _s("saturation", amount=-0.35),
           _s("contrast", amount=-0.1), _s("fade", amount=0.2)),
        _e("thriller", "Thriller", "cine", "Crushed blacks, cold cast, tight vignette.",
           _s("levels", black=0.06, white=1.0, gamma=0.95), _s("temperature", amount=-0.28),
           _s("contrast", amount=0.35), _s("vignette", amount=0.55, radius=0.65)),
        _e("dystopia", "Dystopia", "cine", "Green-grey, bleached, unhappy.",
           _s("bleach_bypass", amount=0.5), _s("tint", amount=-0.3),
           _s("vignette", amount=0.4), _s("grain", amount=0.16)),
        _e("romance", "Romance", "cine", "Warm, soft, slightly overexposed.",
           _s("exposure", stops=0.25), _s("temperature", amount=0.25),
           _s("soft_focus", radius=16.0, amount=0.35), _s("fade", amount=0.18)),
        _e("documentary", "Documentary", "cine",
           "Honest: a small S-curve, correct colour, nothing else.",
           _s("curve_s", amount=0.2), _s("vibrance", amount=0.12)),
        _e("epic", "Epic", "cine", "Wide and heavy: contrast, saturation, deep corners.",
           _s("contrast", amount=0.4, pivot=0.46), _s("vibrance", amount=0.35),
           _s("vignette", amount=0.45), _s("sharpen", amount=0.3)),
        _e("interrogation", "Interrogation", "cine",
           "One hard light: high key centre, everything else gone.",
           _s("contrast", amount=0.5), _s("vignette", amount=0.75, radius=0.5, softness=0.3),
           _s("saturation", amount=-0.4)),
        _e("underwater", "Underwater", "cine", "Blue-green cast with light falling off.",
           _s("temperature", amount=-0.45), _s("tint", amount=-0.2),
           _s("soft_focus", radius=10.0, amount=0.25), _s("vignette", amount=0.4)),
        _e("firelight", "Firelight", "cine", "Warm from below, dark at the edges.",
           _s("temperature", amount=0.5), _s("split_tone", amount=0.4, balance=0.55,
                                             shadow="#2a1005", highlight="#ffb057"),
           _s("vignette", amount=0.5), _s("grain", amount=0.1)),

        # ── mono ────────────────────────────────────────────────────────────
        _e("mono", "Black and white", "mono", "Straight luma weights and nothing else.",
           _s("grayscale", amount=1.0)),
        _e("mono_contrast", "High contrast mono", "mono", "The same, pushed hard.",
           _s("grayscale", amount=1.0), _s("contrast", amount=0.5, pivot=0.48)),
        _e("mono_soft", "Soft mono", "mono", "Lifted blacks and a gentle curve.",
           _s("grayscale", amount=1.0), _s("fade", amount=0.25), _s("curve_s", amount=0.15)),
        _e("mono_red_filter", "Mono, red filter", "mono",
           "The darkroom trick: weight red heavily and a blue sky goes black.",
           _s("grayscale", amount=1.0, red=0.8, green=0.2, blue=0.0),
           _s("contrast", amount=0.3)),
        _e("mono_orange_filter", "Mono, orange filter", "mono",
           "Less brutal than red. Skin stays where it should.",
           _s("grayscale", amount=1.0, red=0.55, green=0.4, blue=0.05)),
        _e("mono_green_filter", "Mono, green filter", "mono",
           "Foliage separates; skin goes heavy.",
           _s("grayscale", amount=1.0, red=0.1, green=0.8, blue=0.1)),
        _e("mono_grain", "Tri-X", "mono", "Fast stock: mono, hard, and grain you can count.",
           _s("grayscale", amount=1.0), _s("contrast", amount=0.4),
           _s("grain", amount=0.3, size=1.5)),
        _e("mono_selenium", "Selenium tone", "mono", "Cold mono with a violet shadow.",
           _s("grayscale", amount=1.0),
           _s("split_tone", amount=0.35, balance=0.45, shadow="#2a2a52", highlight="#f0f0ff")),
        _e("mono_sepia", "Sepia", "mono", "The oldest one there is.",
           _s("grayscale", amount=1.0), _s("sepia", amount=0.85)),
        _e("mono_platinum", "Platinum", "mono", "Long tonal range, no true black.",
           _s("grayscale", amount=1.0), _s("fade", amount=0.3),
           _s("levels", black=0.0, white=0.94, gamma=1.1)),
        _e("high_key", "High key", "mono", "Almost everything above the midpoint.",
           _s("grayscale", amount=1.0), _s("exposure", stops=0.6), _s("fade", amount=0.3)),
        _e("low_key", "Low key", "mono", "Almost everything below it.",
           _s("grayscale", amount=1.0), _s("exposure", stops=-0.6),
           _s("contrast", amount=0.4), _s("vignette", amount=0.55)),

        # ── vintage ─────────────────────────────────────────────────────────
        _e("polaroid", "Polaroid", "vintage", "Warm, low contrast, blown highlights.",
           _s("fade", amount=0.32), _s("temperature", amount=0.22),
           _s("exposure", stops=0.2), _s("saturation", amount=-0.1),
           _s("vignette", amount=0.25)),
        _e("faded_seventies", "1970s", "vintage", "Orange, soft and tired.",
           _s("temperature", amount=0.35), _s("fade", amount=0.3),
           _s("saturation", amount=-0.2), _s("grain", amount=0.18)),
        _e("eighties", "1980s", "vintage", "Magenta and cyan, hard light.",
           _s("split_tone", amount=0.45, balance=0.5, shadow="#2a0d4a", highlight="#ffd0e8"),
           _s("contrast", amount=0.3), _s("saturation", amount=0.25)),
        _e("vhs", "VHS", "vintage", "Tape: chroma bleed, wobble, scanlines and noise.",
           _s("rgb_split", amount=0.005), _s("wave", amplitude=0.004, frequency=18.0, speed=2.0),
           _s("scanlines", count=280.0, amount=0.28), _s("noise", amount=0.12),
           _s("saturation", amount=-0.15)),
        _e("crt", "CRT", "vintage", "Scanlines, a soft glow and curved-lens falloff.",
           _s("scanlines", count=420.0, amount=0.35), _s("bloom", threshold=0.6,
                                                          radius=12.0, intensity=0.5),
           _s("lens_distortion", amount=0.12), _s("vignette", amount=0.4)),
        _e("camcorder", "Camcorder", "vintage", "Soft, noisy, slightly green.",
           _s("soft_focus", radius=6.0, amount=0.3), _s("tint", amount=-0.15),
           _s("noise", amount=0.14), _s("scanlines", count=240.0, amount=0.15)),
        _e("old_photo", "Old photograph", "vintage", "Sepia, dust and dark corners.",
           _s("sepia", amount=0.75), _s("fade", amount=0.25),
           _s("noise", amount=0.1, size=2.5), _s("vignette", amount=0.45)),
        _e("daguerreotype", "Daguerreotype", "vintage",
           "Silver plate: cold mono, high contrast, heavy edges.",
           _s("grayscale", amount=1.0), _s("contrast", amount=0.45),
           _s("split_tone", amount=0.3, balance=0.5, shadow="#1e2230", highlight="#e8e4d0"),
           _s("vignette", amount=0.6, radius=0.6)),
        _e("cross_process", "Cross process", "vintage",
           "Developed in the wrong chemistry: cyan shadows, yellow highlights.",
           _s("split_tone", amount=0.6, balance=0.5, shadow="#0f5a6e", highlight="#ffe66b"),
           _s("contrast", amount=0.4), _s("saturation", amount=0.2)),
        _e("lomo", "Lomo", "vintage", "Saturated, contrasty, and very dark at the edges.",
           _s("saturation", amount=0.45), _s("contrast", amount=0.4),
           _s("vignette", amount=0.7, radius=0.55)),
        _e("infrared", "Infrared", "vintage", "Foliage white, sky black.",
           _s("hue_rotate", degrees=120.0),
           _s("contrast", amount=0.4), _s("grain", amount=0.14)),
        _e("nickelodeon", "Silent era", "vintage",
           "Mono, flickering exposure, dirt and a hard vignette.",
           _s("grayscale", amount=1.0), _s("contrast", amount=0.4),
           _s("noise", amount=0.16, size=2.0), _s("vignette", amount=0.55),
           _s("scanlines", count=90.0, amount=0.12)),
        _e("faded_poster", "Faded poster", "vintage", "Sun-bleached: colour gone, paper left.",
           _s("saturation", amount=-0.45), _s("fade", amount=0.35),
           _s("temperature", amount=0.2), _s("noise", amount=0.08, size=3.0)),
        _e("tintype", "Tintype", "vintage", "Brown, blotchy and very much of 1870.",
           _s("grayscale", amount=1.0), _s("sepia", amount=0.6),
           _s("noise", amount=0.18, size=2.5), _s("vignette", amount=0.65, radius=0.55)),
)


_POP_TO_DREAM: tuple[Effect, ...] = (
    # ── pop ─────────────────────────────────────────────────────────────────
    _e("bright", "Bright", "pop", "Lift, clarity and a little colour. The default fix.",
       _s("exposure", stops=0.3), _s("contrast", amount=0.15), _s("vibrance", amount=0.25)),
    _e("crisp", "Crisp", "pop", "Sharpened and contrasty, for something shot soft.",
       _s("sharpen", amount=0.8), _s("contrast", amount=0.25), _s("vibrance", amount=0.2)),
    _e("punchy", "Punchy", "pop", "Everything up. The thumbnail look.",
       _s("contrast", amount=0.4), _s("saturation", amount=0.4), _s("sharpen", amount=0.5)),
    _e("candy", "Candy", "pop", "Pink highlights, cyan shadows, saturation past sensible.",
       _s("saturation", amount=0.5),
       _s("split_tone", amount=0.4, balance=0.5, shadow="#1ad0e0", highlight="#ff8fd0")),
    _e("sunny", "Sunny", "pop", "Warm and open, as if the sun came out.",
       _s("temperature", amount=0.28), _s("exposure", stops=0.25),
       _s("vibrance", amount=0.3), _s("bloom", threshold=0.75, radius=18.0, intensity=0.35)),
    _e("fresh", "Fresh", "pop", "Cool, clean and slightly green. Product-shot default.",
       _s("temperature", amount=-0.15), _s("tint", amount=-0.08),
       _s("contrast", amount=0.2), _s("sharpen", amount=0.4)),
    _e("matte_pop", "Matte pop", "pop", "Saturated colour on lifted blacks.",
       _s("fade", amount=0.22), _s("saturation", amount=0.35), _s("contrast", amount=0.2)),
    _e("clarity", "Clarity", "pop", "Local contrast only: sharpen wide, leave colour alone.",
       _s("sharpen", amount=0.9, radius=4.0)),
    _e("skin", "Skin", "pop", "Warm, soft and desaturated just enough to be kind.",
       _s("temperature", amount=0.16), _s("soft_focus", radius=10.0, amount=0.22),
       _s("vibrance", amount=0.15), _s("saturation", amount=-0.08)),
    _e("food", "Food", "pop", "Warm, saturated, sharp. Every menu photograph.",
       _s("temperature", amount=0.2), _s("vibrance", amount=0.4),
       _s("sharpen", amount=0.6), _s("contrast", amount=0.2)),
    _e("street", "Street", "pop", "Contrast and grain, colour left where it was.",
       _s("contrast", amount=0.35), _s("grain", amount=0.14), _s("vignette", amount=0.25)),
    _e("hdr", "HDR", "pop", "Flattened dynamic range and heavy local contrast.",
       _s("levels", black=0.02, white=0.98, gamma=1.25), _s("sharpen", amount=1.1, radius=5.0),
       _s("vibrance", amount=0.3)),

    # ── neon ────────────────────────────────────────────────────────────────
    _e("cyberpunk", "Cyberpunk", "neon", "Magenta and cyan, bloomed and aberrated.",
       _s("split_tone", amount=0.55, balance=0.5, shadow="#0d2b6b", highlight="#ff2fd0"),
       _s("bloom", threshold=0.6, radius=32.0, intensity=0.9),
       _s("chromatic_aberration", amount=0.006), _s("contrast", amount=0.3)),
    _e("neon_night", "Neon night", "neon", "Dark, saturated, and glowing where it is bright.",
       _s("exposure", stops=-0.35), _s("saturation", amount=0.45),
       _s("bloom", threshold=0.55, radius=28.0, intensity=1.0), _s("vignette", amount=0.45)),
    _e("synthwave", "Synthwave", "neon", "Purple sky, orange sun, scanlines over it.",
       _s("split_tone", amount=0.6, balance=0.45, shadow="#2a0a5e", highlight="#ff7a3d"),
       _s("bloom", threshold=0.65, radius=24.0, intensity=0.8),
       _s("scanlines", count=300.0, amount=0.16)),
    _e("vaporwave", "Vaporwave", "neon", "Washed pastels, split channels, drifting.",
       _s("split_tone", amount=0.5, balance=0.5, shadow="#5be0e8", highlight="#ffb0e6"),
       _s("fade", amount=0.25), _s("rgb_split", amount=0.005), _s("saturation", amount=0.2)),
    _e("blade", "Blade", "neon", "Cold rain and hot signage.",
       _s("temperature", amount=-0.4), _s("bloom", threshold=0.62, radius=30.0, intensity=0.9),
       _s("split_tone", amount=0.35, balance=0.45, shadow="#07203f", highlight="#ff9a3c"),
       _s("vignette", amount=0.5)),
    _e("laser", "Laser", "neon", "Edges only, glowing.",
       _s("edge", amount=1.0, thickness=1.5, blend=0.85),
       _s("saturation", amount=0.6), _s("bloom", threshold=0.4, radius=20.0, intensity=1.2)),
    _e("infra_neon", "Infra", "neon", "Hue rotated until nothing is its own colour.",
       _s("hue_rotate", degrees=150.0), _s("saturation", amount=0.4),
       _s("bloom", threshold=0.6, radius=20.0, intensity=0.6)),
    _e("club", "Club", "neon", "Blown highlights and colour everywhere.",
       _s("exposure", stops=0.2), _s("saturation", amount=0.5),
       _s("bloom", threshold=0.5, radius=36.0, intensity=1.1), _s("grain", amount=0.12)),
    _e("hologram", "Hologram", "neon", "Cyan, scanned, and not quite registered.",
       _s("duotone", amount=0.75, dark="#021d2e", light="#7ff6ff"),
       _s("scanlines", count=380.0, amount=0.3), _s("rgb_split", amount=0.004),
       _s("bloom", threshold=0.5, radius=18.0, intensity=0.8)),
    _e("ultraviolet", "Ultraviolet", "neon", "Everything under a blacklight.",
       _s("duotone", amount=0.6, dark="#0a0028", light="#c69bff"),
       _s("saturation", amount=0.4), _s("bloom", threshold=0.55, radius=24.0, intensity=0.9)),
    _e("acid", "Acid", "neon", "Posterised, hue-shifted, unpleasant on purpose.",
       _s("posterize", levels=6.0), _s("hue_rotate", degrees=60.0),
       _s("saturation", amount=0.7), _s("contrast", amount=0.3)),
    _e("thermal", "Thermal", "neon", "A false-colour heat map from luminance.",
       _s("grayscale", amount=1.0),
       _s("duotone", amount=1.0, dark="#000a4a", light="#ffe94a"),
       _s("contrast", amount=0.3)),

    # ── dream ───────────────────────────────────────────────────────────────
    _e("dreamy", "Dreamy", "dream", "Soft, lifted and warm.",
       _s("soft_focus", radius=22.0, amount=0.45), _s("fade", amount=0.22),
       _s("temperature", amount=0.15)),
    _e("haze", "Haze", "dream", "Air between the camera and everything.",
       _s("fade", amount=0.3), _s("soft_focus", radius=14.0, amount=0.3),
       _s("saturation", amount=-0.15)),
    _e("glow", "Glow", "dream", "Bloom on its own, generously.",
       _s("bloom", threshold=0.55, radius=34.0, intensity=0.9)),
    _e("ethereal", "Ethereal", "dream", "Cool, bright and almost gone.",
       _s("exposure", stops=0.4), _s("temperature", amount=-0.2),
       _s("soft_focus", radius=26.0, amount=0.5), _s("fade", amount=0.28)),
    _e("blush", "Blush", "dream", "Pink light and a soft edge.",
       _s("split_tone", amount=0.4, balance=0.55, shadow="#4a2440", highlight="#ffc9d8"),
       _s("soft_focus", radius=16.0, amount=0.35)),
    _e("memory", "Memory", "dream", "Warm, grainy, and blurred at the edges.",
       _s("temperature", amount=0.25), _s("fade", amount=0.28),
       _s("tilt_shift", radius=26.0, focus=0.5, width=0.4, amount=0.8),
       _s("grain", amount=0.16)),
    _e("sleep", "Sleep", "dream", "Dark, blue and very soft.",
       _s("exposure", stops=-0.3), _s("temperature", amount=-0.35),
       _s("soft_focus", radius=30.0, amount=0.55)),
    _e("bokeh_frame", "Bokeh frame", "dream",
       "A sharp centre and a blurred everything-else, without a depth map.",
       _s("tilt_shift", radius=32.0, focus=0.5, width=0.3, amount=1.0)),
    _e("miniature", "Miniature", "dream", "Tilt-shift plus saturation, so the world looks small.",
       _s("tilt_shift", radius=26.0, focus=0.55, width=0.22, amount=1.0),
       _s("saturation", amount=0.4), _s("contrast", amount=0.25)),
    _e("watercolour", "Watercolour", "dream", "Posterised, softened, paper-pale.",
       _s("posterize", levels=10.0), _s("soft_focus", radius=8.0, amount=0.4),
       _s("fade", amount=0.2), _s("saturation", amount=-0.1)),
)


_DAMAGE_TO_UTILITY: tuple[Effect, ...] = (
    # ── damage ──────────────────────────────────────────────────────────────
    _e("glitch", "Glitch", "damage", "Displacement, split channels and noise.",
       _s("displace", amount=0.03, scale=8.0, speed=6.0), _s("rgb_split", amount=0.008),
       _s("noise", amount=0.1)),
    _e("glitch_hard", "Hard glitch", "damage", "The same, past the point of readability.",
       _s("displace", amount=0.09, scale=14.0, speed=12.0), _s("rgb_split", amount=0.02),
       _s("posterize", levels=6.0), _s("noise", amount=0.18)),
    _e("datamosh", "Datamosh", "damage", "Smeared blocks in one direction.",
       _s("pixelate", size=14.0), _s("directional_blur", radius=28.0, angle=8.0),
       _s("rgb_split", amount=0.01)),
    _e("signal_loss", "Signal loss", "damage", "Rolling wobble, heavy noise, drained colour.",
       _s("wave", amplitude=0.02, frequency=26.0, speed=8.0),
       _s("noise", amount=0.28), _s("saturation", amount=-0.4),
       _s("scanlines", count=300.0, amount=0.3)),
    _e("broken_tape", "Broken tape", "damage", "VHS, further gone.",
       _s("rgb_split", amount=0.014), _s("wave", amplitude=0.01, frequency=40.0, speed=14.0),
       _s("scanlines", count=260.0, amount=0.4), _s("noise", amount=0.22),
       _s("vignette", amount=0.4)),
    _e("static", "Static", "damage", "Mostly noise, with a picture behind it.",
       _s("noise", amount=0.5, size=1.0), _s("saturation", amount=-0.6),
       _s("contrast", amount=0.3)),
    _e("crushed", "Crushed", "damage", "Quantised to almost nothing, then dithered.",
       _s("dither", levels=3.0, amount=1.0), _s("contrast", amount=0.3)),
    _e("shatter", "Shatter", "damage", "Kaleidoscope with an ugly segment count.",
       _s("kaleidoscope", segments=7.0, angle=12.0, amount=1.0),
       _s("chromatic_aberration", amount=0.01)),
    _e("melt", "Melt", "damage", "A slow vertical wave and a smear.",
       _s("wave", amplitude=0.05, frequency=3.0, speed=1.5, axis=1.0),
       _s("directional_blur", radius=16.0, angle=90.0)),
    _e("overdrive", "Overdrive", "damage", "Clipped, aberrated, blown out.",
       _s("exposure", stops=0.9), _s("contrast", amount=0.6),
       _s("chromatic_aberration", amount=0.012), _s("bloom", threshold=0.5,
                                                     radius=30.0, intensity=1.3)),
    _e("xerox", "Photocopy", "damage", "Threshold and dirt. Fifth generation.",
       _s("grayscale", amount=1.0), _s("threshold", level=0.55, softness=0.08, amount=0.9),
       _s("noise", amount=0.14, size=2.0)),
    _e("smear", "Smear", "damage", "One long directional blur and nothing else.",
       _s("directional_blur", radius=48.0, angle=0.0)),

    # ── print ───────────────────────────────────────────────────────────────
    _e("halftone", "Halftone", "print", "Newsprint dots, at an angle.",
       _s("grayscale", amount=1.0), _s("halftone", size=6.0, angle=15.0, amount=1.0)),
    _e("halftone_colour", "Colour halftone", "print", "The same, in colour.",
       _s("halftone", size=7.0, angle=15.0, amount=0.9), _s("saturation", amount=0.3)),
    _e("newsprint", "Newsprint", "print", "Halftone on paper-warm grey.",
       _s("grayscale", amount=1.0), _s("fade", amount=0.2),
       _s("halftone", size=5.0, angle=45.0, amount=1.0), _s("sepia", amount=0.25)),
    _e("screenprint", "Screen print", "print", "Three flat colours and hard edges.",
       _s("posterize", levels=3.0), _s("saturation", amount=0.5),
       _s("contrast", amount=0.4)),
    _e("risograph", "Risograph", "print", "Two inks, slightly out of register.",
       _s("duotone", amount=0.85, dark="#1c2a8a", light="#ff4f7b"),
       _s("rgb_split", amount=0.003), _s("noise", amount=0.1)),
    _e("comic", "Comic", "print", "Edges drawn over flat colour.",
       _s("posterize", levels=5.0), _s("edge", amount=0.8, thickness=1.2, blend=0.5),
       _s("saturation", amount=0.35)),
    _e("blueprint", "Blueprint", "print", "White lines on cyanotype blue.",
       _s("edge", amount=1.0, thickness=1.0, blend=1.0),
       _s("duotone", amount=1.0, dark="#0a2b6b", light="#e8f2ff"),
       _s("invert", amount=1.0)),
    _e("pixel_art", "Pixel art", "print", "Quantised in space and in colour.",
       _s("pixelate", size=10.0), _s("posterize", levels=6.0),
       _s("saturation", amount=0.3)),
    _e("ascii_dither", "Bayer", "print", "Ordered dithering, two levels.",
       _s("grayscale", amount=1.0), _s("dither", levels=2.0, amount=1.0)),
    _e("poster", "Poster", "print", "Four inks and a heavy contrast.",
       _s("posterize", levels=4.0), _s("contrast", amount=0.45),
       _s("saturation", amount=0.4)),

    # ── utility ─────────────────────────────────────────────────────────────
    #
    # Not looks. Tools, in the same registry because the renderer does not care
    # which is which and neither does an orchestrator picking one.
    _e("green_screen", "Green screen", "utility",
       "Keys mid-green with spill suppression. Start here and widen the tolerance.",
       _s("chroma_key", colour="#00b140", tolerance=0.36, softness=0.1, spill=0.6)),
    _e("blue_screen", "Blue screen", "utility", "The same, for blue.",
       _s("chroma_key", colour="#0047bb", tolerance=0.36, softness=0.1, spill=0.6)),
    _e("drop_black", "Drop black", "utility",
       "Removes the dark end. Titles and logos on black become overlays.",
       _s("luma_key", threshold=0.12, softness=0.08)),
    _e("drop_white", "Drop white", "utility", "The other end, for scans and screenshots.",
       _s("luma_key", threshold=0.9, softness=0.08, invert=1.0)),
    _e("spotlight", "Spotlight", "utility", "A soft circle; everything else goes.",
       _s("mask_radial", centre_x=0.5, centre_y=0.5, radius=0.45, softness=0.25)),
    _e("bottom_fade", "Bottom fade", "utility",
       "A linear matte up from the base — where a caption sits.",
       _s("mask_linear", angle=90.0, position=0.85, softness=0.35, invert=1.0)),
    _e("rounded", "Rounded corners", "utility", "A corner radius, and nothing else.",
       _s("rounded_frame", radius=36.0)),
    _e("card", "Card", "utility", "Rounded, with a white border and a shadow under it.",
       _s("rounded_frame", radius=32.0, border=6.0, border_colour="#ffffff"),
       _s("drop_shadow", radius=24.0, offset_y=14.0, opacity=0.45)),
    _e("repair_soft", "Repair: soft source", "utility",
       "Sharpen and a little contrast, for something that arrived blurry.",
       _s("sharpen", amount=1.0, radius=2.0), _s("contrast", amount=0.15)),
    _e("repair_flat", "Repair: flat source", "utility",
       "Black point, white point and a curve. The first thing to try on anything grey.",
       _s("levels", black=0.03, white=0.97, gamma=1.0), _s("curve_s", amount=0.25),
       _s("vibrance", amount=0.2)),
    _e("repair_dark", "Repair: underexposed", "utility",
       "Lift, then hold the blacks so the lift does not reveal only noise.",
       _s("exposure", stops=0.8), _s("levels", black=0.04, white=1.0, gamma=0.92),
       _s("vibrance", amount=0.15)),
    _e("repair_warm", "Repair: wrong white balance", "utility",
       "Pulls a tungsten-lit shot back toward neutral.",
       _s("temperature", amount=-0.35), _s("tint", amount=0.1)),
)


#: Every declared look, flat. The packs above are for reading this file; nothing
#: downstream knows they were ever separate.
EFFECTS: dict[str, Effect] = {
    item.id: item for item in (*_FILM_TO_VINTAGE, *_POP_TO_DREAM, *_DAMAGE_TO_UTILITY)
}


# ── resolution: a reference becomes a chain of passes ───────────────────────

#: The most primitives one clip may stack.
#:
#: Not a performance guess — it is what stops a document from being a denial of
#: service against the machine that has to draw it. Each pass is a full-screen
#: draw at the project's resolution, and a preset already costs up to five, so
#: this is roughly a dozen looks deep and far past anything anyone stacks on
#: purpose.
MAX_STEPS_PER_CLIP = 48

#: The strength of a look, and the two ends of it. Zero is a guaranteed no-op,
#: because every scaling parameter interpolates from the value at which its
#: primitive does nothing.
MIN_AMOUNT = 0.0
MAX_AMOUNT = 1.0


def _hex_colour(value: Any, *, what: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("#") or len(text) not in (4, 7):
        raise ValueError(f"{what} must be a hex colour like #1b3a5c, not {value!r}.")
    body = text[1:]
    if any(character not in "0123456789abcdefABCDEF" for character in body):
        raise ValueError(f"{what} must be a hex colour like #1b3a5c, not {value!r}.")
    if len(body) == 3:
        # Expand so the renderer never has to know about the short form.
        text = "#" + "".join(character * 2 for character in body)
    return text.lower()


def _number(spec: NumberSpec, value: Any, *, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number, not {value!r}.") from None
    if number != number:  # NaN compares false against everything, including itself
        return spec[0]
    return max(spec[1], min(spec[2], number))


def resolve_primitive(
    primitive_id: str,
    params: Mapping[str, Any] | None = None,
    *,
    amount: float = 1.0,
) -> dict[str, Any]:
    """One primitive, with its parameters checked, scaled and clamped.

    ``amount`` moves every *scaling* parameter from the value at which this
    primitive does nothing toward the value asked for, which is what gives every
    look a strength slider without a single preset having to think about it.
    Parameters with no neutral — colours, a mirror's axis, a kaleidoscope's
    segment count — are structural, and half of one of those is not a weaker
    version of the thing but a different thing.
    """
    spec = primitive(primitive_id)
    given = dict(params or {})
    strength = max(MIN_AMOUNT, min(MAX_AMOUNT, float(amount)))

    unknown = sorted(set(given) - set(spec.numbers) - set(spec.colours))
    if unknown:
        known = ", ".join(sorted([*spec.numbers, *spec.colours])) or "none"
        raise ValueError(
            f"{spec.id} has no parameter {unknown[0]!r}. Its parameters are: {known}."
        )

    numbers: dict[str, float] = {}
    for name, number_spec in spec.numbers.items():
        target = _number(number_spec, given.get(name, number_spec[0]), what=f"{spec.id}.{name}")
        neutral = number_spec[3]
        if neutral is not None:
            target = neutral + (target - neutral) * strength
        numbers[name] = round(target, 6)

    colours: dict[str, str] = {}
    for name, default in spec.colours.items():
        colours[name] = _hex_colour(given.get(name, default), what=f"{spec.id}.{name}")

    return {
        "primitive": spec.id,
        "passes": spec.passes,
        "numbers": numbers,
        "colours": colours,
    }


def effect(effect_id: str) -> Effect:
    key = str(effect_id or "").strip()
    if key not in EFFECTS:
        raise UnknownEffect(
            f"Unknown effect {effect_id!r}. There are {len(EFFECTS)} declared looks; "
            f"ask /video/effects for the list."
        )
    return EFFECTS[key]


def resolve(
    effect_id: str,
    *,
    amount: float = 1.0,
    params: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """One look, flattened into the passes the renderer runs, in order.

    ``params`` overrides parameters *by name across the whole stack*, which is
    how a look gets dialled rather than replaced — ``{"radius": 40}`` on a bloom
    preset widens the bloom and leaves the grade alone, because only one step
    has a ``radius``. A name no step in this look has is refused rather than
    ignored, so a typo does not silently do nothing.
    """
    look = effect(effect_id)
    overrides = dict(params or {})
    used: set[str] = set()
    chain: list[dict[str, Any]] = []
    for step in look.steps:
        spec = PRIMITIVES[step.primitive]
        merged = dict(step.params)
        for name, value in overrides.items():
            if name in spec.numbers or name in spec.colours:
                merged[name] = value
                used.add(name)
        chain.append(resolve_primitive(step.primitive, merged, amount=amount))
    stray = sorted(set(overrides) - used)
    if stray:
        known = sorted({name for step in look.steps
                        for name in (*PRIMITIVES[step.primitive].numbers,
                                     *PRIMITIVES[step.primitive].colours)})
        raise ValueError(
            f"{look.id} has no step with a {stray[0]!r} parameter. It takes: "
            f"{', '.join(known) or 'nothing'}."
        )
    return chain


def resolve_stack(refs: Any) -> list[dict[str, Any]]:
    """A clip's whole effect list, flattened.

    Each reference names **either** a declared look or a single primitive.
    Allowing a bare primitive is not a hole in the default-deny rule — a
    primitive id is as declared as a preset id — and it is what lets an
    orchestrator compose something the catalogue does not contain yet.
    """
    chain: list[dict[str, Any]] = []
    for index, ref in enumerate(list(refs or [])):
        if not isinstance(ref, Mapping):
            raise ValueError(f"Effect {index} must be an object, not {ref!r}.")
        preset_id = str(ref.get("preset") or "").strip()
        primitive_id = str(ref.get("primitive") or "").strip()
        if bool(preset_id) == bool(primitive_id):
            raise ValueError(
                f"Effect {index} must name exactly one of preset or primitive."
            )
        amount = float(ref.get("amount", 1.0))
        params = ref.get("params") or {}
        if not isinstance(params, Mapping):
            raise ValueError(f"Effect {index} params must be an object.")
        if preset_id:
            chain.extend(resolve(preset_id, amount=amount, params=params))
        else:
            chain.append(resolve_primitive(primitive_id, params, amount=amount))
    if len(chain) > MAX_STEPS_PER_CLIP:
        raise ValueError(
            f"That is {len(chain)} pixel operations on one clip; the ceiling is "
            f"{MAX_STEPS_PER_CLIP}. Every one is a full-screen draw per frame."
        )
    return chain


def normalise(ref: Mapping[str, Any]) -> dict[str, Any]:
    """One reference, checked and cleaned, ready to store in a document.

    Resolution is not stored — a document holds the *name* of a look, so
    improving the look improves every project that used it. What is stored is
    the reference, and this is the only thing that decides it is a valid one.
    """
    resolve_stack([ref])
    preset_id = str(ref.get("preset") or "").strip()
    primitive_id = str(ref.get("primitive") or "").strip()
    item: dict[str, Any] = {
        "amount": round(max(MIN_AMOUNT, min(MAX_AMOUNT, float(ref.get("amount", 1.0)))), 6),
        "params": {str(name): value for name, value in dict(ref.get("params") or {}).items()},
    }
    if preset_id:
        item["preset"] = preset_id
    else:
        item["primitive"] = primitive_id
    return item


def label_for(ref: Mapping[str, Any]) -> str:
    """What to call one entry in a stack, on a screen."""
    preset_id = str(ref.get("preset") or "").strip()
    if preset_id:
        return effect(preset_id).label
    return primitive(str(ref.get("primitive") or "")).label


def catalogue() -> dict[str, Any]:
    """Everything a screen or an orchestrator needs to choose from."""
    return {
        "primitives": [item.to_dict() for item in PRIMITIVES.values()],
        "primitive_groups": list(PRIMITIVE_GROUPS),
        "effects": [item.to_dict() for item in EFFECTS.values()],
        "packs": list(EFFECT_PACKS),
        "max_steps_per_clip": MAX_STEPS_PER_CLIP,
    }
