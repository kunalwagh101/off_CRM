"""S-03.02.03 — disconnect destroys the session and records the act."""
from __future__ import annotations

import asyncio
import os
import time

import pytest

from offsetx_apollo_builder.browser.identity import (
    ConnectionStore,
    Platform,
    Reading,
    platform,
)
from offsetx_apollo_builder.browser.revoke import RevokeError, disconnect
from offsetx_apollo_builder.browser.session import (
    BrowserUnavailable,
    find_browser,
    free_port,
    open_session,
)
from offsetx_apollo_builder.browser.trace import Trace
from offsetx_apollo_builder.browser.vault import SessionVault, VaultLocked

PASSPHRASE = "test-only-passphrase-longer-than-twelve"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    return SessionVault(tmp_path, passphrase=PASSPHRASE)


class Connection:
    def __init__(self, *, fail_on: str = ""):
        self.calls = []
        self.fail_on = fail_on

    async def send(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if method == self.fail_on:
            raise RuntimeError("simulated DevTools refusal")
        if method in {"Storage.deleteCookies", "Storage.clearDataForOrigin"}:
            return {}
        raise AssertionError(f"unexpected CDP method {method}")


class Page:
    def __init__(self, *, fail_on: str = ""):
        self.connection = Connection(fail_on=fail_on)


def _connected(store, workspace_id="local"):
    store.record(
        workspace_id,
        Reading("connected", "signed-in marker"),
        platform("linkedin"),
    )


def _seed(vault):
    return vault.seal(
        "local",
        "linkedin",
        {
            "cookies": [
                {
                    "name": "li_at",
                    "value": "LINKEDIN-SECRET",
                    "domain": ".linkedin.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                }
            ]
        },
    )


def test_disconnect_destroys_vault_clears_browser_forgets_record_and_traces(tmp_path, vault):
    store = ConnectionStore(tmp_path)
    _connected(store)
    _seed(vault)
    page = Page()
    trace = Trace.open(tmp_path / "traces", run_id="revoke-success")

    result = asyncio.run(
        disconnect(page, "linkedin", store, vault, trace, "local")
    )

    assert result.platform_id == "linkedin"
    assert result.cookies_removed == 1
    assert result.vault_destroyed is True
    assert store.get("local", "linkedin").state == "unknown"
    with pytest.raises(VaultLocked, match="No vaulted session exists"):
        vault.unseal("local", "linkedin")

    methods = [method for method, _ in page.connection.calls]
    assert methods.count("Storage.deleteCookies") == 1
    assert methods.count("Storage.clearDataForOrigin") == 1
    deleted = next(params for method, params in page.connection.calls if method == "Storage.deleteCookies")
    assert deleted == {"name": "li_at", "domain": ".linkedin.com", "path": "/"}

    rows = [step.to_dict() for step in trace.read()]
    assert rows[-1]["kind"] == "revoke"
    assert rows[-1]["ok"] is True
    assert "vault envelope destroyed" in rows[-1]["detail"]
    assert "LINKEDIN-SECRET" not in trace.path.read_text(encoding="utf-8")


def test_browser_failure_retains_encrypted_vault_and_connected_record_for_retry(tmp_path, vault):
    store = ConnectionStore(tmp_path)
    _connected(store)
    _seed(vault)
    page = Page(fail_on="Storage.deleteCookies")
    trace = Trace.open(tmp_path / "traces", run_id="revoke-failure")

    with pytest.raises(RevokeError, match="encrypted vault was retained"):
        asyncio.run(disconnect(page, "linkedin", store, vault, trace, "local"))

    assert store.get("local", "linkedin").state == "connected"
    assert vault.unseal("local", "linkedin")["cookies"][0]["value"] == "LINKEDIN-SECRET"
    assert trace.steps[-1].ok is False
    assert "retained for retry" in trace.steps[-1].detail
    assert "LINKEDIN-SECRET" not in trace.path.read_text(encoding="utf-8")


def test_disconnect_refuses_cross_platform_material_before_deleting_anything(tmp_path, vault):
    store = ConnectionStore(tmp_path)
    _connected(store)
    vault.seal(
        "local",
        "linkedin",
        {"cookies": [{"name": "sessionid", "value": "SECRET", "domain": ".instagram.com"}]},
    )
    page = Page()
    trace = Trace.open(tmp_path / "traces", run_id="revoke-wrong-platform")

    with pytest.raises(RevokeError, match="another platform"):
        asyncio.run(disconnect(page, "linkedin", store, vault, trace, "local"))

    assert page.connection.calls == []
    assert store.get("local", "linkedin").state == "connected"
    assert vault.inspect("local", "linkedin").platform_id == "linkedin"
    assert trace.steps == []


def test_disconnect_refuses_when_no_vaulted_session_exists(tmp_path, vault):
    store = ConnectionStore(tmp_path)
    _connected(store)
    page = Page()
    trace = Trace.open(tmp_path / "traces", run_id="revoke-missing")

    with pytest.raises(RevokeError, match="cannot be opened safely"):
        asyncio.run(disconnect(page, "linkedin", store, vault, trace, "local"))

    assert page.connection.calls == []
    assert store.get("local", "linkedin").state == "connected"
    assert trace.steps == []


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


needs_browser = pytest.mark.skipif(
    not _browser(), reason="no Chrome, Edge, Brave or Chromium on this machine"
)

LIVE_TARGET = Platform(
    id="linkedin",
    label="Test platform",
    login_url="https://persistence.test/login",
    home_url="https://persistence.test/",
    signed_in=("signed in",),
    signed_out=("sign in",),
)


@needs_browser
def test_real_browser_session_cookie_is_gone_after_disconnect(tmp_path, vault):
    """Gate 2: ask Chromium itself whether a revoked login survived."""
    profile = str(tmp_path / "profile")
    os.makedirs(profile, exist_ok=True)
    flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
    store = ConnectionStore(tmp_path)
    store.record("local", Reading("connected", "test login"), LIVE_TARGET)
    trace = Trace.open(tmp_path / "traces", run_id="revoke-live")
    secret = "live-browser-session-secret"
    cookie = {
        "name": "session_token",
        "value": secret,
        "domain": "persistence.test",
        "path": "/",
        "expires": time.time() + 86_400,
        "secure": True,
    }
    vault.seal("local", LIVE_TARGET.id, {"cookies": [cookie]})

    async def work():
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            await session.connection.send("Storage.setCookies", {"cookies": [cookie]})
            before = await session.connection.send("Storage.getCookies", {})
            assert any(
                item.get("name") == "session_token" and item.get("value") == secret
                for item in before.get("cookies", [])
            ), "the test never planted the session, so revocation would prove nothing"

            page = type("BrowserPage", (), {"connection": session.connection})()
            result = await disconnect(page, LIVE_TARGET, store, vault, trace, "local")
            after = await session.connection.send("Storage.getCookies", {})
            return result, after
        finally:
            await session.close(quit_browser=True)

    result, after = asyncio.run(work())

    assert result.vault_destroyed is True
    assert not any(
        item.get("name") == "session_token" and item.get("domain") == "persistence.test"
        for item in after.get("cookies", [])
    ), "Chromium still has the revoked session cookie"
    with pytest.raises(VaultLocked, match="No vaulted session exists"):
        vault.unseal("local", LIVE_TARGET.id)
    assert store.get("local", LIVE_TARGET.id).state == "unknown"
    assert trace.steps[-1].ok is True
    assert secret not in trace.path.read_text(encoding="utf-8")
