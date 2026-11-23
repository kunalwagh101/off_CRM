"""Keep F-06.02 tracking bounded to its own stories, not later feature text."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "PRODUCT_BACKLOG.md"
TRACKER = ROOT / "docs/evidence/2026-11-22-f0602-feature-tracker.md"


def _sections(text: str, heading_level: int) -> dict[str, str]:
    lines = text.splitlines()
    sections: dict[str, str] = {}
    current: str | None = None
    collected: list[str] = []
    story = re.compile(r"^" + "#" * heading_level + r" (S-06\.02\.\d{2})\b")
    boundary = re.compile(r"^#{1," + str(heading_level) + r"} ")
    for line in lines:
        match = story.match(line)
        if match:
            if current is not None:
                sections[current] = "\n".join(collected)
            current = match.group(1)
            collected = []
        elif current is not None and boundary.match(line):
            sections[current] = "\n".join(collected)
            current = None
        elif current is not None:
            collected.append(line)
    if current is not None:
        sections[current] = "\n".join(collected)
    return sections


def test_f0602_tracker_does_not_cross_feature_boundaries() -> None:
    backlog = _sections(BACKLOG.read_text(encoding="utf-8"), 4)
    tracker = _sections(TRACKER.read_text(encoding="utf-8"), 3)
    story_ids = {f"S-06.02.{i:02}" for i in range(1, 70)}
    assert set(backlog) == story_ids
    assert set(tracker) == story_ids
    for story_id, source in sorted(backlog.items()):
        expected = len(re.findall(r"(?m)^- \*\*Given\*\*", source))
        stated = re.search(r"\*\*Acceptance sub-cases \((\d+) written\):\*\*", tracker[story_id])
        assert stated is not None, story_id
        assert int(stated.group(1)) == expected, story_id
        numbered = re.findall(r"(?m)^\d+\. \*\*Given\*\*", tracker[story_id])
        assert len(numbered) == expected, story_id


def test_unrelated_requirements_not_assigned_to_security_stories() -> None:
    tracker = _sections(TRACKER.read_text(encoding="utf-8"), 3)
    assert "S-12.01.01" not in tracker["S-06.02.20"]
    assert "S-07.01.01" not in tracker["S-06.02.69"]
    assert "T-07.01.04.a" not in tracker["S-06.02.69"]


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _source_cases(text: str) -> list[str]:
    cases: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("- **Given**"):
            if current is not None:
                cases.append(_normalise(current))
            current = line[2:].strip()
        elif current is not None and (
            line.startswith("- ") or line.startswith("#") or not line.strip()
        ):
            cases.append(_normalise(current))
            current = None
        elif current is not None:
            current += " " + line.strip()
    if current is not None:
        cases.append(_normalise(current))
    return cases


def _tracker_cases(text: str) -> list[str]:
    if "**Acceptance sub-cases (" not in text:
        return []
    section = text.split("**Acceptance sub-cases (", 1)[1].split(
        "**Named tasks/subtasks:", 1
    )[0]
    return [
        _normalise(match.group(1))
        for line in section.splitlines()
        if (match := re.match(r"^\d+\. (\*\*Given\*\*.*)$", line))
    ]


def test_all_f0602_acceptance_text_matches_original_backlog() -> None:
    backlog = _sections(BACKLOG.read_text(encoding="utf-8"), 4)
    tracker = _sections(TRACKER.read_text(encoding="utf-8"), 3)
    for story_id, source in sorted(backlog.items()):
        assert _tracker_cases(tracker[story_id]) == _source_cases(source), story_id
