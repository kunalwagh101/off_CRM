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
from broker_fakes import fake_model_calls

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


def model_reply(*, goal_kind="replies", email_volume=25, post_volume=1):
    channels = [
        {"kind": "email", "role": "primary" if goal_kind == "replies" else "support",
         "angle": "Your carrier invoices are wrong more often than you think.",
         "hypothesis": "Controllers reply when shown their own overbilling rate.",
         "daily_volume": email_volume, "send_window": ["08:30", "16:00"],
         "weekdays": "weekdays", "timezone": "Europe/Berlin"},
        {"kind": "distribution", "role": "primary" if goal_kind == "views" else "support",
         "angle": "One overbilled invoice, explained in 20 seconds.",
         "hypothesis": "Short proof videos warm the same accounts.",
         "daily_volume": post_volume, "platforms": ["local_outbox"]},
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


def _plan(client, monkeypatch, *, goal_kind="replies", target=20, horizon=30, post_volume=1):
    product = client.post("/api/v1/gtm/products", json=PRODUCT).json()
    fake_model_calls(monkeypatch, client.app.state.ai_broker,
        lambda *args, **kwargs: SimpleNamespace(
            text=model_reply(goal_kind=goal_kind, post_volume=post_volume), provider_id="p", model_id="m", policy="standard"
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


def test_apply_registers_one_paused_pair_with_the_plan_rate_and_keeps_existing_pairs(client, monkeypatch):
    client.post("/api/v1/distribution/accounts", json={"platform": "local_outbox", "handle": "@local", "daily_cap": 5})
    previous = {"distribution_campaign_id": "old-d", "image_campaign_id": "old-i", "account_ids": []}
    client.app.state.content_automation.update({"pipelines": [previous]})
    _, plan = _plan(client, monkeypatch, goal_kind="views", post_volume=3)
    applied = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()
    config = client.get("/api/v1/content-automation").json()
    assert len(config["pipelines"]) == 2
    pair = next(row for row in config["pipelines"] if row.get("plan_id") == plan["id"])
    links = {row["kind"]: row["campaign_id"] for row in applied["campaigns"]}
    assert pair["distribution_campaign_id"] == links["distribution"]
    assert pair["image_campaign_id"] == links["image"]
    assert pair["posts_per_day"] == 3 and pair["enabled"] is False
    assert config["enabled"] is False
    assert all(client.app.state.engine.store.get_campaign(cid)["status"] == "paused" for cid in links.values())


def test_start_posting_requires_an_applied_plan_and_a_connected_account_then_resumes_the_pair(client, monkeypatch):
    account = client.post("/api/v1/distribution/accounts", json={"platform": "local_outbox", "handle": "@local"}).json()
    _, plan = _plan(client, monkeypatch, goal_kind="views")
    path = f"/api/v1/gtm/plans/{plan['id']}/start-posting"
    assert client.post(path, json={"account_ids": [account["id"]]}).status_code == 409
    client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    assert client.post(path, json={"account_ids": ["missing"]}).status_code == 404
    started = client.post(path, json={"account_ids": [account["id"]]})
    assert started.status_code == 200, started.text
    pair = next(row for row in started.json()["pipelines"] if row.get("plan_id") == plan["id"])
    assert started.json()["enabled"] and pair["enabled"]
    for key in ("distribution_campaign_id", "image_campaign_id"):
        assert client.app.state.engine.store.get_campaign(pair[key])["status"] == "active"
    assert client.post(path, json={"account_ids": [account["id"]]}).status_code == 200
    assert len(client.get("/api/v1/content-automation").json()["pipelines"]) == 1


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
        # "" is a step no screen does yet; the page shows it without a link.
        assert step["page"] in KNOWN_PAGES | {""}
        assert step["label"] and step["why"].endswith(".")
    pages = {step["page"] for step in body["next_steps"]}
    assert {"contacts", "drafts", "campaigns"} <= pages
    # Where the plan's angle reaches an email, said where the owner writes one.
    drafts = next(step for step in body["next_steps"] if step["page"] == "drafts")
    assert "{product_angle}" in drafts["why"]

    for entry in body["campaigns"]:
        summary = client.app.state.engine.store.campaign_summary(entry["campaign_id"])
        assert summary["contacts"] == 0


def test_next_steps_link_the_posting_screen_and_require_explicit_start_and_review(client, monkeypatch):
    _, plan = _plan(client, monkeypatch)
    body = client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").json()
    posting = [step for step in body["next_steps"] if step["page"] == "posting" and "start" in step["why"].lower()]
    assert len(posting) == 1
    assert "start" in posting[0]["why"].lower()
    assert "approve" in posting[0]["why"].lower()
    assert not [step for step in body["next_steps"] if step["page"] == ""]


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


def test_a_campaign_is_paused_before_it_is_linked(tmp_path, monkeypatch):
    """The CRM creates campaigns active. When linking fails after the create, the
    campaign left behind must already be paused — never quietly running."""
    crm = FakeCrm()
    store, service, product = _service(tmp_path, crm)
    plan = service.draft_plan({"product_id": product["id"], "goal_kind": "replies", "goal_target": 20})
    real = store.link_campaign
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "link_campaign", flaky)
    with pytest.raises(RuntimeError):
        service.apply_plan(plan["id"])
    assert len(crm.campaigns) == 1
    assert all(campaign["status"] == "paused" for campaign in crm.campaigns.values())
    store.close()


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


def test_failed_start_leaves_campaigns_paused_and_pair_disabled_then_can_retry(client, monkeypatch):
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@start'}).json()
    _, plan = _plan(client, monkeypatch, goal_kind='views', post_volume=3)
    client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    service = client.app.state.content_automation
    activate = service.activate_pipeline
    def fail(*args, **kwargs):
        raise OSError('test activation failure')
    monkeypatch.setattr(service, 'activate_pipeline', fail)
    response = client.post(f"/api/v1/gtm/plans/{plan['id']}/start-posting", json={'account_ids': [account['id']]})
    assert response.status_code == 500
    assert response.headers['X-Error-ID'].startswith('E-')
    pair = service.config()['pipelines'][0]
    assert not pair['enabled'] and not service.config()['enabled']
    assert all(client.app.state.engine.store.get_campaign(pair[key])['status'] == 'paused' for key in ('distribution_campaign_id', 'image_campaign_id'))
    monkeypatch.setattr(service, 'activate_pipeline', activate)
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/start-posting", json={'account_ids': [account['id']]}).status_code == 200


def test_post_review_refuses_foreign_rows_and_keeps_them_out_of_the_list(client):
    crm = client.app.state.engine.store
    campaign = crm.create_campaign(name='Posts', kind='distribution', daily_send_limit=1)
    store = client.app.state.distribution_store
    account = store.add_account(platform='local_outbox', handle='foreign', workspace_id='other')
    post = store.create_post(campaign_id=campaign, account_id=account, platform='local_outbox', caption='private', workspace_id='other')
    assert client.get(f'/api/v1/campaigns/{campaign}/posts').json()['items'] == []
    for action in ('skip', 'approve', 'schedule-next'):
        response = client.post(f'/api/v1/posts/{post}/{action}')
        assert response.status_code == 404, response.text
    assert store.get_post(post)['status'] == 'draft'
    response = client.post(f'/api/v1/campaigns/{campaign}/posts', json={'account_id': account, 'caption': 'text'})
    assert response.status_code == 404


def test_api_spaces_human_approved_posts_at_plan_rate_and_preserves_caps(client, monkeypatch):
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@slots', 'daily_cap': 5}).json()
    _, plan = _plan(client, monkeypatch, goal_kind='views', post_volume=3)
    client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    client.post(f"/api/v1/gtm/plans/{plan['id']}/start-posting", json={'account_ids': [account['id']]})
    pair = client.app.state.content_automation.config()['pipelines'][0]
    assert pair['posts_per_day'] == 3
    assert client.patch(f"/api/v1/distribution/accounts/{account['id']}", json={'daily_cap': 1}).status_code == 200
    ids = []
    for caption in ('one', 'two'):
        post = client.post(f"/api/v1/campaigns/{pair['distribution_campaign_id']}/posts", json={'account_id': account['id'], 'caption': caption}).json()
        ids.append(post['id'])
        assert client.post(f"/api/v1/posts/{post['id']}/approve").status_code == 200
    first = client.post(f'/api/v1/posts/{ids[0]}/schedule-next')
    assert first.status_code == 200, first.text
    second = client.post(f'/api/v1/posts/{ids[1]}/schedule-next')
    # An 8-hour slot may fall tomorrow; cap refusal is required only today.
    from datetime import datetime
    later = datetime.fromisoformat(first.json()['scheduled_at']) + timedelta(hours=8)
    if later.date() == datetime.fromisoformat(first.json()['scheduled_at']).date():
        assert second.status_code == 422
        assert client.app.state.distribution_store.get_post(ids[1])['status'] == 'approved'
    else:
        assert second.status_code == 200
    assert client.get(f"/api/v1/campaigns/{pair['distribution_campaign_id']}/pacing").json()['previous_per_day'] == 3


def test_another_workspace_apply_does_not_register_the_install_timer(tmp_path):
    crm = FakeCrm()
    store, service, _ = _service(tmp_path, crm)
    service.workspace_id = 'client'
    registered = []
    service.register_posting = registered.append
    product = store.create_product('client', PRODUCT)
    plan = service.draft_plan({'product_id': product['id'], 'goal_kind': 'views', 'goal_target': 1000})
    result = service.apply_plan(plan['id'])
    assert registered == []
    assert any('install owner' in note for note in result['notes'])
    assert any(step['page'] == '' and 'owner' in step['why'].lower() for step in result['next_steps'])
    store.close()


def test_a_revision_starts_the_existing_pair_and_rejects_its_superseded_plan(client, monkeypatch):
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@revised', 'daily_cap': 5}).json()
    _, plan = _plan(client, monkeypatch, goal_kind='views', post_volume=3)
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/apply").status_code == 200
    original = client.app.state.content_automation.config()['pipelines'][0]
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/review", json={'use_model': False}).status_code == 201
    revised = client.post(f"/api/v1/gtm/plans/{plan['id']}/revise", json={'use_model': False})
    assert revised.status_code == 201, revised.text
    revision = revised.json()
    assert client.post(f"/api/v1/gtm/plans/{revision['id']}/apply").status_code == 200
    pair = client.app.state.content_automation.config()['pipelines'][0]
    assert pair['distribution_campaign_id'] == original['distribution_campaign_id']
    assert pair['plan_id'] == revision['id']
    started = client.post(f"/api/v1/gtm/plans/{revision['id']}/start-posting", json={'account_ids': [account['id']]})
    assert started.status_code == 200, started.text
    assert client.post(f"/api/v1/gtm/plans/{plan['id']}/start-posting", json={'account_ids': [account['id']]}).status_code == 409


def test_post_review_resolves_video_and_refuses_foreign_media(client):
    crm = client.app.state.engine.store
    campaign = crm.create_campaign(name='Post media', kind='distribution', daily_send_limit=1)
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@media'}).json()
    store = client.app.state.video_store
    payload = b'video fixture bytes; transport check only'
    local = store.store_render(project_id='p', campaign_id='video-campaign', payload=payload, gate_report=None, status='ready')
    foreign = store.store_render(project_id='q', campaign_id='foreign-video', payload=payload, gate_report=None, status='ready', workspace_id='other')
    ids = []
    for asset in (local, foreign, 'missing-media'):
        response = client.post(f'/api/v1/campaigns/{campaign}/posts', json={'account_id': account['id'], 'caption': 'Media test', 'asset_id': asset})
        assert response.status_code == 201
        ids.append(response.json()['id'])
    posts = client.get(f'/api/v1/campaigns/{campaign}/posts').json()['items']
    own = next(row for row in posts if row['id'] == ids[0])
    assert own['media_kind'] == 'video' and own['media_url'] == f'/posts/{ids[0]}/media'
    response = client.get('/api/v1'+own['media_url'])
    assert response.status_code == 200 and response.content == payload
    assert response.headers['content-type'].startswith('video/')
    for post_id in ids[1:]:
        assert client.get(f'/api/v1/posts/{post_id}/media').status_code == 404
        assert next(row for row in posts if row['id'] == post_id)['media_error']


def test_workspace_login_cannot_change_install_pacing_or_another_accounts_cap(client):
    from offsetx_apollo_builder.api.auth import SESSION_COOKIE
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@owner'}).json()
    auth = client.app.state.workspace_auth
    identity = auth.create(username='posting-client', workspace_id='client', password='valid-test-password-123')
    client.cookies.set(SESSION_COOKIE, auth.issue(identity))
    assert client.post('/api/v1/content-automation/pace', json={'decision': 'accept'}).status_code == 403
    assert client.post('/api/v1/gtm/plans/unknown/start-posting', json={'account_ids': [account['id']]}).status_code == 403
    assert client.patch(f"/api/v1/distribution/accounts/{account['id']}", json={'daily_cap': 100}).status_code == 404
    assert client.app.state.distribution_store.get_account(account['id'])['daily_cap'] == 0


def test_pacing_reads_only_the_accounts_selected_for_this_pair(client, monkeypatch):
    first = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@selected', 'daily_cap': 2}).json()
    client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@other', 'daily_cap': 20})
    _, plan = _plan(client, monkeypatch, goal_kind='views')
    client.post(f"/api/v1/gtm/plans/{plan['id']}/apply")
    client.post(f"/api/v1/gtm/plans/{plan['id']}/start-posting", json={'account_ids': [first['id']]})
    pair = client.app.state.content_automation.config()['pipelines'][0]
    response = client.get(f"/api/v1/campaigns/{pair['distribution_campaign_id']}/pacing")
    assert response.status_code == 200
    assert response.json()['owner_cap'] == 2


def test_a_missing_or_foreign_attachment_cannot_be_approved_or_published(client):
    from datetime import datetime, timezone
    crm = client.app.state.engine.store
    campaign = crm.create_campaign(name='Unsafe attachments', kind='distribution', daily_send_limit=1)
    crm.update_campaign(campaign, {"status": "active"})
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@safe'}).json()
    foreign = client.app.state.video_store.store_render(project_id='foreign', campaign_id='v', payload=b'private media fixture', gate_report=None, status='ready', workspace_id='other')
    dist = client.app.state.distribution_store
    for asset in (foreign, 'missing-attachment'):
        post = dist.create_post(campaign_id=campaign, account_id=account['id'], platform='local_outbox', caption='do not send', asset_id=asset)
        assert client.post(f'/api/v1/posts/{post}/approve').status_code == 404
        # Legacy already-scheduled rows must be validated again at publish time.
        dist.update_post(post, {'status': 'scheduled', 'scheduled_at': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
    result = client.post('/api/v1/distribution/publish-due').json()
    assert result['published'] == 0 and result['failed'] == 2
    assert not list(dist.outbox_dir.glob('*.json'))


def test_starting_plan_b_does_not_publish_a_stopped_plans_scheduled_post(client, monkeypatch):
    account = client.post('/api/v1/distribution/accounts', json={'platform': 'local_outbox', 'handle': '@pair-guard', 'daily_cap': 5}).json()
    _, first = _plan(client, monkeypatch, goal_kind='views')
    client.post(f"/api/v1/gtm/plans/{first['id']}/apply")
    client.post(f"/api/v1/gtm/plans/{first['id']}/start-posting", json={'account_ids': [account['id']]})
    config = client.app.state.content_automation.config()
    campaign = config['pipelines'][0]['distribution_campaign_id']
    post = client.post(f'/api/v1/campaigns/{campaign}/posts', json={'account_id': account['id'], 'caption': 'A waiting post'}).json()
    client.post(f"/api/v1/posts/{post['id']}/approve")
    client.post(f"/api/v1/posts/{post['id']}/schedule-next")
    client.patch('/api/v1/content-automation', json={'enabled': False, 'sweep': False, 'plan': False, 'draft': False})
    _, second = _plan(client, monkeypatch, goal_kind='views')
    client.post(f"/api/v1/gtm/plans/{second['id']}/apply")
    client.post(f"/api/v1/gtm/plans/{second['id']}/start-posting", json={'account_ids': [account['id']]})
    result = client.post('/api/v1/content-automation/run').json()['results']
    published = next(row for row in result if row['step'] == 'publish_due')
    assert published['published'] == 0
    assert client.app.state.distribution_store.get_post(post['id'])['status'] == 'scheduled'
    # Explicitly resuming A makes its previously approved post eligible again.
    client.post(f"/api/v1/gtm/plans/{first['id']}/start-posting", json={'account_ids': [account['id']]})
    assert client.post('/api/v1/content-automation/run').json()['results'][-1]['published'] == 1


def test_pacing_does_not_return_another_plans_or_workspaces_waiting_proposal(client):
    from offsetx_apollo_builder.api.auth import SESSION_COOKIE
    campaign = client.app.state.engine.store.create_campaign(name='Pacing isolation', kind='distribution', daily_send_limit=1)
    service = client.app.state.content_automation
    service.update({'pending_pace': {'distribution_campaign_id': 'other-campaign', 'reason': 'owner-only reason', 'suggested_per_day': 2}})
    assert client.get(f'/api/v1/campaigns/{campaign}/pacing').json()['pending'] == {}
    identity = client.app.state.workspace_auth.create(username='pace-client', workspace_id='client', password='valid-test-password-123')
    client.cookies.set(SESSION_COOKIE, client.app.state.workspace_auth.issue(identity))
    assert client.get(f'/api/v1/campaigns/{campaign}/pacing').json()['pending'] == {}
