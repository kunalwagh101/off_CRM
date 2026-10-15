"""Campaign-scoped reply handling and durable human tasks.

All fixtures are local and no delivery provider is called.
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
from offsetx_apollo_builder.outreach.relationships import CampaignRelationships, TaskConflictError


def seeded(tmp_path):
    engine = OutreachEngine(tmp_path / "crm.db")
    cid = engine.create_campaign(name="Reply triage")
    other = engine.create_campaign(name="Other campaign")
    path = tmp_path / "contacts.csv"
    path.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Ravi Shah,ravi@example.com,Sample,Director,CBAM,Published a climate brief,https://example.com/a,Carbon reporting\n"
        "Anita Rao,anita@example.com,Sample,Lead,CBAM,Published supplier update,https://example.com/b,Audit evidence\n",
        encoding="utf-8",
    )
    assert engine.import_contacts(cid, path)["added"] == 2
    members = engine.store.campaign_contacts(cid)
    ravi = next(m for m in members if m["email"] == "ravi@example.com")
    return engine, cid, other, ravi


def test_reply_inbox_triage_is_campaign_scoped_and_preserves_send_stop(tmp_path):
    engine, cid, other, ravi = seeded(tmp_path)
    try:
        svc = CampaignRelationships(engine.store)
        assert svc.inbox(cid)["total"] == 0
        assert engine.store.record_reply(
            cid, IncomingMessage(
                provider_message_id="mail-reply-1", thread_id="",
                from_email="ravi@example.com",
                subject="Interested in meeting", body_preview="We can talk next week.",
            ),
        ) == [ravi["id"]]
        data = svc.inbox(cid)
        assert data["total"] == 1
        assert data["items"][0]["review_status"] == "unreviewed"
        assert data["items"][0]["reply_preview"] == "We can talk next week."
        assert svc.inbox(other)["total"] == 0
        assert svc.inbox(cid, review_status="triaged")["total"] == 0
        with pytest.raises(ValueError):
            svc.triage(cid, ravi["id"], review_status="done", outcome="")
        with pytest.raises(KeyError):
            svc.triage(other, ravi["id"], review_status="triaged", outcome="meeting")
        changed = svc.triage(
            cid, ravi["id"], review_status="triaged",
            outcome="meeting", note="Book a call.",
        )
        assert changed["outcome"] == "meeting"
        assert svc.inbox(cid, review_status="triaged", outcome="meeting")["total"] == 1
        assert svc.inbox(cid, review_status="unreviewed")["total"] == 0
        # Triage must not reset reply-stop or change a globally shared contact label.
        assert engine.store.get_campaign_contact(cid, ravi["id"])["status"] == "replied"
        assert engine.store.get_contact(ravi["contact_id"])["outcome_label"] == ""
        assert svc.inbox(other)["total"] == 0
    finally:
        engine.close()


def test_conversation_history_is_bounded_and_excludes_raw_provider_json(tmp_path):
    engine, cid, other, ravi = seeded(tmp_path)
    try:
        svc = CampaignRelationships(engine.store)
        for n in range(52):
            engine.store.connection.execute(
                """INSERT INTO messages
                   (id, campaign_contact_id, stage, direction, subject, body, raw_json, created_at)
                   VALUES (?, ?, 'initial', 'outbound', 'Hello', ?, ?, ?)""",
                (f"out-{n:03d}", ravi["id"], "a" * 2400,
                 '{"provider_secret": "MUST_NOT_RETURN"}',
                 (datetime.now(timezone.utc) + timedelta(seconds=n)).isoformat()),
            )
        first = svc.conversation(cid, ravi["id"], limit=25, offset=0)
        second = svc.conversation(cid, ravi["id"], limit=25, offset=25)
        assert first["total"] == 52
        assert len(first["items"]) == 25 and len(second["items"]) == 25
        assert {x["id"] for x in first["items"]}.isdisjoint(
            x["id"] for x in second["items"]
        )
        assert first["items"][0]["truncated"] == 1
        assert len(first["items"][0]["body_preview"]) == 2000
        assert "raw_json" not in first["items"][0]
        assert "MUST_NOT_RETURN" not in repr(first)
        with pytest.raises(KeyError):
            svc.conversation(other, ravi["id"])
    finally:
        engine.close()


def test_followup_tasks_due_assignment_revision_and_persistence(tmp_path):
    engine, cid, other, ravi = seeded(tmp_path)
    task_id = None
    try:
        svc = CampaignRelationships(engine.store)
        due = datetime.now(timezone.utc) + timedelta(days=1)
        task = svc.create_task(
            cid, title="Call Ravi", due_at=due,
            campaign_contact_id=ravi["id"], assigned_to="Anita",
            priority="high", description="Discuss an audit.",
        )
        task_id = task["id"]
        assert task["revision"] == 1 and task["status"] == "open"
        assert svc.list_tasks(cid)["total"] == 1
        assert svc.list_tasks(other)["total"] == 0
        assert svc.list_tasks(cid, overdue_only=True)["total"] == 0
        with pytest.raises(KeyError):
            svc.create_task(other, title="Bad", due_at=due, campaign_contact_id=ravi["id"])
        with pytest.raises(KeyError):
            svc.update_task(other, task_id, revision=1, status="done")
        with pytest.raises(TaskConflictError):
            svc.update_task(cid, task_id, revision=2, status="done")
        done = svc.update_task(cid, task_id, revision=1, status="done")
        assert done["revision"] == 2 and done["status"] == "done"
        assert done["completed_at"]
        assert svc.list_tasks(cid, status="open")["total"] == 0
        assert svc.list_tasks(cid, status="done")["total"] == 1
        reopened = svc.update_task(cid, task_id, revision=2, status="open")
        assert reopened["status"] == "open" and reopened["completed_at"] is None
        assert reopened["revision"] == 3
        with pytest.raises(TaskConflictError):
            svc.update_task(cid, task_id, revision=1, title="Overwrite")
        assert engine.store.get_campaign_contact(cid, ravi["id"])["status"] == "new"
        assert engine.store.list_events(cid)[1] >= 3
    finally:
        engine.close()

    # Existing SQLite file must preserve new task state after cold restart.
    fresh = OutreachEngine(tmp_path / "crm.db")
    try:
        svc = CampaignRelationships(fresh.store)
        assert svc.list_tasks(cid)["total"] == 1
        assert svc.list_tasks(cid)["items"][0]["id"] == task_id
        assert svc.list_tasks(cid)["items"][0]["revision"] == 3
    finally:
        fresh.close()



def test_existing_sqlite_crm_receives_additive_relationship_tables(tmp_path):
    """Simulate a version-nine file with no relationship tables, then reopen."""
    from offsetx_apollo_builder.outreach.schema import CRM_TABLES, SCHEMA_VERSION

    engine = OutreachEngine(tmp_path / "upgrade.db")
    cid = engine.create_campaign(name="Pre-upgrade campaign")
    try:
        engine.store.connection.execute("DROP TABLE campaign_followup_tasks")
        engine.store.connection.execute("DROP TABLE campaign_reply_triage")
        engine.store.connection.execute("PRAGMA user_version = 9")
    finally:
        engine.close()

    reopened = OutreachEngine(tmp_path / "upgrade.db")
    try:
        assert SCHEMA_VERSION == 11
        assert len(CRM_TABLES) == 34
        assert reopened.store.connection.execute("PRAGMA user_version").fetchone()[0] == 10
        assert reopened.store.get_campaign(cid)["name"] == "Pre-upgrade campaign"
        tasks = CampaignRelationships(reopened.store)
        task = tasks.create_task(
            cid, title="Call customer",
            due_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        assert task["status"] == "open"
        assert reopened.store.table_counts()["campaign_followup_tasks"] == 1
        assert reopened.store.table_counts()["campaign_reply_triage"] == 0
    finally:
        reopened.close()


def test_relationship_apis_auth_validation_and_conflict(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing", api_token="z" * 40,
        allowed_hosts=("testserver",),
    )
    auth = {"Authorization": "Bearer " + "z" * 40}
    with TestClient(create_app(settings)) as client:
        campaign = client.post(
            "/api/v1/campaigns", headers=auth, json={"name": "Worklist"}
        )
        assert campaign.status_code == 201, campaign.text
        cid = campaign.json()["id"]
        root = f"/api/v1/campaigns/{cid}"
        for path in ("/replies/inbox", "/followups"):
            assert client.get(root + path).status_code == 401
        assert client.get(root + "/replies/inbox", headers=auth).json()["total"] == 0
        bad = client.post(root + "/followups", headers=auth, json={
            "title": "Bad date", "due_at": "2026-10-14T12:00:00"
        })
        assert bad.status_code == 422
        created = client.post(root + "/followups", headers={**auth, "Idempotency-Key": "followup-test-key"}, json={
            "title": "Contact legal team", "due_at": "2026-10-25T12:00:00+05:30",
            "assigned_to": "Team lead", "priority": "high"
        })
        assert created.status_code == 201, created.text
        task = created.json()
        replay = client.post(root + "/followups", headers={**auth, "Idempotency-Key": "followup-test-key"}, json={
            "title": "Contact legal team", "due_at": "2026-10-25T12:00:00+05:30",
            "assigned_to": "Team lead", "priority": "high"
        })
        assert replay.status_code in (200, 201), replay.text
        assert replay.json()["id"] == task["id"]
        assert client.get(root + "/followups", headers=auth).json()["total"] == 1
        assert client.patch(
            root + "/followups/" + task["id"], headers=auth,
            json={"revision": 1, "status": "done"}
        ).status_code == 200
        stale = client.patch(
            root + "/followups/" + task["id"], headers=auth,
            json={"revision": 1, "status": "open"}
        )
        assert stale.status_code == 409
        assert client.get(root + "/followups", params={"status": "done"}, headers=auth).json()["total"] == 1
        assert client.get(root + "/replies/inbox", params={"review_status": "unknown"}, headers=auth).status_code == 422
        assert client.post(root + "/followups", headers=auth, json={
            "title": "Unknown person", "due_at": "2026-10-25T12:00:00+05:30",
            "campaign_contact_id": "foreign-contact"
        }).status_code == 404
