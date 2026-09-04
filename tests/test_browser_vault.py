"""S-03.02.02 — browser session material is encrypted and never model-visible."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.scanner import scan_payload
from offsetx_apollo_builder.ai.tiers import DataPolicy
from offsetx_apollo_builder.browser.identity import platform
from offsetx_apollo_builder.browser.vault import SessionVault, VaultError, VaultLocked

PASSPHRASE = "test-only-passphrase-longer-than-twelve"


@pytest.fixture
def passphrase_vault(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    return SessionVault(tmp_path, passphrase=PASSPHRASE)


def test_cookie_token_and_password_fields_are_blocked_even_at_full_policy():
    for field, value in (
        ("cookie", "li_at=AQED-not-real"),
        ("access_token", "opaque-token-not-real"),
        ("password", "not-a-real-password"),
    ):
        report = scan_payload(
            {"unrestricted": {field: value}},
            policy=DataPolicy.FULL,
            allow_addresses=True,
        )
        assert not report.clean, field
        assert any(item.kind == "credential" for item in report.findings), field


def test_credential_assignments_in_free_text_are_blocked_at_full_policy():
    for text in (
        "Cookie: li_at=AQED-not-real",
        "password=not-a-real-password",
        "refresh_token=opaque-token-not-real",
    ):
        report = scan_payload(
            {"unrestricted": {"notes": text}},
            policy=DataPolicy.FULL,
            allow_addresses=True,
        )
        assert not report.clean, text
        assert any(item.kind == "credential" for item in report.findings), text


def test_two_platforms_use_different_account_keys_and_plaintext_is_absent(passphrase_vault):
    linkedin = passphrase_vault.seal(
        "local", "linkedin",
        {"cookies": [{"name": "li_at", "value": "LINKEDIN-SECRET", "domain": ".linkedin.com"}]},
    )
    instagram = passphrase_vault.seal(
        "local", "instagram",
        {"cookies": [{"name": "sessionid", "value": "INSTAGRAM-SECRET", "domain": ".instagram.com"}]},
    )

    assert linkedin.key_id != instagram.key_id
    assert linkedin.key_source == instagram.key_source == "passphrase-scrypt"

    stored = b"".join(
        path.read_bytes()
        for path in passphrase_vault.directory.rglob("*")
        if path.is_file()
    )
    assert b"LINKEDIN-SECRET" not in stored
    assert b"INSTAGRAM-SECRET" not in stored
    assert passphrase_vault.unseal("local", "linkedin")["cookies"][0]["value"] == "LINKEDIN-SECRET"
    assert passphrase_vault.unseal("local", "instagram")["cookies"][0]["value"] == "INSTAGRAM-SECRET"


def test_resealing_one_account_reuses_its_key_but_not_another_accounts(passphrase_vault):
    first = passphrase_vault.seal(
        "local", "linkedin", {"cookies": [{"name": "a", "value": "1", "domain": ".linkedin.com"}]}
    )
    second = passphrase_vault.seal(
        "local", "linkedin", {"cookies": [{"name": "a", "value": "2", "domain": ".linkedin.com"}]}
    )
    other = passphrase_vault.seal(
        "local", "instagram", {"cookies": [{"name": "b", "value": "3", "domain": ".instagram.com"}]}
    )
    assert first.key_id == second.key_id
    assert first.key_id != other.key_id


def test_passphrase_derives_master_key_and_no_raw_key_file_is_written(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    vault = SessionVault(tmp_path, passphrase=PASSPHRASE)
    vault.seal(
        "local", "linkedin", {"cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com"}]}
    )

    assert vault.inspect("local", "linkedin").key_source == "passphrase-scrypt"
    assert not list(Path(tmp_path).rglob("*.key"))
    metadata = (vault.directory / "metadata.json").read_text(encoding="utf-8")
    assert "passphrase_salt" in metadata
    assert PASSPHRASE not in metadata

    wrong = SessionVault(tmp_path, passphrase="different-passphrase-long-enough")
    with pytest.raises(VaultLocked, match="account key"):
        wrong.unseal("local", "linkedin")


def test_vault_refuses_to_weaken_when_keychain_and_passphrase_are_absent(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    with pytest.raises(VaultLocked, match="No OS credential store"):
        SessionVault(tmp_path)


def test_vault_refuses_path_traversal_and_non_session_material(passphrase_vault):
    with pytest.raises(VaultError, match="workspace id"):
        passphrase_vault.seal("../other", "linkedin", {"cookies": []})
    with pytest.raises(VaultError, match="only a cookies list"):
        passphrase_vault.seal("local", "linkedin", {"token": "secret"})


def test_lock_drops_the_process_reference_to_master_material(passphrase_vault):
    passphrase_vault.seal(
        "local", "linkedin", {"cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com"}]}
    )
    passphrase_vault.lock()
    with pytest.raises(VaultLocked, match="locked in this process"):
        passphrase_vault.unseal("local", "linkedin")


class FakeConnection:
    def __init__(self, cookies):
        self.cookies = cookies
        self.calls = []

    async def send(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if method == "Storage.getCookies":
            return {"cookies": self.cookies}
        if method == "Storage.setCookies":
            return {}
        raise AssertionError(f"unexpected CDP method {method}")


class FakePage:
    def __init__(self, cookies):
        self.connection = FakeConnection(cookies)


def test_capture_keeps_only_target_platform_and_returns_metadata_only(passphrase_vault):
    page = FakePage([
        {
            "name": "li_at", "value": "LINKEDIN-SECRET", "domain": ".linkedin.com",
            "path": "/", "secure": True, "httpOnly": True, "size": 999,
        },
        {"name": "other", "value": "OTHER-SECRET", "domain": ".example.com", "path": "/"},
    ])

    result = asyncio.run(passphrase_vault.capture(page, platform("linkedin"), "local"))

    assert result.cookie_count == 1
    assert "SECRET" not in str(result.to_dict())
    opened = passphrase_vault.unseal("local", "linkedin")
    assert opened["cookies"][0]["value"] == "LINKEDIN-SECRET"
    assert opened["cookies"][0]["domain"] == ".linkedin.com"
    assert "size" not in opened["cookies"][0]
    assert "OTHER-SECRET" not in str(opened)


def test_restore_moves_plaintext_only_from_vault_to_chrome(passphrase_vault):
    passphrase_vault.seal(
        "local", "linkedin",
        {"cookies": [{
            "name": "li_at", "value": "LINKEDIN-SECRET", "domain": ".linkedin.com",
            "path": "/", "secure": True, "httpOnly": True,
        }]},
    )
    page = FakePage([])

    result = asyncio.run(passphrase_vault.restore(page, platform("linkedin"), "local"))

    assert result.cookie_count == 1
    method, params = page.connection.calls[-1]
    assert method == "Storage.setCookies"
    assert params["cookies"][0]["value"] == "LINKEDIN-SECRET"
    assert "SECRET" not in str(result.to_dict())


def test_capture_refuses_an_empty_session_instead_of_claiming_success(passphrase_vault):
    page = FakePage([{"name": "other", "value": "x", "domain": ".example.com"}])
    with pytest.raises(VaultError, match="no session cookies"):
        asyncio.run(passphrase_vault.capture(page, platform("linkedin"), "local"))


def test_corrupt_ciphertext_fails_closed(passphrase_vault):
    passphrase_vault.seal(
        "local", "linkedin", {"cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com"}]}
    )
    path = passphrase_vault._path("local", "linkedin")
    text = path.read_text(encoding="utf-8").replace('"ciphertext": "', '"ciphertext": "tampered-')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(VaultLocked, match="authenticated decryption"):
        passphrase_vault.unseal("local", "linkedin")
