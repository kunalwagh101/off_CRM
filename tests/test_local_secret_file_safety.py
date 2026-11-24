"""D-500: local API credentials must never follow links or overwrite old files."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from offsetx_apollo_builder.api.config import AppSettings


def _settings(tmp_path: Path) -> AppSettings:
    data = tmp_path / "private-data"
    data.mkdir(exist_ok=True)
    return AppSettings(
        project_root=tmp_path, database_path=data / "crm.db",
        data_dir=data, export_dir=data / "exports",
        frontend_dist=tmp_path / "frontend",
    )


def _issue(settings: AppSettings, kind: str) -> str:
    return (settings.ensure_api_token() if kind == "token"
            else settings.ensure_session_secret())


@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_local_secret_refuses_a_symlink_to_a_foreign_file(tmp_path, kind, filename):
    settings = _settings(tmp_path)
    outside = tmp_path / "foreign-file"
    outside.write_text("z" * 64, encoding="utf-8")
    (settings.data_dir / filename).symlink_to(outside)
    with pytest.raises(ValueError, match="private|symbolic|symlink|unsafe"):
        _issue(settings, kind)
    assert outside.read_text(encoding="utf-8") == "z" * 64


@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_local_secret_never_overwrites_an_invalid_existing_file(tmp_path, kind, filename):
    settings = _settings(tmp_path)
    target = settings.data_dir / filename
    target.write_text("incomplete", encoding="utf-8")
    with pytest.raises(ValueError, match="private|invalid|unsafe"):
        _issue(settings, kind)
    assert target.read_text(encoding="utf-8") == "incomplete"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_local_secret_rejects_world_readable_existing_credentials(tmp_path, kind, filename):
    settings = _settings(tmp_path)
    target = settings.data_dir / filename
    target.write_text("a" * 64, encoding="utf-8")
    target.chmod(0o644)
    with pytest.raises(ValueError, match="private|permission|unsafe"):
        _issue(settings, kind)
    assert target.read_text(encoding="utf-8") == "a" * 64


@pytest.mark.skipif(os.name != "posix", reason="directory descriptor safety is POSIX-specific")
@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_parent_directory_swap_cannot_redirect_created_local_secret(
    tmp_path, monkeypatch, kind, filename
):
    settings = _settings(tmp_path)
    original = tmp_path / "relocated-original"
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if not swapped and flags & os.O_CREAT and Path(path).name.startswith(f".{filename}."):
            settings.data_dir.rename(original)
            settings.data_dir.symlink_to(attacker, target_is_directory=True)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swapping_open)
    created = _issue(settings, kind)
    assert swapped, "test did not inject the parent swap"
    assert len(created) >= 32
    assert not (attacker / filename).exists(), "secret escaped into the replaced parent"
    assert (original / filename).read_text(encoding="utf-8").strip() == created


@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_generated_local_secret_is_private_and_reusable(tmp_path, kind, filename):
    settings = _settings(tmp_path)
    first = _issue(settings, kind)
    second = _issue(_settings(tmp_path), kind)
    assert len(first) >= 32 and first == second
    target = settings.data_dir / filename
    assert target.is_file() and not target.is_symlink()
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

def test_reloading_a_file_managed_token_refuses_a_replaced_symlink(tmp_path):
    settings = _settings(tmp_path)
    original = settings.ensure_api_token()
    token = settings.data_dir / "local_api_token"
    token.unlink()
    outside = tmp_path / "outside-existing-secret"
    outside.write_text("p" * 64, encoding="utf-8")
    token.symlink_to(outside)
    with pytest.raises(ValueError, match="Restored local API token is invalid"):
        settings.reload_local_api_token()
    assert settings.api_token == original
    assert outside.read_text(encoding="utf-8") == "p" * 64

@pytest.mark.skipif(os.name != "posix", reason="POSIX inode and ownership checks")
@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_private_local_secret_rejects_hardlinked_file(tmp_path, kind, filename):
    """D-501: a second pathname must not alias a credential's inode."""
    settings = _settings(tmp_path)
    original = settings.data_dir / filename
    alias = tmp_path / "alias-to-credential"
    alias.write_text("k" * 64, encoding="ascii")
    alias.chmod(0o600)
    os.link(alias, original)
    before = alias.read_bytes()
    with pytest.raises(ValueError, match="private|unsafe|link"):
        _issue(settings, kind)
    assert original.read_bytes() == before
    assert alias.read_bytes() == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX effective-user ownership")
@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_private_local_secret_rejects_other_user_owned_file(tmp_path, monkeypatch, kind, filename):
    """D-501: a privileged service must not accept a planted user's token."""
    settings = _settings(tmp_path)
    token = settings.data_dir / filename
    token.write_text("m" * 64, encoding="ascii")
    token.chmod(0o600)
    before = token.read_bytes()
    real_uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: real_uid + 1)
    with pytest.raises(ValueError, match="private|owner|unsafe"):
        _issue(settings, kind)
    assert token.read_bytes() == before


@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_failed_random_secret_generation_does_not_leave_poisoned_file(
    tmp_path, monkeypatch, kind, filename
):
    """D-504: entropy failure must not strand an invalid permanent credential."""
    from offsetx_apollo_builder.api import config

    settings = _settings(tmp_path)
    target = settings.data_dir / filename
    real_generate = config.secrets.token_urlsafe

    def unavailable_entropy(_number):
        raise OSError("synthetic random source failure")

    monkeypatch.setattr(config.secrets, "token_urlsafe", unavailable_entropy)
    with pytest.raises(ValueError, match="unsafe|inaccessible|credential|secret"):
        _issue(settings, kind)
    assert not target.exists(), "a failed key generation must not poison the next boot"

    monkeypatch.setattr(config.secrets, "token_urlsafe", real_generate)
    created = _issue(_settings(tmp_path), kind)
    assert len(created) >= 32
    assert target.is_file()
    assert target.read_text(encoding="ascii").strip() == created


@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
@pytest.mark.parametrize("failure", ["partial_write", "fsync"])
def test_failed_secret_disk_write_does_not_poison_next_boot(
    tmp_path, monkeypatch, kind, filename, failure
):
    """D-521: never publish incomplete local credentials."""
    from contextlib import contextmanager

    settings = _settings(tmp_path)
    target = settings.data_dir / filename
    original = os.fdopen

    @contextmanager
    def failing_write(fd, mode, *args, **kwargs):
        with original(fd, mode, *args, **kwargs) as stream:
            if mode == "w":
                stream.write("partial")
                stream.flush()
                raise OSError("synthetic disk failure")
            yield stream

    def failing_fsync(_fd):
        raise OSError("synthetic flush failure")

    with monkeypatch.context() as patch:
        if failure == "partial_write":
            patch.setattr(os, "fdopen", failing_write)
        else:
            patch.setattr(os, "fsync", failing_fsync)
        with pytest.raises(ValueError, match="unsafe|inaccessible|credential"):
            _issue(settings, kind)
    assert not target.exists()
    assert list(settings.data_dir.iterdir()) == []
    created = _issue(_settings(tmp_path), kind)
    assert created == _issue(_settings(tmp_path), kind)
    assert target.read_text(encoding="ascii") == created


@pytest.mark.skipif(os.name != "posix", reason="POSIX no-replace publication")
@pytest.mark.parametrize("kind,filename", [
    ("token", "local_api_token"),
    ("session", "workspace_session_secret"),
])
def test_concurrent_credential_creation_preserves_winner(
    tmp_path, monkeypatch, kind, filename
):
    settings = _settings(tmp_path)
    target = settings.data_dir / filename
    original_link = os.link

    def racing_link(src, dst, *args, **kwargs):
        target.write_text("z" * 64, encoding="ascii")
        target.chmod(0o600)
        return original_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "link", racing_link)
    with pytest.raises(ValueError, match="concurrently"):
        _issue(settings, kind)
    assert list(settings.data_dir.iterdir()) == [target]
    assert target.read_text(encoding="ascii") == "z" * 64
    assert _issue(_settings(tmp_path), kind) == "z" * 64
