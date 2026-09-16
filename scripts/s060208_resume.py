from __future__ import annotations

import re
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


def log_recovery() -> None:
    defects = read("DEFECT_LOG.md")
    old_d47 = "| D-47 | 2026-09-16 | security | high | A clean frontend install reports known dependency vulnerabilities, including one high-severity finding | open · `S-06.02.16` |"
    new_d47 = "| D-47 | 2026-09-16 | security | medium | The frontend development dependency tree reports four audit findings, including a high-severity nanoid advisory; the production tree reports zero | open · `S-06.02.16` |"
    if old_d47 in defects:
        defects = defects.replace(old_d47, new_d47, 1)
    d48 = "| D-48 | 2026-09-16 | process | high | The verifier allows a DONE story to declare an upstream story that is not DONE | open · `S-06.02.17` |\n"
    d49 = "| D-49 | 2026-09-16 | process | medium | A delivery Action tried to push a `.github/workflows/` change with a contents-only token and GitHub rejected the otherwise-tested commit | fixed during `S-06.02.08` — workflow-file writes stay outside Actions |\n"
    if d49 not in defects:
        defects = replace_once(defects, d48, d48 + d49, "log D-49")
    write("DEFECT_LOG.md", defects)

    board = read("BOARD.md")
    board = board.replace(
        "- S-06.02.16 · Resolve frontend dependency audit findings",
        "- S-06.02.16 · Resolve frontend development dependency audit findings",
    )
    write("BOARD.md", board)

    backlog = read("PRODUCT_BACKLOG.md")
    backlog = backlog.replace(
        "#### S-06.02.16 — Resolve frontend dependency audit findings",
        "#### S-06.02.16 — Resolve frontend development dependency audit findings",
    )
    backlog = backlog.replace(
        "**As an** operator, **I want** the shipped frontend dependency tree free of known\nhigh-severity audit findings, **so that** a clean install does not knowingly\ncarry a vulnerable production dependency.",
        "**As an** operator, **I want** the frontend development dependency tree free of\nknown high-severity audit findings, **so that** test and build tooling does not\nknowingly carry a vulnerable package while the production tree remains clean.",
    )
    backlog = backlog.replace(
        "- **Given** a clean `npm ci`, **when** the production dependency tree is audited,\n  **then** no high-severity finding remains unresolved or silently ignored.",
        "- **Given** a clean `npm ci`, **when** `npm audit --omit=dev` runs, **then** the\n  production dependency tree reports zero known vulnerabilities.\n- **Given** the full development dependency tree, **when** `npm audit` runs,\n  **then** no high-severity finding remains unresolved or silently ignored.",
    )
    backlog = backlog.replace(
        "- **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit\n  findings in the shipped frontend tree — target zero.",
        "- **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit\n  findings in the frontend development tree — target zero.",
    )
    backlog = backlog.replace(
        "| R-101 | Frontend production dependencies carry no unresolved high-severity audit finding | S-06.02.16 |",
        "| R-101 | Frontend production dependencies stay audit-clean and development dependencies carry no unresolved high-severity finding | S-06.02.16 |",
    )
    write("PRODUCT_BACKLOG.md", backlog)


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
    lingering = [
        line for line in board.splitlines()
        if line.startswith("  command: ") and not line.startswith("  command: uv run ")
    ]
    if lingering:
        raise RuntimeError("non-canonical board commands remain: " + repr(lingering[:5]))
    write("BOARD.md", board)

    tests = read("tests/test_verify_board.py")
    tests = tests.replace('command: python -c "pass"', 'command: uv run python -c "pass"')
    tests = tests.replace(
        'command: python -c "raise SystemExit(1)"',
        'command: uv run python -c "raise SystemExit(1)"',
    )
    anchor = """def test_a_failing_evidence_command_fails_the_verifier(tmp_path):\n    \"\"\"The recorded result says passed. The command says otherwise. The command\n    is what counts.\"\"\"\n    board = GOOD_BOARD.replace('command: uv run python -c \"pass\"', 'command: uv run python -c \"raise SystemExit(1)\"')\n    result = run(build(tmp_path, board=board))\n    assert result.returncode == 1\n    assert \"evidence command failed\" in result.stdout\n\n\n"""
    extra = """def test_done_evidence_must_enter_the_locked_uv_runner(tmp_path):\n    board = GOOD_BOARD.replace(\n        'command: uv run python -c \"pass\"',\n        'command: python -c \"pass\"',\n    )\n    result = run(build(tmp_path, board=board), \"--skip-tests\")\n    assert result.returncode == 1\n    assert \"bypasses the canonical runner 'uv run'\" in result.stdout\n\n\n"""
    if extra not in tests:
        tests = replace_once(tests, anchor, anchor + extra, "add runner regression")
    write("tests/test_verify_board.py", tests)

    ci_tests = read("tests/test_ci_verifier_environment.py")
    ci_anchor = "def test_ci_fetches_history_needed_for_evidence_commit_ancestry():\n"
    ci_extra = """def test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier():\n    text = _workflow()\n    install = text.index(\"name: Install Python dependencies\")\n    sync = text.index(\"uv sync --extra dev --extra email --locked\", install)\n    verifier = text.index(\"name: Verify the board against the repository\")\n    assert install < sync < verifier\n\n\ndef test_clean_checkout_docs_prepare_both_evidence_environments_before_verification():\n    readme = Path(\"README.md\").read_text(encoding=\"utf-8\")\n    readme_sync = readme.index(\"uv sync --extra dev --extra email --locked\")\n    readme_npm = readme.index(\"npm ci --prefix frontend\", readme_sync)\n    readme_verify = readme.index(\"uv run python scripts/verify_board.py\", readme_npm)\n    assert readme_sync < readme_npm < readme_verify\n\n    handoff = Path(\"CONTINUE.md\").read_text(encoding=\"utf-8\")\n    handoff_sync = handoff.index(\"uv sync --extra dev --extra email --locked\")\n    handoff_npm = handoff.index(\"npm ci --prefix frontend\", handoff_sync)\n    handoff_verify = handoff.index(\"uv run python scripts/verify_board.py\", handoff_npm)\n    assert handoff_sync < handoff_npm < handoff_verify\n\n\n"""
    if "test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier" not in ci_tests:
        ci_tests = replace_once(ci_tests, ci_anchor, ci_extra + ci_anchor, "pin clean setup")
    write("tests/test_ci_verifier_environment.py", ci_tests)

    dod = read("DEFINITION_OF_DONE.md")
    dod = dod.replace(
        "  command: python -m pytest tests/test_thing.py -q",
        "  command: uv run pytest tests/test_thing.py -q",
    )
    runner_rule = (
        "- [ ] **Every evidence command starts with `uv run`.** This is enforced by the\n"
        "      verifier so a DONE claim cannot accidentally use a stale ambient Python.\n"
    )
    marker = (
        "- [ ] **The test command was actually run this session** and its output is\n"
        "      pasted into the evidence block. Not \"should pass\".\n"
    )
    if runner_rule not in dod:
        dod = replace_once(dod, marker, marker + runner_rule, "document canonical runner")
    write("DEFINITION_OF_DONE.md", dod)

    readme = read("README.md")
    old = """uv sync --extra dev --extra email --locked\nuv run ruff check --select E9,F63,F7,F82 .\nuv run pytest -q\n\ncd frontend\nnpm ci\nnpm test\nnpm run build\n"""
    new = """uv sync --extra dev --extra email --locked\nnpm ci --prefix frontend\n\nuv run ruff check --select E9,F63,F7,F82 .\nuv run pytest -q\nuv run python scripts/verify_board.py\n\nnpm test --prefix frontend\nnpm run build --prefix frontend\n"""
    readme = replace_once(readme, old, new, "document clean verification setup")
    write("README.md", readme)

    handoff = read("CONTINUE.md")
    old = "Run:  uv run python scripts/verify_board.py\n\nThen report, before anything else:\n"
    new = """On a clean checkout, or after either lockfile changes, prepare the exact\nenvironments the evidence commands use:\n\n  uv sync --extra dev --extra email --locked\n  npm ci --prefix frontend\n\nThen run:  uv run python scripts/verify_board.py\n\nThen report, before anything else:\n"""
    handoff = replace_once(handoff, old, new, "document session verification setup")
    write("CONTINUE.md", handoff)


def close(implementation_sha: str, focused_summary: str, full_summary: str) -> None:
    board = read("BOARD.md")
    item = "- S-06.02.08 · One runner for every evidence command\n"
    board = replace_once(
        board,
        "## IN_PROGRESS\n\n" + item,
        "## IN_PROGRESS\n\n_nothing in flight_\n",
        "clear in progress",
    )
    evidence = (
        item
        + "  tests: tests/test_verify_board.py::test_done_evidence_must_enter_the_locked_uv_runner, tests/test_ci_verifier_environment.py::test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier, tests/test_ci_verifier_environment.py::test_clean_checkout_docs_prepare_both_evidence_environments_before_verification\n"
        + "  command: uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q\n"
        + f"  result: {focused_summary}; full Python regression {full_summary}\n"
        + "  live: every DONE command now starts with uv run; the verifier rejects ambient-Python evidence even with --skip-tests; clean-checkout docs and CI prepare the locked Python and frontend evidence dependencies before verification.\n"
        + "  code: scripts/verify_board.py, tests/test_verify_board.py, tests/test_ci_verifier_environment.py, DEFINITION_OF_DONE.md, README.md, CONTINUE.md\n"
        + f"  commit: {implementation_sha[:7]}\n\n"
    )
    board = replace_once(board, "## DONE\n\n", "## DONE\n\n" + evidence, "move story to DONE")
    write("BOARD.md", board)

    defects = read("DEFECT_LOG.md")
    defects = defects.replace("fixed · filed again as `S-06.02.08`", "fixed · `S-06.02.08`")
    write("DEFECT_LOG.md", defects)

    trace = read("TRACEABILITY.md")
    marker = "| R-100 | S-06.02.15 | 3 | `tests/test_ci_verifier_environment.py`, `tests/test_verify_board.py` | `.github/workflows/ci.yml`, `scripts/verify_board.py` |\n"
    delivered = "| R-90 | S-06.02.08 | 2 | `tests/test_verify_board.py`, `tests/test_ci_verifier_environment.py` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md`, `README.md`, `CONTINUE.md` |\n"
    if delivered not in trace:
        trace = replace_once(trace, marker, marker + delivered, "add delivered traceability")
    planned_marker = "| R-56 | S-07.01.04 | 1 | — | — |\n"
    planned = (
        "| R-101 | S-06.02.16 | 3 | — | — |\n"
        "| R-102 | S-06.02.17 | 2 | — | — |\n"
    )
    if "| R-101 | S-06.02.16" not in trace:
        trace = replace_once(trace, planned_marker, planned_marker + planned, "add planned traceability")
    write("TRACEABILITY.md", trace)

    changelog = read("CHANGELOG.md")
    entry = """- **Every DONE evidence command now enters one locked runner** (`S-06.02.08`, closing `D-10`). The board uses `uv run` consistently, the verifier rejects commands that bypass it even when tests are skipped, and clean-checkout setup documents both locked Python dependencies and frontend `npm ci` before the verifier.\n- **Delivery failures were recorded instead of hidden.** `D-47` is dev-tooling-only: `npm audit --omit=dev` is clean while the full tree has four findings and is tracked by `S-06.02.16`. `D-48` tracks the missing DONE-dependency check under `S-06.02.17`. `D-49` records the rejected workflow-file push and the transport fix used to finish this story.\n\n"""
    changelog = replace_once(changelog, "## Unreleased\n\n", "## Unreleased\n\n" + entry, "add changelog")
    write("CHANGELOG.md", changelog)

    demo = read("DEMO.md")
    demo = replace_once(
        demo,
        "uv sync --locked --extra dev --extra email\n```\n",
        "uv sync --locked --extra dev --extra email\nnpm ci --prefix frontend\n```\n",
        "complete demo setup",
    )
    section = """
---

## S-06.02.08. Evidence uses one runner

```bash
uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q
uv run python scripts/verify_board.py --skip-tests
```

The first command proves the runner contract and clean-checkout setup. The
second checks the real board without replaying historical tests; every DONE
`command:` must begin with `uv run`, or the verifier refuses the board.
"""
    if "## S-06.02.08. Evidence uses one runner" not in demo:
        demo += section
    write("DEMO.md", demo)

    retro = read("RETRO.md")
    section = """
## 2026-09-16 — S-06.02.08 one evidence runner

- **Cut:** nothing. Frontend evidence still executes npm inside a command that enters the locked project through `uv run`; the story standardises the environment boundary, not the JavaScript test framework.
- **Estimate wrong:** the feature was small, but the repository exposed `D-47`/`D-48`, and the first tested delivery commit was rejected because an Actions token with contents write cannot update workflow files (`D-49`). The tested code was reproduced without that unnecessary workflow-comment mutation rather than weakening permissions.
- **Next time:** delivery workflows must never assume `contents: write` includes `.github/workflows/`; keep workflow mutation and cleanup in the connector/API path, and add the failing process fact to the defect log immediately.
"""
    if "## 2026-09-16 — S-06.02.08 one evidence runner" not in retro:
        retro += section
    write("RETRO.md", retro)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: s060208_resume.py log|implement|close ...")
    if sys.argv[1] == "log":
        log_recovery()
    elif sys.argv[1] == "implement":
        implement()
    elif sys.argv[1] == "close":
        if len(sys.argv) != 5:
            raise SystemExit("close requires implementation_sha focused_summary full_summary")
        close(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown mode: {sys.argv[1]}")


if __name__ == "__main__":
    main()
