from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from offsetx_apollo_builder.outreach.engine import OutreachEngine, add_working_days
from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider


HEADERS = (
    "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
)


def _write_contacts(path, rows: str) -> None:
    path.write_text(HEADERS + rows, encoding="utf-8")


def test_sequence_send_daily_cap_and_reply_stop(tmp_path):
    contacts = tmp_path / "contacts.csv"
    _write_contacts(
        contacts,
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff\n"
        "Ravi Shah,ravi@example.com,Audit Works,Partner,MRV,Published a verification methods note,https://example.com/ravi,Verification evidence handoff\n",
    )
    engine = OutreachEngine(tmp_path / "outreach.db")
    campaign_id = engine.create_campaign(name="Pilot", daily_send_limit=1)
    imported = engine.import_contacts(campaign_id, contacts)
    assert imported["added"] == 2

    original_variants = {
        item["email"]: item["variant_id"]
        for item in engine.store.campaign_contacts(campaign_id)
    }
    repeated = engine.import_contacts(campaign_id, contacts)
    assert repeated["updated_or_existing"] == 2
    assert original_variants == {
        item["email"]: item["variant_id"]
        for item in engine.store.campaign_contacts(campaign_id)
    }

    generated = engine.generate_drafts(campaign_id)
    assert generated == {"generated": 6, "blocked": 0, "failures": []}
    assert engine.approve_drafts(campaign_id, stages=["initial"]) == {
        "approved": 2,
        "blocked": 0,
    }
    mail = LocalOutboxProvider(tmp_path / "mail")
    now = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
    first = engine.run_due(
        campaign_id,
        mail_provider=mail,
        own_email="kunal@example.com",
        now=now,
    )
    assert first["sent_count"] == 1
    second = engine.run_due(
        campaign_id,
        mail_provider=mail,
        own_email="kunal@example.com",
        now=now,
    )
    assert second["sent_count"] == 0
    assert len(list((tmp_path / "mail" / "outbox").glob("*.json"))) == 1

    sent_contact = next(
        item for item in engine.store.campaign_contacts(campaign_id) if item["sent_count"]
    )
    outgoing = engine.store.last_outgoing(sent_contact["id"])
    assert outgoing
    (tmp_path / "mail" / "inbox" / "reply.json").write_text(
        json.dumps(
            {
                "id": "reply-1",
                "thread_id": outgoing["thread_id"],
                "from": sent_contact["email"],
                "subject": "Re: evidence",
                "body": "Happy to discuss.",
                "received_at": "2026-07-20T05:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    synced = engine.sync_replies(
        campaign_id,
        mail_provider=mail,
        own_email="kunal@example.com",
        now=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
    )
    assert synced == {"scanned": 1, "matched": 1}
    updated = engine.store.get_campaign_contact(campaign_id, sent_contact["id"])
    assert updated["status"] == "replied"
    assert updated["next_action_at"] is None
    drafts, _ = engine.store.list_drafts(campaign_id, limit=20)
    reply_drafts = [d for d in drafts if d["campaign_contact_id"] == sent_contact["id"]]
    assert {d["approval_status"] for d in reply_drafts if not d["sent_at"]} == {
        "cancelled_reply"
    }
    assert engine.generate_drafts(
        campaign_id, campaign_contact_ids=[sent_contact["id"]]
    )["generated"] == 0
    engine.close()


def test_working_days_and_spreadsheet_formula_safety(tmp_path):
    monday = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
    friday = add_working_days(monday, 4, "Asia/Kolkata")
    assert friday.date().isoformat() == "2026-07-17"

    contacts = tmp_path / "formula.csv"
    _write_contacts(
        contacts,
        "Formula Person,formula@example.com,=HYPERLINK(\"https://bad.example\"),Lead,ESG,Published a climate note,https://example.com/hook,Data handoff\n",
    )
    engine = OutreachEngine(tmp_path / "outreach.db")
    campaign_id = engine.create_campaign(name="Export")
    engine.import_contacts(campaign_id, contacts)
    destination = engine.export_crm(campaign_id, tmp_path / "crm.csv")
    with destination.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["Company"].startswith("'=")
    assert list(row)[:6] == [
        "Checkbox",
        "Outreach Date",
        "POI Name",
        "POI Response",
        "Follow-Up",
        "Meeting Transcript",
    ]
    engine.close()
