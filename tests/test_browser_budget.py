"""Several accounts per platform, each with its own budget.  `S-03.02.04`

The thing being defended against is not a rate limit. A platform that decides
you are a script does not answer `429` — it restricts or closes the account, and
the account is what the owner spent months building. So the budget is checked
*before* the action and the refusal says when it comes back.

Three acceptance criteria, and the last one is the easiest to get wrong:
looking must be free. If `read` and `screenshot` cost budget, an agent trying to
be frugal will act without looking first, which is exactly the behaviour that
gets an account noticed.

The live test drives a real Chromium against a `data:` URL — never a real
platform, because a test that exercises somebody's rate limits to prove it
respects them has missed the point.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser import identity
from offsetx_apollo_builder.browser.budget import (
    COSTED_ACTIONS,
    DEFAULT_BUDGET,
    DEFAULT_BUDGETS,
    Budget,
    BudgetLedger,
    BudgetSpent,
)
from offsetx_apollo_builder.browser.identity import (
    ConnectionStore,
    Reading,
    account_id,
    catalogue,
    platform,
)
from offsetx_apollo_builder.browser.page import ACTIONS, ActionRefused, Page
from offsetx_apollo_builder.browser.session import (
    BrowserUnavailable,
    find_browser,
    free_port,
    open_session,
)

HOUR = 3600.0


# ── AC1: two accounts on one platform are independent ───────────────────────


def test_the_default_account_is_named_after_the_platform(tmp_path):
    """Which is what makes every record written before accounts existed keep
    working with no migration step."""
    assert account_id("linkedin") == "linkedin"
    assert account_id("linkedin", "linkedin") == "linkedin"
    assert account_id("LinkedIn", "Work") == "linkedin:work"


def test_an_account_label_cannot_collide_with_another_account(tmp_path):
    """A colon in the label would produce a key that reads as a different
    account entirely, so it is normalised rather than trusted."""
    assert account_id("linkedin", "work:admin") == "linkedin:work-admin"
    assert account_id("linkedin", "  Work Account! ") == "linkedin:workaccount"


def test_two_accounts_on_one_platform_are_recorded_separately(tmp_path):
    store = ConnectionStore(tmp_path)
    target = platform("linkedin")
    store.record("local", Reading(state="connected", evidence="my network"), target,
                 account="work", handle="Work Profile")
    store.record("local", Reading(state="disconnected", evidence="sign in"), target,
                 account="personal")

    work = store.get("local", "linkedin", "personal")
    assert work.state == "disconnected"
    assert store.get("local", "linkedin", "work").state == "connected"
    assert store.get("local", "linkedin", "work").handle == "Work Profile"

    accounts = store.accounts("local", "linkedin")
    assert sorted(row.account for row in accounts) == ["linkedin:personal", "linkedin:work"]


def test_a_record_written_before_accounts_existed_still_reads(tmp_path):
    """The migration test. Its key is the bare platform id, which is exactly
    what `account_id` returns for the default account."""
    import json

    (tmp_path / "browser_connections.json").write_text(json.dumps({
        "local": {"linkedin": {"platform": "linkedin", "state": "connected",
                               "checked_at": "2026-08-28T00:00:00Z",
                               "evidence": "my network", "handle": "Old"}}
    }), encoding="utf-8")

    old = ConnectionStore(tmp_path).get("local", "linkedin")
    assert old.state == "connected"
    assert old.handle == "Old"
    assert old.account == "linkedin"


def test_forgetting_one_account_leaves_the_other(tmp_path):
    store = ConnectionStore(tmp_path)
    target = platform("linkedin")
    store.record("local", Reading(state="connected", evidence="a"), target, account="work")
    store.record("local", Reading(state="connected", evidence="b"), target, account="personal")

    store.forget("local", "linkedin", "work")
    assert [row.account for row in store.accounts("local", "linkedin")] == ["linkedin:personal"]


def test_spending_one_account_does_not_spend_the_other(tmp_path):
    """AC1, stated as the thing that actually matters."""
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=3, actions_per_day=10)

    for _ in range(3):
        ledger.record("linkedin:work")

    assert ledger.check("linkedin:work", budget)[0] is False
    assert ledger.check("linkedin:personal", budget)[0] is True


# ── AC2: a spent budget refuses, and says when it returns ───────────────────


def test_a_spent_hour_refuses_and_says_when_it_comes_back(tmp_path):
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=2, actions_per_day=100)
    now = 1_800_000_000.0  # a fixed moment, so the arithmetic is checkable

    ledger.record("linkedin", now=now)
    ledger.record("linkedin", now=now)
    allowed, reason = ledger.check("linkedin", budget, now=now)

    assert allowed is False
    assert "2 actions for this hour" in reason
    assert "can act again in" in reason


def test_a_spent_day_refuses_even_when_the_hour_is_fresh(tmp_path):
    """The hour window rolling over must not hand back the day's budget."""
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=5, actions_per_day=6)
    start = 1_800_000_000.0

    for index in range(6):
        ledger.record("x", now=start + index * (HOUR / 4))

    later = start + 2 * HOUR  # a brand new hour window, same day
    allowed, reason = ledger.check("x", budget, now=later)
    assert allowed is False
    assert "6 actions for today" in reason


def test_the_hour_window_reopens_without_anything_rewriting_the_file(tmp_path):
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=2, actions_per_day=100)
    start = 1_800_000_000.0

    ledger.record("x", now=start)
    ledger.record("x", now=start)
    assert ledger.check("x", budget, now=start)[0] is False

    stamp = (tmp_path / "browser_budgets.json").stat().st_mtime
    assert ledger.check("x", budget, now=start + HOUR + 1)[0] is True
    assert (tmp_path / "browser_budgets.json").stat().st_mtime == stamp, (
        "a read rewrote the ledger"
    )


def test_a_budget_of_zero_means_unlimited_not_blocked(tmp_path):
    """Zero has to mean 'no ceiling', because the alternative reading is a
    default that silently stops every account that has not been configured."""
    ledger = BudgetLedger(tmp_path)
    for _ in range(500):
        ledger.record("x")
    assert ledger.check("x", Budget())[0] is True


def test_a_corrupt_ledger_refuses_rather_than_reading_as_empty(tmp_path):
    """An unreadable ledger that returns `{}` hands every account a full budget,
    which is the one failure mode that costs an account rather than a run."""
    (tmp_path / "browser_budgets.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(BudgetSpent, match="could not be read"):
        BudgetLedger(tmp_path).check("x", Budget(actions_per_hour=1))


def test_every_platform_default_is_a_real_ceiling(tmp_path):
    """A default of zero here would be an accidental opt-out of the feature."""
    for name, (hour, day) in DEFAULT_BUDGETS.items():
        assert hour > 0 and day > 0, name
        assert hour <= day, f"{name} allows more per hour than per day"
    assert DEFAULT_BUDGET[0] > 0 and DEFAULT_BUDGET[1] > 0


def test_an_undeclared_platform_gets_a_ceiling_and_not_a_free_pass(tmp_path):
    """The platform we understand least is the wrong one to leave unlimited."""
    assert Budget.for_platform("some-new-site").unlimited is False


def test_remaining_says_what_is_left_before_a_run_rather_than_after(tmp_path):
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=10, actions_per_day=40)
    now = 1_800_000_000.0
    for _ in range(3):
        ledger.record("linkedin:work", now=now)

    left = ledger.remaining("linkedin:work", budget, now=now)
    assert left["used_this_hour"] == 3 and left["used_today"] == 3
    assert left["left_this_hour"] == 7 and left["left_today"] == 37


def test_the_catalogue_carries_each_account_s_budget(tmp_path):
    """"What are this account's limits" is answered next to the account, not in
    a separate call a screen can forget to make."""
    store = ConnectionStore(tmp_path)
    ledger = BudgetLedger(tmp_path)
    store.record("local", Reading(state="connected", evidence="my network"),
                 platform("linkedin"), account="work")
    ledger.record("linkedin:work")

    rows = catalogue(store, "local", ledger)["platforms"]
    work = next(r for r in rows if r["account"] == "linkedin:work")
    assert work["budget"]["used_today"] == 1
    assert work["budget"]["budget"]["actions_per_day"] == DEFAULT_BUDGETS["linkedin"][1]
    # And the promise that survives every change to this file.
    assert catalogue(store, "local", ledger)["stores_no_credentials"] is True


def test_the_catalogue_still_works_with_no_ledger(tmp_path):
    rows = catalogue(ConnectionStore(tmp_path), "local")["platforms"]
    assert rows and all("budget" not in row for row in rows)


# ── AC3: observing is free ──────────────────────────────────────────────────


def test_looking_costs_nothing_and_acting_costs_one(tmp_path):
    """If `read` cost budget, an agent trying to be frugal would act without
    looking first — which is the behaviour that gets an account noticed."""
    assert set(COSTED_ACTIONS) <= set(ACTIONS)
    for observing in ("read", "screenshot", "wait_for"):
        assert observing in ACTIONS
        assert observing not in COSTED_ACTIONS
    for acting in ("goto", "click", "type", "select", "scroll", "press", "back"):
        assert acting in COSTED_ACTIONS, f"{acting} touches the site and must cost"


def test_every_costed_action_is_a_real_verb():
    """A typo here would silently make an action free."""
    for action in COSTED_ACTIONS:
        assert action in ACTIONS, f"{action} is not one of the ten verbs"


# ── against a real browser, end to end ──────────────────────────────────────


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


needs_browser = pytest.mark.skipif(
    not _browser(), reason="no Chrome, Edge, Brave or Chromium on this machine"
)

PAGE = "data:text/html,<button id=b>Go</button><p>hello</p>"


async def _drive(work, **page_kwargs):
    with tempfile.TemporaryDirectory() as profile:
        flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            _, session_id = await session.new_tab()
            page = Page(connection=session.connection, session_id=session_id, **page_kwargs)
            await page.start()
            return await work(page)
        finally:
            await session.close(quit_browser=True)


@needs_browser
def test_a_real_browser_stops_when_the_account_is_spent(tmp_path):
    """AC2 against a real Chromium. Two actions are allowed, the third is
    refused, and the refusal names the account and the wait."""
    ledger = BudgetLedger(tmp_path)

    async def work(page: Page):
        first = await page.goto(PAGE)
        assert first.ok is True
        second = await page.scroll(down=1)
        assert second.ok is True

        with pytest.raises(ActionRefused, match="can act again in"):
            await page.scroll(down=1)

        # Looking still works with the budget spent, which is the point of AC3.
        text = await page.read()
        assert "hello" in text.text
        shot = await page.screenshot()
        assert shot.screenshot[:8] == b"\x89PNG\r\n\x1a\n"
        return ledger.remaining("linkedin:work", Budget(actions_per_hour=2, actions_per_day=9))

    left = asyncio.run(_drive(
        work,
        ledger=ledger,
        account="linkedin:work",
        budget=Budget(actions_per_hour=2, actions_per_day=9),
    ))
    assert left["used_this_hour"] == 2, "looking was charged, or acting was not"


@needs_browser
def test_an_unattributed_tab_is_not_charged_to_anybody(tmp_path):
    """No account named means no account at risk, so nothing is spent — and
    every existing caller keeps working unchanged."""
    ledger = BudgetLedger(tmp_path)

    async def work(page: Page):
        for _ in range(6):
            await page.goto(PAGE)
        return True

    assert asyncio.run(_drive(work, ledger=ledger))
    assert not (tmp_path / "browser_budgets.json").exists()


@needs_browser
def test_a_refused_action_does_not_spend_the_budget(tmp_path):
    """The budget counts actions, not attempts. An action that raised on the
    way down never reached the site."""
    ledger = BudgetLedger(tmp_path)
    budget = Budget(actions_per_hour=50, actions_per_day=50)

    async def work(page: Page):
        await page.goto(PAGE)
        for _ in range(4):
            with pytest.raises(LookupError):
                await page.click(9999)
        return ledger.remaining("x:one", budget)

    left = asyncio.run(_drive(work, ledger=ledger, account="x:one", budget=budget))
    assert left["used_today"] == 1, "a refused click was charged"


def test_the_sign_in_path_can_actually_reach_a_second_account():
    """The store supporting accounts is not the feature — being able to *connect*
    one is. Without this, a second account is representable and unreachable."""
    import inspect

    from offsetx_apollo_builder.browser import signin

    for name in ("connect", "verify"):
        parameters = inspect.signature(getattr(signin, name)).parameters
        assert "account" in parameters, f"signin.{name} cannot reach a second account"
        assert parameters["account"].default == "", (
            f"signin.{name} must default to the platform's own account"
        )


def test_naming_an_account_still_cannot_carry_a_credential():
    """`account` is a label the owner chose. The guarantee that no function in
    this path accepts a secret has to survive every parameter added to it."""
    assert "account" not in identity.FORBIDDEN_FIELDS
    for forbidden in identity.FORBIDDEN_FIELDS:
        assert account_id("linkedin", forbidden) != forbidden
