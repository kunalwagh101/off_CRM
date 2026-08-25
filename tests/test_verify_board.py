"""The board verifier has to fail when the board lies, or it is decoration.

`scripts/verify_board.py` is what makes a "done" in BUILD_STATE.md checkable, so
its failure modes are the behaviour worth testing: a claim with no test behind
it, a path that no longer exists, an entry that quietly skipped the board, two
items sharing an id, and work markers left inside finished code. The last test
runs the real board so this file also fails when BUILD_STATE.md itself drifts.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_board", ROOT / "scripts" / "verify_board.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


verify_board = _load()


def _board(entries: str) -> str:
    return (
        "# BUILD_STATE.md\n\n## 3. Done\n\n"
        + entries
        + "\n\n## 4. Not built yet\n\n"
        "| § | Item | Note |\n|---|---|---|\n| 4D | Something | later |\n"
        "\n## 5. Decisions and why\n\n1. A decision.\n"
        "\n## 6. Open questions for the owner\n\n1. A question.\n2. Another.\n"
    )


def _entry(title: str, ident: str, status: str, tests: str, code: str, gap: str = "") -> str:
    block = (
        f"### {title}\n- [x] did a thing\n\n"
        f"> **BOARD** `{ident}` · status `{status}`\n"
        f"> tests: {tests}\n> code: {code}\n"
    )
    return block + (f"> gap: {gap}\n" if gap else "")


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A throwaway checkout the verifier can be pointed at."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "test_thing.py").write_text("def test_thing():\n    assert True\n")
    (tmp_path / "src" / "thing.py").write_text("def thing():\n    return 1\n")
    monkeypatch.setattr(verify_board, "ROOT", tmp_path)
    return tmp_path


def _parse(repo: Path, entries: str):
    path = repo / "BUILD_STATE.md"
    path.write_text(_board(entries))
    return verify_board.parse_board(path.read_text())


def test_a_well_formed_entry_parses_into_evidence(repo):
    items, unboarded, backlog, blocked = _parse(
        repo, _entry("A thing", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    )
    assert unboarded == []
    assert backlog == 1 and blocked == 2
    assert [i.id for i in items] == ["D-01"]
    assert items[0].tests == ["tests/test_thing.py"]
    assert items[0].code == ["src/thing.py"]
    verify_board.check_paths(items)
    assert items[0].ok


def test_an_entry_with_no_board_block_is_reported(repo):
    items, unboarded, _, _ = _parse(repo, "### Unboarded work\n- [x] done, allegedly\n")
    assert items == []
    assert unboarded == ["Unboarded work"]


def test_done_with_no_test_named_is_refused(repo):
    items, _, _, _ = _parse(repo, _entry("A claim", "D-01", "DONE", "NONE", "`src/thing.py`"))
    verify_board.check_paths(items)
    assert not items[0].ok
    assert any("no test named" in f for f in items[0].failures)


def test_in_review_may_stand_without_a_test(repo):
    """The honest way to record something built but unproven."""
    items, _, _, _ = _parse(
        repo, _entry("A doc", "D-01", "IN_REVIEW", "NONE", "`src/thing.py`", "nothing runs it")
    )
    verify_board.check_paths(items)
    assert items[0].ok
    assert items[0].gap == "nothing runs it"


def test_a_path_that_no_longer_exists_fails(repo):
    items, _, _, _ = _parse(
        repo, _entry("Moved code", "D-01", "DONE", "`tests/test_thing.py`", "`src/deleted.py`")
    )
    verify_board.check_paths(items)
    assert any("does not exist" in f for f in items[0].failures)


def test_a_missing_test_file_fails_too(repo):
    items, _, _, _ = _parse(
        repo, _entry("Gone", "D-01", "DONE", "`tests/test_gone.py`", "`src/thing.py`")
    )
    verify_board.check_paths(items)
    assert any("does not exist" in f for f in items[0].failures)


def test_two_entries_cannot_share_an_id(repo):
    entries = _entry("One", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    entries += "\n" + _entry("Two", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    items, _, _, _ = _parse(repo, entries)
    verify_board.check_paths(items)
    assert any("duplicate board id" in f for f in items[1].failures)


def test_an_unknown_status_is_refused(repo):
    items, _, _, _ = _parse(
        repo, _entry("Odd", "D-01", "SHIPPED", "`tests/test_thing.py`", "`src/thing.py`")
    )
    verify_board.check_paths(items)
    assert any("unknown status" in f for f in items[0].failures)


def test_a_work_marker_inside_done_code_fails(repo):
    (repo / "src" / "thing.py").write_text("def thing():\n    return 1  # TODO: handle retries\n")
    items, _, _, _ = _parse(
        repo, _entry("Half done", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    )
    verify_board.scan_stubs(items)
    assert any("work marker inside DONE code" in f for f in items[0].failures)


def test_the_same_marker_under_partial_is_only_a_note(repo):
    """PARTIAL already says it is unfinished; the marker is information, not a lie."""
    (repo / "src" / "thing.py").write_text("def thing():\n    return 1  # TODO: handle retries\n")
    items, _, _, _ = _parse(
        repo, _entry("Partly", "D-01", "PARTIAL", "`tests/test_thing.py`", "`src/thing.py`", "rest")
    )
    verify_board.scan_stubs(items)
    assert items[0].ok
    assert any("work marker" in n for n in items[0].notes)


def test_an_abstract_base_method_is_a_note_not_a_failure(repo):
    """db/connection.py raises NotImplementedError by design; that must not fail."""
    (repo / "src" / "thing.py").write_text("class Base:\n    def run(self):\n        raise NotImplementedError\n")
    items, _, _, _ = _parse(
        repo, _entry("Base class", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    )
    verify_board.scan_stubs(items)
    assert items[0].ok
    assert any("NotImplementedError" in n for n in items[0].notes)


def test_a_failing_test_is_attributed_back_to_the_claim_that_leans_on_it(repo):
    (repo / "tests" / "test_thing.py").write_text("def test_thing():\n    assert False\n")
    items, _, _, _ = _parse(
        repo, _entry("Broken", "D-01", "DONE", "`tests/test_thing.py`", "`src/thing.py`")
    )
    verify_board.run_python(items)
    assert any("failing test behind this claim" in f for f in items[0].failures)


def test_the_real_build_state_board_still_holds():
    """Guards the live file: every DONE claim resolves to code and a named test."""
    items, unboarded, _, _ = verify_board.parse_board(
        (ROOT / "BUILD_STATE.md").read_text()
    )
    verify_board.check_paths(items)
    verify_board.scan_stubs(items)
    assert unboarded == [], f"entries with no BOARD block: {unboarded}"
    broken = {i.id: i.failures for i in items if not i.ok}
    assert not broken, f"board entries that do not resolve: {broken}"
