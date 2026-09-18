from __future__ import annotations

from offsetx_apollo_builder.browser.identity import ConnectionStore, Reading, platform
from offsetx_apollo_builder.browser.vault import SessionVault


def test_browser_connection_and_vault_state_do_not_cross_workspaces(tmp_path, monkeypatch) -> None:
    from offsetx_apollo_builder.browser import vault as vault_module

    linkedin = platform("linkedin")
    store = ConnectionStore(tmp_path)
    store.record("alpha", Reading("connected", "signed-in marker"), linkedin)

    assert store.get("alpha", "linkedin").state == "connected"
    assert store.get("beta", "linkedin").state == "unknown"

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    vault = SessionVault(tmp_path / "vault", passphrase="workspace-passphrase-value")

    vault.seal(
        "alpha",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "A" * 24, "domain": ".linkedin.com"}]},
    )
    vault.seal(
        "beta",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "B" * 24, "domain": ".linkedin.com"}]},
    )

    assert vault.unseal("alpha", "linkedin")["cookies"][0]["value"] == "A" * 24
    assert vault.unseal("beta", "linkedin")["cookies"][0]["value"] == "B" * 24
    assert vault.inspect("alpha", "linkedin").key_id != vault.inspect("beta", "linkedin").key_id
