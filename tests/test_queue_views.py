"""Queue visibility and page-sized reads; no live mail provider is exercised."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.engine import OutreachEngine


def _contacts_csv(size: int) -> bytes:
    header = "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
    rows = [
        f"Person {index:03d},person{index}@example.com,Example,Analyst,CBAM,"
        f"Published briefing {index},https://example.com/{index},Evidence handoff\n"
        for index in range(size)
    ]
    return (header + "".join(rows)).encode("utf-8")


def _seed(tmp_path: Path, count: int = 211):
    engine = OutreachEngine(tmp_path / "crm.db")
    cid = engine.create_campaign(name="Large queued campaign")
    input_path = tmp_path / "contacts.csv"
    input_path.write_bytes(_contacts_csv(count))
    imported = engine.import_contacts(cid, input_path)
    assert imported["added"] == count
    items = engine.store.campaign_contacts(cid)
    assert len(items) == count
    return engine, cid, items


def test_queue_counts_come_from_every_contact_not_the_visible_page(tmp_path):
    engine, campaign, contacts = _seed(tmp_path)
    try:
        # A ready draft near the end; a reply on another late record.
        last = contacts[-1]
        assert engine.generate_drafts(
            campaign, campaign_contact_ids=[last["id"]], stages=["initial"]
        )["generated"] == 1
        assert engine.approve_drafts(campaign, stages=["initial"])["approved"] == 1
        engine.store.update_campaign_contact(
            campaign, contacts[-2]["id"], {"status": "replied"}
        )
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        first = engine.store.send_queue_view(campaign, now=now, limit=10, offset=0)
        assert len(first["items"]) == 10
        assert first["total"] == 211
        assert first["counts"] == {
            "all": 211, "ready": 1, "approval": 209, "replied": 1,
        }
        assert all("campaign_contact_id" in item for item in first["items"])
        last_page = engine.store.send_queue_view(
            campaign, now=now, limit=100, offset=200
        )
        assert last_page["total"] == 211
        assert len(last_page["items"]) == 11
        assert last_page["counts"] == first["counts"]
        assert set(item["campaign_contact_id"] for item in last_page["items"]).isdisjoint(
            item["campaign_contact_id"] for item in first["items"]
        )

        for view, expected in [("ready", 1), ("approval", 209), ("replied", 1)]:
            result = engine.store.send_queue_view(campaign, now=now, limit=50, view=view)
            assert result["total"] == expected
            assert result["counts"] == first["counts"]
        assert engine.store.send_queue_view(
            campaign, now=now, limit=100, offset=0, view="ready"
        )["items"][0]["campaign_contact_id"] == last["id"]

        future = (now + timedelta(days=2)).isoformat()
        engine.store.connection.execute(
            "UPDATE drafts SET scheduled_at = ? WHERE campaign_contact_id = ?",
            (future, last["id"]),
        )
        delayed = engine.store.send_queue_view(campaign, now=now, view="ready")
        assert delayed["counts"]["ready"] == 0
        assert delayed["total"] == 0
        assert engine.store.send_queue_view(campaign, now=now)["counts"]["approval"] == 209
    finally:
        engine.close()


def test_queue_rejects_invalid_limit_offset_and_view(tmp_path):
    engine, campaign, _ = _seed(tmp_path, 2)
    try:
        now = datetime.now(timezone.utc)
        for params in [
            {"view": "unknown"},
            {"limit": 0},
            {"limit": 201},
            {"offset": -1},
        ]:
            with pytest.raises(ValueError):
                engine.store.send_queue_view(campaign, now=now, **params)
    finally:
        engine.close()


def test_queue_api_requires_auth_and_returns_paged_counts(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing", api_token="q" * 40,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        auth = {"Authorization": "Bearer " + "q" * 40}
        create = client.post(
            "/api/v1/campaigns", json={"name": "Queue pages"}, headers=auth
        )
        assert create.status_code == 201
        campaign = create.json()["id"]
        url = f"/api/v1/campaigns/{campaign}/queue"
        assert client.get(url).status_code == 401
        uploaded = client.post(
            f"/api/v1/campaigns/{campaign}/contacts/import",
            files={"file": ("contacts.csv", _contacts_csv(3), "text/csv")},
            headers=auth,
        )
        assert uploaded.status_code == 200
        first = client.get(url, params={"limit": 2, "offset": 0}, headers=auth)
        assert first.status_code == 200
        assert first.json()["total"] == 3
        assert first.json()["limit"] == 2
        assert len(first.json()["items"]) == 2
        assert first.json()["counts"]["approval"] == 3
        second = client.get(url, params={"limit": 2, "offset": 2}, headers=auth)
        assert len(second.json()["items"]) == 1
        assert second.json()["counts"] == first.json()["counts"]
        filtered = client.get(url, params={"view": "ready"}, headers=auth)
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 0
        assert filtered.json()["counts"]["approval"] == 3
        for params in [
            {"limit": 0}, {"limit": 201}, {"offset": -1}, {"view": "bad"},
        ]:
            assert client.get(url, params=params, headers=auth).status_code == 422
