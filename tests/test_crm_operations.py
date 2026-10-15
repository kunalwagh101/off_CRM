"""Acceptance tests for F-06.19, F-06.20 and F-06.21.

All tests use real local CRM tables and no provider/network calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.crm_operations import CRMOperations
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.relationships import CampaignRelationships
from offsetx_apollo_builder.outreach.sales import SalesTracker


def seed(tmp_path: Path):
    engine = OutreachEngine(tmp_path / "operations.db")
    first = engine.create_campaign(name="Alpha outreach")
    second = engine.create_campaign(name="Beta outreach")
    alice = engine.store.upsert_contact(ContactInput(
        full_name="Alice Stone", email="alice@example.com",
        company="Example Ltd", title="Director",
    ))
    bob = engine.store.upsert_contact(ContactInput(
        full_name="Bob Jones", email="bob@example.com",
        company="", title="",
    ))
    unused = engine.store.upsert_contact(ContactInput(
        full_name="Cara Jones", email="cara@example.com",
        company="Example Ltd", title="Manager",
    ))
    a, _ = engine.store.add_contact_to_campaign(first, alice)
    b, _ = engine.store.add_contact_to_campaign(first, bob)
    engine.store.add_contact_to_campaign(second, alice)
    sales = SalesTracker(engine.store)
    sales.create_lead({"lead_name": "Alice", "email": "ALICE@example.com"})
    engine.store.connection.execute(
        """INSERT INTO messages (id, campaign_contact_id, stage, direction, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("out1", a, "initial", "outbound", "2026-10-10T10:00:00+00:00"),
    )
    engine.store.connection.execute(
        """INSERT INTO messages (id, campaign_contact_id, stage, direction, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("out2", a, "followup1", "outbound", "2026-10-11T10:00:00+00:00"),
    )
    engine.store.connection.execute(
        """INSERT INTO messages (id, campaign_contact_id, stage, direction, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("in1", a, "initial", "inbound", "2026-10-11T10:01:00+00:00"),
    )
    engine.store.connection.execute(
        """INSERT INTO messages (id, campaign_contact_id, stage, direction, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("in2", a, "initial", "inbound", "2026-10-11T10:02:00+00:00"),
    )
    engine.store.connection.execute(
        """INSERT INTO campaign_reply_triage
            (campaign_contact_id, review_status, outcome, note, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (a, "triaged", "positive", "", "2026-10-12T10:00:00+00:00"),
    )
    rel = CampaignRelationships(engine.store)
    overdue = rel.create_task(
        first, title="Contact Alice", assigned_to="  Ravi  ",
        due_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        campaign_contact_id=a,
    )
    done = rel.create_task(
        second, title="Review proposal", assigned_to="ravi",
        due_at=datetime(2035, 1, 1, tzinfo=timezone.utc),
    )
    rel.update_task(second, done["id"], revision=done["revision"], status="done")
    rel.create_task(
        first, title="Unassigned task",
        due_at=datetime(2035, 1, 1, tzinfo=timezone.utc),
        campaign_contact_id=b,
    )
    return engine, sales, first, second, alice, unused, overdue


def test_quality_filters_exact_saved_records_and_no_private_fields(tmp_path):
    engine, sales, first, second, alice, unused, _ = seed(tmp_path)
    try:
        service = CRMOperations(engine.store, sales)
        missing = service.contact_quality(issue="missing_company")
        assert missing["total"] == 1
        assert missing["items"][0]["full_name"] == "Bob Jones"
        assert "missing_title" in missing["items"][0]["issues"]
        overlap = service.contact_quality(issue="sales_overlap")
        assert overlap["total"] == 1
        assert overlap["items"][0]["id"] == alice
        # Two memberships can share a creation timestamp; their UUIDs do not
        # encode insertion order. Assert pair integrity and stable selection,
        # not which arbitrary UUID sorts first.
        picked = overlap["items"][0]
        assert picked["campaign_id"] in {first, second}
        assert picked["campaign_contact_id"]
        linked = engine.store.get_campaign_contact(
            picked["campaign_id"], picked["campaign_contact_id"]
        )
        assert linked["contact_id"] == alice
        again = service.contact_quality(issue="sales_overlap")["items"][0]
        assert (again["campaign_id"], again["campaign_contact_id"]) == (
            picked["campaign_id"], picked["campaign_contact_id"]
        )
        assert "notes" not in overlap["items"][0]
        assert "source_json" not in overlap["items"][0]
        orphan = service.contact_quality(issue="not_in_campaign")
        assert orphan["total"] == 1
        assert orphan["items"][0]["id"] == unused
        assert service.contact_quality(issue="all", limit=1, offset=1)["total"] == 3
        assert service.contact_quality(issue="all", search="%%")["total"] == 0
        assert service.contact_quality(issue="all", search="a_")["total"] == 0
        for value in ("dedupe", "", "unknown"):
            with pytest.raises(ValueError):
                service.contact_quality(issue=value)
        with pytest.raises(ValueError):
            service.contact_quality(limit=101)
    finally:
        engine.close()


def test_comparison_counts_unique_memberships_not_message_fanout(tmp_path):
    engine, sales, first, second, _, _, _ = seed(tmp_path)
    try:
        service = CRMOperations(engine.store, sales)
        all_rows = service.campaign_comparison()
        assert all_rows["total"] == 2
        alpha = next(x for x in all_rows["items"] if x["campaign_id"] == first)
        beta = next(x for x in all_rows["items"] if x["campaign_id"] == second)
        assert alpha["contacts"] == 2
        assert alpha["contacted"] == 1
        assert alpha["inbound_contacts"] == 1
        assert alpha["replied_after_outreach"] == 1
        assert alpha["reply_rate_percent"] == 100.0
        assert alpha["qualified"] == 1
        assert beta["reply_rate_percent"] is None
        assert service.campaign_comparison(search="alpha")["total"] == 1
        assert service.campaign_comparison(search="%%")["total"] == 0
        assert service.campaign_comparison(limit=1, offset=1)["total"] == 2
        with pytest.raises(ValueError):
            service.campaign_comparison(offset=-1)
    finally:
        engine.close()


def test_followup_performance_groups_labels_and_preserves_global_totals(tmp_path):
    engine, sales, first, second, _, _, _ = seed(tmp_path)
    try:
        service = CRMOperations(engine.store, sales)
        result = service.followup_performance(limit=1)
        assert result["total"] == 2
        assert result["overall"] == {
            "tasks": 3, "open": 2, "done": 1, "overdue": 1, "on_time": 1,
        }
        other_page = service.followup_performance(limit=1, offset=1)
        assert other_page["overall"] == result["overall"]
        alpha = service.followup_performance(campaign_id=first)
        assert alpha["overall"]["tasks"] == 2
        assert alpha["overall"]["overdue"] == 1
        assert alpha["overall"]["done"] == 0
        beta = service.followup_performance(campaign_id=second)
        assert beta["overall"]["done"] == 1
        assert beta["total"] == 1
        with pytest.raises(KeyError):
            service.followup_performance(campaign_id="other")
        with pytest.raises(ValueError):
            service.followup_performance(limit=0)
    finally:
        engine.close()


def test_crm_operations_endpoints_require_auth_and_validate_filters(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "none",
        api_token="o" * 40, allowed_hosts=("testserver",),
    )
    auth = {"Authorization": "Bearer " + "o" * 40}
    with TestClient(create_app(settings)) as client:
        first = client.post(
            "/api/v1/campaigns", headers=auth, json={"name": "Compare me"},
        ).json()["id"]
        for path in ("/crm/quality", "/crm/compare", "/crm/followup-performance"):
            assert client.get("/api/v1" + path).status_code == 401
            ok = client.get("/api/v1" + path, headers=auth)
            assert ok.status_code == 200, ok.text
        assert client.get("/api/v1/crm/quality", headers=auth,
                          params={"issue": "delete"}).status_code == 422
        assert client.get("/api/v1/crm/compare", headers=auth,
                          params={"limit": 101}).status_code == 422
        assert client.get("/api/v1/crm/followup-performance", headers=auth,
                          params={"offset": -1}).status_code == 422
        assert client.get("/api/v1/crm/followup-performance", headers=auth,
                          params={"campaign_id": first}).status_code == 200
        assert client.get("/api/v1/crm/followup-performance", headers=auth,
                          params={"campaign_id": "nonexistent"}).status_code == 404
