"""The content-distribution campaign runner.

The third campaign kind, and the one that composes the others: an approved
picture becomes a post, the post goes out, and what the audience did comes back
as the measurement the system has been missing.

Two things are being protected here.

**The platform reality.** Every real platform allows far less automated posting
than it looks like from outside, and the tools that appear to offer more are the
ones that get accounts banned. off_CRM publishes through official APIs only, so
a platform with no adapter is refused *at scheduling* — a schedule that cannot
be delivered is worse than one never made, because the first looks like a plan.

**Snapshots are not increments.** Engagement readings accumulate — views on
Tuesday are not new views on Friday — so a total built by summing every reading
would count the same view repeatedly and report a goal as met when it is not.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offsetx_apollo_builder.campaigns import WrongCampaignKind
from offsetx_apollo_builder.distribution.engine import DistributionEngine
from offsetx_apollo_builder.distribution.platforms import (
    UNIVERSAL_REFUSALS,
    PlatformNotPublishable,
    PublishSupport,
    UnknownPlatform,
    assert_publishable,
    list_platforms,
    platform_spec,
    publishable_platforms,
)
from offsetx_apollo_builder.distribution.publishers import LocalOutboxPublisher
from offsetx_apollo_builder.distribution.store import DistributionStore

CAMPAIGN = "dist-1"


@pytest.fixture()
def engine(tmp_path: Path):
    store = DistributionStore(tmp_path / "dist.db", outbox_dir=tmp_path / "outbox")
    made = DistributionEngine(
        store=store,
        publisher=LocalOutboxPublisher(tmp_path / "outbox"),
        campaign_reader=lambda cid: {"id": cid, "kind": "distribution"},
        asset_reader=lambda aid: {
            "id": aid,
            "provider_id": "nvidia",
            "model_id": "flux",
            "path": "",
        },
    )
    yield made
    store.close()


# ─────────────────────────────────────────────────────────────────────────────
# The platform registry
# ─────────────────────────────────────────────────────────────────────────────


def test_only_the_local_outbox_can_publish_today():
    """Stated rather than implied.

    Every real platform is declared with its official API; none has an adapter.
    A registry that quietly listed them as available would be the dishonest
    version of this.
    """
    assert publishable_platforms() == ("local_outbox",)


def test_every_real_platform_names_its_official_api_and_preconditions():
    for spec in (platform_spec(name) for name in ("instagram", "youtube", "facebook", "tiktok")):
        assert spec.api, f"{spec.id} must name the official route"
        assert spec.preconditions, f"{spec.id} must say what has to be true first"


def test_scheduling_to_a_platform_with_no_adapter_is_refused_with_the_route():
    with pytest.raises(PlatformNotPublishable) as exc:
        assert_publishable("instagram")
    message = str(exc.value)
    assert "Instagram Content Publishing API" in message
    assert "Nothing was scheduled" in message


def test_the_quota_that_is_not_per_account_is_recorded_as_such():
    """The detail people get wrong.

    YouTube's quota is per API project, so "more channels" does not mean more
    uploads. Instagram's is genuinely per account. A planner that assumed both
    were per account would over-promise on YouTube by however many channels
    there are.
    """
    youtube = platform_spec("youtube")
    assert youtube.shared_daily_budget and "per API project" in youtube.shared_daily_budget
    assert youtube.daily_posts_per_account == 0

    instagram = platform_spec("instagram")
    assert instagram.daily_posts_per_account == 25


def test_instagram_refuses_personal_accounts_by_name():
    spec = platform_spec("instagram")
    assert any("personal account" in item for item in spec.refuses)


def test_the_universal_refusals_say_why_not_just_what():
    assert len(UNIVERSAL_REFUSALS) >= 3
    for refusal in UNIVERSAL_REFUSALS:
        assert "—" in refusal or "banned" in refusal, refusal


def test_an_undeclared_platform_is_refused():
    with pytest.raises(UnknownPlatform):
        platform_spec("myspace")


def test_platforms_are_listed_publishable_first():
    ids = [item["id"] for item in list_platforms()]
    assert ids[0] == "local_outbox"


# ─────────────────────────────────────────────────────────────────────────────
# Accounts and posts
# ─────────────────────────────────────────────────────────────────────────────


def test_connecting_an_account_off_crm_cannot_post_to_is_refused(engine):
    """Storing it anyway would let a schedule be built against a dead end."""
    with pytest.raises(PlatformNotPublishable):
        engine.connect_account(platform="instagram", handle="@depot")
    assert engine.accounts() == []


def test_the_pipeline_runs_end_to_end(engine, tmp_path):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="Dawn at the depot")

    assert post["status"] == "draft"
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))

    result = engine.publish_due()
    assert result.published == 1 and result.failed == 0

    stored = engine.store.get_post(post["id"])
    assert stored["status"] == "published"
    assert stored["external_id"].startswith("local:")

    written = json.loads(
        (tmp_path / "outbox" / "local_outbox" / f"{post['id']}.json").read_text()
    )
    assert written["caption"] == "Dawn at the depot"


def test_a_post_must_be_approved_before_it_can_be_scheduled(engine):
    """Approval is the point at which a person agreed to it going out."""
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="x")
    with pytest.raises(ValueError) as exc:
        engine.schedule(post["id"], at=datetime.now(timezone.utc))
    assert "approved" in str(exc.value)


def test_a_future_post_is_not_published_yet(engine):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="later")
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) + timedelta(hours=2))
    assert engine.publish_due().published == 0


def test_a_publisher_failure_is_recorded_and_does_not_stop_the_round(engine):
    class Broken:
        def __init__(self):
            self.calls = 0

        def publish(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("platform returned 503")
            return {"external_id": "ok"}

    engine.publisher = Broken()
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    for caption in ("one", "two"):
        post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption=caption)
        engine.approve(post["id"])
        engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))

    result = engine.publish_due()
    assert result.failed == 1 and result.published == 1
    failed = engine.store.list_posts(CAMPAIGN, status="failed")
    assert "503" in failed[0]["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Goals and measurement
# ─────────────────────────────────────────────────────────────────────────────


def _publish(engine, caption="x", asset_id=""):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(
        CAMPAIGN, account_id=account["id"], caption=caption, asset_id=asset_id
    )
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))
    engine.publish_due()
    return post["id"]


def test_a_campaign_is_goal_shaped(engine):
    """"A million views", not "publish these posts"."""
    post_id = _publish(engine)
    engine.set_goal(CAMPAIGN, metric="views", target=1_000_000)

    engine.record_metrics(post_id, views=250_000, likes=900)
    progress = engine.progress(CAMPAIGN)
    goal = progress["goals"][0]
    assert goal["achieved"] == 250_000
    assert goal["remaining"] == 750_000
    assert goal["percent"] == 25.0
    assert goal["met"] is False


def test_later_readings_replace_earlier_ones_rather_than_adding(engine):
    """The bug this design exists to avoid.

    Views on Tuesday are not new views on Friday. Summing every snapshot would
    count the same view once per measurement and report a goal as met when it
    is not.
    """
    post_id = _publish(engine)
    engine.set_goal(CAMPAIGN, metric="views", target=100)

    engine.record_metrics(post_id, views=40)
    engine.record_metrics(post_id, views=60)

    progress = engine.progress(CAMPAIGN)
    assert progress["totals"]["views"] == 60, "the newest reading, not 40 + 60"
    assert progress["goals"][0]["met"] is False


def test_engagement_cannot_be_recorded_for_a_post_that_never_went_out(engine):
    """Otherwise fiction enters the benchmark."""
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="x")
    with pytest.raises(ValueError) as exc:
        engine.record_metrics(post["id"], views=10)
    assert "audience" in str(exc.value)


def test_views_are_attributed_back_to_the_generator_that_drew_the_picture(engine):
    """Layer three of the benchmark, joined to layer two.

    The swipe says what the owner liked; this says what got watched. They are
    the same generators, so the two can be compared — and can disagree, which is
    the whole reason for measuring both.
    """
    first = _publish(engine, caption="a", asset_id="asset-1")
    second = _publish(engine, caption="b", asset_id="asset-2")
    engine.record_metrics(first, views=1000)
    engine.record_metrics(second, views=3000)

    performance = engine.generator_performance(CAMPAIGN)
    assert len(performance) == 1
    row = performance[0]
    assert row["provider_id"] == "nvidia" and row["model_id"] == "flux"
    assert row["views"] == 4000
    assert row["views_per_post"] == 2000.0


def test_without_an_asset_reader_the_join_returns_nothing_rather_than_guessing(tmp_path):
    store = DistributionStore(tmp_path / "d.db", outbox_dir=tmp_path / "o")
    engine = DistributionEngine(
        store=store,
        publisher=LocalOutboxPublisher(tmp_path / "o"),
        campaign_reader=lambda cid: {"id": cid, "kind": "distribution"},
        asset_reader=None,
    )
    try:
        assert engine.generator_performance(CAMPAIGN) == []
    finally:
        store.close()


# ─────────────────────────────────────────────────────────────────────────────
# The kind gate, from the third side
# ─────────────────────────────────────────────────────────────────────────────


def test_the_distribution_runner_refuses_another_kind(tmp_path):
    """All three runners check now, so none can pick up another's work."""
    store = DistributionStore(tmp_path / "d.db", outbox_dir=tmp_path / "o")
    engine = DistributionEngine(
        store=store,
        publisher=LocalOutboxPublisher(tmp_path / "o"),
        campaign_reader=lambda cid: {"id": cid, "kind": "email"},
    )
    try:
        for call in (
            lambda: engine.progress(CAMPAIGN),
            lambda: engine.set_goal(CAMPAIGN, target=10),
            lambda: engine.plan_post(CAMPAIGN, account_id="x", caption="y"),
        ):
            with pytest.raises(WrongCampaignKind):
                call()
    finally:
        store.close()


def test_the_module_reaches_no_platform_directly():
    """Structural: publishing goes through an adapter, and there is one.

    A module that could call a platform from anywhere would make the registry in
    platforms.py advisory, which is exactly what it must not be.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "distribution"
    imported: set[str] = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")

    assert not (imported & {"requests", "httpx", "selenium", "playwright", "urllib.request"}), (
        imported
    )
