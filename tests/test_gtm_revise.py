"""S-12.02.04 — a review becomes the next version of the plan.

"Learns from where it went wrong", in terms a test can check: the next version
assumes the reply rate that was *measured*, keeps the deadline the owner set,
aims for what is left of the goal, and is written with the review in view. The
campaigns it drives are the same ones — a revision changes a line, it does not
start a new one.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.gtm.service import GtmService, Readers
from offsetx_apollo_builder.gtm.store import GtmStore, PlanStateError

PRODUCT = {
    "name": "Zephyrledger",
    "one_liner": "Zephyrledger reconciles freight invoices overnight for you.",
    "audience": "Quartermaster finance leads at mid-size freight forwarders.",
    "problem": "Carriers overbill by marmalade margins nobody audits.",
    "offer": "a walkthrough on your own invoices",
    "forbidden_claims": ["guaranteed"],
}


class World:
    """The CRM, delivery health and the pacer, as dictionaries a test can move."""

    def __init__(self) -> None:
        self.campaigns: dict[str, dict] = {}
        self.goals: dict[str, list[dict]] = {}
        self.summary = {"contacts": 0, "messages_by_stage": {}, "contact_status": {}, "draft_status": {}}
        self.asked: list[dict] = []
        self.replies: list[str] = []
        self._ids = count(1)

    def create_campaign(self, **values):
        campaign_id = f"c{next(self._ids)}"
        self.campaigns[campaign_id] = {"id": campaign_id, "status": "active", **values}
        return campaign_id

    def update_campaign(self, campaign_id, changes):
        self.campaigns[campaign_id].update(changes)

    def set_goal(self, *, campaign_id, metric, target, deadline):
        self.goals.setdefault(campaign_id, []).append(
            {"metric": metric, "target": target, "deadline": deadline})

    def sent(self, contacted, replied, contacts=500):
        self.summary = {"contacts": contacts, "messages_by_stage": {"initial": contacted},
                        "contact_status": {"replied": replied}, "draft_status": {}}

    def ask(self, **kwargs):
        self.asked.append(kwargs)
        return SimpleNamespace(text=self.replies.pop(0), provider_id="p", model_id="m",
                               policy="standard")

    def service(self, store, *, accounts=(), model=False):
        return GtmService(
            store, workspace_id="w", identities=lambda: [], accounts=lambda: list(accounts),
            apollo_ready=lambda: False, ask=self.ask if model else None,
            create_campaign=self.create_campaign, update_campaign=self.update_campaign,
            set_goal=self.set_goal, goals_of=lambda campaign_id: self.goals.get(campaign_id, []),
            lock=lambda key: nullcontext(),
            readers=Readers(
                campaign=lambda campaign_id: self.campaigns[campaign_id],
                email_summary=lambda campaign_id: self.summary,
                health=lambda campaign_id: {"breached": [], "paused_reason": ""},
                weak_templates=lambda: 0,
                published=lambda campaign_id: 0,
                pacing=lambda campaign_id: {"action": "hold", "reason": "r", "measured_posts": 0,
                                            "steering": False},
            ),
        )


YOUTUBE = {"platform": "youtube", "daily_cap": 1, "enabled": 1}


def applied_line(tmp_path, *, goal_kind="replies", target=20, horizon=30, accounts=(), model=False):
    world = World()
    store = GtmStore(tmp_path / "gtm.db")
    service = world.service(store, accounts=accounts, model=model)
    product = store.create_product("w", PRODUCT)
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": goal_kind,
                               "goal_target": target, "horizon_days": horizon, "use_model": False})
    service.apply_plan(plan["id"])
    for campaign in world.campaigns.values():
        campaign["status"] = "active"  # the owner resumed them
    return world, service, service.get_plan(plan["id"])


def day(plan, days):
    return datetime.fromisoformat(plan["created_at"]) + timedelta(days=days)


def reviewed(world, service, plan, *, contacted, replied, days=15):
    world.sent(contacted, replied)
    return service.review_plan(plan["id"], {"use_model": False}, now=day(plan, days))


# ── criterion 4: no revision without a review ───────────────────────────────


def test_a_plan_with_no_review_is_not_revised(tmp_path):
    world, service, plan = applied_line(tmp_path)
    with pytest.raises(PlanStateError) as refused:
        service.revise_plan(plan["id"], {}, now=day(plan, 15))
    assert "Review" in str(refused.value)


def test_only_an_applied_plan_is_revised(tmp_path):
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=100, replied=2)
    draft = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 15))
    with pytest.raises(PlanStateError):
        service.revise_plan(draft["id"], {}, now=day(plan, 15))


# ── criterion 1: the measured rate replaces the assumed one ─────────────────


def test_a_measured_rate_replaces_the_assumption(tmp_path):
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=100, replied=2)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 15))
    assert revision["status"] == "draft"
    assert revision["version"] == 2
    assert revision["parent_id"] == plan["id"]
    assert revision["root_id"] == plan["root_id"]
    assert revision["request"]["assumed_reply_rate"] == pytest.approx(0.02)
    assert any("2.0%" in note and "3.4%" in note for note in revision["notes"])


# ── criterion 2: too little data carries the assumption forward ─────────────


def test_too_few_contacted_carries_the_assumption_forward(tmp_path):
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=12, replied=1)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 15))
    assert revision["request"]["assumed_reply_rate"] == pytest.approx(0.034)
    assert any("12" in note and "20" in note for note in revision["notes"])


def test_a_measured_zero_is_floored_and_says_so(tmp_path):
    """No replies from forty is a real measurement. A plan cannot assume 0%, so
    it assumes the lowest rate a request may carry, and the note says both."""
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=40, replied=0)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 15))
    assert revision["request"]["assumed_reply_rate"] == pytest.approx(0.001)
    assert any("0.0%" in note and "0.1%" in note for note in revision["notes"])


# ── the deadline the owner set stays set ────────────────────────────────────


def test_the_deadline_stays_and_the_target_is_what_is_left(tmp_path):
    world, service, plan = applied_line(tmp_path, target=20, horizon=30)
    reviewed(world, service, plan, contacted=100, replied=8)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 12))
    assert revision["request"]["horizon_days"] == 18
    assert revision["request"]["goal_target"] == 12
    assert any("remaining 12" in note for note in revision["notes"])


@pytest.mark.parametrize(("days", "replied", "why"), [
    (30, 3, "ended"),        # the window has closed
    (26, 3, "4 days"),       # too little of it left to plan in
    (12, 25, "met"),         # the goal is already reached
])
def test_a_closed_window_starts_a_new_one(tmp_path, days, replied, why):
    world, service, plan = applied_line(tmp_path, target=20, horizon=30)
    reviewed(world, service, plan, contacted=200, replied=replied, days=days)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, days))
    assert revision["request"]["horizon_days"] == 30
    assert revision["request"]["goal_target"] == 20
    assert any(why in note and "new 30-day window" in note for note in revision["notes"])


# ── criterion 3: applying it updates the same campaigns ─────────────────────


def model_revision(*channels):
    specs = {
        "email": {"kind": "email", "role": "primary", "angle": "Lead with the overbilling number.",
                  "hypothesis": "A number they can check earns more replies.", "daily_volume": 20},
        "distribution": {"kind": "distribution", "role": "support", "angle": "a", "hypothesis": "h",
                         "daily_volume": 1, "platforms": ["youtube"]},
    }
    return json.dumps({"summary": "Revised.", "channels": [specs[kind] for kind in channels],
                       "audience": {"description": "Finance leads.", "source": "existing_contacts"}})


def test_applying_a_revision_updates_the_same_campaigns(tmp_path):
    world, service, plan = applied_line(tmp_path, accounts=[YOUTUBE], model=True)
    first = dict(world.campaigns)
    assert {item["kind"] for item in first.values()} == {"email", "distribution", "image"}
    reviewed(world, service, plan, contacted=100, replied=1)
    world.replies.append(model_revision("email"))  # drops posting and pictures
    revision = service.revise_plan(plan["id"], {"use_model": True}, now=day(plan, 12))
    result = service.apply_plan(revision["id"])

    assert set(world.campaigns) == set(first)  # nothing new was created
    assert {item["action"] for item in result["campaigns"]} == {"updated"}
    dropped = [c for c in world.campaigns.values() if c["kind"] in ("distribution", "image")]
    assert all(campaign["status"] == "paused" for campaign in dropped)
    assert service.get_plan(plan["id"])["status"] == "superseded"
    assert service.get_plan(revision["id"])["status"] == "applied"


def test_the_review_of_a_revision_counts_only_its_own_sends(tmp_path):
    """Replies to the old angle are not evidence about the new one. Without this,
    the second version's rate is mostly the first version's."""
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=100, replied=5)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 12))
    service.apply_plan(revision["id"])
    for campaign in world.campaigns.values():
        campaign["status"] = "active"

    world.sent(150, 6)
    review = service.review_plan(revision["id"], {"use_model": False}, now=day(plan, 20))
    email = next(item for item in review["measurements"] if item["channel"] == "email")
    assert (email["contacted"], email["replied"]) == (50, 1)
    assert (email["contacted_before"], email["replied_before"]) == (100, 5)


def test_a_revision_keeps_the_views_deadline(tmp_path):
    world, service, plan = applied_line(tmp_path, goal_kind="views", target=5000, accounts=[YOUTUBE])
    distribution = next(cid for cid, c in world.campaigns.items() if c["kind"] == "distribution")
    assert len(world.goals[distribution]) == 1
    reviewed(world, service, plan, contacted=0, replied=0)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 10))
    service.apply_plan(revision["id"])
    # Same target, same deadline: the goal the pacer steers by is untouched.
    assert len(world.goals[distribution]) == 1


# ── the review is in view when the next version is written ──────────────────


def test_a_revision_is_written_with_the_review_in_view(tmp_path):
    world, service, plan = applied_line(tmp_path, model=True)
    world.replies.append(json.dumps({"summary": "s", "remedies": [
        {"channel": "email", "action": "test_new_angle", "why": "Not landing.",
         "proposal": "Lead with the overbilling number."}]}))
    world.sent(400, 2)
    service.review_plan(plan["id"], {"use_model": True}, now=day(plan, 12))
    world.replies.append(model_revision("email"))
    service.revise_plan(plan["id"], {"use_model": True}, now=day(plan, 12))

    sent = world.asked[-1]
    assert sent["task_type"] == "gtm_plan"
    assert "revises version 1" in sent["instructions"]
    assert "behind_target" in sent["instructions"]
    assert "Lead with the overbilling number." in sent["campaign_notes"]
    # The owner's words travel where their policy governs them, never in instructions.
    for value in PRODUCT.values():
        if isinstance(value, str):
            assert value not in sent["instructions"]
            assert value not in sent["system_prompt"]


def test_the_rules_revision_does_what_rules_can(tmp_path):
    world, service, plan = applied_line(tmp_path, model=True)
    world.replies.append(json.dumps({"summary": "s", "remedies": [
        {"channel": "email", "action": "test_new_angle", "why": "Not landing.",
         "proposal": "Lead with the overbilling number."},
        {"channel": "email", "action": "narrow_audience", "why": "Too broad."}]}))
    world.sent(400, 2)
    service.review_plan(plan["id"], {"use_model": True}, now=day(plan, 12))

    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 12))
    email = next(item for item in revision["plan"]["channels"] if item["kind"] == "email")
    # The review's proposal is adopted: it was already checked for forbidden claims.
    assert email["angle"] == "Lead with the overbilling number."
    # A narrower audience with no words for it is the owner's to write.
    assert any("narrower audience" in note.lower() for note in revision["notes"])
    assert revision["source"] == "rules"


def test_the_rules_revision_halves_volume_when_delivery_is_unhealthy(tmp_path):
    """Delivery first, in the revision as in the review. With no model, the
    review's first remedy is an owner action — clean the list — and the plan
    itself must still stop sending at the rate that caused the bounces."""
    world, service, plan = applied_line(tmp_path)
    before = next(item for item in plan["plan"]["channels"] if item["kind"] == "email")["daily_volume"]
    world.sent(300, 3)
    service.readers = Readers(**{**service.readers.__dict__, "health": lambda campaign_id: {
        "breached": ["hard_bounce_rate"], "paused_reason": "", "accepted": 300,
        "hard_bounce_rate": 0.08, "complaint_rate": 0.0}})
    review = service.review_plan(plan["id"], {"use_model": False}, now=day(plan, 12))
    assert review["remedies"][0]["action"] == "fix_list_quality"

    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 12))
    email = next(item for item in revision["plan"]["channels"] if item["kind"] == "email")
    assert email["daily_volume"] == max(1, before // 2)
    assert any("delivery" in note for note in revision["notes"])


def test_a_revised_angle_reaches_the_posts_and_the_emails(tmp_path):
    """A copy remedy that changes nothing that is sent is not a remedy. The
    applied version's angle is what posts are written from and what a template's
    `{product_angle}` says; a draft changes nothing until it is applied."""
    from offsetx_apollo_builder.api.gtm import resolve_angle

    world, service, plan = applied_line(tmp_path, accounts=[YOUTUBE], model=True)
    kinds = {c["kind"]: cid for cid, c in world.campaigns.items()}
    first = {c["kind"]: c["angle"] for c in plan["plan"]["channels"]}
    assert resolve_angle(service.store, "w", kinds["distribution"], "") == first["distribution"]
    assert service.store.product_for_campaign(kinds["email"], "w")["angle"] == first["email"]

    reviewed(world, service, plan, contacted=100, replied=1)
    world.replies.append(model_revision("email", "distribution"))
    revision = service.revise_plan(plan["id"], {"use_model": True}, now=day(plan, 12))
    assert resolve_angle(service.store, "w", kinds["distribution"], "") == first["distribution"]

    service.apply_plan(revision["id"])
    assert resolve_angle(service.store, "w", kinds["distribution"], "") == "a"
    assert service.store.product_for_campaign(kinds["email"], "w")["angle"] == \
        "Lead with the overbilling number."
    # The owner's own angle still wins over the plan's.
    assert resolve_angle(service.store, "w", kinds["distribution"], "mine") == "mine"


def test_the_rules_revision_leaves_the_posting_rate_to_the_posting_screen(tmp_path):
    """Posting runs at the rate set on Posting; a plan's posts-a-day is read by
    nothing that posts. Raising it in the plan would be a change that changes
    nothing, so the remedy is named as the screen action it is."""
    world, service, plan = applied_line(tmp_path, goal_kind="views", accounts=[YOUTUBE])
    reviewed(world, service, plan, contacted=0, replied=0, days=5)
    review = service.store.latest_review(plan["id"], "w")
    service.store.create_review(
        plan["id"], "w", measurements=review["measurements"], findings=review["findings"],
        remedies=[{"channel": "distribution", "action": "raise_post_rate", "why": "Behind.",
                   "proposal": ""}],
        summary="", notes=[], source="rules")
    before = next(c for c in plan["plan"]["channels"] if c["kind"] == "distribution")["daily_volume"]
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 5))
    after = next(c for c in revision["plan"]["channels"] if c["kind"] == "distribution")["daily_volume"]
    assert after == before
    assert any("Posting" in note for note in revision["notes"])


# ── a line survives what the owner does to its campaigns ────────────────────


def test_a_deleted_campaign_is_made_again_when_the_revision_is_applied(tmp_path):
    """Restoring a backup replaces the CRM and not the plans, so a link can point
    at nothing. The review says revising creates it again; it must."""
    world, service, plan = applied_line(tmp_path)
    old = next(cid for cid, c in world.campaigns.items() if c["kind"] == "email")
    del world.campaigns[old]
    review = service.review_plan(plan["id"], {"use_model": False}, now=day(plan, 5))
    assert next(f for f in review["findings"] if f["channel"] == "email")["code"] == "no_campaign"

    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 5))
    result = service.apply_plan(revision["id"])
    email = next(item for item in result["campaigns"] if item["kind"] == "email")
    assert email["action"] == "created" and email["campaign_id"] != old
    assert world.campaigns[email["campaign_id"]]["status"] == "paused"
    assert service.store.line_links(plan["root_id"], "w")["email"] == email["campaign_id"]
    assert any("no longer exists" in note for note in result["notes"])


def test_apply_leaves_an_archived_campaign_archived(tmp_path):
    """Archiving is the owner's decision. Apply pausing it would quietly bring
    back a campaign they put away."""
    world, service, plan = applied_line(tmp_path, accounts=[YOUTUBE], model=True)
    kinds = {c["kind"]: cid for cid, c in world.campaigns.items()}
    world.campaigns[kinds["image"]]["status"] = "archived"
    world.campaigns[kinds["email"]]["status"] = "archived"
    reviewed(world, service, plan, contacted=0, replied=0, days=5)
    world.replies.append(model_revision("email", "distribution"))  # drops pictures
    revision = service.revise_plan(plan["id"], {"use_model": True}, now=day(plan, 5))
    result = service.apply_plan(revision["id"])
    assert world.campaigns[kinds["image"]]["status"] == "archived"
    assert world.campaigns[kinds["email"]]["status"] == "archived"
    assert any("archived" in note for note in result["notes"])


def test_an_older_draft_cannot_replace_a_newer_applied_version(tmp_path):
    world, service, plan = applied_line(tmp_path)
    reviewed(world, service, plan, contacted=100, replied=2, days=5)
    second = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 5))
    third = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 5))
    service.apply_plan(third["id"])
    with pytest.raises(PlanStateError) as refused:
        service.apply_plan(second["id"])
    assert "version 3" in str(refused.value).lower()
    assert service.get_plan(third["id"])["status"] == "applied"


def test_replies_between_a_review_and_the_next_apply_count_for_the_next_version(tmp_path):
    """The next version aims for what was left at the review, so it counts from
    the review — not from when it happened to be applied, which lost the replies
    in between from both versions."""
    world, service, plan = applied_line(tmp_path, target=20)
    reviewed(world, service, plan, contacted=100, replied=5, days=10)
    revision = service.revise_plan(plan["id"], {"use_model": False}, now=day(plan, 10))
    assert revision["request"]["goal_target"] == 15
    world.sent(120, 8)  # three more replies arrive before the revision is applied
    service.apply_plan(revision["id"])
    for campaign in world.campaigns.values():
        campaign["status"] = "active"
    world.sent(200, 20)
    review = service.review_plan(revision["id"], {"use_model": False}, now=day(plan, 20))
    email = next(item for item in review["measurements"] if item["channel"] == "email")
    assert email["replied"] == 15


def test_a_first_version_counts_every_send_even_after_a_resumed_apply(tmp_path, monkeypatch):
    """A first version's campaigns are new, so it has nothing to subtract — even
    when its apply failed half way, sends happened, and it was applied again."""
    world = World()
    store = GtmStore(tmp_path / "gtm.db")
    service = world.service(store, accounts=[YOUTUBE])  # three channels, so a second link
    product = store.create_product("w", PRODUCT)
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": "replies",
                               "goal_target": 20, "use_model": False})
    real = store.link_campaign
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("database is locked")
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "link_campaign", flaky)
    world.sent(40, 2)
    with pytest.raises(RuntimeError):
        service.apply_plan(plan["id"])
    service.apply_plan(plan["id"])
    assert service.get_plan(plan["id"])["baseline"] == {}


# ── over HTTP ───────────────────────────────────────────────────────────────


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


def test_revise_over_http(client):
    product = client.post("/api/v1/gtm/products", json=PRODUCT).json()
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product["id"], "goal_kind": "replies", "goal_target": 20, "use_model": False,
    }).json()
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/revise", json={}).status_code == 409
    client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    unreviewed = client.post(f"/api/v1/gtm/plans/{plan['id']}/revise", json={})
    assert unreviewed.status_code == 409
    assert unreviewed.json()["detail"]["error"] == "wrong_state"

    client.post(f"/api/v1/gtm/plans/{plan['id']}/review", json={"use_model": False})
    revised = client.post(f"/api/v1/gtm/plans/{plan['id']}/revise", json={"use_model": False})
    assert revised.status_code == 201, revised.text
    body = revised.json()
    assert (body["version"], body["parent_id"], body["status"]) == (2, plan["id"], "draft")
    assert client.post("/api/v1/gtm/plans/no-such/revise", json={}).status_code == 404
    bad = client.post(f"/api/v1/gtm/plans/{plan['id']}/revise", json={"use_modle": False})
    assert bad.status_code == 422


def test_an_older_database_gains_the_baseline_column(tmp_path):
    """`gtm_plans` shipped without `baseline_json`, and `CREATE TABLE IF NOT
    EXISTS` never adds a column. A database made then must still open, keep its
    plans, and read their baseline as empty."""
    import sqlite3

    path = tmp_path / "gtm.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE gtm_plans (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, "
        "product_id TEXT NOT NULL, root_id TEXT NOT NULL, parent_id TEXT NOT NULL DEFAULT '', "
        "version INTEGER NOT NULL, status TEXT NOT NULL, request_json TEXT NOT NULL, "
        "product_snapshot_json TEXT NOT NULL, product_version INTEGER NOT NULL, "
        "envelope_json TEXT NOT NULL, plan_json TEXT NOT NULL, feasibility_json TEXT NOT NULL, "
        "notes_json TEXT NOT NULL, source TEXT NOT NULL, provider_id TEXT NOT NULL DEFAULT '', "
        "model_id TEXT NOT NULL DEFAULT '', policy TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, applied_at TEXT);"
        "INSERT INTO gtm_plans VALUES ('p1','w','prod','p1','',1,'applied','{}','{}',1,'{}',"
        "'{\"channels\": []}','{}','[]','rules','','','','2026-09-22T00:00:00+00:00',NULL);"
    )
    old.commit()
    old.close()

    store = GtmStore(path)
    assert store.get_plan("p1", "w")["baseline"] == {}
    store.set_baseline("p1", "w", {"email": {"contacted": 3, "replied": 1}})
    assert store.get_plan("p1", "w")["baseline"]["email"]["contacted"] == 3
    store.close()
