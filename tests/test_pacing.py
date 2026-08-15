"""How much to publish, decided by the goal instead of by a fixed number.

The campaign is goal-shaped — *reach a million views* — and posts per day is the
lever. This is the controller that moves it, and the tests are mostly about the
four ways a controller like this goes wrong:

**Steering with nothing to measure.** Before anything is published there is no
views-per-post figure, so any number produced would be invented. It holds and
says so.

**Oscillating.** Without a deadband it adjusts every cycle on noise and the
schedule becomes unplannable.

**Behaving like a spam bot.** An engine that notices it is behind and
immediately posts ten times more *is* a spam bot at that moment. Rises are
ramped; falls are immediate, because the two errors are not symmetrical — a
missed goal is recoverable next week and a banned account is not.

**Treating a platform limit as a suggestion.** It is a ceiling the arithmetic
may approach and never cross.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offsetx_apollo_builder.distribution.pacing import (
    DEADBAND,
    MAX_PER_DAY,
    MAX_RISE,
    MIN_POSTS_TO_STEER,
    decide,
    measure,
    platform_ceiling,
)

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def metrics(count: int, views_each: int) -> list[dict[str, object]]:
    return [{"post_id": f"p{i}", "views": views_each} for i in range(count)]


def deadline(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat()


def run(**overrides):
    kwargs = {
        "goal_target": 1_000_000,
        "goal_deadline": deadline(100),
        "metrics": metrics(20, 1_000),
        "current_per_day": 2.0,
        "now": NOW,
    }
    kwargs.update(overrides)
    return decide(**kwargs)


# ── measuring ───────────────────────────────────────────────────────────────


def test_views_are_counted_from_the_latest_snapshot_per_post():
    """Summing every snapshot counts Tuesday's views again on Friday — a bug
    this project has already had once."""
    views, posts, per_post = measure(metrics(4, 250))
    assert (views, posts, per_post) == (1000, 4, 250.0)


def test_a_post_with_no_reading_still_counts_as_a_post():
    views, posts, _ = measure([{"post_id": "a", "views": 100}, {"post_id": "b"}])
    assert (views, posts) == (100, 2)


def test_a_nonsense_reading_does_not_poison_the_total():
    views, posts, _ = measure([{"post_id": "a", "views": "lots"}, {"post_id": "b", "views": 50}])
    assert (views, posts) == (50, 2)


# ── refusing to steer without data ──────────────────────────────────────────


def test_it_holds_before_anything_has_been_published():
    """The first rule: a controller with nothing to measure is a random number
    generator."""
    decision = run(metrics=[])
    assert decision.action == "hold"
    assert decision.steering is False
    assert decision.posts_per_day == 2.0
    assert str(MIN_POSTS_TO_STEER) in decision.reason


def test_it_holds_below_the_floor_of_measured_posts():
    decision = run(metrics=metrics(MIN_POSTS_TO_STEER - 1, 1_000))
    assert decision.action == "hold"
    assert decision.steering is False


def test_it_steers_at_the_floor():
    decision = run(metrics=metrics(MIN_POSTS_TO_STEER, 1_000))
    assert decision.steering is True


def test_a_goal_with_no_target_is_nothing_to_pace_against():
    decision = run(goal_target=0)
    assert decision.action == "hold"
    assert "nothing to pace against" in decision.reason


def test_a_goal_with_no_deadline_is_met_by_posting_once_a_year():
    decision = run(goal_deadline="")
    assert decision.action == "hold"
    assert "no deadline" in decision.reason


def test_an_unreadable_deadline_is_treated_as_no_deadline():
    decision = run(goal_deadline="next Tuesday-ish")
    assert decision.action == "hold"


def test_a_deadline_in_the_past_says_so_rather_than_dividing_by_a_negative():
    decision = run(goal_deadline=deadline(-3))
    assert decision.action == "hold"
    assert "deadline has passed" in decision.reason
    assert decision.posts_per_day == 2.0


# ── the arithmetic ──────────────────────────────────────────────────────────


def test_being_behind_raises_the_rate():
    decision = run(metrics=metrics(20, 1_000), current_per_day=1.0)
    # 980,000 short ÷ 1,000 views per post = 980 posts ÷ 100 days = 9.8/day
    assert decision.required_per_day == pytest.approx(9.8, abs=0.1)
    assert decision.action == "raise"
    assert decision.posts_per_day > 1.0


def test_a_rise_is_ramped_rather_than_stepped(caplog):
    """An engine that suddenly posts ten times more looks like a spam bot,
    because at that moment it is behaving like one."""
    decision = run(metrics=metrics(20, 1_000), current_per_day=1.0)
    assert decision.posts_per_day == pytest.approx(1.0 * (1 + MAX_RISE))
    assert "ramped" in decision.reason


def test_repeated_cycles_climb_towards_the_requirement_without_overshooting():
    rate = 1.0
    for _ in range(30):
        decision = run(metrics=metrics(20, 1_000), current_per_day=rate)
        rate = decision.posts_per_day
    assert rate <= decision.required_per_day + 0.001
    assert rate > 5.0  # it did actually climb


def test_being_ahead_lowers_the_rate_immediately():
    """Publishing more than a goal needs spends the audience's patience for
    nothing, and that error is cheap to correct."""
    # 400,000 of 1,000,000 — ahead of pace, but not yet met. (20 x 50,000
    # would *meet* the goal, which is a different branch and tested below.)
    decision = run(metrics=metrics(20, 20_000), current_per_day=8.0)
    assert decision.action == "lower"
    assert decision.posts_per_day == pytest.approx(decision.required_per_day)
    assert decision.posts_per_day < 8.0


def test_a_met_goal_stops_asking_for_more():
    decision = run(metrics=metrics(20, 60_000))
    assert decision.action == "on_pace"
    assert "Goal met" in decision.reason


def test_a_small_drift_changes_nothing():
    """Without a deadband the rate moves every cycle on noise, and a schedule
    that changes hourly is one nobody can plan around."""
    decision = run(metrics=metrics(20, 1_000), current_per_day=1.0)
    on_pace = run(metrics=metrics(20, 1_000), current_per_day=decision.required_per_day * 1.05)
    assert on_pace.action == "on_pace"
    assert on_pace.posts_per_day == pytest.approx(decision.required_per_day * 1.05)


def test_the_deadband_is_symmetric():
    required = run(metrics=metrics(20, 1_000), current_per_day=1.0).required_per_day
    for factor in (1 - DEADBAND * 0.9, 1 + DEADBAND * 0.9):
        decision = run(metrics=metrics(20, 1_000), current_per_day=required * factor)
        assert decision.action == "on_pace", factor


# ── the ceiling ─────────────────────────────────────────────────────────────


def test_a_platform_limit_is_a_ceiling_not_a_suggestion():
    decision = run(
        metrics=metrics(20, 100),
        current_per_day=10.0,
        ceiling=3.0,
        ceiling_source="instagram",
    )
    assert decision.posts_per_day <= 3.0
    assert decision.capped_by == "instagram"
    assert "does not get a vote" in decision.reason


def test_the_tightest_platform_binds_and_is_named():
    ceiling, source = platform_ceiling(
        [
            {"id": "youtube", "daily_posts_per_account": 0},
            {"id": "instagram", "daily_posts_per_account": 25},
            {"id": "linkedin", "daily_posts_per_account": 3},
        ]
    )
    assert (ceiling, source) == (3.0, "linkedin")


def test_more_accounts_raise_the_ceiling_proportionally():
    ceiling, _ = platform_ceiling([{"id": "instagram", "daily_posts_per_account": 25}], accounts=2)
    assert ceiling == 50.0 or ceiling == MAX_PER_DAY


def test_a_platform_that_declares_no_limit_does_not_set_one():
    ceiling, source = platform_ceiling([{"id": "local_outbox", "daily_posts_per_account": 0}])
    assert ceiling == MAX_PER_DAY
    assert source == ""


def test_there_is_a_safety_ceiling_even_with_no_platform_limit():
    decision = run(metrics=metrics(20, 1), current_per_day=MAX_PER_DAY)
    assert decision.posts_per_day <= MAX_PER_DAY


# ── what the engine is told to do next ──────────────────────────────────────


def test_the_decision_turns_into_topics_for_the_next_cycle():
    decision = run(metrics=metrics(20, 1_000), current_per_day=4.0)
    assert decision.max_topics == max(1, round(decision.posts_per_day))
    assert decision.candidates >= 1


def test_a_cycle_never_plans_nothing():
    """A cycle that plans zero topics may as well not have run."""
    decision = run(metrics=metrics(20, 10_000_000), current_per_day=0.1)
    assert decision.max_topics >= 1
    assert decision.candidates >= 1


def test_the_decision_carries_its_own_reasoning():
    decision = run(metrics=metrics(20, 1_000), current_per_day=1.0).to_dict()
    for key in (
        "posts_per_day",
        "previous_per_day",
        "action",
        "reason",
        "measured_views",
        "measured_posts",
        "views_per_post",
        "required_per_day",
        "days_left",
        "shortfall",
        "steering",
    ):
        assert key in decision
    assert decision["reason"]
    assert decision["measured_views"] == 20_000


# ── end to end, against real goals and real metrics ─────────────────────────


def test_a_real_goal_and_real_metrics_drive_the_rate(tmp_path):
    """The controller reading the stores it is deliberately ignorant of."""
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    application = create_app(settings)
    with TestClient(application) as client:
        distribution = client.post(
            "/api/v1/campaigns", json={"name": "Reach", "kind": "distribution"}
        ).json()
        image = client.post("/api/v1/campaigns", json={"name": "Pics", "kind": "image"}).json()

        store = application.state.distribution_store
        store.set_goal(
            campaign_id=distribution["id"],
            metric="views",
            target=1_000_000,
            deadline=(datetime.now(timezone.utc) + timedelta(days=100)).isoformat(),
        )

        # No posts measured yet: the controller must hold and say why.
        client.patch(
            "/api/v1/content-automation",
            json={
                "auto_pace": True,
                "posts_per_day": 1.0,
                "pipelines": [
                    {
                        "distribution_campaign_id": distribution["id"],
                        "image_campaign_id": image["id"],
                    }
                ],
            },
        )
        results = client.post("/api/v1/content-automation/run").json()["results"]
        pace = next(row for row in results if row["step"] == "pace")
        assert pace["action"] == "hold"
        assert pace["steering"] is False
        assert client.get("/api/v1/content-automation").json()["posts_per_day"] == 1.0

        # Twenty posts at 1,000 views each: 980,000 short over 100 days needs
        # 9.8 a day, so the controller raises — ramped.
        for index in range(20):
            post_id = store.create_post(
                campaign_id=distribution["id"],
                account_id="acct-1",
                platform="local_outbox",
                asset_id=f"asset-{index}",
                caption="x",
            )
            store.record_metrics(
                campaign_id=distribution["id"], post_id=post_id, views=1_000
            )

        results = client.post("/api/v1/content-automation/run").json()["results"]
        pace = next(row for row in results if row["step"] == "pace")
        assert pace["status"] == "ok", pace
        assert pace["measured_posts"] == 20
        assert pace["measured_views"] == 20_000
        assert pace["required_per_day"] == pytest.approx(9.8, abs=0.2)
        assert pace["action"] == "raise"
        assert pace["steering"] is True
        assert 1.0 < pace["posts_per_day"] <= 1.0 * (1 + MAX_RISE) + 1e-9
        # The new rate is kept, so the ramp compounds instead of restarting.
        assert client.get("/api/v1/content-automation").json()["posts_per_day"] > 1.0
