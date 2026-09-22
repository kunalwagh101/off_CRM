"""S-12.02.02 — an approved plan becomes paused campaigns, and nothing sends by itself.

Driven through the real app and the real CRM store, because "paused" only means
something if the campaign row the engine reads really says so. The one failure
path a unit test drives directly is the half-finished apply, since the two
stores involved cannot share a transaction and resuming without duplicating is
the property that has to hold.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.gtm.service import GtmService
from offsetx_apollo_builder.gtm.store import GtmStore, PlanStateError

#: The screens a next step may point at. Every one exists in `frontend/src/App.tsx`.
KNOWN_PAGES = {"discovery", "contacts", "deliverability", "drafts", "campaigns", "posting", "imagereview"}

PRODUCT = {
    "name": "Ledgerline",
    "one_liner": "Reconciles freight invoices against delivery records overnight.",
    "audience": "Finance leads at logistics companies with 50 to 500 staff.",
    "problem": "Carriers overbill and nobody has time to check every invoice.",
    "offer": "a 15-minute walkthrough on your own invoices",
    "forbidden_claims": ["guaranteed"],
}


def model_reply(*, goal_kind="replies", email_volume=25):
    channels = [
        {"kind": "email", "role": "primary" if goal_kind == "replies" else "support",
         "angle": "Your carrier invoices are wrong more often than you think.",
         "hypothesis": "Controllers reply when shown their own overbilling rate.",
         "daily_volume": email_volume, "send_window": ["08:30", "16:00"],
         "weekdays": "weekdays", "timezone": "Europe/Berlin"},
        {"kind": "distribution", "role": "primary" if goal_kind == "views" else "support",
         "angle": "One overbilled invoice, explained in 20 seconds.",
         "hypothesis": "Short proof videos warm the same accounts.",
         "daily_volume": 1, "platforms": ["youtube"]},
        {"kind": "image", "role": "support", "angle": "Before and after an audit.",
         "hypothesis": "A before-and-after picture carries the proof.", "recipe_family": "demo"},
    ]
    return json.dumps({
        "summary": "Email finance leads; support with short videos.",
        "audience": {"description": "Finance leads at freight forwarders.", "source": "existing_contacts"},
        "channels": channels,
    })


@pytest.fixture()
def client(tmp_path, monkeypatch):
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


def _plan(client, monkeypatch, *, goal_kind="replies", target=20, horizon=30):
    product = client.post("/api/v1/gtm/products", json=PRODUCT).json()
    monkeypatch.setattr(
        client.app.state.ai_broker,
        "call",
        lambda *args, **kwargs: SimpleNamespace(
            text=model_reply(goal_kind=goal_kind), provider_id="p", model_id="m", policy="standard"
        ),
    )
    plan = client.post("/api/v1/gtm/plans", json={
        "product_id": product["id"], "goal_kind": goal_kind, "goal_target": target,
        "horizon_days": horizon,
    })
    assert plan.status_code == 201, plan.text
    return product, plan.json()


def _count(client) -> int:
    # `list_campaigns` returns (rows, total).
    _, total = client.app.state.engine.store.list_campaigns(limit=500)
    return total


# ── criterion 1: one paused campaign per channel, each linked ───────────────


def test_apply_creates_one_paused_campaign_per_channel(client, monkeypatch):
    product, plan = _plan(client, monkeypatch)
    before = _count(client)

    applied = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    assert applied.status_code == 200, applied.text
    body = applied.json()

    assert body["plan"]["status"] == "applied"
    assert body["plan"]["applied_at"]
    assert _count(client) == before + 3
    store = client.app.state.engine.store
    gtm = client.app.state.gtm_store
    kinds = []
    for entry in body["campaigns"]:
        campaign = store.get_campaign(entry["campaign_id"])
        kinds.append(campaign["kind"])
        # Paused: the engine acts only on `active`, so nothing moves from here.
        assert campaign["status"] == "paused"
        assert gtm.product_for_campaign(entry["campaign_id"], "local")["id"] == product["id"]
    assert sorted(kinds) == ["distribution", "email", "image"]
    links = {item["channel"]: item["plan_id"] for item in gtm.plan_links(plan["id"], "local")}
    assert links == {"email": plan["id"], "distribution": plan["id"], "image": plan["id"]}


# ── criterion 2: email settings come from the plan ──────────────────────────


def test_email_settings_come_from_the_plan(client, monkeypatch):
    _, plan = _plan(client, monkeypatch)
    body = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()
    email_id = next(item["campaign_id"] for item in body["campaigns"] if item["kind"] == "email")
    campaign = client.app.state.engine.store.get_campaign(email_id)
    email = next(item for item in plan["plan"]["channels"] if item["kind"] == "email")

    assert campaign["daily_send_limit"] == email["daily_volume"] == 25
    assert campaign["send_window_start"] == "08:30"
    assert campaign["send_window_end"] == "16:00"
    assert campaign["send_weekdays"] == [0, 1, 2, 3, 4]
    assert campaign["timezone"] == "Europe/Berlin"
    assert campaign["experiment_hypothesis"] == email["hypothesis"]
    assert campaign["approval_mode"] == "each_message"
    assert "Ledgerline" in campaign["name"] and len(campaign["name"]) <= 120


# ── criterion 3: a views goal lands on the distribution campaign ───────────


def test_views_goal_is_set_on_distribution(client, monkeypatch):
    _, plan = _plan(client, monkeypatch, goal_kind="views", target=50000, horizon=60)
    body = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()
    distribution_id = next(
        item["campaign_id"] for item in body["campaigns"] if item["kind"] == "distribution"
    )
    goals = client.app.state.distribution_store.list_goals(distribution_id)
    assert len(goals) == 1
    assert goals[0]["metric"] == "views"
    assert int(goals[0]["target"]) == 50000
    expected = (date.fromisoformat(plan["created_at"][:10]) + timedelta(days=60)).isoformat()
    assert goals[0]["deadline"] == expected


# ── criterion 4: only a draft can be applied ────────────────────────────────


def test_only_a_draft_can_be_applied(client, monkeypatch):
    _, plan = _plan(client, monkeypatch)
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").status_code == 200
    after_first = _count(client)

    again = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    assert again.status_code == 409
    assert again.json()["detail"]["error"] == "wrong_state"
    assert _count(client) == after_first

    _, discarded = _plan(client, monkeypatch)
    client.post(f"/api/v1/gtm/plans/{discarded['id']}/discard")
    refused = client.post(f"/api/v1/gtm/plans/{discarded['id']}/apply")
    assert refused.status_code == 409
    assert _count(client) == after_first
    assert client.post("/api/v1/gtm/plans/no-such/apply").status_code == 404


def test_two_applies_at_once_cannot_both_run(client, monkeypatch):
    _, plan = _plan(client, monkeypatch)
    before = _count(client)
    with client.app.state.campaign_locks.hold(f"gtm-plan:{plan['id']}"):
        busy = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    assert busy.status_code == 409
    assert _count(client) == before
    assert client.get(f"/api/v1/gtm/plans/{plan['id']}").json()["status"] == "draft"


# ── criterion 5: next steps, and nothing spent or imported ──────────────────


def test_apply_returns_next_steps_and_spends_nothing(client, monkeypatch):
    _, plan = _plan(client, monkeypatch)
    body = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()

    assert body["next_steps"]
    for step in body["next_steps"]:
        assert step["page"] in KNOWN_PAGES
        assert step["label"] and step["why"].endswith(".")
    pages = {step["page"] for step in body["next_steps"]}
    assert {"contacts", "drafts", "campaigns"} <= pages

    for entry in body["campaigns"]:
        summary = client.app.state.engine.store.campaign_summary(entry["campaign_id"])
        assert summary["contacts"] == 0


# ── the half-finished apply, driven directly ────────────────────────────────


class FakeCrm:
    """Enough of the CRM for apply: campaigns, updates and goals, in memory."""

    def __init__(self, *, fail_on_call: int = 0) -> None:
        self.campaigns: dict[str, dict] = {}
        self.goals: dict[str, list[dict]] = {}
        self.calls = 0
        self.fail_on_call = fail_on_call

    def create_campaign(self, **kwargs) -> str:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("the database went away")
        campaign_id = f"c{len(self.campaigns) + 1}"
        self.campaigns[campaign_id] = {"id": campaign_id, "status": "active", **kwargs}
        return campaign_id

    def update_campaign(self, campaign_id: str, changes: dict) -> dict:
        self.campaigns[campaign_id].update(changes)
        return self.campaigns[campaign_id]

    def set_goal(self, **kwargs) -> str:
        self.goals.setdefault(kwargs["campaign_id"], []).append(kwargs)
        return "g"

    def goals_of(self, campaign_id: str) -> list[dict]:
        return self.goals.get(campaign_id, [])


@contextmanager
def no_lock(key: str):
    yield


def _service(tmp_path, crm: FakeCrm, *, identities=()):
    store = GtmStore(tmp_path / "gtm.db")
    service = GtmService(
        store,
        workspace_id="local",
        identities=lambda: list(identities),
        accounts=lambda: [{"platform": "youtube", "daily_cap": 0}],
        apollo_ready=lambda: False,
        ask=lambda **kwargs: SimpleNamespace(text=model_reply(), provider_id="p", model_id="m",
                                             policy="standard"),
        create_campaign=crm.create_campaign,
        update_campaign=crm.update_campaign,
        set_goal=crm.set_goal,
        goals_of=crm.goals_of,
        lock=no_lock,
    )
    product = store.create_product("local", PRODUCT)
    return store, service, product


def test_a_failed_apply_resumes_without_duplicates(tmp_path):
    crm = FakeCrm(fail_on_call=2)
    store, service, product = _service(tmp_path, crm)
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": "replies", "goal_target": 20})

    with pytest.raises(RuntimeError):
        service.apply_plan(plan["id"])
    # Half done: one campaign exists, and the plan has not claimed to be applied.
    assert len(crm.campaigns) == 1
    assert store.get_plan(plan["id"], "local")["status"] == "draft"

    crm.fail_on_call = 0
    applied = service.apply_plan(plan["id"])
    # The first campaign is reused, not made twice.
    assert len(crm.campaigns) == 3
    assert sorted(item["campaign_id"] for item in applied["campaigns"]) == ["c1", "c2", "c3"]
    assert all(campaign["status"] == "paused" for campaign in crm.campaigns.values())
    assert applied["plan"]["status"] == "applied"
    store.close()


def test_a_volume_above_the_campaign_limit_is_capped_and_said(tmp_path):
    identities = [
        {"name": f"Box {i}", "stream": "targeted_outreach", "status": "active",
         "provider_type": "gmail"}
        for i in range(20)
    ]
    crm = FakeCrm()
    store, service, product = _service(tmp_path, crm, identities=identities)
    service.ask = lambda **kwargs: SimpleNamespace(
        text=model_reply(email_volume=600), provider_id="p", model_id="m", policy="standard"
    )
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": "replies", "goal_target": 20})
    email = next(item for item in plan["plan"]["channels"] if item["kind"] == "email")
    assert email["daily_volume"] == 600  # twenty mailboxes really do carry it

    applied = service.apply_plan(plan["id"])
    created = next(c for c in crm.campaigns.values() if c["kind"] == "email")
    assert created["daily_send_limit"] == 500
    assert any("500" in note for note in applied["notes"])
    store.close()


def test_apply_on_an_unknown_or_foreign_plan_is_not_found(tmp_path):
    crm = FakeCrm()
    store, service, _ = _service(tmp_path, crm)
    with pytest.raises(KeyError):
        service.apply_plan("no-such")
    assert crm.calls == 0
    store.close()


def test_state_errors_are_the_store_type():
    assert issubclass(PlanStateError, RuntimeError)


def test_apply_refuses_when_the_product_was_deleted(tmp_path):
    crm = FakeCrm()
    store, service, product = _service(tmp_path, crm)
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": "replies", "goal_target": 20})
    store.delete_product(product["id"], "local")
    with pytest.raises(PlanStateError) as refused:
        service.apply_plan(plan["id"])
    assert "deleted" in str(refused.value)
    assert crm.calls == 0
    store.close()


def test_saving_the_product_checklist_keeps_what_apply_recorded(client, monkeypatch):
    product, plan = _plan(client, monkeypatch)
    body = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()
    ids = [item["campaign_id"] for item in body["campaigns"]]

    # The owner re-saves the checklist with the same campaigns ticked.
    client.put(f"/api/v1/gtm/products/{product['id']}/campaigns", json={"campaign_ids": ids})

    links = {item["channel"]: item["plan_id"]
             for item in client.app.state.gtm_store.plan_links(plan["id"], "local")}
    assert links == {"email": plan["id"], "distribution": plan["id"], "image": plan["id"]}
