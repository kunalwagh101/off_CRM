#!/usr/bin/env python3
"""Check the board against the repository. Independently of anything I say.

Run it yourself:

    python scripts/verify_board.py

**This exists because "done" is a claim, and a claim without a check is a
sentence.** Everything here is recomputed from the repository — counts are
never read from a number somebody typed, tests are re-run rather than trusted,
and a file named as evidence is opened to see whether it exists.

Standard library only, deliberately: a verifier that needed installing is one
that stops being run.

Exit codes: ``0`` everything checks out, ``1`` at least one check failed.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "BOARD.md"
BACKLOG = ROOT / "PRODUCT_BACKLOG.md"
QUESTIONS = ROOT / "OPEN_QUESTIONS.md"

COLUMNS = (
    "BACKLOG", "READY", "IN_PROGRESS", "IN_REVIEW", "BLOCKED", "DONE", "DEFERRED",
)
WIP_LIMIT = 2

#: `- S-01.02.03 · Title`
ITEM = re.compile(r"^-\s+(?P<id>[EFST]-[\d.]+[a-z]?)\s+·\s+(?P<title>.+?)\s*$")
#: An indented `key: value` beneath an item.
FIELD = re.compile(r"^\s+(?P<key>[a-z_]+):\s*(?P<value>.+?)\s*$")
#: `#### S-01.02.03 — Title` in the backlog.
DEFINITION = re.compile(r"^#{2,4}\s+(?P<id>[EFST]-[\d.]+[a-z]?)\s+[—-]\s+(?P<title>.+?)\s*$")
#: A coverage row: `| R-01 | text | S-01.02.03, S-01.02.04 |`
COVERAGE = re.compile(r"^\|\s*(?P<req>R-\d+)\s*\|(?P<text>[^|]*)\|\s*(?P<ids>[^|]*)\|")
#: Words that mean "not finished" wherever they appear in a comment.
UNFINISHED = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")

#: Acceptance criteria in the backlog are `- **Given** … **then** …`.
CRITERION = re.compile(r"^-\s+\*\*Given\*\*", re.M)


@dataclass
class Item:
    identifier: str
    title: str
    column: str
    fields: dict[str, str] = field(default_factory=dict)
    line: int = 0


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def ok(self) -> bool:
        return not self.failures


# ── reading the two files ───────────────────────────────────────────────────


def read_board(path: Path, report: Report) -> list[Item]:
    """Parse BOARD.md into items. A column heading that is not one of the
    declared columns is itself a failure — a typo would otherwise silently
    create a column nobody counts."""
    if not path.exists():
        report.fail(f"{path.name} does not exist. The board is the source of truth.")
        return []

    items: list[Item] = []
    column = ""
    current: Item | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        heading = re.match(r"^##\s+([A-Z_]+)\s*$", raw)
        if heading:
            column = heading.group(1)
            current = None
            if column not in COLUMNS:
                report.fail(
                    f"{path.name}:{number} — '{column}' is not a declared column. "
                    f"Declared: {', '.join(COLUMNS)}."
                )
            continue

        match = ITEM.match(raw)
        if match and column:
            current = Item(
                identifier=match.group("id"), title=match.group("title"),
                column=column, line=number,
            )
            items.append(current)
            continue

        detail = FIELD.match(raw)
        if detail and current is not None:
            current.fields[detail.group("key")] = detail.group("value")
    return items


def read_backlog(path: Path, report: Report) -> tuple[dict[str, str], dict[str, list[str]], dict[str, int]]:
    """Returns (defined ids → title, requirement → ids, story id → criteria count)."""
    if not path.exists():
        report.fail(f"{path.name} does not exist. Nothing can be traced without it.")
        return {}, {}, {}

    text = path.read_text(encoding="utf-8")
    defined: dict[str, str] = {}
    criteria: dict[str, int] = {}

    # Split on definitions so each story's criteria can be counted against it.
    blocks = re.split(r"(?m)^(#{2,4}\s+[EFST]-[\d.]+[a-z]?\s+[—-]\s+.+)$", text)
    for index in range(1, len(blocks), 2):
        header = DEFINITION.match(blocks[index].strip())
        if not header:
            continue
        identifier = header.group("id")
        defined[identifier] = header.group("title")
        body = blocks[index + 1] if index + 1 < len(blocks) else ""
        criteria[identifier] = len(CRITERION.findall(body))

    coverage: dict[str, list[str]] = {}
    for line in text.splitlines():
        row = COVERAGE.match(line)
        if not row:
            continue
        ids = [piece.strip() for piece in row.group("ids").split(",") if piece.strip()]
        coverage[row.group("req")] = ids
    return defined, coverage, criteria


# ── the checks ──────────────────────────────────────────────────────────────


def check_coverage(coverage: dict[str, list[str]], defined: dict[str, str], report: Report) -> None:
    """Rule 2: no requirement without a backlog ID, and no ID that does not exist."""
    if not coverage:
        report.fail("The coverage table is empty. Every requirement must map to an ID.")
    for requirement, ids in sorted(coverage.items()):
        if not ids:
            report.fail(f"{requirement} is an orphan requirement — no backlog ID covers it.")
            continue
        for identifier in ids:
            if identifier not in defined:
                report.fail(
                    f"{requirement} names {identifier}, which is not defined in "
                    f"{BACKLOG.name}."
                )


def check_board_completeness(
    items: list[Item], defined: dict[str, str], report: Report
) -> None:
    """Rule 3: every story defined in the backlog appears on the board, once."""
    seen: dict[str, list[Item]] = {}
    for item in items:
        seen.setdefault(item.identifier, []).append(item)

    for identifier, entries in sorted(seen.items()):
        if len(entries) > 1:
            columns = ", ".join(f"{entry.column}:{entry.line}" for entry in entries)
            report.fail(f"{identifier} is on the board more than once ({columns}).")
        if identifier not in defined:
            report.fail(
                f"{identifier} is on the board at line {entries[0].line} but is not "
                f"defined in {BACKLOG.name}."
            )

    stories = {key for key in defined if key.startswith("S-")}
    for identifier in sorted(stories - set(seen)):
        report.fail(f"{identifier} is defined in the backlog and is not on the board.")


def check_wip(items: list[Item], report: Report) -> None:
    in_progress = [item for item in items if item.column == "IN_PROGRESS"]
    if len(in_progress) > WIP_LIMIT:
        names = ", ".join(item.identifier for item in in_progress)
        report.fail(
            f"WIP limit is {WIP_LIMIT} and {len(in_progress)} items are IN_PROGRESS "
            f"({names}). Finish or escalate before pulling more."
        )


def check_blocked(items: list[Item], report: Report) -> None:
    """A blocked item with no escalation is a process violation, not a status."""
    known = set()
    if QUESTIONS.exists():
        known = set(re.findall(r"^###\s+(Q-\d+)", QUESTIONS.read_text(encoding="utf-8"), re.M))
    for item in items:
        if item.column != "BLOCKED":
            continue
        reason = item.fields.get("blocked", "")
        if not reason:
            report.fail(
                f"{item.identifier} is BLOCKED with no escalation. It needs a linked "
                "Q-nn or a named external dependency."
            )
            continue
        for question in re.findall(r"Q-\d+", reason):
            if question not in known:
                report.fail(
                    f"{item.identifier} is blocked on {question}, which is not in "
                    f"{QUESTIONS.name}."
                )


def check_ready(items: list[Item], report: Report) -> None:
    """Definition of Ready: nothing enters READY with an open question against it."""
    if not QUESTIONS.exists():
        return
    text = QUESTIONS.read_text(encoding="utf-8")
    for item in items:
        if item.column != "READY":
            continue
        if re.search(rf"\b{re.escape(item.identifier)}\b", text):
            report.fail(
                f"{item.identifier} is READY but has an open question filed against "
                "it. An answer may change its shape."
            )


def check_deferred(items: list[Item], report: Report) -> None:
    """Scope is never silently dropped: DEFERRED needs a reason and a trigger."""
    for item in items:
        if item.column != "DEFERRED":
            continue
        for required in ("reason", "trigger"):
            if not item.fields.get(required):
                report.fail(
                    f"{item.identifier} is DEFERRED with no {required}. Cut scope "
                    "carries both, or it is scope that vanished."
                )


# ── evidence ────────────────────────────────────────────────────────────────


def _resolve_code(reference: str) -> tuple[Path, tuple[int, int] | None, str]:
    """`path`, `path:88`, or `path:88-140`."""
    span: tuple[int, int] | None = None
    text = reference.strip()
    match = re.match(r"^(?P<path>[^:]+):(?P<start>\d+)(?:-(?P<end>\d+))?$", text)
    if match:
        text = match.group("path")
        start = int(match.group("start"))
        span = (start, int(match.group("end") or start))
    return ROOT / text, span, text


def check_evidence(items: list[Item], report: Report, *, run_tests: bool) -> tuple[int, int]:
    """Rules 4, 5 and 6. Returns (tests run, tests passed)."""
    ran = passed = 0
    for item in items:
        if item.column != "DONE":
            continue
        missing = [key for key in ("tests", "command", "result", "code")
                   if not item.fields.get(key)]
        if missing:
            report.fail(
                f"{item.identifier} is DONE with no {', '.join(missing)} in its "
                "evidence block."
            )
            continue

        if item.fields.get("result", "").strip().lower().startswith("pending"):
            report.fail(
                f"{item.identifier} is DONE with a pending result. A story with code "
                "but no run test is IN_REVIEW, not DONE."
            )

        # Rule 4 — every named file exists, and a line range is inside the file.
        for reference in item.fields["code"].split(","):
            path, span, shown = _resolve_code(reference)
            if not path.exists():
                report.fail(f"{item.identifier} names code {shown!r}, which does not exist.")
                continue
            if span is not None:
                length = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                if span[1] > length:
                    report.fail(
                        f"{item.identifier} names {shown!r} but that file has "
                        f"{length} lines."
                    )
            # Rule 6 — a finished slice contains no unfinished markers.
            for problem in unfinished_markers(path):
                report.fail(f"{item.identifier} is DONE but {problem}")

        for reference in item.fields["tests"].split(","):
            test_path = ROOT / reference.strip().split("::")[0]
            if not test_path.exists():
                report.fail(
                    f"{item.identifier} names test {reference.strip()!r}, which does "
                    "not exist."
                )

        # Rule 5 — re-run the tests rather than believe the recorded result.
        if run_tests:
            command = item.fields["command"]
            outcome = subprocess.run(
                command, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=900,
            )
            ran += 1
            if outcome.returncode == 0:
                passed += 1
            else:
                tail = (outcome.stdout or outcome.stderr).strip().splitlines()[-3:]
                report.fail(
                    f"{item.identifier}'s evidence command failed: {command}\n"
                    + "\n".join(f"      {line}" for line in tail)
                )
    return ran, passed


def unfinished_markers(path: Path) -> list[str]:
    """TODO/FIXME in a *comment*, and functions whose body is a stub.

    Comments are found with `tokenize` rather than a regex over the whole file,
    so the word "TODO" inside a string or a docstring — which is prose, not an
    unfinished path — does not trip it. Stubs are found with `ast`, so a `pass`
    that is the entire body of a function is caught while a `pass` inside an
    `except` block is not.
    """
    if path.suffix != ".py" or not path.exists():
        return []
    source = path.read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []

    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and UNFINISHED.search(token.string):
                problems.append(
                    f"{path.relative_to(ROOT)}:{token.start[0]} still carries "
                    f"{UNFINISHED.search(token.string).group(1)}."
                )
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return problems

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [step for step in node.body if not _is_docstring(step)]
        if len(body) != 1:
            continue
        only = body[0]
        if isinstance(only, ast.Pass):
            problems.append(
                f"{path.relative_to(ROOT)}:{node.lineno} — {node.name}() is a "
                "pass-stub."
            )
        elif isinstance(only, ast.Raise):
            raised = only.exc
            name = getattr(raised, "id", None) or getattr(
                getattr(raised, "func", None), "id", None
            )
            if name == "NotImplementedError":
                problems.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} — {node.name}() raises "
                    "NotImplementedError."
                )
    return problems


def _is_docstring(step: ast.stmt) -> bool:
    return isinstance(step, ast.Expr) and isinstance(step.value, ast.Constant) and isinstance(
        step.value.value, str
    )


# ── the summary ─────────────────────────────────────────────────────────────


def summarise(
    items: list[Item],
    defined: dict[str, str],
    coverage: dict[str, list[str]],
    criteria: dict[str, int],
    tests: tuple[int, int],
    report: Report,
) -> str:
    """Counts recomputed from the repository, never typed in."""
    lines = ["", "BOARD", "-" * 60]
    by_column = {column: [item for item in items if item.column == column] for column in COLUMNS}
    total = sum(len(entries) for entries in by_column.values())
    for column in COLUMNS:
        entries = by_column[column]
        bar = "#" * min(len(entries), 40)
        limit = f"  (limit {WIP_LIMIT})" if column == "IN_PROGRESS" else ""
        lines.append(f"  {column:<13} {len(entries):>3}  {bar}{limit}")
    lines.append(f"  {'TOTAL':<13} {total:>3}")

    done = by_column["DONE"]
    covered = sum(criteria.get(item.identifier, 0) for item in done)
    everything = sum(criteria.values()) or 1
    lines += [
        "",
        "COVERAGE",
        "-" * 60,
        f"  requirements mapped     {len(coverage)}",
        f"  backlog IDs defined     {len(defined)}",
        f"  acceptance criteria     {everything if everything != 1 else 0}",
        f"  criteria behind a DONE  {covered}  ({round(covered / everything * 100)}%)",
        f"  evidence commands run   {tests[0]}, passed {tests[1]}",
    ]

    remaining = [item for item in items if item.column not in ("DONE", "DEFERRED")]
    lines += ["", f"NOT BUILT YET ({len(remaining)})", "-" * 60]
    for item in remaining:
        marker = {"BLOCKED": "!", "IN_PROGRESS": ">", "IN_REVIEW": "?"}.get(item.column, " ")
        lines.append(f"  {marker} {item.identifier:<12} {item.column:<12} {item.title}")

    if report.notes:
        lines += ["", "NOTES", "-" * 60]
        lines += [f"  {note}" for note in report.notes]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-tests", action="store_true",
        help="Parse and check the board without re-running evidence commands.",
    )
    arguments = parser.parse_args()

    report = Report()
    defined, coverage, criteria = read_backlog(BACKLOG, report)
    items = read_board(BOARD, report)

    check_coverage(coverage, defined, report)
    check_board_completeness(items, defined, report)
    check_wip(items, report)
    check_blocked(items, report)
    check_ready(items, report)
    check_deferred(items, report)
    tests = check_evidence(items, report, run_tests=not arguments.skip_tests)
    if arguments.skip_tests:
        report.note("Evidence commands were not run (--skip-tests).")

    print(summarise(items, defined, coverage, criteria, tests, report))

    if report.failures:
        print("")
        print(f"FAILED — {len(report.failures)} problem(s)")
        print("-" * 60)
        for failure in report.failures:
            print(f"  x {failure}")
        return 1

    print("")
    print("OK — the board matches the repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
