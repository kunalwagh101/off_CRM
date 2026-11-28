from __future__ import annotations

from pathlib import Path
import inspect

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import DemoSessionAuth, LoginAttemptLimiter, WorkspaceAuthStore, SESSION_COOKIE
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



def test_A20_token_only_session_status_matches_private_media_access(tmp_path):
    """Token mode must never tell an anonymous browser it is signed in."""
    settings = _demo_settings(tmp_path)
    settings.demo_username = ""
    settings.demo_password = ""
    settings.api_token = "token-mode-" + "q" * 42
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        anonymous = client.get("/api/v1/auth/session")
        assert anonymous.status_code == 200, anonymous.text
        assert anonymous.json()["authenticated"] is False
        assert client.get("/api/v1/dashboard").status_code == 401
        # Permission check happens before a non-existent asset can be probed.
        assert client.get("/api/v1/image-assets/non-existent/file").status_code == 401
        headers = {"Authorization": f"Bearer {settings.api_token}"}
        authenticated = client.get("/api/v1/auth/session", headers=headers)
        assert authenticated.status_code == 200, authenticated.text
        assert authenticated.json()["authenticated"] is True
        assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
        assert client.get("/api/v1/image-assets/non-existent/file", headers=headers).status_code != 401


def test_logout_revokes_copied_cookie_even_after_application_restart(tmp_path):
    """A06: clearing the browser cookie cannot leave a stolen replay valid."""
    settings = _demo_settings(tmp_path)
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert login.status_code == 200
        copied = login.cookies.get(SESSION_COOKIE)
        assert copied
        assert client.get("/api/v1/dashboard").status_code == 200
        assert client.post("/api/v1/auth/logout", json={}).status_code == 200
        client.cookies.set(SESSION_COOKIE, copied, domain="crm.test", path="/")
        assert client.get("/api/v1/dashboard").status_code == 401

    with TestClient(create_app(settings), base_url="https://crm.test") as restarted:
        restarted.cookies.set(SESSION_COOKIE, copied, domain="crm.test", path="/")
        assert restarted.get("/api/v1/dashboard").status_code == 401


def test_failed_revocation_cannot_report_successful_logout(tmp_path, monkeypatch):
    """An unavailable revocation store must not pretend a copied cookie died."""
    settings = _demo_settings(tmp_path)
    with TestClient(
        create_app(settings), base_url="https://crm.test", raise_server_exceptions=False,
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert login.status_code == 200

        def database_unavailable(_store, _token):
            raise RuntimeError("revocation storage unavailable")

        monkeypatch.setattr(WorkspaceAuthStore, "revoke", database_unavailable)
        logout = client.post("/api/v1/auth/logout", json={})
        assert logout.status_code >= 500
        assert client.get("/api/v1/dashboard").status_code == 200


def test_revoking_one_workspace_session_does_not_revoke_a_second(tmp_path):
    """One browser logging out must not log out every other owner session."""
    path = tmp_path / "sessions.db"
    auth = WorkspaceAuthStore(path, session_secret="s" * 48, session_hours=2)
    identity = auth.create(
        username="owner", workspace_id="local", password="long-safe-password",
    )
    first = auth.issue(identity)
    second = auth.issue(identity)
    assert first != second
    assert auth.verify(first) is not None
    assert auth.verify(second) is not None
    assert auth.revoke(first) is True
    assert auth.revoke(first) is False
    assert auth.verify(first) is None
    assert auth.verify(second) is not None

    reopened = WorkspaceAuthStore(path, session_secret="s" * 48, session_hours=2)
    assert reopened.verify(first) is None
    assert reopened.verify(second) is not None
    import hashlib
    import sqlite3
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT token_digest FROM workspace_revoked_sessions").fetchall()
    assert rows == [(hashlib.sha256(first.encode("utf-8")).hexdigest(),)]
    assert first not in str(rows)




def test_api_logout_revokes_only_current_session(tmp_path):
    """A06: revoking one browser's cookie must not revoke another live login."""
    settings = _demo_settings(tmp_path)
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        first = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert first.status_code == 200
        first_token = first.cookies.get(SESSION_COOKIE)
        assert first_token

        second = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert second.status_code == 200
        second_token = second.cookies.get(SESSION_COOKIE)
        assert second_token and second_token != first_token

        assert client.get("/api/v1/dashboard").status_code == 200
        assert client.post("/api/v1/auth/logout", json={}).status_code == 200

        client.cookies.set(SESSION_COOKIE, second_token, domain="crm.test", path="/")
        assert client.get("/api/v1/dashboard").status_code == 401

        client.cookies.set(SESSION_COOKIE, first_token, domain="crm.test", path="/")
        assert client.get("/api/v1/dashboard").status_code == 200


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
    from offsetx_apollo_builder.api.app import is_public_api_path

    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        failures = []
        for route in client.app.routes:
            path = getattr(route, "path", "")
            methods = sorted(
                method
                for method in (getattr(route, "methods", set()) or set())
                if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            )
            if not path.startswith("/api/"):
                continue
            for method in methods:
                if is_public_api_path(_route_path(path), method):
                    continue
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
        (
            "/api/v1/companions",
            {"name": "x", "instructions": "ok", "unexpected": "SECRET-SHOULD-NOT-ECHO"},
        ),
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
        assert "secret-should-not-echo" not in body



def test_parameterised_public_allowlist_does_not_leak_to_nested_routes():
    from offsetx_apollo_builder.api.app import is_public_api_path

    assert is_public_api_path("/api/v1/email/unsubscribe/signed-token")
    assert not is_public_api_path("/api/v1/email/unsubscribe/")
    assert not is_public_api_path("/api/v1/email/unsubscribe/token/admin")
    assert is_public_api_path("/api/v1/email-delivery/events/ses/sns")
    assert not is_public_api_path("/api/v1/email-delivery/events/ses/sns/debug")


def test_generic_value_error_never_reflects_sensitive_input(tmp_path):
    settings = _demo_settings(tmp_path)
    settings.api_token = "a" * 40
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        # This route performs domain validation after Pydantic has accepted the
        # body. The rejected address must not be reflected by the catch-all
        # ValueError handler.
        response = client.post(
            "/api/v1/email-delivery/suppressions",
            headers={"X-Offsetx-Token": settings.api_token},
            json={
                "email": "SECRET-SHOULD-NOT-ECHO",
                "reason": "operator",
            },
        )
        assert response.status_code == 422
        assert "secret-should-not-echo" not in response.text.lower()
        assert "traceback" not in response.text.lower()


@pytest.mark.parametrize("foreign", [
    {"Origin": "https://evil.example"},
    {"Origin": "null"},
    {"Origin": "https://crm.test.evil.example"},
    {"Origin": "http://crm.test"},
    {"Origin": "https://crm.test:444"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Origin": "https://crm.test", "Sec-Fetch-Site": "cross-site"},
])
def test_D456_cookie_unsafe_writes_refuse_foreign_browser_origins(tmp_path, foreign):
    """A login cookie must not approve mutations from a different site."""
    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        assert client.post("/api/v1/auth/login", json={
            "username": "demo-owner", "password": "temporary-password-123",
        }).status_code == 200
        rejected = client.post("/api/v1/auth/logout", json={}, headers=foreign)
        assert rejected.status_code == 403, (foreign, rejected.text)
        assert "origin" in rejected.text.lower() or "site" in rejected.text.lower()
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True
        assert client.post("/api/v1/auth/logout", json={},
                           headers={"Origin": "https://crm.test"}).status_code == 200


def test_D456_loopback_development_and_token_clients_still_work(tmp_path):
    settings = _demo_settings(tmp_path)
    settings.host = "127.0.0.1"
    with TestClient(create_app(settings), base_url="http://localhost:8766") as client:
        assert client.post("/api/v1/auth/login", json={
            "username": "demo-owner", "password": "temporary-password-123",
        }).status_code == 200
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True
        assert client.post(
            "/api/v1/auth/logout", json={},
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-site"},
        ).status_code == 200
    settings = _demo_settings(tmp_path / "token")
    settings.demo_username = ""
    settings.demo_password = ""
    settings.api_token = "external-client-" + "b" * 32
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        response = client.post(
            "/api/v1/memory", json={"content": "A sourced fact for the team."},
            headers={"Authorization": "Bearer " + settings.api_token,
                     "Origin": "https://evil.example"},
        )
        assert response.status_code == 201, response.text

@pytest.mark.parametrize("host,may_print", [
    ("127.0.0.1", True),
    ("localhost", True),
    ("0.0.0.0", False),
    ("::", False),
])
def test_web_cli_does_not_print_api_token_on_public_bind(
    tmp_path, monkeypatch, capsys, host, may_print,
):
    """D-491: a publicly bound Render process must not leak API tokens in logs.

    Token-only local loopback installs may still show the token to their
    interactive owner. A process reachable off-host cannot safely print it.
    """
    from offsetx_apollo_builder import web_cli

    # The local-loopback cases must behave the same under Render build CI.
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.setattr(web_cli.os, "isatty", lambda fd: fd == 1)
    settings = _demo_settings(tmp_path)
    settings.host = host
    settings.api_token = "TEST-PRIVATE-API-TOKEN-" + "a" * 48
    settings.demo_username = ""
    settings.demo_password = ""
    settings.session_secret = ""
    monkeypatch.setattr(
        web_cli.AppSettings, "from_env", classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(web_cli, "create_app", lambda given: object())
    run_calls = []
    monkeypatch.setattr(
        web_cli.uvicorn, "run",
        lambda app, **kwargs: run_calls.append(kwargs),
    )

    assert web_cli.main([]) == 0
    captured = capsys.readouterr()
    assert (settings.api_token in captured.out) is may_print
    assert settings.api_token not in captured.err
    assert len(run_calls) == 1 and run_calls[0]["host"] == host


def test_web_cli_never_logs_api_token_in_render_environment(
    tmp_path, monkeypatch, capsys,
):
    """D-491: Render log sinks stay secret-free even with a loopback bind."""
    from offsetx_apollo_builder import web_cli

    settings = _demo_settings(tmp_path)
    settings.host = "127.0.0.1"
    settings.api_token = "TEST-PRIVATE-RENDER-TOKEN-" + "r" * 48
    settings.demo_username = ""
    settings.demo_password = ""
    settings.session_secret = ""
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "isolated-qa.onrender.com")
    monkeypatch.setattr(
        web_cli.AppSettings, "from_env", classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(web_cli, "create_app", lambda given: object())
    monkeypatch.setattr(web_cli.uvicorn, "run", lambda app, **kwargs: None)

    assert web_cli.main([]) == 0
    captured = capsys.readouterr()
    assert settings.api_token not in captured.out
    assert settings.api_token not in captured.err


def test_web_cli_does_not_print_api_token_when_stdout_is_a_pipe(
    tmp_path, monkeypatch, capsys,
):
    """D-492: even localhost can log a bearer credential under a supervisor."""
    from offsetx_apollo_builder import web_cli

    settings = _demo_settings(tmp_path)
    settings.host = "127.0.0.1"
    settings.api_token = "TEST-PRIVATE-PIPE-TOKEN-" + "p" * 48
    settings.demo_username = ""
    settings.demo_password = ""
    settings.session_secret = ""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.setattr(web_cli.os, "isatty", lambda fd: False)
    monkeypatch.setattr(
        web_cli.AppSettings, "from_env", classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(web_cli, "create_app", lambda given: object())
    monkeypatch.setattr(web_cli.uvicorn, "run", lambda app, **kwargs: None)

    assert web_cli.main([]) == 0
    captured = capsys.readouterr()
    assert settings.api_token not in captured.out
    assert settings.api_token not in captured.err



@pytest.mark.parametrize("leak_source", ["message", "location", "type"])
def test_A22_validation_errors_never_reflect_sensitive_input(tmp_path, leak_source):
    """Untrusted validator messages and dynamic keys must not echo credentials.

    This runs through real FastAPI routing, authentication, and the app's
    RequestValidationError handler. The synthetic route only supplies the
    adversarial validator error; production response handling is unchanged.
    """
    from fastapi.exceptions import RequestValidationError

    canary = "sk-proj-SENSITIVE-CANARY-DO-NOT-RETURN"
    app = create_app(_demo_settings(tmp_path))

    async def malicious_validation_error():
        location = ("body", canary if leak_source == "location" else "api_key")
        message = (
            f"Value error, rejected credential {canary}"
            if leak_source == "message"
            else "Value error, invalid field"
        )
        raise RequestValidationError([{
            "type": f"custom_{canary}" if leak_source == "type" else "value_error",
            "loc": location,
            "msg": message,
            "input": canary,
        }])

    app.add_api_route(
        "/api/v1/_audit_validation_redaction",
        malicious_validation_error,
        methods=["POST"],
    )
    with TestClient(app, base_url="https://crm.test") as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        )
        assert login.status_code == 200
        response = client.post("/api/v1/_audit_validation_redaction", json={})
        assert response.status_code == 422, response.text
        assert canary not in response.text
        assert "detail" in response.json()
        assert len(response.text) < 3000



def test_A22_validation_path_indexes_keep_the_existing_string_contract(tmp_path):
    """A22 safety must not change JSON location element types for list inputs."""
    from fastapi.exceptions import RequestValidationError

    app = create_app(_demo_settings(tmp_path))

    async def bad_index():
        raise RequestValidationError([{
            "type": "int_parsing", "loc": ("body", 7),
            "msg": "Input should be a valid integer", "input": "not-an-int",
        }])

    app.add_api_route("/api/v1/_audit_validation_index", bad_index, methods=["POST"])
    with TestClient(app, base_url="https://crm.test") as client:
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        ).status_code == 200
        response = client.post("/api/v1/_audit_validation_index", json={})
        assert response.status_code == 422
        assert response.json()["errors"][0]["location"] == ["7"]


@pytest.mark.parametrize("private_key", [
    "customer-private-ref-78540",
    "sk-proj-SENSITIVE-CANARY-DO-NOT-RETURN",
])
def test_A22_unexpected_keyerror_does_not_echo_private_identifiers(tmp_path, private_key):
    """A22/D-515: 404 responses must not expose arbitrary KeyError arguments."""
    app = create_app(_demo_settings(tmp_path))

    async def missing_lookup():
        raise KeyError(private_key)

    app.add_api_route("/api/v1/_audit_missing_key", missing_lookup, methods=["GET"])
    with TestClient(app, base_url="https://crm.test") as client:
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "demo-owner", "password": "temporary-password-123"},
        ).status_code == 200
        response = client.get("/api/v1/_audit_missing_key")
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "Requested resource was not found."}
        assert private_key not in response.text


@pytest.mark.parametrize("header", [b"x-offsetx-token", b"authorization"])
def test_malformed_non_ascii_api_credential_is_401_not_500(tmp_path, header):
    settings = _demo_settings(tmp_path)
    settings.api_token = "valid-install-token-" + "q" * 40
    with TestClient(create_app(settings), base_url="https://crm.test") as client:
        value = b"caf\xe9" if header == b"x-offsetx-token" else b"Bearer caf\xe9"
        response = client.get("/api/v1/dashboard", headers=[(header, value)])
        assert response.status_code == 401
        assert response.json() == {"detail": "CRM login required"}
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/dashboard", headers={"X-Offsetx-Token": settings.api_token}).status_code == 200


def test_malformed_session_signature_refused_before_database(tmp_path):
    from offsetx_apollo_builder.api.auth import constant_time_text_equal

    assert not constant_time_text_equal("caf\xe9", "ascii-token")
    assert constant_time_text_equal("valid", "valid")
    assert not constant_time_text_equal("bad", "valid")
    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        # Raw header bytes simulate malformed input reaching ASGI.
        response = client.get("/api/v1/dashboard", headers=[
            (b"cookie", SESSION_COOKIE.encode() + b"=YWJj.caf\xe9"),
        ])
        assert response.status_code == 401
        assert client.app.state.workspace_auth.verify("YWJj.caf\xe9") is None
    auth = DemoSessionAuth(username="demo", password="long-demo-password",
                           session_secret="x" * 32, session_hours=1)
    assert auth.verify("YWJj.caf\xe9") is None


@pytest.mark.parametrize("path,allowed,refused", [
    ("/api/v1/meta", "GET", "POST"),
    ("/api/v1/auth/session", "GET", "DELETE"),
    ("/api/v1/auth/login", "POST", "GET"),
    ("/api/v1/auth/logout", "POST", "GET"),
    ("/api/v1/email-delivery/events/ses/sns", "POST", "GET"),
    ("/api/v1/email/unsubscribe/synthetic-token", "POST", "PATCH"),
])
def test_public_exemption_requires_exact_method(tmp_path, path, allowed, refused):
    from offsetx_apollo_builder.api.app import is_public_api_path
    assert is_public_api_path(path, allowed)
    assert not is_public_api_path(path, refused)
    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        assert client.request(refused, path).status_code == 401


def test_rejected_host_not_reflected(tmp_path):
    with TestClient(create_app(_demo_settings(tmp_path)), base_url="https://crm.test") as client:
        response = client.get("/api/v1/meta", headers={"Host": "private-canary.example"})
        assert response.status_code == 421
        assert "private-canary" not in response.text


@pytest.mark.parametrize("status", [400, 409, 422])
def test_wrapped_credential_error_never_returns_secret(tmp_path, status):
    from fastapi import HTTPException
    app = create_app(_demo_settings(tmp_path))
    canary = "sk-synthetic-canary-abcdefghijklmnopqrstuvwxyz"

    async def refused():
        raise HTTPException(status, detail="Rejected credential " + canary)

    app.add_api_route("/api/v1/_audit_wrapped_error", refused, methods=["POST"])
    with TestClient(app, base_url="https://crm.test") as client:
        assert client.post("/api/v1/auth/login", json={
            "username": "demo-owner", "password": "temporary-password-123",
        }).status_code == 200
        response = client.post("/api/v1/_audit_wrapped_error", json={})
        assert response.status_code == status
        assert canary not in response.text
