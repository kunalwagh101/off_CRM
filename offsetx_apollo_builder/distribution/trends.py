"""Watching competitors, and working out what is actually rising.

The Amul point from the owner's brief: the value is not knowing what is popular,
it is knowing what is popular **now**, early enough to make something about it.

---

**Why raw view count is the wrong signal.**

Sort a competitor set by views and you get the same answer every week: the
biggest channels' oldest videos. Both facts are already known and neither is
actionable.

Two measures are computed instead, and the second is the one that matters:

**Velocity** — views per hour since publication. Corrects for age, so a
three-day-old video is not compared against a three-year-old one.

**Outlier multiple** — how many times the channel's *own* median this video is
doing. This is the one that finds a topic rather than a channel. A small channel
whose video is running at 20× its usual is a signal about the *subject*; a large
channel's ordinary upload doing ten times that number in absolute terms is a
signal about the channel, which you already knew.

Ranked on the multiple, within a recency window, a competitor set surfaces
subjects that are moving. That is the thing worth making something about.

---

**On the median, honestly.**

It is taken over the videos off_CRM has actually seen for that channel, not over
its whole history. A channel watched for a week has a median of that week. That
makes early readings noisy, so a channel needs
:data:`MIN_VIDEOS_FOR_BASELINE` observations before its multiples are trusted —
below that the video is still listed, flagged, and left out of the ranking.

Reporting a 20× multiple computed from two videos would be the kind of number
that looks like insight and is arithmetic on noise.
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..db import Database, open_database
from .youtube import YouTubeClient, YouTubeError

SCHEMA = """
CREATE TABLE IF NOT EXISTS yt_channels (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    uploads_playlist_id TEXT NOT NULL DEFAULT '',
    subscribers INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_swept_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_yt_channel
    ON yt_channels(workspace_id, channel_id);

CREATE TABLE IF NOT EXISTS yt_videos (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    video_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_yt_video
    ON yt_videos(workspace_id, video_id);
CREATE INDEX IF NOT EXISTS ix_yt_videos_channel ON yt_videos(channel_id, published_at);
"""

#: Below this many observed videos a channel has no usable baseline, so its
#: multiples are reported but not ranked.
MIN_VIDEOS_FOR_BASELINE = 5

#: Default recency window. Older than this and it is not a trend, it is history.
DEFAULT_WINDOW_HOURS = 72


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse(value: str) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class SweepResult:
    channels_swept: int = 0
    videos_seen: int = 0
    videos_new: int = 0
    units_spent: int = 0
    skipped: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.skipped is None:
            self.skipped = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels_swept": self.channels_swept,
            "videos_seen": self.videos_seen,
            "videos_new": self.videos_new,
            "units_spent": self.units_spent,
            "skipped": list(self.skipped),
        }


class TrendWatcher:
    """Watches competitor channels and reports what is rising."""

    def __init__(
        self,
        *,
        database_path: Path | str | None = None,
        client: YouTubeClient | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.target = database_path
        self.client = client
        self.workspace_id = workspace_id
        self._connection: Database | None = None

    @property
    def connection(self) -> Database:
        if self._connection is None:
            database = open_database(self.target)
            database.executescript(SCHEMA)
            self._connection = database
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _require_client(self) -> YouTubeClient:
        if self.client is None:
            raise YouTubeError(
                "No YouTube client. Set a Data API key before watching channels."
            )
        return self.client

    # ── the watch list ──────────────────────────────────────────────────────

    def watch(self, handle_or_id: str) -> dict[str, Any]:
        """Add a competitor channel, resolving its uploads playlist once."""
        channel = self._require_client().resolve_channel(handle_or_id)
        self.connection.execute(
            "INSERT INTO yt_channels(id, workspace_id, channel_id, title,"
            " uploads_playlist_id, subscribers, enabled, created_at)"
            " VALUES(?,?,?,?,?,?,1,?)"
            " ON CONFLICT(workspace_id, channel_id) DO UPDATE SET"
            " title = excluded.title,"
            " uploads_playlist_id = excluded.uploads_playlist_id,"
            " subscribers = excluded.subscribers, enabled = 1",
            (
                str(uuid.uuid4()),
                self.workspace_id,
                channel.id,
                channel.title,
                channel.uploads_playlist_id,
                channel.subscribers,
                _now().isoformat(),
            ),
        )
        return channel.to_dict()

    def watched(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM yt_channels WHERE workspace_id = ? AND enabled = 1"
            " ORDER BY title",
            (self.workspace_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── the sweep ───────────────────────────────────────────────────────────

    def sweep(self, *, per_channel: int = 10, limit: int = 0) -> SweepResult:
        """Read recent uploads for every watched channel.

        Uploads playlists, never search — one unit per fifty videos rather than
        a hundred per query. The budget is checked before each channel, so a
        sweep that runs out stops cleanly with a note rather than raising
        halfway through and leaving the day's picture half-updated.
        """
        client = self._require_client()
        channels = self.watched()
        if limit:
            channels = channels[: max(1, int(limit))]
        result = SweepResult()
        before = client.quota.spent

        for channel in channels:
            if not client.quota.can_afford("playlistItems.list", 2):
                result.skipped.append(
                    {
                        "channel_id": channel["channel_id"],
                        "reason": "daily quota would be exceeded",
                    }
                )
                continue
            try:
                video_ids = client.recent_uploads(
                    str(channel["uploads_playlist_id"]), limit=per_channel
                )
                videos = client.video_stats(video_ids)
            except YouTubeError as exc:
                result.skipped.append(
                    {"channel_id": channel["channel_id"], "reason": str(exc)[:200]}
                )
                continue

            for video in videos:
                result.videos_seen += 1
                if self._record(video):
                    result.videos_new += 1
            result.channels_swept += 1
            self.connection.execute(
                "UPDATE yt_channels SET last_swept_at = ? WHERE workspace_id = ?"
                " AND channel_id = ?",
                (_now().isoformat(), self.workspace_id, channel["channel_id"]),
            )

        result.units_spent = client.quota.spent - before
        return result

    def _record(self, video: Any) -> bool:
        """Store or refresh one video. Returns whether it was new."""
        existing = self.connection.execute(
            "SELECT id FROM yt_videos WHERE workspace_id = ? AND video_id = ?",
            (self.workspace_id, video.id),
        ).fetchone()
        now = _now().isoformat()
        if existing:
            self.connection.execute(
                "UPDATE yt_videos SET views = ?, likes = ?, comments = ?,"
                " last_seen_at = ? WHERE workspace_id = ? AND video_id = ?",
                (
                    video.views,
                    video.likes,
                    video.comments,
                    now,
                    self.workspace_id,
                    video.id,
                ),
            )
            return False
        self.connection.execute(
            "INSERT INTO yt_videos(id, workspace_id, video_id, channel_id, title,"
            " published_at, views, likes, comments, first_seen_at, last_seen_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                self.workspace_id,
                video.id,
                video.channel_id,
                video.title,
                video.published_at,
                video.views,
                video.likes,
                video.comments,
                now,
                now,
            ),
        )
        return True

    # ── what is rising ──────────────────────────────────────────────────────

    def channel_baselines(self) -> dict[str, dict[str, Any]]:
        """Each channel's median views over what has been observed."""
        rows = self.connection.execute(
            "SELECT channel_id, views FROM yt_videos WHERE workspace_id = ?",
            (self.workspace_id,),
        ).fetchall()
        grouped: dict[str, list[int]] = {}
        for row in rows:
            grouped.setdefault(str(row["channel_id"]), []).append(int(row["views"]))
        return {
            channel_id: {
                "median_views": statistics.median(values) if values else 0,
                "observed": len(values),
                "trustworthy": len(values) >= MIN_VIDEOS_FOR_BASELINE,
            }
            for channel_id, values in grouped.items()
        }

    def trending(
        self, *, window_hours: int = DEFAULT_WINDOW_HOURS, limit: int = 20
    ) -> list[dict[str, Any]]:
        """What is rising, newest window first, ranked by outlier multiple.

        Videos from a channel without a trustworthy baseline are returned with
        ``ranked=False`` rather than dropped: they may be exactly the thing
        worth looking at, and hiding them would make the list quietly depend on
        how long each channel had been watched.
        """
        cutoff = _now() - timedelta(hours=max(1, int(window_hours)))
        baselines = self.channel_baselines()
        rows = self.connection.execute(
            "SELECT * FROM yt_videos WHERE workspace_id = ?", (self.workspace_id,)
        ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            published = _parse(str(row["published_at"]))
            if published is None or published < cutoff:
                continue
            hours = max(1.0, (_now() - published).total_seconds() / 3600.0)
            views = int(row["views"])
            baseline = baselines.get(str(row["channel_id"]), {})
            median = float(baseline.get("median_views") or 0)
            items.append(
                {
                    "video_id": row["video_id"],
                    "channel_id": row["channel_id"],
                    "title": row["title"],
                    "published_at": row["published_at"],
                    "views": views,
                    "likes": int(row["likes"]),
                    "hours_since_publish": round(hours, 1),
                    "views_per_hour": round(views / hours, 1),
                    "channel_median_views": median,
                    "outlier_multiple": round(views / median, 2) if median else 0.0,
                    "ranked": bool(baseline.get("trustworthy")),
                    "baseline_videos": int(baseline.get("observed") or 0),
                }
            )

        ranked = [item for item in items if item["ranked"]]
        unranked = [item for item in items if not item["ranked"]]
        ranked.sort(key=lambda item: (-item["outlier_multiple"], -item["views_per_hour"]))
        unranked.sort(key=lambda item: -item["views_per_hour"])
        return (ranked + unranked)[: max(1, int(limit))]

    def report(self, *, window_hours: int = DEFAULT_WINDOW_HOURS) -> dict[str, Any]:
        channels = self.watched()
        client = self.client
        return {
            "channels_watched": len(channels),
            "videos_observed": int(
                self.connection.execute(
                    "SELECT COUNT(*) AS total FROM yt_videos WHERE workspace_id = ?",
                    (self.workspace_id,),
                ).fetchone()["total"]
            ),
            "window_hours": window_hours,
            "min_videos_for_baseline": MIN_VIDEOS_FOR_BASELINE,
            "trending": self.trending(window_hours=window_hours),
            "quota": client.quota.to_dict() if client else {},
            "estimated_sweep_cost": client.sweep_cost(len(channels)) if client else 0,
        }
