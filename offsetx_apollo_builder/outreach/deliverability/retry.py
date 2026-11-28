"""Bounded retry timing for definite pre-send refusals and worker polling."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math

MAX_RETRY_AFTER_SECONDS = 3600
MAX_WORKER_WAIT_SECONDS = 60.0


def valid_poll_seconds(value: float) -> bool:
    return math.isfinite(value) and 0.25 <= value <= MAX_WORKER_WAIT_SECONDS


def next_worker_retry_wait(poll_seconds: float, previous: float | None) -> float:
    # Double the bounded delay, not an ever-growing exponent.
    return min(MAX_WORKER_WAIT_SECONDS, 2 * (poll_seconds if previous is None else previous))


def delivery_retry_delay(attempt: int, hint: object) -> int | None:
    """None means a valid requested delay is beyond the automatic retry limit."""
    if type(hint) is int and hint > 0:
        return hint if hint <= MAX_RETRY_AFTER_SECONDS else None
    return min(MAX_RETRY_AFTER_SECONDS, 5 * 2 ** min(10, max(0, attempt - 1)))


def parse_retry_after(value: object, *, now: datetime | None = None) -> int | None:
    """Return bounded seconds, or a sentinel for a valid excessive delay."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.isascii() and value.isdecimal():
        digits = value.lstrip('0')
        if len(digits) > 4:
            return MAX_RETRY_AFTER_SECONDS + 1
        return min(MAX_RETRY_AFTER_SECONDS + 1, int(digits or '0'))
    if not value or len(value) > 128:
        return None
    try:
        target = parsedate_to_datetime(value)
        if target.tzinfo is None:
            return None
        seconds = math.ceil((target - (now or datetime.now(timezone.utc))).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None
    return min(MAX_RETRY_AFTER_SECONDS + 1, max(0, seconds))
