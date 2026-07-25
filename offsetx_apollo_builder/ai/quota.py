"""Local quota accounting.

Most providers do not expose remaining-quota over their API, and the ones that
do disagree on how.  So off_CRM counts locally (§4E): every call the broker
makes is recorded against the provider's published per-minute and per-day
limits, and a provider that has run out is skipped rather than called and
rate-limited.

Counting locally also means the numbers survive a provider that lies, and it
gives the owner a usage display even for providers with no usage endpoint.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

#: Spend and call ceilings the owner can set per provider, independent of the
#: provider's own free-tier limits.
@dataclass(slots=True)
class QuotaLimits:
    requests_per_minute: int = 0
    requests_per_day: int = 0
    max_spend_usd_per_day: float = 0.0

    @property
    def unlimited(self) -> bool:
        return (
            self.requests_per_minute <= 0
            and self.requests_per_day <= 0
            and self.max_spend_usd_per_day <= 0
        )


@dataclass(slots=True)
class QuotaState:
    provider_id: str
    minute_window: int = 0
    minute_count: int = 0
    day: str = ""
    day_count: int = 0
    day_spend_usd: float = 0.0
    last_call_at: float = 0.0
    consecutive_rate_limits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "minute_window": self.minute_window,
            "minute_count": self.minute_count,
            "day": self.day,
            "day_count": self.day_count,
            "day_spend_usd": round(self.day_spend_usd, 6),
            "last_call_at": self.last_call_at,
            "consecutive_rate_limits": self.consecutive_rate_limits,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuotaState":
        return cls(
            provider_id=str(payload.get("provider_id", "")),
            minute_window=int(payload.get("minute_window", 0) or 0),
            minute_count=int(payload.get("minute_count", 0) or 0),
            day=str(payload.get("day", "")),
            day_count=int(payload.get("day_count", 0) or 0),
            day_spend_usd=float(payload.get("day_spend_usd", 0.0) or 0.0),
            last_call_at=float(payload.get("last_call_at", 0.0) or 0.0),
            consecutive_rate_limits=int(payload.get("consecutive_rate_limits", 0) or 0),
        )


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _minute_window() -> int:
    return int(time.time() // 60)


class QuotaTracker:
    """Per-provider call and spend accounting, persisted to a JSON file.

    Deliberately file-backed rather than in the CRM database: the AI module has
    to be liftable into its own repository (§4M), so it does not reach into the
    CRM's schema for its own bookkeeping.
    """

    def __init__(self, data_dir: Path | str) -> None:
        self.path = Path(data_dir) / "ai_quota.json"
        self._lock = threading.RLock()
        self._states: dict[str, QuotaState] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._states = {
                        str(key): QuotaState.from_dict(value)
                        for key, value in payload.items()
                        if isinstance(value, dict)
                    }
            except (OSError, json.JSONDecodeError):
                # Corrupt counters must not stop the app; worst case we
                # under-count for the rest of the day.
                self._states = {}
        self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: value.to_dict() for key, value in self._states.items()}
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                temporary = Path(handle.name)
            os.replace(temporary, self.path)
        except OSError:
            pass

    def _state(self, provider_id: str) -> QuotaState:
        self._load()
        state = self._states.get(provider_id)
        if state is None:
            state = QuotaState(provider_id=provider_id)
            self._states[provider_id] = state
        window = _minute_window()
        if state.minute_window != window:
            state.minute_window = window
            state.minute_count = 0
        today = _today()
        if state.day != today:
            state.day = today
            state.day_count = 0
            state.day_spend_usd = 0.0
        return state

    def check(self, provider_id: str, limits: QuotaLimits) -> tuple[bool, str]:
        """Return ``(allowed, reason)`` without consuming quota."""
        with self._lock:
            state = self._state(provider_id)
            if limits.requests_per_minute > 0 and state.minute_count >= limits.requests_per_minute:
                return False, (
                    f"per-minute limit reached ({state.minute_count}/"
                    f"{limits.requests_per_minute}); resets within a minute"
                )
            if limits.requests_per_day > 0 and state.day_count >= limits.requests_per_day:
                return False, (
                    f"daily limit reached ({state.day_count}/{limits.requests_per_day}); "
                    "resets at 00:00 UTC"
                )
            if (
                limits.max_spend_usd_per_day > 0
                and state.day_spend_usd >= limits.max_spend_usd_per_day
            ):
                return False, (
                    f"daily spend cap reached (${state.day_spend_usd:.2f}/"
                    f"${limits.max_spend_usd_per_day:.2f})"
                )
            return True, ""

    def record(self, provider_id: str, *, spend_usd: float = 0.0, rate_limited: bool = False) -> None:
        with self._lock:
            state = self._state(provider_id)
            state.minute_count += 1
            state.day_count += 1
            state.day_spend_usd += max(0.0, spend_usd)
            state.last_call_at = time.time()
            state.consecutive_rate_limits = (
                state.consecutive_rate_limits + 1 if rate_limited else 0
            )
            self._save()

    def usage(self, provider_id: str, limits: QuotaLimits) -> dict[str, Any]:
        """Shape the Connectors screen renders as a usage bar."""
        with self._lock:
            state = self._state(provider_id)
            return {
                "provider_id": provider_id,
                "minute_used": state.minute_count,
                "minute_limit": limits.requests_per_minute,
                "day_used": state.day_count,
                "day_limit": limits.requests_per_day,
                "day_spend_usd": round(state.day_spend_usd, 4),
                "day_spend_cap_usd": limits.max_spend_usd_per_day,
                "source": "counted_locally",
                "exhausted": not self.check(provider_id, limits)[0],
            }

    def reset(self, provider_id: str = "") -> None:
        with self._lock:
            self._load()
            if provider_id:
                self._states.pop(provider_id, None)
            else:
                self._states = {}
            self._save()
