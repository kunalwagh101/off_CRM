"""Safe, unauthenticated checks against a disposable Render CRM host."""
from __future__ import annotations

import json
import pytest

from scripts.live import remote_render_smoke as smoke


@pytest.mark.parametrize("unsafe", [
    "http://qa.onrender.com",
    "https://qa.onrender.com.evil.example",
    "https://user:secret@qa.onrender.com",
    "https://qa.onrender.com:443",
    "https://qa.onrender.com:invalid-port",
    "https://qa.onrender.com/path",
    "https://127.0.0.1",
])
def test_render_smoke_refuses_untrusted_urls(unsafe, monkeypatch):
    calls = []
    monkeypatch.setattr(smoke, "_request", lambda *a, **kw: calls.append((a, kw)))
    with pytest.raises(smoke.SmokeError):
        smoke.run_smoke(unsafe)
    assert calls == []


def _fake_responses(authenticated=False, dashboard_code=401, login_code=401):
    return {
        ("GET", "/"): (200, {"content-type": "text/html"}, b"<!DOCTYPE html><html></html>"),
        ("GET", "/health/ready"): (200, {"content-type": "application/json"}, b'{"status":"ready"}'),
        ("GET", "/api/v1/auth/session"): (
            200, {"content-type": "application/json"},
            json.dumps({"configured": True, "authenticated": authenticated, "username": "",
                        "workspace_id": "", "expires_at": None}).encode(),
        ),
        ("GET", "/api/v1/dashboard"): (dashboard_code, {}, b""),
        ("POST", "/api/v1/auth/login"): (login_code, {}, b""),
    }


def test_render_smoke_checks_real_unauthenticated_boundaries(monkeypatch):
    responses = _fake_responses()
    observed = []

    def fake_request(base_url, path, *, method="GET", data=None):
        observed.append((method, path))
        return responses[(method, path)]

    monkeypatch.setattr(smoke, "_request", fake_request)
    checks = smoke.run_smoke("https://off-crm-qa.onrender.com")
    assert set(checks) == {"root", "ready", "anonymous_session", "private_dashboard", "wrong_login"}
    assert observed == list(responses)
    

@pytest.mark.parametrize("overrides", [
    {"authenticated": True},
    {"dashboard_code": 200},
    {"login_code": 200},
])
def test_render_smoke_rejects_false_success_or_exposed_private_api(monkeypatch, overrides):
    responses = _fake_responses(**overrides)
    monkeypatch.setattr(
        smoke, "_request",
        lambda base_url, path, *, method="GET", data=None: responses[(method, path)],
    )
    with pytest.raises(smoke.SmokeError):
        smoke.run_smoke("https://off-crm-qa.onrender.com")
