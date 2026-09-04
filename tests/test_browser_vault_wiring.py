"""Trusted sign-in wiring for S-03.02.02."""
from __future__ import annotations

import asyncio

import pytest

from offsetx_apollo_builder.browser import signin
from offsetx_apollo_builder.browser.identity import ConnectionStore, Platform, Reading
from offsetx_apollo_builder.browser.vault import VaultError, VaultMetadata

TARGET = Platform(
    id="linkedin",
    label="LinkedIn",
    login_url="https://www.linkedin.com/login",
    home_url="https://www.linkedin.com/feed/",
    signed_in=("my network",),
    signed_out=("sign in",),
)


class DummyPage:
    pass


class RecordingVault:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def capture(self, page, target, workspace_id):
        self.calls.append((page, target.id, workspace_id))
        if self.fail:
            raise VaultError("simulated vault failure")
        return VaultMetadata(workspace_id, target.id, "key-1", "test", 1)


def test_connected_state_is_vaulted_before_it_is_recorded(tmp_path, monkeypatch):
    page = DummyPage()
    vault = RecordingVault()
    store = ConnectionStore(tmp_path)

    async def already_connected(_page, _target):
        return Reading("connected", "signed-in marker")

    monkeypatch.setattr(signin, "open_login", already_connected)
    connection = asyncio.run(
        signin.connect(page, TARGET, store, "local", vault=vault)
    )

    assert connection.state == "connected"
    assert vault.calls == [(page, "linkedin", "local")]
    assert store.get("local", "linkedin").state == "connected"


def test_vault_failure_refuses_the_connection_and_writes_no_green_state(tmp_path, monkeypatch):
    page = DummyPage()
    vault = RecordingVault(fail=True)
    store = ConnectionStore(tmp_path)

    async def already_connected(_page, _target):
        return Reading("connected", "signed-in marker")

    monkeypatch.setattr(signin, "open_login", already_connected)
    with pytest.raises(signin.SignInRefused, match="could not protect"):
        asyncio.run(signin.connect(page, TARGET, store, "local", vault=vault))

    assert store.get("local", "linkedin").state == "unknown"


def test_vault_is_a_required_keyword_and_not_an_optional_security_bypass():
    import inspect

    parameter = inspect.signature(signin.connect).parameters["vault"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
