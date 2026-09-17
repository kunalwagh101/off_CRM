#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "BOARD.md"
STORY = "- S-03.02.05 · A platform is a row, not a code change"

text = BOARD.read_text(encoding="utf-8")
if STORY not in text:
    raise SystemExit("S-03.02.05 is not on the board")
ready_marker = "## READY\n"
progress_marker = "## IN_PROGRESS\n\n_nothing in flight_"
if progress_marker not in text:
    raise SystemExit("IN_PROGRESS is not empty; refusing to pull another story")
# Remove exactly the READY occurrence, then place the story in IN_PROGRESS.
ready_pos = text.index(ready_marker)
story_pos = text.index(STORY, ready_pos)
progress_pos = text.index("## IN_PROGRESS")
if story_pos > progress_pos:
    raise SystemExit("S-03.02.05 is not in READY")
text = text[:story_pos] + text[story_pos + len(STORY):]
text = text.replace(progress_marker, f"## IN_PROGRESS\n\n{STORY}", 1)
BOARD.write_text(text, encoding="utf-8")
