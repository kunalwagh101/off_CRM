from __future__ import annotations

import inspect

import pytest

from offsetx_apollo_builder.browser import identity, policy
from offsetx_apollo_builder.browser.budget import Budget
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.platforms import (
    PlatformRegistry,
    PlatformRegistryError,
    default_registry,
)


def _row(**overrides):
    row = {
        "id": "example",
        "aliases": [],
        "label": "Example",
        "login_url": "https://example.com/login",
        "home_url": "https://example.com/",
        "signed_in": ["account menu"],
        "signed_out": ["log in"],
        "domains": ["example.com"],
        "policy": {
            "min_seconds_between_actions": 2.0,
            "unattended": False,
            "refuse": [],
            "confirm": ["send"],
            "note": "",
        },
        "budget": {"actions_per_hour": 10, "actions_per_day": 40},
        "note": "",
    }
    row.update(overrides)
    return row


def test_reddit_was_added_as_one_registry_row_not_a_python_branch():
    target = identity.platform("reddit")
    assert target.label == "Reddit"
    assert target.login_url.endswith("/login/")
    assert Budget.for_platform("reddit").actions_per_hour == 40

    rule = policy.rule_for("https://old.reddit.com/r/python")
    assert rule.label == "Reddit"
    assert rule.min_seconds_between_actions == 4.0
    assert rule.unattended is False

    signed_in = identity.read_state(
        Snapshot(
            url=target.home_url,
            nodes=[Node(1, "button", "Create post")],
        ),
        target,
    )
    assert signed_in.state == "connected"


def test_registry_aliases_drive_the_same_platform_without_duplicate_code():
    target = default_registry().get("twitter")
    assert target.id == "x"
    assert default_registry().get("x") is target
    assert Budget.for_platform("twitter").to_dict() == Budget.for_platform("x").to_dict()
    assert policy.rule_for("https://mobile.twitter.com/home").label == "X"


@pytest.mark.parametrize(
    "row, message",
    [
        ({**_row(), "budget": {}}, "actions_per_hour"),
        ({**_row(), "domains": []}, "domains"),
        ({**_row(), "signed_in": []}, "signed_in"),
        ({**_row(), "login_url": "http://example.com/login"}, "https"),
        (
            {
                **_row(),
                "policy": {
                    **_row()["policy"],
                    "unattended": "false",
                },
            },
            "unattended",
        ),
    ],
)
def test_missing_or_unsafe_required_platform_fields_fail_at_load_time(row, message):
    with pytest.raises(PlatformRegistryError, match=message):
        PlatformRegistry.from_data({"version": 1, "platforms": [row]})


def test_duplicate_domain_or_alias_fails_the_whole_registry():
    other = _row(
        id="other",
        aliases=["example"],
        domains=["other.example.com"],
        login_url="https://other.example.com/login",
        home_url="https://other.example.com/",
    )
    with pytest.raises(PlatformRegistryError, match="alias"):
        PlatformRegistry.from_data({"version": 1, "platforms": [_row(), other]})


def test_signin_connection_and_budget_code_contains_no_reddit_specific_branch():
    for module in (identity, policy):
        source = inspect.getsource(module).lower()
        assert '"reddit"' not in source
        assert "'reddit'" not in source
    source = inspect.getsource(Budget.for_platform).lower()
    assert "reddit" not in source
