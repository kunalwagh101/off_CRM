"""S-12.02.03 — the brain says where it is going wrong, in a fixed order.

The diagnosis is deterministic and most of these tests pin its order, because
the order is the design: the pipe before the copy, and a broken pipe before an
idle one. A model only chooses among remedies the diagnosis already permits.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.gtm.review import (
    REMEDIES,
    ReviewRefused,
    baseline_remedies,
    contacts_to_decide,
    diagnose,
    parse_remedies,
    wilson_interval,
)
from broker_fakes import fake_model_calls

NOW = "2026-09-22T12:00:00+00:00"


def plan(*, applied_at="2026-09-22T09:00:00+00:00", volume=30, weekdays="weekdays",
         goal_kind="replies", rate=0.034):
    return {
        "id": "plan-1",
        "status": "applied",
        "applied_at": applied_at,
        "request": {"goal_kind": goal_kind, "goal_target": 20, "horizon_days": 30,
                    "assumed_reply_rate": rate},
        "plan": {
            "summary": "",
            "audience": {"description": "", "source": "existing_contacts"},
            "channels": [
                {"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h",
                 "daily_volume": volume, "weekdays": weekdays},
                {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h",
                 "daily_volume": 1, "platforms": ["youtube"]},
                {"kind": "image", "role": "support", "angle": "a", "hypothesis": "h"},
            ],
        },
        "product_snapshot": {"forbidden_claims": ["guaranteed"]},
    }


def email(**overrides):
    values = {
        "channel": "email",
        "campaign_id": "c-email",
        "status": "active",
        "contacts": 500,
        "contacted": 300,
        "replied": 10,
        "drafts_pending": 0,
        "health": {"breached": [], "paused_reason": "", "accepted": 300,
                   "hard_bounce_rate": 0.0, "complaint_rate": 0.0},
        "weak_templates": 0,
    }
    values.update(overrides)
    return values


def distribution(**overrides):
    values = {
        "channel": "distribution",
        "campaign_id": "c-dist",
        "status": "active",
        "accounts": 1,
        "published": 6,
        "pacing": None,
    }
    values.update(overrides)
    return values


def image():
    return {"channel": "image", "campaign_id": "c-img", "status": "paused"}


def email_finding(measure, **plan_kwargs):
    findings = diagnose(plan(**plan_kwargs), [measure, distribution(), image()],
                        min_sample=20, now=NOW)
    return next(item for item in findings if item.channel == "email")


# ── criterion 1: delivery before copy ───────────────────────────────────────


def test_delivery_is_diagnosed_before_copy():
    # A reply rate anyone would celebrate, on mail that is bouncing.
    finding = email_finding(email(replied=90, health={
        "breached": ["hard_bounce_rate"], "paused_reason": "", "accepted": 300,
        "hard_bounce_rate": 0.06, "complaint_rate": 0.0,
    }))
    assert finding.code == "delivery_unhealthy"
    assert "raise_volume" not in finding.permitted
    assert set(finding.permitted) == {"fix_list_quality", "check_domain_authentication", "reduce_volume"}
    assert "6.0%" in finding.sentence


def test_a_campaign_paused_for_bouncing_is_never_told_to_resume():
    """The health auto-pause sets the campaign's own status to `paused`. Read in
    the wrong order that looks like "not started — resume it", the one piece of
    advice that does real damage."""
    finding = email_finding(email(status="paused", health={
        "breached": [], "paused_reason": "complaint rate above threshold", "accepted": 300,
        "hard_bounce_rate": 0.0, "complaint_rate": 0.004,
    }))
    assert finding.code == "delivery_unhealthy"
    assert "resume_campaign" not in finding.permitted


# ── criterion 2: the order is fixed ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("expected", "overrides", "applied_at"),
    [
        # Each case keeps every *later* condition true as well, so the test
        # proves the earlier one wins rather than merely that it fires alone.
        ("not_started", {"status": "paused", "contacts": 0, "contacted": 0, "drafts_pending": 4},
         "2026-09-08T09:00:00+00:00"),
        ("no_contacts", {"contacts": 0, "contacted": 0, "drafts_pending": 4},
         "2026-09-08T09:00:00+00:00"),
        ("awaiting_approval", {"contacts": 400, "contacted": 5, "drafts_pending": 4},
         "2026-09-08T09:00:00+00:00"),
        ("under_volume", {"contacts": 400, "contacted": 5, "drafts_pending": 0},
         "2026-09-08T09:00:00+00:00"),
        ("insufficient_data", {"contacts": 400, "contacted": 12, "replied": 0},
         "2026-09-22T09:00:00+00:00"),
    ],
)
def test_the_order_is_fixed(expected, overrides, applied_at):
    finding = email_finding(email(**overrides), applied_at=applied_at)
    assert finding.code == expected, finding.sentence


def test_under_volume_points_at_causes_not_more_volume():
    finding = email_finding(email(contacted=5, contacts=8), applied_at="2026-09-08T09:00:00+00:00")
    assert finding.code == "under_volume"
    assert "raise_volume" not in finding.permitted
    assert set(finding.permitted) == {"add_contacts", "check_send_settings"}
    # 30 a day over the 10 weekdays since 8 September.
    assert finding.numbers["expected_contacted"] == 300


# ── criterion 3: no verdict without enough data ─────────────────────────────


def test_no_verdict_without_enough_data():
    finding = email_finding(email(contacted=12, replied=6))
    assert finding.code == "insufficient_data"
    assert finding.permitted == ("wait_for_data",)
    assert "8 more" in finding.sentence


# ── criterion 4: an interval, not a threshold ───────────────────────────────


def test_verdict_uses_an_interval_not_a_threshold():
    behind = email_finding(email(contacted=400, replied=2))
    assert behind.code == "behind_target"
    assert {"test_new_angle", "narrow_audience", "change_offer"} <= set(behind.permitted)
    assert "rewrite_weak_template" not in behind.permitted  # no weak template to rewrite

    with_weak = email_finding(email(contacted=400, replied=2, weak_templates=1))
    assert "rewrite_weak_template" in with_weak.permitted

    ahead = email_finding(email(contacted=200, replied=30))
    assert ahead.code == "ahead_of_target"
    assert set(ahead.permitted) == {"hold", "raise_volume"}

    unclear = email_finding(email(contacted=150, replied=5))
    assert unclear.code == "inconclusive"
    assert unclear.numbers["contacts_to_decide"] is not None
    assert "more" in unclear.sentence

    # Zero replies from forty is 25% likely at a true 3.4% rate. Calling that
    # "behind" would be the threshold mistake bandit.py was written against.
    silent = email_finding(email(contacted=40, replied=0))
    assert silent.code == "inconclusive"


def test_wilson_interval_matches_the_sales_trackers():
    """Repeated here because importing outreach.sales pulls in the engine (DD-47).
    This test is what holds the two copies equal."""
    from offsetx_apollo_builder.outreach.sales import _wilson_interval

    for successes, total in [(0, 1), (0, 40), (2, 400), (5, 150), (30, 200), (7, 7), (0, 0)]:
        assert wilson_interval(successes, total) == _wilson_interval(successes, total)


def test_contacts_to_decide_is_the_same_statistic_as_the_verdict():
    # 5 from 150 is 3.3%, and its range (to 5.8%) still includes 5.1%.
    needed = contacts_to_decide(5, 150, 0.051)
    assert needed is not None and needed > 150
    _, high = wilson_interval(round(5 / 150 * needed), needed)
    assert high < 0.051
    _, high = wilson_interval(round(5 / 150 * (needed - 1)), needed - 1)
    assert high >= 0.051  # the first total that decides it, not merely one that does
    # Already decided: nobody more is needed.
    assert contacts_to_decide(5, 150, 0.068) == 150
    # The same measured rate as the assumption can never be told apart.
    assert contacts_to_decide(34, 1000, 0.034) is None


# ── criterion 5: distribution follows the pacer ─────────────────────────────


def pacer(action=None, *, views=(), deadline="2026-12-01", current=1.0, owner_cap=0.0):
    """A real `pacing.decide()` — so the mapping is pinned to what the pacer says,
    not to a dictionary shaped like it."""
    from datetime import datetime, timezone

    from offsetx_apollo_builder.distribution import pacing

    decision = pacing.decide(
        goal_target=100_000, goal_deadline=deadline, metrics=[{"views": v} for v in views],
        current_per_day=current, now=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
        owner_cap=owner_cap,
    )
    if action:
        assert decision.action == action, decision.reason
    return decision.to_dict()


def distribution_finding(pacing, **plan_kwargs):
    findings = diagnose(plan(goal_kind="views", **plan_kwargs),
                        [email(), distribution(pacing=pacing), image()], min_sample=20, now=NOW)
    return next(item for item in findings if item.channel == "distribution")


@pytest.mark.parametrize(
    ("action", "views", "expected"),
    [
        ("hold", [], "insufficient_data"),              # nothing measured to divide by
        ("raise", [100] * 6, "behind_target"),          # 100 views a post will not reach 100k
        ("lower", [10_000] * 6, "ahead_of_target"),     # four more posts would do it
        ("on_pace", [20_000] * 6, "on_track"),          # the goal is already met
    ],
)
def test_distribution_review_follows_the_pacers_action(action, views, expected):
    decision = pacer(action, views=views)
    found = distribution_finding(decision)
    assert found.code == expected
    assert decision["reason"] in found.sentence


def test_a_pacer_holding_for_the_goal_not_the_data_is_not_told_to_wait():
    """The pacer also holds when the goal's deadline has passed, and lowers to the
    owner's cap before any goal arithmetic. Neither is "not enough data", and
    "wait" would be advice to wait for something that is not coming."""
    passed = distribution_finding(pacer("hold", views=[500] * 6, deadline="2026-09-01"))
    assert passed.code == "pacer_idle"
    assert "wait_for_data" not in passed.permitted
    capped = distribution_finding(pacer("lower", views=[500] * 6, current=3.0, owner_cap=1.0))
    assert capped.code == "pacer_idle"


def test_a_pacer_holding_for_a_dead_goal_is_idle_even_with_few_posts():
    """Below five measured posts the pacer holds for want of data — and also for
    a passed deadline or a goal of nothing. Only the first is "wait"."""
    passed = distribution_finding(pacer("hold", views=[500] * 3, deadline="2026-09-01"))
    assert passed.code == "pacer_idle"
    no_deadline = distribution_finding(pacer("hold", views=[500] * 3, deadline=""))
    assert no_deadline.code == "pacer_idle"
    waiting = distribution_finding(pacer("hold", views=[500] * 3))
    assert waiting.code == "insufficient_data"


def test_what_the_brain_needs_survives_the_shape_filter():
    """Below `full` the payload builder widens numbers ("5%" becomes "a share").
    The brain's arithmetic is all in code, so what a model needs is the finding
    codes and the actions it may choose — and those must survive the filter."""
    from offsetx_apollo_builder.ai.payload import EgressRequest, build_payload
    from offsetx_apollo_builder.ai.tiers import DataClass, DataPolicy
    from offsetx_apollo_builder.gtm.review import review_fields

    findings = diagnose(plan(), [email(contacted=400, replied=2, weak_templates=1),
                                 distribution(accounts=0), image()], min_sample=20, now=NOW)
    fields = review_fields({**plan(), "created_at": "2026-09-22T09:00:00+00:00"}, findings,
                           {"name": "N", "one_liner": "O", "audience": "A", "problem": "P", "offer": "F"})
    built = build_payload(
        EgressRequest(task_type="gtm_review", data_class=DataClass.CAMPAIGN, **fields),
        DataPolicy.STANDARD,
    )
    for item in findings:
        assert item.code in built["instructions"]
        for action in item.permitted:
            assert action in built["instructions"]


def test_distribution_is_checked_for_accounts_status_and_posts_first():
    def code(**overrides):
        found = diagnose(plan(), [email(), distribution(**overrides), image()], min_sample=20, now=NOW)
        return next(i for i in found if i.channel == "distribution")

    assert code(accounts=0, published=0).code == "no_account"
    assert code(status="paused", published=0).code == "not_started"
    assert code(status="paused").permitted == ("resume_campaign",)
    assert code(status="archived").code == "archived"
    # Active and still silent: resuming would be advice for a campaign already
    # running, so the finding names what is actually missing.
    idle = code(published=0)
    assert idle.code == "nothing_published"
    assert idle.permitted == ("set_up_posting",)
    assert code().code == "supporting"


def test_after_the_window_the_plan_is_over_not_short_of_data():
    found = distribution_finding(pacer("hold", views=[]), applied_at="2026-08-01T09:00:00+00:00")
    assert found.code == "window_ended"
    assert "2026-08-31" in found.sentence


def test_expected_sends_stop_at_the_end_of_the_window():
    # Applied Saturday 1 August with a 30-day horizon: 20 weekdays before the
    # window closes on 31 August, not the 36 there are before 22 September.
    finding = email_finding(email(contacted=5, contacts=8), applied_at="2026-08-01T09:00:00+00:00")
    assert finding.numbers["send_days"] == 20
    assert finding.numbers["expected_contacted"] == 600


def test_an_archived_email_campaign_is_not_told_to_resume():
    finding = email_finding(email(status="archived"))
    assert finding.code == "archived"
    assert finding.permitted == ()


def test_min_sample_matches_the_context_layers_floor():
    from offsetx_apollo_builder.ai.context import MIN_SENDS_TO_JUDGE
    from offsetx_apollo_builder.gtm.review import MIN_SAMPLE

    assert MIN_SAMPLE == MIN_SENDS_TO_JUDGE


def test_images_are_left_to_the_swipe_queue():
    findings = diagnose(plan(), [email(), distribution(), image()], min_sample=20, now=NOW)
    found = next(item for item in findings if item.channel == "image")
    assert found.code == "supporting"
    assert found.permitted == ()


def test_a_missing_measurement_is_a_finding_not_a_crash():
    findings = diagnose(plan(), [email()], min_sample=20, now=NOW)
    missing = next(item for item in findings if item.channel == "distribution")
    assert missing.code == "no_campaign"


# ── criterion 6: a model's remedies are checked ─────────────────────────────


def _findings():
    return diagnose(plan(), [email(contacted=400, replied=2), distribution(), image()],
                    min_sample=20, now=NOW)


def test_remedies_outside_the_permitted_set_are_dropped():
    text = json.dumps({
        "summary": "Change the angle.",
        "remedies": [
            {"channel": "email", "action": "test_new_angle", "why": "It is not landing.",
             "proposal": "Lead with the overbilling number."},
            {"channel": "email", "action": "raise_volume", "why": "More!"},
            {"channel": "telegram", "action": "hold", "why": "?"},
            {"channel": "email", "action": "change_offer", "why": "w",
             "proposal": "Savings guaranteed or your money back."},
            {"channel": "email", "action": "narrow_audience", "why": "w", "proposal": "Only 3PLs."},
            {"channel": "email", "action": "rewrite_weak_template", "why": "w"},
        ],
    })
    parsed = parse_remedies(text, findings=_findings(), product={"forbidden_claims": ["guaranteed"]})
    kept = [(item["channel"], item["action"]) for item in parsed.remedies]
    assert kept == [("email", "test_new_angle"), ("email", "narrow_audience")]
    joined = " ".join(parsed.notes)
    for named in ("raise_volume", "telegram", "guaranteed", "rewrite_weak_template"):
        assert named in joined
    assert "guaranteed" not in json.dumps(parsed.remedies)


def test_a_reply_that_is_not_json_is_refused():
    with pytest.raises(ReviewRefused):
        parse_remedies("Just keep going.", findings=_findings(), product={})
    with pytest.raises(ReviewRefused):
        parse_remedies('{"summary": "fine"}', findings=_findings(), product={})


def test_a_finding_the_model_skipped_still_gets_the_rules_remedy():
    """A model that only talks about the copy must not bury "no account connected"."""
    findings = diagnose(plan(), [email(contacted=400, replied=2), distribution(accounts=0), image()],
                        min_sample=20, now=NOW)
    text = json.dumps({"summary": "s", "remedies": [
        {"channel": "email", "action": "test_new_angle", "why": "w", "proposal": "p"}]})
    parsed = parse_remedies(text, findings=findings, product={})
    kept = [(item["channel"], item["action"]) for item in parsed.remedies]
    assert kept == [("email", "test_new_angle"), ("distribution", "connect_account")]
    assert any("distribution" in note for note in parsed.notes)


def test_no_model_review_uses_rules():
    parsed = baseline_remedies(_findings())
    by_channel = {item["channel"]: item["action"] for item in parsed.remedies}
    assert by_channel["email"] == "test_new_angle"
    assert "image" not in by_channel  # nothing permitted, nothing invented
    assert parsed.source == "rules"


def test_every_remedy_names_a_screen_that_exists_or_the_next_plan():
    pages = {"contacts", "deliverability", "campaigns", "drafts", "memory", "posting", "product", ""}
    for action, (page, label) in REMEDIES.items():
        assert page in pages, action
        assert label.endswith(".")


# ── through the service and over HTTP ───────────────────────────────────────

PRODUCT = {
    "name": "Zephyrledger",
    "one_liner": "Zephyrledger reconciles freight invoices overnight for you.",
    "audience": "Quartermaster finance leads at mid-size freight forwarders.",
    "problem": "Carriers overbill by marmalade margins nobody audits.",
    "offer": "a walkthrough on your own invoices",
}


def model_plan():
    return json.dumps({
        "summary": "Email first.",
        "audience": {"description": "Finance leads.", "source": "existing_contacts"},
        "channels": [
            {"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h", "daily_volume": 20},
            {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h",
             "daily_volume": 1, "platforms": ["youtube"]},
        ],
    })


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )
    with TestClient(create_app(settings)) as opened:
        yield opened


def _applied_plan(client, monkeypatch, *, review_reply=None):
    seen: dict[str, list] = {"requests": [], "prompts": []}

    def call(request, settings, **kwargs):
        seen["requests"].append(request)
        seen["prompts"].append(kwargs.get("system_prompt", ""))
        text = model_plan() if request.task_type == "gtm_plan" else (review_reply or "{}")
        return SimpleNamespace(text=text, provider_id="p", model_id="m", policy="standard")

    fake_model_calls(monkeypatch, client.app.state.ai_broker, call)
    product = client.post("/api/v1/gtm/products", json=PRODUCT).json()
    plan_body = client.post("/api/v1/gtm/plans", json={
        "product_id": product["id"], "goal_kind": "replies", "goal_target": 20,
    }).json()
    applied = client.post(f"/api/v1/gtm/plans/{plan_body['id']}/apply").json()
    return plan_body, applied, seen


def test_review_stores_what_it_measured(client, monkeypatch):
    plan_body, applied, _ = _applied_plan(client, monkeypatch, review_reply=json.dumps({
        "summary": "Start the campaign.",
        "remedies": [{"channel": "email", "action": "resume_campaign", "why": "It is paused."}],
    }))
    reviewed = client.post(f"/api/v1/gtm/plans/{plan_body['id']}/review", json={})
    assert reviewed.status_code == 201, reviewed.text
    review = reviewed.json()

    email_id = next(item["campaign_id"] for item in applied["campaigns"] if item["kind"] == "email")
    measured = {item["channel"]: item for item in review["measurements"]}
    assert measured["email"]["campaign_id"] == email_id
    assert measured["email"]["status"] == "paused"
    assert measured["email"]["contacts"] == 0
    assert measured["distribution"]["accounts"] == 0
    finding = next(item for item in review["findings"] if item["channel"] == "email")
    assert finding["code"] == "not_started"
    assert review["remedies"][0]["action"] == "resume_campaign"
    assert review["remedies"][0]["page"] == "campaigns"
    assert review["source"] == "model"

    stored = client.get(f"/api/v1/gtm/plans/{plan_body['id']}").json()
    assert stored["review"]["id"] == review["id"]


def test_the_review_request_is_campaign_class_and_the_prompt_code_only(client, monkeypatch):
    from offsetx_apollo_builder.ai.tiers import DataClass

    plan_body, _, seen = _applied_plan(client, monkeypatch)
    client.post(f"/api/v1/gtm/plans/{plan_body['id']}/review", json={})
    sent = seen["requests"][-1]
    assert sent.task_type == "gtm_review"
    assert sent.data_class is DataClass.CAMPAIGN
    for value in PRODUCT.values():
        assert value not in seen["prompts"][-1]
        assert value not in sent.instructions
    assert "not_started" in sent.instructions


def test_a_review_with_no_model_uses_rules_and_says_so(client, monkeypatch):
    plan_body, _, _ = _applied_plan(client, monkeypatch)
    monkeypatch.undo()  # the real broker, with nothing connected
    review = client.post(f"/api/v1/gtm/plans/{plan_body['id']}/review", json={}).json()
    assert review["source"] == "rules"
    assert any("rules" in note for note in review["notes"])
    assert review["remedies"][0]["action"] == "resume_campaign"


def test_review_needs_an_applied_plan(client, monkeypatch):
    seen = {"n": 0}

    def call(request, settings, **kwargs):
        seen["n"] += 1
        return SimpleNamespace(text=model_plan(), provider_id="p", model_id="m", policy="standard")

    fake_model_calls(monkeypatch, client.app.state.ai_broker, call)
    product = client.post("/api/v1/gtm/products", json=PRODUCT).json()
    draft = client.post("/api/v1/gtm/plans", json={
        "product_id": product["id"], "goal_kind": "replies", "goal_target": 20,
    }).json()
    refused = client.post(f"/api/v1/gtm/plans/{draft['id']}/review", json={})
    assert refused.status_code == 409
    assert refused.json()["detail"]["error"] == "wrong_state"
    assert client.post("/api/v1/gtm/plans/no-such/review", json={}).status_code == 404


# ── through the service, with plain functions for everything it reads ───────


def _service(tmp_path, *, goal_kind="replies", accounts=(), ask=None, **reads):
    """A real store and service; the CRM, health and pacer are dictionaries."""
    from contextlib import nullcontext
    from itertools import count

    from offsetx_apollo_builder.gtm.service import GtmService, Readers
    from offsetx_apollo_builder.gtm.store import GtmStore

    campaigns: dict[str, dict] = {}
    numbers = count(1)
    seen: dict[str, list] = {"pacing": [], "asked": []}

    def create_campaign(**values):
        campaign_id = f"c{next(numbers)}"
        campaigns[campaign_id] = {"id": campaign_id, "status": "active", **values}
        return campaign_id

    def pacing(campaign_id):
        seen["pacing"].append(campaign_id)
        return reads.get("pacing") or {"action": "hold", "reason": "Only 0 post(s).",
                                       "measured_posts": 0, "steering": False}

    def asked(**kwargs):
        seen["asked"].append(kwargs)
        return ask(**kwargs)

    readers = Readers(
        campaign=lambda campaign_id: campaigns[campaign_id],
        email_summary=lambda campaign_id: reads.get("summary") or {},
        health=lambda campaign_id: reads.get("health") or {"breached": [], "paused_reason": ""},
        weak_templates=lambda: reads.get("weak", 0),
        published=lambda campaign_id: reads.get("published", 0),
        pacing=pacing,
    )
    store = GtmStore(tmp_path / "gtm.db")
    service = GtmService(
        store, workspace_id="w", identities=lambda: [], accounts=lambda: list(accounts),
        apollo_ready=lambda: False, ask=asked if ask else None,
        create_campaign=create_campaign,
        update_campaign=lambda campaign_id, changes: campaigns[campaign_id].update(changes),
        set_goal=lambda **values: None, goals_of=lambda campaign_id: [],
        lock=lambda key: nullcontext(), readers=readers,
    )
    product = store.create_product("w", {**PRODUCT, "forbidden_claims": ["guaranteed"]})
    drafted = service.draft_plan({"product_id": product["id"], "goal_kind": goal_kind,
                                  "goal_target": 20, "use_model": False})
    applied = service.apply_plan(drafted["id"])
    by_kind = {item["kind"]: item["campaign_id"] for item in applied["campaigns"]}
    return service, drafted["id"], campaigns, by_kind, seen


YOUTUBE = {"platform": "youtube", "daily_cap": 1, "enabled": 1}


def _found(review, channel):
    return next(item for item in review["findings"] if item["channel"] == channel)


def test_contacted_and_replies_come_from_the_crm_summary(tmp_path):
    """Contacted is people sent a first email, not every message: a follow-up
    is a second message to someone already counted."""
    service, plan_id, campaigns, _, _ = _service(tmp_path, summary={
        "contacts": 400,
        "messages_by_stage": {"initial": 300, "followup1": 200},
        "contact_status": {"replied": 10, "active": 390},
        "draft_status": {"pending": 3, "approved": 9},
    })
    review = service.review_plan(plan_id, {})
    email_measured = next(item for item in review["measurements"] if item["channel"] == "email")
    assert (email_measured["contacts"], email_measured["contacted"], email_measured["replied"],
            email_measured["drafts_pending"]) == (400, 300, 10, 3)


def test_a_disabled_account_is_not_somewhere_to_post(tmp_path):
    service, plan_id, *_ = _service(tmp_path, goal_kind="views",
                                    accounts=[{**YOUTUBE, "enabled": 0}])
    review = service.review_plan(plan_id, {})
    assert _found(review, "distribution")["code"] == "no_account"


def test_a_deleted_campaign_is_a_finding_not_a_crash(tmp_path):
    service, plan_id, campaigns, by_kind, _ = _service(tmp_path)
    del campaigns[by_kind["email"]]
    review = service.review_plan(plan_id, {})
    assert _found(review, "email")["code"] == "no_campaign"
    assert review["measurements"][0]["missing"] is True


def test_only_a_views_plan_asks_the_pacer(tmp_path):
    service, plan_id, _, by_kind, seen = _service(tmp_path, accounts=[YOUTUBE])
    assert "distribution" in by_kind  # a connected account puts posting in the plan
    replies = service.review_plan(plan_id, {})
    assert seen["pacing"] == []
    assert next(i for i in replies["measurements"] if i["channel"] == "distribution")["pacing"] is None

    views, views_id, campaigns, views_kinds, views_seen = _service(
        tmp_path / "views", goal_kind="views", accounts=[YOUTUBE], published=6,
        pacing={"action": "raise", "reason": "Behind: raising.", "measured_posts": 6, "steering": True},
    )
    for campaign in campaigns.values():
        campaign["status"] = "active"
    review = views.review_plan(views_id, {})
    assert views_seen["pacing"] == [views_kinds["distribution"]]
    assert _found(review, "distribution")["code"] == "behind_target"


def test_reviews_are_kept_and_the_plan_shows_the_latest(tmp_path):
    service, plan_id, *_ = _service(tmp_path)
    first = service.review_plan(plan_id, {})
    second = service.review_plan(plan_id, {})
    assert first["id"] != second["id"]
    assert service.get_plan(plan_id)["review"]["id"] == second["id"]
    assert service.store.get_review(first["id"], "w")["id"] == first["id"]


def test_no_model_is_asked_when_no_finding_has_a_choice(tmp_path):
    def ask(**kwargs):
        raise AssertionError("a call that could only say nothing was made")

    service, plan_id, campaigns, by_kind, seen = _service(tmp_path, ask=ask)
    del campaigns[by_kind["email"]]  # the only channel, and it permits nothing
    review = service.review_plan(plan_id, {})
    assert seen["asked"] == []
    assert review["remedies"] == []
    assert any("no model was asked" in note for note in review["notes"])


def test_a_model_writing_under_a_thin_policy_is_named(tmp_path):
    def ask(**kwargs):
        return SimpleNamespace(text=json.dumps({"summary": "s", "remedies": []}),
                               provider_id="groq", model_id="m", policy="pseudonymous")

    service, plan_id, *_ = _service(tmp_path, ask=ask)
    review = service.review_plan(plan_id, {})
    assert review["source"] == "model"
    assert "pseudonymous" in review["notes"][0]


def test_a_review_request_names_what_it_does_not_understand(tmp_path):
    from offsetx_apollo_builder.gtm.strategy import RequestInvalid

    service, plan_id, *_ = _service(tmp_path)
    with pytest.raises(RequestInvalid) as refused:
        service.review_plan(plan_id, {"use_modle": False})
    assert refused.value.field == "use_modle"
    with pytest.raises(RequestInvalid):
        service.review_plan(plan_id, {"use_model": "no"})


def test_the_review_uses_what_the_owner_forbids_today(tmp_path):
    """A claim forbidden after the plan was written is still dropped from a remedy."""
    def ask(**kwargs):
        return SimpleNamespace(text=json.dumps({"summary": "s", "remedies": [
            {"channel": "email", "action": "resume_campaign", "why": "Instant results."}]}),
            provider_id="p", model_id="m", policy="standard")

    service, plan_id, campaigns, by_kind, _ = _service(tmp_path, ask=ask)
    campaigns[by_kind["email"]]["status"] = "paused"
    product_id = service.store.get_plan(plan_id, "w")["product_id"]
    service.store.update_product(product_id, "w", {"forbidden_claims": ["instant results"]})
    review = service.review_plan(plan_id, {})
    assert "Instant results" not in json.dumps(review["remedies"])
    assert any("changed since this plan" in note for note in review["notes"])
