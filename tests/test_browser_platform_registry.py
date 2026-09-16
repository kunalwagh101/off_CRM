"""S-03.02.05 — one platform row drives identity, policy and budget."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser.budget import Budget
from offsetx_apollo_builder.browser.identity import PLATFORMS, platform
from offsetx_apollo_builder.browser.policy import rule_for
from offsetx_apollo_builder.browser.registry import (
    PACKAGED_REGISTRY_PATH,
    SOURCE_REGISTRY_PATH,
    PlatformRegistryError,
    load_platforms,
)


def test_source_and_packaged_platform_registries_are_identical():
    assert SOURCE_REGISTRY_PATH.read_bytes() == PACKAGED_REGISTRY_PATH.read_bytes()


def test_reddit_is_a_data_row_beyond_the_original_six():
    assert len(PLATFORMS) >= 7
    reddit = platform("reddit")
    assert reddit.label == "Reddit"
    assert reddit.login_url == "https://www.reddit.com/login/"
    assert Budget.for_platform("reddit").to_dict() == {
        "actions_per_hour": 40,
        "actions_per_day": 200,
    }
    rule = rule_for("https://www.reddit.com/r/python/")
    assert rule.label == "Reddit"
    assert rule.min_seconds_between_actions == 3.0
    assert rule.unattended is False


def test_aliases_share_the_declared_platform_policy_and_budget():
    assert platform("twitter").id == "x"
    assert Budget.for_platform("twitter") == Budget.for_platform("x")
    assert rule_for("https://twitter.com/home").label == "X"


def _custom_registry(path: Path) -> None:
    path.write_text(
        """platforms:
  - id: forum
    label: Example Forum
    login_url: https://forum.example/login
    home_url: https://forum.example/home
    signed_in: [member home]
    signed_out: [sign in]
    domains:
      - suffix: forum.example
        min_seconds_between_actions: 2.5
        unattended: false
        confirm: [send, submit]
    budget:
      actions_per_hour: 7
      actions_per_day: 21
""",
        encoding="utf-8",
    )


def test_a_new_registry_row_drives_signin_state_policy_and_budget_without_code_change(tmp_path):
    registry = tmp_path / "platforms.yaml"
    _custom_registry(registry)
    script = r'''
import asyncio
from offsetx_apollo_builder.browser.budget import Budget
from offsetx_apollo_builder.browser.identity import platform
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.policy import rule_for
from offsetx_apollo_builder.browser.signin import check

class Page:
    def __init__(self):
        self.url = ""
    async def goto(self, url):
        self.url = url
    async def snapshot(self):
        return Snapshot(url=self.url, nodes=[Node(handle=1, role="button", name="Member Home")])

target = platform("forum")
assert target.label == "Example Forum"
reading = asyncio.run(check(Page(), "forum"))
assert reading.state == "connected"
assert reading.url == "https://forum.example/home"
assert Budget.for_platform("forum").actions_per_hour == 7
assert Budget.for_platform("forum").actions_per_day == 21
rule = rule_for("https://sub.forum.example/thread/1")
assert rule.label == "Example Forum"
assert rule.min_seconds_between_actions == 2.5
assert rule.unattended is False
'''
    env = os.environ.copy()
    env["OFFSETX_PLATFORM_REGISTRY"] = str(registry)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_missing_required_field_is_refused_by_platform_name_at_load_time(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """platforms:
  - id: forum
    label: Example Forum
    login_url: https://forum.example/login
    home_url: https://forum.example/home
    signed_in: [member home]
    domains:
      - suffix: forum.example
        min_seconds_between_actions: 2.5
        unattended: false
    budget:
      actions_per_hour: 7
      actions_per_day: 21
""",
        encoding="utf-8",
    )
    load_platforms.cache_clear()
    with pytest.raises(PlatformRegistryError, match=r"forum.*signed_out"):
        load_platforms(path)


def test_duplicate_domain_is_refused_at_load_time(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text(
        """platforms:
  - id: one
    label: One
    login_url: https://one.example/login
    home_url: https://one.example/home
    signed_in: [home]
    signed_out: [sign in]
    domains:
      - suffix: shared.example
        min_seconds_between_actions: 1
        unattended: true
    budget: {actions_per_hour: 1, actions_per_day: 2}
  - id: two
    label: Two
    login_url: https://two.example/login
    home_url: https://two.example/home
    signed_in: [home]
    signed_out: [sign in]
    domains:
      - suffix: shared.example
        min_seconds_between_actions: 1
        unattended: true
    budget: {actions_per_hour: 1, actions_per_day: 2}
""",
        encoding="utf-8",
    )
    load_platforms.cache_clear()
    with pytest.raises(PlatformRegistryError, match=r"two.*shared\.example.*one"):
        load_platforms(path)


def test_sign_in_and_sign_out_signals_cannot_overlap(tmp_path):
    path = tmp_path / "overlap.yaml"
    path.write_text(
        """platforms:
  - id: forum
    label: Forum
    login_url: https://forum.example/login
    home_url: https://forum.example/home
    signed_in: [Account Menu]
    signed_out: [account menu]
    domains:
      - suffix: forum.example
        min_seconds_between_actions: 1
        unattended: true
    budget: {actions_per_hour: 1, actions_per_day: 2}
""",
        encoding="utf-8",
    )
    load_platforms.cache_clear()
    with pytest.raises(PlatformRegistryError, match=r"forum.*same sign-in and sign-out"):
        load_platforms(path)
