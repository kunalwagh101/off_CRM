#!/usr/bin/env python3
"""Run one DONE story's replayable evidence through one deterministic runner.

The board names *what* proves a story in its ``tests:`` field. This script owns
*how* those tests are run. Python evidence always uses this process's exact
interpreter; frontend evidence always uses the repository's npm test command.
No board entry is allowed to smuggle in a second shell, interpreter or virtual
environment.

Documented verification setup:

    uv sync --extra dev --extra email --locked
    npm ci --prefix frontend
    uv run --no-sync python scripts/verify_board.py

The verifier launches this script with ``sys.executable``, so every Python
story is replayed in the exact environment that launched the verifier.
Environment-gated ``verification/`` files remain live evidence and are not
silently promoted into the deterministic replay set.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # imported as scripts.run_evidence in tests
    from .verify_board import BOARD, Report, read_board
except ImportError:  # executed as `python scripts/run_evidence.py`
    from verify_board import BOARD, Report, read_board

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CANONICAL_COMMAND = "python scripts/run_evidence.py"


class EvidenceError(RuntimeError):
    """The board's evidence cannot be replayed deterministically."""


@dataclass(frozen=True)
class EvidencePlan:
    story: str
    python: tuple[str, ...]
    frontend: tuple[str, ...]
    live_only: tuple[str, ...]


def command_for(story: str) -> str:
    """The only command shape a DONE board item may record."""
    return f"{CANONICAL_COMMAND} {story}"


def plan_for(story: str, *, board: Path = BOARD) -> EvidencePlan:
    """Resolve one DONE item's declared tests into replayable phases.

    The ``tests:`` field stays the source of truth. A path is classified by the
    repository boundary it belongs to; arbitrary commands and arbitrary paths
    are not accepted here.
    """
    report = Report()
    items = read_board(board, report)
    if report.failures:
        raise EvidenceError("; ".join(report.failures))

    item = next((entry for entry in items if entry.identifier == story), None)
    if item is None:
        raise EvidenceError(f"{story} is not on the board")
    if item.column != "DONE":
        raise EvidenceError(f"{story} is {item.column}, not DONE")

    raw = item.fields.get("tests", "")
    if not raw:
        raise EvidenceError(f"{story} has no tests field")

    python: list[str] = []
    frontend: list[str] = []
    live_only: list[str] = []
    for piece in raw.split(","):
        target = piece.strip()
        if not target:
            continue
        path = target.split("::", 1)[0]
        if path.startswith("tests/"):
            python.append(target)
        elif path.startswith("frontend/"):
            relative = path[len("frontend/") :]
            if not relative or relative.startswith("-") or ".." in Path(relative).parts:
                raise EvidenceError(f"{story} has unsafe frontend test path {target!r}")
            frontend.append(relative)
        elif path.startswith("verification/"):
            # Live/deployment acceptance is recorded separately in `live:`. The
            # board's replay must work in a clean checkout without credentials,
            # browsers, Docker or production infrastructure.
            live_only.append(target)
        else:
            raise EvidenceError(
                f"{story} has unsupported test target {target!r}; replayable evidence "
                "must live under tests/ or frontend/, with verification/ reserved "
                "for live evidence"
            )

    if not python and not frontend:
        raise EvidenceError(
            f"{story} has no replayable tests; live verification alone cannot make DONE"
        )
    return EvidencePlan(story, tuple(python), tuple(frontend), tuple(live_only))


def run_plan(plan: EvidencePlan) -> int:
    """Run the plan without a shell, failing on the first red phase."""
    if plan.python:
        outcome = subprocess.run(
            [sys.executable, "-m", "pytest", *plan.python, "-q"],
            cwd=ROOT,
            check=False,
        )
        if outcome.returncode:
            return int(outcome.returncode)

    if plan.frontend:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            raise EvidenceError(
                "npm is not available. Run the documented verification setup first."
            )
        outcome = subprocess.run(
            [npm, "test", "--", *plan.frontend],
            cwd=FRONTEND,
            check=False,
        )
        if outcome.returncode:
            return int(outcome.returncode)

    return 0


def main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    if len(args) != 1:
        print("usage: python scripts/run_evidence.py S-nn.nn.nn", file=sys.stderr)
        return 2
    try:
        plan = plan_for(args[0])
        if plan.live_only:
            print(
                "live-only evidence not replayed here: " + ", ".join(plan.live_only),
                file=sys.stderr,
            )
        return run_plan(plan)
    except EvidenceError as exc:
        print(f"evidence error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
