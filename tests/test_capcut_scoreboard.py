"""The feature map's scoreboard has to match its own table.

`docs/architecture/CAPCUT_FEATURE_MAP.md` carries a status column and a summary
at the top saying how much of CapCut exists. A summary that drifts from the
table under it is worse than no summary: it is a number someone will quote.

So the counts are recomputed from the rows and checked against the header. Mark
a row built and forget the header, and this fails.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

MAP = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "CAPCUT_FEATURE_MAP.md"

BUILT, PARTIAL, NOT_BUILT = "●", "◐", "○"


def rows() -> list[tuple[str, str, str]]:
    """(feature, verdict, status mark) for every row in the numbered sections."""
    text = MAP.read_text(encoding="utf-8").split("## What this means here")[0]
    found: list[tuple[str, str, str]] = []
    section = None
    for line in text.splitlines():
        if re.match(r"^## \d+\. ", line):
            section = line
            continue
        if not section or not line.startswith("| ") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3 and cells[0] != "Feature":
            found.append((cells[0], cells[1], cells[2][:1]))
    return found


def header_numbers() -> dict[str, int]:
    text = MAP.read_text(encoding="utf-8")
    # Split on a horizontal rule at the start of a line: the table's own
    # separator row is full of dashes and would cut the summary in half.
    summary = re.split(r"^---$", text.split("## Where it stands")[1], flags=re.M)[0]
    numbers: dict[str, int] = {}
    for mark, key in ((BUILT, "built"), (PARTIAL, "partial"), (NOT_BUILT, "not_built")):
        match = re.search(rf"\|\s*{mark}[^|]*\|\s*\*\*(\d+)\*\*", summary)
        assert match, f"no header count for {mark}"
        numbers[key] = int(match.group(1))
    total = re.search(r"\|\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\|", summary)
    assert total, "no total in the header"
    numbers["total"] = int(total.group(1))
    return numbers


def test_every_row_carries_a_status_mark():
    """A row with no mark is a feature nobody decided about."""
    for feature, _, mark in rows():
        assert mark in (BUILT, PARTIAL, NOT_BUILT), f"{feature!r} has no status"


def test_the_scoreboard_matches_the_table_under_it():
    counts = Counter(mark for _, _, mark in rows())
    header = header_numbers()
    assert counts[BUILT] == header["built"]
    assert counts[PARTIAL] == header["partial"]
    assert counts[NOT_BUILT] == header["not_built"]
    assert sum(counts.values()) == header["total"] == len(rows())


def test_the_reachable_share_is_arithmetic_and_not_a_claim():
    """Out-of-scope rows are excluded from the denominator, and the text says
    which number that leaves."""
    items = rows()
    out_of_scope = [item for item in items if item[1].startswith("X") and item[2] == NOT_BUILT]
    reachable = len(items) - len(out_of_scope)
    touched = sum(1 for _, _, mark in items if mark in (BUILT, PARTIAL))

    text = MAP.read_text(encoding="utf-8")
    assert f"Nine of those" in text or f"{len(out_of_scope)} of those" in text
    assert f"{reachable} rows that are actually" in text
    assert f"{touched} are touched" in text
    assert f"{round(touched / reachable * 100)}%" in text


def test_auto_captions_is_marked_built_because_it_is():
    """The two rows the last build delivered, guarded against a silent revert."""
    marks = {feature: mark for feature, _, mark in rows()}
    assert marks["**Auto captions from speech**"] == BUILT
    assert marks["Caption editing, split, merge, re-sync"] == BUILT


def test_nothing_claims_to_be_built_that_the_code_does_not_have():
    """Spot-check the claims that would be easiest to inflate.

    Masks and keying need shader work that does not exist; MP4 needs a second
    muxer; text-to-video needs a generator nobody has wired. None of them may
    be marked built, whatever else moves.
    """
    marks = {feature: mark for feature, _, mark in rows()}
    for feature, mark in marks.items():
        if feature.startswith("Masks:") or "Chroma key" in feature or "Mask invert" in feature:
            assert mark == NOT_BUILT, f"{feature!r} is not built"
    assert marks["MP4 / MOV, H.264 / HEVC"] == NOT_BUILT
    assert marks["**Text to video**"] == NOT_BUILT
    assert marks["Smooth slow motion (frame interpolation)"] == NOT_BUILT
    assert marks["Motion blur between keyframes"] == NOT_BUILT


def test_the_rows_stage_two_delivered_are_marked_built():
    """The other direction: work that shipped must not quietly lose its mark."""
    marks = {feature: mark for feature, _, mark in rows()}
    for feature in (
        "Transitions: dissolve, wipe, glitch, zoom, whip, prism, page turn, light leak",
        "Transition duration slider",
        "Apply transition to all cuts",
        "Clip animations: in, out, combo/loop",
        "Blend modes (screen, multiply, overlay…)",
        "Copy–paste attributes between clips",
        "Text style presets",
    ):
        assert marks[feature] == BUILT, f"{feature!r} shipped and is not marked built"


def test_the_rows_stage_four_delivered_are_marked_built():
    """Audio in the export. Every file this project produced before it was
    silent, so this is the row that must never quietly go back."""
    marks = {feature: mark for feature, _, mark in rows()}
    for feature in (
        "**Audio in the export — WebAudio mix, Opus in the muxer**",
        "**Volume, fade in/out, audio keyframes**",
        "Audio speed, split, trim",
    ):
        assert marks[feature] == BUILT, f"{feature!r} shipped and is not marked built"


def test_the_rows_the_retime_build_delivered_are_marked_built():
    """Freeze, reverse and speed curves are one thing in the document — the map
    lists them as three, and all three have to move together or one of them is
    a claim the code does not back."""
    marks = {feature: mark for feature, _, mark in rows()}
    for feature in (
        "**Freeze frame**",
        "**Reverse clip**",
        "**Speed curves — ramp, hero, bullet, stutter, pulse**",
        "**Time remapping with keyframes**",
        "Freeze frame, reverse",
    ):
        assert marks[feature] == BUILT, f"{feature!r} shipped and is not marked built"


def test_the_audio_work_that_was_deliberately_left_out_is_still_marked_so():
    """Ducking, EQ and vocal isolation change what the mix *sounds* like rather
    than what it *is*, and each is a feature in its own right."""
    marks = {feature: mark for feature, _, mark in rows()}
    for feature in (
        "Auto ducking under speech",
        "Equaliser, reverb, echo",
        "Noise reduction / denoise",
        "Waveform display",
        "**Beat detection, auto beat markers**",
    ):
        assert marks[feature] == NOT_BUILT, f"{feature!r} is not built"
