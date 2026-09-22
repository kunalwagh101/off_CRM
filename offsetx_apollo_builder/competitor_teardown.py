"""Structure-only competitor post analysis.

This module turns normalized public structural/performance facts into one of the
video recipe shapes the product already knows. It never downloads, stores, or
accepts competitor media/captions/transcripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Mapping

from .discovery import validate_public_url
from .video import recipes
from .video.timeline import TICKS_PER_SECOND

ANALYSER_VERSION = "rules-v1"
_ALLOWED_KEYS = frozenset({
    "source_url",
    "source_id",
    "platform",
    "observed_at",
    "duration_seconds",
    "views",
    "likes",
    "comments",
    "channel_median_views",
    "cuts_per_minute",
    "list_items",
    "before_after",
    "demo",
    "opening_seconds",
    "visual_motion",
})
_VISUAL_MOTION = frozenset({"low", "medium", "high"})


class CompetitorTeardownError(ValueError):
    """Public post facts are unsafe, unsupported or insufficient."""


def _non_negative_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool):
        raise CompetitorTeardownError(f"{name} must be a number")
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise CompetitorTeardownError(f"{name} must be a number") from exc
    if not math.isfinite(number):
        raise CompetitorTeardownError(f"{name} must be a finite number")
    if number < 0:
        raise CompetitorTeardownError(f"{name} cannot be negative")
    return number


def _non_negative_integer(value: Any, *, name: str) -> int:
    number = _non_negative_number(value, name=name)
    if not float(number).is_integer():
        raise CompetitorTeardownError(f"{name} must be a whole number")
    return int(number)


def _boolean(value: Any, *, name: str) -> bool:
    if value in (None, ""):
        return False
    if not isinstance(value, bool):
        raise CompetitorTeardownError(f"{name} must be true or false")
    return value


@dataclass(frozen=True, slots=True)
class CompetitorTeardown:
    source_url: str
    source_id: str
    platform: str
    observed_at: str
    recipe_id: str
    target_ticks: int
    hook_class: str
    pacing_band: str
    visual_treatment: str
    parameters: dict[str, Any]
    performance: dict[str, float]
    analyser_version: str = ANALYSER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": {
                "url": self.source_url,
                "id": self.source_id,
                "platform": self.platform,
                "observed_at": self.observed_at,
            },
            "recipe_id": self.recipe_id,
            "target_ticks": self.target_ticks,
            "hook_class": self.hook_class,
            "pacing_band": self.pacing_band,
            "visual_treatment": self.visual_treatment,
            "parameters": dict(self.parameters),
            "performance": dict(self.performance),
            "analyser_version": self.analyser_version,
        }


def analyse_public_post(facts: Mapping[str, Any]) -> CompetitorTeardown:
    """Map bounded public facts to a known recipe, deterministically."""
    unknown = set(facts) - _ALLOWED_KEYS
    if unknown:
        raise CompetitorTeardownError(
            "Competitor teardown accepts structural/performance facts only; "
            f"unsupported fields: {', '.join(sorted(unknown))}"
        )

    source_url = str(facts.get("source_url") or "").strip()
    if not source_url:
        raise CompetitorTeardownError("source_url is required")
    try:
        source_url = validate_public_url(source_url)
    except ValueError as exc:
        raise CompetitorTeardownError(str(exc)) from exc

    observed_at = str(facts.get("observed_at") or "").strip()
    if not observed_at:
        raise CompetitorTeardownError("observed_at is required for provenance")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CompetitorTeardownError("observed_at must be an ISO-8601 timestamp") from exc

    duration = _non_negative_number(facts.get("duration_seconds"), name="duration_seconds")
    if duration < 3 or duration > 600:
        raise CompetitorTeardownError("duration_seconds must be between 3 and 600")

    cuts = _non_negative_number(facts.get("cuts_per_minute"), name="cuts_per_minute")
    list_items = _non_negative_integer(facts.get("list_items"), name="list_items")
    opening = _non_negative_number(facts.get("opening_seconds"), name="opening_seconds")
    before_after = _boolean(facts.get("before_after", False), name="before_after")
    demo = _boolean(facts.get("demo", False), name="demo")
    motion = str(facts.get("visual_motion") or "").strip().lower()
    if motion and motion not in _VISUAL_MOTION:
        raise CompetitorTeardownError("visual_motion must be low, medium or high")

    if not any((cuts, list_items, before_after, demo, opening, motion)):
        raise CompetitorTeardownError(
            "insufficient structural evidence: provide at least one pacing/shape signal"
        )

    if before_after:
        recipe_id = "before_after"
        hook_class = "contrast"
    elif demo:
        recipe_id = "show_then_detail"
        hook_class = "show_first"
    elif list_items >= 3:
        recipe_id = "quick_list" if cuts >= 30 or duration <= 20 else "three_points"
        hook_class = "list"
    elif cuts >= 35:
        recipe_id = "fast_montage"
        hook_class = "visual_interrupt"
    elif opening and opening <= 1.5 and motion == "high":
        recipe_id = "pattern_interrupt"
        hook_class = "pattern_interrupt"
    else:
        recipe_id = "hook_hold_payoff"
        hook_class = "direct_hook"

    try:
        recipes.recipe(recipe_id)
    except recipes.UnknownRecipe as exc:
        raise CompetitorTeardownError(str(exc)) from exc
    pacing = "fast" if cuts >= 30 else "steady" if cuts and cuts <= 12 else "medium"
    if not cuts:
        pacing = "medium"
    visual_treatment = {
        "high": "high_motion",
        "medium": "balanced_motion",
        "low": "restrained_motion",
        "": "unspecified",
    }[motion]

    views = _non_negative_number(facts.get("views"), name="views")
    likes = _non_negative_number(facts.get("likes"), name="likes")
    comments = _non_negative_number(facts.get("comments"), name="comments")
    median = _non_negative_number(
        facts.get("channel_median_views"), name="channel_median_views"
    )
    engagement = (likes + comments) / views if views else 0.0
    outlier = views / median if views and median else 0.0

    return CompetitorTeardown(
        source_url=source_url,
        source_id=str(facts.get("source_id") or "").strip(),
        platform=str(facts.get("platform") or "").strip().lower(),
        observed_at=observed_at,
        recipe_id=recipe_id,
        target_ticks=int(round(duration * TICKS_PER_SECOND)),
        hook_class=hook_class,
        pacing_band=pacing,
        visual_treatment=visual_treatment,
        parameters={
            "duration_seconds": round(duration, 3),
            "cuts_per_minute": round(cuts, 3),
            "list_items": list_items,
            "before_after": before_after,
            "demo": demo,
            "opening_seconds": round(opening, 3),
            "visual_motion": motion,
        },
        performance={
            "views": views,
            "likes": likes,
            "comments": comments,
            "channel_median_views": median,
            "engagement_rate": round(engagement, 8),
            "outlier_multiple": round(outlier, 4),
        },
    )
