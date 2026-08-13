"""YouTube trend detection.

Built on YouTube because it is the only one of the four platforms whose terms
genuinely allow reading public data at scale — no research application, no
scraping.

Two things are being protected.

**The quota arithmetic, which decides the design.** `search.list` costs 100
units against a 10,000/day budget; a channel's uploads playlist costs 1 unit for
50 videos. A watcher built on search covers nine channels and stops for the day,
and that failure looks like a bug rather than a spent budget. So search is
refused with the arithmetic in the message, and every sweep goes through uploads
playlists.

**What "trending" means.** Raw view count returns the biggest channels' oldest
videos every week — both already known. The signal is a video doing many times
its *own channel's* median, which is a fact about the subject rather than about
the channel.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offsetx_apollo_builder.distribution.trends import (
    DEFAULT_WINDOW_HOURS,
    MIN_VIDEOS_FOR_BASELINE,
    TrendWatcher,
)
from offsetx_apollo_builder.distribution.youtube import (
    DEFAULT_DAILY_QUOTA,
    QUOTA_COSTS,
    QuotaExhausted,
    YouTubeClient,
    YouTubeError,
)


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


class FakeYouTube:
    """Stands in for the Data API. Records what was asked for."""

    def __init__(self):
        self.channels: dict[str, dict] = {}
        self.playlists: dict[str, list[str]] = {}
        self.videos: dict[str, dict] = {}
        self.calls: list[str] = []

    def add_channel(self, channel_id, title, uploads, subs=1000):
        self.channels[channel_id] = {
            "id": channel_id,
            "snippet": {"title": title},
            "contentDetails": {"relatedPlaylists": {"uploads": uploads}},
            "statistics": {"subscriberCount": str(subs)},
        }
        self.playlists.setdefault(uploads, [])

    def add_video(self, video_id, channel_id, uploads, *, title, views, hours_ago):
        self.playlists.setdefault(uploads, []).insert(0, video_id)
        self.videos[video_id] = {
            "id": video_id,
            "snippet": {
                "channelId": channel_id,
                "title": title,
                "publishedAt": _iso(hours_ago),
            },
            "statistics": {"viewCount": str(views), "likeCount": "10", "commentCount": "2"},
        }

    def __call__(self, url: str, params: dict) -> dict:
        assert url.startswith("https://www.googleapis.com/youtube/v3"), url
        assert "key" in params, "every call carries the API key"
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append(endpoint)
        if endpoint == "channels":
            handle = params.get("forHandle") or params.get("id")
            found = [
                item
                for item in self.channels.values()
                if item["id"] == handle or item["snippet"]["title"] == str(handle).lstrip("@")
            ]
            return {"items": found}
        if endpoint == "playlistItems":
            ids = self.playlists.get(params["playlistId"], [])[: params.get("maxResults", 50)]
            return {"items": [{"contentDetails": {"videoId": vid}} for vid in ids]}
        if endpoint == "videos":
            wanted = str(params["id"]).split(",")
            return {"items": [self.videos[v] for v in wanted if v in self.videos]}
        raise AssertionError(f"unexpected endpoint {endpoint}")


@pytest.fixture()
def fake():
    return FakeYouTube()


@pytest.fixture()
def watcher(tmp_path: Path, fake):
    client = YouTubeClient("test-key", fetch=fake)
    made = TrendWatcher(database_path=tmp_path / "trends.db", client=client)
    yield made
    made.close()


# ─────────────────────────────────────────────────────────────────────────────
# The quota, which decides the design
# ─────────────────────────────────────────────────────────────────────────────


def test_search_is_refused_with_the_arithmetic(watcher):
    """Not unimplemented — declined, and the message says why.

    One search costs what a hundred playlist reads cost. A watcher built on it
    covers nine channels and stops for the day, and that presents as a bug in
    off_CRM rather than as a budget that was spent.
    """
    with pytest.raises(YouTubeError) as exc:
        watcher.client.search(q="depot")
    message = str(exc.value)
    assert "100 units" in message
    assert "uploads playlist costs 1 unit" in message


def test_the_documented_costs_are_what_the_design_assumes():
    assert QUOTA_COSTS["search.list"] == 100
    assert QUOTA_COSTS["playlistItems.list"] == 1
    assert QUOTA_COSTS["videos.list"] == 1
    assert DEFAULT_DAILY_QUOTA == 10_000


def test_a_thousand_channels_fits_in_a_day(watcher):
    """The claim the whole approach rests on, checked rather than asserted."""
    cost = watcher.client.sweep_cost(1000)
    assert cost < DEFAULT_DAILY_QUOTA, f"a 1,000-channel sweep costs {cost}"
    # The same coverage through search is not merely expensive.
    assert 1000 * QUOTA_COSTS["search.list"] > DEFAULT_DAILY_QUOTA * 9


def test_video_statistics_are_batched(watcher, fake):
    """Fifty separate calls would cost fifty units for the same answer."""
    watcher.client.video_stats([f"v{i}" for i in range(50)])
    assert fake.calls.count("videos") == 1
    assert watcher.client.quota.spent == 1


def test_spending_past_the_budget_is_refused_not_retried(tmp_path, fake):
    client = YouTubeClient("k", fetch=fake, daily_quota=2)
    client.quota.charge("videos.list", 2)
    with pytest.raises(QuotaExhausted) as exc:
        client.video_stats(["v1"])
    assert "resets at midnight" in str(exc.value)


def test_a_sweep_that_runs_out_stops_cleanly(tmp_path, fake):
    """Rather than raising halfway and leaving the day's picture half-updated."""
    fake.add_channel("UC1", "One", "UU1")
    fake.add_channel("UC2", "Two", "UU2")
    fake.add_video("a", "UC1", "UU1", title="a", views=10, hours_ago=1)
    fake.add_video("b", "UC2", "UU2", title="b", views=10, hours_ago=1)

    client = YouTubeClient("k", fetch=fake, daily_quota=100)
    watcher = TrendWatcher(database_path=tmp_path / "t.db", client=client)
    try:
        watcher.watch("@One")
        watcher.watch("@Two")
        client.quota.spent = client.quota.daily_quota - 1  # only one unit left

        result = watcher.sweep()
        assert result.channels_swept == 0
        assert len(result.skipped) == 2
        assert "quota" in result.skipped[0]["reason"]
    finally:
        watcher.close()


# ─────────────────────────────────────────────────────────────────────────────
# Watching and sweeping
# ─────────────────────────────────────────────────────────────────────────────


def test_watching_a_channel_resolves_its_uploads_playlist(watcher, fake):
    """The uploads playlist is the cheap door to everything a channel published."""
    fake.add_channel("UC1", "Depot Daily", "UU1", subs=42_000)
    channel = watcher.watch("@Depot Daily")
    assert channel["uploads_playlist_id"] == "UU1"
    assert channel["subscribers"] == 42_000
    assert len(watcher.watched()) == 1


def test_watching_the_same_channel_twice_updates_rather_than_duplicates(watcher, fake):
    fake.add_channel("UC1", "Depot Daily", "UU1")
    watcher.watch("@Depot Daily")
    watcher.watch("@Depot Daily")
    assert len(watcher.watched()) == 1


def test_an_unknown_channel_is_reported(watcher):
    with pytest.raises(YouTubeError) as exc:
        watcher.watch("@nobody")
    assert "No channel matched" in str(exc.value)


def test_a_sweep_stores_videos_and_refreshes_them(watcher, fake):
    fake.add_channel("UC1", "Depot", "UU1")
    fake.add_video("v1", "UC1", "UU1", title="Dawn", views=100, hours_ago=5)
    watcher.watch("@Depot")

    first = watcher.sweep()
    assert first.channels_swept == 1 and first.videos_new == 1

    fake.videos["v1"]["statistics"]["viewCount"] = "5000"
    second = watcher.sweep()
    assert second.videos_new == 0, "the same video is refreshed, not duplicated"
    assert watcher.trending()[0]["views"] == 5000


def test_a_sweep_never_reaches_for_search(watcher, fake):
    fake.add_channel("UC1", "Depot", "UU1")
    fake.add_video("v1", "UC1", "UU1", title="Dawn", views=100, hours_ago=5)
    watcher.watch("@Depot")
    watcher.sweep()
    assert "search" not in fake.calls


# ─────────────────────────────────────────────────────────────────────────────
# What "trending" means
# ─────────────────────────────────────────────────────────────────────────────


def _stock_channel(fake, watcher, channel_id, uploads, name, *, baseline_views, count=6):
    fake.add_channel(channel_id, name, uploads)
    for index in range(count):
        fake.add_video(
            f"{channel_id}-base{index}",
            channel_id,
            uploads,
            title=f"{name} regular {index}",
            views=baseline_views,
            hours_ago=200 + index,
        )
    watcher.watch(f"@{name}")


def test_a_small_channel_beating_its_own_baseline_outranks_a_big_ordinary_one(
    watcher, fake
):
    """The measure that finds a subject rather than a channel.

    A small channel at 20x its usual is a signal about the topic. A large
    channel's ordinary upload doing more views in absolute terms is a signal
    about the channel, which is already known.
    """
    _stock_channel(fake, watcher, "UCsmall", "UUsmall", "Small", baseline_views=1_000)
    _stock_channel(fake, watcher, "UCbig", "UUbig", "Big", baseline_views=500_000)

    fake.add_video("hit", "UCsmall", "UUsmall", title="Depot fire", views=20_000, hours_ago=6)
    fake.add_video("ordinary", "UCbig", "UUbig", title="Weekly", views=520_000, hours_ago=6)
    watcher.sweep(per_channel=50)

    trending = watcher.trending()
    assert trending[0]["video_id"] == "hit", [
        (item["video_id"], item["outlier_multiple"]) for item in trending[:3]
    ]
    assert trending[0]["outlier_multiple"] > trending[1]["outlier_multiple"]
    assert trending[0]["views"] < trending[1]["views"], "and it did so on fewer views"


def test_velocity_corrects_for_age(watcher, fake):
    _stock_channel(fake, watcher, "UC1", "UU1", "Depot", baseline_views=1_000)
    fake.add_video("fresh", "UC1", "UU1", title="Fresh", views=6_000, hours_ago=2)
    watcher.sweep(per_channel=50)

    fresh = next(item for item in watcher.trending() if item["video_id"] == "fresh")
    assert fresh["views_per_hour"] == pytest.approx(3000, rel=0.2)


def test_old_videos_are_not_trends(watcher, fake):
    _stock_channel(fake, watcher, "UC1", "UU1", "Depot", baseline_views=1_000)
    fake.add_video("old", "UC1", "UU1", title="Last year", views=999_999, hours_ago=5_000)
    watcher.sweep(per_channel=50)

    assert all(item["video_id"] != "old" for item in watcher.trending())


def test_a_channel_without_a_baseline_is_listed_but_not_ranked(watcher, fake):
    """A 20x multiple computed from two videos looks like insight and is noise.

    Listed anyway, because it may be exactly the thing worth looking at, and
    hiding it would make the list quietly depend on how long each channel had
    been watched.
    """
    fake.add_channel("UCnew", "New", "UUnew")
    fake.add_video("n1", "UCnew", "UUnew", title="First", views=50_000, hours_ago=3)
    fake.add_video("n2", "UCnew", "UUnew", title="Second", views=100, hours_ago=4)
    watcher.watch("@New")
    watcher.sweep(per_channel=50)

    item = next(entry for entry in watcher.trending() if entry["video_id"] == "n1")
    assert item["ranked"] is False
    assert item["baseline_videos"] < MIN_VIDEOS_FOR_BASELINE


def test_a_trustworthy_baseline_needs_enough_videos(watcher, fake):
    _stock_channel(
        fake, watcher, "UC1", "UU1", "Depot", baseline_views=1_000, count=MIN_VIDEOS_FOR_BASELINE
    )
    fake.add_video("hit", "UC1", "UU1", title="Hit", views=10_000, hours_ago=2)
    watcher.sweep(per_channel=50)
    assert watcher.trending()[0]["ranked"] is True


def test_the_report_says_what_a_sweep_would_cost(watcher, fake):
    _stock_channel(fake, watcher, "UC1", "UU1", "Depot", baseline_views=1_000)
    watcher.sweep(per_channel=50)
    report = watcher.report()
    assert report["channels_watched"] == 1
    assert report["videos_observed"] >= 6
    assert report["quota"]["spent"] > 0
    assert report["estimated_sweep_cost"] >= 1
    assert report["min_videos_for_baseline"] == MIN_VIDEOS_FOR_BASELINE


# ─────────────────────────────────────────────────────────────────────────────
# Structural
# ─────────────────────────────────────────────────────────────────────────────


def test_the_api_key_is_never_written_to_the_log(tmp_path, fake):
    """The log records what left. The key is the one thing that must not."""
    recorded: list[dict] = []
    client = YouTubeClient(
        "SECRET-KEY", fetch=fake, logger=lambda **kwargs: recorded.append(kwargs)
    )
    fake.add_channel("UC1", "Depot", "UU1")
    client.resolve_channel("@Depot")

    assert recorded, "the contact is logged at all"
    blob = repr(recorded)
    assert "SECRET-KEY" not in blob
    assert recorded[0]["provider_id"] == "youtube"
    assert recorded[0]["data_class"] == "public"


def test_only_one_module_here_touches_the_network():
    """Publishing goes through an adapter; reading goes through one client.

    A transport anywhere else would make the platform registry advisory.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "distribution"
    offenders = []
    for path in root.glob("*.py"):
        if path.name == "youtube.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: set[str] = set()
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            if names & {"requests", "httpx", "urllib.request", "selenium", "playwright"}:
                offenders.append(path.name)
    assert not offenders, offenders
