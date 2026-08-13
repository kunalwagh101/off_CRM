"""YouTube Data API v3 — the read side.

Of the four platforms the owner named, YouTube is the only one whose terms
genuinely allow reading public data at scale: the Data API serves video and
channel information under an ordinary quota, with no research application and no
scraping. That is why trend detection is built here first and not on Instagram or
TikTok.

---

**The number that decides the whole design.**

The default quota is **10,000 units a day**, and the endpoints are not priced
anywhere near each other:

| Call | Units | Returns |
|---|---|---|
| `playlistItems.list` | **1** | up to 50 videos from a channel's uploads |
| `videos.list` | **1** | statistics for up to 50 video ids |
| `channels.list` | **1** | up to 50 channels |
| `search.list` | **100** | one page of search results |

So a sweep of 1,000 competitor channels through their uploads playlists costs
roughly **1,100 units** — about a ninth of a day's budget, comfortably daily.
The same coverage through ``search.list`` is not merely expensive, it is
impossible: the entire daily quota buys 100 searches.

Everything here is therefore built on **uploads playlists**, and
:meth:`YouTubeClient.search` exists only to refuse, with that arithmetic in the
message. A watcher that reached for search would work for nine channels and then
stop for the day, which is the kind of failure that looks like a bug in off_CRM
rather than a budget that was spent.

---

**Why this does not go through the broker**, and is still logged.

The same reasoning as ``ai/discovery.py``: the broker exists to guard *payloads*,
and these calls carry none — a channel id, a region code and an API key. No
owner data, no person data.

It is still written to the egress log, so the log remains a complete record of
every time off_CRM contacted an outside service. A quota-consuming call that
left no trace would be the one nobody could account for later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

API_ROOT = "https://www.googleapis.com/youtube/v3"

#: Documented quota cost per call. Read rather than guessed, because the whole
#: sweep strategy is chosen from these numbers.
QUOTA_COSTS: dict[str, int] = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "search.list": 100,
}

#: The default a new Google Cloud project gets. Raising it is an application to
#: Google, not a setting here.
DEFAULT_DAILY_QUOTA = 10_000

#: Both endpoints page at 50, and paying one unit for 50 rather than for 1 is
#: the entire reason a large sweep fits in a day.
MAX_IDS_PER_CALL = 50

REQUEST_TIMEOUT_SECONDS = 20


class YouTubeError(RuntimeError):
    """A problem talking to the Data API, with the fix where there is one."""


class QuotaExhausted(YouTubeError):
    """The day's budget is spent. Refused rather than retried."""


@dataclass
class QuotaLedger:
    """What today's sweep has spent.

    Counted locally rather than read back from Google, which does not expose a
    live balance. That makes this an estimate — but an estimate from documented
    per-call costs, which is accurate unless a call fails in a way that still
    charges.
    """

    daily_quota: int = DEFAULT_DAILY_QUOTA
    spent: int = 0
    calls: dict[str, int] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return max(0, self.daily_quota - self.spent)

    def can_afford(self, endpoint: str, times: int = 1) -> bool:
        return self.remaining >= QUOTA_COSTS.get(endpoint, 1) * times

    def charge(self, endpoint: str, times: int = 1) -> None:
        cost = QUOTA_COSTS.get(endpoint, 1) * times
        if cost > self.remaining:
            raise QuotaExhausted(
                f"This would spend {cost} units and {self.remaining} remain of "
                f"{self.daily_quota} today. The quota resets at midnight "
                "Pacific time; a larger one is an application to Google, not a "
                "setting in off_CRM."
            )
        self.spent += cost
        self.calls[endpoint] = self.calls.get(endpoint, 0) + times

    def to_dict(self) -> dict[str, Any]:
        return {
            "daily_quota": self.daily_quota,
            "spent": self.spent,
            "remaining": self.remaining,
            "calls": dict(self.calls),
        }


@dataclass(frozen=True)
class Channel:
    id: str
    title: str
    uploads_playlist_id: str
    subscribers: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "uploads_playlist_id": self.uploads_playlist_id,
            "subscribers": self.subscribers,
        }


@dataclass(frozen=True)
class Video:
    id: str
    channel_id: str
    title: str
    published_at: str
    views: int = 0
    likes: int = 0
    comments: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "title": self.title,
            "published_at": self.published_at,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
        }


def _http_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """The only place this package touches the network.

    Isolated so it can be replaced in a test without a fake server, and so the
    structural test can assert that nothing else here has a transport.
    """
    import requests

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code == 403:
        raise QuotaExhausted(
            "YouTube refused the call with 403. The usual cause is the daily "
            "quota being spent; the other is an API key without the Data API "
            "enabled. Both are fixed in the Google Cloud console."
        )
    if not response.ok:
        raise YouTubeError(f"YouTube returned {response.status_code}: {response.text[:300]}")
    return response.json()


class YouTubeClient:
    """Read-only access to public YouTube data, with the quota counted."""

    def __init__(
        self,
        api_key: str,
        *,
        fetch: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        logger: Callable[..., Any] | None = None,
        daily_quota: int = DEFAULT_DAILY_QUOTA,
    ) -> None:
        if not str(api_key or "").strip():
            raise YouTubeError(
                "A YouTube Data API key is needed. Create one in the Google "
                "Cloud console with the YouTube Data API v3 enabled."
            )
        self.api_key = api_key
        self._fetch = fetch or _http_get
        self.logger = logger
        self.quota = QuotaLedger(daily_quota=daily_quota)

    # ── the refusal ─────────────────────────────────────────────────────────

    def search(self, *_: Any, **__: Any) -> None:
        """Refused, with the arithmetic.

        Not unimplemented — declined. One search costs what a hundred playlist
        reads cost, so a watcher built on it covers nine channels and then stops
        for the day. That failure looks like a bug in off_CRM rather than a
        budget that was spent, which is the worst way for it to present.
        """
        raise YouTubeError(
            "off_CRM does not use search.list for sweeps. It costs 100 units "
            f"against a {self.quota.daily_quota}/day quota — the whole budget "
            "buys 100 searches — while a channel's uploads playlist costs 1 "
            "unit for 50 videos. Watch channels instead of searching."
        )

    # ── reads ───────────────────────────────────────────────────────────────

    def _call(self, endpoint: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.quota.charge(endpoint)
        payload = dict(params)
        payload["key"] = self.api_key
        try:
            data = self._fetch(f"{API_ROOT}/{path}", payload)
        finally:
            self._log(endpoint, params)
        if not isinstance(data, dict):
            raise YouTubeError("YouTube returned a response that was not an object.")
        return data

    def _log(self, endpoint: str, params: dict[str, Any]) -> None:
        """Record the contact, never the key.

        The egress log exists to show what left. `params` carries channel ids
        and region codes, which are public; the API key is added after this and
        is the one thing that must not appear.
        """
        if self.logger is None:
            return
        try:
            self.logger(
                provider_id="youtube",
                provider_name="YouTube Data API",
                jurisdiction="US",
                tier="B",
                policy="public",
                data_class="public",
                task_type="trend_read",
                status="ok",
                payload={"endpoint": endpoint, "params": params},
                payload_summary={"endpoint": endpoint, "units": QUOTA_COSTS.get(endpoint, 1)},
            )
        except Exception:  # noqa: BLE001 - logging must never break a read
            pass

    def resolve_channel(self, handle_or_id: str) -> Channel:
        """Find a channel and its uploads playlist.

        The uploads playlist is the whole point: it is the cheap door to
        everything a channel has published.
        """
        value = str(handle_or_id or "").strip()
        if not value:
            raise YouTubeError("Give a channel handle (@name) or a channel id.")
        params: dict[str, Any] = {"part": "snippet,contentDetails,statistics"}
        if value.startswith("@"):
            params["forHandle"] = value
        elif value.startswith("UC"):
            params["id"] = value
        else:
            params["forHandle"] = f"@{value}"

        data = self._call("channels.list", "channels", params)
        items = data.get("items") or []
        if not items:
            raise YouTubeError(f"No channel matched {value!r}.")
        item = items[0]
        uploads = (
            item.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads", "")
        )
        if not uploads:
            raise YouTubeError(f"{value!r} has no uploads playlist to watch.")
        return Channel(
            id=str(item.get("id", "")),
            title=str(item.get("snippet", {}).get("title", "")),
            uploads_playlist_id=str(uploads),
            subscribers=int(item.get("statistics", {}).get("subscriberCount", 0) or 0),
        )

    def recent_uploads(self, uploads_playlist_id: str, *, limit: int = 50) -> list[str]:
        """Video ids from a channel's uploads, newest first. One unit per 50."""
        data = self._call(
            "playlistItems.list",
            "playlistItems",
            {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(MAX_IDS_PER_CALL, max(1, int(limit))),
            },
        )
        ids = []
        for item in data.get("items") or []:
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                ids.append(str(video_id))
        return ids

    def video_stats(self, video_ids: list[str]) -> list[Video]:
        """Statistics for up to 50 videos, for one unit.

        Batched deliberately: fifty separate calls would cost fifty units for
        exactly the same answer, and over a thousand channels that difference is
        the whole day's quota.
        """
        wanted = [str(item) for item in video_ids if item][:MAX_IDS_PER_CALL]
        if not wanted:
            return []
        data = self._call(
            "videos.list",
            "videos",
            {"part": "snippet,statistics", "id": ",".join(wanted)},
        )
        videos = []
        for item in data.get("items") or []:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            videos.append(
                Video(
                    id=str(item.get("id", "")),
                    channel_id=str(snippet.get("channelId", "")),
                    title=str(snippet.get("title", "")),
                    published_at=str(snippet.get("publishedAt", "")),
                    views=int(stats.get("viewCount", 0) or 0),
                    likes=int(stats.get("likeCount", 0) or 0),
                    comments=int(stats.get("commentCount", 0) or 0),
                )
            )
        return videos

    def sweep_cost(self, channel_count: int) -> int:
        """What watching this many channels would spend, before spending it."""
        playlist_calls = channel_count
        video_calls = max(1, (channel_count * 10) // MAX_IDS_PER_CALL)
        return playlist_calls * QUOTA_COSTS["playlistItems.list"] + (
            video_calls * QUOTA_COSTS["videos.list"]
        )
