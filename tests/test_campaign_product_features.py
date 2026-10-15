"""Product-level campaign settings, safe reuse and operational performance."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _settings(tmp: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp / "crm.db",
        data_dir=tmp / "data",
        export_dir=tmp / "exports",
        frontend_dist=tmp / "missing",
        api_token="x" * 40,
        allowed_hosts=("testserver",),
    )


def _make_client_campaign(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/campaigns", headers=headers, json={
        "name": "Original", "daily_send_limit": 12,
        "timezone": "Asia/Kolkata",
        "followup1_working_days": 3, "followup2_working_days": 8,
        "send_window_start": "08:30", "send_window_end": "18:15",
        "send_weekdays": [0, 2, 4], "experiment_hypothesis": "Specific hook",
        "experiment_min_sample": 15, "control_variant": "B",
        "approval_mode": "each_message", "variants": ["A", "B"]
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_campaign_settings_save_and_timezone_is_rejected_before_database_write(tmp_path: Path):
    settings = _settings(tmp_path)
    headers = {"Authorization": "Bearer " + "x" * 40}
    with TestClient(create_app(settings)) as client:
        cid = _make_client_campaign(client, headers)
        endpoint = f"/api/v1/campaigns/{cid}"
        assert client.patch(endpoint, json={"name": "Unauthorised"}).status_code == 401
        good = client.patch(endpoint, headers=headers, json={
            "name": "Production sequence",
            "daily_send_limit": 7,
            "timezone": "Europe/London",
            "send_weekdays": [0, 1, 2, 3],
            "send_window_start": "10:00",
            "send_window_end": "16:30",
            "approval_mode": "whole_sequence",
            "experiment_hypothesis": "Public evidence converts",
            "experiment_min_sample": 25,
            "followup1_working_days": 2,
            "followup2_working_days": 5,
        })
        assert good.status_code == 200, good.text
        fields = good.json()
        assert fields["name"] == "Production sequence"
        assert fields["timezone"] == "Europe/London"
        assert fields["send_weekdays"] == [0, 1, 2, 3]
        assert fields["approval_mode"] == "whole_sequence"
        bad = client.patch(endpoint, headers=headers, json={"timezone": "No/Such_Zone"})
        assert bad.status_code == 422
        after = client.get(endpoint, headers=headers).json()
        assert after["timezone"] == "Europe/London"
        assert client.patch(endpoint, headers=headers, json={"kind": "image"}).status_code == 422
        assert client.patch(endpoint, headers=headers, json={"control_variant": "Z"}).status_code == 422

    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(endpoint, headers=headers).json()["name"] == "Production sequence"


def test_configuration_clone_is_paused_empty_idempotent_and_preserves_source(tmp_path: Path):
    settings = _settings(tmp_path)
    headers = {"Authorization": "Bearer " + "x" * 40}
    with TestClient(create_app(settings)) as client:
        source_id = _make_client_campaign(client, headers)
        csv = (
            "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
            "Asha Rao,asha@example.com,Example,Lead,CBAM,Published report,https://example.com,Supplier evidence handoff\n"
        ).encode()
        imported = client.post(
            f"/api/v1/campaigns/{source_id}/contacts/import",
            headers=headers, files={"file": ("contacts.csv", csv, "text/csv")},
        )
        assert imported.status_code == 200, imported.text
        headers["Idempotency-Key"] = "clone-key-unique-123"
        clone = client.post(
            f"/api/v1/campaigns/{source_id}/clone", headers=headers,
            json={"name": "Copy, intentionally paused"},
        )
        assert clone.status_code == 201, clone.text
        target = clone.json()
        assert target["id"] != source_id
        assert target["status"] == "paused"
        for field in (
            "kind", "timezone", "daily_send_limit",
            "followup1_working_days", "followup2_working_days", "approval_mode",
            "variants", "send_window_start", "send_window_end", "send_weekdays",
            "experiment_hypothesis", "experiment_min_sample", "control_variant"
        ):
            original = client.get(f"/api/v1/campaigns/{source_id}", headers=headers).json()
            assert target[field] == original[field], field
        assert client.get(
            f"/api/v1/campaigns/{target['id']}/contacts", headers=headers
        ).json()["total"] == 0
        assert client.get(
            f"/api/v1/campaigns/{target['id']}/queue", headers=headers
        ).json()["total"] == 0
        replay = client.post(
            f"/api/v1/campaigns/{source_id}/clone", headers=headers,
            json={"name": "Copy, intentionally paused"},
        )
        assert replay.status_code in (200, 201), replay.text
        assert replay.json()["id"] == target["id"]
        assert client.get(f"/api/v1/campaigns/{source_id}", headers=headers).json()["status"] == "active"
        assert client.post(
            f"/api/v1/campaigns/{source_id}/clone", headers=headers,
            json={"name": "X", "copy_contacts": True}
        ).status_code == 422
        assert client.post(f"/api/v1/campaigns/no-such-id/clone", headers={
            "Authorization": "Bearer " + "x" * 40
        }, json={"name": "No"}).status_code == 404
        assert client.post(
            f"/api/v1/campaigns/{source_id}/clone", json={"name": "Unauthorised"}
        ).status_code == 401

    with TestClient(create_app(settings)) as restarted:
        restored = restarted.get(
            f"/api/v1/campaigns/{target['id']}",
            headers={"Authorization": "Bearer " + "x" * 40},
        )
        assert restored.status_code == 200
        assert restored.json()["status"] == "paused"


def test_performance_denominator_is_unique_contacted_and_excludes_unsent_replies(tmp_path: Path):
    settings = _settings(tmp_path)
    headers = {"Authorization": "Bearer " + "x" * 40}
    with TestClient(create_app(settings)) as client:
        cid = _make_client_campaign(client, headers)
        csv = (
            "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
            "One,one@example.com,Company,Role,CBAM,Published a supplier emissions brief,https://example.com,Supplier evidence handoff\n"
            "Two,two@example.com,Company,Role,CBAM,Published a supplier emissions brief,https://example.com,Supplier evidence handoff\n"
            "Three,three@example.com,Company,Role,CBAM,Published a supplier emissions brief,https://example.com,Supplier evidence handoff\n"
        ).encode()
        assert client.post(
            f"/api/v1/campaigns/{cid}/contacts/import",
            headers=headers, files={"file": ("contacts.csv", csv, "text/csv")}
        ).status_code == 200
        performance_url = f"/api/v1/campaigns/{cid}/performance"
        assert client.get(performance_url).status_code == 401
        initial = client.get(performance_url, headers=headers).json()
        assert initial["contacts"] == 3
        assert initial["contacted"] == 0
        assert initial["messages_sent"] == 0
        assert initial["reply_rate"] == 0
        records = client.get(f"/api/v1/campaigns/{cid}/contacts", headers=headers).json()["items"]
        # Manual reply entry for an unsent contact must not create a fake >100% rate.
        assert client.patch(
            f"/api/v1/campaigns/{cid}/contacts/{records[0]['id']}",
            headers=headers, json={"status": "replied"}
        ).status_code == 200
        after = client.get(performance_url, headers=headers).json()
        assert after["replied"] == 1
        assert after["replied_contacted"] == 0
        assert after["contacted"] == 0
        assert after["reply_rate"] == 0.0
        assert after["awaiting_first_contact"] == 3
        assert after["reply_rate_denominator"] == "unique_contacts_sent"

        # Exercise an actual local-outbox send through the application, then
        # verify that only the replied recipient who was sent mail enters
        # the rate's numerator.
        prepared = client.post(
            f"/api/v1/campaigns/{cid}/drafts/generate",
            headers=headers,
            json={"campaign_contact_ids": [records[1]["id"]], "stages": ["initial"]},
        )
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["generated"] == 1
        drafts = client.get(f"/api/v1/campaigns/{cid}/drafts", headers=headers).json()["items"]
        chosen = next(row for row in drafts if row["campaign_contact_id"] == records[1]["id"])
        assert client.post(
            f"/api/v1/campaigns/{cid}/drafts/approve",
            headers=headers,
            json={"draft_ids": [chosen["id"]], "stages": []}
        ).status_code == 200
        assert client.patch(
            f"/api/v1/campaigns/{cid}", headers=headers,
            json={"send_weekdays": [0, 1, 2, 3, 4, 5, 6],
                  "send_window_start": "00:00", "send_window_end": "00:00"}
        ).status_code == 200
        sent = client.post(
            f"/api/v1/campaigns/{cid}/send", headers=headers,
            json={"mode": "local", "confirmation": "",
                  "sync_replies_first": False, "max_messages": 1}
        )
        assert sent.status_code == 200, sent.text
        assert sent.json()["sent_count"] == 1
        after_send = client.get(performance_url, headers=headers).json()
        assert after_send["messages_sent"] == 1
        assert after_send["contacted"] == 1
        assert after_send["replied_contacted"] == 0
        assert after_send["reply_rate"] == 0
        assert client.patch(
            f"/api/v1/campaigns/{cid}/contacts/{records[1]['id']}",
            headers=headers, json={"status": "replied"}
        ).status_code == 200
        final = client.get(performance_url, headers=headers).json()
        assert final["replied"] == 2
        assert final["replied_contacted"] == 1
        assert final["contacted"] == 1
        assert final["reply_rate"] == 100.0
