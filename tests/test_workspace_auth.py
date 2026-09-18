from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import WorkspaceSessionAuth
from offsetx_apollo_builder.api.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=ROOT,
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="0.0.0.0",
        workspace_logins={
            "alpha": ("alice", "a" * 20),
            "beta": ("bob", "b" * 20),
        },
        session_secret="s" * 48,
        session_hours=2,
        allowed_hosts=("testserver", "crm.test"),
    )


def test_workspace_session_is_signed_to_one_workspace() -> None:
    auth = WorkspaceSessionAuth(
        logins={"alpha": ("alice", "a" * 20), "beta": ("bob", "b" * 20)},
        session_secret="x" * 48,
        session_hours=1,
    )
    identity = auth.authenticate("alice", "a" * 20)
    assert identity is not None
    assert identity.workspace_id == "alpha"

    token = auth.issue(identity, now=1000)
    verified = auth.verify(token, now=1001)
    assert verified is not None
    assert verified.workspace_id == "alpha"

    encoded, signature = token.split(".", 1)
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    changed = raw.replace("\nalpha\n", "\nbeta\n", 1)
    changed_encoded = base64.urlsafe_b64encode(changed.encode()).rstrip(b"=").decode()
    assert auth.verify(f"{changed_encoded}.{signature}", now=1001) is None


def test_workspace_config_rejects_duplicate_usernames(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.workspace_logins["beta"] = ("alice", "c" * 20)
    with pytest.raises(ValueError, match="configured more than once"):
        settings.validate()


def test_authenticated_session_reports_server_selected_workspace(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path)), base_url="https://crm.test") as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "a" * 20},
        )
        assert response.status_code == 200
        assert response.json()["workspace_id"] == "alpha"
        session = client.get("/api/v1/auth/session").json()
        assert session["authenticated"] is True
        assert session["workspace_id"] == "alpha"


def test_workspace_login_env_prevents_local_token_autoprovision(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "OFFSETX_WORKSPACE_LOGINS",
        '{"alpha":{"username":"alice","password":"' + ("a" * 20) + '"}}',
    )
    monkeypatch.setenv("OFFSETX_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("OFFSETX_LOCAL_API_TOKEN", raising=False)
    monkeypatch.delenv("OFFSETX_DEMO_USERNAME", raising=False)
    monkeypatch.delenv("OFFSETX_DEMO_PASSWORD", raising=False)

    settings = AppSettings.from_env(tmp_path)
    assert settings.workspace_logins == {"alpha": ("alice", "a" * 20)}
    assert settings.api_token == ""
    assert not (settings.data_dir / settings.TOKEN_FILENAME).exists()


def test_legacy_demo_login_remains_bound_to_local_workspace(tmp_path: Path) -> None:
    settings = AppSettings(
        project_root=ROOT,
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="0.0.0.0",
        demo_username="legacy",
        demo_password="l" * 20,
        session_secret="s" * 48,
        allowed_hosts=("testserver", "crm.test"),
    )
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "legacy", "password": "l" * 20},
        )
        assert response.status_code == 200
        assert response.json()["workspace_id"] == "local"


@pytest.mark.parametrize(
    ("workspace_logins", "message"),
    [
        ({"../escape": ("alice", "a" * 20)}, "Invalid workspace id"),
        ({"alpha": ("", "a" * 20)}, "requires a username"),
        ({"alpha": ("alice", "short")}, "password must contain at least 12 characters"),
    ],
)
def test_workspace_config_refuses_invalid_identity_shapes(
    tmp_path: Path,
    workspace_logins: dict[str, tuple[str, str]],
    message: str,
) -> None:
    settings = _settings(tmp_path)
    settings.workspace_logins = workspace_logins
    with pytest.raises(ValueError, match=message):
        settings.validate()


def test_workspace_login_env_rejects_invalid_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFSETX_WORKSPACE_LOGINS", "{not-json")
    monkeypatch.setenv("OFFSETX_SESSION_SECRET", "s" * 48)
    with pytest.raises(ValueError, match="must be valid JSON"):
        AppSettings.from_env(tmp_path)
