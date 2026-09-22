from __future__ import annotations

from pathlib import Path
import inspect

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import DemoSessionAuth, LoginAttemptLimiter
from offsetx_apollo_builder.api.config import AppSettings


def _demo_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="0.0.0.0",
        demo_username="demo-owner",
        demo_password="temporary-password-123",
        session_secret="s" * 48,
        session_hours=2,
        allowed_hosts=("testserver", "crm.test"),
    )


def test_demo_login_uses_secure_session_cookie_and_logout(tmp_path):
    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        status = client.get("/api/v1/auth/session")
        assert status.json() == {
            "configured": True,
            "authenticated": False,
            "username": "",
            "workspace_id": "",
            "expires_at": None,
        }
        assert client.get("/api/v1/dashboard").status_code == 401
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "incorrect-password"},
        ).status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert login.status_code == 200
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=strict" in cookie
        assert client.get("/api/v1/dashboard").status_code == 200
        assert client.get("/api/v1/auth/session").json()["username"] == "demo-owner"

        logout = client.post("/api/v1/auth/logout", json={})
        assert logout.status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 401


def test_session_signature_and_expiry_are_enforced():
    auth = DemoSessionAuth(
        username="demo",
        password="long-demo-password",
        session_secret="x" * 32,
        session_hours=1,
    )
    token = auth.issue(now=100)
    assert auth.verify(token, now=101).username == "demo"
    assert auth.verify(token + "tampered", now=101) is None
    assert auth.verify(token, now=3700) is None
    assert auth.verify("not-a-token", now=101) is None


def test_login_attempt_limiter_recovers_after_window():
    limiter = LoginAttemptLimiter(maximum=2, window_seconds=10)
    assert limiter.allowed("client", now=0)
    limiter.failed("client", now=0)
    limiter.failed("client", now=1)
    assert not limiter.allowed("client", now=2)
    assert limiter.allowed("client", now=11)


def test_non_loopback_accepts_complete_demo_login_and_rejects_partial(tmp_path):
    settings = _demo_settings(tmp_path)
    settings.validate()
    settings.session_secret = ""
    with pytest.raises(ValueError, match="requires OFFSETX_DEMO_USERNAME"):
        settings.validate()



def _route_path(path: str) -> str:
    import re
    return re.sub(r"\{[^}]+\}", "test-resource", path)


def test_every_protected_api_route_refuses_before_validation_without_auth(tmp_path):
    from offsetx_apollo_builder.api.app import PUBLIC_API_PATHS, PUBLIC_API_PREFIXES

    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        failures = []
        for route in client.app.routes:
            path = getattr(route, "path", "")
            methods = sorted(
                method
                for method in (getattr(route, "methods", set()) or set())
                if method in {"GET", "POST", "PATCH", "DELETE"}
            )
            if not path.startswith("/api/"):
                continue
            public = path in PUBLIC_API_PATHS or any(
                path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES
            )
            if public:
                continue
            for method in methods:
                response = client.request(method, _route_path(path))
                if response.status_code != 401:
                    failures.append((method, path, response.status_code))
        assert failures == []


def test_no_api_route_accepts_an_untyped_raw_dict_body(tmp_path):
    from fastapi.routing import APIRoute
    from offsetx_apollo_builder.api.app import create_app as factory

    app = factory(_demo_settings(tmp_path))
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        signature = inspect.signature(route.endpoint)
        for parameter in signature.parameters.values():
            annotation = parameter.annotation
            text = str(annotation)
            if parameter.name == "body" and (
                annotation is dict
                or text in {"dict[str, typing.Any]", "dict[str, Any]"}
            ):
                offenders.append(f"{','.join(sorted(route.methods or []))} {route.path}")
    assert offenders == []


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/companions", {"name": "x", "instructions": "ok", "unexpected": True}),
        ("/api/v1/ai/run", {"instructions": "hello", "max_rounds": "three"}),
        (
            "/api/v1/privacy/subject-access",
            {"subject": {"emails": "alice@example.com"}},
        ),
    ],
)
def test_malformed_bodies_are_bounded_4xx_without_echo_or_stacktrace(
    tmp_path, path, payload
):
    settings = _demo_settings(tmp_path)
    settings.api_token = "a" * 40
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        response = client.post(
            path,
            headers={"X-Offsetx-Token": settings.api_token},
            json=payload,
        )
        assert 400 <= response.status_code < 500
        body = response.text.lower()
        assert "traceback" not in body
        assert "stack trace" not in body
        assert "unexpected" not in body
