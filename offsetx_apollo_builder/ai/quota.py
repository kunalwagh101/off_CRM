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
import math
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..db.hosted import QUOTA, HostedStorage
from ..observability import report_failure

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
    # A reservation is committed BEFORE network I/O. An in-flight or crashed
    # call is charged conservatively until its actual receipt is reconciled.
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

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
            "pending": self.pending,
            "settled": self.settled,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuotaState":
        if not isinstance(payload, dict):
            raise QuotaStorageError("The quota ledger is invalid; restore a verified backup.")
        try:
            state = cls(
                provider_id=str(payload.get("provider_id", "")),
                minute_window=int(payload.get("minute_window", 0) or 0),
                minute_count=int(payload.get("minute_count", 0) or 0),
                day=str(payload.get("day", "")),
                day_count=int(payload.get("day_count", 0) or 0),
                day_spend_usd=float(payload.get("day_spend_usd", 0.0) or 0.0),
                last_call_at=float(payload.get("last_call_at", 0.0) or 0.0),
                consecutive_rate_limits=int(payload.get("consecutive_rate_limits", 0) or 0),
                pending=payload.get("pending", {}),
                settled=payload.get("settled", {}),
            )
            if (
                min(state.minute_window, state.minute_count, state.day_count,
                    state.consecutive_rate_limits) < 0
                or state.day_spend_usd < 0
                or not math.isfinite(state.day_spend_usd)
                or not math.isfinite(state.last_call_at)
                or not isinstance(state.pending, dict)
                or not isinstance(state.settled, dict)
            ):
                raise ValueError("Invalid quota value")
            for ticket, hold in state.pending.items():
                if (
                    not isinstance(ticket, str)
                    or not isinstance(hold, dict)
                    or not isinstance(hold.get("day"), str)
                    or not isinstance(hold.get("amount"), (int, float))
                    or not math.isfinite(float(hold["amount"]))
                    or float(hold["amount"]) < 0
                ):
                    raise ValueError("Invalid reservation")
            if not all(isinstance(k, str) and isinstance(v, str)
                       for k, v in state.settled.items()):
                raise ValueError("Invalid reconciled IDs")
            return state
        except (TypeError, ValueError, OverflowError) as exc:
            raise QuotaStorageError(
                "The quota ledger is invalid; no AI call was sent. Restore a verified backup."
            ) from None


class QuotaStorageError(RuntimeError):
    """Unreadable or unwritable usage must block provider transport."""


class QuotaLimitError(RuntimeError):
    """A reservation was refused before a paid provider attempt."""


@contextmanager
def _local_quota_lock(path: Path) -> Iterator[None]:
    """Cross-process lock kept *beside* the replaceable quota JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt
                # Windows byte-range locks need the locked byte to exist.
                if handle.tell() == 0:
                    handle.write(b"1")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        raise QuotaStorageError(
            "The quota ledger is unavailable; no AI call was sent. Check its storage."
        ) from None


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _minute_window() -> int:
    return int(time.time() // 60)


class QuotaTracker:
    """Per-provider call and spend accounting, persisted to a JSON file.

    Deliberately file-backed rather than in the CRM database: the AI module has
    to be liftable into its own repository (§4M), so it does not reach into the
    CRM's schema for its own bookkeeping.

    Or, given hosted storage, the same document in the hosted database
    (`S-06.03.02`, `DD-69`): a free Render service loses its disk at every
    spin-down, and a daily limit counted there started again from zero each
    time — not a limit at all (D-198).
    """

    def __init__(self, data_dir: Path | str, *, hosted: HostedStorage | None = None) -> None:
        self.path = Path(data_dir) / "ai_quota.json"
        self._hosted = hosted
        self._lock = threading.RLock()
        self._states: dict[str, QuotaState] = {}
        self._loaded = False
        #: Calls recorded while the counters could not be read: (provider,
        #: spend, rate limited, day), counted in at the next good read (D-207).
        self._pending: list[tuple[str, float, bool, str]] = []

    def prepare(self) -> None:
        """Read the counters before any call is made.

        The broker asks this before it calls a provider, so a database that
        cannot answer fails the task while nothing has been sent or billed —
        not after, when the answer would be lost (D-207).
        """
        with self._lock:
            self._load()

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self._hosted is not None:
                body = self._hosted.read(QUOTA)
            else:
                if self.path.is_symlink():
                    raise QuotaStorageError("The quota ledger is not a regular file; check its storage.")
                body = self.path.read_text(encoding="utf-8") if self.path.exists() else None
            payload = json.loads(
                body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
            ) if body is not None else {}
            if not isinstance(payload, dict) or not all(
                isinstance(k, str) and isinstance(v, dict)
                for k, v in payload.items()
            ):
                raise ValueError("Invalid quota document")
            self._states = {
                key: QuotaState.from_dict(value) for key, value in payload.items()
            }
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            raise QuotaStorageError(
                "The quota ledger is corrupt or unavailable; no AI call was sent. "
                "Restore verified counters before retrying."
            ) from None
        self._loaded = True
        pending, self._pending = self._pending, []
        today = _today()
        for provider_id, spend_usd, rate_limited, day in pending:
            if day == today:
                self._count(self._state(provider_id), spend_usd, rate_limited)
        if pending:
            self._save()

    def _save(self, *, strict: bool = False) -> None:
        payload = {key: value.to_dict() for key, value in self._states.items()}
        try:
            if self._hosted is not None:
                self._hosted.write(QUOTA, json.dumps(payload, ensure_ascii=False, allow_nan=False))
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.path.parent, delete=False
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        except Exception as exc:
            if strict:
                raise QuotaStorageError(
                    "The quota reservation could not be saved; no AI call was sent. "
                    "Check durable quota storage before retrying."
                ) from None
            report_failure(exc, operation="ai.usage.save", data_dir=self.path.parent)

    @contextmanager
    def _exclusive_state(self) -> Iterator[None]:
        """Reload, check, reserve and commit under ONE interprocess transaction.

        SQLite/PG use the existing HostedStorage transaction and advisory lock.
        The local ledger uses a separate OS lock file (the JSON is replaced).
        No network I/O is done while holding either lock.
        """
        with self._lock:
            context = (
                self._hosted.exclusive() if self._hosted is not None
                else _local_quota_lock(self.path.with_suffix(".lock"))
            )
            with context:
                self._loaded = False
                try:
                    self._load()
                    yield
                    self._save(strict=True)
                finally:
                    self._loaded = False

    @staticmethod
    def _scope(provider_id: str, scope_id: str) -> str:
        if not scope_id:
            return provider_id
        # The scope ID is the credential fingerprint, never the credential.
        return f"account:{provider_id}:{scope_id}"

    def try_reserve(
        self, provider_id: str, limits: QuotaLimits, *,
        worst_case_usd: float = 0.0, scope_id: str = "",
    ) -> tuple[str | None, str]:
        """Atomically book one provider attempt before transport.

        A crashed/unknown attempt keeps its count and max spend held. A later
        measured receipt may refund unused spend, but never the attempt count.
        """
        if not math.isfinite(worst_case_usd) or worst_case_usd < 0:
            raise QuotaStorageError("Quota reservation requires a valid non-negative cost bound.")
        key = self._scope(provider_id, scope_id)
        ticket = uuid.uuid4().hex
        denied = ""
        with self._exclusive_state():
            state = self._state(key)
            # The old provider-only ledger is retained as a conservative
            # baseline for accounts migrated while a day's window is active.
            old = self._states.get(provider_id) if key != provider_id else None
            minute = state.minute_count + (
                old.minute_count if old and old.minute_window == state.minute_window else 0
            )
            count = state.day_count + (old.day_count if old and old.day == state.day else 0)
            spend = state.day_spend_usd + (
                old.day_spend_usd if old and old.day == state.day else 0
            )
            if limits.requests_per_minute > 0 and minute >= limits.requests_per_minute:
                denied = "per-minute limit reached; resets within a minute"
            elif limits.requests_per_day > 0 and count >= limits.requests_per_day:
                denied = "daily limit reached; resets at 00:00 UTC"
            elif limits.max_spend_usd_per_day > 0 and (
                spend + worst_case_usd > limits.max_spend_usd_per_day + 1e-12
            ):
                denied = "daily spend cap reached or the conservative cost bound is too high"
            if not denied:
                state.minute_count += 1
                state.day_count += 1
                state.day_spend_usd += worst_case_usd
                state.last_call_at = time.time()
                state.pending[ticket] = {
                    "day": state.day, "amount": worst_case_usd,
                }
        return (None, denied) if denied else (ticket, "")

    def reserve(
        self, provider_id: str, limits: QuotaLimits, *,
        worst_case_usd: float = 0.0, scope_id: str = "",
    ) -> str:
        ticket, reason = self.try_reserve(
            provider_id, limits, worst_case_usd=worst_case_usd, scope_id=scope_id,
        )
        if ticket is None:
            raise QuotaLimitError(reason)
        return ticket

    def reconcile(
        self, provider_id: str, ticket: str, *,
        spend_usd: float, rate_limited: bool = False, scope_id: str = "",
    ) -> bool:
        """Settle one ticket once. Never retry an uncertain provider action."""
        if not math.isfinite(spend_usd) or spend_usd < 0:
            raise QuotaStorageError("Provider usage cannot be reconciled with an invalid cost.")
        key = self._scope(provider_id, scope_id)
        changed = False
        with self._exclusive_state():
            state = self._states.get(key)
            if state is None:
                raise QuotaStorageError("Quota reservation not found; check the ledger before retrying.")
            if ticket in state.settled:
                return False
            entry = state.pending.get(ticket)
            if entry is None:
                raise QuotaStorageError("Quota reservation not found; do not repeat provider transport.")
            if entry["day"] == state.day:
                state.day_spend_usd += spend_usd - float(entry["amount"])
                state.day_spend_usd = max(0.0, state.day_spend_usd)
            state.consecutive_rate_limits = (
                state.consecutive_rate_limits + 1 if rate_limited else 0
            )
            del state.pending[ticket]
            state.settled[ticket] = _today()
            changed = True
        return changed

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
        """Count a call that was made. Never raises: the answer it counts was
        already produced and billed, and losing it to a counter read would
        make the user pay for it twice (D-207)."""
        with self._lock:
            try:
                state = self._state(provider_id)
            except Exception as exc:  # noqa: BLE001 - counted at the next good read
                self._pending.append((provider_id, spend_usd, rate_limited, _today()))
                report_failure(exc, operation="ai.usage.read", data_dir=self.path.parent)
                return
            self._count(state, spend_usd, rate_limited)
            self._save()

    @staticmethod
    def _count(state: QuotaState, spend_usd: float, rate_limited: bool) -> None:
        state.minute_count += 1
        state.day_count += 1
        state.day_spend_usd += max(0.0, spend_usd)
        state.last_call_at = time.time()
        state.consecutive_rate_limits = (
            state.consecutive_rate_limits + 1 if rate_limited else 0
        )

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
