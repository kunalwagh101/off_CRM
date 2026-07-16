from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


CSV = b"""Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension
Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff
"""


def _settings(tmp_path: Path, *, token: str = "", max_upload_bytes: int = 1024 * 1024):
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token=token,
        max_upload_bytes=max_upload_bytes,
    )


def test_complete_api_workflow_uses_local_outbox_by_default(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        health = client.get("/health/ready")
        assert health.status_code == 200
        assert health.headers["x-content-type-options"] == "nosniff"
        assert "default-src 'self'" in health.headers["content-security-policy"]

        created = client.post(
            "/api/v1/campaigns",
            headers={"Idempotency-Key": "campaign-key"},
            json={"name": "API Pilot", "daily_send_limit": 2},
        )
        assert created.status_code == 201
        campaign_id = created.json()["id"]
        replay = client.post(
            "/api/v1/campaigns",
            headers={"Idempotency-Key": "campaign-key"},
            json={"name": "Ignored on replay", "daily_send_limit": 2},
        )
        assert replay.json()["id"] == campaign_id
        assert replay.json()["idempotent_replay"] is True

        imported = client.post(
            f"/api/v1/campaigns/{campaign_id}/contacts/import",
            files={"file": ("../../contacts.csv", CSV, "text/csv")},
            data={"default_category": "Sustainability / ESG / Climate"},
        )
        assert imported.status_code == 200
        assert imported.json()["added"] == 1

        generated = client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/generate",
            json={
                "campaign_contact_ids": [],
                "stages": ["initial", "followup1", "followup2"],
                "provider": None,
            },
        )
        assert generated.status_code == 200
        assert generated.json()["generated"] == 3
        drafts = client.get(f"/api/v1/campaigns/{campaign_id}/drafts").json()["items"]
        assert len(drafts) == 3
        assert all(item["sendable"] for item in drafts)

        approved = client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/approve",
            json={"draft_ids": [item["id"] for item in drafts], "stages": []},
        )
        assert approved.json() == {"approved": 3, "blocked": 0}
        sent = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            json={
                "mode": "local",
                "confirmation": "",
                "sync_replies_first": True,
                "max_messages": 1,
            },
        )
        assert sent.status_code == 200
        assert sent.json()["sent_count"] == 1
        assert len(list((tmp_path / "data" / "mail" / "outbox").glob("*.json"))) == 1

        live_without_confirmation = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            json={"mode": "gmail", "confirmation": "", "sync_replies_first": True},
        )
        assert live_without_confirmation.status_code == 400

        exported = client.get(f"/api/v1/campaigns/{campaign_id}/export?format=csv")
        assert exported.status_code == 200
        header = exported.content.decode("utf-8-sig").splitlines()[0]
        assert header.split(",")[:6] == [
            "Checkbox",
            "Outreach Date",
            "POI Name",
            "POI Response",
            "Follow-Up",
            "Meeting Transcript",
        ]
        assert client.get(f"/api/v1/campaigns/{campaign_id}/reports/ab").json()["items"][0]["initial_sent"] == 1
        assert client.get(f"/api/v1/campaigns/{campaign_id}/events").json()["total"] >= 4
        assert client.get("/api/v1/templates").json()["total"] == 8


def test_security_token_upload_limits_and_provider_boundary(tmp_path):
    token = "a" * 32
    settings = _settings(tmp_path, token=token, max_upload_bytes=1024)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/meta").status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 401
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
        campaign_id = client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={"name": "Secured"},
        ).json()["id"]
        oversized = client.post(
            f"/api/v1/campaigns/{campaign_id}/contacts/import",
            headers=headers,
            files={"file": ("contacts.csv", b"x" * 1025, "text/csv")},
        )
        assert oversized.status_code == 413
        unsupported = client.post(
            f"/api/v1/campaigns/{campaign_id}/contacts/import",
            headers=headers,
            files={"file": ("contacts.exe", b"test", "application/octet-stream")},
        )
        assert unsupported.status_code == 415
        command_provider = client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/generate",
            headers=headers,
            json={
                "campaign_contact_ids": [],
                "stages": ["initial"],
                "provider": {
                    "provider_type": "local_command",
                    "model": "",
                    "api_key_env": "",
                    "base_url": "",
                    "timeout_seconds": 60,
                    "extra": {"command": ["sh"]},
                },
            },
        )
        assert command_provider.status_code == 422


def test_expert_source_requires_declared_rights_basis(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        invalid = client.post(
            "/api/v1/expert-sources/import",
            files={"file": ("notes.md", b"Useful permitted notes.", "text/markdown")},
            data={"rights_basis": "scraped_without_permission"},
        )
        assert invalid.status_code == 422
        accepted = client.post(
            "/api/v1/expert-sources/import",
            files={"file": ("notes.md", b"Useful permitted notes.", "text/markdown")},
            data={"rights_basis": "owned", "expert_name": "OffsetX"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["chunks_added"] == 1


def test_non_loopback_binding_requires_strong_token(tmp_path):
    settings = _settings(tmp_path, token="short")
    settings.host = "0.0.0.0"
    with pytest.raises(ValueError, match="non-loopback"):
        settings.validate()


def test_production_frontend_is_served_by_fastapi(tmp_path):
    settings = _settings(tmp_path)
    settings.frontend_dist = Path("frontend/dist").resolve()
    with TestClient(create_app(settings)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "OffsetX Outreach" in response.text
        assert "text/html" in response.headers["content-type"]
