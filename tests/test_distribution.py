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


def test_a_publisher_failure_is_recorded_and_does_not_stop_the_round(engine, capsys):
    engine.workspace_id = "synthetic-workspace"
    class Broken:
        def __init__(self):
            self.calls = 0

        def publish(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("private-customer-content and secret-cookie")
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
    failures = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    assert len(failures) == 1
    assert failures[0]["error_id"] in failed[0]["error"]
    assert failures[0]["workspace"] == "synthetic-workspace"
    assert "private-customer-content" not in json.dumps(result.to_dict())
    assert "secret-cookie" not in failed[0]["error"]


def test_skip_is_final_and_cannot_be_published_or_changed_by_another_workspace(engine):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="review")
    engine.workspace_id = "other"
    with pytest.raises(KeyError):
        engine.skip(post["id"])
    engine.workspace_id = "local"
    assert engine.skip(post["id"])["status"] == "skipped"
    with pytest.raises(ValueError):
        engine.approve(post["id"])
    assert engine.publish_due().published == 0


def test_next_slot_keeps_approvals_and_spaces_posts_at_the_pair_rate(engine):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    now = datetime.now(timezone.utc)
    first = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="one")
    second = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="two")
    with pytest.raises(ValueError):
        engine.schedule_next(first["id"], posts_per_day=3, now=now)
    engine.approve(first["id"])
    engine.approve(second["id"])
    a = engine.schedule_next(first["id"], posts_per_day=3, now=now)
    b = engine.schedule_next(second["id"], posts_per_day=3, now=now)
    assert datetime.fromisoformat(b["scheduled_at"]) - datetime.fromisoformat(a["scheduled_at"]) == timedelta(hours=8)
    assert engine.publish_due(now=now + timedelta(minutes=1)).published == 1


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


def test_analyst_metrics_and_goals_never_mix_workspaces_with_shared_campaign_ids(engine):
    """A05: an overlapping global CRM ID is not permission to read another workspace."""
    own_post = engine.store.create_post(
        campaign_id=CAMPAIGN, account_id="ours", platform="local_outbox",
        caption="Own draft", asset_id="own-asset", workspace_id="local",
    )
    foreign_post = engine.store.create_post(
        campaign_id=CAMPAIGN, account_id="foreign", platform="local_outbox",
        caption="Private draft", asset_id="private-asset", workspace_id="other",
    )
    engine.store.set_goal(campaign_id=CAMPAIGN, target=100, workspace_id="local")
    engine.store.set_goal(campaign_id=CAMPAIGN, target=999, workspace_id="other")
    engine.store.record_metrics(
        post_id=own_post, campaign_id=CAMPAIGN, views=20, workspace_id="local",
    )
    engine.store.record_metrics(
        post_id=foreign_post, campaign_id=CAMPAIGN, views=900, workspace_id="other",
    )

    result = engine.progress(CAMPAIGN)
    assert result["totals"]["views"] == 20
    assert len(result["goals"]) == 1
    assert result["goals"][0]["target"] == 100
    assert result["posts"]["draft"] == 1

    # Generator performance is also scoped BEFORE aggregating or sorting.
    engine.store.connection.execute(
        "UPDATE dist_posts SET status='published' WHERE id IN (?,?)",
        (own_post, foreign_post),
    )
    ranked = engine.generator_performance(CAMPAIGN)
    assert len(ranked) == 1
    assert ranked[0]["posts"] == 1
    assert ranked[0]["views"] == 20


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


def test_no_module_here_can_drive_a_browser():
    """The refusal that protects the accounts.

    Browser automation is how "post to all your accounts" is usually done and
    how accounts get banned. It is refused everywhere, with no exception —
    unlike an HTTP client, which the read-only YouTube client legitimately
    needs and which `test_trends.py` scopes to that one module.
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

    assert not (imported & {"selenium", "playwright", "pyppeteer", "undetected_chromedriver"}), (
        imported
    )


def test_the_publishing_path_carries_no_transport():
    """Publishing goes through an adapter, and there is one.

    A module on this path that could call a platform directly would make the
    registry in platforms.py advisory, which is exactly what it must not be.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "distribution"
    for name in ("engine.py", "publishers.py", "platforms.py", "store.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert not (imported & {"requests", "httpx", "urllib.request"}), (name, imported)


def test_a_paused_campaign_publishes_nothing_and_the_post_waits(engine):
    """Pausing a campaign is the owner saying stop. Publishing used to check the
    account and never the campaign, so a scheduled post went out anyway — and a
    plan's Apply, which pauses every campaign it touches, said "nothing has sent"
    while it did (D-87). The post stays scheduled, so resuming sends it."""
    status = {"value": "active"}
    engine.campaign_reader = lambda cid: {"id": cid, "kind": "distribution", "status": status["value"]}
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="held")
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))

    for stopped in ("paused", "archived"):
        status["value"] = stopped
        result = engine.publish_due()
        assert (result.published, result.skipped) == (0, 1)
        assert stopped in result.details[0]["detail"]
        assert engine.store.get_post(post["id"])["status"] == "scheduled"

    status["value"] = "active"
    assert engine.publish_due().published == 1


def test_a_post_for_a_campaign_that_no_longer_exists_is_not_published(engine):
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="orphan")
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))

    def gone(cid):
        raise KeyError(f"Campaign not found: {cid}")

    engine.campaign_reader = gone
    result = engine.publish_due()
    assert (result.published, result.skipped) == (0, 1)
    assert "no longer exists" in result.details[0]["detail"]


def test_a_campaign_that_cannot_be_read_holds_its_posts_and_the_round_goes_on(engine):
    """Fail closed, and never let one campaign cost the round."""
    account = engine.connect_account(platform="local_outbox", handle="@depot")
    post = engine.plan_post(CAMPAIGN, account_id=account["id"], caption="unknown state")
    engine.approve(post["id"])
    engine.schedule(post["id"], at=datetime.now(timezone.utc) - timedelta(minutes=1))

    def broken(cid):
        raise RuntimeError("database is locked")

    engine.campaign_reader = broken
    result = engine.publish_due()
    assert (result.published, result.skipped) == (0, 1)
    assert "could not be read" in result.details[0]["detail"]


def test_concurrent_reviews_cannot_resurrect_a_skipped_post(engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    account = engine.connect_account(platform='local_outbox', handle='@review')
    for index in range(8):
        post = engine.plan_post(CAMPAIGN, account_id=account['id'], caption=str(index))
        ready = Barrier(2)
        def review(action):
            ready.wait(timeout=5)
            try:
                return action(post['id'])['status']
            except ValueError:
                return 'refused'
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(review, (engine.approve, engine.skip)))
        assert results.count('refused') == 1
        assert engine.store.get_post(post['id'])['status'] in ('approved', 'skipped')


def test_concurrent_scheduling_from_two_connections_allocates_distinct_slots(engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    account = engine.connect_account(platform='local_outbox', handle='@parallel')
    posts = [engine.plan_post(CAMPAIGN, account_id=account['id'], caption=str(i)) for i in range(2)]
    for post in posts:
        engine.approve(post['id'])
    other_store = DistributionStore(engine.store.target, outbox_dir=engine.store.outbox_dir)
    other = DistributionEngine(store=other_store, publisher=LocalOutboxPublisher(other_store.outbox_dir), campaign_reader=engine.campaign_reader)
    ready = Barrier(2)
    moment = datetime.now(timezone.utc)
    def schedule(pair):
        runner, post = pair
        ready.wait(timeout=5)
        return runner.schedule_next(post['id'], posts_per_day=3, now=moment)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(schedule, ((engine, posts[0]), (other, posts[1]))))
        dates = sorted(datetime.fromisoformat(row['scheduled_at']) for row in results)
        assert dates[1] - dates[0] == timedelta(hours=8)
    finally:
        other_store.close()


def test_next_slot_orders_legacy_offset_timestamps_by_actual_time(engine):
    account = engine.connect_account(platform='local_outbox', handle='@offsets')
    for at in ('2026-10-10T20:00:00+14:00', '2026-10-10T15:00:00+00:00'):
        post = engine.plan_post(CAMPAIGN, account_id=account['id'], caption=at)
        # Preserve actual pre-upgrade rows, including their original offsets.
        engine.store.update_post(post['id'], {'status': 'scheduled', 'scheduled_at': at})
    pending = engine.plan_post(CAMPAIGN, account_id=account['id'], caption='next')
    engine.approve(pending['id'])
    next_post = engine.schedule_next(pending['id'], posts_per_day=3, now=datetime(2026, 10, 9, tzinfo=timezone.utc))
    assert datetime.fromisoformat(next_post['scheduled_at']) == datetime(2026, 10, 10, 23, tzinfo=timezone.utc)


def test_legacy_offset_posts_publish_at_their_actual_due_time(engine):
    account = engine.connect_account(platform='local_outbox', handle='@due-offset')
    ids = []
    for at in ('2026-10-10T20:00:00+14:00', '2026-10-10T15:00:00+00:00'):
        post = engine.plan_post(CAMPAIGN, account_id=account['id'], caption=at)
        engine.store.update_post(post['id'], {'status': 'scheduled', 'scheduled_at': at})
        ids.append(post['id'])
    result = engine.publish_due(now=datetime(2026, 10, 10, 14, tzinfo=timezone.utc))
    assert result.published == 1
    assert engine.store.get_post(ids[0])['status'] == 'published'
    assert engine.store.get_post(ids[1])['status'] == 'scheduled'


def test_outbox_refuses_an_attachment_that_vanished_before_copying(tmp_path):
    publisher = LocalOutboxPublisher(tmp_path / 'outbox')
    with pytest.raises(FileNotFoundError):
        publisher.publish(platform='local_outbox', handle='@safe', caption='Requires its attachment', asset={'path': str(tmp_path / 'gone.png')}, post_id='missing-file')
    assert not list((tmp_path / 'outbox').rglob('*.json'))


def test_malformed_legacy_schedule_does_not_block_valid_publication(engine):
    account = engine.connect_account(platform='local_outbox', handle='@legacy-invalid')
    bad = engine.plan_post(CAMPAIGN, account_id=account['id'], caption='invalid')
    valid = engine.plan_post(CAMPAIGN, account_id=account['id'], caption='valid')
    engine.store.update_post(bad['id'], {'status': 'scheduled', 'scheduled_at': 'not-a-date'})
    engine.store.update_post(valid['id'], {'status': 'scheduled', 'scheduled_at': '2020-01-01T00:00:00Z'})
    result = engine.publish_due(now=datetime(2026, 10, 9, tzinfo=timezone.utc))
    assert result.published == 1
    assert engine.store.get_post(valid['id'])['status'] == 'published'
    quarantined = engine.store.get_post(bad['id'])
    assert quarantined['status'] == 'failed'
    assert 'E-' in quarantined['error']
    assert 'not-a-date' not in quarantined['error']
    assert result.failed == 1
    assert any(item['post_id'] == bad['id'] and item['detail'] == quarantined['error'] for item in result.details)


def test_malformed_legacy_schedule_does_not_block_next_slot(engine):
    account = engine.connect_account(platform='local_outbox', handle='@legacy-slot')
    bad = engine.plan_post(CAMPAIGN, account_id=account['id'], caption='invalid')
    pending = engine.plan_post(CAMPAIGN, account_id=account['id'], caption='next')
    engine.store.update_post(bad['id'], {'status': 'scheduled', 'scheduled_at': 'not-a-date'})
    engine.approve(pending['id'])
    moment = datetime(2026, 10, 9, tzinfo=timezone.utc)
    scheduled = engine.schedule_next(pending['id'], posts_per_day=3, now=moment)
    assert datetime.fromisoformat(scheduled['scheduled_at']) == moment
    assert engine.store.get_post(bad['id'])['status'] == 'failed'
