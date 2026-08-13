"""What several competitors are all talking about at once.

One channel's video running hot is an outlier. **Six channels posting about the
same thing today is a topic**, and it is a much stronger signal — it is the
difference between "this creator had a good week" and "something happened".

---

**The measure is distinct channels, not videos.**

A channel that posts five videos about its own product has not started a trend;
it has a content calendar. So every score here is driven by how many *different*
channels touched a term, and a term only one channel uses scores one however
often it repeats it.

---

**What makes a term a topic: it is common now and was not before.**

The same shape as the outlier multiple one level down. A term is not interesting
because it is frequent — if you watch twenty logistics channels, "logistics" is
in half the titles and always was. A term is interesting when its share of
channels **inside the window** is well above its share **outside** it.

That gives adaptive stopwords for free. Nobody has to list the domain's
vocabulary, because the domain's vocabulary has a high baseline by definition
and is filtered by the same arithmetic that finds the spike. A hand-written list
would need maintaining per industry and would still miss the words that matter
to one owner and not another.

---

**The limitation, stated plainly: this is lexical, not semantic.**

"Rotterdam port strike" and "Dutch dockworkers walk out" are the same story and
share no significant word, so they will not group. Titles are short — five to
twelve words — which leaves little to match on, and the honest description of
this is *shared vocabulary detection*, not topic understanding.

It is built this way deliberately. Semantic grouping means an embedding or a
model call per sweep: a cost, a provider dependency, and a feature that stops
working when a key expires. Shared vocabulary catches the common case — a place
name, a company, an event, a product — deterministically, offline and free, and
it is honest about the case it misses rather than appearing to understand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

#: Ordinary English filler plus the words YouTube titles are padded with. Small
#: on purpose — the adaptive baseline below does the domain-specific work, and a
#: long hand-written list is the thing that goes stale.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but if then than that this these those with without within
    for from into onto out over under about after before during while when where
    what which who whom whose why how all any both each few more most other some
    such no nor not only own same so too very can will just should now
    is are was were be been being have has had do does did doing
    i you he she it we they me him her us them my your his its our their
    at by in of on to up as
    video videos official full new watch subscribe episode part ep shorts short
    vlog live stream trailer review first best top ultimate guide tutorial
    """.split()
)

#: A term has to be at least this long to be a candidate. Two-letter tokens are
#: almost always noise a stopword list has not caught.
MIN_TERM_LENGTH = 3

#: How many distinct channels must use a term before it is called a topic.
#: Two is a coincidence often enough to be worth excluding.
MIN_CHANNELS_FOR_TOPIC = 3

#: How much more common a term must be inside the window than outside it. A
#: term already used by half the channels is vocabulary; the same term jumping
#: to nearly all of them is an event.
MIN_LIFT = 2.0

#: Two term-clusters covering mostly the same videos are one topic described two
#: ways, and are merged. High enough that unrelated stories sharing a video stay
#: separate.
MERGE_OVERLAP = 0.6

_WORD = re.compile(r"[a-z0-9']+")
_YEAR = re.compile(r"^(19|20)\d{2}$")


def significant_terms(title: str) -> set[str]:
    """The words in a title worth matching on.

    Bare numbers are dropped except four-digit years, which are often the story
    ("the 2026 rules"). Everything else numeric is a part number, an episode
    index or a view count in a thumbnail caption.
    """
    terms: set[str] = set()
    for raw in _WORD.findall(str(title or "").lower()):
        word = raw.strip("'")
        if len(word) < MIN_TERM_LENGTH or word in STOPWORDS:
            continue
        if word.isdigit() and not _YEAR.match(word):
            continue
        terms.add(word)
    return terms


@dataclass
class Topic:
    """A subject several channels touched at once."""

    terms: list[str] = field(default_factory=list)
    video_ids: list[str] = field(default_factory=list)
    channel_ids: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    views: int = 0
    lift: float = 0.0
    earliest_published_at: str = ""

    @property
    def channels(self) -> int:
        return len(self.channel_ids)

    @property
    def videos(self) -> int:
        return len(self.video_ids)

    @property
    def label(self) -> str:
        return " + ".join(self.terms[:3])

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "terms": list(self.terms),
            "channels": self.channels,
            "videos": self.videos,
            "video_ids": list(self.video_ids),
            "channel_ids": list(self.channel_ids),
            "titles": list(self.titles)[:5],
            "views": self.views,
            "lift": round(self.lift, 2),
            "earliest_published_at": self.earliest_published_at,
        }


def _parse(value: str) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _channels_per_term(rows: Iterable[dict[str, Any]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for row in rows:
        channel = str(row.get("channel_id", ""))
        for term in significant_terms(str(row.get("title", ""))):
            index.setdefault(term, set()).add(channel)
    return index


def find_topics(
    videos: Sequence[dict[str, Any]],
    *,
    window_hours: int = 72,
    now: datetime | None = None,
    min_channels: int = MIN_CHANNELS_FOR_TOPIC,
    min_lift: float = MIN_LIFT,
    limit: int = 10,
) -> list[Topic]:
    """Group recent videos by the terms several channels started using.

    ``videos`` is every observed video, not only the recent ones — the older
    ones are what the baseline is made of. Passing only the window would leave
    nothing to compare against, and every common word would look like an event.
    """
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(hours=max(1, int(window_hours)))

    inside: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for row in videos:
        published = _parse(str(row.get("published_at", "")))
        if published is None:
            continue
        (inside if published >= cutoff else outside).append(row)

    if not inside:
        return []

    channels_inside = {str(row.get("channel_id", "")) for row in inside}
    channels_outside = {str(row.get("channel_id", "")) for row in outside}
    window_index = _channels_per_term(inside)
    baseline_index = _channels_per_term(outside)

    candidates: list[tuple[str, float, set[str]]] = []
    for term, channels in window_index.items():
        if len(channels) < min_channels:
            continue
        window_share = len(channels) / max(1, len(channels_inside))
        baseline_share = (
            len(baseline_index.get(term, set())) / len(channels_outside)
            if channels_outside
            else 0.0
        )
        # No history for this term at all is the strongest case, not a division
        # by zero: a word nobody used before that three channels now share is
        # exactly what this is looking for.
        lift = window_share / baseline_share if baseline_share else float("inf")
        if lift < min_lift:
            continue
        candidates.append((term, lift, channels))

    candidates.sort(key=lambda item: (-len(item[2]), -item[1]))

    topics: list[Topic] = []
    for term, lift, _ in candidates:
        matching = [
            row for row in inside if term in significant_terms(str(row.get("title", "")))
        ]
        if not matching:
            continue
        topic = Topic(
            terms=[term],
            video_ids=[str(row.get("video_id", "")) for row in matching],
            channel_ids=sorted({str(row.get("channel_id", "")) for row in matching}),
            titles=[str(row.get("title", "")) for row in matching],
            views=sum(int(row.get("views", 0) or 0) for row in matching),
            lift=lift,
            earliest_published_at=min(
                str(row.get("published_at", "")) for row in matching
            ),
        )
        merged_into = _merge(topics, topic)
        if not merged_into:
            topics.append(topic)

    topics.sort(key=lambda item: (-item.channels, -item.views))
    return topics[: max(1, int(limit))]


def _merge(topics: list[Topic], candidate: Topic) -> bool:
    """Fold a term-cluster into an existing one when they cover the same videos.

    Merging on *video overlap* rather than on shared terms, because term
    chaining is how clustering quietly turns everything into one blob: A shares
    a word with B and B with C, and suddenly three unrelated stories are one
    topic. Two clusters over the same videos really are one subject named twice.
    """
    candidate_videos = set(candidate.video_ids)
    for existing in topics:
        existing_videos = set(existing.video_ids)
        union = existing_videos | candidate_videos
        if not union:
            continue
        if len(existing_videos & candidate_videos) / len(union) >= MERGE_OVERLAP:
            existing.terms.extend(
                term for term in candidate.terms if term not in existing.terms
            )
            for video_id, title in zip(candidate.video_ids, candidate.titles):
                if video_id not in existing.video_ids:
                    existing.video_ids.append(video_id)
                    existing.titles.append(title)
            existing.channel_ids = sorted(
                set(existing.channel_ids) | set(candidate.channel_ids)
            )
            existing.views = max(existing.views, candidate.views)
            existing.lift = max(existing.lift, candidate.lift)
            existing.earliest_published_at = min(
                existing.earliest_published_at, candidate.earliest_published_at
            )
            return True
    return False
