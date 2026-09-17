"""Packaging and safety contract for the declarative platform registry."""
from __future__ import annotations

from pathlib import Path

import tomllib

from offsetx_apollo_builder.browser import policy
from offsetx_apollo_builder.browser.platform_registry import DEFAULT_REGISTRY_PATH


ROOT = Path(__file__).resolve().parents[1]


def test_platform_registry_is_declared_as_package_data():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]
    assert "platforms.yaml" in package_data["offsetx_apollo_builder.browser"]
    assert DEFAULT_REGISTRY_PATH.is_file()


def test_registry_rules_cannot_replace_generic_network_refusals():
    # These checks happen before rule lookup. A future registry row cannot make
    # local/network infrastructure reachable by declaring a matching suffix.
    for url in (
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/",
        "https://service.internal/",
    ):
        try:
            policy.check_navigation(url)
        except policy.Refused:
            pass
        else:
            raise AssertionError(f"generic network guard was weakened for {url}")


def test_gmail_remains_a_separate_attended_crm_boundary():
    rule = policy.rule_for("https://mail.google.com/mail/u/0/")
    assert rule.label == "Gmail"
    assert rule.unattended is False
    assert "send" in rule.confirm
