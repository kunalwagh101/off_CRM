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
        if not swapped and flags & os.O_CREAT and Path(path).name == filename:
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

