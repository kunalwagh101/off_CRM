"""File lease semantics must hold on Linux and native Windows."""
import subprocess
import sys

import pytest

from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceBusy, WorkspaceLock


def test_shared_leases_overlap_but_exclude_recovery(tmp_path):
    with WorkspaceLock(tmp_path / 'data'), WorkspaceLock(tmp_path / 'data'):
        with pytest.raises(WorkspaceBusy):
            with WorkspaceLock(tmp_path / 'data', exclusive=True):
                pytest.fail('exclusive recovery entered during normal work')
    with WorkspaceLock(tmp_path / 'data', exclusive=True):
        with pytest.raises(WorkspaceBusy):
            with WorkspaceLock(tmp_path / 'data'):
                pytest.fail('normal work entered during recovery')
    with WorkspaceLock(tmp_path / 'data'):
        pass


def test_recovery_lease_is_shared_across_processes(tmp_path):
    script = 'from pathlib import Path; import sys; from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock;\nwith WorkspaceLock(Path(sys.argv[1])): print("acquired")'
    with WorkspaceLock(tmp_path / 'data', exclusive=True):
        process = subprocess.run([sys.executable, '-c', script, str(tmp_path / 'data')], capture_output=True, text=True, timeout=15)
        assert process.returncode != 0
        assert 'WorkspaceBusy' in process.stderr
    process = subprocess.run([sys.executable, '-c', script, str(tmp_path / 'data')], capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == 'acquired'


def _pending_restore(tmp_path):
    """A restore swapped in and never committed, as a crash leaves it."""
    from offsetx_apollo_builder.outreach import backup
    from test_audit_wp1 import PASSPHRASE, _settings, _sqlite

    settings = _settings(tmp_path)
    _sqlite(settings.database_path, "before")
    content = backup.create_encrypted_backup(
        database_path=settings.database_path, data_dir=settings.data_dir, passphrase=PASSPHRASE
    )
    backup.restore_encrypted_backup(
        content, database_path=settings.database_path, data_dir=settings.data_dir, passphrase=PASSPHRASE
    )
    assert backup.restore_pending(settings.data_dir)
    return settings


def test_the_app_starts_while_the_email_worker_is_mid_cycle(tmp_path):
    """Start-up took the recovery lock without waiting, even with nothing to
    recover, so a worker's shared lease stopped the web app starting (D-129)."""
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api import create_app
    from test_audit_wp1 import _settings

    settings = _settings(tmp_path)
    with WorkspaceLock(settings.data_dir):
        with TestClient(create_app(settings)) as client:
            assert client.get("/health/live").status_code == 200


def test_start_up_waits_for_the_worker_before_rolling_back_a_restore(tmp_path):
    import threading

    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api import create_app
    from offsetx_apollo_builder.outreach import backup

    settings = _pending_restore(tmp_path)
    worker = WorkspaceLock(settings.data_dir).__enter__()
    threading.Timer(0.5, worker.__exit__).start()
    with TestClient(create_app(settings)):
        assert not backup.restore_pending(settings.data_dir)


def test_start_up_gives_up_with_a_reason_when_the_workspace_stays_busy(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import offsetx_apollo_builder.api.app as app_module

    monkeypatch.setattr(app_module, "RECOVERY_WAIT_SECONDS", 0.3)
    settings = _pending_restore(tmp_path)
    with WorkspaceLock(settings.data_dir):
        with pytest.raises(WorkspaceBusy, match="restore"):
            with TestClient(app_module.create_app(settings)):
                pytest.fail("started over a half-restored workspace")


def test_explicit_file_lease_finds_the_workspace_even_from_another_folder(tmp_path, monkeypatch):
    from offsetx_apollo_builder.outreach.workspace_lock import cli_workspace_leases

    home = tmp_path / "web-data"
    home.mkdir()
    external = tmp_path / "elsewhere"
    external.mkdir()
    monkeypatch.chdir(external)
    with WorkspaceLock(home, exclusive=True):
        with pytest.raises(SystemExit, match="backing up or restoring"):
            with cli_workspace_leases(home / "offsetx_outreach.db"):
                pytest.fail("worked in the file of an exclusively locked workspace")
        with pytest.raises(SystemExit, match="backing up or restoring"):
            with cli_workspace_leases(home / "runs" / "one" / "trace.json"):
                pytest.fail("worked in a nested run directory under restore")


def test_independent_file_does_not_take_an_unrelated_workspace_lease(tmp_path):
    from offsetx_apollo_builder.outreach.workspace_lock import cli_workspace_leases

    web = tmp_path / "web"
    web.mkdir()
    independent = tmp_path / "independent"
    independent.mkdir()
    with WorkspaceLock(web, exclusive=True):
        with cli_workspace_leases(independent / "notes.db"):
            pass


def test_the_worker_does_not_run_over_a_half_restored_workspace(tmp_path, monkeypatch):
    """A restore whose rollback failed leaves its journal; the worker took its
    lease anyway and worked over the half-restored workspace (D-129)."""
    from offsetx_apollo_builder import email_worker_cli

    settings = _pending_restore(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(settings.database_path))
    monkeypatch.setattr(
        email_worker_cli, "_service", lambda *a, **k: pytest.fail("worked over a half-restored workspace")
    )
    with pytest.raises(SystemExit, match="restore"):
        email_worker_cli.main([])
