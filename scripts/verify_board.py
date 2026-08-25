#!/usr/bin/env python3
"""Check BUILD_STATE.md's claims against the repository.

BUILD_STATE.md is the board. Section 3 is the DONE column, section 4 is the
backlog, section 6 is what is blocked on an owner decision. This script exists
because a written "done" is a claim, and a claim nobody can check is worth
nothing: it re-derives the answer from the repo instead of trusting the prose.

For every entry in the DONE column it requires a BOARD block naming the tests
and the code, then:

  * every cited code path and test target must exist on disk
  * every DONE item must name at least one test (no test -> not DONE)
  * the cited tests are executed, and their real outcome is attributed back to
    the item that leans on them
  * cited code is scanned for TODO/FIXME markers left inside "finished" work

Exit code is 0 only when every DONE claim survives all four. Run it yourself:

    python scripts/verify_board.py           # full check, runs the tests
    python scripts/verify_board.py --no-run  # structure and paths only, fast

Standard library only, so it works in any checkout without an install step.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD_FILE = ROOT / "BUILD_STATE.md"

DONE_SECTION = "## 3. Done"
BACKLOG_SECTION = "## 4. Not built yet"
BLOCKED_SECTION = "## 6. Open questions for the owner"

# Statuses an entry in the DONE column may carry. Only DONE counts as finished;
# the other two are honest declarations that something is not, and they are
# reported rather than hidden.
STATUSES = {"DONE", "IN_REVIEW", "PARTIAL"}

# A marker left inside code an item calls finished. NotImplementedError is
# deliberately not here: this repo uses it for abstract base methods that
# concrete backends fill in (db/connection.py), which is design, not a stub.
# Those are reported as notes instead, so a real one still surfaces.
STUB_MARKERS = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")

BOARD_RE = re.compile(r"^>\s*\*\*BOARD\*\*\s*`([\w.-]+)`\s*·\s*status\s*`(\w+)`\s*$")
FIELD_RE = re.compile(r"^>\s*(\w+):\s*(.*)$")


class Item:
    """One entry in the DONE column, with the evidence it claims."""

    def __init__(self, ident: str, title: str, status: str, line: int) -> None:
        self.id = ident
        self.title = title
        self.status = status
        self.line = line
        self.tests: list[str] = []
        self.code: list[str] = []
        self.gap = ""
        self.failures: list[str] = []
        self.notes: list[str] = []
        self.ran = 0
        self.passed = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def fail(self, msg: str) -> None:
        self.failures.append(msg)


def _sections(text: str) -> dict[str, tuple[int, int]]:
    """Line ranges of every level-2 section, keyed by heading."""
    heads = [(i, ln) for i, ln in enumerate(text.split("\n")) if ln.startswith("## ")]
    total = len(text.split("\n"))
    out = {}
    for pos, (i, ln) in enumerate(heads):
        end = heads[pos + 1][0] if pos + 1 < len(heads) else total
        out[ln.strip()] = (i, end)
    return out


def _split(value: str) -> list[str]:
    """`a.py`, `b.py` -> ['a.py', 'b.py']; NONE -> []."""
    parts = [p.strip().strip("`").strip() for p in value.split(",")]
    return [p for p in parts if p and p.upper() != "NONE"]


def parse_board(text: str) -> tuple[list[Item], list[str], int, int]:
    """Return (done-column items, entries missing a BOARD block, backlog, blocked)."""
    lines = text.split("\n")
    sections = _sections(text)
    missing = sections.keys() - {DONE_SECTION, BACKLOG_SECTION, BLOCKED_SECTION}
    for required in (DONE_SECTION, BACKLOG_SECTION, BLOCKED_SECTION):
        if required not in sections:
            raise SystemExit(f"BUILD_STATE.md has no '{required}' section — board unreadable")
    del missing

    start, end = sections[DONE_SECTION]
    items: list[Item] = []
    unboarded: list[str] = []
    current_title = None
    current_line = 0
    current: Item | None = None

    for i in range(start, end):
        line = lines[i]
        if line.startswith("### "):
            if current_title is not None and current is None:
                unboarded.append(current_title)
            current_title = line[4:].strip()
            current_line = i + 1
            current = None
            continue
        board = BOARD_RE.match(line)
        if board and current_title is not None:
            current = Item(board.group(1), current_title, board.group(2), current_line)
            items.append(current)
            continue
        field = FIELD_RE.match(line)
        if field and current is not None:
            key, value = field.group(1).lower(), field.group(2)
            if key == "tests":
                current.tests = _split(value)
            elif key == "code":
                current.code = _split(value)
            elif key == "gap":
                current.gap = value.strip()
    if current_title is not None and current is None:
        unboarded.append(current_title)

    b_start, b_end = sections[BACKLOG_SECTION]
    backlog = sum(
        1
        for ln in lines[b_start:b_end]
        if ln.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln) and "| Item |" not in ln
    )
    q_start, q_end = sections[BLOCKED_SECTION]
    blocked = sum(1 for ln in lines[q_start:q_end] if re.match(r"^\d+[a-z]?\.\s", ln))
    return items, unboarded, backlog, blocked


def check_paths(items: list[Item]) -> None:
    """Every cited path must resolve, and a DONE item must cite a test."""
    seen: dict[str, Item] = {}
    for item in items:
        if item.id in seen:
            item.fail(f"duplicate board id, also used by '{seen[item.id].title}'")
        seen[item.id] = item
        if item.status not in STATUSES:
            item.fail(f"unknown status '{item.status}' (expected one of {sorted(STATUSES)})")
        if item.status == "DONE" and not item.tests:
            item.fail("status DONE with no test named — evidence ledger requires one")
        if not item.code:
            item.fail("no code path named")
        for path in item.code + item.tests:
            target = path.split("::", 1)[0]
            if not (ROOT / target).exists():
                item.fail(f"cited path does not exist: {target}")


def scan_stubs(items: list[Item]) -> None:
    """A finished item should not still carry work markers in the code it cites."""
    for item in items:
        for path in item.code:
            file = ROOT / path
            if not file.is_file() or file.suffix not in {".py", ".ts", ".tsx"}:
                continue
            for number, line in enumerate(file.read_text(errors="replace").split("\n"), 1):
                if STUB_MARKERS.search(line):
                    where = f"{path}:{number}"
                    if item.status == "DONE":
                        item.fail(f"work marker inside DONE code: {where}")
                    else:
                        item.notes.append(f"work marker: {where}")
                if "NotImplementedError" in line:
                    item.notes.append(f"NotImplementedError at {path}:{number}")


def _module_file(classname: str) -> str:
    """pytest classname 'tests.test_x.Klass' -> 'tests/test_x.py'."""
    parts = classname.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = "/".join(parts[:cut]) + ".py"
        if (ROOT / candidate).exists():
            return candidate
    return parts[0] + ".py" if parts else ""


def run_python(items: list[Item]) -> None:
    """Run every cited pytest target once, then attribute outcomes back."""
    targets = sorted({t for i in items for t in i.tests if t.startswith("tests/")})
    if not targets:
        return
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as handle:
        report = Path(handle.name)
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", *targets, "-q", "--no-header",
             f"--junitxml={report}", "-o", "junit_family=xunit2"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if not report.exists() or not report.stat().st_size:
            for item in items:
                if any(t.startswith("tests/") for t in item.tests):
                    item.fail("pytest produced no report — the suite could not run")
            return
        outcomes: dict[str, list[tuple[str, bool]]] = {}
        for case in ET.parse(report).getroot().iter("testcase"):
            file = case.get("file") or _module_file(case.get("classname", ""))
            good = not any(case.find(tag) is not None for tag in ("failure", "error"))
            outcomes.setdefault(file, []).append((case.get("name", "?"), good))
    finally:
        report.unlink(missing_ok=True)

    for item in items:
        for target in item.tests:
            if not target.startswith("tests/"):
                continue
            file, _, node = target.partition("::")
            cases = outcomes.get(file, [])
            if node:
                cases = [c for c in cases if c[0] == node or c[0].startswith(node + "[")]
            if not cases:
                item.fail(f"no test ran for {target} — it does not exist or was not collected")
                continue
            item.ran += len(cases)
            item.passed += sum(1 for _, good in cases if good)
            for name, good in cases:
                if not good:
                    item.fail(f"failing test behind this claim: {file}::{name}")


def run_frontend(items: list[Item]) -> None:
    """Same, for the vitest targets — a UI claim needs a UI check."""
    targets = sorted({t for i in items for t in i.tests if t.startswith("frontend/")})
    if not targets:
        return
    relative = [t[len("frontend/"):] for t in targets]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        report = Path(handle.name)
    try:
        subprocess.run(
            ["npx", "vitest", "run", *relative, "--reporter=json", f"--outputFile={report}"],
            cwd=ROOT / "frontend", capture_output=True, text=True, check=False,
        )
        if not report.exists() or not report.stat().st_size:
            for item in items:
                if any(t.startswith("frontend/") for t in item.tests):
                    item.fail("vitest produced no report — the frontend suite could not run")
            return
        data = json.loads(report.read_text())
    finally:
        report.unlink(missing_ok=True)

    outcomes: dict[str, tuple[int, int]] = {}
    for suite in data.get("testResults", []):
        name = Path(suite.get("name", "")).resolve()
        try:
            key = "frontend/" + str(name.relative_to((ROOT / "frontend").resolve()))
        except ValueError:
            continue
        cases = suite.get("assertionResults", [])
        good = sum(1 for c in cases if c.get("status") == "passed")
        outcomes[key] = (len(cases), good)

    for item in items:
        for target in item.tests:
            if not target.startswith("frontend/"):
                continue
            if target not in outcomes:
                item.fail(f"no frontend test ran for {target}")
                continue
            total, good = outcomes[target]
            item.ran += total
            item.passed += good
            if good != total:
                item.fail(f"{total - good} failing frontend test(s) in {target}")


def report(items: list[Item], unboarded: list[str], backlog: int, blocked: int, ran: bool) -> int:
    columns = {status: [i for i in items if i.status == status] for status in sorted(STATUSES)}
    broken = [i for i in items if not i.ok]

    print("\n" + "=" * 72)
    print("BOARD — BUILD_STATE.md, re-derived from the repository")
    print("=" * 72)
    print(f"  DONE (verified)     {len([i for i in columns['DONE'] if i.ok]):>4}")
    print(f"  DONE (claim failed) {len([i for i in columns['DONE'] if not i.ok]):>4}")
    print(f"  IN_REVIEW           {len(columns['IN_REVIEW']):>4}   built, not proven here")
    print(f"  PARTIAL             {len(columns['PARTIAL']):>4}   named gap, see 'gap:'")
    print(f"  BACKLOG             {backlog:>4}   section 4 rows")
    print(f"  BLOCKED             {blocked:>4}   section 6, waiting on an owner decision")
    if ran:
        tests_run = sum(i.ran for i in items)
        tests_ok = sum(i.passed for i in items)
        print(f"\n  tests executed behind these claims: {tests_ok}/{tests_run} passed")
    else:
        print("\n  --no-run: no tests were executed, so nothing here is proven to work")

    not_done = columns["IN_REVIEW"] + columns["PARTIAL"]
    if not_done:
        print("\n--- NOT FINISHED, stated plainly -------------------------------------")
        for item in sorted(not_done, key=lambda i: i.id):
            print(f"  {item.id:<8} {item.status:<10} {item.title}")
            if item.gap:
                print(f"           gap: {item.gap}")

    notes = [(i, n) for i in items for n in i.notes]
    if notes:
        print("\n--- NOTES (not failures) ---------------------------------------------")
        for item, note in notes[:20]:
            print(f"  {item.id:<8} {note}")
        if len(notes) > 20:
            print(f"  ... and {len(notes) - 20} more")

    if unboarded:
        print("\n--- ENTRIES WITH NO BOARD BLOCK --------------------------------------")
        for title in unboarded:
            print(f"  {title}")

    if broken or unboarded:
        print("\n--- FAILED CLAIMS ----------------------------------------------------")
        for item in broken:
            print(f"  {item.id}  {item.title}  (BUILD_STATE.md:{item.line})")
            for failure in item.failures:
                print(f"      - {failure}")
        count = len(broken) + len(unboarded)
        print(f"\nFAIL: {count} board entr{'y' if count == 1 else 'ies'} could not be verified.")
        print("=" * 72)
        return 1

    if ran:
        print("\nOK: every DONE claim resolves to code and to a test that passes.")
    else:
        print("\nOK so far: paths and structure hold. Drop --no-run to prove the tests pass.")
    print("=" * 72)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--no-run", action="store_true",
                        help="skip test execution; check structure, paths and stubs only")
    args = parser.parse_args()

    items, unboarded, backlog, blocked = parse_board(BOARD_FILE.read_text())
    check_paths(items)
    scan_stubs(items)
    if not args.no_run:
        run_python(items)
        run_frontend(items)
    return report(items, unboarded, backlog, blocked, not args.no_run)


if __name__ == "__main__":
    raise SystemExit(main())
