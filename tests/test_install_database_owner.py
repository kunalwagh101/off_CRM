"""A logical installation owns one hosted database across concurrent starts."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.db.hosted import HostedStorage


def test_independent_install_cannot_take_over_a_database(tmp_path):
    key = Fernet.generate_key().decode()
    target = str(tmp_path / "shared.db")
    first = HostedStorage(target, key)
    try:
        first.claim_install(str(uuid.UUID(int=1)))
        first.write("customer-state", "must remain")
    finally:
        first.close()
    same = HostedStorage(target, key)
    other = HostedStorage(target, key)
    try:
        same.claim_install(str(uuid.UUID(int=1)))
        with pytest.raises(ValueError, match="another install"):
            other.claim_install(str(uuid.UUID(int=2)))
        assert same.read("customer-state") == "must remain"
        assert same.read("install.identity.v1") == str(uuid.UUID(int=1))
    finally:
        same.close()
        other.close()


@pytest.mark.parametrize("identity", ["", "not-a-uuid", "0" * 1000])
def test_invalid_identity_never_claims_a_database(tmp_path, identity):
    store = HostedStorage(str(tmp_path / "hosted.db"), Fernet.generate_key().decode())
    try:
        with pytest.raises(ValueError, match="OFFSETX_INSTALL_ID"):
            store.claim_install(identity)
        assert store.read("install.identity.v1") is None
    finally:
        store.close()


def test_two_independent_install_claims_have_exactly_one_winner(tmp_path):
    key = Fernet.generate_key().decode()
    target = str(tmp_path / "shared.db")
    stores = [HostedStorage(target, key) for _ in range(2)]
    # Complete initial schema setup first so the race tests ownership, not DDL.
    stores[0].probe()

    def claim(index):
        try:
            stores[index].claim_install(str(uuid.UUID(int=index + 1)))
            return "claimed"
        except ValueError:
            return "refused"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(claim, range(2))) == ["claimed", "refused"]
    finally:
        for store in stores:
            store.close()


def test_actual_app_refuses_a_second_install_with_the_same_database(
    tmp_path, monkeypatch
):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(tmp_path / "hosted.db"))
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)

    def settings(root):
        return AppSettings(
            project_root=Path.cwd(),
            database_path=root / "crm.db",
            data_dir=root,
            export_dir=root / "exports",
            frontend_dist=tmp_path / "missing",
            api_token="install-owner-" + "x" * 40,
            secrets_key=key,
            allowed_hosts=("testserver",),
        )

    monkeypatch.setenv("OFFSETX_INSTALL_ID", str(uuid.UUID(int=1)))
    with TestClient(create_app(settings(tmp_path / "first-install"))) as client:
        assert client.get("/health/ready").status_code == 200
    monkeypatch.setenv("OFFSETX_INSTALL_ID", str(uuid.UUID(int=2)))
    with pytest.raises(ValueError, match="another install"):
        create_app(settings(tmp_path / "second-install"))


def test_real_postgres_reconnect_preserves_install_owner(isolated_postgres_target):
    key = Fernet.generate_key().decode()
    first = HostedStorage(isolated_postgres_target, key)
    try:
        first.claim_install(str(uuid.UUID(int=1)))
    finally:
        first.close()
    second = HostedStorage(isolated_postgres_target, key)
    try:
        second.claim_install(str(uuid.UUID(int=1)))
        with pytest.raises(ValueError, match="another install"):
            second.claim_install(str(uuid.UUID(int=2)))
        assert second.read("install.identity.v1") == str(uuid.UUID(int=1))
    finally:
        second.close()


def test_actual_hosted_app_requires_explicit_install_identity(tmp_path, monkeypatch):
    from pathlib import Path
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(tmp_path / "hosted.db"))
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    monkeypatch.delenv("OFFSETX_INSTALL_ID", raising=False)
    root = tmp_path / "unbound"
    with pytest.raises(ValueError, match="OFFSETX_INSTALL_ID"):
        create_app(
            AppSettings(
                project_root=Path.cwd(),
                database_path=root / "crm.db",
                data_dir=root,
                export_dir=root / "exports",
                frontend_dist=tmp_path / "missing",
                api_token="install-owner-" + "x" * 40,
                secrets_key=key,
                allowed_hosts=("testserver",),
            )
        )
