"""The lie detector, tested.

`scripts/verify_board.py` exists so "this is done" is a claim the owner can
check rather than trust. That only works if the verifier itself is honest — a
checker that passes everything is worse than no checker, because it launders a
false claim into a green tick.

So each test here builds a small, deliberately broken repository and asserts the
verifier **fails** on it. The dangerous failure mode for this file is a check
that silently never fires, so every rule from the brief gets a test that proves
it can go red.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

VERIFIER = Path(__file__).resolve().parents[1] / "scripts" / "verify_board.py"


GOOD_BACKLOG = """# Product backlog

#### S-01.01.01 — A thing that works
**As a** person, **I want** it, **so that** something.
- **Given** a state, **when** an act, **then** an outcome.

## Coverage

| Req | Requirement | Backlog IDs |
|---|---|---|
| R-01 | The thing works | S-01.01.01 |
"""

GOOD_BOARD = """# Board

## BACKLOG

## READY

## IN_PROGRESS

## IN_REVIEW

## BLOCKED

## DONE

- S-01.01.01 · A thing that works
  tests: src/mod.py
  command: python -c "pass"
  result: 1 passed (2026-08-25)
  code: src/mod.py
  commit: abc1234

## DEFERRED
"""


def build(tmp_path: Path, *, board: str = GOOD_BOARD, backlog: str = GOOD_BACKLOG,
          questions: str = "# Open questions\n", code: str = "def works():\n    return 1\n") -> Path:
    """A tiny repository with the same shape the real one has."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "verify_board.py").write_bytes(VERIFIER.read_bytes())
    (tmp_path / "BOARD.md").write_text(board, encoding="utf-8")
    (tmp_path / "PRODUCT_BACKLOG.md").write_text(backlog, encoding="utf-8")
    (tmp_path / "OPEN_QUESTIONS.md").write_text(questions, encoding="utf-8")
    (tmp_path / "src" / "mod.py").write_text(code, encoding="utf-8")
    return tmp_path


def run(repo: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "verify_board.py"), *arguments],
        cwd=repo, capture_output=True, text=True, timeout=300,
    )


# ── it passes when it should ────────────────────────────────────────────────


def test_a_truthful_board_passes_and_exits_zero(tmp_path):
    """The baseline. If this ever fails, every test below proves nothing."""
    result = run(build(tmp_path))
    assert result.returncode == 0, result.stdout
    assert "OK — the board matches the repository" in result.stdout


def test_the_summary_is_recomputed_and_not_read_from_the_file(tmp_path):
    """Rule 7. The counts come from parsing, so a board claiming otherwise in
    prose cannot change them."""
    result = run(build(tmp_path))
    assert "DONE            1" in result.stdout
    assert "requirements mapped     1" in result.stdout


# ── rule 2: orphan requirements ─────────────────────────────────────────────


def test_a_requirement_with_no_backlog_id_fails(tmp_path):
    backlog = GOOD_BACKLOG + "| R-02 | Something nobody planned |  |\n"
    result = run(build(tmp_path, backlog=backlog))
    assert result.returncode == 1
    assert "R-02 is an orphan requirement" in result.stdout


def test_a_requirement_naming_an_id_that_does_not_exist_fails(tmp_path):
    backlog = GOOD_BACKLOG + "| R-02 | Invented | S-09.09.09 |\n"
    result = run(build(tmp_path, backlog=backlog))
    assert result.returncode == 1
    assert "S-09.09.09" in result.stdout


def test_an_empty_coverage_table_fails(tmp_path):
    result = run(build(tmp_path, backlog="#### S-01.01.01 — A thing\n"))
    assert result.returncode == 1
    assert "coverage table is empty" in result.stdout


# ── rule 3: orphan stories ──────────────────────────────────────────────────


def test_a_story_in_the_backlog_and_not_on_the_board_fails(tmp_path):
    backlog = GOOD_BACKLOG.replace(
        "## Coverage",
        "#### S-01.01.02 — A thing nobody tracked\n\n## Coverage",
    ) + "| R-02 | Second thing | S-01.01.02 |\n"
    result = run(build(tmp_path, backlog=backlog))
    assert result.returncode == 1
    assert "S-01.01.02 is defined in the backlog and is not on the board" in result.stdout


def test_an_id_on_the_board_that_no_backlog_defines_fails(tmp_path):
    board = GOOD_BOARD.replace("## READY\n", "## READY\n\n- S-04.04.04 · Where did this come from\n")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "S-04.04.04" in result.stdout


def test_the_same_id_in_two_columns_fails(tmp_path):
    board = GOOD_BOARD.replace("## READY\n", "## READY\n\n- S-01.01.01 · A thing that works\n")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "more than once" in result.stdout


def test_a_column_that_is_not_declared_fails(tmp_path):
    """A typo would otherwise create a column nobody counts, which is where work
    goes to be forgotten."""
    board = GOOD_BOARD + "\n## ALMOST_DONE\n\n"
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "ALMOST_DONE" in result.stdout


# ── rule 4: evidence resolves to artifacts ──────────────────────────────────


def test_done_without_an_evidence_block_fails(tmp_path):
    board = GOOD_BOARD.split("- S-01.01.01")[0] + "- S-01.01.01 · A thing that works\n\n## DEFERRED\n"
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "DONE with no" in result.stdout


def test_done_naming_a_file_that_does_not_exist_fails(tmp_path):
    board = GOOD_BOARD.replace("code: src/mod.py", "code: src/imaginary.py")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "does not exist" in result.stdout


def test_done_naming_a_line_range_past_the_end_of_the_file_fails(tmp_path):
    """The subtle one: the file exists, so a check that only looked for the path
    would pass while the evidence points at nothing."""
    board = GOOD_BOARD.replace("code: src/mod.py", "code: src/mod.py:1-9000")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "9000" in result.stdout or "lines" in result.stdout


def test_done_naming_a_test_file_that_does_not_exist_fails(tmp_path):
    board = GOOD_BOARD.replace("tests: src/mod.py", "tests: tests/test_nothing.py")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "test 'tests/test_nothing.py'" in result.stdout


def test_done_with_a_pending_result_fails(tmp_path):
    """Code written and not verified is IN_REVIEW. There is no third state for
    'I am fairly sure it works'."""
    board = GOOD_BOARD.replace("result: 1 passed (2026-08-25)", "result: pending first run")
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "pending result" in result.stdout


# ── rule 5: the tests are re-run, not believed ──────────────────────────────


def test_a_failing_evidence_command_fails_the_verifier(tmp_path):
    """The recorded result says passed. The command says otherwise. The command
    is what counts."""
    board = GOOD_BOARD.replace('command: python -c "pass"', 'command: python -c "raise SystemExit(1)"')
    result = run(build(tmp_path, board=board))
    assert result.returncode == 1
    assert "evidence command failed" in result.stdout


def test_skip_tests_does_not_hide_that_it_skipped(tmp_path):
    result = run(build(tmp_path), "--skip-tests")
    assert result.returncode == 0
    assert "were not run" in result.stdout


# ── rule 6: no unfinished markers in a done slice ───────────────────────────


def test_a_todo_comment_in_a_done_slice_fails(tmp_path):
    result = run(build(tmp_path, code="def works():\n    # TODO: handle the other case\n    return 1\n"))
    assert result.returncode == 1
    assert "TODO" in result.stdout


def test_a_pass_stub_in_a_done_slice_fails(tmp_path):
    result = run(build(tmp_path, code="def works():\n    pass\n"))
    assert result.returncode == 1
    assert "pass-stub" in result.stdout


def test_a_not_implemented_stub_in_a_done_slice_fails(tmp_path):
    result = run(build(tmp_path, code="def works():\n    raise NotImplementedError\n"))
    assert result.returncode == 1
    assert "NotImplementedError" in result.stdout


def test_the_word_todo_in_prose_does_not_trip_it(tmp_path):
    """The false positive that would make people stop trusting it. A docstring
    explaining what a TODO comment means is prose, not an unfinished path."""
    code = 'def works():\n    """Explains why a TODO comment would be wrong here."""\n    return 1\n'
    result = run(build(tmp_path, code=code))
    assert result.returncode == 0, result.stdout


def test_a_pass_inside_an_except_block_does_not_trip_it(tmp_path):
    """`pass` as an entire function body is a stub. `pass` as a deliberate
    swallow inside `except` is a decision, and flagging it would train people to
    ignore the checker."""
    code = "def works():\n    try:\n        return 1\n    except ValueError:\n        pass\n"
    result = run(build(tmp_path, code=code))
    assert result.returncode == 0, result.stdout


# ── process rules ───────────────────────────────────────────────────────────


def test_more_than_two_items_in_progress_fails(tmp_path):
    backlog = GOOD_BACKLOG.replace(
        "## Coverage",
        "#### S-02.01.01 — One\n\n#### S-02.01.02 — Two\n\n#### S-02.01.03 — Three\n\n## Coverage",
    ) + "| R-02 | More | S-02.01.01, S-02.01.02, S-02.01.03 |\n"
    board = GOOD_BOARD.replace(
        "## IN_PROGRESS\n",
        "## IN_PROGRESS\n\n- S-02.01.01 · One\n- S-02.01.02 · Two\n- S-02.01.03 · Three\n",
    )
    result = run(build(tmp_path, board=board, backlog=backlog))
    assert result.returncode == 1
    assert "WIP limit is 2" in result.stdout


def test_blocked_without_an_escalation_fails(tmp_path):
    """'Blocked' with nobody to unblock it is a status, not an escalation."""
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-03.01.01 — Stuck\n\n## Coverage") \
        + "| R-02 | Stuck thing | S-03.01.01 |\n"
    board = GOOD_BOARD.replace("## BLOCKED\n", "## BLOCKED\n\n- S-03.01.01 · Stuck\n")
    result = run(build(tmp_path, board=board, backlog=backlog))
    assert result.returncode == 1
    assert "BLOCKED with no escalation" in result.stdout


def test_blocked_on_a_question_that_does_not_exist_fails(tmp_path):
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-03.01.01 — Stuck\n\n## Coverage") \
        + "| R-02 | Stuck thing | S-03.01.01 |\n"
    board = GOOD_BOARD.replace(
        "## BLOCKED\n", "## BLOCKED\n\n- S-03.01.01 · Stuck\n  blocked: Q-99 — invented\n"
    )
    result = run(build(tmp_path, board=board, backlog=backlog))
    assert result.returncode == 1
    assert "Q-99" in result.stdout


def test_ready_with_an_open_question_against_it_fails(tmp_path):
    """Definition of Ready. An item whose shape may still change is not ready,
    and building it means building it twice."""
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-05.01.01 — Unclear\n\n## Coverage") \
        + "| R-02 | Unclear thing | S-05.01.01 |\n"
    board = GOOD_BOARD.replace("## READY\n", "## READY\n\n- S-05.01.01 · Unclear\n")
    questions = "# Open questions\n\n### Q-01 — Something\n\nBlocks S-05.01.01.\n"
    result = run(build(tmp_path, board=board, backlog=backlog, questions=questions))
    assert result.returncode == 1
    assert "Q-01 is still open against it" in result.stdout


def test_an_answered_question_stops_blocking_ready(tmp_path):
    """S-06.02.07. Recording a decision is what unblocks the board. If an
    answered question still blocked, the only way forward would be deleting the
    question — and that loses why the work was ever held up."""
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-05.01.01 — Was unclear\n\n## Coverage") \
        + "| R-02 | Formerly unclear thing | S-05.01.01 |\n"
    board = GOOD_BOARD.replace("## READY\n", "## READY\n\n- S-05.01.01 · Was unclear\n")
    questions = (
        "# Open questions\n\n### Q-01 — Something\n\n"
        "**Status:** answered · **Decision:** we chose option 3.\n\nBlocks S-05.01.01.\n"
    )
    result = run(build(tmp_path, board=board, backlog=backlog, questions=questions))
    assert result.returncode == 0, result.stdout


def test_blocked_on_a_question_that_was_already_answered_fails(tmp_path):
    """The other direction: a board still citing a decided question is stale,
    and stale is how work sits still while everyone believes it is waiting."""
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-03.01.01 — Stuck\n\n## Coverage") \
        + "| R-02 | Stuck thing | S-03.01.01 |\n"
    board = GOOD_BOARD.replace(
        "## BLOCKED\n", "## BLOCKED\n\n- S-03.01.01 · Stuck\n  blocked: Q-01 — decided already\n"
    )
    questions = "# Open questions\n\n### Q-01 — Something\n\n**Status:** answered\n"
    result = run(build(tmp_path, board=board, backlog=backlog, questions=questions))
    assert result.returncode == 1
    assert "has been answered" in result.stdout


def test_deferred_without_a_reason_and_a_trigger_fails(tmp_path):
    """Scope is never silently dropped."""
    backlog = GOOD_BACKLOG.replace("## Coverage", "#### S-06.01.01 — Cut\n\n## Coverage") \
        + "| R-02 | Cut thing | S-06.01.01 |\n"
    board = GOOD_BOARD.replace("## DEFERRED\n", "## DEFERRED\n\n- S-06.01.01 · Cut\n")
    result = run(build(tmp_path, board=board, backlog=backlog))
    assert result.returncode == 1
    assert "no reason" in result.stdout or "no trigger" in result.stdout


def test_a_missing_board_fails_rather_than_passing_vacuously(tmp_path):
    """The worst possible bug in a verifier: nothing to check, so everything is
    fine."""
    repo = build(tmp_path)
    (repo / "BOARD.md").unlink()
    result = run(repo)
    assert result.returncode == 1
    assert "BOARD.md does not exist" in result.stdout
