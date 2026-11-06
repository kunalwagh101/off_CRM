"""The UI can grant only enabled registered tools in its authenticated workspace."""

from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def test_catalogue_authentication_workspace_scope_and_no_execution_recipe(tmp_path):
    token = "catalogue-owner-" + "x" * 40
    app = create_app(
        AppSettings(
            project_root=Path.cwd(),
            database_path=tmp_path / "crm.db",
            data_dir=tmp_path / "data",
            export_dir=tmp_path / "exports",
            frontend_dist=tmp_path / "missing",
            api_token=token,
            allowed_hosts=("testserver",),
        )
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/companion-tools").status_code == 401
        owner = {"X-Offsetx-Token": token}
        for workspace in ("alpha", "beta"):
            assert (
                client.post(
                    "/api/v1/workspaces",
                    headers=owner,
                    json={
                        "username": workspace,
                        "workspace_id": workspace,
                        "password": workspace + "-password-123",
                    },
                ).status_code
                == 201
            )
            app.state.ai_tools.register(
                name=workspace + "-tool",
                workspace_id=workspace,
                repository_url="https://github.com/example/example",
                commit_sha="a" * 40,
                image="python@sha256:" + "b" * 64,
                command=("python", "tool.py"),
            )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"username": "alpha", "password": "alpha-password-123"},
            ).status_code
            == 200
        )
        response = client.get("/api/v1/companion-tools")
        assert response.status_code == 200
        rows = response.json()["items"]
        assert [row["name"] for row in rows] == ["alpha-tool"]
        assert not ({"command", "image", "repository_url"} & rows[0].keys())
        app.state.ai_tools.set_enabled(rows[0]["id"], False, workspace_id="alpha")
        assert client.get("/api/v1/companion-tools").json()["items"] == []
