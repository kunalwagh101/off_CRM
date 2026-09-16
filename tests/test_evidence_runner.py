from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_evidence
from scripts.verify_board import Report, read_board

ROOT = Path(__file__).resolve().parents[1]


def _board(tmp_path: Path, *, column: str = "DONE", tests: str = "tests/test_x.py") -> Path:
    path = tmp_path / "BOARD.md"
    path.write_text(
        "# Board\n\n"
        "## BACKLOG\n\n## READY\n\n## IN_PROGRESS\n\n## IN_REVIEW\n\n"
        "## BLOCKED\n\n## DONE\n\n"
        + (f"- S-01.01.01 · X\n  tests: {tests}\n" if column == "DONE" else "")
        + "\n## DEFERRED\n",
        encoding="utf-8",
    )
    if column != "DONE":
        text = path.read_text(encoding="utf-8")
        text = text.replace(f"## {column}\n", f"## {column}\n\n- S-01.01.01 · X\n  tests: {tests}\n")
        path.write_text(text, encoding="utf-8")
    return path


def test_every_done_command_uses_the_one_runner():
    report = Report()
    items = read_board(ROOT / "BOARD.md", report)
    assert not report.failures
    wrong = {
        item.identifier: item.fields.get("command", "")
        for item in items
        if item.column == "DONE"
        and item.fields.get("command", "") != run_evidence.command_for(item.identifier)
    }
    assert wrong == {}


def test_a_plan_uses_python_frontend_and_keeps_live_evidence_separate(tmp_path):
    board = _board(
        tmp_path,
        tests=(
            "tests/test_x.py::test_one, frontend/src/x.test.tsx, "
            "verification/test_x_live.py"
        ),
    )
    plan = run_evidence.plan_for("S-01.01.01", board=board)
    assert plan.python == ("tests/test_x.py::test_one",)
    assert plan.frontend == ("src/x.test.tsx",)
    assert plan.live_only == ("verification/test_x_live.py",)


def test_a_story_not_done_cannot_be_replayed(tmp_path):
    board = _board(tmp_path, column="READY")
    with pytest.raises(run_evidence.EvidenceError, match="not DONE"):
        run_evidence.plan_for("S-01.01.01", board=board)


def test_unknown_test_boundaries_are_refused(tmp_path):
    board = _board(tmp_path, tests="scripts/something.py")
    with pytest.raises(run_evidence.EvidenceError, match="unsupported test target"):
        run_evidence.plan_for("S-01.01.01", board=board)


def test_live_evidence_alone_cannot_make_done(tmp_path):
    board = _board(tmp_path, tests="verification/test_x_live.py")
    with pytest.raises(run_evidence.EvidenceError, match="no replayable tests"):
        run_evidence.plan_for("S-01.01.01", board=board)


def test_python_evidence_uses_this_exact_interpreter_and_no_shell(monkeypatch):
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(run_evidence.subprocess, "run", fake_run)
    result = run_evidence.run_plan(
        run_evidence.EvidencePlan("S-01.01.01", ("tests/test_x.py",), (), ())
    )
    assert result == 0
    argv, kwargs = calls[0]
    assert argv[:3] == [sys.executable, "-m", "pytest"]
    assert "shell" not in kwargs or kwargs["shell"] is False


def test_frontend_evidence_uses_npm_without_a_shell(monkeypatch):
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(run_evidence.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(run_evidence.subprocess, "run", fake_run)
    result = run_evidence.run_plan(
        run_evidence.EvidencePlan("S-01.01.01", (), ("src/x.test.tsx",), ())
    )
    assert result == 0
    argv, kwargs = calls[0]
    assert argv == ["/usr/bin/npm", "test", "--", "src/x.test.tsx"]
    assert kwargs["cwd"] == ROOT / "frontend"
    assert "shell" not in kwargs or kwargs["shell"] is False


def test_documented_verification_setup_names_both_dependency_sets_and_no_sync_verifier():
    guide = (ROOT / "docs" / "architecture" / "EVIDENCE_RUNNER.md").read_text(
        encoding="utf-8"
    )
    assert "uv sync --extra dev --extra email --locked" in guide
    assert "npm ci --prefix frontend" in guide
    assert "uv run --no-sync python scripts/verify_board.py" in guide
