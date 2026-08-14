"""Turning a transcript into captions a person can actually read.

The model gives back words and the times they were said. Everything hard is
what happens next, and none of it is transcription: where to break, how long to
hold a line, what to do about a pause, and how to land all of it on a timeline
whose invariant refuses two clips that overlap by a single tick.

**Why word timings and not sentence timings.** A caption timed to a sentence
appears in full at the start of the sentence and sits there until the end. That
is a wall of text that arrives before it is spoken, which is the opposite of
what captions are for. Breaking on words means each line appears as it is said.

**Why this is deterministic.** Asking a model where to break would be a second
call, a second cost and a second thing that fails on a bad day, to answer a
question with rules: break at the end of a sentence, break at a pause, break
before a line gets too long to read. Those rules are here, they are testable,
and they run offline.

**Where the human is.** Captions come out as ordinary text clips on their own
track. Every edit already in the editor works on them — retime, restyle, fix a
word, delete a line. A transcript is a guess about what was said, and the
person reads it before anything is published. That is the same judgement the
swipe and the post approval already are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .timeline import (
    MIN_CLIP_TICKS,
    TICKS_PER_SECOND,
    Clip,
    snap_to_frame,
)

#: Characters in one caption. Two lines of about twenty-one, which is the
#: broadcast convention and roughly what fits across a vertical video at a
#: readable size. Longer lines do not fail, they just stop being read.
MAX_CHARS = 42

#: The longest a single caption may hold the screen. Past this it stops feeling
#: connected to the speech underneath it.
MAX_TICKS = 5 * TICKS_PER_SECOND

#: The shortest a caption may be shown, whatever the speech did. A word said in
#: 180ms still has to be readable, so short cues are stretched — into the
#: silence after them, never into the next cue.
MIN_TICKS = int(0.7 * TICKS_PER_SECOND)

#: A gap between words longer than this is a pause, and a pause is a break. This
#: is what keeps a caption from spanning the silence between two sentences.
PAUSE_TICKS = int(0.6 * TICKS_PER_SECOND)

#: Characters a viewer reads per second. Used only to *report* that a caption is
#: too fast — the speech cannot be slowed down, so flagging it is the honest
#: response, and it usually means the caption should have been split.
READABLE_CPS = 22

#: Ends a sentence, so a break here is always right.
_SENTENCE_END = re.compile(r"[.!?…]+[\"'”’)\]]*$")
#: A softer break, taken only when the line is already long enough to be worth
#: ending. Breaking at every comma produces a stutter of two-word captions.
_CLAUSE_END = re.compile(r"[,;:—–][\"'”’)\]]*$")

#: What a caption looks like unless the caller says otherwise. Deliberately
#: plain: a stroke and a shadow read on any background, which is the one thing a
#: caption has to do on video it was not designed against.
DEFAULT_STYLE: dict[str, Any] = {
    "size": 72,
    "font": "Inter, system-ui, sans-serif",
    "weight": "800",
    "colour": "#ffffff",
    "stroke": 8,
    "stroke_colour": "#000000",
    "align": "center",
    "line_height": 1.2,
    "max_width": 0.86,
}

#: Where captions sit by default: low, but clear of the platform's own furniture.
#: A caption centred vertically covers the subject; one at the very bottom is
#: covered by the caption *the platform* draws over it.
DEFAULT_Y_FRACTION = 0.32

CAPTION_TRACK_NAME = "Captions"


@dataclass(frozen=True)
class Word:
    """One word and when it was said, in ticks from the start of the media."""

    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass
class Cue:
    """One caption: what it says, and the span it says it over."""

    text: str
    start: int
    end: int
    words: list[Word] = field(default_factory=list)

    @property
    def duration(self) -> int:
        return self.end - self.start

    @property
    def chars_per_second(self) -> float:
        seconds = self.duration / TICKS_PER_SECOND
        return len(self.text) / seconds if seconds > 0 else float("inf")

    @property
    def too_fast(self) -> bool:
        return self.chars_per_second > READABLE_CPS

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "chars_per_second": round(self.chars_per_second, 1),
            "too_fast": self.too_fast,
            "words": [word.to_dict() for word in self.words],
        }


def words_from_transcript(items: Iterable[Mapping[str, Any] | Any]) -> list[Word]:
    """Read the broker's transcript words into tick time.

    Accepts the broker's ``TranscriptWord`` or a plain mapping, so a stored
    transcript reloaded from the database and a fresh one behave the same.
    """
    words: list[Word] = []
    for item in items:
        if isinstance(item, Mapping):
            text = str(item.get("word") or item.get("text") or "").strip()
            start, end = item.get("start"), item.get("end")
        else:
            text = str(getattr(item, "word", "") or getattr(item, "text", "")).strip()
            start, end = getattr(item, "start", None), getattr(item, "end", None)
        if not text or start is None or end is None:
            continue
        try:
            first = int(round(float(start) * TICKS_PER_SECOND))
            last = int(round(float(end) * TICKS_PER_SECOND))
        except (TypeError, ValueError):
            continue
        if last < first:
            continue
        words.append(Word(text=text, start=max(0, first), end=max(0, last)))
    words.sort(key=lambda word: (word.start, word.end))
    return words


def build_cues(
    words: Sequence[Word],
    *,
    max_chars: int = MAX_CHARS,
    max_ticks: int = MAX_TICKS,
    pause_ticks: int = PAUSE_TICKS,
) -> list[Cue]:
    """Group words into captions.

    Four reasons to break, in the order they are checked:

    1. the sentence ended — always right, and the only break a reader expects
    2. the speaker paused — a caption spanning silence looks stuck
    3. the line is as long as it can be and still be read
    4. the caption has been up as long as one should be

    A clause break (comma, dash, colon) is taken only once the line is over half
    full. Breaking at every comma gives a stutter of two-word captions, which is
    harder to read than the long line it was avoiding.
    """
    cues: list[Cue] = []
    current: list[Word] = []

    def flush() -> None:
        if not current:
            return
        cues.append(
            Cue(
                text=" ".join(word.text for word in current).strip(),
                start=current[0].start,
                end=current[-1].end,
                words=list(current),
            )
        )
        current.clear()

    for index, word in enumerate(words):
        pending = len(" ".join(item.text for item in current)) + (1 if current else 0) + len(word.text)
        if current and (pending > max_chars or word.end - current[0].start > max_ticks):
            flush()
        current.append(word)

        following = words[index + 1] if index + 1 < len(words) else None
        if following is None:
            break
        line = " ".join(item.text for item in current)
        if _SENTENCE_END.search(word.text):
            flush()
        elif following.start - word.end >= pause_ticks:
            flush()
        elif _CLAUSE_END.search(word.text) and len(line) >= max_chars // 2:
            flush()
    flush()
    return cues


def lay_out(
    cues: Sequence[Cue],
    *,
    fps: str,
    min_ticks: int = MIN_TICKS,
    limit: int = 0,
) -> list[Cue]:
    """Snap cues to frames and make them a legal track.

    This is the step that exists because of the timeline's own rule: clips on a
    track cannot overlap, not by one tick. Speech does not respect that — words
    run together, a stretched short cue can reach into the next one, and
    rounding two adjacent cues to the same frame boundary makes them collide.

    So every cue is snapped, then held back to at least a frame before the next
    one starts, then stretched towards ``min_ticks`` only into the space that is
    actually free. A cue that still cannot reach one frame is merged into its
    neighbour rather than dropped: losing a word is worse than a short caption.

    ``limit`` is the end of the material. A cue past it would caption a clip
    that has already finished.
    """
    if not cues:
        return []
    frame = max(1, snap_to_frame(MIN_CLIP_TICKS, fps))
    placed: list[Cue] = []

    for cue in cues:
        start = snap_to_frame(max(0, cue.start), fps)
        end = snap_to_frame(max(cue.end, cue.start + 1), fps)
        if limit:
            start = min(start, limit)
            end = min(end, limit)
        if end <= start:
            end = start + frame
        placed.append(Cue(text=cue.text, start=start, end=end, words=list(cue.words)))

    # Stretch each cue towards the minimum, using only the gap in front of it.
    for index, cue in enumerate(placed):
        ceiling = placed[index + 1].start if index + 1 < len(placed) else (limit or cue.end + min_ticks)
        if limit:
            ceiling = min(ceiling, limit)
        if cue.duration < min_ticks:
            cue.end = snap_to_frame(min(ceiling, cue.start + min_ticks), fps)
        if cue.end > ceiling:
            cue.end = snap_to_frame(ceiling, fps)

    # Anything that could not be given a single frame joins the cue before it.
    merged: list[Cue] = []
    for cue in placed:
        if cue.duration < frame and merged:
            previous = merged[-1]
            previous.text = f"{previous.text} {cue.text}".strip()
            previous.end = max(previous.end, cue.end)
            previous.words.extend(cue.words)
            continue
        if cue.duration < frame:
            cue.end = cue.start + frame
        merged.append(cue)

    return [cue for cue in merged if cue.duration >= frame and cue.text]


def to_timeline(
    cues: Sequence[Cue],
    clip: Clip,
    *,
    fps: str,
) -> list[Cue]:
    """Move cues from media time onto the timeline, under one clip.

    Three things have to be undone, and forgetting any of them puts the words in
    the wrong place rather than producing an error:

    - the clip starts somewhere on the timeline, not at zero
    - the clip may have been trimmed, so it starts reading part-way into the
      media — that is ``in_point``
    - the clip may not run at 1×, so a second of media is not a second of
      timeline

    Words spoken outside what the clip actually shows are dropped. Captioning a
    trimmed clip should caption what is left, not what was cut.
    """
    speed = clip.speed if clip.speed > 0 else 1.0
    visible_start = clip.in_point
    visible_end = clip.in_point + int(round(clip.duration * speed))
    moved: list[Cue] = []

    for cue in cues:
        start = max(cue.start, visible_start)
        end = min(cue.end, visible_end)
        if end <= start:
            continue
        moved.append(
            Cue(
                text=cue.text,
                start=clip.start + int(round((start - visible_start) / speed)),
                end=clip.start + int(round((end - visible_start) / speed)),
                words=list(cue.words),
            )
        )
    return lay_out(moved, fps=fps, limit=clip.start + clip.duration)


def caption_style(
    overrides: Mapping[str, Any] | None = None,
    *,
    height: int = 1920,
) -> tuple[dict[str, Any], float]:
    """The style for caption clips, and the y offset they sit at.

    Returned together because they are one decision: a bigger caption sits
    higher, and a caller that changed the size without the position would put
    the text under the platform's own overlay.
    """
    style = {**DEFAULT_STYLE, **dict(overrides or {})}
    fraction = float(style.pop("y_fraction", DEFAULT_Y_FRACTION))
    return style, height * fraction


def as_operations(
    cues: Sequence[Cue],
    *,
    track_id: str,
    style: Mapping[str, Any],
    y: float,
) -> list[dict[str, Any]]:
    """The cues as timeline edits, ready for one batched apply.

    One batch rather than one call per caption: a minute of speech is forty
    captions, and forty steps of undo to remove something the person asked for
    once is not an undo history, it is a chore.
    """
    return [
        {
            "op": "add_clip",
            "params": {
                "track_id": track_id,
                "kind": "text",
                "start": cue.start,
                "duration": cue.duration,
                "text": cue.text,
                "label": cue.text[:40],
                "style": dict(style),
                "properties": {"y": y},
            },
        }
        for cue in cues
    ]


def report(cues: Sequence[Cue]) -> dict[str, Any]:
    """What the caller should be told about the captions that were made."""
    fast = [cue for cue in cues if cue.too_fast]
    return {
        "captions": len(cues),
        "seconds": round(
            sum(cue.duration for cue in cues) / TICKS_PER_SECOND, 2
        ),
        "too_fast": len(fast),
        "warnings": (
            [
                f"{len(fast)} caption(s) are on screen too briefly to read at "
                f"{READABLE_CPS} characters a second. The speech is fast — "
                "shorten them by hand, or split them where the sense allows."
            ]
            if fast
            else []
        ),
    }
