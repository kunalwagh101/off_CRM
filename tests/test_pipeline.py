"""Trend to post — the piece that joins the three campaign kinds.

```
topic → brief → generate → gates → [SWIPE] → caption → draft post → [APPROVE] → schedule
                                      ↑                                 ↑
                                a person decides                 a person decides
```

**Where the automation stops is the whole design.** The pipeline runs in two
halves and the boundary between them is a judgement that already existed: `plan`
stops at the review queue, `draft` stops at a draft post. The machine fetches,
composes, generates and schedules; a person decides *is this picture good* and
*does this go out*.

Removing either would let the system publish something nobody ever saw, under
the owner's name. Most of the tests here exist to make sure neither can be
skipped by accident.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offsetx_apollo_builder.campaigns import WrongCampaignKind
from offsetx_apollo_builder.distribution.engine import DistributionEngine
from offsetx_apollo_builder.distribution.pipeline import (
    DEFAULT_COOLDOWN_HOURS,
    TrendPipeline,
    compose_brief,
    compose_caption,
    topic_key,
)
from offsetx_apollo_builder.distribution.publishers import LocalOutboxPublisher
from offsetx_apollo_builder.distribution.store import DistributionStore
from offsetx_apollo_builder.imagery.engine import ImageCampaignEngine
from offsetx_apollo_builder.imagery.store import ImageStore

from test_imagery import _Broker, _Generated, png  # noqa: E402

DIST = "dist-1"
IMAGES = "img-1"

TOPIC = {
    "label": "rotterdam + strike",
    "terms": ["rotterdam", "strike", "port"],
    "channels": 4,
    "videos": 5,
    "titles": ["Rotterdam strike begins", "Why the strike matters"],
    "views": 90_000,
}


class FakeTrends:
    def __init__(self, topics=None):
        self._topics = topics if topics is not None else [dict(TOPIC)]

    def topics(self, **kwargs):
        return [dict(item) for item in self._topics]


@pytest.fixture()
def parts(tmp_path: Path):
    image_store = ImageStore(tmp_path / "img.db", assets_dir=tmp_path / "assets")
    dist_store = DistributionStore(tmp_path / "dist.db", outbox_dir=tmp_path / "outbox")
    broker = _Broker()
    images = ImageCampaignEngine(
        store=image_store,
        broker=broker,
        settings_resolver=lambda workspace: object(),
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
    )
    distribution = DistributionEngine(
        store=dist_store,
        publisher=LocalOutboxPublisher(tmp_path / "outbox"),
        campaign_reader=lambda cid: {"id": cid, "kind": "distribution"},
        asset_reader=image_store.get_asset,
    )
    kinds = {DIST: "distribution", IMAGES: "image"}
    pipeline = TrendPipeline(
        trends=FakeTrends(),
        images=images,
        distribution=distribution,
        campaign_reader=lambda cid: {"id": cid, "kind": kinds.get(cid, "email")},
    )
    yield pipeline, images, distribution, broker
    image_store.close()
    dist_store.close()


def _account(distribution):
    return distribution.connect_account(platform="local_outbox", handle="@depot")["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Composition without a model
# ─────────────────────────────────────────────────────────────────────────────


def test_a_brief_can_be_written_without_a_model():
    """A pipeline that cannot run offline stops when a key expires."""
    brief = compose_brief(TOPIC)
    assert "rotterdam" in brief and "strike" in brief
    assert "No text" in brief, "generators put unreadable text in pictures"


def test_a_brief_describes_the_subject_not_the_composition():
    """Over-specifying produces the same picture from every model.

    Which defeats running several of them, and the swipe that compares them.
    """
    brief = compose_brief(TOPIC).lower()
    for over_specified in ("35mm", "golden hour", "wide angle", "bokeh"):
        assert over_specified not in brief


def test_an_owner_angle_reaches_both_the_brief_and_the_caption():
    assert "Our depot handles it" in compose_brief(TOPIC, angle="Our depot handles it")
    assert "Our depot handles it" in compose_caption(TOPIC, angle="Our depot handles it")


def test_a_topic_keeps_its_identity_when_it_gains_a_term():
    """The label is the first three terms; the key is all of them, sorted."""
    assert topic_key(["strike", "rotterdam"]) == topic_key(["Rotterdam", "STRIKE"])
    assert topic_key(["rotterdam"]) != topic_key(["rotterdam", "strike"])


# ─────────────────────────────────────────────────────────────────────────────
# Half one: topic to candidates, stopping at the queue
# ─────────────────────────────────────────────────────────────────────────────


def test_a_topic_becomes_a_brief_and_candidates(parts):
    pipeline, images, _, broker = parts
    broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]

    run = pipeline.plan(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, candidates=3
    )
    assert run.topics_planned == 1
    assert run.candidates == 3
    assert "rotterdam" in run.planned[0].brief_text

    queued = images.review_queue(IMAGES)
    assert len(queued) == 3, "and they are waiting for a person"


def test_planning_stops_at_the_review_queue(parts):
    """Nothing that has not been looked at becomes a post."""
    pipeline, _, distribution, broker = parts
    broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]

    pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)
    assert distribution.store.list_posts(DIST) == [], "no posts were created"


def test_the_same_topic_is_not_planned_twice(parts):
    """A story that runs three days is one topic, not three.

    Without the cooldown every sweep makes a fresh brief and the review queue
    fills with the same picture.
    """
    pipeline, images, _, broker = parts
    broker.script = [_Generated([png(1024, 576)]) for _ in range(10)]

    first = pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)
    second = pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)

    assert first.topics_planned == 1
    assert second.topics_planned == 0
    assert second.topics_skipped == 1
    assert "cooldown" in second.planned[0].skipped
    assert len(images.store.list_briefs(IMAGES)) == 1


def test_the_cooldown_can_be_shortened(parts):
    pipeline, _, _, broker = parts
    broker.script = [_Generated([png(1024, 576)]) for _ in range(10)]
    pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)
    again = pipeline.plan(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, cooldown_hours=1
    )
    assert again.topics_skipped == 1, "one hour has not passed either"
    assert DEFAULT_COOLDOWN_HOURS == 168


def test_the_number_of_topics_per_run_is_capped(parts):
    """Every candidate costs a call, and the queue is reviewed one at a time."""
    pipeline, images, _, broker = parts
    pipeline.trends = FakeTrends(
        [
            {**TOPIC, "label": f"topic{i}", "terms": [f"term{i}", "shared"]}
            for i in range(6)
        ]
    )
    broker.script = [_Generated([png(1024, 576)]) for _ in range(30)]

    run = pipeline.plan(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, max_topics=2
    )
    assert run.topics_planned == 2
    assert len(images.store.list_briefs(IMAGES)) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Half two: kept pictures to draft posts
# ─────────────────────────────────────────────────────────────────────────────


def _plan_and_keep(pipeline, images, broker, *, keep=1):
    broker.script = [_Generated([png(1024, 576)]) for _ in range(5)]
    pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES, candidates=3)
    queue = images.review_queue(IMAGES)
    for asset in queue[:keep]:
        images.approve(asset["id"])
    for asset in queue[keep:]:
        images.reject(asset["id"])
    return queue


def test_only_pictures_the_owner_kept_become_posts(parts):
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    account = _account(distribution)

    run = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    assert run.posts_created == 1, "two were discarded and did not become posts"
    assert run.posts[0]["status"] == "draft"


def test_a_drafted_post_still_needs_approval_before_scheduling(parts):
    """The pipeline does not route around the check that already existed."""
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    account = _account(distribution)
    run = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    post_id = run.posts[0]["id"]

    with pytest.raises(ValueError) as exc:
        distribution.schedule(post_id, at=datetime.now(timezone.utc))
    assert "approved" in str(exc.value)


def test_the_whole_chain_runs_to_a_published_post(parts, tmp_path):
    """End to end, with both human decisions made explicitly."""
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    account = _account(distribution)

    run = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    post_id = run.posts[0]["id"]
    distribution.approve(post_id)
    distribution.schedule(post_id, at=datetime.now(timezone.utc) - timedelta(minutes=1))
    published = distribution.publish_due()

    assert published.published == 1
    stored = distribution.store.get_post(post_id)
    assert stored["status"] == "published"
    assert stored["asset_id"], "the picture travelled with it"
    written = list((tmp_path / "outbox" / "local_outbox").glob("*.json"))
    assert written, "and something reached the outbox"


def test_a_picture_is_not_posted_twice(parts):
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    account = _account(distribution)

    first = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    second = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    assert first.posts_created == 1
    assert second.posts_created == 0
    assert second.skipped[0]["reason"] == "already posted"


def test_one_picture_can_go_to_several_accounts(parts):
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    accounts = [
        distribution.connect_account(platform="local_outbox", handle=f"@a{i}")["id"]
        for i in range(3)
    ]
    run = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=accounts
    )
    assert run.posts_created == 3


def test_drafting_with_no_account_is_refused(parts):
    """A draft with no destination is not a plan."""
    pipeline, images, _, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    with pytest.raises(ValueError) as exc:
        pipeline.draft(
            distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[]
        )
    assert "Connect one first" in str(exc.value)


def test_the_caption_recovers_the_topic_the_picture_came_from(parts):
    pipeline, images, distribution, broker = parts
    _plan_and_keep(pipeline, images, broker, keep=1)
    account = _account(distribution)
    run = pipeline.draft(
        distribution_campaign_id=DIST, image_campaign_id=IMAGES, account_ids=[account]
    )
    assert "rotterdam" in run.posts[0]["caption"].lower()


def test_a_hand_made_brief_falls_back_rather_than_inventing_a_topic(parts):
    """Creating a brief by hand is normal, and it has no topic behind it."""
    pipeline, images, distribution, broker = parts
    broker.script = [_Generated([png(1024, 576)])]
    brief_id = images.add_brief(IMAGES, brief="a warehouse at dawn", width=16, height=9)
    images.generate(brief_id, count=1)
    images.approve(images.review_queue(IMAGES)[0]["id"])

    run = pipeline.draft(
        distribution_campaign_id=DIST,
        image_campaign_id=IMAGES,
        account_ids=[_account(distribution)],
    )
    assert run.posts_created == 1
    assert run.posts[0]["caption"], "a caption was still written"


# ─────────────────────────────────────────────────────────────────────────────
# The writer
# ─────────────────────────────────────────────────────────────────────────────


def test_a_writer_is_used_when_one_is_supplied(parts):
    pipeline, images, _, broker = parts
    seen: list[str] = []

    def writer(kind: str, prompt: str) -> str:
        seen.append(kind)
        return "A rain-slicked container terminal at first light."

    pipeline.writer = writer
    broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]
    run = pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)

    assert "brief" in seen
    assert run.planned[0].brief_text.startswith("A rain-slicked")


def test_a_failing_writer_falls_back_instead_of_breaking_the_run(parts):
    """A model having a bad day must not cost the sweep."""
    pipeline, images, _, broker = parts
    pipeline.writer = lambda kind, prompt: (_ for _ in ()).throw(RuntimeError("503"))
    broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]

    run = pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)
    assert run.topics_planned == 1
    assert "rotterdam" in run.planned[0].brief_text, "the deterministic brief was used"


def test_an_empty_answer_falls_back_too(parts):
    pipeline, images, _, broker = parts
    pipeline.writer = lambda kind, prompt: "   "
    broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]
    run = pipeline.plan(distribution_campaign_id=DIST, image_campaign_id=IMAGES)
    assert "rotterdam" in run.planned[0].brief_text


# ─────────────────────────────────────────────────────────────────────────────
# The kind gate, across two campaigns at once
# ─────────────────────────────────────────────────────────────────────────────


def test_both_campaigns_are_checked(parts):
    """This is the first thing to touch two campaigns in one call.

    Each has to be the kind its half of the pipeline belongs to, or the run
    would quietly write image briefs against an email campaign.
    """
    pipeline, _, _, _ = parts
    with pytest.raises(WrongCampaignKind):
        pipeline.plan(distribution_campaign_id="email-1", image_campaign_id=IMAGES)
    with pytest.raises(WrongCampaignKind):
        pipeline.plan(distribution_campaign_id=DIST, image_campaign_id="email-1")
    with pytest.raises(WrongCampaignKind):
        pipeline.draft(
            distribution_campaign_id=DIST,
            image_campaign_id="email-1",
            account_ids=["x"],
        )
