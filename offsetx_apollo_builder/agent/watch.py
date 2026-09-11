"""Watching a run while it happens.  `S-11.04.02`

`S-11.04.01` tells you what a run did, after it did it. This is so a run going
wrong at step 4 can be seen at step 4 rather than read about at step 40.

**It shows; it does not stop.** Interrupting a run is `S-02.02.03` and is not
smuggled in here — but a person who can see a run heading for the wrong page can
kill the process, and `S-11.01.03` means resuming costs nothing. Visibility is
the half that makes the other half worth having.

The hook lives on `Trace`, not here, because the trace is already the single
funnel every recorded event passes through: a watcher hung there cannot be
forgotten at a new call site, and there are forty of them.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, TextIO

from ..browser.trace import Step, Trace, signature_in

#: How much of a step's detail one line carries. A terminal is 80 columns and a
#: detail can be two thousand characters.
MAX_LINE_DETAIL = 90


@dataclass(frozen=True, slots=True)
class Progress:
    """One step, as it happens, with the run's totals so far."""

    index: int
    kind: str
    detail: str
    url: str
    ok: bool
    took_ms: int
    #: Running, not per step — "what has this cost me so far" is the question
    #: somebody watching is actually asking.
    cost_usd: float
    tokens_in: int
    tokens_out: int

    @property
    def action(self) -> str:
        """The verb, when this step was one. Empty for decisions and endings.

        Read from the signature the step recorded, not from the prose around
        it: a click reads "clicked More", and "clicked" is not one of the ten
        verbs. The signature is the record of what actually ran.
        """
        if self.kind != "action":
            return ""
        return signature_in(self.detail).split("(", 1)[0].strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "kind": self.kind, "detail": self.detail,
            "url": self.url, "ok": self.ok, "took_ms": self.took_ms,
            "action": self.action, "cost_usd": round(self.cost_usd, 8),
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
        }

    def line(self) -> str:
        """One readable line. What a person watching a terminal actually sees."""
        mark = " " if self.ok else "!"
        detail = self.detail.replace("\n", " ").strip()
        if len(detail) > MAX_LINE_DETAIL:
            detail = detail[: MAX_LINE_DETAIL - 1] + "…"
        # The verb gets its own column rather than being left inside the detail,
        # where a long one would truncate it away — and the action is half of
        # what somebody watching is here to see.
        label = f"{self.kind} {self.action}".strip()
        parts = [f"{mark}{self.index:>3} {label:<20} {detail}"]
        if self.url:
            parts.append(f"      {self.url}")
        parts.append(f"      ${self.cost_usd:.4f} · {self.tokens_in}+{self.tokens_out} tokens")
        return "\n".join(parts)


def observer(trace: Trace, report: Callable[[Progress], None]) -> Callable[[Step], None]:
    """Turn a step into a `Progress` carrying the run's running totals.

    The totals come from the trace rather than being accumulated here, so a
    watcher attached to a *resumed* run counts the whole run and not just the
    part it happened to be present for.
    """

    def listen(step: Step) -> None:
        report(
            Progress(
                index=len(trace.steps) - 1,
                kind=step.kind,
                detail=step.detail,
                url=step.url,
                ok=step.ok,
                took_ms=step.took_ms,
                cost_usd=sum(item.estimated_cost_usd for item in trace.steps),
                tokens_in=sum(item.tokens_in for item in trace.steps),
                tokens_out=sum(item.tokens_out for item in trace.steps),
            )
        )

    return listen


def console(stream: TextIO | None = None) -> Callable[[Progress], None]:
    """A ready-made watcher that prints one block per step.

    Flushed per step, because an unflushed watcher shows you the run after it
    has finished, which is the thing this story exists to stop.
    """
    out = stream if stream is not None else sys.stdout

    def show(progress: Progress) -> None:
        out.write(progress.line() + "\n")
        out.flush()

    return show
