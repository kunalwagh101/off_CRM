from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import (
    API_PREFIX,
    PUBLIC_API_PATHS,
    PUBLIC_API_PREFIXES,
    PUBLIC_HEALTH_PATHS,
    create_app,
)
from offsetx_apollo_builder.api.config import AppSettings


TOKEN = "boundary-token-" + "x" * 40
_PARAM = re.compile(r"{([^}:]+)(?::[^}]+)?}")


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=TOKEN,
        allowed_hosts=("testserver",),
    )


def _concrete(path: str) -> str:
    values = {
        "campaign_id": "missing-campaign",
        "contact_id": "missing-contact",
        "draft_id": "missing-draft",
        "lead_id": "missing-lead",
        "chat_id": "missing-chat",
        "project_id": "missing-project",
        "companion_id": "missing-companion",
        "routine_id": "missing-routine",
        "request_id": "missing-request",
        "provider_id": "mistral",
        "template_id": "missing-template",
        "account_id": "missing-account",
        "asset_id": "missing-asset",
        "brief_id": "missing-brief",
        "post_id": "missing-post",
        "media_id": "missing-media",
        "event_name": "test.event",
    }
    return _PARAM.sub(lambda match: values.get(match.group(1), "missing-id"), path)


def _is_public(path: str) -> bool:
    return path in PUBLIC_API_PATHS or path.startswith(PUBLIC_API_PREFIXES)


def _api_routes(app) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]


def test_every_private_api_route_refuses_an_unauthenticated_request(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        checked: list[tuple[str, str]] = []
        for route in _api_routes(client.app):
            if _is_public(route.path):
                continue
            for method in sorted(route.methods or ()):
                if method in {"HEAD", "OPTIONS"}:
                    continue
                response = client.request(
                    method,
                    _concrete(route.path),
                    follow_redirects=False,
                )
                assert response.status_code == 401, (
                    f"{method} {route.path} was reachable without authentication: "
                    f"{response.status_code} {response.text[:300]}"
                )
                assert response.json() == {"detail": "CRM login required"}
                checked.append((method, route.path))

        # A test that accidentally enumerates nothing is worse than no test.
        assert len(checked) >= 150


def test_public_api_exceptions_are_closed_and_intentional(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        route_paths = {route.path for route in _api_routes(client.app)}

        for path in PUBLIC_API_PATHS:
            assert path in route_paths, f"stale public-path exemption: {path}"

        for prefix in PUBLIC_API_PREFIXES:
            assert any(path.startswith(prefix) for path in route_paths), (
                f"stale public-prefix exemption: {prefix}"
            )

        # Operational health probes are the only explicitly public app endpoints
        # outside /api that execute backend code. They contain no customer data.
        for path in PUBLIC_HEALTH_PATHS:
            response = client.get(path)
            assert response.status_code == 200


def test_every_json_body_endpoint_rejects_broken_json_without_a_traceback(tmp_path):
    headers = {
        "X-Offsetx-Token": TOKEN,
        "Content-Type": "application/json",
    }
    with TestClient(create_app(_settings(tmp_path))) as client:
        spec: dict[str, Any] = client.app.openapi()
        checked = 0
        for path, operations in spec.get("paths", {}).items():
            if not path.startswith("/api/"):
                continue
            for method, operation in operations.items():
                if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
                    continue
                body = operation.get("requestBody") or {}
                content = body.get("content") or {}
                if "application/json" not in content:
                    continue

                response = client.request(
                    method.upper(),
                    _concrete(path),
                    headers=headers,
                    content=b"{",
                    follow_redirects=False,
                )
                assert 400 <= response.status_code < 500, (
                    f"{method.upper()} {path} turned malformed JSON into "
                    f"{response.status_code}: {response.text[:300]}"
                )
                payload = response.json()
                assert payload.get("detail"), (method, path, payload)
                rendered = response.text.lower()
                assert "traceback" not in rendered
                assert 'file "' not in rendered
                checked += 1

        assert checked >= 50


def test_every_json_object_endpoint_rejects_a_list_body(tmp_path):
    headers = {"X-Offsetx-Token": TOKEN}
    with TestClient(create_app(_settings(tmp_path))) as client:
        spec: dict[str, Any] = client.app.openapi()
        checked = 0
        for path, operations in spec.get("paths", {}).items():
            if not path.startswith("/api/"):
                continue
            for method, operation in operations.items():
                if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
                    continue
                body = operation.get("requestBody") or {}
                schema = ((body.get("content") or {}).get("application/json") or {}).get(
                    "schema"
                ) or {}
                if not schema:
                    continue

                response = client.request(
                    method.upper(),
                    _concrete(path),
                    headers=headers,
                    json=[],
                    follow_redirects=False,
                )
                assert 400 <= response.status_code < 500, (
                    f"{method.upper()} {path} accepted/wrecked on a list body: "
                    f"{response.status_code} {response.text[:300]}"
                )
                assert "traceback" not in response.text.lower()
                checked += 1

        assert checked >= 50


def test_validation_error_never_echoes_a_secret_request_body(tmp_path):
    secret = "sk-" + "a" * 32
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            f"{API_PREFIX}/workspaces",
            headers={"X-Offsetx-Token": TOKEN},
            json={
                "username": "alice",
                "workspace_id": "INVALID WORKSPACE",
                "password": secret,
                "unexpected": secret,
            },
        )
        assert response.status_code == 422
        assert secret not in response.text
        assert response.json()["detail"] == "Request validation failed"
