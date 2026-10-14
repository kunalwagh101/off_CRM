"""Product feature regressions: audience controls, readiness and activity."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _settings(tmp: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp / "outreach.db",
        data_dir=tmp / "data",
        export_dir=tmp / "exports",
        frontend_dist=tmp / "missing-dist",
        api_token="x" * 40,
        allowed_hosts=("testserver",),
    )


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer " + "x" * 40}


def _campaign(client: TestClient, name: str) -> str:
    response = client.post("/api/v1/campaigns", headers=_headers(), json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _manual(client: TestClient, campaign: str, email: str, name: str = "One Person"):
    return client.post(
        f"/api/v1/campaigns/{campaign}/contacts/manual", headers=_headers(),
        json={
            "full_name": name,
            "email": email,
            "company": "Sample Company",
            "category": "Sustainability / ESG / Climate",
            "public_hook": "Published a supplier emissions brief",
            "hook_source": "https://example.com/brief",
        },
    )


def test_manual_audience_entry_deduplicates_and_never_mutates_existing_profile(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        first = _campaign(client, "First campaign")
        second = _campaign(client, "Second campaign")
        url = f"/api/v1/campaigns/{first}/contacts/manual"
        assert client.post(url, json={"full_name": "No Auth", "email": "na@example.com"}).status_code == 401
        for bad in (
            {"full_name": "", "email": "valid@example.com"},
            {"full_name": "Name", "email": "not-an-email"},
            {"full_name": "Name", "email": "valid@example.com", "ignored": "blocked"},
        ):
            assert client.post(url, headers=_headers(), json=bad).status_code == 422
        created = _manual(client, first, "one@example.com")
        assert created.status_code == 200, created.text
        assert created.json()["added"] is True
        assert created.json()["status"] == "new"
        assert _manual(client, first, "ONE@example.com").json()["added"] is False

        # Linking an existing global record must preserve that profile in both
        # campaigns; changing name in a second-campaign request cannot rewrite it.
        linked = _manual(client, second, "one@example.com", name="Do not overwrite")
        assert linked.status_code == 200
        assert linked.json()["added"] is True
        assert linked.json()["reused_contact"] is True
        orig = client.get(
            f"/api/v1/campaigns/{first}/contacts", headers=_headers()
        ).json()
        assert orig["total"] == 1
        assert orig["items"][0]["full_name"] == "One Person"
        assert client.get(
            f"/api/v1/campaigns/{first}/drafts", headers=_headers()
        ).json()["total"] == 0
        assert client.get(
            f"/api/v1/campaigns/{first}/queue", headers=_headers()
        ).json()["counts"]["ready"] == 0

    with TestClient(create_app(settings)) as restarted:
        result = restarted.get(f"/api/v1/campaigns/{first}/contacts", headers=_headers())
        assert result.status_code == 200
        assert result.json()["total"] == 1


def test_bulk_selection_mark_stop_atomicity_and_terminal_protection(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        cid = _campaign(client, "Bulk lifecycle")
        other = _campaign(client, "Different campaign")
        first = _manual(client, cid, "one@example.com").json()
        second = _manual(client, cid, "two@example.com", "Two Person").json()
        foreign = _manual(client, other, "foreign@example.com").json()
        endpoint = f"/api/v1/campaigns/{cid}/contacts/bulk"
        ids = [first["id"], second["id"]]

        assert client.post(endpoint, json={"contact_ids": ids, "action": "stop"}).status_code == 401
        for body in (
            {"contact_ids": [], "action": "mark"},
            {"contact_ids": [first["id"], first["id"]], "action": "mark"},
            {"contact_ids": ids, "action": "delete"},
        ):
            assert client.post(endpoint, headers=_headers(), json=body).status_code == 422

        # No partial write if even one ID belongs to a different campaign.
        foreign_action = client.post(endpoint, headers=_headers(), json={
            "contact_ids": [first["id"], foreign["id"]], "action": "mark"
        })
        assert foreign_action.status_code == 404, foreign_action.text
        marked_check = client.get(
            f"/api/v1/campaigns/{cid}/contacts", headers=_headers(),
            params={"selected_only": True},
        ).json()
        assert marked_check["total"] == 0

        marked = client.post(endpoint, headers=_headers(), json={"contact_ids": ids, "action": "mark"})
        assert marked.status_code == 200, marked.text
        assert marked.json()["changed"] == 2
        assert client.post(endpoint, headers=_headers(), json={
            "contact_ids": ids, "action": "mark"
        }).json()["changed"] == 0
        assert client.get(
            f"/api/v1/campaigns/{cid}/contacts", headers=_headers(),
            params={"selected_only": True}
        ).json()["total"] == 2
        assert client.post(endpoint, headers=_headers(), json={
            "contact_ids": [first["id"]], "action": "unmark"
        }).json()["changed"] == 1

        assert client.patch(
            f"/api/v1/campaigns/{cid}/contacts/{second['id']}",
            headers=_headers(), json={"status": "replied"},
        ).status_code == 200
        stopped = client.post(endpoint, headers=_headers(), json={
            "contact_ids": ids, "action": "stop"
        })
        assert stopped.status_code == 200
        assert stopped.json()["changed"] == 1
        rows = client.get(f"/api/v1/campaigns/{cid}/contacts", headers=_headers()).json()["items"]
        by_email = {row["email"]: row for row in rows}
        assert by_email["one@example.com"]["status"] == "stopped"
        assert by_email["two@example.com"]["status"] == "replied"
        assert client.get(f"/api/v1/campaigns/{cid}/queue", headers=_headers()).json()["counts"]["ready"] == 0


def test_launch_readiness_identifies_gates_without_calling_send(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        cid = _campaign(client, "Local review")
        path = f"/api/v1/campaigns/{cid}/launch-readiness"
        assert client.get(path).status_code == 401
        empty = client.get(path, headers=_headers())
        assert empty.status_code == 200
        assert empty.json()["eligible_for_local_review"] is False
        assert {item["id"] for item in empty.json()["checks"]} == {
            "active", "audience", "approved_due", "daily_cap"
        }
        assert empty.json()["external_delivery_verified"] is False

        created = _manual(client, cid, "review@example.com")
        assert created.status_code == 200
        audience = client.get(path, headers=_headers()).json()
        assert audience["candidate_count"] == 0
        assert next(x for x in audience["checks"] if x["id"] == "audience")["passed"] is True

        contact_id = created.json()["id"]
        prepared = client.post(f"/api/v1/campaigns/{cid}/drafts/generate", headers=_headers(), json={
            "campaign_contact_ids": [contact_id], "stages": ["initial"]
        })
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["generated"] == 1
        drafts = client.get(f"/api/v1/campaigns/{cid}/drafts", headers=_headers()).json()["items"]
        assert client.post(
            f"/api/v1/campaigns/{cid}/drafts/approve", headers=_headers(),
            json={"draft_ids": [drafts[0]["id"]], "stages": []},
        ).status_code == 200
        ready = client.get(path, headers=_headers()).json()
        assert ready["candidate_count"] == 1
        assert ready["eligible_for_local_review"] is True
        assert ready["external_delivery_verified"] is False

        assert client.patch(
            f"/api/v1/campaigns/{cid}", headers=_headers(), json={"status": "paused"}
        ).status_code == 200
        paused = client.get(path, headers=_headers()).json()
        assert paused["eligible_for_local_review"] is False
        assert next(x for x in paused["checks"] if x["id"] == "active")["passed"] is False


def test_event_timeline_facets_filters_pagination_and_authentication(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        cid = _campaign(client, "Activity")
        root = f"/api/v1/campaigns/{cid}/events"
        assert client.get(root).status_code == 401
        assert client.get(root + "/types").status_code == 401
        for index in range(56):
            changed = client.patch(
                f"/api/v1/campaigns/{cid}", headers=_headers(),
                json={"name": f"Activity {index}"},
            )
            assert changed.status_code == 200
        facets = client.get(root + "/types", headers=_headers())
        assert facets.status_code == 200, facets.text
        kinds = {row["event_type"]: row["count"] for row in facets.json()["items"]}
        assert kinds["campaign_updated"] == 56
        assert kinds["campaign_created"] == 1
        first = client.get(root, headers=_headers(), params={"limit": 50, "offset": 0})
        second = client.get(root, headers=_headers(), params={"limit": 50, "offset": 50})
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["total"] == 57
        assert len(first.json()["items"]) == 50
        assert len(second.json()["items"]) == 7
        assert set(x["id"] for x in first.json()["items"]).isdisjoint(
            x["id"] for x in second.json()["items"]
        )
        filtered = client.get(root, headers=_headers(), params={
            "event_type": "campaign_created"
        })
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["event_type"] == "campaign_created"
        assert client.get(root, headers=_headers(), params={
            "event_type": "missing"
        }).json()["total"] == 0
        assert client.get(root, headers=_headers(), params={
            "event_type": "a" * 101
        }).status_code == 422
