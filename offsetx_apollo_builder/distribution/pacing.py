"""How much to publish, decided by the goal rather than by a fixed number.

A campaign is goal-shaped — *reach a million views* — and the number of posts a
week is the lever that moves it. Setting that number by hand once is guessing at
the start of the campaign and then never revisiting it. This module makes it a
measured decision: look at where the goal stands, look at how much a post is
actually worth, and say how many to make next.

---

**A controller with nothing to measure is a random number generator.**

That is the first rule here, and it is the one most likely to be broken by
someone trying to make this look clever. Before any post has been published
there is no views-per-post figure, so there is nothing to divide by, and any
number the controller produces would be invented. So it **holds the declared
baseline and says why**, in a sentence the owner can read. It starts steering
only once there is real data behind it.

---

**Increase slowly, decrease immediately.**

The two errors are not symmetrical:

- Publishing too little misses a goal. That is a business problem and it is
  recoverable next week.
- Publishing too much gets the account restricted or banned, and the audience —
  the actual asset — goes with it. That is not recoverable.

So a rise is rate-limited to a fraction per cycle and a fall is applied at once.
An engine that spots it is behind and immediately posts ten times more looks
exactly like a spam bot, because at that moment it is behaving like one.

---

**Platform caps are not suggestions.**

Instagram allows 25 API-published posts per account per day. That number is a
ceiling the controller may approach and never cross, whatever the arithmetic
says. The goal does not get a vote on the platform's terms.

---

**The owner's cap outranks all of it.**

The platform says what is *allowed*. The owner says what they are *willing to
do with their name on it*, and that is a smaller number for almost everybody —
Instagram permits 25 a day and nobody sane posts 25 a day. So an owner cap sits
under every other limit, and the controller treats it exactly as it treats the
platform's: a number to approach and never cross.

It is deliberately not a default. A cap this module invented would be a number
the owner never chose being enforced as though they had, and the honest state
before anyone sets one is *no cap*, with the platform's limit still binding.

---

**Recommending and doing are two different things.**

This module only ever *works out a number*. Whether that number is applied is a
decision made above it, and the owner picks between three modes: leave the rate
alone, be told what the ideal rate would be, or let it move on its own within
the cap. That split is the same one the review queue makes about video — the
machine proposes, the person decides — and it exists for the same reason. How
loudly you speak in public is not a setting to have changed for you.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

#: How far off pace the campaign has to be before anything changes. Without a
#: deadband the controller adjusts every cycle on noise, and a schedule that
#: changes hourly is one nobody can plan around.
DEADBAND = 0.10

#: The most the rate may rise in one adjustment, as a fraction. A campaign that
#: is behind gets a ramp, not a step. See the module docstring for why the two
#: directions are not treated the same.
MAX_RISE = 0.25

#: Below this many measured posts, a views-per-post average is arithmetic on
#: noise. Same reasoning as the generator bandit's floor before it steers, and
#: the trend watcher's five observations before it ranks a multiple.
MIN_POSTS_TO_STEER = 5

#: Absolute floor and ceiling on posts per day, whatever the goal says. The
#: floor keeps a campaign alive; the ceiling is a sanity bound below every
#: platform's own limit.
MIN_PER_DAY = 0.0
MAX_PER_DAY = 20.0


@dataclass
class PacingDecision:
    """What to do next, and the reasoning in a form that can be read back."""

    posts_per_day: float
    previous_per_day: float
    #: What the engine should ask for on the next cycle.
    max_topics: int
    candidates: int
    #: "hold" until there is data, then "raise", "lower" or "on_pace".
    action: str = "hold"
    reason: str = ""
    #: Everything the decision was made from, so it can be argued with.
    measured_views: int = 0
    measured_posts: int = 0
    views_per_post: float = 0.0
    required_per_day: float = 0.0
    days_left: float = 0.0
    shortfall: int = 0
    capped_by: str = ""
    steering: bool = False
    #: The owner's own limit, or 0 when they have not set one.
    owner_cap: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "posts_per_day": round(self.posts_per_day, 3),
            "previous_per_day": round(self.previous_per_day, 3),
            "max_topics": self.max_topics,
            "candidates": self.candidates,
            "action": self.action,
            "reason": self.reason,
            "measured_views": self.measured_views,
            "measured_posts": self.measured_posts,
            "views_per_post": round(self.views_per_post, 1),
            "required_per_day": round(self.required_per_day, 3),
            "days_left": round(self.days_left, 2),
            "shortfall": self.shortfall,
            "capped_by": self.capped_by,
            "steering": self.steering,
            "owner_cap": round(self.owner_cap, 3),
        }


def _parse(moment: str) -> datetime | None:
    text = str(moment or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def measure(metrics: Sequence[Mapping[str, Any]]) -> tuple[int, int, float]:
    """Total views, posts measured, and views per post.

    Takes the **latest snapshot per post**, which is what `latest_metrics`
    already returns. Summing every snapshot would count Tuesday's views again on
    Friday and report a goal met that is not — a bug this project has already
    had once, and the reason that store method exists.
    """
    posts = 0
    views = 0
    for row in metrics:
        posts += 1
        try:
            views += max(0, int(row.get("views") or 0))
        except (TypeError, ValueError):
            continue
    return views, posts, (views / posts if posts else 0.0)


def platform_ceiling(platforms: Iterable[Mapping[str, Any]], accounts: int = 1) -> tuple[float, str]:
    """The most this campaign may publish a day, and which platform said so.

    The **lowest** cap across the platforms in play, because a schedule is one
    number and the tightest limit is the one that binds. Named, so a throttled
    campaign says which platform throttled it rather than appearing to
    under-perform for no reason.
    """
    ceiling = MAX_PER_DAY
    source = ""
    for platform in platforms:
        try:
            per_account = int(platform.get("daily_posts_per_account") or 0)
        except (TypeError, ValueError):
            continue
        if per_account <= 0:
            continue
        allowed = float(per_account) * max(1, int(accounts))
        if allowed < ceiling:
            ceiling = allowed
            source = str(platform.get("id") or platform.get("name") or "")
    return ceiling, source


def decide(
    *,
    goal_target: int,
    goal_deadline: str,
    metrics: Sequence[Mapping[str, Any]],
    current_per_day: float,
    now: datetime | None = None,
    ceiling: float = MAX_PER_DAY,
    ceiling_source: str = "",
    owner_cap: float = 0.0,
    floor: float = MIN_PER_DAY,
    candidates_per_topic: int = 3,
) -> PacingDecision:
    """How many posts a day this campaign should be making.

    The arithmetic is deliberately plain — shortfall ÷ views per post ÷ days
    left — because every term in it is something the owner can check. A model
    could produce a number here and nobody could argue with it, which is exactly
    the wrong property for a control that decides how loudly you speak in
    public.
    """
    moment = now or datetime.now(timezone.utc)
    # The owner's number outranks the platform's, because it is the smaller one
    # for almost everybody and it is the one with their name on it. Zero means
    # they have not set one, which is not the same as zero posts a day.
    cap = float(owner_cap or 0.0)
    if cap > 0 and cap < ceiling:
        ceiling, ceiling_source = cap, "your own cap"
    views, posts, per_post = measure(metrics)
    decision = PacingDecision(
        posts_per_day=current_per_day,
        previous_per_day=current_per_day,
        max_topics=max(1, round(current_per_day)) if current_per_day else 1,
        candidates=max(1, int(candidates_per_topic)),
        measured_views=views,
        measured_posts=posts,
        views_per_post=per_post,
        owner_cap=cap,
    )

    if cap > 0 and current_per_day > cap:
        # Before any goal arithmetic. A rate already above the cap is not a
        # pacing question, it is a limit being exceeded right now.
        decision.posts_per_day = cap
        decision.action = "lower"
        decision.capped_by = "your own cap"
        decision.reason = (
            f"The rate is set to {current_per_day:.2f} a day and your cap is "
            f"{cap:.2f}. Lowering to the cap — a limit you set is not something "
            "the goal gets to argue with."
        )
        return decision

    if goal_target <= 0:
        decision.action = "hold"
        decision.reason = (
            "No views goal is set for this campaign, so there is nothing to pace "
            "against. Set one and the rate becomes a measured decision instead of "
            "a fixed number."
        )
        return decision

    deadline = _parse(goal_deadline)
    if deadline is None:
        decision.action = "hold"
        decision.reason = (
            "The goal has no deadline. A rate is views per *day*, so without a "
            "date there is no arithmetic to do — a million views eventually is "
            "met by posting once a year."
        )
        return decision

    days_left = (deadline - moment).total_seconds() / 86400
    decision.days_left = days_left
    decision.shortfall = max(0, int(goal_target) - views)

    if days_left <= 0:
        decision.action = "hold"
        decision.reason = (
            f"The deadline has passed with {views:,} of {int(goal_target):,} views. "
            "Set a new goal rather than letting the engine keep pacing against a "
            "date that is gone."
        )
        return decision

    if decision.shortfall == 0:
        decision.action = "on_pace"
        decision.reason = f"Goal met: {views:,} views against a target of {int(goal_target):,}."
        return decision

    if posts < MIN_POSTS_TO_STEER or per_post <= 0:
        decision.action = "hold"
        decision.reason = (
            f"Only {posts} post(s) have measured views, and a views-per-post "
            f"figure needs at least {MIN_POSTS_TO_STEER} to be worth dividing by. "
            "Holding the declared rate until there is something real to steer on."
        )
        return decision

    # From here there is genuine data behind every term.
    decision.steering = True
    posts_needed = decision.shortfall / per_post
    required = posts_needed / days_left
    decision.required_per_day = required

    if current_per_day > 0:
        drift = (required - current_per_day) / current_per_day
    else:
        drift = 1.0 if required > 0 else 0.0

    if abs(drift) <= DEADBAND:
        decision.action = "on_pace"
        decision.reason = (
            f"On pace: {required:.2f} posts a day needed, {current_per_day:.2f} "
            f"scheduled, inside the {int(DEADBAND * 100)}% deadband."
        )
        target = current_per_day
    elif required > current_per_day:
        # Ramped. An engine that suddenly posts ten times more looks like a spam
        # bot because at that moment it is behaving like one.
        target = min(required, current_per_day * (1 + MAX_RISE) if current_per_day else required)
        decision.action = "raise"
        decision.reason = (
            f"Behind: {decision.shortfall:,} views short with {days_left:.1f} days "
            f"left needs {required:.2f} posts a day at {per_post:,.0f} views each. "
            f"Raising {current_per_day:.2f} → {target:.2f}, ramped so the account "
            "does not look like a spam bot overnight."
        )
    else:
        # Down at once: over-posting risks the account, and that is the one
        # error that is not recoverable next week.
        target = required
        decision.action = "lower"
        decision.reason = (
            f"Ahead: {required:.2f} posts a day is enough to reach "
            f"{int(goal_target):,} views by the deadline. Lowering "
            f"{current_per_day:.2f} → {target:.2f} immediately — publishing more "
            "than a goal needs spends the audience's patience for nothing."
        )

    bounded = max(float(floor), min(float(target), float(ceiling), MAX_PER_DAY))
    if ceiling < target and ceiling_source:
        decision.capped_by = ceiling_source
        # Two different sentences, because they are two different facts: a
        # platform limit is something neither of you chose, and an owner cap is
        # something one of you did.
        decision.reason += (
            f" Capped at {ceiling:.2f} a day by your own cap. Raise it if you "
            "want the goal met sooner."
            if ceiling_source == "your own cap"
            else f" Capped at {ceiling:.2f} a day by {ceiling_source}'s published "
                 "limit, which the goal does not get a vote on."
        )
    elif bounded != target and cap > 0 and bounded == cap:
        decision.capped_by = "your own cap"
        decision.reason += f" Held at your cap of {cap:.2f} a day."
    elif bounded != target and bounded == MAX_PER_DAY:
        decision.capped_by = "safety_ceiling"
        decision.reason += f" Capped at the {MAX_PER_DAY:.0f}/day safety ceiling."

    decision.posts_per_day = bounded
    # One topic produces one brief and `candidates` pictures, and roughly one
    # post survives the swipe. Topics per cycle is therefore the daily rate
    # scaled to the cycle, and never zero — a cycle that plans nothing is a
    # cycle that may as well not have run.
    decision.max_topics = max(1, round(bounded))
    decision.candidates = max(1, int(candidates_per_topic))
    return decision
