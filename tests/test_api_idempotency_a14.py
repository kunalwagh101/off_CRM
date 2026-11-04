"""A14: real HTTP idempotency must survive races, crashes and hostile key reuse."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _settings(root: Path, name: str) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=root / "same-crm.db",
        data_dir=root / name,
        export_dir=root / name / "exports",
        frontend_dist=root / "no-frontend",
        allowed_hosts=("testserver",),
        allow_unauthenticated=True,
    )


def _post_campaign(client: TestClient, key: str, name: str = "A14 campaign"):
    return client.post(
        "/api/v1/campaigns",
        headers={"Idempotency-Key": key},
        json={"name": name, "daily_send_limit": 3},
    )


def test_A14_two_live_http_instances_cannot_duplicate_same_key(tmp_path):
    """A14: concurrent app instances use the same durable key, not a Python lock."""
    app1, app2 = create_app(_settings(tmp_path, "instance-one")), create_app(
        _settings(tmp_path, "instance-two")
    )
    first_entered = threading.Event()
    with TestClient(app1) as client1, TestClient(app2) as client2:
        original = app1.state.engine.create_campaign

        def slow_create(*args, **kwargs):
            first_entered.set()
            time.sleep(0.35)  # real overlap, after the first request got past lookup
            return original(*args, **kwargs)

        app1.state.engine.create_campaign = slow_create
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_post_campaign, client1, "same-concurrent-key")
            assert first_entered.wait(timeout=8), "First HTTP operation never started"
            second = pool.submit(_post_campaign, client2, "same-concurrent-key")
            responses = [first.result(timeout=20), second.result(timeout=20)]

        assert [r.status_code for r in responses] == [201, 201], [
            (r.status_code, r.text[:300]) for r in responses
        ]
        ids = [r.json()["id"] for r in responses]
        assert ids[0] == ids[1], ids
        assert sum(bool(r.json().get("idempotent_replay")) for r in responses) == 1
        listed = client1.get("/api/v1/campaigns").json()
        assert listed["total"] == 1


def test_A14_same_key_with_different_payload_is_conflict(tmp_path):
    """A14: the key is not permission to silently return another operation."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app) as client:
        initial = _post_campaign(client, "fixed-key", name="Original")
        assert initial.status_code == 201
        conflict = _post_campaign(client, "fixed-key", name="Altered")
        assert conflict.status_code == 409
        assert "idempotency" in conflict.text.lower() or "key" in conflict.text.lower()
        assert "Original" in str(client.get("/api/v1/campaigns").json())
        assert client.get("/api/v1/campaigns").json()["total"] == 1


def test_A14_failure_after_mutation_rolls_back_effect_and_key(tmp_path):
    """A14: crash before commit cannot leave a campaign without its replay."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app, raise_server_exceptions=False) as client:
        original = app.state.engine.create_campaign

        def crashed(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("simulated process crash before response")

        app.state.engine.create_campaign = crashed
        failed = _post_campaign(client, "crash-key")
        assert failed.status_code >= 500
        assert client.get("/api/v1/campaigns").json()["total"] == 0
        app.state.engine.create_campaign = original
        retried = _post_campaign(client, "crash-key")
        assert retried.status_code == 201, retried.text[:300]
        assert client.get("/api/v1/campaigns").json()["total"] == 1
        replay = _post_campaign(client, "crash-key")
        assert replay.json()["id"] == retried.json()["id"]


def test_A14_uncertain_send_error_is_not_replayed_automatically(tmp_path):
    """A14: a provider might have accepted an email before returning an error."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app, raise_server_exceptions=False) as client:
        campaign = client.post(
            "/api/v1/campaigns",
            json={"name": "A14 external", "daily_send_limit": 2},
        )
        assert campaign.status_code == 201
        campaign_id = campaign.json()["id"]
        called = []

        def uncertain(*args, **kwargs):
            called.append("external action already occurred")
            raise RuntimeError("transport may have accepted")

        app.state.engine.run_due = uncertain
        payload = {"mode": "local", "sync_replies_first": False, "max_messages": 1}
        first = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            headers={"Idempotency-Key": "uncertain-send"},
            json=payload,
        )
        assert first.status_code >= 500
        second = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            headers={"Idempotency-Key": "uncertain-send"},
            json=payload,
        )
        assert second.status_code == 409, second.text[:300]
        assert called == ["external action already occurred"]


def test_A14_key_cannot_be_blank_or_excessive(tmp_path):
    """A14: malformed and unbounded header values fail before mutation."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app) as client:
        for key in ("   ", "x" * 300):
            response = _post_campaign(client, key)
            assert response.status_code == 422, response.text[:300]
        assert client.get("/api/v1/campaigns").json()["total"] == 0



def test_A14_real_postgres_two_app_instances_share_one_idempotency_effect(tmp_path, monkeypatch):
    """A14: two real PostgreSQL connections serialize the operation plus result."""
    import os
    import uuid

    import pytest
    import psycopg
    from cryptography.fernet import Fernet

    url = os.environ.get("OFF_CRM_TEST_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("requires disposable PostgreSQL: OFF_CRM_TEST_POSTGRES_URL")
    schema = "a14_" + uuid.uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    target = url + ("&" if "?" in url else "?") + f"options=-csearch_path%3D{schema}"
    monkeypatch.setenv("OFFSETX_DATABASE_URL", target)
    master = Fernet.generate_key().decode()
    try:
        settings_a, settings_b = _settings(tmp_path, "pg-a"), _settings(tmp_path, "pg-b")
        settings_a.secrets_key = master
        settings_b.secrets_key = master
        app_a, app_b = create_app(settings_a), create_app(settings_b)
        started = threading.Event()
        with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
            original = app_a.state.engine.create_campaign

            def slow_create(*args, **kwargs):
                started.set()
                time.sleep(0.30)
                return original(*args, **kwargs)

            app_a.state.engine.create_campaign = slow_create
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(_post_campaign, client_a, "a14-pg-key")
                assert started.wait(timeout=12)
                second = pool.submit(_post_campaign, client_b, "a14-pg-key")
                responses = [first.result(timeout=25), second.result(timeout=25)]
            assert [response.status_code for response in responses] == [201, 201], [
                (r.status_code, r.text[:200]) for r in responses
            ]
            assert responses[0].json()["id"] == responses[1].json()["id"]
            assert client_a.get("/api/v1/campaigns").json()["total"] == 1
            assert client_b.get("/api/v1/campaigns").json()["total"] == 1
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def test_A14_successful_external_call_replays_without_resending(tmp_path):
    """A14: a completed provider action can replay its result, not the send."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/campaigns", json={"name": "A14 send replay", "daily_send_limit": 2},
        )
        assert created.status_code == 201
        campaign_id = created.json()["id"]
        calls = []

        def simulated_send(*args, **kwargs):
            calls.append("sent")
            return {"sent_count": 1, "skipped": 0}

        app.state.engine.run_due = simulated_send
        body = {"mode": "local", "sync_replies_first": False, "max_messages": 1}
        first = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            json=body, headers={"Idempotency-Key": "send-once"},
        )
        assert first.status_code == 200, first.text[:300]
        replay = client.post(
            f"/api/v1/campaigns/{campaign_id}/send",
            json=body, headers={"Idempotency-Key": "send-once"},
        )
        assert replay.status_code == 200, replay.text[:300]
        assert replay.json() == {**first.json(), "idempotent_replay": True}
        assert calls == ["sent"]


def test_A14_unverified_legacy_key_does_not_replay_another_request(tmp_path):
    """A14: old rows have no principal or payload binding: refuse them safely."""
    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app) as client:
        app.state.engine.store.save_idempotency(
            "create_campaign", "legacy-key", {"id": "unsafe-old-result"},
        )
        refused = _post_campaign(client, "legacy-key")
        assert refused.status_code == 409
        assert client.get("/api/v1/campaigns").json()["total"] == 0



def test_A14_same_key_from_another_authenticated_principal_is_refused(tmp_path):
    """A14: a login cannot read an install token's earlier private result."""
    settings = _settings(tmp_path, "authenticated")
    settings.allow_unauthenticated = False
    settings.api_token = "t" * 32
    settings.demo_username = "a14-owner"
    settings.demo_password = "a14-temporary-password-123"
    settings.session_secret = "s" * 32
    with TestClient(create_app(settings)) as client:
        first = client.post(
            "/api/v1/campaigns",
            headers={"Idempotency-Key": "shared-key", "Authorization": "Bearer " + "t" * 32},
            json={"name": "Private campaign", "daily_send_limit": 3},
        )
        assert first.status_code == 201, first.text[:300]
        logged_in = client.post(
            "/api/v1/auth/login",
            json={"username": "a14-owner", "password": "a14-temporary-password-123"},
        )
        assert logged_in.status_code == 200, logged_in.text[:300]
        other = _post_campaign(client, "shared-key", "Private campaign")
        assert other.status_code == 409
        assert "idempotency" in other.text.lower()
        assert client.get("/api/v1/campaigns").json()["total"] == 1



def test_A14_completed_send_replays_even_if_provider_setup_is_now_unavailable(tmp_path):
    """A14: a replay must not reconstruct a provider or reread its credentials."""
    from unittest.mock import patch

    app = create_app(_settings(tmp_path, "one"))
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/campaigns",
            json={"name": "A14 provider independent replay", "daily_send_limit": 2},
        )
        campaign_id = created.json()["id"]
        calls = []

        def send_once(*args, **kwargs):
            calls.append("sent")
            return {"sent_count": 1}

        app.state.engine.run_due = send_once
        uri = f"/api/v1/campaigns/{campaign_id}/send"
        headers = {"Idempotency-Key": "provider-replay"}
        payload = {"mode": "local", "sync_replies_first": False, "max_messages": 1}
        first = client.post(uri, headers=headers, json=payload)
        assert first.status_code == 200, first.text[:300]
        with patch(
            "offsetx_apollo_builder.api.app._mail_provider",
            side_effect=RuntimeError("provider is unavailable after original send"),
        ):
            replay = client.post(uri, headers=headers, json=payload)
        assert replay.status_code == 200, replay.text[:300]
        assert replay.json() == {**first.json(), "idempotent_replay": True}
        assert calls == ["sent"]
