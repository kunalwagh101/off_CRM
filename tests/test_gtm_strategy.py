"""S-12.02.01 — a goal becomes a checked plan that fits what is connected.

Most of these tests are about the checking, not the asking, for the reason
`video/director.py` gives: the model's reply is untrusted input, and the value
of this module is everything that stands between that reply and a campaign.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.distribution.platforms import PLATFORMS
from offsetx_apollo_builder.gtm.strategy import (
    ASSUMED_REPLY_RATE,
    COLD_EMAILS_PER_IDENTITY_PER_DAY,
    ModelUnavailable,
    PlanRefused,
    RequestInvalid,
    baseline_plan,
    build_prompt,
    envelope_from,
    feasibility,
    parse_plan,
    request_fields,
    validate_request,
)

IMPLEMENTED = ("distribution", "email", "image")

#: Distinctive strings, so "no product text in the system prompt" is a search
#: that cannot pass by accident.
SENTINELS = {
    "name": "Zephyrledger",
    "one_liner": "Zephyrledger reconciles freight invoices overnight for you.",
    "audience": "Quartermaster finance leads at mid-size freight forwarders.",
    "problem": "Carriers overbill by marmalade margins nobody audits.",
    "offer": "a walkthrough on your own invoices",
}


def product(**overrides):
    values = {
        "id": "prod-1",
        "workspace_id": "local",
        **SENTINELS,
        "outcome": "Overbilling is caught before payment.",
        "proof": ["Recovered 3.1% of freight spend at a 3PL"],
        "differentiators": ["Reads PDF invoices without a template"],
        "forbidden_claims": ["guaranteed", "100% accuracy"],
        "voice": "Plain and specific.",
        "website": "https://example.com",
        "version": 3,
        "created_at": "2026-09-22T00:00:00+00:00",
        "updated_at": "2026-09-22T00:00:00+00:00",
    }
    values.update(overrides)
    return values


def identity(name, *, stream="targeted_outreach", status="active", checks="pass"):
    return {
        "name": name,
        "stream": stream,
        "status": status,
        "provider_type": "ses",
        "spf_status": "pass",
        "dkim_status": checks,
        "dmarc_status": "pass",
        "alignment_status": "pass",
    }


def connected(**overrides):
    values = {
        "identities": [
            identity("Primary"),
            identity("Second", checks="fail"),
            identity("Newsletter", stream="permission_marketing"),
            identity("Old", status="paused"),
        ],
        "accounts": [
            {"platform": "youtube", "daily_cap": 0},
            {"platform": "instagram", "daily_cap": 2},
        ],
        "apollo_ready": True,
        "per_identity_cap": COLD_EMAILS_PER_IDENTITY_PER_DAY,
    }
    values.update(overrides)
    return envelope_from(**values)


def request(**overrides):
    values = {"product_id": "prod-1", "goal_kind": "replies", "goal_target": 20}
    values.update(overrides)
    return validate_request(values, implemented=IMPLEMENTED)


def reply(**overrides):
    body = {
        "summary": "Email finance leads directly; support with short videos.",
        "audience": {
            "description": "Finance leads at freight forwarders with 50-500 staff.",
            "source": "apollo_search",
            "titles": ["Head of Finance", "Controller"],
            "industries": ["logistics"],
            "company_sizes": ["51-200", "201-1000"],
            "regions": ["Germany"],
        },
        "channels": [
            {
                "kind": "email",
                "role": "primary",
                "angle": "Your carrier invoices are wrong more often than you think.",
                "hypothesis": "Controllers reply when shown their own overbilling rate.",
                "daily_volume": 40,
                "send_window": ["08:30", "16:00"],
                "weekdays": "weekdays",
                "timezone": "Europe/Berlin",
            },
            {
                "kind": "distribution",
                "role": "support",
                "angle": "One overbilled invoice, explained in 20 seconds.",
                "hypothesis": "Short proof videos warm the same accounts.",
                "daily_volume": 1,
                "platforms": ["youtube"],
            },
            {
                "kind": "image",
                "role": "support",
                "angle": "Before and after an audit.",
                "hypothesis": "A before-and-after picture carries the proof.",
                "recipe_family": "demo",
            },
        ],
    }
    body.update(overrides)
    return json.dumps(body)


def parse(text, **overrides):
    kwargs = {"request": request(), "envelope": connected(), "product": product()}
    kwargs.update(overrides)
    return parse_plan(text, **kwargs)


def channel(plan, kind):
    return next(item for item in plan.channels if item["kind"] == kind)


# ── the envelope: capacity from what is actually connected ──────────────────


def test_envelope_counts_only_what_is_connected():
    envelope = connected()
    # Two active targeted-outreach identities; the newsletter and the paused
    # one are not outbound capacity.
    assert envelope.email_identities == 2
    assert envelope.email_daily_capacity == 2 * COLD_EMAILS_PER_IDENTITY_PER_DAY
    assert envelope.email_unverified == ("Second",)
    youtube = PLATFORMS["youtube"].daily_posts_per_account or 1
    instagram = min(2, PLATFORMS["instagram"].daily_posts_per_account or 2)
    assert envelope.post_daily_capacity == min(youtube, 1) + instagram
    assert envelope.platforms == ("instagram", "youtube")
    assert any("Second" in blocker for blocker in envelope.blockers)


def test_no_identity_assumes_one_mailbox_and_says_so():
    envelope = connected(identities=[], accounts=[], apollo_ready=False)
    assert envelope.email_identities == 0
    assert envelope.email_daily_capacity == COLD_EMAILS_PER_IDENTITY_PER_DAY
    assert envelope.post_daily_capacity == 0
    joined = " ".join(envelope.blockers)
    assert "one mailbox" in joined
    assert "account" in joined


# ── criterion 1: a required choice outside the vocabulary refuses ────────────


def test_unknown_kind_is_refused_by_name():
    text = reply(channels=[{"kind": "telepathy", "role": "primary", "angle": "x", "hypothesis": "y"}])
    with pytest.raises(PlanRefused) as refused:
        parse(text)
    message = str(refused.value)
    assert "telepathy" in message
    for kind in ("email", "distribution", "image"):
        assert kind in message


def test_unknown_source_is_refused_by_name():
    text = reply(audience={"description": "Anyone", "source": "linkedin_scrape"})
    with pytest.raises(PlanRefused) as refused:
        parse(text)
    assert "linkedin_scrape" in str(refused.value)
    assert "apollo_search" in str(refused.value)


def test_prose_is_refused_and_fences_are_read():
    with pytest.raises(PlanRefused):
        parse("I think you should send some emails.")
    with pytest.raises(PlanRefused):
        parse(json.dumps(["not", "an", "object"]))
    with pytest.raises(PlanRefused):
        parse(reply(channels=[]))
    fenced = f"Here is the plan:\n```json\n{reply()}\n```"
    assert channel(parse(fenced), "email")["daily_volume"] == 40


# ── criterion 2: volume is clamped to real capacity ─────────────────────────


def test_volume_is_clamped_to_the_envelope():
    text = reply(
        channels=[
            {"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h", "daily_volume": 5000},
            {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h",
             "daily_volume": 90, "platforms": ["instagram"]},
        ]
    )
    plan = parse(text)
    capacity = connected()
    assert channel(plan, "email")["daily_volume"] == capacity.email_daily_capacity
    assert channel(plan, "distribution")["daily_volume"] == capacity.post_daily_capacity
    joined = " ".join(plan.notes)
    assert "5000" in joined and str(capacity.email_daily_capacity) in joined
    assert "90" in joined


def test_a_missing_or_silly_volume_falls_back_to_capacity():
    text = reply(channels=[{"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h",
                            "daily_volume": "lots"}])
    plan = parse(text)
    assert channel(plan, "email")["daily_volume"] == connected().email_daily_capacity
    assert any("lots" in note for note in plan.notes)


# ── criterion 3: a forbidden claim never survives ───────────────────────────


def test_forbidden_claim_is_removed_and_named():
    text = reply(
        summary="Savings are GUARANTEED.",
        channels=[{"kind": "email", "role": "primary", "hypothesis": "h",
                   "angle": "We deliver 100% accuracy on every invoice."}],
    )
    plan = parse(text)
    assert plan.summary == ""
    assert channel(plan, "email")["angle"] == ""
    joined = " ".join(plan.notes)
    assert "guaranteed" in joined and "100% accuracy" in joined
    assert "GUARANTEED" not in json.dumps(plan.to_dict())
    assert "100% accuracy" not in json.dumps(plan.to_dict())


# ── criterion 4: email only on the targeted-outreach stream ─────────────────


def test_email_always_uses_targeted_outreach():
    text = reply(channels=[{"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h",
                            "stream": "permission_marketing"}])
    plan = parse(text)
    assert channel(plan, "email")["stream"] == "targeted_outreach"
    assert any("stream" in note for note in plan.notes)
    rules = baseline_plan(request=request(), envelope=connected(), product=product())
    assert channel(rules, "email")["stream"] == "targeted_outreach"


# ── the rest of parse_plan's table, in order ────────────────────────────────


def test_a_kind_the_owner_did_not_allow_is_dropped_and_image_needs_distribution():
    owner = request(channels=["email", "image"])
    plan = parse(reply(), request=owner)
    kinds = [item["kind"] for item in plan.channels]
    assert kinds == ["email"]
    joined = " ".join(plan.notes)
    assert "distribution" in joined and "image" in joined


def test_a_duplicate_kind_keeps_the_first():
    text = reply(channels=[
        {"kind": "email", "role": "primary", "angle": "first", "hypothesis": "h"},
        {"kind": "email", "role": "support", "angle": "second", "hypothesis": "h"},
    ])
    plan = parse(text)
    assert [item["angle"] for item in plan.channels] == ["first"]


def test_exactly_one_primary():
    none = parse(reply(channels=[
        {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h"},
        {"kind": "email", "role": "support", "angle": "a", "hypothesis": "h"},
    ]))
    # With no primary, the channel the goal is measured on becomes it.
    assert channel(none, "email")["role"] == "primary"
    assert channel(none, "distribution")["role"] == "support"

    two = parse(reply(channels=[
        {"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h"},
        {"kind": "distribution", "role": "primary", "angle": "a", "hypothesis": "h"},
    ]))
    assert [item["role"] for item in two.channels] == ["primary", "support"]
    assert any("primary" in note for note in two.notes)


def test_optional_preferences_outside_the_vocabulary_are_dropped_and_named():
    text = reply(
        audience={"description": "d", "source": "existing_contacts",
                  "company_sizes": ["51-200", "gigantic"],
                  "titles": [f"Title {index}" for index in range(12)]},
        channels=[
            {"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h", "mood": "bold"},
            {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h",
             "platforms": ["youtube", "myspace"]},
            {"kind": "image", "role": "support", "angle": "a", "hypothesis": "h",
             "recipe_family": "opera"},
        ],
        budget="all of it",
    )
    plan = parse(text)
    assert plan.audience["company_sizes"] == ["51-200"]
    assert len(plan.audience["titles"]) == 8
    assert channel(plan, "distribution")["platforms"] == ["youtube"]
    assert channel(plan, "image")["recipe_family"] == ""
    joined = " ".join(plan.notes)
    for named in ("gigantic", "myspace", "opera", "mood", "budget"):
        assert named in joined


def test_bad_window_and_timezone_fall_back_with_a_note():
    text = reply(channels=[{"kind": "email", "role": "primary", "angle": "a", "hypothesis": "h",
                            "send_window": ["18:00", "09:00"], "timezone": "Mars/Olympus"}])
    plan = parse(text)
    email = channel(plan, "email")
    assert email["send_window"] == ["09:00", "17:00"]
    assert email["timezone"] == ""
    joined = " ".join(plan.notes)
    assert "Mars/Olympus" in joined and "18:00" in joined


def test_apollo_source_without_apollo_is_kept_and_named():
    plan = parse(reply(), envelope=connected(apollo_ready=False))
    assert plan.audience["source"] == "apollo_search"
    assert any("Apollo" in note for note in plan.notes)


# ── criteria 5 and 6: the system prompt, and where the product travels ──────


def test_system_prompt_carries_no_product_text():
    prompt = build_prompt()
    for value in SENTINELS.values():
        assert value not in prompt
    for kind in IMPLEMENTED:
        assert kind in prompt
    for family in ("hook", "demo"):
        assert family in prompt


def test_product_travels_in_classified_fields():
    fields = request_fields(product(), request(), connected())
    assert fields["positioning_line"] == SENTINELS["one_liner"]
    for key in ("audience", "problem", "offer", "name"):
        assert SENTINELS[key] in fields["campaign_notes"]
    assert "100% accuracy" in fields["campaign_notes"]  # the model is told what never to say
    # Instructions are code-authored numbers and names: nothing from the product.
    for value in SENTINELS.values():
        assert value not in fields["instructions"]
    assert "20 replies" in fields["instructions"]


# ── criterion 8: feasibility is arithmetic the owner can check ──────────────


def test_feasibility_is_arithmetic_the_owner_can_check():
    plan = parse(reply())
    result = feasibility(plan, request(horizon_days=28, contact_budget=400))
    # 40 a day (under the 60 the envelope carries) × 20 weekdays in 28 days =
    # 800, capped at the 400-contact budget because the source is Apollo.
    assert result["send_days"] == 20
    assert result["reachable"] == 400
    assert result["expected"] == round(400 * ASSUMED_REPLY_RATE, 1)
    assert result["feasible"] is False
    assert "13.6" in result["explanation"]
    assert "5.0%" in result["explanation"]  # 20 ÷ 400, the rate the goal needs


def test_views_goal_has_no_estimate_before_data():
    views = request(goal_kind="views", goal_target=100000, channels=["distribution", "image"])
    plan = baseline_plan(request=views, envelope=connected(), product=product())
    result = feasibility(plan, views)
    assert result["feasible"] is None
    assert "5 posts" in result["explanation"]


# ── the baseline: what the owner gets with no model ─────────────────────────


def test_baseline_plan_obeys_the_same_rules():
    rules = baseline_plan(request=request(), envelope=connected(), product=product())
    assert rules.source == "rules"
    assert [item["kind"] for item in rules.channels][0] == "email"
    assert channel(rules, "email")["role"] == "primary"
    assert channel(rules, "email")["angle"] == SENTINELS["one_liner"]
    assert channel(rules, "email")["daily_volume"] == connected().email_daily_capacity
    assert rules.audience["source"] == "existing_contacts"  # budget 0: nothing to buy

    # Product text the rules plan reuses is checked like a model's: an audience
    # that happens to contain a forbidden claim is removed, and named.
    risky = product(audience="Teams who want guaranteed savings on every freight invoice.")
    rules = baseline_plan(request=request(), envelope=connected(), product=risky)
    assert "guaranteed" not in json.dumps(rules.to_dict()).lower()
    assert any("guaranteed" in note for note in rules.notes)

    # Nowhere to post: a replies plan leaves distribution and image out quietly
    # rather than adding image and then dropping it with a note.
    lonely = baseline_plan(request=request(), envelope=connected(accounts=[]), product=product())
    assert [item["kind"] for item in lonely.channels] == ["email"]
    assert not any("image" in note for note in lonely.notes)


# ── criterion 9: bad requests are refused with a sentence ───────────────────


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"goal_kind": "meetings"}, "goal_kind"),
        ({"goal_target": 0}, "goal_target"),
        ({"goal_target": 100001}, "goal_target"),
        ({"goal_target": 2.5}, "goal_target"),
        ({"goal_target": True}, "goal_target"),
        ({"horizon_days": 3}, "horizon_days"),
        ({"horizon_days": 400}, "horizon_days"),
        ({"contact_budget": -1}, "contact_budget"),
        ({"channels": []}, "channels"),
        ({"channels": ["email", "fax"]}, "channels"),
        ({"channels": ["distribution"]}, "channels"),  # a replies goal needs email
        ({"assumed_reply_rate": 0.9}, "assumed_reply_rate"),
        ({"per_identity_daily_cap": 0}, "per_identity_daily_cap"),
        ({"notes": "ping me at owner@example.com"}, "notes"),
        ({"use_model": "yes"}, "use_model"),
        ({"surprise": 1}, "surprise"),
        ({"product_id": ""}, "product_id"),
    ],
)
def test_bad_plan_requests_are_refused(overrides, field):
    with pytest.raises(RequestInvalid) as refused:
        request(**overrides)
    assert refused.value.field == field
    assert str(refused.value).endswith(".")


# ── through the service and over HTTP ───────────────────────────────────────


def _settings(tmp_path):
    from offsetx_apollo_builder.api.config import AppSettings

    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )


PRODUCT_BODY = {
    **SENTINELS,
    "forbidden_claims": ["guaranteed", "100% accuracy"],
}


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app

    with TestClient(create_app(_settings(tmp_path))) as opened:
        yield opened


def _spy(client, monkeypatch, *, text, policy="standard"):
    seen: dict[str, list] = {"requests": [], "system_prompts": []}

    def call(request, settings, **kwargs):
        seen["requests"].append(request)
        seen["system_prompts"].append(kwargs.get("system_prompt", ""))
        return SimpleNamespace(text=text, provider_id="mistral", model_id="m-large", policy=policy)

    monkeypatch.setattr(client.app.state.ai_broker, "call", call)
    return seen


def test_the_request_the_brain_sends_is_campaign_class_with_the_product_classified(client, monkeypatch):
    from offsetx_apollo_builder.ai.tiers import DataClass

    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    seen = _spy(client, monkeypatch, text=reply())
    drafted = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    })
    assert drafted.status_code == 201, drafted.text
    sent = seen["requests"][-1]
    assert sent.data_class is DataClass.CAMPAIGN
    assert sent.task_type == "gtm_plan"
    assert sent.positioning_line == SENTINELS["one_liner"]
    assert SENTINELS["problem"] in sent.campaign_notes
    for value in SENTINELS.values():
        assert value not in seen["system_prompts"][-1]
        assert value not in sent.instructions
    plan = drafted.json()
    assert plan["source"] == "model"
    assert plan["provider_id"] == "mistral"


def test_forbidden_claim_never_survives_into_a_stored_plan(client, monkeypatch):
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    _spy(client, monkeypatch, text=reply(summary="Results guaranteed in a week."))
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    }).json()
    stored = client.get(f"/api/v1/gtm/plans/{plan['id']}").json()
    assert "guaranteed" not in json.dumps(stored["plan"]).lower()
    assert any("guaranteed" in note for note in stored["notes"])


def test_no_permitted_model_returns_the_rules_plan(client):
    """The real broker, with nothing connected: the first thing anyone hits."""
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    drafted = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    })
    assert drafted.status_code == 201, drafted.text
    plan = drafted.json()
    assert plan["source"] == "rules"
    assert any("rules-based" in note for note in plan["notes"])


def test_a_minimal_policy_is_named_on_the_plan(client, monkeypatch):
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    _spy(client, monkeypatch, text=reply(), policy="minimal")
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    }).json()
    assert any("minimal" in note and "one-liner" in note for note in plan["notes"])


def test_a_refused_model_plan_falls_back_to_rules_and_says_why(client, monkeypatch):
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    _spy(client, monkeypatch, text="Sure! Send emails to everyone.")
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    }).json()
    assert plan["source"] == "rules"
    assert any("refused" in note for note in plan["notes"])


def test_the_plan_records_the_product_it_was_written_against(client, monkeypatch):
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    client.patch(f"/api/v1/gtm/products/{product_id}", json={"voice": "Warmer."})
    _spy(client, monkeypatch, text=reply())
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    }).json()
    assert plan["product_version"] == 2
    assert plan["product_snapshot"]["voice"] == "Warmer."
    assert plan["version"] == 1 and plan["status"] == "draft"

    client.patch(f"/api/v1/gtm/products/{product_id}", json={"voice": "Cooler."})
    stored = client.get(f"/api/v1/gtm/plans/{plan['id']}").json()
    # The copy is the one it was written against, and it knows it is stale.
    assert stored["product_snapshot"]["voice"] == "Warmer."
    assert stored["product_stale"] is True


def test_plans_list_discard_and_refuse_over_http(client, monkeypatch):
    product_id = client.post("/api/v1/gtm/products", json=PRODUCT_BODY).json()["id"]
    _spy(client, monkeypatch, text=reply())
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "replies", "goal_target": 20,
    }).json()

    listed = client.get(f"/api/v1/gtm/plans?product_id={product_id}").json()["items"]
    assert [item["id"] for item in listed] == [plan["id"]]

    discarded = client.post(f"/api/v1/gtm/plans/{plan['id']}/discard")
    assert discarded.json()["status"] == "discarded"
    again = client.post(f"/api/v1/gtm/plans/{plan['id']}/discard")
    assert again.status_code == 409
    assert again.json()["detail"]["error"] == "wrong_state"

    unknown = client.post("/api/v1/gtm/plans", json={
        "product_id": "no-such", "goal_kind": "replies", "goal_target": 20,
    })
    assert unknown.status_code == 404
    bad = client.post("/api/v1/gtm/plans", json={
        "product_id": product_id, "goal_kind": "meetings", "goal_target": 20,
    })
    assert bad.status_code == 422
    assert bad.json()["detail"]["field"] == "goal_kind"
    assert client.get("/api/v1/gtm/plans/no-such").status_code == 404


def test_the_envelope_endpoint_shows_capacity_and_vocabulary(client):
    body = client.get("/api/v1/gtm/envelope").json()
    assert body["envelope"]["email_daily_capacity"] == COLD_EMAILS_PER_IDENTITY_PER_DAY
    assert set(IMPLEMENTED) <= set(body["vocabulary"]["kinds"])
    assert body["defaults"]["assumed_reply_rate"] == ASSUMED_REPLY_RATE


def test_the_ask_contract_raises_model_unavailable_not_a_provider_error():
    """gtm must not know the broker's exception types: it imports nothing from ai/."""
    assert issubclass(ModelUnavailable, RuntimeError)


def test_feasibility_says_when_the_contact_count_is_the_real_ceiling():
    rules = baseline_plan(request=request(), envelope=connected(), product=product())
    assert rules.audience["source"] == "existing_contacts"
    assert "real ceiling" in feasibility(rules, request())["explanation"]
    capped = feasibility(parse(reply()), request(contact_budget=400))
    assert "real ceiling" not in capped["explanation"]
