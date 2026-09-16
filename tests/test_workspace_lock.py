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
