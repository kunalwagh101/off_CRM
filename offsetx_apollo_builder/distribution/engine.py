"""The content-distribution campaign runner.

The third campaign kind, and the one that composes the others: an approved
picture from an image campaign becomes a post, the post goes out to accounts you
have connected, and what the audience did with it comes back as the measurement
the whole system has been missing.

```
asset (image campaign)  →  post  →  approve  →  schedule  →  publish
                                                                 ↓
   generator score  ←────────────  views, likes  ←────────  read back
```

**This closes the benchmark.** `CAMPAIGN_TYPES.md` described three layers:
deterministic gates, then the owner's swipe, then real engagement. The gates and
the swipe were built with the image runner. This is layer three — and it is the
one that can disagree with the other two. A picture the owner loved that nobody
watched is information, and it is the kind that only arrives here.

---

**On publishing, which is where the difficulty actually is.**

off_CRM publishes through **official APIs only**, and today that means one
adapter: the local outbox. Every real platform is declared in ``platforms.py``
with its API, its preconditions and its quotas, and scheduling to one that has no
adapter is refused at the point of scheduling rather than at the point of
sending. See that module for why the unofficial routes are not an option.

That is a smaller feature than "posts to all your accounts", and it is the one
that does not end with a banned account. The local outbox is the same device
``LocalOutboxProvider`` is for email: the entire pipeline runs, is reviewable and
is testable without touching a real platform.

**Quotas are checked when a post is scheduled**, not when it is sent. A schedule
that cannot be delivered is worse than one that was never made, because the
first looks like a plan.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..campaigns import assert_kind
from .platforms import assert_publishable, platform_spec
from .store import DistributionStore


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class PublishRound:
    """What one pass of :meth:`publish_due` did."""

    published: int = 0
    failed: int = 0
    skipped: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "failed": self.failed,
            "skipped": self.skipped,
            "details": list(self.details),
        }


class DistributionEngine:
    """Runs distribution campaigns: accounts, posts, publishing, measurement."""

    CAMPAIGN_KIND = "distribution"

    def __init__(
        self,
        *,
        store: DistributionStore,
        publisher: Any,
        campaign_reader: Callable[[str], dict[str, Any]] | None = None,
        asset_reader: Callable[[str], dict[str, Any]] | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.store = store
        self.publisher = publisher
        self.campaign_reader = campaign_reader
        #: Optional: reads an image asset, so a post can carry a picture and the
        #: generator that made it can be credited with real engagement later.
        self.asset_reader = asset_reader
        self.workspace_id = workspace_id
        self._lock = threading.RLock()

    def _require_own_kind(self, campaign_id: str, action: str) -> None:
        """The third runner to carry this check, for the same reason as the others."""
        if self.campaign_reader is None:
            return
        assert_kind(self.campaign_reader(campaign_id), self.CAMPAIGN_KIND, action=action)

    # ── accounts ────────────────────────────────────────────────────────────

    def set_account(self, account_id: str, **changes: Any) -> dict[str, Any]:
        """Change a connected handle: its label, whether it is on, and its cap."""
        return self.store.set_account(account_id, changes)

    def connect_account(
        self, *, platform: str, handle: str, label: str = "", daily_cap: int = 0
    ) -> dict[str, Any]:
        """Register an account to post to.

        Refused for a platform off_CRM cannot publish to. Storing it anyway would
        let the owner build a schedule against an account that will never
        deliver, which is the failure this whole module is arranged to avoid.
        """
        assert_publishable(platform)
        account_id = self.store.add_account(
            platform=platform, handle=handle, label=label,
            daily_cap=daily_cap, workspace_id=self.workspace_id,
        )
        return self.store.get_account(account_id)

    def accounts(self) -> list[dict[str, Any]]:
        return self.store.list_accounts(workspace_id=self.workspace_id)

    # ── goals ───────────────────────────────────────────────────────────────

    def set_goal(
        self, campaign_id: str, *, metric: str = "views", target: int = 0, deadline: str = ""
    ) -> dict[str, Any]:
        """A campaign is goal-shaped: "a million views", not "publish these"."""
        self._require_own_kind(campaign_id, "setting a goal")
        self.store.set_goal(
            campaign_id=campaign_id,
            metric=metric,
            target=target,
            deadline=deadline,
            workspace_id=self.workspace_id,
        )
        return self.progress(campaign_id)

    # ── posts ───────────────────────────────────────────────────────────────

    def plan_post(
        self,
        campaign_id: str,
        *,
        account_id: str,
        caption: str,
        asset_id: str = "",
    ) -> dict[str, Any]:
        self._require_own_kind(campaign_id, "planning a post")
        account = self.store.get_account(account_id)
        assert_publishable(str(account["platform"]))
        post_id = self.store.create_post(
            campaign_id=campaign_id,
            account_id=account_id,
            platform=str(account["platform"]),
            caption=caption,
            asset_id=asset_id,
            workspace_id=self.workspace_id,
        )
        return self.store.get_post(post_id)

    def approve(self, post_id: str) -> dict[str, Any]:
        post = self.store.get_post(post_id)
        if post["status"] != "draft":
            raise ValueError(f"This post is already {post['status']}.")
        return self.store.update_post(post_id, {"status": "approved"})

    def schedule(self, post_id: str, *, at: datetime | str) -> dict[str, Any]:
        """Queue an approved post, checking the platform's ceiling first.

        The check happens here rather than at send time because a schedule that
        cannot be delivered looks like a plan, and the owner will act as though
        it is one.
        """
        post = self.store.get_post(post_id)
        if post["status"] != "approved":
            raise ValueError(
                "Only an approved post can be scheduled. Approval is the point "
                "at which a person agreed to it going out."
            )
        spec = assert_publishable(str(post["platform"]))
        when = at if isinstance(at, str) else at.isoformat()
        day = str(when)[:10]
        account = self.store.get_account(str(post["account_id"]))

        # Two ceilings, and the owner's is checked first because it is the one
        # they will be surprised by. Counted across the whole account rather
        # than one campaign: the handle is what gets restricted, and it does not
        # care which campaign filled its day.
        owner_cap = int(account.get("daily_cap") or 0)
        already = self.store.published_on(str(post["account_id"]), day=day)
        if owner_cap and already >= owner_cap:
            raise ValueError(
                f"You capped {account['handle']} at {owner_cap} post(s) a day and "
                f"{already} are already committed for {day}. Pick another day, "
                "another account, or raise the cap."
            )

        limit = spec.daily_posts_per_account
        if limit and already >= limit:
            raise ValueError(
                f"{spec.label} allows {limit} API posts per account per day, "
                f"and {already} are already queued for {day}. Pick another "
                "day or another account."
            )
        return self.store.update_post(post_id, {"status": "scheduled", "scheduled_at": when})

    # ── publishing ──────────────────────────────────────────────────────────

    def publish_due(self, *, now: datetime | None = None, limit: int = 50) -> PublishRound:
        """Send everything whose time has come."""
        moment = (now or _now()).isoformat()
        round_result = PublishRound()

        with self._lock:
            for post in self.store.due_posts(now=moment, limit=limit):
                account = self.store.get_account(str(post["account_id"]))
                if not int(account.get("enabled") or 0):
                    round_result.skipped += 1
                    round_result.details.append(
                        {"post_id": post["id"], "status": "skipped", "detail": "account disabled"}
                    )
                    continue

                asset = None
                if post["asset_id"] and self.asset_reader is not None:
                    try:
                        asset = self.asset_reader(str(post["asset_id"]))
                    except Exception:  # noqa: BLE001 - a missing picture is a failure to report
                        asset = None

                try:
                    receipt = self.publisher.publish(
                        platform=str(post["platform"]),
                        handle=str(account["handle"]),
                        caption=str(post["caption"]),
                        asset=asset,
                        post_id=str(post["id"]),
                    )
                except Exception as exc:  # noqa: BLE001 - recorded, round continues
                    round_result.failed += 1
                    self.store.update_post(
                        post["id"], {"status": "failed", "error": str(exc)[:500]}
                    )
                    round_result.details.append(
                        {"post_id": post["id"], "status": "failed", "detail": str(exc)[:200]}
                    )
                    continue

                self.store.update_post(
                    post["id"],
                    {
                        "status": "published",
                        "published_at": _now().isoformat(),
                        "external_id": str(receipt.get("external_id", "")),
                        "error": "",
                    },
                )
                round_result.published += 1
                round_result.details.append(
                    {"post_id": post["id"], "status": "published", "detail": receipt}
                )
        return round_result

    # ── measurement: layer three ────────────────────────────────────────────

    def record_metrics(self, post_id: str, **counts: int) -> dict[str, Any]:
        """Store a reading of how a post is doing.

        Readings are snapshots rather than increments, so a later one replaces an
        earlier one in every total. Summing snapshots would count the same view
        as many times as it was measured.
        """
        post = self.store.get_post(post_id)
        if post["status"] != "published":
            raise ValueError(
                "Only a published post has an audience. Recording engagement for "
                "one that never went out would put fiction into the benchmark."
            )
        self.store.record_metrics(
            post_id=post_id,
            campaign_id=str(post["campaign_id"]),
            workspace_id=self.workspace_id,
            **counts,
        )
        return self.progress(str(post["campaign_id"]))

    def progress(self, campaign_id: str) -> dict[str, Any]:
        """Where the campaign stands against its goal."""
        self._require_own_kind(campaign_id, "reading progress")
        latest = self.store.latest_metrics(campaign_id)
        totals = {
            "views": sum(int(row["views"]) for row in latest),
            "likes": sum(int(row["likes"]) for row in latest),
            "comments": sum(int(row["comments"]) for row in latest),
            "shares": sum(int(row["shares"]) for row in latest),
        }
        goals = []
        for goal in self.store.list_goals(campaign_id):
            achieved = totals.get(str(goal["metric"]), 0)
            target = int(goal["target"])
            goals.append(
                {
                    **goal,
                    "achieved": achieved,
                    "remaining": max(0, target - achieved),
                    "percent": round(achieved / target * 100, 1) if target else 0.0,
                    "met": bool(target) and achieved >= target,
                }
            )
        posts = self.store.list_posts(campaign_id, limit=10000)
        return {
            "campaign_id": campaign_id,
            "totals": totals,
            "goals": goals,
            "posts": {
                status: len([item for item in posts if item["status"] == status])
                for status in ("draft", "approved", "scheduled", "published", "failed")
            },
            "measured_posts": len(latest),
        }

    def generator_performance(self, campaign_id: str) -> list[dict[str, Any]]:
        """What the audience thought, grouped by the generator that drew it.

        The link the benchmark was missing. The image campaign's swipe records
        what the owner liked; this records what got watched, against the same
        generators — so the two can be compared, and disagree.

        Needs ``asset_reader``; without it the join cannot be made and the
        honest answer is an empty list rather than a guess.
        """
        self._require_own_kind(campaign_id, "reading generator performance")
        if self.asset_reader is None:
            return []

        by_post = {str(row["post_id"]): row for row in self.store.latest_metrics(campaign_id)}
        grouped: dict[str, dict[str, Any]] = {}
        for post in self.store.list_posts(campaign_id, status="published", limit=10000):
            if not post["asset_id"]:
                continue
            try:
                asset = self.asset_reader(str(post["asset_id"]))
            except Exception:  # noqa: BLE001 - a deleted asset is not a crash
                continue
            key = f"{asset.get('provider_id', '')}:{asset.get('model_id', '')}"
            bucket = grouped.setdefault(
                key,
                {
                    "provider_id": asset.get("provider_id", ""),
                    "model_id": asset.get("model_id", ""),
                    "posts": 0,
                    "views": 0,
                    "likes": 0,
                    "measured": 0,
                },
            )
            bucket["posts"] += 1
            metrics = by_post.get(str(post["id"]))
            if metrics:
                bucket["measured"] += 1
                bucket["views"] += int(metrics["views"])
                bucket["likes"] += int(metrics["likes"])

        for bucket in grouped.values():
            bucket["views_per_post"] = (
                round(bucket["views"] / bucket["measured"], 1) if bucket["measured"] else 0.0
            )
        return sorted(grouped.values(), key=lambda item: -item["views_per_post"])
