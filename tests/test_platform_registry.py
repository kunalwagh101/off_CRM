"""Declarative platform coverage.  `S-03.02.05`

The important test is not that Reddit exists. It is that a row the Python code
has never heard of acquires sign-in observation, connection state, account
budget and browser policy in one clean process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser import policy
from offsetx_apollo_builder.browser.budget import Budget, DEFAULT_BUDGETS, BudgetLedger
from offsetx_apollo_builder.browser.identity import ConnectionStore, PLATFORMS, platform, read_state
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.platform_registry import (
    DEFAULT_REGISTRY_PATH,
    PlatformRegistryError,
    load_registry,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def test_the_packaged_registry_is_the_source_for_identity_budget_and_policy(tmp_path):
    assert DEFAULT_REGISTRY_PATH.is_file()
    assert {"linkedin", "instagram", "facebook", "youtube", "x", "tiktok", "reddit"} <= set(PLATFORMS)

    reddit = platform("reddit")
    connected = Snapshot(nodes=[Node(handle=1, role="button", name="Create post")])
    assert read_state(connected, reddit).state == "connected"

    store = ConnectionStore(tmp_path)
    store.record("local", read_state(connected, reddit), reddit)
    assert store.get("local", "reddit").state == "connected"

    budget = Budget.for_platform("reddit")
    assert (budget.actions_per_hour, budget.actions_per_day) == DEFAULT_BUDGETS["reddit"]
    assert budget.actions_per_hour > 0

    rule = policy.rule_for("https://www.reddit.com/")
    assert rule.label == "Reddit"
    assert rule.min_seconds_between_actions == 4.0
    assert rule.unattended is False
    with pytest.raises(policy.Refused, match="attended-only"):
        policy.check_navigation("https://www.reddit.com/", unattended=True)


def test_an_alias_uses_the_same_declared_platform_and_budget():
    assert platform("twitter") is platform("x")
    assert Budget.for_platform("twitter") == Budget.for_platform("x")


def test_a_new_row_gets_the_whole_vertical_slice_without_a_code_change(tmp_path):
    registry = _write(
        tmp_path / "platforms.yaml",
        """
        version: 1
        platforms:
          - id: mastodon
            label: Mastodon Test
            login_url: https://social.example/login
            home_url: https://social.example/home
            signed_in: [new post]
            signed_out: [sign in]
            budget:
              actions_per_hour: 7
              actions_per_day: 21
            domains:
              - suffix: social.example
                min_seconds_between_actions: 3.5
                unattended: false
                confirm: [send, submit, publish]
        """,
    )
    data = tmp_path / "data"
    data.mkdir()

    program = r'''
from pathlib import Path
from offsetx_apollo_builder.browser import policy
from offsetx_apollo_builder.browser.budget import Budget, BudgetLedger
from offsetx_apollo_builder.browser.identity import ConnectionStore, read_state, platform
from offsetx_apollo_builder.browser.perceive import Node, Snapshot

import os

target = platform("mastodon")
snapshot = Snapshot(nodes=[Node(handle=1, role="button", name="New post")])
reading = read_state(snapshot, target)
assert reading.state == "connected"

store = ConnectionStore(Path(os.environ["S030205_DATA"]))
store.record("workspace", reading, target)
assert store.get("workspace", "mastodon").state == "connected"

budget = Budget.for_platform("mastodon")
assert (budget.actions_per_hour, budget.actions_per_day) == (7, 21)
ledger = BudgetLedger(Path(os.environ["S030205_DATA"]))
for _ in range(7):
    ledger.record("mastodon")
assert ledger.check("mastodon", budget)[0] is False

rule = policy.rule_for("https://social.example/home")
assert rule.label == "Mastodon Test"
assert rule.min_seconds_between_actions == 3.5
assert rule.unattended is False
try:
    policy.check_navigation("https://social.example/home", unattended=True)
except policy.Refused as exc:
    assert "attended-only" in str(exc)
else:
    raise AssertionError("declared unattended=false did not refuse")
print("mastodon declaration powers identity + connection + budget + policy")
'''
    env = dict(os.environ)
    env["OFF_CRM_PLATFORM_REGISTRY"] = str(registry)
    env["S030205_DATA"] = str(data)
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "identity + connection + budget + policy" in result.stdout


def test_a_missing_required_field_is_refused_at_load_time_by_platform_name(tmp_path):
    bad = _write(
        tmp_path / "bad.yaml",
        """
        version: 1
        platforms:
          - id: broken
            login_url: https://broken.example/login
            home_url: https://broken.example/
            signed_in: [home]
            signed_out: [sign in]
            budget: {actions_per_hour: 1, actions_per_day: 2}
            domains:
              - suffix: broken.example
                min_seconds_between_actions: 1
                unattended: false
        """,
    )
    with pytest.raises(PlatformRegistryError, match=r"broken.*label"):
        load_registry(bad)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
            version: 1
            platforms:
              - id: badurl
                label: Bad URL
                login_url: http://bad.example/login
                home_url: https://bad.example/
                signed_in: [home]
                signed_out: [sign in]
                budget: {actions_per_hour: 1, actions_per_day: 2}
                domains:
                  - suffix: bad.example
                    min_seconds_between_actions: 1
                    unattended: false
            """,
            "https",
        ),
        (
            """
            version: 1
            platforms:
              - id: one
                label: One
                login_url: https://same.example/login
                home_url: https://same.example/
                signed_in: [home]
                signed_out: [sign in]
                budget: {actions_per_hour: 1, actions_per_day: 2}
                domains:
                  - suffix: same.example
                    min_seconds_between_actions: 1
                    unattended: false
              - id: two
                label: Two
                login_url: https://same.example/login2
                home_url: https://same.example/two
                signed_in: [dashboard]
                signed_out: [log in]
                budget: {actions_per_hour: 1, actions_per_day: 2}
                domains:
                  - suffix: same.example
                    min_seconds_between_actions: 1
                    unattended: false
            """,
            "same.example",
        ),
        (
            """
            version: 1
            platforms:
              - id: inverted
                label: Inverted
                login_url: https://inverted.example/login
                home_url: https://inverted.example/
                signed_in: [home]
                signed_out: [sign in]
                budget: {actions_per_hour: 20, actions_per_day: 10}
                domains:
                  - suffix: inverted.example
                    min_seconds_between_actions: 1
                    unattended: false
            """,
            "hourly",
        ),
    ],
)
def test_bad_registry_rows_fail_closed_before_a_run(tmp_path, body, message):
    with pytest.raises(PlatformRegistryError, match=message):
        load_registry(_write(tmp_path / "bad.yaml", body))


def test_connection_catalogue_and_budget_ledger_need_no_platform_specific_branch(tmp_path):
    from offsetx_apollo_builder.browser.identity import catalogue

    store = ConnectionStore(tmp_path)
    ledger = BudgetLedger(tmp_path)
    rows = catalogue(store, "workspace", ledger)["platforms"]
    reddit = next(row for row in rows if row["id"] == "reddit")
    assert reddit["state"] == "unknown"
    assert reddit["budget"]["budget"]["actions_per_hour"] == 40
