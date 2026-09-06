"""What one account is allowed to do, and how much of it is left.  `S-03.02.04`

**The problem this exists for is not rate limiting. It is account termination.**

A platform that thinks you are a script does not answer with `429`. LinkedIn,
Instagram and the rest restrict or close the account, and the account is the
thing the owner spent months building. `policy.py` already slows the agent to
human *pace* — a floor between actions. Pace alone is not enough: a human at
reading pace for eleven hours is still not a human, and ten accounts each at
human pace is unmistakably a farm.

So this counts. Per account, per hour and per day, refused **before** the action
rather than noticed after it.

---

**Why this is not `ai/quota.py`.** That module is the same shape — file-backed,
locked, check-then-record — and it was read closely before this was written. It
is not reused because it answers a different question. Provider quota is about
*money and rate limits*: minute and day windows, a spend ceiling, and running
out means "use a different provider". Account budget is about *not being
banned*: hour and day windows, no spend, and running out means "stop, and come
back later, because there is no different account that is this account".

Generalising `QuotaTracker` over both would mean parameterising its windows and
loosening its vocabulary for the benefit of a caller it does not otherwise know
about — a shared abstraction over two things that are only superficially alike.
Two small concrete ledgers are the smaller change and the honest one.

What *is* reused is the write: `ai/workspace.atomic_json`, so a crash mid-write
cannot leave a half-written ledger that reads as an empty one — which would
silently hand every account a fresh budget.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ai.workspace import atomic_json

#: Actions that touch the platform and therefore cost budget. `read`,
#: `screenshot` and `wait_for` are absent on purpose: they observe what is
#: already on the screen and send nothing, and charging for looking would push
#: an agent towards acting blind to save budget.
COSTED_ACTIONS = ("goto", "click", "type", "select", "scroll", "press", "back")

#: Deliberately conservative, and deliberately not "what you can get away with".
#: These are set below the informal thresholds each platform is observed to act
#: on, because the cost of being wrong is asymmetric: too low wastes a run, too
#: high loses the account. The owner can raise them per account and owns that
#: decision; nothing here raises itself.
DEFAULT_BUDGETS: dict[str, tuple[int, int]] = {
    #  platform:      (per hour, per day)
    "linkedin": (30, 120),
    "instagram": (25, 100),
    "facebook": (25, 100),
    "tiktok": (25, 100),
    "x": (40, 200),
    "twitter": (40, 200),
    "youtube": (60, 400),
    "reddit": (40, 200),
}

#: Anything not named above. Not unlimited — an unknown platform is the one
#: whose enforcement we understand least.
DEFAULT_BUDGET = (60, 300)


class BudgetSpent(RuntimeError):
    """The account has no budget left, and the message says when it returns."""


@dataclass(frozen=True, slots=True)
class Budget:
    """The ceiling for one account. Zero on either field means unlimited."""

    actions_per_hour: int = 0
    actions_per_day: int = 0

    @classmethod
    def for_platform(cls, platform_id: str) -> "Budget":
        hour, day = DEFAULT_BUDGETS.get(str(platform_id).lower(), DEFAULT_BUDGET)
        return cls(actions_per_hour=hour, actions_per_day=day)

    @property
    def unlimited(self) -> bool:
        return self.actions_per_hour <= 0 and self.actions_per_day <= 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions_per_hour": self.actions_per_hour,
            "actions_per_day": self.actions_per_day,
        }


@dataclass(slots=True)
class Spend:
    """What one account has used, in the windows that are still open."""

    account: str
    hour_window: int = 0
    hour_count: int = 0
    day: str = ""
    day_count: int = 0
    last_action_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "account": self.account,
            "hour_window": self.hour_window,
            "hour_count": self.hour_count,
            "day": self.day,
            "day_count": self.day_count,
            "last_action_at": self.last_action_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Spend":
        return cls(
            account=str(payload.get("account", "")),
            hour_window=int(payload.get("hour_window", 0) or 0),
            hour_count=int(payload.get("hour_count", 0) or 0),
            day=str(payload.get("day", "")),
            day_count=int(payload.get("day_count", 0) or 0),
            last_action_at=float(payload.get("last_action_at", 0.0) or 0.0),
        )


def _today(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now if now is not None else time.time()))


def _hour_window(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // 3600)


def _until(seconds: float) -> str:
    """`4h 12m`, or `7m`. A refusal that does not say when is not actionable."""
    total = max(0, int(seconds))
    hours, minutes = divmod(total // 60, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


class BudgetLedger:
    """Per-account action accounting, persisted to one JSON file.

    A file rather than a table for the same reason `ConnectionStore` is a file:
    it is a small, readable record of what has been done to the owner's
    accounts, and it is the kind of thing they should be able to open.
    """

    def __init__(self, data_dir: Path | str) -> None:
        self.path = Path(data_dir) / "browser_budgets.json"
        self._lock = threading.RLock()

    # ── reading ─────────────────────────────────────────────────────────────

    def _document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            import json

            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (ValueError, OSError):
            # A corrupt ledger must not read as an empty one, because an empty
            # one hands every account a full budget. Refuse instead.
            raise BudgetSpent(
                f"The action ledger at {self.path} could not be read, so off_CRM "
                "cannot tell how much of your accounts' budgets is left. Nothing "
                "will act until it is repaired or removed."
            ) from None

    def spend_of(self, account_id: str, *, now: float | None = None) -> Spend:
        """What is used in the windows that are open right now.

        Windows that have rolled over read as zero rather than being rewritten,
        so a pure read never touches the file.
        """
        raw = self._document().get(str(account_id))
        spend = Spend.from_dict(raw) if isinstance(raw, dict) else Spend(account=str(account_id))
        if spend.hour_window != _hour_window(now):
            spend.hour_window, spend.hour_count = _hour_window(now), 0
        if spend.day != _today(now):
            spend.day, spend.day_count = _today(now), 0
        return spend

    def check(self, account_id: str, budget: Budget, *,
              now: float | None = None) -> tuple[bool, str]:
        """`(allowed, reason)`, consuming nothing.

        Separate from `record` on purpose: an action can be refused for other
        reasons after this passes, and a budget spent on an action that never
        happened is a budget that lies.
        """
        if budget.unlimited:
            return True, ""
        moment = now if now is not None else time.time()
        spend = self.spend_of(account_id, now=moment)

        if budget.actions_per_hour > 0 and spend.hour_count >= budget.actions_per_hour:
            resets = (spend.hour_window + 1) * 3600 - moment
            return False, (
                f"{account_id} has used its {budget.actions_per_hour} actions for "
                f"this hour. It can act again in {_until(resets)}."
            )
        if budget.actions_per_day > 0 and spend.day_count >= budget.actions_per_day:
            midnight = (int(moment) // 86400 + 1) * 86400
            return False, (
                f"{account_id} has used its {budget.actions_per_day} actions for "
                f"today. It can act again in {_until(midnight - moment)}."
            )
        return True, ""

    # ── writing ─────────────────────────────────────────────────────────────

    def record(self, account_id: str, *, now: float | None = None) -> Spend:
        """Count one action against the account. Called after it happened."""
        moment = now if now is not None else time.time()
        with self._lock:
            document = self._document()
            spend = self.spend_of(account_id, now=moment)
            spend.hour_count += 1
            spend.day_count += 1
            spend.last_action_at = moment
            document[str(account_id)] = spend.to_dict()
            atomic_json(self.path, document)
            return spend

    def reset(self, account_id: str) -> None:
        """Forget an account's spend. For a disconnect, not for a tight budget."""
        with self._lock:
            document = self._document()
            document.pop(str(account_id), None)
            atomic_json(self.path, document)

    def remaining(self, account_id: str, budget: Budget,
                  *, now: float | None = None) -> dict[str, Any]:
        """What is left, for a screen to show before a run rather than after."""
        spend = self.spend_of(account_id, now=now)
        return {
            "account": str(account_id),
            "used_this_hour": spend.hour_count,
            "used_today": spend.day_count,
            "left_this_hour": max(0, budget.actions_per_hour - spend.hour_count)
            if budget.actions_per_hour > 0 else None,
            "left_today": max(0, budget.actions_per_day - spend.day_count)
            if budget.actions_per_day > 0 else None,
            "budget": budget.to_dict(),
        }
