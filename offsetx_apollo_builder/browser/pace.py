"""The rhythm of one host, shared by everything acting on it.  `S-11.05.01`

`policy.py` sets a floor between actions per host, and says why it is the single
most important number there: on a site being driven through your own session,
the thing that gets an account restricted is rhythm. Thirty actions a minute is
not something a person does.

A floor is only a floor if it is counted **across** whatever is acting. Before
this, each tab kept its own clock, so two runs on one host halved the interval
and N runs divided it by N — measured at 2.00s where 5.00s was honest. The
agent was not going faster because anybody asked it to; it was going faster
because nobody was counting the two of them together.

---

**Keyed by host, shared by object.** A `Pace` is handed to every tab that should
share a rhythm, the same way a `BudgetLedger` is handed to every tab that should
share an account. Two browsers driving two different accounts are two paces; two
runs in one browser are one.

**It waits; it does not refuse.** A run that arrives early is slowed, not
stopped. Refusing would push the decision back to the caller, and the caller is
a model that cannot be trusted to wait.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class Pace:
    """How recently each host was acted on, and who is waiting.

    One of these is shared by every tab that should keep one rhythm. It is safe
    for any number of concurrent callers: the wait is computed and the slot
    claimed under a single lock, so two runs arriving together are spaced rather
    than both being told the coast is clear.
    """

    #: When the next action on each host may happen. A *deadline*, not a last-
    #: seen time, because a caller has to claim its slot before sleeping —
    #: otherwise two runs both read "the last action was long ago", both decide
    #: they need not wait, and both act in the same millisecond.
    _next_allowed_at: dict[str, float] = field(default_factory=dict)
    _lock: asyncio.Lock | None = field(default=None, repr=False)

    def _guard(self) -> asyncio.Lock:
        # Built on first use rather than in the constructor: an `asyncio.Lock`
        # binds to the running loop, and this object is often made before there
        # is one.
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def wait_for(self, host: str, floor_seconds: float) -> float:
        """Wait until this host may be acted on again. Returns what it cost.

        The slot is claimed under the lock and the sleep happens outside it, so
        one run waiting does not stop another run reserving its own later slot.
        """
        key = str(host or "")
        floor = max(0.0, float(floor_seconds or 0.0))
        if floor <= 0.0:
            return 0.0

        async with self._guard():
            now = time.monotonic()
            starts_at = max(now, self._next_allowed_at.get(key, 0.0))
            self._next_allowed_at[key] = starts_at + floor

        waited = starts_at - time.monotonic()
        if waited > 0:
            await asyncio.sleep(waited)
        return max(0.0, waited)

    def next_free(self, host: str) -> float:
        """When this host is next actionable, as a monotonic time. For tests
        and for anything that wants to show the owner why it is waiting."""
        return self._next_allowed_at.get(str(host or ""), 0.0)
