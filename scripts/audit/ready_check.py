#!/usr/bin/env python3
"""Which stories could be pulled today, and which are in READY too early.

Standard library only, like `verify_board.py`. This is the audit that found
fourteen stale stories on 2026-09-10; `S-06.02.11` is to fold it into the
verifier so nobody has to remember to run it.

    python scripts/audit/ready_check.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: Story ids contain periods. A dependency pattern of `[^.]*` stops at the first
#: one, so `S-03.02.04` parses as `S-03` and every dependency looks unmet — which
#: is exactly the bug the first version of this script had. Read to `**Size:**`.
DEPENDENCIES = re.compile(r"\*\*Dependencies:\*\*(.*?)\*\*Size:\*\*", re.DOTALL)
STORY_ID = re.compile(r"S-\d+\.\d+\.\d+")


def sections(board: str) -> dict[str, str]:
    where, section = {}, ""
    for line in board.split("\n"):
        if line.startswith("## "):
            section = line[3:].strip()
        found = re.match(r"- (S-[\d.]+) ", line.strip())
        if found:
            where[found.group(1)] = section
    return where


def dependencies(backlog: str) -> dict[str, list[str]]:
    found = {}
    for block in re.split(r"\n#### ", backlog):
        story = re.match(r"(S-[\d.]+)", block)
        if not story:
            continue
        named = DEPENDENCIES.search(block)
        found[story.group(1)] = sorted(set(STORY_ID.findall(named.group(1)))) if named else []
    return found


def blocking_questions(questions: str) -> set[str]:
    """Stories named by a question that has no recorded decision."""
    blocked = set()
    for block in re.split(r"\n### ", questions):
        if not block.startswith("Q-"):
            continue
        if re.search(r"\*\*Status:\*\*\s*answered", block, re.IGNORECASE):
            continue
        header = block.split("\n", 1)[0]
        if "blocks" in header.lower():
            blocked.update(STORY_ID.findall(header))
    return blocked


def main() -> int:
    where = sections((ROOT / "BOARD.md").read_text(encoding="utf-8"))
    needs = dependencies((ROOT / "PRODUCT_BACKLOG.md").read_text(encoding="utf-8"))
    blocked = blocking_questions((ROOT / "OPEN_QUESTIONS.md").read_text(encoding="utf-8"))

    unknown = [
        f"{story} -> {name}"
        for story, named in needs.items()
        for name in named
        if name not in where
    ]
    early = [
        f"{story} waits on {[d for d in needs.get(story, []) if where.get(d) != 'DONE']}"
        for story in sorted(where)
        if where[story] == "READY"
        and any(where.get(d) != "DONE" for d in needs.get(story, []))
    ]
    late = [
        story for story in sorted(where)
        if where[story] == "BACKLOG"
        and story not in blocked
        and all(where.get(d) == "DONE" for d in needs.get(story, []))
    ]

    print(f"{len(where)} stories · {len(blocked)} blocked by an open question\n")
    for title, rows in (
        ("READY too early (a dependency is not DONE)", early),
        ("Dependency names a story that does not exist", unknown),
        ("Could be pulled today but sits in BACKLOG", late),
    ):
        print(f"{title}\n" + "-" * 60)
        print("\n".join(f"  {row}" for row in rows) or "  (none)")
        print()

    if early or unknown:
        print("FAIL — the Definition of Ready is not advisory.")
        return 1
    print("OK — READY is honest." if not late else
          f"OK, but {len(late)} stor{'y' if len(late) == 1 else 'ies'} could move.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
