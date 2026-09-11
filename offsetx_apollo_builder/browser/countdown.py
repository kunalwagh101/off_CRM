"""A visible, cancellable delay before something irreversible.  `S-02.02.04`

`policy.py` states the rule this implements, and states it better than a
restatement would:

    Sensitive actions get a countdown, not a dialog. A confirm box trains
    people to click through it; that is what confirm boxes are for. A visible
    five-second delay with a cancel button does not, because there is nothing
    to click.

That is the whole idea. A dialog asks for an action and gets a reflex. A
countdown asks for *nothing* — the person only has to act if they want to stop
it — so the reflex has nowhere to land.

---

**What this is not.** It is not a way for an unattended run to approve itself
after five seconds. `docs/architecture/AUTONOMOUS_BROWSING.md` is explicit:
*E-11 does not auto-confirm anything. Autonomy is about the path, not about the
permission.* A countdown with nobody watching is a sleep with extra steps, and
worse than that, it is the human gate deleted while looking like it is still
there. `Page.click` refuses one in unattended mode for exactly that reason —
the rule is in the code and not only in the document.

**One countdown, one action.** A finished countdown cannot be handed to a
second action. Otherwise "the owner watched this one elapse" becomes a token
that waves through something they never saw.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

#: What `policy.py` says: five seconds. Long enough to read what is about to
#: happen and reach for the cancel; short enough that a person who meant it is
#: not being punished.
DEFAULT_SECONDS = 5.0

#: How often the clock is checked. Fine enough that cancelling feels immediate
#: rather than "some time in the next second", which is the difference between
#: a control and a decoration.
TICK_SECONDS = 0.05


class CountdownSpent(RuntimeError):
    """A countdown was reused. One countdown covers one action, and no more."""


@dataclass
class Countdown:
    """A delay somebody can watch and stop.

    `on_tick` is called with the whole seconds remaining, once per second and
    once at zero — not once per poll, because a watcher wants `5, 4, 3, 2, 1`
    and not two hundred callbacks.
    """

    seconds: float = DEFAULT_SECONDS
    #: What is about to happen, in the owner's words. Shown by whatever is
    #: watching; carried here so the thing being delayed and the thing being
    #: described cannot drift apart.
    label: str = ""
    on_tick: "Callable[[int], None] | None" = None

    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _reason: str = field(default="", repr=False)
    _spent: bool = field(default=False, repr=False)

    #: Safe to call from any thread, which is the point — the cancel arrives
    #: from a person, and a person is never on the event loop.
    def cancel(self, reason: str = "") -> None:
        if not self._stop.is_set():
            self._reason = str(reason or "cancelled by the owner")
        self._stop.set()

    @property
    def cancelled(self) -> bool:
        return self._stop.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    async def run(self) -> bool:
        """Wait it out. `True` if it elapsed, `False` if it was cancelled.

        Raises `CountdownSpent` if this one has already been used.
        """
        if self._spent:
            raise CountdownSpent(
                "This countdown has already been used. A countdown covers one "
                "action; a second action needs its own, or the owner is "
                "approving something they never saw."
            )
        self._spent = True

        # Cancelled before it even started is still cancelled. Checked here so
        # a caller that cancels between construction and `run` is not ignored.
        if self._stop.is_set():
            return False

        deadline = time.monotonic() + max(0.0, float(self.seconds))
        announced: int | None = None
        while True:
            remaining = deadline - time.monotonic()
            whole = max(0, int(remaining + 0.999))  # 4.2s left reads as "5"
            if whole != announced:
                announced = whole
                self._announce(whole)
            if remaining <= 0:
                return True
            if self._stop.is_set():
                return False
            await asyncio.sleep(min(TICK_SECONDS, remaining))

    def _announce(self, remaining: int) -> None:
        if self.on_tick is None:
            return
        try:
            self.on_tick(remaining)
        except Exception:  # noqa: BLE001 - a watcher is not load-bearing
            # The same rule the trace listener follows: somebody's terminal
            # going away must not be able to fire or cancel an action.
            pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "seconds": float(self.seconds),
            "label": self.label,
            "cancelled": self.cancelled,
            "reason": self.reason,
        }
