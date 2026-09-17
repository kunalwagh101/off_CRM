#!/usr/bin/env python3
"""One-shot, assertion-backed delivery helper for S-06.02.17.

The script edits only repository artifacts. The temporary workflow that invokes
it is created and removed through the GitHub connector, not from inside Actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def write(name: str, text: str) -> None:
    (ROOT / name).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def pull() -> None:
    board = read("BOARD.md")
    story = "- S-06.02.17 · DONE may not depend on unfinished work\n"
    if story not in board:
        raise RuntimeError("S-06.02.17 is not in the board backlog")
    board = replace_once(board, story, "", label="remove S-06.02.17 from BACKLOG")
    board = replace_once(
        board,
        "## IN_PROGRESS\n\n_nothing in flight_\n",
        "## IN_PROGRESS\n\n- S-06.02.17 · DONE may not depend on unfinished work\n",
        label="pull S-06.02.17",
    )
    write("BOARD.md", board)


def implement() -> None:
    verifier = read("scripts/verify_board.py")
    verifier = replace_once(
        verifier,
        "    python scripts/verify_board.py\n",
        "    uv run python scripts/verify_board.py\n",
        label="canonical verifier invocation",
    )
    old = '''        if item.column == "READY":\n            unmet = [name for name in waiting\n                     if name in column and column[name] != "DONE"]\n            if unmet:\n                report.fail(\n                    f"{item.identifier} is READY but waits on {', '.join(unmet)}, "\n                    "which is not DONE. The Definition of Ready is not advisory."\n                )\n'''
    new = old + '''\n        # A DONE story is a claim about delivery history as well as current code.\n        # If an upstream story is not DONE, that history is impossible: either\n        # the dependency is false or the DONE claim is. `S-06.02.17` / `D-48`.\n        if item.column == "DONE":\n            unfinished = [name for name in waiting\n                          if name in column and column[name] != "DONE"]\n            if unfinished:\n                detail = ", ".join(\n                    f"{name} ({column[name]})" for name in unfinished\n                )\n                report.fail(\n                    f"{item.identifier} is DONE but waits on {detail}, which is "\n                    "not DONE. A completed story cannot depend on unfinished work."\n                )\n'''
    verifier = replace_once(verifier, old, new, label="DONE dependency invariant")
    write("scripts/verify_board.py", verifier)

    tests = read("tests/test_verify_board.py")
    marker = "\n\n# ── rule 10: a recorded commit is on the branch  `S-06.02.12` ───────────────\n"
    addition = r'''

# ── rule 9b: DONE cannot depend on unfinished work  `S-06.02.17` ────────────


def _done_on_board(board: str, identifier: str) -> str:
    """Put a second story in DONE with the minimum truthful evidence fixture."""
    block = f'''## DONE

- {identifier} · Another thing
  tests: src/mod.py
  command: uv run python -c "pass"
  result: 1 passed (fixture)
  code: src/mod.py

'''
    return board.replace("## DONE\n", block, 1)


def _unfinished_on_board(board: str, identifier: str, column: str) -> str:
    if column == "BLOCKED":
        return board.replace(
            "## BLOCKED\n",
            f"## BLOCKED\n\n- {identifier} · Another thing\n"
            "  blocked: external — fixture dependency\n",
            1,
        )
    if column == "DEFERRED":
        return board.replace(
            "## DEFERRED\n",
            f"## DEFERRED\n\n- {identifier} · Another thing\n"
            "  reason: fixture deferral\n"
            "  trigger: fixture trigger\n",
            1,
        )
    return _on_board(board, identifier, column)


@pytest.mark.parametrize(
    "dependency_column",
    ["BACKLOG", "READY", "IN_PROGRESS", "IN_REVIEW", "BLOCKED", "DEFERRED"],
)
def test_done_with_any_unfinished_dependency_fails(tmp_path, dependency_column):
    """A DONE claim cannot be built on any state other than DONE.

    The acceptance criterion names BACKLOG, READY and BLOCKED. The remaining
    unfinished columns are included because the invariant is stronger and
    simpler than a hand-maintained allow/deny list.
    """
    backlog = _with_story(GOOD_BACKLOG, "S-02.02.02", waits_on="S-03.03.03")
    backlog = _with_story(backlog, "S-03.03.03")
    board = _done_on_board(GOOD_BOARD, "S-02.02.02")
    board = _unfinished_on_board(board, "S-03.03.03", dependency_column)

    result = run(build(tmp_path, backlog=backlog, board=board), "--skip-tests")

    assert result.returncode == 1
    assert "S-02.02.02 is DONE but waits on S-03.03.03" in result.stdout
    assert f"S-03.03.03 ({dependency_column})" in result.stdout


def test_done_with_only_done_dependencies_passes(tmp_path):
    """The guard must not reject a truthful delivery chain."""
    backlog = _with_story(GOOD_BACKLOG, "S-02.02.02", waits_on="S-01.01.01")
    board = _done_on_board(GOOD_BOARD, "S-02.02.02")

    result = run(build(tmp_path, backlog=backlog, board=board), "--skip-tests")

    assert result.returncode == 0, result.stdout
    assert "OK — the board matches the repository" in result.stdout
'''
    tests = replace_once(tests, marker, addition + marker, label="S-06.02.17 tests")
    write("tests/test_verify_board.py", tests)

    dod = read("DEFINITION_OF_DONE.md")
    anchor = "- [ ] **Tests exist and are named in the evidence block**, covering *each*\n      acceptance criterion. A story with three criteria and one test is not done.\n"
    inserted = anchor + (
        "- [ ] **Every declared upstream dependency is already `DONE`.** A DONE\n"
        "      story cannot certify an impossible delivery history on unfinished work.\n"
    )
    dod = replace_once(dod, anchor, inserted, label="Definition of Done dependency rule")
    write("DEFINITION_OF_DONE.md", dod)

    changelog = read("CHANGELOG.md")
    changelog_entry = (
        "- **DONE dependency history is now mechanically enforced** (`S-06.02.17`, "
        "closing `D-48`). The verifier rejects a DONE story whose declared upstream "
        "story is in any non-DONE column, names both stories and the upstream state, "
        "and still accepts a chain whose dependencies are all DONE.\n"
    )
    changelog = replace_once(
        changelog,
        "## Unreleased\n\n",
        "## Unreleased\n\n" + changelog_entry,
        label="CHANGELOG entry",
    )
    write("CHANGELOG.md", changelog)

    demo = read("DEMO.md")
    demo_addition = '''\n\n---\n\n## DONE cannot depend on unfinished work\n\nThe verifier's delivery-history guard is tested against every non-DONE board\ncolumn, plus the valid all-DONE case:\n\n```bash\nuv run pytest tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails tests/test_verify_board.py::test_done_with_only_done_dependencies_passes -q\n```\n\nExpect `7 passed`. The failing fixtures deliberately put the upstream story in\nBACKLOG, READY, IN_PROGRESS, IN_REVIEW, BLOCKED and DEFERRED; each must make the\nverifier name both story IDs and refuse the DONE claim.\n'''
    if "## DONE cannot depend on unfinished work" in demo:
        raise RuntimeError("DEMO entry already exists")
    write("DEMO.md", demo.rstrip() + demo_addition + "\n")


def close(implementation_sha: str, focused_summary: str, full_summary: str) -> None:
    short = implementation_sha[:7]
    board = read("BOARD.md")
    in_progress = "- S-06.02.17 · DONE may not depend on unfinished work\n"
    board = replace_once(board, in_progress, "", label="remove S-06.02.17 from IN_PROGRESS")
    board = board.replace("## IN_PROGRESS\n\n", "## IN_PROGRESS\n\n_nothing in flight_\n", 1)
    done = f'''- S-06.02.17 · DONE may not depend on unfinished work
  tests: tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails, tests/test_verify_board.py::test_done_with_only_done_dependencies_passes
  command: uv run pytest tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails tests/test_verify_board.py::test_done_with_only_done_dependencies_passes -q
  result: {focused_summary}; full Python regression {full_summary}
  live: the acceptance fixture places the upstream story in BACKLOG, READY, IN_PROGRESS, IN_REVIEW, BLOCKED and DEFERRED and the verifier refuses every impossible DONE chain while naming both story IDs and the upstream state; an all-DONE chain passes.
  code: scripts/verify_board.py, tests/test_verify_board.py, DEFINITION_OF_DONE.md
  commit: {short}

'''
    board = replace_once(board, "## DONE\n\n", "## DONE\n\n" + done, label="DONE evidence")
    write("BOARD.md", board)

    defects = read("DEFECT_LOG.md")
    defects = replace_once(
        defects,
        "| D-48 | 2026-09-16 | process | high | The verifier allows a DONE story to declare an upstream story that is not DONE | open · `S-06.02.17` |",
        "| D-48 | 2026-09-16 | process | high | The verifier allows a DONE story to declare an upstream story that is not DONE | fixed · `S-06.02.17` |",
        label="close D-48",
    )
    write("DEFECT_LOG.md", defects)

    trace = read("TRACEABILITY.md")
    planned = "| R-102 | S-06.02.17 | 2 | — | — |\n"
    trace = replace_once(trace, planned, "", label="remove planned R-102")
    delivered_anchor = "| R-90 | S-06.02.08 | 2 | `tests/test_verify_board.py`, `tests/test_ci_verifier_environment.py` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md`, `README.md`, `CONTINUE.md` |\n"
    delivered = delivered_anchor + (
        "| R-102 | S-06.02.17 | 2 | `tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails`, "
        "`tests/test_verify_board.py::test_done_with_only_done_dependencies_passes` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md` |\n"
    )
    trace = replace_once(trace, delivered_anchor, delivered, label="deliver R-102")
    write("TRACEABILITY.md", trace)

    retro = read("RETRO.md")
    retro_entry = f'''\n\n---\n\n## 2026-09-17 — S-06.02.17, DONE dependency integrity\n\n**What was cut.** Nothing. The criterion names BACKLOG, READY and BLOCKED; the\nimplementation intentionally covers every non-DONE column instead of maintaining\na narrower list that could miss IN_PROGRESS, IN_REVIEW or DEFERRED later.\n\n**What the estimate got wrong.** The dependency parser and READY enforcement were\nalready correct. The gap was smaller and more dangerous: the same parsed data was\nnever applied to DONE. That let an impossible delivery history pass a green\nverifier even though all the information required to reject it was already present.\n\n**What to change next time.** When a process invariant is defined over a lifecycle,\ntest the invariant across every state, not only the state that first exposed the\nbug. A checker should encode the invariant once and make new impossible states\nfail automatically. Focused evidence: {focused_summary}. Full regression: {full_summary}.\n'''
    if "## 2026-09-17 — S-06.02.17" in retro:
        raise RuntimeError("RETRO entry already exists")
    write("RETRO.md", retro.rstrip() + retro_entry + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: s060217_once.py pull|implement|close [...]")
    phase = sys.argv[1]
    if phase == "pull":
        pull()
    elif phase == "implement":
        implement()
    elif phase == "close":
        if len(sys.argv) != 5:
            raise SystemExit("close needs implementation_sha focused_summary full_summary")
        close(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown phase: {phase}")
