from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def pull() -> None:
    board = read("BOARD.md")
    ready = "- S-06.02.08 · One runner for every evidence command\n"
    in_progress_marker = "## IN_PROGRESS\n\n_nothing in flight_\n"
    if ready not in board:
        raise RuntimeError("S-06.02.08 is not READY")
    board = board.replace(ready, "", 1)
    board = replace_once(
        board,
        in_progress_marker,
        "## IN_PROGRESS\n\n- S-06.02.08 · One runner for every evidence command\n",
        "pull S-06.02.08",
    )
    backlog_marker = "## BACKLOG\n\n*(E-11, waiting on an upstream story rather than on a decision. Each names it.)*\n\n"
    new_board_items = (
        "- S-06.02.16 · Resolve frontend dependency audit findings\n"
        "- S-06.02.17 · DONE may not depend on unfinished work\n"
    )
    board = replace_once(board, backlog_marker, backlog_marker + new_board_items, "add defect stories to board")
    write("BOARD.md", board)

    backlog = read("PRODUCT_BACKLOG.md")
    story_marker = "\n---\n\n## 3b. Amendments to shipped definitions\n"
    stories = """
#### S-06.02.16 — Resolve frontend dependency audit findings
**As an** operator, **I want** the shipped frontend dependency tree free of known
high-severity audit findings, **so that** a clean install does not knowingly
carry a vulnerable production dependency.
- **Given** a clean `npm ci`, **when** the production dependency tree is audited,
  **then** no high-severity finding remains unresolved or silently ignored.
- **Given** a remediation that requires a breaking upgrade, **when** it is
  applied, **then** frontend tests and the production build prove the upgrade
  rather than relying on `npm audit fix --force`.
- **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit
  findings in the shipped frontend tree — target zero.

#### S-06.02.17 — DONE may not depend on unfinished work
**As an** owner, **I want** the verifier to reject a DONE story whose declared
upstream dependency is not DONE, **so that** a green board cannot contain an
impossible delivery history.
- **Given** a DONE story that depends on a READY, BACKLOG or BLOCKED story,
  **when** the verifier runs, **then** it fails and names both stories.
- **Given** a DONE story whose declared dependencies are all DONE, **when** the
  verifier runs, **then** the dependency check passes.
- **Dependencies:** S-06.02.11. **Size:** S. **Indicator:** DONE stories whose
  dependencies are not DONE — target zero.

"""
    backlog = replace_once(backlog, story_marker, stories + story_marker, "add new defect stories")
    coverage_marker = "| R-100 | CI gives the verifier full history and evidence dependencies before it runs | S-06.02.15 |\n"
    coverage = (
        "| R-101 | Frontend production dependencies carry no unresolved high-severity audit finding | S-06.02.16 |\n"
        "| R-102 | A DONE story cannot depend on unfinished work | S-06.02.17 |\n"
    )
    backlog = replace_once(backlog, coverage_marker, coverage_marker + coverage, "add defect requirement coverage")
    write("PRODUCT_BACKLOG.md", backlog)

    defects = read("DEFECT_LOG.md")
    row = "| D-46 | 2026-09-16 | process | high | CI gave the verifier shallow Git history and no frontend dependencies, so truthful DONE evidence looked broken | fixed · `S-06.02.15` |\n"
    new_rows = (
        "| D-47 | 2026-09-16 | security | high | A clean frontend install reports known dependency vulnerabilities, including one high-severity finding | open · `S-06.02.16` |\n"
        "| D-48 | 2026-09-16 | process | high | The verifier allows a DONE story to declare an upstream story that is not DONE | open · `S-06.02.17` |\n"
    )
    defects = replace_once(defects, row, row + new_rows, "log D-47 and D-48")
    write("DEFECT_LOG.md", defects)


def implement() -> None:
    verifier = read("scripts/verify_board.py")
    verifier = replace_once(
        verifier,
        "WIP_LIMIT = 2\n",
        'WIP_LIMIT = 2\nEVIDENCE_RUNNER = "uv run "\n',
        "declare canonical evidence runner",
    )
    needle = """        # Rule 5 — re-run the tests rather than believe the recorded result.\n        if run_tests:\n            command = item.fields[\"command\"]\n            outcome = subprocess.run(\n"""
    replacement = """        # Rule 5 — every evidence command enters the same locked project\n        # environment before it is allowed to run. D-10 existed because some\n        # commands used the ambient Python while others used uv; a verifier that\n        # changes interpreter by story can report environment drift as code drift.\n        command = item.fields[\"command\"].strip()\n        if not command.startswith(EVIDENCE_RUNNER):\n            report.fail(\n                f\"{item.identifier}'s evidence command bypasses the canonical \"\n                f\"runner {EVIDENCE_RUNNER.strip()!r}: {command}\"\n            )\n            continue\n\n        # Re-run the tests rather than believe the recorded result.\n        if run_tests:\n            outcome = subprocess.run(\n"""
    verifier = replace_once(verifier, needle, replacement, "enforce uv evidence runner")
    write("scripts/verify_board.py", verifier)

    board = read("BOARD.md")
    board = re.sub(r"(?m)^  command: python -m pytest ", "  command: uv run pytest ", board)
    lingering = [line for line in board.splitlines() if line.startswith("  command: ") and not line.startswith("  command: uv run ")]
    if lingering:
        raise RuntimeError("non-canonical board commands remain: " + repr(lingering[:5]))
    write("BOARD.md", board)

    tests = read("tests/test_verify_board.py")
    tests = tests.replace('command: python -c "pass"', 'command: uv run python -c "pass"')
    tests = tests.replace('command: python -c "raise SystemExit(1)"', 'command: uv run python -c "raise SystemExit(1)"')
    anchor = """def test_a_failing_evidence_command_fails_the_verifier(tmp_path):\n    \"\"\"The recorded result says passed. The command says otherwise. The command\n    is what counts.\"\"\"\n    board = GOOD_BOARD.replace('command: uv run python -c \"pass\"', 'command: uv run python -c \"raise SystemExit(1)\"')\n    result = run(build(tmp_path, board=board))\n    assert result.returncode == 1\n    assert \"evidence command failed\" in result.stdout\n\n\n"""
    extra = """def test_done_evidence_must_enter_the_locked_uv_runner(tmp_path):\n    board = GOOD_BOARD.replace(\n        'command: uv run python -c \"pass\"',\n        'command: python -c \"pass\"',\n    )\n    result = run(build(tmp_path, board=board), \"--skip-tests\")\n    assert result.returncode == 1\n    assert \"bypasses the canonical runner 'uv run'\" in result.stdout\n\n\n"""
    if extra not in tests:
        tests = replace_once(tests, anchor, anchor + extra, "add evidence runner regression")
    write("tests/test_verify_board.py", tests)

    ci_tests = read("tests/test_ci_verifier_environment.py")
    ci_anchor = """def test_ci_fetches_history_needed_for_evidence_commit_ancestry():\n"""
    ci_extra = """def test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier():\n    text = _workflow()\n    install = text.index(\"name: Install Python dependencies\")\n    sync = text.index(\"uv sync --extra dev --extra email --locked\", install)\n    verifier = text.index(\"name: Verify the board against the repository\")\n    assert install < sync < verifier\n\n\n"""
    if ci_extra not in ci_tests:
        ci_tests = replace_once(ci_tests, ci_anchor, ci_extra + ci_anchor, "pin Python setup before verifier")
    write("tests/test_ci_verifier_environment.py", ci_tests)

    dod = read("DEFINITION_OF_DONE.md")
    dod = dod.replace("  command: python -m pytest tests/test_thing.py -q", "  command: uv run pytest tests/test_thing.py -q")
    runner_rule = "- [ ] **Every evidence command starts with `uv run`.** This is enforced by the\n      verifier so a DONE claim cannot accidentally use a stale ambient Python.\n"
    marker = "- [ ] **The test command was actually run this session** and its output is\n      pasted into the evidence block. Not \"should pass\".\n"
    if runner_rule not in dod:
        dod = replace_once(dod, marker, marker + runner_rule, "document canonical runner in DoD")
    write("DEFINITION_OF_DONE.md", dod)

    readme = read("README.md")
    old = """uv sync --extra dev --extra email --locked\nuv run ruff check --select E9,F63,F7,F82 .\nuv run pytest -q\n\ncd frontend\nnpm ci\nnpm test\nnpm run build\n"""
    new = """uv sync --extra dev --extra email --locked\nnpm ci --prefix frontend\n\nuv run ruff check --select E9,F63,F7,F82 .\nuv run pytest -q\nuv run python scripts/verify_board.py\n\nnpm test --prefix frontend\nnpm run build --prefix frontend\n"""
    readme = replace_once(readme, old, new, "document clean verification setup")
    write("README.md", readme)

    cont = read("CONTINUE.md")
    old = """Run:  uv run python scripts/verify_board.py\n\nThen report, before anything else:\n"""
    new = """On a clean checkout, or after either lockfile changes, prepare the exact\nenvironments the evidence commands use:\n\n  uv sync --extra dev --extra email --locked\n  npm ci --prefix frontend\n\nThen run:  uv run python scripts/verify_board.py\n\nThen report, before anything else:\n"""
    cont = replace_once(cont, old, new, "document session verification setup")
    write("CONTINUE.md", cont)

    ci = read(".github/workflows/ci.yml")
    ci = ci.replace(
        "# it re-runs are not: they invoke `python -m pytest` and, for shipped UI\n      # slices, `npm test`. Run it only after both locked environments exist.",
        "# it re-runs are not. Every board command enters the locked Python\n      # environment with `uv run`; shipped UI evidence also invokes `npm test`.\n      # Run it only after both locked environments exist.",
    )
    write(".github/workflows/ci.yml", ci)


def close(implementation_sha: str, focused_summary: str, full_summary: str) -> None:
    board = read("BOARD.md")
    item = "- S-06.02.08 · One runner for every evidence command\n"
    board = replace_once(board, "## IN_PROGRESS\n\n" + item, "## IN_PROGRESS\n\n_nothing in flight_\n", "clear in progress")
    done_marker = "## DONE\n\n"
    evidence = (
        item
        + "  tests: tests/test_verify_board.py::test_done_evidence_must_enter_the_locked_uv_runner, tests/test_ci_verifier_environment.py::test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier\n"
        + "  command: uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q\n"
        + f"  result: {focused_summary}; full Python regression {full_summary}\n"
        + "  live: every DONE command now starts with uv run; the verifier rejects an ambient-Python command even with --skip-tests; clean-checkout docs and CI install the locked Python and frontend evidence dependencies before verification.\n"
        + "  code: scripts/verify_board.py, tests/test_verify_board.py, tests/test_ci_verifier_environment.py, DEFINITION_OF_DONE.md, README.md, CONTINUE.md\n"
        + f"  commit: {implementation_sha[:7]}\n\n"
    )
    board = replace_once(board, done_marker, done_marker + evidence, "move S-06.02.08 to DONE")
    write("BOARD.md", board)

    defects = read("DEFECT_LOG.md")
    defects = defects.replace("fixed · filed again as `S-06.02.08`", "fixed · `S-06.02.08`")
    write("DEFECT_LOG.md", defects)

    trace = read("TRACEABILITY.md")
    delivered_marker = "| R-100 | S-06.02.15 | 3 | `tests/test_ci_verifier_environment.py`, `tests/test_verify_board.py` | `.github/workflows/ci.yml`, `scripts/verify_board.py` |\n"
    delivered = "| R-90 | S-06.02.08 | 2 | `tests/test_verify_board.py`, `tests/test_ci_verifier_environment.py` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md`, `README.md`, `CONTINUE.md` |\n"
    if delivered not in trace:
        trace = replace_once(trace, delivered_marker, delivered_marker + delivered, "add R-90 delivered traceability")
    planned_marker = "| R-56 | S-07.01.04 | 1 | — | — |\n"
    planned = (
        "| R-101 | S-06.02.16 | 2 | — | — |\n"
        "| R-102 | S-06.02.17 | 2 | — | — |\n"
    )
    if "| R-101 | S-06.02.16" not in trace:
        trace = replace_once(trace, planned_marker, planned_marker + planned, "add planned defect traceability")
    write("TRACEABILITY.md", trace)

    changelog = read("CHANGELOG.md")
    marker = "## Unreleased\n\n"
    entry = """- **Every DONE evidence command now enters one locked runner** (`S-06.02.08`, closing `D-10`). The board uses `uv run` consistently, the verifier rejects commands that bypass it even when tests are skipped, and clean-checkout setup documents both locked Python dependencies and frontend `npm ci` before the verifier.\n- **Two follow-up defects were filed rather than hidden:** `D-47` tracks the frontend dependency audit finding under `S-06.02.16`; `D-48` tracks the verifier gap that allowed a DONE story to depend on unfinished work under `S-06.02.17`.\n\n"""
    changelog = replace_once(changelog, marker, marker + entry, "add S-06.02.08 changelog")
    write("CHANGELOG.md", changelog)

    demo = read("DEMO.md")
    setup_old = """uv sync --locked --extra dev --extra email\n```\n"""
    setup_new = """uv sync --locked --extra dev --extra email\nnpm ci --prefix frontend\n```\n"""
    demo = replace_once(demo, setup_old, setup_new, "make demo setup complete")
    demo_entry = """
---

## S-06.02.08. Evidence uses one runner

```bash
uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q
uv run python scripts/verify_board.py --skip-tests
```

The first command proves the runner contract and clean CI ordering. The second
checks the real board without replaying every historical test; every DONE
`command:` must begin with `uv run`, or the verifier refuses the board.
"""
    if "## S-06.02.08. Evidence uses one runner" not in demo:
        demo += demo_entry
    write("DEMO.md", demo)

    retro = read("RETRO.md")
    retro_entry = """
## 2026-09-16 — S-06.02.08 one evidence runner

- **Cut:** nothing from the story. Cross-language frontend evidence stays on npm, but every board command enters the locked Python project through the same `uv run` gate before verification.
- **Estimate wrong:** the runner drift was smaller than the process drift around it. While tracing the story, the board exposed a DONE dependency on unfinished work (`D-48`), and the clean install repeated the already-seen frontend audit warning (`D-47`); both were filed under new IDs instead of being absorbed here.
- **Next time:** when adding a process rule, add the failing fixture to the verifier in the same increment so the repository can never silently return to the old state.
"""
    if "## 2026-09-16 — S-06.02.08 one evidence runner" not in retro:
        retro += retro_entry
    write("RETRO.md", retro)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: s060208_once.py pull|implement|close ...")
    mode = sys.argv[1]
    if mode == "pull":
        pull()
    elif mode == "implement":
        implement()
    elif mode == "close":
        if len(sys.argv) != 5:
            raise SystemExit("close requires implementation_sha focused_summary full_summary")
        close(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
