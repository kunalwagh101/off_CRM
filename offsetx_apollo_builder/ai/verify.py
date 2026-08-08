"""The verify loop: cheap generate, deterministic check, repair, strong review.

This is where the quality actually comes from, and it is not what people expect.
It is not several models voting — published work on Mixture-of-Agents found that
mixing a weak model into a blend often drags the result *below* what the best
single model would have produced alone.  The gain comes from somewhere else:

* **Checking is easier than producing.**  A model spots a problem in text more
  reliably than it avoids the problem while writing.
* **Checking is cheaper than producing.**  Providers charge roughly three to
  five times more for output tokens than input tokens, and reviewing is mostly
  reading.
* **The best checker is not a model at all.**  A rule that cannot be wrong costs
  nothing and never has an off day.

So the loop is: let a cheap model write, let *code* judge it, hand back the
specific failures, and let the cheap model fix them.  Spend a strong model only
on the part rules cannot judge, and only on reading.

**The checks are the same ones the eval harness scores with.**  That is
deliberate.  ``config/evals.yaml`` defines what "good" means once, and both the
offline measurement and the online enforcement read it.  Improving the suite
improves production quality in the same edit, and the two can never drift into
disagreeing about what a good draft looks like.

Two rules keep it honest:

* **Deterministic checks are the gate; a model review is only an advisor.**  A
  model may suggest a repair, never decide that output is acceptable.  The same
  reason policy is code: a grader that varies is not a gate.
* **The best attempt wins, not the last one.**  Repair can make things worse —
  a model told to fix a length problem will happily break something else.  The
  loop keeps every attempt and returns the highest scoring one.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from .broker import EgressBroker, WorkspaceEgressSettings
from .errors import EgressBlocked, NoPermittedProvider, PolicyViolation
from .evals import CheckResult, run_checks
from .payload import EgressRequest
from .tiers import TrustTier

#: Rounds 1-2 capture most of the available improvement in published work on
#: verification loops, so the default is deliberately low.  Each extra round is
#: another generation call for a shrinking return.
DEFAULT_MAX_ROUNDS = 3

#: A hard stop regardless of what a caller asks for.  A loop that can run twenty
#: times is a way to spend twenty times the money on a task that is not
#: converging; at that point the checks or the prompt are wrong, not the model.
HARD_ROUND_CAP = 5

REVIEW_SYSTEM_PROMPT = """You review a draft and reply with specific, actionable
problems. You do not rewrite it and you do not praise it.

Reply with at most three short bullet points, each naming one concrete problem
and what to do about it. If the draft is genuinely fine, reply with exactly:
NO NOTES

Judge only what rules cannot: whether the opening follows from the stated hook,
whether the ask is clear, whether it reads as written for this specific reader
rather than assembled from a template."""


@dataclass(slots=True)
class Attempt:
    """One generation, with the verdict code passed on it."""

    round: int
    text: str
    checks: list[CheckResult] = field(default_factory=list)
    provider_id: str = ""
    model_id: str = ""
    tier: str = ""
    duration_ms: int = 0
    error: str = ""

    @property
    def score(self) -> float:
        if not self.checks:
            return 0.0
        return sum(1 for item in self.checks if item.passed) / len(self.checks)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [item for item in self.checks if not item.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "text": self.text,
            "score": round(self.score, 4),
            "passed": self.passed,
            "checks": [item.to_dict() for item in self.checks],
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "tier": self.tier,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass(slots=True)
class VerifiedResult:
    """The outcome of a verify loop."""

    text: str
    passed: bool
    rounds: int
    calls: int
    attempts: list[Attempt] = field(default_factory=list)
    review_notes: str = ""
    reviewer: str = ""
    duration_ms: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def best(self) -> Attempt | None:
        if not self.attempts:
            return None
        scored = [item for item in self.attempts if not item.error]
        if not scored:
            return self.attempts[0]
        # Highest score; earliest round breaks ties, because a later round that
        # only matched an earlier one cost money for nothing.
        return sorted(scored, key=lambda item: (-item.score, item.round))[0]

    @property
    def score(self) -> float:
        best = self.best
        return best.score if best else 0.0

    @property
    def remaining_failures(self) -> list[CheckResult]:
        best = self.best
        return best.failures if best else []

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "passed": self.passed,
            "score": round(self.score, 4),
            "rounds": self.rounds,
            "calls": self.calls,
            "attempts": [item.to_dict() for item in self.attempts],
            "review_notes": self.review_notes,
            "reviewer": self.reviewer,
            "duration_ms": self.duration_ms,
            "notes": self.notes,
            "remaining_failures": [item.to_dict() for item in self.remaining_failures],
        }


def build_repair_instructions(
    original: str, attempt: Attempt, review_notes: str = ""
) -> str:
    """The instruction for a repair round.

    The previous draft goes back in the *instructions* field rather than
    ``prior_drafts``, which only travels at ``standard`` and above.  That matters
    for restricted providers: a tier C model must be able to fix its own work
    without the payload widening to carry campaign material.  The text is the
    model's own output, so at ``pseudonymous`` it already contains tokens rather
    than names — and ``build_payload`` scrubs the field again on the way out
    regardless, so a regression cannot leak through this path.
    """
    problems = "\n".join(
        f"- {item.name}: {item.detail}" if item.detail else f"- {item.name}"
        for item in attempt.failures
    )
    parts = [
        original.strip(),
        "",
        "Your previous attempt was rejected. Here it is:",
        "---",
        attempt.text.strip(),
        "---",
        "",
        "Problems found:",
        problems or "- did not meet the required shape",
    ]
    if review_notes and review_notes.strip().upper() != "NO NOTES":
        parts += ["", "Reviewer notes:", review_notes.strip()]
    parts += [
        "",
        "Rewrite it so every problem above is fixed. Keep what already worked. "
        "Return only the corrected version, with no commentary.",
    ]
    return "\n".join(parts)


class VerifyLoop:
    """Generate, check, repair — with a strong model reading at the end.

    Holds no transport of its own: every call goes through the broker with the
    ordinary tier rules, so a verified run cannot see more than a plain one.
    """

    def __init__(self, broker: EgressBroker) -> None:
        self.broker = broker

    def run(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        system_prompt: str,
        checks: Sequence[dict[str, Any]],
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        provider_id: str = "",
        review: bool = True,
    ) -> VerifiedResult:
        started = time.monotonic()
        rounds = max(1, min(int(max_rounds), HARD_ROUND_CAP))
        attempts: list[Attempt] = []
        notes: list[str] = []
        calls = 0

        if not checks:
            notes.append(
                "No checks were supplied, so nothing was verified. This ran as a "
                "plain single call."
            )

        original_instructions = request.instructions
        current = request

        for index in range(rounds):
            attempt, ok = self._generate(
                current, settings, system_prompt, provider_id, index + 1, checks
            )
            calls += 1
            attempts.append(attempt)
            if not ok:
                # A refusal or a blocked payload is not something another round
                # will fix — the answer would be identical. Stop and report.
                notes.append(
                    "Stopped early: the call could not be made, so retrying would "
                    "produce the same refusal."
                )
                break
            if attempt.passed or index == rounds - 1 or not checks:
                # No checks means nothing to repair toward: another round would
                # just buy a different sample of the same thing.
                break
            current = _with_instructions(
                request, build_repair_instructions(original_instructions, attempt)
            )

        best = _best_of(attempts)
        review_notes = ""
        reviewer = ""
        if review and best is not None and not best.error:
            review_notes, reviewer, review_calls = self._review(
                best, request, settings, provider_id
            )
            calls += review_calls
            # One extra repair round if the reviewer found something real and we
            # have not already spent the budget. The reviewer advises; the
            # deterministic checks still decide whether the result passed.
            if (
                review_notes
                and review_notes.strip().upper() != "NO NOTES"
                and len(attempts) < rounds
            ):
                repaired, ok = self._generate(
                    _with_instructions(
                        request,
                        build_repair_instructions(
                            original_instructions, best, review_notes
                        ),
                    ),
                    settings,
                    system_prompt,
                    provider_id,
                    len(attempts) + 1,
                    checks,
                )
                calls += 1
                attempts.append(repaired)
                if ok and repaired.score < best.score:
                    notes.append(
                        "The reviewer-driven rewrite scored lower than the draft "
                        "before it, so the earlier draft was kept."
                    )

        final = _best_of(attempts)
        if final is not None and final.round < len(attempts):
            notes.append(
                f"Round {final.round} was the best of {len(attempts)}; later rounds "
                "did not improve on it."
            )
        return VerifiedResult(
            text=final.text if final else "",
            passed=bool(final and final.passed),
            rounds=len(attempts),
            calls=calls,
            attempts=attempts,
            review_notes=review_notes,
            reviewer=reviewer,
            duration_ms=int((time.monotonic() - started) * 1000),
            notes=notes,
        )

    # ── internals ───────────────────────────────────────────────────────────

    def _generate(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        system_prompt: str,
        provider_id: str,
        round_number: int,
        checks: Sequence[dict[str, Any]],
    ) -> tuple[Attempt, bool]:
        try:
            result = self.broker.call(
                request, settings, system_prompt=system_prompt, provider_id=provider_id
            )
        except (NoPermittedProvider, PolicyViolation, EgressBlocked) as exc:
            return Attempt(round=round_number, text="", error=str(exc)[:400]), False
        except Exception as exc:  # noqa: BLE001 - recorded, loop stops
            return Attempt(round=round_number, text="", error=str(exc)[:400]), False
        return (
            Attempt(
                round=round_number,
                text=result.text,
                checks=run_checks(result.text, checks),
                provider_id=result.provider_id,
                model_id=result.model_id,
                tier=result.tier,
                duration_ms=result.duration_ms,
            ),
            True,
        )

    def _review(
        self,
        attempt: Attempt,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        provider_id: str,
    ) -> tuple[str, str, int]:
        """Ask the most trusted permitted model to read the draft.

        Reading is mostly input tokens, which cost a fraction of generation, so
        this is the cheap half of the loop even on an expensive model.

        The review keeps the **original request's data class**. Relabelling it
        as ``public`` on the grounds that "it is only the draft" would be a way
        to smuggle person material past the tier rules, since the draft is built
        from exactly that material.
        """
        review_request = EgressRequest(
            task_type=f"{request.task_type}_review",
            data_class=request.data_class,
            person=request.person,
            instructions=(
                "Review this draft and list what is wrong with it.\n---\n"
                f"{attempt.text.strip()}\n---"
            ),
            positioning_line=request.positioning_line,
        )
        try:
            candidates, _ = self.broker.plan(review_request, settings)
        except (NoPermittedProvider, PolicyViolation):
            return "", "", 0
        if not candidates:
            return "", "", 0
        # Most trusted first; a reviewer that sees less than the writer did is a
        # reviewer judging a draft it cannot fully understand.
        # Prefer a second opinion over the model marking its own homework — but
        # only within the tier the task already runs at. Dropping a tier to find
        # a different reviewer would hand the draft to a provider the task was
        # not cleared for, and a reviewer seeing less than the writer did judges
        # a draft it cannot fully understand.
        alternatives = [c for c in candidates if c.id != attempt.provider_id]
        pool = alternatives or candidates
        reviewer = sorted(pool, key=lambda item: -item.tier.rank)[0]
        self_review = reviewer.id == attempt.provider_id
        try:
            result = self.broker.call(
                review_request,
                settings,
                system_prompt=REVIEW_SYSTEM_PROMPT,
                provider_id=reviewer.id,
            )
        except Exception:  # noqa: BLE001 - a failed review is not a failed run
            return "", "", 1
        label = result.provider_id + (" (self-review)" if self_review else "")
        return result.text.strip()[:2000], label, 1


def _with_instructions(request: EgressRequest, instructions: str) -> EgressRequest:
    from dataclasses import replace

    return replace(request, instructions=instructions)


def _best_of(attempts: Sequence[Attempt]) -> Attempt | None:
    if not attempts:
        return None
    scored = [item for item in attempts if not item.error]
    if not scored:
        return attempts[0]
    return sorted(scored, key=lambda item: (-item.score, item.round))[0]
