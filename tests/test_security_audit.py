"""Regressions for three defects found in the 2026-09-08 security audit.

Each test here failed before its fix and would fail again if the fix were
reverted. They are grouped because they share an origin — an audit rather than a
feature — and separating them would hide that these are the *found* bugs rather
than designed behaviour.

None of them is exotic. All three are what happens when code written for one
user at a time meets a threadpool and a network.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time

import pytest

from offsetx_apollo_builder.api.auth import DemoSessionAuth, LoginAttemptLimiter
from offsetx_apollo_builder.outreach.store import OutreachStore


# ── 1. concurrent transactions on one shared connection ─────────────────────


def _probe_store(tmp_path) -> OutreachStore:
    store = OutreachStore(tmp_path / "audit.db")
    store.initialize()
    store.connection.execute(
        "CREATE TABLE IF NOT EXISTS audit_probe (id INTEGER PRIMARY KEY, who TEXT)"
    )
    store.connection.commit()
    return store


def test_concurrent_transactions_do_not_lose_writes(tmp_path):
    """The one that cost forty rows.

    `check_same_thread=False` hands one connection to every thread and FastAPI
    runs 193 of its 206 handlers in a threadpool, so two requests really do
    arrive here at once. `sqlite3.threadsafety` is 3, which serialises one
    *statement* and does nothing for a transaction made of several.

    Before the fix this lost exactly half its rows: one thread raised "cannot
    start a transaction within a transaction" and the other thread's commit and
    rollback acted on its open transaction. Four threads rather than two,
    because a bug that needs a precise interleaving should be given more chances
    to appear, not fewer.
    """
    store = _probe_store(tmp_path)
    writers, rows_each = 4, 40
    barrier = threading.Barrier(writers)
    errors: list[tuple[str, str]] = []

    def write(name: str) -> None:
        try:
            barrier.wait(timeout=10)
            for index in range(rows_each):
                with store.transaction() as conn:
                    conn.execute("INSERT INTO audit_probe (who) VALUES (?)", (f"{name}-{index}",))
        except Exception as exc:  # noqa: BLE001 - the failure is the assertion
            errors.append((name, f"{type(exc).__name__}: {exc}"))

    threads = [threading.Thread(target=write, args=(name,)) for name in "ABCD"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == [], f"a concurrent writer failed: {errors}"
    total = store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0]
    assert total == writers * rows_each, f"lost {writers * rows_each - total} committed rows"


def test_an_immediate_transaction_is_also_serialised(tmp_path):
    """`claim_next` — the email worker's exclusive claim — uses `immediate=True`.

    BEGIN IMMEDIATE takes SQLite's *file* lock, which protects this database
    from other processes. It cannot protect a connection from itself, so the
    claim was only exclusive between processes and not between threads.
    """
    store = _probe_store(tmp_path)
    barrier = threading.Barrier(3)
    errors: list[str] = []

    def claim(name: str) -> None:
        try:
            barrier.wait(timeout=10)
            for index in range(25):
                with store.transaction(immediate=True) as conn:
                    conn.execute("INSERT INTO audit_probe (who) VALUES (?)", (f"{name}-{index}",))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=claim, args=(name,)) for name in "XYZ"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == [], errors
    assert store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 75


def test_a_failing_transaction_still_rolls_back_and_releases(tmp_path):
    """A lock that is not released on the error path turns data loss into a hang."""
    store = _probe_store(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as conn:
            conn.execute("INSERT INTO audit_probe (id, who) VALUES (1, 'first')")
            conn.execute("INSERT INTO audit_probe (id, who) VALUES (1, 'clash')")

    assert store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 0

    done = threading.Event()

    def after() -> None:
        with store.transaction() as conn:
            conn.execute("INSERT INTO audit_probe (who) VALUES ('after')")
        done.set()

    thread = threading.Thread(target=after)
    thread.start()
    thread.join(timeout=10)
    assert done.is_set(), "the write lock was not released by the failing transaction"


# ── 2. the login limiter grew without bound ─────────────────────────────────


def test_the_login_limiter_forgets_a_client_once_its_window_closes():
    """Pruning emptied each deque and left the key, so the dict only ever grew.

    The key is a client address, and one IPv6 /64 — a single residential
    allocation — is 18 quintillion of them. Measured at 50,000 retained keys
    with every window long expired.
    """
    limiter = LoginAttemptLimiter()
    for index in range(2_000):
        limiter.failed(f"2001:db8::{index:x}", now=0.0)
    assert len(limiter._attempts) == 2_000

    for index in range(2_000):
        limiter.allowed(f"2001:db8::{index:x}", now=100_000.0)

    assert len(limiter._attempts) == 0, "expired clients are still held in memory"


def test_forgetting_expired_clients_does_not_weaken_the_limit():
    """The fix must not become a way to reset the counter by asking politely."""
    limiter = LoginAttemptLimiter(maximum=5, window_seconds=300)
    for _ in range(5):
        limiter.failed("198.51.100.7", now=1.0)

    for moment in (1.0, 2.0, 100.0, 299.0):
        assert limiter.allowed("198.51.100.7", now=moment) is False, moment
    assert limiter.allowed("198.51.100.7", now=1_000.0) is True


# ── 3. the username was a timing oracle ─────────────────────────────────────


def test_a_wrong_username_compares_the_password_anyway():
    """`and` short-circuits, so a wrong username returned before the password
    was ever compared — and that difference is measurable. The constant-time
    comparison underneath is wasted if the call above it branches.

    Asserted structurally rather than by timing: a wall-clock test of a
    microsecond difference is flaky on shared CI and would be deleted within a
    month. This counts comparisons instead, which is the property that matters.
    """
    import hmac

    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    calls: list[int] = []
    real = hmac.compare_digest

    def counting(left, right):
        calls.append(1)
        return real(left, right)

    hmac.compare_digest = counting
    try:
        calls.clear()
        auth.authenticate("owner", "wrong-password-entirely")
        with_right_user = len(calls)

        calls.clear()
        auth.authenticate("not-the-owner", "wrong-password-entirely")
        with_wrong_user = len(calls)
    finally:
        hmac.compare_digest = real

    assert with_wrong_user == with_right_user == 2, (
        "a wrong username skips the password comparison, which leaks which "
        "usernames are real"
    )


def test_authentication_still_answers_correctly():
    """The obvious thing to break while removing a short circuit."""
    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    assert auth.authenticate("owner", "a-long-enough-password") is True
    assert auth.authenticate("owner", "wrong") is False
    assert auth.authenticate("wrong", "a-long-enough-password") is False
    assert auth.authenticate("", "") is False


def test_a_session_token_still_round_trips_and_expires():
    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    token = auth.issue(now=1_000)
    assert auth.verify(token, now=1_000).username == "owner"
    assert auth.verify(token, now=1_000 + 3601) is None
    assert auth.verify(token[:-2] + "xx", now=1_000) is None
