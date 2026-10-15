"""Product feature regressions: qualified reply conversion, Contact 360 and actions.

No external provider or AI call. SQLite fixtures; hosted PostgreSQL is an
independent required release gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import IncomingMessage
from offsetx_apollo_builder.outreach.relationships import CampaignRelationships
from offsetx_apollo_builder.outreach.relationship_ops import RelationshipOperations
from offsetx_apollo_builder.outreach.sales import SalesTracker


def _seed(tmp_path: Path):
    engine = OutreachEngine(tmp_path / "crm.db")
    campaign = engine.create_campaign(name="Reply conversion")
    other = engine.create_campaign(name="Second campaign")
    csv = tmp_path / "contacts.csv"
    csv.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Ravi Shah,ravi@example.com,Sample Exporters,Director,CBAM,"
        "Published emissions summary,https://example.com/source,Audit readiness\n"
        "Anita Rao,anita@example.com,Sample Exporters,Lead,CBAM,"
        "Published supplier memo,https://example.com/a,Audit documentation\n",
        encoding="utf-8",
    )
    assert engine.import_contacts(campaign, csv)["added"] == 2
    members = {m["email"]: m for m in engine.store.campaign_contacts(campaign)}
    return engine, campaign, other, members


def _reply(engine: OutreachEngine, campaign: str, email: str, identity: str):
    return engine.store.record_reply(
        campaign,
        IncomingMessage(
            provider_message_id=identity,
            thread_id="",
            from_email=email,
            subject="Discuss an introduction",
            body_preview="Happy to discuss next steps.",
        ),
    )


def test_qualified_promotion_is_explicit_idempotent_and_reuses_email(tmp_path: Path):
    engine, campaign, other, members = _seed(tmp_path)
    try:
        sales = SalesTracker(engine.store)
        reviews = CampaignRelationships(engine.store)
        ops = RelationshipOperations(engine.store, sales)
        ravi = members["ravi@example.com"]
        with pytest.raises(ValueError, match="Mark a received reply"):
            ops.promote_reply(campaign, ravi["id"])
        assert _reply(engine, campaign, ravi["email"], "reply-1") == [ravi["id"]]
        with pytest.raises(ValueError, match="Mark a received reply"):
            ops.promote_reply(campaign, ravi["id"])
        reviews.triage(
            campaign, ravi["id"], review_status="triaged", outcome="positive",
        )
        first = ops.promote_reply(campaign, ravi["id"])
        assert first["created"] is True
        assert first["linked"] is True
        lead_id = first["lead"]["id"]
        assert sales.get_lead(lead_id)["email"] == ravi["email"]
        assert sales.list_leads()[1] == 1
        repeat = ops.promote_reply(campaign, ravi["id"])
        assert repeat["lead"]["id"] == lead_id
        assert repeat["created"] is False and repeat["linked"] is False
        assert sales.list_leads()[1] == 1

        # Same email in a different campaign references the same sales lead,
        # not a new lead and not a changed profile.
        membership_id, added = engine.store.add_contact_to_campaign(
            other, ravi["contact_id"]
        )
        assert added is True
        assert _reply(engine, other, ravi["email"], "reply-2") == [membership_id]
        reviews.triage(other, membership_id, review_status="triaged", outcome="meeting")
        result = ops.promote_reply(other, membership_id)
        assert result["created"] is False
        assert result["lead"]["id"] == lead_id
        assert sales.list_leads()[1] == 1
        assert ops.contact_360(campaign, ravi["id"])["sales_lead"]["id"] == lead_id
        assert ops.contact_360(other, membership_id)["sales_lead"]["id"] == lead_id

        # A different campaign cannot borrow a membership ID directly.
        with pytest.raises(KeyError):
            ops.promote_reply(other, members["anita@example.com"]["id"])
        assert engine.store.get_campaign_contact(campaign, ravi["id"])["status"] == "replied"
        assert engine.store.list_events(campaign)[1] >= 2
    finally:
        engine.close()


def test_duplicate_sales_email_requires_human_reconciliation(tmp_path: Path):
    engine, campaign, _, members = _seed(tmp_path)
    try:
        ravi = members["ravi@example.com"]
        sales = SalesTracker(engine.store)
        sales.create_lead({"lead_name": "Ravi A", "email": ravi["email"]})
        sales.create_lead({"lead_name": "Ravi B", "email": ravi["email"]})
        _reply(engine, campaign, ravi["email"], "duplicate-reply")
        CampaignRelationships(engine.store).triage(
            campaign, ravi["id"], review_status="triaged", outcome="meeting",
        )
        with pytest.raises(ValueError, match="Multiple existing sales leads"):
            RelationshipOperations(engine.store, sales).promote_reply(campaign, ravi["id"])
        assert engine.store._row(
            "SELECT COUNT(*) AS total FROM campaign_sales_links"
        )["total"] == 0
        assert sales.list_leads()[1] == 2
    finally:
        engine.close()


def test_contact_360_only_exposes_campaign_data_and_safe_projection(tmp_path: Path):
    engine, campaign, other, members = _seed(tmp_path)
    try:
        ravi = members["ravi@example.com"]
        ops = RelationshipOperations(engine.store, SalesTracker(engine.store))
        original = ops.contact_360(campaign, ravi["id"])
        assert original["messages"] == {"sent": 0, "received": 0}
        assert original["sales_lead"] is None
        assert original["tasks"]["open"] == 0
        assert "notes" not in original["contact"]
        with pytest.raises(KeyError):
            ops.contact_360(other, ravi["id"])

        _reply(engine, campaign, ravi["email"], "overview-reply")
        due = datetime.now(timezone.utc) + timedelta(days=1)
        task = CampaignRelationships(engine.store).create_task(
            campaign, title="Discuss meeting", due_at=due,
            campaign_contact_id=ravi["id"], assigned_to="Owner",
        )
        summary = ops.contact_360(campaign, ravi["id"])
        assert summary["messages"]["received"] == 1
        assert summary["latest_reply"]["subject"] == "Discuss an introduction"
        assert summary["tasks"]["open"] == 1
        assert summary["tasks"]["next"]["id"] == task["id"]
        assert "body" not in summary["latest_reply"]
        assert "raw_json" not in repr(summary)
    finally:
        engine.close()


def test_daily_action_center_filters_prioritises_and_deduplicates_leads(tmp_path: Path):
    engine, campaign, other, members = _seed(tmp_path)
    try:
        sales = SalesTracker(engine.store)
        reviews = CampaignRelationships(engine.store)
        ops = RelationshipOperations(engine.store, sales)
        now = datetime.now(timezone.utc)
        ravi = members["ravi@example.com"]
        anita = members["anita@example.com"]
        _reply(engine, campaign, ravi["email"], "action-ravi")
        _reply(engine, campaign, anita["email"], "action-anita")
        reviews.triage(campaign, ravi["id"], review_status="triaged", outcome="positive")
        sales_lead = ops.promote_reply(campaign, ravi["id"])
        assert sales_lead["created"]
        reviews.create_task(
            campaign, title="Past due high priority", due_at=now - timedelta(days=2),
            campaign_contact_id=ravi["id"], priority="high",
        )
        reviews.create_task(
            campaign, title="Future call", due_at=now + timedelta(days=3),
            campaign_contact_id=anita["id"],
        )
        # Do not double count the same sales lead linked to another campaign.
        duplicate_member, _ = engine.store.add_contact_to_campaign(other, ravi["contact_id"])
        _reply(engine, other, ravi["email"], "action-ravi-other")
        reviews.triage(other, duplicate_member, review_status="triaged", outcome="positive")
        ops.promote_reply(other, duplicate_member)
        report = ops.action_center(campaign, now=now)
        assert report["counts"] == {
            "overdue_task": 1, "reply_review": 1, "sales_attention": 1
        }
        assert report["total"] == 3
        assert [x["action_type"] for x in report["items"]] == [
            "overdue_task", "reply_review", "sales_attention"
        ]
        assert "body" not in repr(report)
        assert ops.action_center(other, now=now)["counts"] == {
            "overdue_task": 0, "reply_review": 0, "sales_attention": 1
        }
        for kind in ("overdue_task", "reply_review", "sales_attention"):
            filtered = ops.action_center(campaign, now=now, action_type=kind)
            assert filtered["total"] == 1
            assert filtered["items"][0]["action_type"] == kind
        assert ops.action_center(campaign, now=now, limit=1, offset=2)["items"][0]["action_type"] == "sales_attention"
        for bad in ({"action_type": "unknown"}, {"limit": 0}, {"limit": 101}, {"offset": -1}):
            with pytest.raises(ValueError):
                ops.action_center(campaign, now=now, **bad)
        assert sales.get_lead(sales_lead["lead"]["id"])["lead_status"] == "new"
    finally:
        engine.close()


def test_relationship_action_apis_enforce_auth_and_promote_once(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing",
        api_token="z" * 40, allowed_hosts=("testserver",),
    )
    auth = {"Authorization": "Bearer " + "z" * 40}
    with TestClient(create_app(settings)) as client:
        c = client.post("/api/v1/campaigns", headers=auth, json={"name": "Lead conversion"})
        assert c.status_code == 201
        campaign = c.json()["id"]
        contact = client.post(
            f"/api/v1/campaigns/{campaign}/contacts/manual", headers=auth,
            json={"full_name": "Ravi Shah", "email": "ravi@example.com"}
        )
        assert contact.status_code == 200
        member = contact.json()["id"]
        base = f"/api/v1/campaigns/{campaign}"
        paths = [f"/contacts/{member}/overview", "/actions"]
        for path in paths:
            assert client.get(base + path).status_code == 401
            assert client.get(base + path, headers=auth).status_code == 200
        promote_path = base + f"/contacts/{member}/promote"
        assert client.post(promote_path).status_code == 401
        assert client.post(promote_path, headers=auth, json={}).status_code == 400
        assert client.get(base + "/actions", headers=auth, params={"action_type": "bad"}).status_code == 422
        assert client.get(base + "/actions", headers=auth, params={"limit": 101}).status_code == 422
        assert client.get(base + f"/contacts/missing/overview", headers=auth).status_code == 404
        # Real local reply, explicit triage, then durable conversion.
        assert client.app.state.engine.store.record_reply(
            campaign,
            IncomingMessage(
                provider_message_id="api-reply-one", thread_id="",
                from_email="ravi@example.com",
                subject="Can we meet?", body_preview="Yes, interested",
            ),
        ) == [member]
        triage = client.patch(
            base + f"/replies/{member}/triage", headers=auth,
            json={"review_status": "triaged", "outcome": "positive"},
        )
        assert triage.status_code == 200, triage.text
        promoted = client.post(
            promote_path, headers={**auth, "Idempotency-Key": "promote-once"},
            json={},
        )
        assert promoted.status_code == 200, promoted.text
        lead_id = promoted.json()["lead"]["id"]
        assert promoted.json()["created"] is True
        duplicate = client.post(
            promote_path, headers={**auth, "Idempotency-Key": "promote-once"},
            json={},
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["lead"]["id"] == lead_id
        assert client.get("/api/v1/sales/leads", headers=auth).json()["total"] == 1
        assert client.get(base + f"/contacts/{member}/overview", headers=auth).json()["sales_lead"]["id"] == lead_id
        assert client.get(base + "/actions", headers=auth).json()["counts"]["sales_attention"] == 1


def test_sqlite_v10_upgrade_adds_sales_links_without_touching_old_records(tmp_path: Path):
    from offsetx_apollo_builder.outreach.schema import CRM_TABLES, SCHEMA_VERSION

    path = tmp_path / "existing.db"
    engine = OutreachEngine(path)
    campaign = engine.create_campaign(name="Persisted campaign")
    try:
        # Simulate an upgraded v10 database before campaign_sales_links exists.
        engine.store.connection.execute("DROP TABLE campaign_sales_links")
        engine.store.connection.execute("PRAGMA user_version = 10")
    finally:
        engine.close()

    reopened = OutreachEngine(path)
    try:
        assert SCHEMA_VERSION == 11
        assert len(CRM_TABLES) == 34
        assert reopened.store.connection.execute("PRAGMA user_version").fetchone()[0] == 11
        assert reopened.store.get_campaign(campaign)["name"] == "Persisted campaign"
        assert reopened.store.table_counts()["campaign_sales_links"] == 0
    finally:
        reopened.close()
