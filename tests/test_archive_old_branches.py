"""The owner's branch clean-up keeps every old branch as a tag before deleting it.

`scripts/archive_old_branches.sh` is run once, by hand, against the real
repository — so it is proved here against a throwaway one first.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_old_branches.sh"
OLD = ("feature/old-one", "claude/old-two")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="needs bash and git"
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repositories(tmp_path: Path) -> tuple[Path, Path]:
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    _git(tmp_path, "init", "--bare", "-q", str(remote))
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "config", "user.email", "owner@example.invalid")
    _git(work, "config", "user.name", "Owner")
    (work / "file").write_text("base")
    _git(work, "add", "file")
    _git(work, "commit", "-qm", "base")
    for name in ("main", "develop"):
        _git(work, "push", "-q", "origin", f"HEAD:refs/heads/{name}")
    for name in OLD:
        _git(work, "checkout", "-qb", name)
        (work / "file").write_text(name)
        _git(work, "commit", "-qam", name)
        _git(work, "push", "-q", "origin", f"HEAD:refs/heads/{name}")
    return remote, work


def _run(work: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=work, capture_output=True, text=True)


def _heads(remote: Path) -> list[str]:
    return sorted(_git(remote, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())


def test_every_old_branch_is_a_tag_before_any_is_deleted(tmp_path):
    remote, work = _repositories(tmp_path)
    tips = {name: _git(remote, "rev-parse", f"refs/heads/{name}") for name in OLD}

    dry = _run(work)
    assert dry.returncode == 0, dry.stderr
    assert "Nothing deleted" in dry.stdout
    assert _heads(remote) == sorted(["develop", "main", *OLD])
    for name, commit in tips.items():
        assert _git(remote, "rev-parse", f"refs/tags/archive/{name}") == commit

    deleted = _run(work, "--delete")
    assert deleted.returncode == 0, deleted.stderr
    assert _heads(remote) == ["develop", "main"]
    for name, commit in tips.items():
        assert _git(remote, "rev-parse", f"refs/tags/archive/{name}") == commit

    again = _run(work, "--delete")
    assert again.returncode == 0, again.stderr
    assert "Nothing to archive" in again.stdout


def test_a_tag_already_pointing_elsewhere_stops_everything(tmp_path):
    remote, work = _repositories(tmp_path)
    _git(work, "tag", "archive/feature/old-one", "origin/main")

    result = _run(work, "--delete")
    assert result.returncode != 0
    assert "Nothing was deleted" in result.stderr
    assert _heads(remote) == sorted(["develop", "main", *OLD])
