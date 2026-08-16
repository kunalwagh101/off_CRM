"""How a video is put together, as data.

A recipe is a shape: how long the opening is, how many cuts the middle gets,
which animation each stretch uses, what happens between them. It is the thing a
person means when they say "make it like one of those hook-then-payoff clips",
written down so a machine can follow it.

---

**Why this is data and the assembler is code.**

The obvious way to build "AI that edits video" is to have a model emit a
timeline. It is also the way that cannot work here: a model that writes a
document directly writes invalid ones — clips that overlap, transitions that do
not fit, footage read past its end — and every invariant this project spent its
existence enforcing becomes a suggestion.

So the split is: **a model chooses a recipe and writes the words; it never
builds the timeline.** Choosing from a declared list is something a model is
good at and something that can be checked. Assembly is arithmetic, it runs
without a model, and its output goes through the same :mod:`edits` functions a
person's clicks do — so an assembled project is valid for exactly the same
reason a hand-made one is.

That also makes the whole space *searchable*, which is the point of every other
registry here. A recipe is rows; an orchestrator can score them against what
performed and pick differently next week without anyone editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .timeline import TICKS_PER_SECOND

#: What a recipe is for. Not a taste label — each of these is a different
#: *structure*, and the difference shows up in the beat shares.
RECIPE_FAMILIES = ("hook", "list", "story", "montage", "demo")


@dataclass(frozen=True)
class Beat:
    """One stretch of the finished video, and how it is treated.

    ``share`` is a fraction of the whole, so a recipe fits any target length.
    The rest is a reference into the preset registries — an animation id, a
    speed curve id, a text style — which is what keeps a recipe a description
    rather than a second implementation of the editor.
    """

    name: str
    share: float
    #: An id from ``presets.ANIMATIONS``, applied to every clip in this beat.
    animation: str = ""
    #: An id from ``presets.SPEED_CURVES``, applied to footage that has the
    #: material to spare. Stills have no material, so they never take one.
    speed: str = ""
    #: An id from ``presets.TEXT_STYLES`` for any line that lands here.
    text_style: str = "caption"
    #: How many cuts this beat gets, before the material has its say.
    min_clips: int = 1
    max_clips: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "share": round(self.share, 4),
            "animation": self.animation,
            "speed": self.speed,
            "text_style": self.text_style,
            "min_clips": self.min_clips,
            "max_clips": self.max_clips,
        }


@dataclass(frozen=True)
class Recipe:
    """A whole structure, from first frame to last."""

    id: str
    label: str
    family: str
    beats: tuple[Beat, ...]
    #: What goes between beats. Empty means a hard cut, which is a choice —
    #: fast content is often worse with a dissolve on every join.
    transition: str = ""
    transition_ticks: int = 30_000
    #: How loud the music sits when there is also a voice over it.
    music_gain: float = 0.35
    #: How loud the music sits on its own.
    music_gain_alone: float = 0.85
    note: str = ""

    @property
    def shares(self) -> float:
        return sum(beat.share for beat in self.beats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "beats": [beat.to_dict() for beat in self.beats],
            "transition": self.transition,
            "transition_ticks": self.transition_ticks,
            "music_gain": self.music_gain,
            "music_gain_alone": self.music_gain_alone,
            "note": self.note,
        }


def _b(name: str, share: float, **kwargs: Any) -> Beat:
    return Beat(name=name, share=share, **kwargs)


def _r(id: str, label: str, family: str, note: str, *beats: Beat, **kwargs: Any) -> Recipe:
    return Recipe(id=id, label=label, family=family, beats=tuple(beats), note=note, **kwargs)


RECIPES: dict[str, Recipe] = {
    recipe.id: recipe
    for recipe in (
        # ── hook: the first second decides whether there is a second one ─────
        _r(
            "hook_hold_payoff",
            "Hook, hold, payoff",
            "hook",
            "A hard opening, a steady middle, a close that lands.",
            _b("hook", 0.18, animation="pop_in", speed="ramp_up", text_style="bold_block", max_clips=1),
            _b("hold", 0.60, animation="drift_in", text_style="caption", min_clips=2, max_clips=5),
            _b("payoff", 0.22, animation="rise_in", speed="hero", text_style="highlight", max_clips=2),
            transition="dissolve",
        ),
        _r(
            "pattern_interrupt",
            "Pattern interrupt",
            "hook",
            "Opens on something that does not belong, then explains itself.",
            _b("interrupt", 0.12, animation="zoom_out_in", speed="bullet", text_style="neon", max_clips=1),
            _b("explain", 0.66, animation="fade_in", text_style="clean", min_clips=3, max_clips=6),
            _b("land", 0.22, animation="pop_in", text_style="highlight", max_clips=2),
            transition="whip_left",
            transition_ticks=18_000,
        ),
        # ── list: numbered points, one cut each ─────────────────────────────
        _r(
            "three_points",
            "Three points",
            "list",
            "A title, three even beats, a close.",
            _b("title", 0.14, animation="rise_in", text_style="bold_block", max_clips=1),
            _b("one", 0.24, animation="slide_in_left", text_style="caption", max_clips=2),
            _b("two", 0.24, animation="slide_in_left", text_style="caption", max_clips=2),
            _b("three", 0.24, animation="slide_in_left", text_style="caption", max_clips=2),
            _b("close", 0.14, animation="fade_in", text_style="highlight", max_clips=1),
            transition="dissolve",
            transition_ticks=18_000,
        ),
        _r(
            "quick_list",
            "Quick list",
            "list",
            "No title, straight into it, hard cuts throughout.",
            _b("one", 0.3, animation="pop_in", text_style="bold_block", max_clips=2),
            _b("two", 0.3, animation="pop_in", text_style="bold_block", max_clips=2),
            _b("three", 0.4, animation="pop_in", speed="ramp_down", text_style="highlight", max_clips=3),
        ),
        # ── story: setup, turn, resolution ──────────────────────────────────
        _r(
            "setup_turn_resolve",
            "Setup, turn, resolve",
            "story",
            "The oldest shape there is.",
            _b("setup", 0.32, animation="fade_in", speed="breathe", text_style="serif_quiet", min_clips=2),
            _b("turn", 0.28, animation="zoom_in", speed="punch", text_style="bold_block", max_clips=2),
            _b("resolve", 0.40, animation="drift_in", speed="ease_out_slow", text_style="clean", min_clips=2),
            transition="dissolve",
            transition_ticks=45_000,
        ),
        _r(
            "before_after",
            "Before and after",
            "story",
            "Two halves and one cut between them, which is the whole point.",
            _b("before", 0.45, animation="fade_in", text_style="mono_tag", min_clips=1, max_clips=3),
            _b("after", 0.55, animation="zoom_in", speed="hero", text_style="highlight", min_clips=1, max_clips=3),
            transition="wipe_left",
            transition_ticks=27_000,
        ),
        # ── montage: cuts carry it, words are sparse ────────────────────────
        _r(
            "fast_montage",
            "Fast montage",
            "montage",
            "Short cuts throughout. Needs material more than it needs words.",
            _b("open", 0.15, animation="pop_in", speed="ramp_up", text_style="bold_block", max_clips=2),
            _b("run", 0.70, animation="drift_in", speed="pulse", text_style="mono_tag", min_clips=4, max_clips=10),
            _b("stop", 0.15, animation="rise_in", speed="ease_out_slow", text_style="highlight", max_clips=1),
            transition="dissolve",
            transition_ticks=13_500,
            music_gain_alone=0.95,
        ),
        # ── demo: show the thing, then the detail ───────────────────────────
        _r(
            "show_then_detail",
            "Show, then detail",
            "demo",
            "The whole thing first, then the parts worth a second look.",
            _b("whole", 0.30, animation="zoom_out_in", text_style="bold_block", min_clips=1, max_clips=2),
            _b("detail", 0.50, animation="fade_in", speed="reveal", text_style="clean", min_clips=2, max_clips=5),
            _b("recap", 0.20, animation="pop_in", text_style="highlight", max_clips=2),
            transition="dissolve",
            transition_ticks=22_500,
        ),
    )
}

#: Nothing shorter than this is a video. Below it the beats round to nothing and
#: the shape stops being a shape.
MIN_TARGET_TICKS = 3 * TICKS_PER_SECOND
#: A ceiling, so a typo cannot ask for a four-hour render.
MAX_TARGET_TICKS = 600 * TICKS_PER_SECOND


class UnknownRecipe(ValueError):
    """A recipe nobody declared. Never assembled as something arbitrary."""


def recipe(recipe_id: str) -> Recipe:
    key = str(recipe_id or "").strip()
    if key not in RECIPES:
        raise UnknownRecipe(
            f"Unknown recipe {recipe_id!r}. Falling back to some default would "
            "produce a video nobody chose the shape of. Known: "
            f"{', '.join(sorted(RECIPES))}."
        )
    return RECIPES[key]


def catalogue() -> dict[str, Any]:
    """Every recipe, for the UI and for anything that searches the space."""
    return {
        "recipes": [item.to_dict() for item in RECIPES.values()],
        "recipe_families": list(RECIPE_FAMILIES),
        "limits": {
            "min_target_ticks": MIN_TARGET_TICKS,
            "max_target_ticks": MAX_TARGET_TICKS,
        },
    }
