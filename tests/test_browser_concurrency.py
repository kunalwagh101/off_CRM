"""Concurrent runs share one browser safely.  `S-11.05.01`

Three acceptance criteria. Before this story, measured rather than assumed:

    handle isolation   HELD    each tab keeps its own snapshot
    per-host pace      BROKEN  two runs, a 1.0s floor, six actions: 2.00s where
                               5.00s is honest. Each run kept its own clock, so
                               N runs divided the floor by N.
    one account budget BROKEN  four concurrent runs, 25 actions each: the
                               ledger counted 33 of 100. Two thirds of the
                               account's budget spent off the books.

Both failures are one mistake wearing two hats — **state that has to be shared
across runs, held per run.** That is the defect log's pattern 3, and the reason
these tests are written concurrently rather than in sequence: a sequential probe
passed both of them while both were broken.
"""
from __future__ import annotations

import asyncio
import tempfile
import threading
import time
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser.budget import Budget, BudgetLedger
from offsetx_apollo_builder.browser.pace import Pace
from offsetx_apollo_builder.browser.page import Page
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.policy import DomainRule

SLOW = DomainRule(suffix="slow.test", label="Slow", min_seconds_between_actions=0.2)
FREE = DomainRule(suffix="quick.test", label="Quick", min_seconds_between_actions=0.0)


class _Connection:
    async def send(self, method, params=None, *, session_id="", timeout=None):
        return {}


def _tabs(count: int, *, pace: Pace | None = None) -> list[Page]:
    shared = pace if pace is not None else Pace()
    return [Page(connection=_Connection(), session_id=f"s{n}", pace=shared)
            for n in range(count)]


# ── the floor is counted across runs, not per run ───────────────────────────


def test_two_runs_on_one_host_share_the_floor():
    """The criterion. Six actions at a 0.2s floor is 1.0s of spacing however
    many runs are taking them."""
    async def go():
        a, b = _tabs(2)
        started = time.monotonic()
        await asyncio.gather(*[tab._pace(SLOW, "slow.test")
                               for tab in (a, b) for _ in range(3)])
        return time.monotonic() - started

    assert asyncio.run(go()) >= 1.0


def test_a_private_clock_is_what_the_bug_looked_like():
    """The measurement that proved it, kept as a test so the fix cannot be
    quietly undone: tabs that do *not* share a pace go twice as fast."""
    async def go():
        a = Page(connection=_Connection(), session_id="a", pace=Pace())
        b = Page(connection=_Connection(), session_id="b", pace=Pace())
        started = time.monotonic()
        await asyncio.gather(*[tab._pace(SLOW, "slow.test")
                               for tab in (a, b) for _ in range(3)])
        return time.monotonic() - started

    assert asyncio.run(go()) < 0.9, "separate paces no longer run independently"


def test_the_floor_holds_as_the_number_of_runs_grows():
    """N runs must not divide the interval by N. This is the shape of the bug,
    so it is tested at a size where the old behaviour could not hide."""
    async def go():
        tabs = _tabs(5)
        started = time.monotonic()
        await asyncio.gather(*[tab._pace(SLOW, "slow.test") for tab in tabs])
        return time.monotonic() - started

    assert asyncio.run(go()) >= 0.8, "five runs did not queue behind each other"


def test_runs_arriving_together_are_spaced_rather_than_all_waved_through():
    """The race the deadline exists for: everybody reads "the last action was
    long ago", everybody decides not to wait, everybody acts at once."""
    async def go():
        tabs = _tabs(4)
        finished: list[float] = []

        async def act(tab):
            await tab._pace(SLOW, "slow.test")
            finished.append(time.monotonic())

        await asyncio.gather(*(act(tab) for tab in tabs))
        return sorted(finished)

    at = asyncio.run(go())
    gaps = [b - a for a, b in zip(at, at[1:])]
    assert all(gap >= 0.15 for gap in gaps), f"actions bunched together: {gaps}"


def test_different_hosts_do_not_wait_for_each_other():
    """The floor is per host. Slowing an unrelated site would make the agent
    pointlessly slow, and slow things get switched off."""
    async def go():
        tabs = _tabs(2)
        started = time.monotonic()
        await asyncio.gather(tabs[0]._pace(SLOW, "slow.test"),
                             tabs[1]._pace(SLOW, "other.test"))
        return time.monotonic() - started

    assert asyncio.run(go()) < 0.15


def test_a_host_with_no_floor_costs_nothing():
    async def go():
        tabs = _tabs(3)
        started = time.monotonic()
        await asyncio.gather(*[tab._pace(FREE, "quick.test") for tab in tabs])
        return time.monotonic() - started

    assert asyncio.run(go()) < 0.1


def test_one_run_waiting_does_not_block_another_reserving_its_slot():
    """The sleep happens outside the lock. Otherwise the pacer serialises the
    whole program rather than just the host."""
    async def go():
        pace = Pace()
        started = time.monotonic()
        await asyncio.gather(pace.wait_for("slow.test", 0.3),
                             pace.wait_for("elsewhere.test", 0.3))
        return time.monotonic() - started

    assert asyncio.run(go()) < 0.35, "two hosts were serialised against each other"


# ── one account, one budget ─────────────────────────────────────────────────


def test_concurrent_runs_draw_on_one_budget_not_one_each():
    """The criterion, and the measurement that proved it broken: four runs
    taking 25 actions each left 33 of 100 in the ledger."""
    runs, actions = 4, 25
    data = Path(tempfile.mkdtemp())
    ready = threading.Barrier(runs)

    def one_run():
        ledger = BudgetLedger(data)      # its own object, over the same file
        ready.wait()
        for _ in range(actions):
            ledger.record("acct")

    threads = [threading.Thread(target=one_run) for _ in range(runs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    counted = BudgetLedger(data).spend_of("acct").hour_count
    assert counted == runs * actions, (
        f"{runs * actions - counted} actions were spent off the books"
    )


def test_separate_ledger_objects_over_one_file_share_a_lock():
    """The fix, stated directly. Correctness that depends on every caller
    remembering to share an instance lapses the first time somebody builds one
    locally — so the lock is keyed by the file rather than handed in."""
    data = Path(tempfile.mkdtemp())
    assert BudgetLedger(data)._lock is BudgetLedger(data)._lock


def test_ledgers_over_different_files_do_not_block_each_other():
    assert BudgetLedger(Path(tempfile.mkdtemp()))._lock is not \
        BudgetLedger(Path(tempfile.mkdtemp()))._lock


@pytest.mark.parametrize("runs", [1, 2, 3, 5])
def test_the_ceiling_can_be_overshot_by_the_runs_in_flight_and_no_more(runs):
    """**A known limit, measured and pinned rather than discovered.**

    `S-03.02.04` decided deliberately that an action is checked *before* it
    happens and recorded *after*, so an action that raises on the way down —
    a stale handle, an element with no shape — never spends budget on a page
    the agent could not use. That decision is not reversed here.

    The cost of it under concurrency is a gap between the check and the record,
    and exactly one action per run can be inside that gap. So the ceiling can
    be exceeded by at most **one action per concurrent run, minus the one that
    would have been allowed anyway** — and by no more, however long the runs go
    on. Measured at 1, 2, 3, 5 and 8 runs: the overshoot was N-1 every time.

    Closing it entirely needs a reserve-and-release protocol threaded through
    every action's error path, which is a larger change than the gap it shuts
    and would reverse a decision made with its own reasoning.
    """
    ceiling = 30
    data = Path(tempfile.mkdtemp())
    budget = Budget(actions_per_hour=ceiling, actions_per_day=3_000)
    ready = threading.Barrier(runs)
    allowed: list[bool] = []
    guard = threading.Lock()

    def one_run():
        ledger = BudgetLedger(data)
        ready.wait()
        for _ in range(40):
            ok, _ = ledger.check("acct", budget)
            with guard:
                allowed.append(ok)
            if ok:
                ledger.record("acct")

    threads = [threading.Thread(target=one_run) for _ in range(runs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    taken = sum(allowed)
    assert taken >= ceiling, "the ceiling was not reached at all"
    assert taken <= ceiling + (runs - 1), (
        f"{taken} actions against a ceiling of {ceiling} with {runs} runs — "
        f"the overshoot is meant to be bounded by {runs - 1}"
    )


# ── one tab cannot reach into another ───────────────────────────────────────


def test_neither_run_can_resolve_a_handle_from_the_others_page():
    """Held before this story and kept held: handles are numbered per snapshot,
    and a snapshot belongs to one tab."""
    a, b = _tabs(2)
    a._snapshot = Snapshot(url="https://a.test/",
                           nodes=[Node(handle=1, role="button", name="A only")])
    b._snapshot = Snapshot(url="https://b.test/",
                           nodes=[Node(handle=2, role="button", name="B only")])

    with pytest.raises(LookupError):
        a._current(2).find(2)
    with pytest.raises(LookupError):
        b._current(1).find(1)


def test_each_run_keeps_its_own_url_and_snapshot():
    a, b = _tabs(2)
    a._snapshot = Snapshot(url="https://a.test/", nodes=[])
    a.url = "https://a.test/"
    b._snapshot = Snapshot(url="https://b.test/", nodes=[])
    b.url = "https://b.test/"

    assert a._snapshot is not b._snapshot
    assert a.url != b.url


def test_a_session_hands_out_one_pace_so_there_is_a_right_answer():
    """The gap this closes: a tab given no pace keeps a private clock, which is
    the bug. `BrowserSession` holds one so the obvious construction is correct
    rather than a convention somebody has to remember."""
    from offsetx_apollo_builder.browser.session import BrowserSession

    session = BrowserSession(connection=_Connection(), endpoint="ws://x", port=1)
    assert isinstance(session.pace, Pace)
    first, second = (Page(connection=_Connection(), session_id="a", pace=session.pace),
                     Page(connection=_Connection(), session_id="b", pace=session.pace))
    assert first.pace is second.pace
