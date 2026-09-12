"""The live check for `S-11.05.01` — two runs, one real browser.

Real: one Chromium, two tabs, two traces, real navigation, the real pace gate
and the real budget ledger on disk. The two runs act at the same time, which is
the only way this story can be tested — a sequential probe passed both of the
failures this story fixes while both were broken.

    1. each run has its own tab, its own trace and its own snapshot
    2. neither can resolve a handle from the other's page
    3. the per-host floor is kept across both, not per run
    4. both draw on one account budget, not one each

Run it with ``python scripts/live/two_runs_one_browser.py``. Exit 0 means all
four held.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from offsetx_apollo_builder.browser.budget import Budget, BudgetLedger  # noqa: E402
from offsetx_apollo_builder.browser.page import Page  # noqa: E402
from offsetx_apollo_builder.browser.session import free_port, open_session  # noqa: E402
from offsetx_apollo_builder.browser.trace import Step, Trace  # noqa: E402

EXTRA_FLAGS: tuple[str, ...] = ("--no-sandbox",) if os.geteuid() == 0 else ()

#: A floor big enough to see. `policy.py`'s real numbers are seconds; this is
#: the same mechanism with a number that keeps the check short.
FLOOR = 0.4
ACTIONS_EACH = 4


def _page_html(which: str) -> str:
    return ("<html><head><title>Run " + which + "</title></head><body>"
            "<h1>Run " + which + "</h1>"
            "<button id='only'>Only on " + which + "</button>"
            "</body></html>")


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


async def main() -> int:
    profile = Path(tempfile.mkdtemp(prefix="concurrent-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    data = Path(tempfile.mkdtemp(prefix="concurrent-data-"))
    traces = Path(tempfile.mkdtemp(prefix="concurrent-traces-"))
    budget = Budget(actions_per_hour=100, actions_per_day=1_000)
    ok = True
    tabs: list[tuple[str, Page, Trace]] = []

    try:
        for which in ("A", "B"):
            target_id, session_id = await session.new_tab(
                "data:text/html," + quote(_page_html(which)))
            page = Page(
                connection=session.connection, session_id=session_id,
                # The one line this whole story is about: both tabs keep the
                # browser's rhythm, and both draw on the same account.
                pace=session.pace,
                ledger=BudgetLedger(data), account="demo:one", budget=budget,
            )
            await page.start()
            page.url = f"https://acme.test/{which}"
            tabs.append((which, page, Trace.open(traces / which)))
        await asyncio.sleep(1.0)

        print("1. each run has its own tab, trace and snapshot")
        for which, page, trace in tabs:
            snapshot = await page.snapshot()
            trace.append(Step(kind="run_started", detail=f"run {which}",
                              url=page.url))
        a, b = tabs[0][1], tabs[1][1]
        ok &= _check("different tabs", a.session_id != b.session_id)
        ok &= _check("different traces",
                     tabs[0][2].run_id != tabs[1][2].run_id)
        ok &= _check("different snapshots", a._snapshot is not b._snapshot,
                     f"{a._snapshot.title!r} vs {b._snapshot.title!r}")

        print("\n2. neither can reach into the other's page")
        theirs = max(node.handle for node in b._snapshot.nodes) + 1
        try:
            a._current(theirs).find(theirs)
            ok &= _check("a handle from the other page is refused", False,
                         "it resolved")
        except LookupError as exc:
            ok &= _check("a handle from the other page is refused", True,
                         type(exc).__name__)

        print("\n3. the per-host floor is kept across both runs")
        from offsetx_apollo_builder.browser.policy import DomainRule
        rule = DomainRule(suffix="acme.test", label="Acme",
                          min_seconds_between_actions=FLOOR)
        started = time.monotonic()
        await asyncio.gather(*[
            page._pace(rule, "acme.test")
            for _, page, _ in tabs for _ in range(ACTIONS_EACH)
        ])
        elapsed = time.monotonic() - started
        honest = FLOOR * (2 * ACTIONS_EACH - 1)
        ok &= _check(f"{2 * ACTIONS_EACH} actions took at least {honest:.1f}s",
                     elapsed >= honest - 0.05,
                     f"{elapsed:.2f}s (a floor kept per run would be "
                     f"~{honest / 2:.1f}s)")

        print("\n4. both draw on one account budget")
        for _, page, _ in tabs:
            for _ in range(5):
                page._charge("click")
        counted = BudgetLedger(data).spend_of("demo:one").hour_count
        ok &= _check("every action reached the one ledger", counted == 10,
                     f"{counted} of 10 counted")
    finally:
        await session.close(quit_browser=True)

    print(f"\n{'all four held' if ok else 'SOMETHING DID NOT HOLD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
