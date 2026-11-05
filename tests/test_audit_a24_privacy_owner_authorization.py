"""A24/A05: privacy inventory and destructive erasure require install-owner rights.

Use real authenticated FastAPI sessions and synthetic contacts. No production data.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.privacy import DELETE_CONFIRMATION


ADMIN_TOKEN = "a24-install-admin-" + "x" * 36
SUBJECT = {"subject": {"emails": ["privacy-a24-alice@example.test"]}}


@pytest.fixture()
def privacy_clients(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token=ADMIN_TOKEN,
        session_secret="a24-privacy-session-" + "s" * 36,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as install:
        admin_headers = {"X-Offsetx-Token": ADMIN_TOKEN}
        for name, workspace, owner in (
            ("operator", "team-a", False),
            ("other", "team-b", False),
            ("install-owner", "local", True),
        ):
            account = install.post(
                "/api/v1/workspaces", headers=admin_headers,
                json={
                    "username": name,
                    "workspace_id": workspace,
                    "password": name + "-safe-password-123",
                    **({"confirm_install_owner": True} if owner else {}),
                },
            )
            assert account.status_code == 201, account.text
        crm = install.app.state.engine.store
        target_id = crm.upsert_contact(ContactInput(
            full_name="Synthetic Privacy Person",
            email="privacy-a24-alice@example.test",
        ))
        other_id = crm.upsert_contact(ContactInput(
            full_name="Unrelated Other Contact",
            email="privacy-a24-bob@example.test",
        ))
        clients = {}
        for username in ("operator", "other", "install-owner"):
            client = TestClient(install.app, raise_server_exceptions=False)
            logged = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": username + "-safe-password-123"},
            )
            assert logged.status_code == 200, logged.text
            clients[username] = client
        yield install, admin_headers, clients, crm, target_id, other_id
        for client in clients.values():
            client.close()


def test_A24_ordinary_workspace_session_cannot_inventory_or_preview_subject(privacy_clients):
    """A24: any ordinary login must not read another person's global CRM data."""
    install, admin, clients, crm, target, other = privacy_clients
    operator = clients["operator"]
    for path in (
        "/api/v1/privacy/subject-access",
        "/api/v1/privacy/deletion-preview",
    ):
        refused = operator.post(path, json=SUBJECT)
        assert refused.status_code == 403, (path, refused.text)
        assert "privacy-a24-alice@example.test" not in refused.text

    confirmation = operator.get("/api/v1/privacy/deletion-confirmation")
    assert confirmation.status_code == 403
    assert crm.get_contact(target) is not None
    assert crm.get_contact(other) is not None


def test_A24_ordinary_login_cannot_erase_even_with_confirmed_owner_preview(privacy_clients):
    """A24: knowledge of a preview ID and phrase does not grant delete authority."""
    install, admin, clients, crm, target, other = privacy_clients
    owner_preview = install.post(
        "/api/v1/privacy/deletion-preview", json=SUBJECT, headers=admin,
    )
    assert owner_preview.status_code == 201, owner_preview.text
    request_id = owner_preview.json()["request_id"]

    for username in ("operator", "other"):
        user = clients[username]
        for body in (
            {**SUBJECT, "confirmation": DELETE_CONFIRMATION},
            {
                "subject": {
                    "workspace_id": "local",
                    "emails": ["privacy-a24-alice@example.test"],
                },
                "confirmation": DELETE_CONFIRMATION,
            },
        ):
            denied = user.post(
                f"/api/v1/privacy/deletions/{request_id}",
                json=body,
                headers={"X-Workspace-Id": "local", "X-Offsetx-Workspace": "local"},
            )
            assert denied.status_code == 403, denied.text
            assert crm.get_contact(target) is not None
            assert crm.get_contact(other) is not None


def test_A24_nonowner_cannot_create_and_execute_own_privacy_deletion(privacy_clients):
    """A24: a nonowner must not preview and erase shared, unscoped CRM contacts."""
    install, admin, clients, crm, target, other = privacy_clients
    operator = clients["operator"]
    preview = operator.post("/api/v1/privacy/deletion-preview", json=SUBJECT)
    assert preview.status_code == 403, preview.text
    deletion = operator.post(
        "/api/v1/privacy/deletions/any-other-request-id",
        json={**SUBJECT, "confirmation": DELETE_CONFIRMATION},
    )
    assert deletion.status_code == 403, deletion.text
    assert crm.get_contact(target) is not None
    assert crm.get_contact(other) is not None


def test_A24_owner_login_and_install_token_keep_complete_deletion_workflow(privacy_clients):
    """A24: only the intended install owner can inventory, confirm and finish."""
    install, admin, clients, crm, target, other = privacy_clients
    local_owner = clients["install-owner"]
    for actor, headers in ((install, admin), (local_owner, {})):
        access = actor.post("/api/v1/privacy/subject-access", json=SUBJECT, headers=headers)
        assert access.status_code == 200, access.text
        assert access.json()["total_records"] >= 1
    confirmation = local_owner.get("/api/v1/privacy/deletion-confirmation")
    assert confirmation.status_code == 200
    assert confirmation.json()["confirmation"] == DELETE_CONFIRMATION

    preview = local_owner.post("/api/v1/privacy/deletion-preview", json=SUBJECT)
    assert preview.status_code == 201, preview.text
    request_id = preview.json()["request_id"]
    deleted = local_owner.post(
        f"/api/v1/privacy/deletions/{request_id}",
        json={**SUBJECT, "confirmation": DELETE_CONFIRMATION},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["complete"] is True
    assert crm.get_contact(target) is None
    assert crm.get_contact(other) is not None
    assert "privacy-a24-alice@example.test" not in deleted.text


def test_A24_permission_refusal_survives_a_fresh_client_session(privacy_clients):
    """A24: permissions are server-side, not a browser UI or stale local state."""
    install, admin, clients, crm, target, other = privacy_clients
    with TestClient(install.app, raise_server_exceptions=False) as new_session:
        logged = new_session.post(
            "/api/v1/auth/login",
            json={"username": "operator", "password": "operator-safe-password-123"},
        )
        assert logged.status_code == 200, logged.text
        assert new_session.post(
            "/api/v1/privacy/subject-access", json=SUBJECT,
        ).status_code == 403
        assert new_session.post(
            "/api/v1/privacy/deletion-preview", json=SUBJECT,
        ).status_code == 403
    assert crm.get_contact(target) is not None
    assert crm.get_contact(other) is not None
