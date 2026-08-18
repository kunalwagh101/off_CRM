"""Storage for distribution campaigns: accounts, posts, goals, measurements.

Its own database, like the imagery store and for the same reason: no foreign key
into the CRM, so it can move backends alone.

Four tables. ``dist_metrics`` is the one that closes the loop — it holds what
actually happened after a post went out, which is layer three of the benchmark
in ``CAMPAIGN_TYPES.md``. The swipe says what the owner liked; this says what
the audience did, and they are not always the same answer.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db import Database, open_database

SCHEMA = """
CREATE TABLE IF NOT EXISTS dist_accounts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    -- The owner's own ceiling for this handle, in posts per day. 0 means they
    -- have not set one, which is not the same as zero: with no cap the
    -- platform's published limit is still what binds.
    daily_cap INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dist_account
    ON dist_accounts(workspace_id, platform, handle);

CREATE TABLE IF NOT EXISTS dist_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    asset_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_at TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dist_posts_due
    ON dist_posts(status, scheduled_at);
CREATE INDEX IF NOT EXISTS ix_dist_posts_campaign
    ON dist_posts(campaign_id, status);

CREATE TABLE IF NOT EXISTS dist_goals (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    metric TEXT NOT NULL DEFAULT 'views',
    target INTEGER NOT NULL DEFAULT 0,
    deadline TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dist_goals_campaign ON dist_goals(campaign_id);

CREATE TABLE IF NOT EXISTS dist_metrics (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    measured_at TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_dist_metrics_post ON dist_metrics(post_id, measured_at);

CREATE TABLE IF NOT EXISTS dist_topic_actions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    topic_key TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    campaign_id TEXT NOT NULL DEFAULT '',
    brief_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dist_topic_actions
    ON dist_topic_actions(workspace_id, topic_key, created_at);
CREATE INDEX IF NOT EXISTS ix_dist_topic_brief
    ON dist_topic_actions(brief_id);
"""

POST_STATUSES = ("draft", "approved", "scheduled", "published", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DistributionStore:
    def __init__(self, database_path: Path | str | None = None, *, outbox_dir: Path | str) -> None:
        self.target = database_path
        self.outbox_dir = Path(outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self._connection: Database | None = None

    @property
    def connection(self) -> Database:
        if self._connection is None:
            database = open_database(self.target)
            database.executescript(SCHEMA)
            # `CREATE TABLE IF NOT EXISTS` does nothing to a table that already
            # exists, so a workspace created before caps existed needs the
            # column added rather than declared.
            database.add_column_if_missing(
                "dist_accounts", "daily_cap", "INTEGER NOT NULL DEFAULT 0"
            )
            self._connection = database
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ── accounts ────────────────────────────────────────────────────────────

    def add_account(
        self,
        *,
        platform: str,
        handle: str,
        label: str = "",
        daily_cap: int = 0,
        workspace_id: str = "local",
    ) -> str:
        account_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO dist_accounts(id, workspace_id, platform, handle, label,"
            " enabled, daily_cap, created_at) VALUES(?,?,?,?,?,1,?,?)"
            # Reconnecting an account deliberately does not reset its cap: the
            # limit is a decision about the handle, not about this connection.
            " ON CONFLICT(workspace_id, platform, handle) DO UPDATE SET"
            " label = excluded.label, enabled = 1",
            (account_id, workspace_id, platform, handle, label or handle,
             max(0, int(daily_cap or 0)), _now()),
        )
        row = self.connection.execute(
            "SELECT id FROM dist_accounts WHERE workspace_id = ? AND platform = ?"
            " AND handle = ?",
            (workspace_id, platform, handle),
        ).fetchone()
        return str(row["id"]) if row else account_id

    def get_account(self, account_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM dist_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Account not found: {account_id}")
        return dict(row)

    def set_account(
        self, account_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Change what an owner is allowed to change about a connected handle.

        Deliberately a closed list. An account row is the thing that decides
        where posts go, and a generic column writer here would let any caller
        move a post to another platform by name.
        """
        allowed = {"label": str, "enabled": int, "daily_cap": int}
        updates = {key: allowed[key](value) for key, value in changes.items() if key in allowed}
        if "daily_cap" in updates:
            updates["daily_cap"] = max(0, min(int(updates["daily_cap"]), 200))
        if not updates:
            return self.get_account(account_id)
        assignments = ", ".join(f"{key} = ?" for key in updates)
        self.connection.execute(
            f"UPDATE dist_accounts SET {assignments} WHERE id = ?",
            (*updates.values(), account_id),
        )
        return self.get_account(account_id)

    def published_on(self, account_id: str, *, day: str) -> int:
        """How many posts this handle has already committed to one day.

        Scheduled counts as well as published: a post queued for tomorrow is a
        post that will go out tomorrow, and a cap that only looked at what had
        already happened would let a whole day be filled in one afternoon.
        """
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM dist_posts WHERE account_id = ?"
            " AND status IN ('scheduled', 'published')"
            " AND substr(COALESCE(NULLIF(scheduled_at, ''), published_at, ''), 1, 10) = ?",
            (account_id, day),
        ).fetchone()
        return int(row["total"]) if row else 0

    def list_accounts(self, *, workspace_id: str = "local") -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM dist_accounts WHERE workspace_id = ? ORDER BY platform, handle",
            (workspace_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── posts ───────────────────────────────────────────────────────────────

    def create_post(
        self,
        *,
        campaign_id: str,
        account_id: str,
        platform: str,
        caption: str,
        asset_id: str = "",
        workspace_id: str = "local",
    ) -> str:
        post_id = str(uuid.uuid4())
        now = _now()
        self.connection.execute(
            "INSERT INTO dist_posts(id, campaign_id, workspace_id, account_id,"
            " platform, caption, asset_id, status, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,'draft',?,?)",
            (
                post_id,
                campaign_id,
                workspace_id,
                account_id,
                platform,
                str(caption or "")[:4000],
                asset_id,
                now,
                now,
            ),
        )
        return post_id

    def get_post(self, post_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM dist_posts WHERE id = ?", (post_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Post not found: {post_id}")
        return dict(row)

    def list_posts(
        self, campaign_id: str, *, status: str = "", limit: int = 200
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM dist_posts WHERE campaign_id = ?"
        params: list[Any] = [campaign_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at LIMIT ?"
        params.append(max(1, int(limit)))
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    def update_post(self, post_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "status",
            "scheduled_at",
            "published_at",
            "external_id",
            "error",
            "caption",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_post(post_id)
        if "status" in values and values["status"] not in POST_STATUSES:
            raise ValueError(f"Unknown post status: {values['status']}")
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.connection.execute(
            f"UPDATE dist_posts SET {assignments}, updated_at = ? WHERE id = ?",
            (*values.values(), _now(), post_id),
        )
        return self.get_post(post_id)

    def due_posts(self, *, now: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM dist_posts WHERE status = 'scheduled' AND scheduled_at <= ?"
            " ORDER BY scheduled_at LIMIT ?",
            (now, max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]

    def published_today(self, account_id: str, *, day: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM dist_posts WHERE account_id = ?"
            " AND status = 'published' AND published_at >= ?",
            (account_id, day),
        ).fetchone()
        return int(row["total"]) if row else 0

    # ── goals ───────────────────────────────────────────────────────────────

    def set_goal(
        self,
        *,
        campaign_id: str,
        metric: str = "views",
        target: int = 0,
        deadline: str = "",
        workspace_id: str = "local",
    ) -> str:
        goal_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO dist_goals(id, campaign_id, workspace_id, metric, target,"
            " deadline, created_at) VALUES(?,?,?,?,?,?,?)",
            (goal_id, campaign_id, workspace_id, metric, max(0, int(target)), deadline, _now()),
        )
        return goal_id

    def list_goals(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM dist_goals WHERE campaign_id = ? ORDER BY created_at",
            (campaign_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── measurements ────────────────────────────────────────────────────────

    @staticmethod
    def _measured_now() -> str:
        """Microsecond precision, unlike the second-precision used elsewhere.

        Engagement readings can legitimately be taken seconds apart, and the
        newest one has to be identifiable. Everything else in this store records
        events a person caused, where a second is finer than anyone needs.
        """
        return datetime.now(timezone.utc).isoformat()

    def record_metrics(
        self,
        *,
        post_id: str,
        campaign_id: str,
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        source: str = "",
        workspace_id: str = "local",
    ) -> str:
        metric_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO dist_metrics(id, post_id, campaign_id, workspace_id,"
            " measured_at, views, likes, comments, shares, source)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                metric_id,
                post_id,
                campaign_id,
                workspace_id,
                self._measured_now(),
                max(0, int(views)),
                max(0, int(likes)),
                max(0, int(comments)),
                max(0, int(shares)),
                source,
            ),
        )
        return metric_id

    # ── topics already acted on ─────────────────────────────────────────────

    def record_topic_action(
        self,
        *,
        topic_key: str,
        label: str,
        campaign_id: str,
        brief_id: str,
        workspace_id: str = "local",
    ) -> str:
        """Remember that this topic already produced a brief.

        A story that runs for three days is one topic, not three. Without this
        record every sweep makes a fresh brief for it and the review queue fills
        with the same picture.
        """
        action_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO dist_topic_actions(id, workspace_id, topic_key, label,"
            " campaign_id, brief_id, created_at) VALUES(?,?,?,?,?,?,?)",
            (action_id, workspace_id, topic_key, label, campaign_id, brief_id, _now()),
        )
        return action_id

    def last_topic_action(
        self, topic_key: str, *, workspace_id: str = "local"
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM dist_topic_actions WHERE workspace_id = ? AND topic_key = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (workspace_id, topic_key),
        ).fetchone()
        return dict(row) if row else None

    def topic_action_for_brief(self, brief_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM dist_topic_actions WHERE brief_id = ? LIMIT 1", (brief_id,)
        ).fetchone()
        return dict(row) if row else None

    def latest_metrics(self, campaign_id: str) -> list[dict[str, Any]]:
        """The most recent snapshot per post.

        Snapshots accumulate — views on Tuesday are not views on Friday — so a
        total has to be built from the newest reading per post rather than by
        summing every row. Summing them would count the same view many times and
        report a goal as met when it is not.
        """
        rows = self.connection.execute(
            "SELECT * FROM dist_metrics WHERE campaign_id = ?", (campaign_id,)
        ).fetchall()
        newest: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            key = str(item["post_id"])
            current = newest.get(key)
            # Ordered by time, then by id so two readings taken in the same
            # instant still resolve to one answer. An earlier version compared
            # only the timestamp, and because timestamps were second-precision
            # two readings a moment apart *both* matched the maximum and were
            # summed — reporting 100 views where there were 60.
            if current is None or (item["measured_at"], item["id"]) > (
                current["measured_at"],
                current["id"],
            ):
                newest[key] = item
        return list(newest.values())
