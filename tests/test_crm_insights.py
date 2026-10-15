"""Product tests: cross-campaign search, company coverage and revenue attribution.

Read-only insights over real CRM records. No network/AI/send side effects.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.sales import SalesTracker
from offsetx_apollo_builder.outreach.crm_insights import CRMInsights


def _seed(tmp_path: Path):
    engine = OutreachEngine(tmp_path / "insights.db")
    first = engine.create_campaign(name="Autumn campaign")
    second = engine.create_campaign(name="Winter campaign")
    contact_a = engine.store.upsert_contact(ContactInput(
        full_name="Asha Rao", email="asha@example.com",
        company="Acme Systems", title="Head of Compliance",
    ))
    contact_b = engine.store.upsert_contact(ContactInput(
        full_name="Bilal Khan", email="bilal@example.com",
        company=" acme systems ", title="Engineer",
    ))
    contact_c = engine.store.upsert_contact(ContactInput(
        full_name="Cara Lee", email="cara@example.com", company="Separate Ltd",
    ))
    a, added = engine.store.add_contact_to_campaign(first, contact_a)
    assert added
    b, added = engine.store.add_contact_to_campaign(first, contact_b)
    assert added
    a_other, added = engine.store.add_contact_to_campaign(second, contact_a)
    assert added
    engine.store.add_contact_to_campaign(second, contact_c)
    sales = SalesTracker(engine.store)
    won = sales.create_lead({
        "lead_name": "Asha Rao", "email": "asha@example.com",
        "company": "Acme Systems", "lead_status": "won",
        "total_deal_value": 1000, "cash_collected": 600,
        "refund_clawback_amount": 100,
    })
    open_lead = sales.create_lead({
        "lead_name": "Bilal Khan", "email": "bilal@example.com",
        "company": "ACME SYSTEMS", "lead_status": "proposal",
        "total_deal_value": 700,
    })
    # Simulate previously human-approved campaign-sales associations.
    # Attribution is derived from persisted links, not from email text.
    for member, lead, date in (
        (a, won["id"], "2026-10-14T09:00:00+00:00"),
        (a_other, won["id"], "2026-10-15T09:00:00+00:00"),
        (b, open_lead["id"], "2026-10-14T11:00:00+00:00"),
    ):
        engine.store.connection.execute(
            """INSERT INTO campaign_sales_links
               (campaign_contact_id, sales_lead_id, linked_at) VALUES (?, ?, ?)""",
            (member, lead, date),
        )
    return engine, sales, first, second, a, a_other


def test_unified_search_filters_privately_and_returns_consistent_campaign_links(tmp_path):
    engine, sales, first, second, a, a_other = _seed(tmp_path)
    try:
        service = CRMInsights(engine.store, sales)
        found = service.search("AcMe", limit=1)
        assert found["kind"] == "contacts"
        assert found["total"] == 2
        assert len(found["items"]) == 1
        more = service.search("AcMe", limit=1, offset=1)
        assert len(more["items"]) == 1
        assert {found["items"][0]["id"]}.isdisjoint(
            {more["items"][0]["id"]}
        )
        by_email = service.search("asha@example.com")
        assert by_email["total"] == 1
        row = by_email["items"][0]
        assert row["campaign_count"] == 2
        assert (row["campaign_id"], row["campaign_contact_id"]) in {
            (first, a), (second, a_other)
        }
        assert "notes" not in row and "source_json" not in row
        leads = service.search("acme", kind="leads")
        assert leads["total"] == 2
        assert {item["lead_status"] for item in leads["items"]} == {"won", "proposal"}
        assert service.search("%%")["total"] == 0  # wildcard escaped
        assert service.search("a_")["total"] == 0
        for kwargs in ({"kind": "messages"}, {"limit": 0}, {"offset": -1}):
            with pytest.raises(ValueError):
                service.search("acme", **kwargs)
        with pytest.raises(ValueError):
            service.search("a")
    finally:
        engine.close()


def test_accounts_group_casefolded_company_with_no_join_fanout(tmp_path):
    engine, sales, first, second, a, _ = _seed(tmp_path)
    try:
        svc = CRMInsights(engine.store, sales)
        accounts = svc.accounts()
        assert accounts["total"] == 2
        group = next(item for item in accounts["items"] if item["company_key"] == "acme systems")
        assert group["contacts"] == 2
        assert group["campaigns"] == 2
        assert group["sales_leads"] == 2
        assert group["won_leads"] == 1
        assert svc.accounts(search="separate")["total"] == 1
        assert svc.accounts(search="%%")["total"] == 0
        profile = svc.account("  ACME SYSTEMS  ", limit=1)
        assert profile["contacts"]["total"] == 2
        assert profile["sales_leads"]["total"] == 2
        assert profile["coverage"]["campaigns"] == 2
        assert len(profile["contacts"]["items"]) == 1
        assert len(svc.account("acme systems", limit=1, offset=1)["contacts"]["items"]) == 1
        assert profile["coverage"]["outbound_messages"] == 0
        assert profile["coverage"]["inbound_messages"] == 0
        assert "notes" not in repr(profile)
        with pytest.raises(KeyError):
            svc.account("unknown plc")
        with pytest.raises(ValueError):
            svc.accounts(limit=101)
        with pytest.raises(ValueError):
            svc.account("acme systems", offset=-1)
    finally:
        engine.close()


def test_revenue_attribution_first_link_and_global_totals_not_double_counted(tmp_path):
    engine, sales, first, second, a, _ = _seed(tmp_path)
    try:
        svc = CRMInsights(engine.store, sales)
        data = svc.revenue_attribution()
        assert data["total"] == 2
        by_campaign = {x["campaign_id"]: x for x in data["items"]}
        autumn, winter = by_campaign[first], by_campaign[second]
        assert autumn["contacts"] == 2
        assert winter["contacts"] == 2
        assert autumn["converted_memberships"] == 2
        assert winter["converted_memberships"] == 1
        assert autumn["attributed_leads"] == 2
        assert winter["attributed_leads"] == 0
        assert autumn["won_deals"] == 1
        assert winter["won_deals"] == 0
        assert autumn["booked_value"] == 1000
        assert autumn["recorded_cash"] == 600
        assert autumn["cash_less_clawbacks"] == 500
        assert data["overall"]["attributed_leads"] == 2
        assert data["overall"]["won_deals"] == 1
        assert data["overall"]["recorded_cash"] == 600
        assert sum(x["recorded_cash"] for x in data["items"]) == 600
        page = svc.revenue_attribution(limit=1, offset=1)
        assert page["total"] == 2
        assert len(page["items"]) == 1
        assert page["overall"] == data["overall"]
        assert "not proof" in data["attribution_rule"].lower()
        for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with pytest.raises(ValueError):
                svc.revenue_attribution(**bad)
        assert engine.store.get_campaign_contact(first, a)["status"] == "new"
    finally:
        engine.close()


def test_crm_intelligence_endpoints_are_authenticated_and_bounded(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "none",
        api_token="i" * 40, allowed_hosts=("testserver",),
    )
    auth = {"Authorization": "Bearer " + "i" * 40}
    with TestClient(create_app(settings)) as client:
        cid = client.post("/api/v1/campaigns", json={"name": "Test"}, headers=auth).json()["id"]
        manual = client.post(
            f"/api/v1/campaigns/{cid}/contacts/manual", headers=auth,
            json={"full_name": "Asha Rao", "email": "asha@example.com", "company": "Acme Systems"},
        )
        assert manual.status_code == 200, manual.text
        for path in ("/crm/search?query=asha", "/crm/accounts",
                     "/crm/account?company_key=acme%20systems", "/crm/attribution"):
            assert client.get("/api/v1" + path).status_code == 401
            assert client.get("/api/v1" + path, headers=auth).status_code == 200
        assert client.get("/api/v1/crm/search", headers=auth, params={"query": "a"}).status_code == 422
        assert client.get("/api/v1/crm/search", headers=auth, params={"query": "asha", "kind": "bad"}).status_code == 422
        assert client.get("/api/v1/crm/accounts", headers=auth, params={"limit": 101}).status_code == 422
        assert client.get("/api/v1/crm/accounts/unknown", headers=auth).status_code == 404
        assert client.get("/api/v1/crm/attribution", headers=auth).json()["overall"]["attributed_leads"] == 0
