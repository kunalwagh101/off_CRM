"""Topic clustering across channels.

One channel's video running hot is an outlier. Six channels posting about the
same thing today is a topic, and it is the stronger signal — the difference
between "this creator had a good week" and "something happened".

Three properties carry the design:

**Distinct channels, not videos.** A channel posting five times about its own
product has a content calendar, not a trend.

**A topic is common now and was not before.** The same shape as the outlier
multiple one level down. That gives adaptive stopwords for free: a domain's own
vocabulary has a high baseline by definition and filters itself, with no
hand-written list to maintain per industry.

**It is lexical, not semantic** — and there is a test that says so, because the
limitation matters more than the feature and should not be discovered by
someone trusting it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from offsetx_apollo_builder.distribution.topics import (
    MIN_CHANNELS_FOR_TOPIC,
    MIN_LIFT,
    find_topics,
    significant_terms,
)


def video(video_id, channel_id, title, *, hours_ago, views=1000):
    return {
        "video_id": video_id,
        "channel_id": channel_id,
        "title": title,
        "published_at": (
            datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        ).isoformat(),
        "views": views,
    }


def routine(count=24, *, channels=4, title="Weekly logistics update"):
    """A boring baseline: every channel, always saying the same thing."""
    return [
        video(f"old{i}", f"c{i % channels}", title, hours_ago=200 + i)
        for i in range(count)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Terms
# ─────────────────────────────────────────────────────────────────────────────


def test_titles_reduce_to_the_words_worth_matching_on():
    terms = significant_terms("The Rotterdam Port Strike Explained | Full Video 2026")
    assert "rotterdam" in terms and "strike" in terms and "port" in terms
    assert "the" not in terms, "stopword"
    assert "video" not in terms, "YouTube title padding"
    assert "full" not in terms


def test_a_year_survives_but_a_bare_number_does_not():
    """"The 2026 rules" is often the story; "Part 7" never is."""
    assert "2026" in significant_terms("What the 2026 rules change")
    assert "7" not in significant_terms("Depot tour part 7")


# ─────────────────────────────────────────────────────────────────────────────
# What makes a topic
# ─────────────────────────────────────────────────────────────────────────────


def test_several_channels_on_one_subject_becomes_a_topic():
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike hits exports", hours_ago=5),
        video("n2", "c1", "Why the Rotterdam strike matters", hours_ago=6),
        video("n3", "c2", "Rotterdam: what shippers should do now", hours_ago=7),
    ]
    topics = find_topics(videos, window_hours=72)
    assert topics, "three channels on one subject is a topic"
    assert topics[0].label.startswith("rotterdam")
    assert topics[0].channels == 3
    assert set(topics[0].channel_ids) == {"c0", "c1", "c2"}


def test_one_channel_repeating_itself_is_not_a_topic():
    """A content calendar, not a trend.

    The measure is distinct channels, so five videos from one channel score one
    however loudly they repeat.
    """
    videos = routine() + [
        video(f"n{i}", "c0", f"Our depot series episode {i} warehouse", hours_ago=5 + i)
        for i in range(5)
    ]
    assert find_topics(videos, window_hours=72) == []


def test_the_domain_vocabulary_filters_itself():
    """No hand-written per-industry stopword list.

    Every channel always says "logistics", so its baseline is high and the same
    arithmetic that finds a spike removes it. A list would need maintaining and
    would still miss the words that matter to one owner and not another.
    """
    videos = routine(title="Weekly logistics update") + [
        video("n1", "c0", "Monday logistics update", hours_ago=5),
        video("n2", "c1", "Tuesday logistics update", hours_ago=6),
        video("n3", "c2", "Wednesday logistics update", hours_ago=7),
    ]
    labels = " ".join(topic.label for topic in find_topics(videos, window_hours=72))
    assert "logistics" not in labels
    assert "update" not in labels


def test_a_word_nobody_used_before_is_the_strongest_case():
    """No history is not a division by zero — it is exactly the signal."""
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike", hours_ago=5),
        video("n2", "c1", "Rotterdam latest", hours_ago=6),
        video("n3", "c2", "Rotterdam explained", hours_ago=7),
    ]
    topic = find_topics(videos, window_hours=72)[0]
    assert topic.lift == float("inf")
    assert topic.to_dict()["lift"] == pytest.approx(float("inf"))


def test_a_term_needs_a_real_jump_not_just_presence():
    """Already used by most channels and still used: vocabulary, not an event."""
    videos = [
        video(f"old{i}", f"c{i % 4}", "Port update weekly", hours_ago=200 + i)
        for i in range(24)
    ] + [
        video("n1", "c0", "Port update monday", hours_ago=5),
        video("n2", "c1", "Port update tuesday", hours_ago=6),
        video("n3", "c2", "Port update wednesday", hours_ago=7),
    ]
    assert all("port" not in topic.label for topic in find_topics(videos, window_hours=72))


def test_two_channels_is_below_the_threshold():
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike", hours_ago=5),
        video("n2", "c1", "Rotterdam latest", hours_ago=6),
    ]
    assert find_topics(videos, window_hours=72) == []
    assert MIN_CHANNELS_FOR_TOPIC == 3

    # ...and it is a threshold, not a hard rule.
    loosened = find_topics(videos, window_hours=72, min_channels=2)
    assert loosened and loosened[0].channels == 2


def test_old_coverage_is_not_a_current_topic():
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike", hours_ago=500),
        video("n2", "c1", "Rotterdam latest", hours_ago=520),
        video("n3", "c2", "Rotterdam explained", hours_ago=540),
    ]
    assert find_topics(videos, window_hours=72) == []


def test_the_baseline_needs_the_older_videos_to_exist():
    """Passing only the window would make every common word look like an event."""
    only_recent = [
        video("n1", "c0", "Weekly logistics update", hours_ago=5),
        video("n2", "c1", "Weekly logistics update", hours_ago=6),
        video("n3", "c2", "Weekly logistics update", hours_ago=7),
    ]
    # With no history, "logistics" is indistinguishable from a new event — which
    # is correct, and is why the caller passes the whole corpus.
    assert find_topics(only_recent, window_hours=72)


# ─────────────────────────────────────────────────────────────────────────────
# Merging
# ─────────────────────────────────────────────────────────────────────────────


def test_one_subject_named_twice_becomes_one_topic():
    """"rotterdam" and "strike" cover the same three videos, so they are one."""
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike begins", hours_ago=5),
        video("n2", "c1", "Rotterdam strike spreads", hours_ago=6),
        video("n3", "c2", "Rotterdam strike explained", hours_ago=7),
    ]
    topics = find_topics(videos, window_hours=72)
    assert len(topics) == 1
    assert set(topics[0].terms) >= {"rotterdam", "strike"}


def test_unrelated_stories_do_not_chain_into_one_blob():
    """Merging is on shared *videos*, not shared terms.

    Term chaining is how clustering quietly turns everything into one topic: A
    shares a word with B and B with C, and three unrelated stories become one.
    """
    videos = routine(channels=6, count=36) + [
        video("a1", "c0", "Rotterdam strike begins", hours_ago=5),
        video("a2", "c1", "Rotterdam strike spreads", hours_ago=6),
        video("a3", "c2", "Rotterdam strike explained", hours_ago=7),
        video("b1", "c3", "Battery plant opens", hours_ago=5),
        video("b2", "c4", "Battery plant tour", hours_ago=6),
        video("b3", "c5", "Battery plant jobs", hours_ago=7),
    ]
    topics = find_topics(videos, window_hours=72)
    labels = [topic.label for topic in topics]
    assert len(topics) >= 2, labels
    joined = {topic.label.split(" + ")[0] for topic in topics}
    assert "rotterdam" in joined or "strike" in joined
    assert "battery" in joined or "plant" in joined
    for topic in topics:
        assert not ({"rotterdam", "battery"} <= set(topic.terms)), (
            "two unrelated stories were chained into one topic"
        )


# ─────────────────────────────────────────────────────────────────────────────
# The limitation, on the record
# ─────────────────────────────────────────────────────────────────────────────


def test_paraphrases_do_not_group_and_that_is_documented():
    """This is shared vocabulary detection, not topic understanding.

    "Rotterdam port strike" and "Dutch dockworkers walk out" are the same story
    and share no significant word. Semantic grouping needs an embedding or a
    model call per sweep — a cost, a provider dependency, and a feature that
    stops working when a key expires. This test exists so the limitation is
    found here rather than by someone trusting the output.
    """
    videos = routine() + [
        video("n1", "c0", "Rotterdam port strike", hours_ago=5),
        video("n2", "c1", "Dutch dockworkers walk out", hours_ago=6),
        video("n3", "c2", "Netherlands harbour stoppage", hours_ago=7),
    ]
    topics = find_topics(videos, window_hours=72)
    assert topics == [], (
        "three ways of saying the same thing share no word, so they do not "
        "group — the honest description of this feature is lexical"
    )


def test_a_topic_reports_enough_to_act_on():
    videos = routine() + [
        video("n1", "c0", "Rotterdam strike", hours_ago=5, views=40_000),
        video("n2", "c1", "Rotterdam latest", hours_ago=6, views=10_000),
        video("n3", "c2", "Rotterdam explained", hours_ago=7, views=5_000),
    ]
    described = find_topics(videos, window_hours=72)[0].to_dict()
    assert described["channels"] == 3
    assert described["videos"] == 3
    assert described["views"] == 55_000
    assert described["titles"], "the actual headlines, to judge the angle"
    assert described["earliest_published_at"], "how early it was caught"
