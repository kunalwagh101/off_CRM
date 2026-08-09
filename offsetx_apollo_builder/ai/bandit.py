"""Traffic shifting between template variants (§4H).

``ai/context.py`` counts sends and replies. This decides what to do with those
numbers: which share of the next batch each variant should get.

**The problem with the obvious approach.** "Run both to 20 sends, then pick the
winner" is how most A/B splits are described, and on cold outreach it is close to
useless. Reply rates are low, so the numbers are brutal::

    telling  2% from  4% apart needs ~1,140 sends per variant
    telling  2% from  3% apart needs ~3,800 sends per variant
    telling  5% from 10% apart needs   ~434 sends per variant

Twenty sends with no replies has a 54% chance of happening even when the true
rate is a perfectly healthy 3%. A threshold rule fed that data does not make a
cautious decision — it makes a confident wrong one.

**Why Thompson sampling instead.** Each variant gets a Beta posterior over its
reply rate. To allocate, draw one sample from each and give the batch to whoever
drew highest; repeat, and the share each variant wins *is* its probability of
being best.

That behaves correctly at both ends without anyone choosing a cut-off:

* with little data the posteriors overlap almost completely, the draws come out
  near even, and traffic stays near even — the system says "I don't know" by
  *acting* like it doesn't know;
* as evidence accumulates the posteriors separate and traffic shifts on its own.

The graceful degradation is the whole reason for the choice. A threshold has to
be right; this does not.

**What it will not do.** It allocates only between variants the owner has
already approved. §3 of the build brief is explicit that nothing goes live
automatically — a rewrite is offered and saved as a variant, and a human decides
whether it runs at all. This module decides *how much*, never *whether*.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Draws used to estimate the allocation. 4,000 puts the Monte-Carlo error on a
#: share at well under a percentage point, which is far finer than the decision
#: needs, and costs about a millisecond.
DEFAULT_DRAWS = 4000

#: Smallest share an active variant keeps. Without a floor a bad early run can
#: starve a variant to zero and it never gets the chance to recover — and you
#: would stop noticing if the winner degraded.
DEFAULT_FLOOR = 0.05

#: Beta(1, 1) is uniform: before any data, every rate from 0 to 1 is equally
#: plausible. Deliberately not a "smart" prior — an informative one would be the
#: author's guess about reply rates leaking into the owner's results.
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


@dataclass(slots=True)
class Arm:
    """One variant, and what has been observed of it."""

    id: str
    label: str = ""
    sends: int = 0
    replies: int = 0
    retired: bool = False

    def __post_init__(self) -> None:
        if self.replies > self.sends:
            raise ValueError(
                f"Variant {self.id!r} has {self.replies} replies from "
                f"{self.sends} sends, which is impossible."
            )

    @property
    def alpha(self) -> float:
        return PRIOR_ALPHA + self.replies

    @property
    def beta(self) -> float:
        return PRIOR_BETA + (self.sends - self.replies)

    @property
    def observed_rate(self) -> float:
        """The raw fraction.  Shown, but never used to allocate — see the module
        docstring for why a raw rate on small samples is a trap."""
        return self.replies / self.sends if self.sends else 0.0

    @property
    def posterior_mean(self) -> float:
        """The rate to quote. Pulled toward 50% when there is little data, which
        is the honest summary of "we hardly know"."""
        return self.alpha / (self.alpha + self.beta)


@dataclass(slots=True)
class ArmAllocation:
    arm_id: str
    label: str
    share: float
    probability_best: float
    posterior_mean: float
    observed_rate: float
    sends: int
    replies: int
    low: float = 0.0
    high: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "label": self.label,
            "share": round(self.share, 4),
            "probability_best": round(self.probability_best, 4),
            "posterior_mean": round(self.posterior_mean, 4),
            "observed_rate": round(self.observed_rate, 4),
            "sends": self.sends,
            "replies": self.replies,
            "credible_interval": [round(self.low, 4), round(self.high, 4)],
        }


@dataclass(slots=True)
class Allocation:
    """How the next batch should be split, and how confident that is."""

    arms: list[ArmAllocation] = field(default_factory=list)
    confident: bool = False
    verdict: str = ""

    @property
    def leader(self) -> ArmAllocation | None:
        return max(self.arms, key=lambda a: a.probability_best) if self.arms else None

    def share_for(self, arm_id: str) -> float:
        for arm in self.arms:
            if arm.arm_id == arm_id:
                return arm.share
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "arms": [arm.to_dict() for arm in self.arms],
            "confident": self.confident,
            "verdict": self.verdict,
            "leader": self.leader.arm_id if self.leader else "",
        }


def sends_needed(rate_a: float, rate_b: float, *, power: float = 0.8) -> int:
    """Sends **per variant** to detect a difference of this size.

    Standard two-proportion sample size at 95% confidence. Exposed because it is
    the number that makes the whole feature honest: an owner looking at 40 sends
    and two similar rates should be told how far off a real answer is, not shown
    a winner.
    """
    if rate_a <= 0 or rate_b <= 0 or rate_a >= 1 or rate_b >= 1:
        return 0
    if abs(rate_a - rate_b) < 1e-9:
        return 0
    z_alpha = 1.96
    z_beta = 0.84 if power >= 0.8 else 0.52
    pooled = (rate_a + rate_b) / 2
    numerator = (
        z_alpha * (2 * pooled * (1 - pooled)) ** 0.5
        + z_beta * (rate_a * (1 - rate_a) + rate_b * (1 - rate_b)) ** 0.5
    ) ** 2
    return int(numerator / (rate_a - rate_b) ** 2 + 0.999)


def allocate(
    arms: Sequence[Arm],
    *,
    draws: int = DEFAULT_DRAWS,
    floor: float = DEFAULT_FLOOR,
    confidence: float = 0.95,
    seed: int | None = None,
) -> Allocation:
    """Thompson allocation over the active variants.

    ``seed`` makes a run reproducible, which tests need and which also lets the
    owner re-derive an allocation they were shown last week.
    """
    active = [arm for arm in arms if not arm.retired]
    if not active:
        return Allocation(
            verdict="No active variants. Nothing to allocate between."
        )
    if len(active) == 1:
        only = active[0]
        return Allocation(
            arms=[
                ArmAllocation(
                    arm_id=only.id,
                    label=only.label,
                    share=1.0,
                    probability_best=1.0,
                    posterior_mean=only.posterior_mean,
                    observed_rate=only.observed_rate,
                    sends=only.sends,
                    replies=only.replies,
                )
            ],
            confident=False,
            verdict=(
                f"Only one active variant, so it takes the whole batch. Add a "
                f"rewrite as a second variant to start comparing."
            ),
        )

    rng = random.Random(seed)
    wins = {arm.id: 0 for arm in active}
    samples: dict[str, list[float]] = {arm.id: [] for arm in active}

    for _ in range(max(1, draws)):
        best_id, best_value = "", -1.0
        for arm in active:
            value = rng.betavariate(arm.alpha, arm.beta)
            samples[arm.id].append(value)
            if value > best_value:
                best_id, best_value = arm.id, value
        wins[best_id] += 1

    total = sum(wins.values()) or 1
    raw = {arm_id: count / total for arm_id, count in wins.items()}

    # Apply the floor, then renormalise what is left over the remainder. A floor
    # that pushed the total past 1.0 would silently inflate the leader's share.
    capped_floor = min(floor, 1.0 / len(active))
    remaining = 1.0 - capped_floor * len(active)
    raw_total = sum(raw.values()) or 1.0
    shares = {
        arm_id: capped_floor + remaining * (value / raw_total)
        for arm_id, value in raw.items()
    }

    tail = (1.0 - confidence) / 2
    allocations: list[ArmAllocation] = []
    for arm in active:
        ordered = sorted(samples[arm.id])
        low = ordered[int(tail * len(ordered))]
        high = ordered[min(len(ordered) - 1, int((1 - tail) * len(ordered)))]
        allocations.append(
            ArmAllocation(
                arm_id=arm.id,
                label=arm.label,
                share=shares[arm.id],
                probability_best=raw[arm.id],
                posterior_mean=arm.posterior_mean,
                observed_rate=arm.observed_rate,
                sends=arm.sends,
                replies=arm.replies,
                low=low,
                high=high,
            )
        )
    allocations.sort(key=lambda item: -item.probability_best)

    leader, runner_up = allocations[0], allocations[1]
    confident = leader.probability_best >= confidence
    verdict = _verdict(leader, runner_up, confident, confidence)
    return Allocation(arms=allocations, confident=confident, verdict=verdict)


def _verdict(
    leader: ArmAllocation,
    runner_up: ArmAllocation,
    confident: bool,
    confidence: float,
) -> str:
    """A sentence the owner can act on, including how far off an answer is."""
    if confident:
        return (
            f"{leader.label or leader.arm_id} is ahead with "
            f"{leader.probability_best:.0%} probability of being best "
            f"({leader.replies}/{leader.sends} vs {runner_up.replies}/"
            f"{runner_up.sends}). Taking {leader.share:.0%} of the next batch."
        )
    needed = sends_needed(leader.posterior_mean, runner_up.posterior_mean)
    shortfall = max(0, needed - min(leader.sends, runner_up.sends))
    name = leader.label or leader.arm_id

    # Describe the split that is actually happening. Thompson does shift traffic
    # below the confidence bar — that is the point of it — so a verdict claiming
    # "traffic stays near even" while allocating 80/20 would be plainly untrue.
    if leader.share >= 0.65:
        movement = (
            f"{name} already takes {leader.share:.0%} of the next batch, and the "
            f"remaining {1 - leader.share:.0%} keeps testing the alternative "
            "rather than abandoning it."
        )
    else:
        movement = (
            f"Traffic stays close to even ({leader.share:.0%} / "
            f"{runner_up.share:.0%}) while the evidence is this thin."
        )

    if not needed or shortfall <= 0:
        return (
            f"Leaning towards {name}: {leader.probability_best:.0%} against "
            f"{runner_up.probability_best:.0%}, but not past the "
            f"{confidence:.0%} bar. {movement}"
        )
    return (
        f"Leaning towards {name} — {leader.probability_best:.0%} against "
        f"{runner_up.probability_best:.0%} — but not conclusive. Separating "
        f"rates this similar takes roughly {needed:,} sends per variant, about "
        f"{shortfall:,} more each. {movement}"
    )


def arms_from_scores(scores: Iterable[Any]) -> list[Arm]:
    """Build arms from ``context.TemplateScore`` rows.

    Kept as a loose adapter so ``bandit.py`` does not import the context layer:
    the allocation maths has no business knowing about SQLite.
    """
    arms: list[Arm] = []
    for score in scores:
        arms.append(
            Arm(
                id=getattr(score, "variant_id", "") or getattr(score, "id", ""),
                label=getattr(score, "label", ""),
                sends=int(getattr(score, "sends", 0)),
                replies=int(getattr(score, "replies", 0)),
                retired=bool(getattr(score, "retired", False)),
            )
        )
    return arms
