from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import (
    API_PREFIX,
    PUBLIC_API_PATHS,
    PUBLIC_UNSUBSCRIBE_PREFIX,
    create_app,
)
from offsetx_apollo_builder.api.config import AppSettings


TOKEN = "endpoint-boundary-token-" + "x" * 32


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
    return re.sub(r"\{[^{}]+\}", "probe", path)


def test_every_non_public_api_method_refuses_before_route_logic(tmp_path):
    """Future routes join this test automatically; no manual endpoint list."""
    app = create_app(_settings(tmp_path))
    failures: list[str] = []

    with TestClient(app) as client:
        for route in app.routes:
            if not isinstance(route, APIRoute) or not route.path.startswith(API_PREFIX):
                continue
            if route.path in PUBLIC_API_PATHS:
                continue
            if route.path.startswith(PUBLIC_UNSUBSCRIBE_PREFIX):
                # The signed unsubscribe token is the authentication mechanism.
                continue

            path = _concrete(route.path)
            for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
                response = client.request(method, path)
                if response.status_code != 401:
                    failures.append(
                        f"{method} {route.path} -> {response.status_code}: "
                        f"{response.text[:200]}"
                    )

    assert not failures, "\n".join(failures)


def test_public_api_surface_is_closed_and_small(tmp_path):
    app = create_app(_settings(tmp_path))
    declared = set(PUBLIC_API_PATHS)
    actual_public_routes = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith(API_PREFIX)
        and route.path in declared
    }

    assert actual_public_routes == declared
    assert PUBLIC_UNSUBSCRIBE_PREFIX.endswith("/")
    # A nested path must not inherit public access from the unsubscribe prefix.
    with TestClient(app) as client:
        response = client.get(PUBLIC_UNSUBSCRIBE_PREFIX + "token/extra")
        assert response.status_code == 401


def test_malformed_body_is_bounded_and_never_echoes_sensitive_input(tmp_path):
    secret = "sk-live-SHOULD-NEVER-BE-ECHOED-123456789"
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            f"{API_PREFIX}/workspaces",
            headers={
                "X-Offsetx-Token": TOKEN,
                "Content-Type": "application/json",
            },
            content=(
                '{"username":"' + secret + '","workspace_id":"alpha","password":'
            ),
        )

    assert 400 <= response.status_code < 500
    assert secret not in response.text
    assert len(response.text) < 10_000
    payload = response.json()
    assert payload["detail"] == "Request validation failed"


def test_wrong_body_types_do_not_reach_business_logic_or_echo_values(tmp_path):
    secret = "password=ULTRA-SECRET-DO-NOT-ECHO"
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            f"{API_PREFIX}/workspaces",
            headers={"X-Offsetx-Token": TOKEN},
            json={
                "username": {"nested": secret},
                "workspace_id": "alpha",
                "password": "valid-password-123",
            },
        )

    assert response.status_code == 422
    assert secret not in response.text
    assert len(response.json().get("errors", [])) <= 50
