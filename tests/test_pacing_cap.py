"""The owner's cap, and a recommendation that waits.

The engine works out the ideal posting rate. It does not get to act on it.

That split is the whole point of this file, and it is the owner's own words:
*"it should be left up to the user, he will decide, although the AI will make
him the ideal recommendation after looking at the data."* So three things are
protected here.

**A cap the owner set is not something the goal argues with.** A million views
by December does not entitle anything to post nine times a day to a handle
capped at three. The cap sits under the platform's own limit, and under the
arithmetic, and it wins.

**No cap is invented.** Zero means *no cap set*, and that is not the same as
zero posts a day. A default this code made up would be a number the owner never
chose being enforced as though they had — and the honest state before anyone
sets one is the platform's published limit and nothing else.

**Recommending and doing are separate.** The default is `suggest`: the number
is worked out every cycle and applied by nobody. Turning that into `auto` is a
deliberate act, and even then the cap still binds.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.distribution import pacing


def _in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


BEHIND = [{"post_id": f"p{index}", "views": 1_000} for index in range(20)]


def _decide(**overrides):
    arguments = {
        "goal_target": 1_000_000,
        "goal_deadline": _in_days(100),
        "metrics": BEHIND,
        "current_per_day": 1.0,
    }
    arguments.update(overrides)
    return pacing.decide(**arguments)


# ── the cap binds ───────────────────────────────────────────────────────────


def test_with_no_cap_the_rate_climbs_toward_what_the_goal_needs():
    """The baseline the cap has to be measured against."""
    decision = _decide()
    assert decision.action == "raise"
    assert decision.posts_per_day > 1.0
    assert decision.capped_by == ""
    assert decision.owner_cap == 0.0


def test_a_cap_stops_the_climb_and_says_it_was_the_owner_who_stopped_it():
    decision = _decide(owner_cap=1.1)
    assert decision.posts_per_day == pytest.approx(1.1)
    assert decision.capped_by == "your own cap"
    assert "Raise it if you want the goal met sooner" in decision.reason


def test_the_cap_is_worded_as_the_owners_and_not_as_a_platform_rule():
    """Two different facts. A platform limit is one neither of you chose; a cap
    is one of you did, and the sentence should not blame the wrong party."""
    owner = _decide(owner_cap=1.1)
    platform = _decide(ceiling=1.1, ceiling_source="instagram")
    assert "published limit" not in owner.reason
    assert "published limit" in platform.reason


def test_the_lower_of_the_two_ceilings_is_the_one_that_binds():
    tight_owner = _decide(owner_cap=1.05, ceiling=8.0, ceiling_source="instagram")
    assert tight_owner.capped_by == "your own cap"
    tight_platform = _decide(owner_cap=9.0, ceiling=1.05, ceiling_source="instagram")
    assert tight_platform.capped_by == "instagram"


def test_a_rate_already_over_the_cap_comes_down_before_any_goal_arithmetic():
    """Not a pacing question. A limit is being exceeded right now, and that is
    true whether or not there is a goal to pace against."""
    decision = _decide(current_per_day=9.0, owner_cap=3.0, goal_target=0)
    assert decision.action == "lower"
    assert decision.posts_per_day == 3.0
    assert decision.capped_by == "your own cap"


def test_zero_means_no_cap_and_never_zero_posts():
    """The distinction the whole setting turns on."""
    assert _decide(owner_cap=0.0).posts_per_day > 1.0
    assert _decide(owner_cap=0).capped_by == ""


# ── over HTTP, on a real account ────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _account(client: TestClient, **body) -> dict:
    response = client.post(
        "/api/v1/distribution/accounts",
        json={"platform": "local_outbox", "handle": "@studio", "label": "Studio", **body},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_a_new_account_has_no_cap_until_somebody_sets_one(client):
    assert _account(client)["daily_cap"] == 0


def test_a_cap_can_be_set_at_connect_time_or_changed_afterwards(client):
    account = _account(client, daily_cap=3)
    assert account["daily_cap"] == 3
    changed = client.patch(
        f"/api/v1/distribution/accounts/{account['id']}", json={"daily_cap": 5}
    )
    assert changed.status_code == 200
    assert changed.json()["daily_cap"] == 5


def test_a_cap_is_bounded_rather_than_trusted(client):
    account = _account(client)
    for given, want in ((-4, 0), (9999, 200)):
        body = client.patch(
            f"/api/v1/distribution/accounts/{account['id']}", json={"daily_cap": given}
        ).json()
        assert body["daily_cap"] == want


def test_reconnecting_an_account_does_not_wipe_its_cap(client):
    """The limit is a decision about the handle, not about this connection."""
    account = _account(client, daily_cap=4)
    again = _account(client)
    assert again["id"] == account["id"]
    assert again["daily_cap"] == 4


def _campaign(client: TestClient) -> str:
    return client.post(
        "/api/v1/campaigns", json={"name": "Reach", "kind": "distribution"}
    ).json()["id"]


def _post(client: TestClient, campaign_id: str, account_id: str) -> str:
    return client.post(
        f"/api/v1/campaigns/{campaign_id}/posts",
        json={"account_id": account_id, "caption": "hello"},
    ).json()["id"]


def test_the_cap_refuses_the_post_that_would_cross_it(client):
    campaign_id = _campaign(client)
    account = _account(client, daily_cap=2)
    day = "2027-03-04T09:00:00+00:00"

    for _ in range(2):
        post_id = _post(client, campaign_id, account["id"])
        client.post(f"/api/v1/posts/{post_id}/approve")
        assert client.post(
            f"/api/v1/posts/{post_id}/schedule", json={"at": day}
        ).status_code == 200

    third = _post(client, campaign_id, account["id"])
    client.post(f"/api/v1/posts/{third}/approve")
    refused = client.post(f"/api/v1/posts/{third}/schedule", json={"at": day})
    assert refused.status_code == 422
    assert "capped @studio at 2" in refused.json()["detail"]


def test_the_cap_is_per_day_and_tomorrow_is_a_fresh_one(client):
    campaign_id = _campaign(client)
    account = _account(client, daily_cap=1)
    first = _post(client, campaign_id, account["id"])
    client.post(f"/api/v1/posts/{first}/approve")
    client.post(f"/api/v1/posts/{first}/schedule", json={"at": "2027-03-04T09:00:00+00:00"})

    second = _post(client, campaign_id, account["id"])
    client.post(f"/api/v1/posts/{second}/approve")
    assert client.post(
        f"/api/v1/posts/{second}/schedule", json={"at": "2027-03-05T09:00:00+00:00"}
    ).status_code == 200


def test_the_cap_counts_across_campaigns_because_the_handle_does(client):
    """It is the account that gets restricted, and it does not care which
    campaign filled its day."""
    account = _account(client, daily_cap=1)
    day = "2027-03-04T09:00:00+00:00"
    first_campaign, second_campaign = _campaign(client), _campaign(client)

    one = _post(client, first_campaign, account["id"])
    client.post(f"/api/v1/posts/{one}/approve")
    client.post(f"/api/v1/posts/{one}/schedule", json={"at": day})

    two = _post(client, second_campaign, account["id"])
    client.post(f"/api/v1/posts/{two}/approve")
    assert client.post(f"/api/v1/posts/{two}/schedule", json={"at": day}).status_code == 422


# ── the recommendation, and who acts on it ──────────────────────────────────


def test_the_default_is_to_recommend_and_wait(client):
    body = client.get("/api/v1/content-automation").json()
    assert body["pace_mode"] == "suggest"
    assert body["pending_pace"] == {}


def test_the_suggestion_endpoint_reads_and_never_writes(client):
    campaign_id = _campaign(client)
    store = client.app.state.distribution_store
    store.set_goal(campaign_id=campaign_id, metric="views", target=1_000_000,
                   deadline=_in_days(100))
    for index in range(20):
        post_id = store.create_post(
            campaign_id=campaign_id, account_id="a", platform="local_outbox",
            caption=f"c{index}", asset_id="",
        )
        store.update_post(post_id, {"status": "published"})
        store.record_metrics(post_id=post_id, campaign_id=campaign_id, views=1_000)

    before = client.get("/api/v1/content-automation").json()["posts_per_day"]
    body = client.get(f"/api/v1/campaigns/{campaign_id}/pacing").json()
    assert body["action"] == "raise"
    assert body["reason"]
    assert body["mode"] == "suggest"
    assert client.get("/api/v1/content-automation").json()["posts_per_day"] == before


def test_an_answer_that_is_neither_accept_nor_dismiss_is_a_400(client):
    response = client.post("/api/v1/content-automation/pace", json={"decision": "maybe"})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unknown_decision"


def test_accepting_with_nothing_waiting_is_a_422_and_says_so(client):
    response = client.post("/api/v1/content-automation/pace", json={"decision": "accept"})
    assert response.status_code == 422
    assert "no rate suggestion waiting" in response.json()["detail"]


def test_the_campaigns_own_cap_is_the_sum_of_its_accounts_caps(client):
    """A campaign rate is one number, and three handles capped at two really can
    carry six posts between them."""
    campaign_id = _campaign(client)
    for index, cap in enumerate((2, 3)):
        client.post(
            "/api/v1/distribution/accounts",
            json={"platform": "local_outbox", "handle": f"@studio{index}", "daily_cap": cap},
        )
    body = client.get(f"/api/v1/campaigns/{campaign_id}/pacing").json()
    assert body["owner_cap"] == 5.0


def test_one_uncapped_account_means_the_campaign_has_no_cap(client):
    """Summing over a partly-capped set would invent a campaign limit out of
    handles the owner deliberately left open."""
    campaign_id = _campaign(client)
    client.post("/api/v1/distribution/accounts",
                json={"platform": "local_outbox", "handle": "@one", "daily_cap": 2})
    client.post("/api/v1/distribution/accounts",
                json={"platform": "local_outbox", "handle": "@two"})
    assert client.get(f"/api/v1/campaigns/{campaign_id}/pacing").json()["owner_cap"] == 0.0
