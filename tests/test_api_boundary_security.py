from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import (
    PUBLIC_API_EXACT,
    PUBLIC_API_PREFIX_METHODS,
    create_app,
)
from offsetx_apollo_builder.api.config import AppSettings


API_PREFIX = "/api/v1"
STACK_MARKERS = ("traceback (most recent call last)", "site-packages/", 'file "')


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token="k" * 40,
        allowed_hosts=("testserver",),
    )


def _api_routes(app) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]


def _is_public(method: str, path: str) -> bool:
    verb = method.upper()
    if (verb, path) in PUBLIC_API_EXACT:
        return True
    return any(
        verb == allowed and path.startswith(prefix)
        for allowed, prefix in PUBLIC_API_PREFIX_METHODS
    )


def _concrete_path(route: APIRoute) -> str:
    values: dict[str, str] = {}
    for name, convertor in route.param_convertors.items():
        kind = type(convertor).__name__.lower()
        if "int" in kind:
            values[name] = "1"
        elif "float" in kind:
            values[name] = "1.0"
        elif "uuid" in kind:
            values[name] = "00000000-0000-4000-8000-000000000001"
        elif name == "email":
            values[name] = "boundary@example.com"
        else:
            values[name] = "boundary-probe"
    path = route.path
    for name, value in values.items():
        path = re.sub(r"\{" + re.escape(name) + r"(?::[^}]+)?\}", value, path)
    return path


def _methods(route: APIRoute) -> list[str]:
    return sorted((route.methods or set()) - {"HEAD", "OPTIONS"})


def _assert_safe_4xx(response) -> None:
    assert 400 <= response.status_code < 500, response.text
    lowered = response.text.lower()
    for marker in STACK_MARKERS:
        assert marker not in lowered, response.text


def test_public_policy_points_only_at_live_declared_methods(tmp_path):
    app = create_app(_settings(tmp_path))
    live = {
        (method, route.path)
        for route in _api_routes(app)
        for method in _methods(route)
    }

    assert PUBLIC_API_EXACT <= live
    for method, prefix in PUBLIC_API_PREFIX_METHODS:
        assert any(
            live_method == method and path.startswith(prefix)
            for live_method, path in live
        ), f"public prefix has no live route: {method} {prefix}"


def test_every_current_protected_api_route_rejects_anonymous_requests(tmp_path):
    app = create_app(_settings(tmp_path))
    checked: list[str] = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for route in _api_routes(app):
            for method in _methods(route):
                if _is_public(method, route.path):
                    continue
                response = client.request(method, _concrete_path(route))
                assert response.status_code == 401, (
                    f"{method} {route.path} was reachable without owner auth: "
                    f"{response.status_code} {response.text}"
                )
                assert response.json() == {"detail": "CRM login required"}
                checked.append(f"{method} {route.path}")
    assert checked, "route inventory unexpectedly contained no protected API routes"


def test_a_future_method_under_a_public_prefix_is_protected_by_default(tmp_path):
    app = create_app(_settings(tmp_path))

    @app.delete(f"{API_PREFIX}/email/unsubscribe/admin-probe")
    def privileged_probe():
        return {"should_not_be_public": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.delete(f"{API_PREFIX}/email/unsubscribe/admin-probe")
    assert response.status_code == 401
    assert response.json() == {"detail": "CRM login required"}


def test_wrong_methods_on_exact_public_paths_do_not_inherit_public_access(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.delete(f"{API_PREFIX}/auth/logout").status_code == 401
        assert client.post(f"{API_PREFIX}/meta").status_code == 401


def test_auth_session_never_claims_anonymous_api_token_user_is_authenticated(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        anonymous = client.get(f"{API_PREFIX}/auth/session")
        assert anonymous.status_code == 200
        assert anonymous.json()["authenticated"] is False

        authorised = client.get(
            f"{API_PREFIX}/auth/session",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
        assert authorised.status_code == 200
        assert authorised.json()["authenticated"] is True


def test_spoofed_identity_headers_and_wrong_token_have_no_authority(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        spoofed = client.get(
            f"{API_PREFIX}/dashboard",
            headers={
                "X-User": "owner",
                "X-Workspace": "workspace-1",
                "X-Workspace-Id": "workspace-1",
                "X-Forwarded-User": "owner",
                "X-Offsetx-User": "owner",
                "X-Offsetx-Token": "not-the-real-token",
            },
        )
        assert spoofed.status_code == 401
        _assert_safe_4xx(spoofed)

        authorised = client.get(
            f"{API_PREFIX}/dashboard",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
        assert authorised.status_code == 200


def test_every_protected_body_route_rejects_malformed_input_before_handler(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)
    headers = {
        "Authorization": f"Bearer {settings.api_token}",
        "Content-Type": "application/json",
    }
    checked: list[str] = []

    with TestClient(app, raise_server_exceptions=False) as client:
        for route in _api_routes(app):
            if route.body_field is None:
                continue
            for method in _methods(route):
                if _is_public(method, route.path):
                    continue
                called: list[str] = []
                original = route.dependant.call

                def must_not_run(*args, **kwargs):
                    called.append(route.path)
                    raise AssertionError("business logic ran before request validation")

                route.dependant.call = must_not_run
                try:
                    response = client.request(
                        method,
                        _concrete_path(route),
                        headers=headers,
                        content=b'{"broken":',
                    )
                finally:
                    route.dependant.call = original

                _assert_safe_4xx(response)
                assert called == [], f"{method} {route.path} executed business logic"
                checked.append(f"{method} {route.path}")

    assert checked, "route inventory unexpectedly contained no protected body routes"


def test_typed_query_validation_runs_before_business_logic(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)
    route = next(
        route
        for route in _api_routes(app)
        if route.path == f"{API_PREFIX}/sales/leads" and "GET" in (route.methods or set())
    )
    called: list[str] = []
    original = route.dependant.call

    def must_not_run(*args, **kwargs):
        called.append("handler")
        raise AssertionError("business logic ran before query validation")

    route.dependant.call = must_not_run
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                f"{API_PREFIX}/sales/leads?limit=0",
                headers={"Authorization": f"Bearer {settings.api_token}"},
            )
    finally:
        route.dependant.call = original

    assert response.status_code == 422
    _assert_safe_4xx(response)
    assert called == []


def test_public_boundaries_are_narrow_and_reject_bad_input(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        meta = client.get(f"{API_PREFIX}/meta")
        assert meta.status_code == 200
        assert settings.api_token not in meta.text

        malformed_login = client.post(
            f"{API_PREFIX}/auth/login",
            headers={"Content-Type": "application/json"},
            content=b'{"username":',
        )
        _assert_safe_4xx(malformed_login)

        bad_sns = client.post(
            f"{API_PREFIX}/email-delivery/events/ses/sns",
            json={"Type": "Notification", "MessageId": "not-signed"},
        )
        _assert_safe_4xx(bad_sns)

        bad_unsubscribe = client.get(f"{API_PREFIX}/email/unsubscribe/not-a-real-token")
        _assert_safe_4xx(bad_unsubscribe)

        bad_one_click = client.post(
            f"{API_PREFIX}/email/unsubscribe/not-a-real-token",
            content=b"List-Unsubscribe=wrong",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        _assert_safe_4xx(bad_one_click)

        logout = client.post(f"{API_PREFIX}/auth/logout", json={})
        assert logout.status_code == 200
