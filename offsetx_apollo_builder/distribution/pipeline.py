"""Trend to post: the piece that joins the three campaign kinds.

Everything it needs was already built. Topics report what several competitors
are covering; the image runner turns a brief into candidates and collects a
verdict on each; the distribution runner turns a caption and an asset into a
scheduled post. This is the wiring, and it is what "run this campaign" finally
means end to end.

```
topic  →  brief  →  generate  →  gates  →  [ SWIPE ]  →  caption  →  draft post  →  [ APPROVE ]  →  schedule
                                              ↑                                          ↑
                                        a person decides                          a person decides
```

---

**Where the automation stops is the whole design.**

The pipeline runs in **two halves**, and the boundary between them is a human
judgement that already existed:

:meth:`TrendPipeline.plan` goes from a detected topic to generated candidates
waiting in the review queue. It stops there. Nothing that has not been looked at
becomes a post.

:meth:`TrendPipeline.draft` picks up the pictures the owner kept, writes a
caption for each and creates a **draft** post. It stops there too — a draft
still needs the approval the distribution runner has always required before
anything can be scheduled.

So the machine does the fetching, the composing, the generating and the
scheduling arithmetic, and a person does the two things that are judgement:
*is this picture good* and *does this go out*. Removing either would make the
system able to publish something nobody ever saw, which is not a feature worth
having in a tool that posts under the owner's name.

---

**On writing the words.**

Composition is deterministic by default and takes an optional ``writer``. With
no writer it assembles a serviceable brief and caption from the topic's own
terms and the headlines competitors used — which is genuinely enough for an
image brief, and is a starting point for a caption that a person is going to
read before approving anyway.

Given a writer — the API supplies one backed by the egress broker — it asks a
model. The data class is chosen by what is actually being sent: topic terms and
competitor video titles are **public**, so a public request goes to whichever
model is cheapest and permitted. Supplying an owner angle makes it **campaign**
class, because that is the owner's own positioning and it is not public.

Working without a writer matters for the same reason trends work without an API
key: a pipeline that cannot run offline is one that stops when a key expires.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

from ..campaigns import assert_kind

#: A topic that is still being covered a week later is the same topic. Without
#: this a persistent story creates a fresh brief every sweep and floods the
#: review queue with the same picture.
DEFAULT_COOLDOWN_HOURS = 168

#: Candidates generated per topic. Small: every one costs a call and the owner
#: reviews them one at a time.
DEFAULT_CANDIDATES = 3


def topic_key(terms: Sequence[str]) -> str:
    """A stable identity for a topic, so the same one is recognised tomorrow.

    Built from the sorted terms rather than the label, because the label is the
    first three and a topic can gain a term between sweeps without becoming a
    different subject.
    """
    joined = "|".join(sorted(str(term).strip().lower() for term in terms if term))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


@dataclass
class PlannedTopic:
    """One topic taken through to generated candidates."""

    label: str
    terms: list[str]
    channels: int
    brief_id: str = ""
    brief_text: str = ""
    generated: int = 0
    gate_failed: int = 0
    skipped: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "terms": list(self.terms),
            "channels": self.channels,
            "brief_id": self.brief_id,
            "brief_text": self.brief_text,
            "generated": self.generated,
            "gate_failed": self.gate_failed,
            "skipped": self.skipped,
        }


@dataclass
class PipelineRun:
    """What one pass produced."""

    topics_found: int = 0
    topics_planned: int = 0
    topics_skipped: int = 0
    candidates: int = 0
    planned: list[PlannedTopic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topics_found": self.topics_found,
            "topics_planned": self.topics_planned,
            "topics_skipped": self.topics_skipped,
            "candidates": self.candidates,
            "planned": [item.to_dict() for item in self.planned],
        }


@dataclass
class DraftRun:
    """Approved pictures turned into draft posts."""

    assets_considered: int = 0
    posts_created: int = 0
    posts: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assets_considered": self.assets_considered,
            "posts_created": self.posts_created,
            "posts": list(self.posts),
            "skipped": list(self.skipped),
        }


def compose_brief(topic: dict[str, Any], *, angle: str = "") -> str:
    """An image brief from a topic, without a model.

    Describes the *subject* and leaves the composition to the generator. A brief
    that over-specifies produces the same picture from every model, which
    defeats the point of running several.
    """
    terms = ", ".join(str(term) for term in (topic.get("terms") or [])[:4])
    brief = f"A striking editorial photograph illustrating: {terms}."
    if angle:
        brief += f" Angle: {angle.strip()}."
    brief += " No text, no logos, no recognisable faces."
    return brief


def compose_caption(topic: dict[str, Any], *, angle: str = "") -> str:
    """A caption from a topic, without a model.

    Deliberately plain. It is a starting point for something a person reads
    before approving, and a plain sentence is easier to correct than a
    confident one that is subtly wrong.
    """
    label = str(topic.get("label") or "").replace(" + ", ", ")
    caption = f"{label.capitalize()} — {topic.get('channels', 0)} channels covering it today."
    if angle:
        caption = f"{angle.strip()} {caption}"
    return caption


class TrendPipeline:
    """Joins topics, image generation and posting into one run."""

    def __init__(
        self,
        *,
        trends: Any,
        images: Any,
        distribution: Any,
        writer: Callable[[str, str], str] | None = None,
        campaign_reader: Callable[[str], dict[str, Any]] | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.trends = trends
        self.images = images
        self.distribution = distribution
        #: Optional ``(kind, prompt) -> text``. The API backs it with the broker.
        self.writer = writer
        self.campaign_reader = campaign_reader
        self.workspace_id = workspace_id

    # ── half one: topic to candidates ───────────────────────────────────────

    def plan(
        self,
        *,
        distribution_campaign_id: str,
        image_campaign_id: str,
        window_hours: int = 72,
        min_channels: int = 3,
        max_topics: int = 3,
        candidates: int = DEFAULT_CANDIDATES,
        angle: str = "",
        cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    ) -> PipelineRun:
        """Topic → brief → candidates, stopping at the review queue.

        Stops there on purpose. The next step is a person looking at the
        pictures, and there is no version of this that should skip it.
        """
        self._require_kind(distribution_campaign_id, "distribution", "planning from trends")
        self._require_kind(image_campaign_id, "image", "generating from trends")

        topics = self.trends.topics(
            window_hours=window_hours, min_channels=min_channels, limit=max_topics * 3
        )
        run = PipelineRun(topics_found=len(topics))

        for topic in topics:
            if run.topics_planned >= max_topics:
                break
            key = topic_key(topic.get("terms") or [])
            if self._recently_actioned(key, cooldown_hours):
                run.topics_skipped += 1
                run.planned.append(
                    PlannedTopic(
                        label=str(topic.get("label", "")),
                        terms=list(topic.get("terms") or []),
                        channels=int(topic.get("channels", 0)),
                        skipped="already covered within the cooldown window",
                    )
                )
                continue

            brief_text = self._write_brief(topic, angle=angle)
            brief_id = self.images.add_brief(
                image_campaign_id,
                brief=brief_text,
                width=16,
                height=9,
                wanted=1,
            )
            generated = self.images.generate(brief_id, count=candidates)
            self._record_action(
                key=key,
                label=str(topic.get("label", "")),
                campaign_id=distribution_campaign_id,
                brief_id=brief_id,
            )

            run.topics_planned += 1
            run.candidates += generated.stored
            run.planned.append(
                PlannedTopic(
                    label=str(topic.get("label", "")),
                    terms=list(topic.get("terms") or []),
                    channels=int(topic.get("channels", 0)),
                    brief_id=brief_id,
                    brief_text=brief_text,
                    generated=generated.stored,
                    gate_failed=generated.gate_failed,
                )
            )
        return run

    # ── half two: kept pictures to draft posts ──────────────────────────────

    def draft(
        self,
        *,
        distribution_campaign_id: str,
        image_campaign_id: str,
        account_ids: Sequence[str],
        angle: str = "",
        limit: int = 20,
    ) -> DraftRun:
        """Approved pictures → draft posts, stopping before approval.

        Only pictures the owner kept are considered, and the post it creates is
        a **draft**: the distribution runner has always required an approval
        before anything can be scheduled, and this does not route around it.
        """
        self._require_kind(distribution_campaign_id, "distribution", "drafting posts")
        self._require_kind(image_campaign_id, "image", "reading approved images")
        if not account_ids:
            raise ValueError(
                "Give at least one account to post to. Connect one first — a "
                "draft with no destination is not a plan."
            )

        approved = self.images.store.list_assets(
            image_campaign_id, status="approved", limit=limit
        )
        already = {
            str(post.get("asset_id"))
            for post in self.distribution.store.list_posts(
                distribution_campaign_id, limit=10000
            )
            if post.get("asset_id")
        }

        run = DraftRun(assets_considered=len(approved))
        for asset in approved:
            asset_id = str(asset["id"])
            if asset_id in already:
                run.skipped.append({"asset_id": asset_id, "reason": "already posted"})
                continue
            topic = self._topic_for_brief(str(asset.get("brief_id", "")))
            caption = self._write_caption(topic, angle=angle)
            for account_id in account_ids:
                post = self.distribution.plan_post(
                    distribution_campaign_id,
                    account_id=account_id,
                    caption=caption,
                    asset_id=asset_id,
                )
                run.posts_created += 1
                run.posts.append(post)
        return run

    # ── composition ─────────────────────────────────────────────────────────

    def _write_brief(self, topic: dict[str, Any], *, angle: str) -> str:
        fallback = compose_brief(topic, angle=angle)
        if self.writer is None:
            return fallback
        headlines = "; ".join(str(item) for item in (topic.get("titles") or [])[:5])
        prompt = (
            "Several competitors published about the same subject today. Write "
            "one sentence describing a photograph that illustrates it. Describe "
            "the subject, not the composition. No text or logos in the image.\n"
            f"Subject terms: {', '.join(topic.get('terms') or [])}\n"
            f"Their headlines: {headlines}"
        )
        if angle:
            prompt += f"\nOur angle: {angle}"
        try:
            written = str(self.writer("brief", prompt) or "").strip()
        except Exception:  # noqa: BLE001 - a writer failure falls back, never breaks the run
            return fallback
        return written or fallback

    def _write_caption(self, topic: dict[str, Any], *, angle: str) -> str:
        fallback = compose_caption(topic, angle=angle)
        if self.writer is None or not topic:
            return fallback
        prompt = (
            "Write a short social caption about this subject. Plain language, "
            "no hashtags, no emoji, under 200 characters.\n"
            f"Subject: {topic.get('label', '')}\n"
            f"Their headlines: {'; '.join(str(i) for i in (topic.get('titles') or [])[:5])}"
        )
        if angle:
            prompt += f"\nOur angle: {angle}"
        try:
            written = str(self.writer("caption", prompt) or "").strip()
        except Exception:  # noqa: BLE001
            return fallback
        return written[:400] or fallback

    # ── bookkeeping ─────────────────────────────────────────────────────────

    def _require_kind(self, campaign_id: str, kind: str, action: str) -> None:
        if self.campaign_reader is None:
            return
        assert_kind(self.campaign_reader(campaign_id), kind, action=action)

    def _recently_actioned(self, key: str, cooldown_hours: int) -> bool:
        row = self.distribution.store.last_topic_action(key)
        if not row:
            return False
        seen = str(row.get("created_at") or "")
        try:
            when = datetime.fromisoformat(seen.replace("Z", "+00:00"))
        except ValueError:
            return False
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(cooldown_hours)))
        return when >= cutoff

    def _record_action(self, *, key: str, label: str, campaign_id: str, brief_id: str) -> None:
        self.distribution.store.record_topic_action(
            topic_key=key,
            label=label,
            campaign_id=campaign_id,
            brief_id=brief_id,
            workspace_id=self.workspace_id,
        )

    def _topic_for_brief(self, brief_id: str) -> dict[str, Any]:
        """Recover the topic a brief came from, for the caption.

        Returns an empty mapping when the brief was created by hand rather than
        by the pipeline — which is a normal thing to do, and means the caption
        falls back rather than inventing a topic that never existed.
        """
        if not brief_id:
            return {}
        row = self.distribution.store.topic_action_for_brief(brief_id)
        if not row:
            return {}
        return {"label": row.get("label", ""), "terms": str(row.get("label", "")).split(" + ")}
