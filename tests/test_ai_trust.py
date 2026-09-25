"""Trust is the owner's to change, per provider and per model (S-06.02.33).

The rule (DD-65): a model's own setting wins; else the provider's, which never
lifts a model past the cap set by who built it; else the default. Lowering needs
nothing; raising needs a typed reason, stored with who and when. No trust
setting opens the mailbox.

NVIDIA is the case throughout: tier B by default, hosting US-built models at B
and Chinese-built ones (``deepseek-ai/deepseek-r1``) capped at C.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.api.app import create_app
from test_ai_api import API, _settings

US_MODEL = "meta/llama-3.1-70b-instruct"
CN_MODEL = "deepseek-ai/deepseek-r1"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as test_client:
        yield test_client


def _trust(client, body):
    return client.post(f"{API}/ai/providers/nvidia/trust", json=body)


def _nvidia(client) -> dict:
    rows = client.get(f"{API}/ai/providers").json()["providers"]
    return next(row for row in rows if row["id"] == "nvidia")


def _model_tier(row: dict, model_id: str) -> str:
    return next(model for model in row["available_models"] if model["id"] == model_id)["tier"]


def test_lowering_a_provider_applies_to_its_models_with_no_reason_asked(client):
    assert _trust(client, {"tier": "C"}).status_code == 200
    row = _nvidia(client)
    assert row["effective_tier"] == "C"
    assert _model_tier(row, US_MODEL) == "C"


def test_raising_needs_a_typed_reason_and_records_who_and_when(client):
    refused = _trust(client, {"tier": "A"})
    assert refused.status_code == 400
    assert "reason" in refused.json()["detail"]["message"]
    assert _nvidia(client)["effective_tier"] == "B"

    accepted = _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    assert accepted.status_code == 200, accepted.text
    row = _nvidia(client)
    assert row["effective_tier"] == "A"
    assert row["override"]["trust_reason"] == "Our data agreement with NVIDIA covers this"
    assert row["override"]["trust_decided_by"] == "local"
    assert row["override"]["trust_decided_at"]


def test_a_models_own_setting_wins_over_the_providers(client):
    _trust(client, {"tier": "C"})
    raised = _trust(client, {"tier": "B", "model_id": US_MODEL, "reason": "Llama is built and hosted in the US"})
    assert raised.status_code == 200, raised.text
    row = _nvidia(client)
    assert row["effective_tier"] == "C"
    assert _model_tier(row, US_MODEL) == "B"

    _trust(client, {"tier": ""})
    assert _trust(client, {"tier": "D", "model_id": US_MODEL}).status_code == 200
    row = _nvidia(client)
    assert row["effective_tier"] == "B"
    assert _model_tier(row, US_MODEL) == "D"


def test_raising_a_model_needs_a_reason_too(client):
    refused = _trust(client, {"tier": "B", "model_id": CN_MODEL})
    assert refused.status_code == 400
    assert _model_tier(_nvidia(client), CN_MODEL) == "C"


def test_a_provider_raise_never_lifts_a_model_capped_by_who_built_it(client):
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    row = _nvidia(client)
    assert _model_tier(row, US_MODEL) == "A"
    assert _model_tier(row, CN_MODEL) == "C"  # only its own setting can lift it

    _trust(client, {"tier": "B", "model_id": CN_MODEL, "reason": "Self-hosted weights; nothing goes to the developer"})
    assert _model_tier(_nvidia(client), CN_MODEL) == "B"


def test_no_trust_setting_opens_the_mailbox(client):
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    app = client.app
    settings = app.state.ai_workspaces.egress_settings("local")
    resolved = app.state.ai_registry.resolve("nvidia", model_id=US_MODEL, override=settings.overrides["nvidia"])
    assert resolved.tier.value == "A"
    assert not resolved.permits(DataClass.MAILBOX)


def test_routing_follows_a_lowered_trust(client):
    client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-test", "model_ids": [US_MODEL]})
    _trust(client, {"tier": "D"})
    app = client.app
    settings = app.state.ai_workspaces.egress_settings("local")
    permitted, _ = app.state.ai_registry.candidates_for(
        DataClass.PUBLIC,
        enabled_ids=["nvidia"],
        overrides=settings.overrides,
        enabled_models=settings.enabled_models,
    )
    assert permitted == []


def test_the_connect_ceiling_follows_a_changed_trust(client):
    _trust(client, {"tier": "C"})
    connected = client.post(
        f"{API}/ai/providers/nvidia/connect",
        json={"api_key": "nvapi-test", "data_policy": "standard"},
    ).json()
    assert connected["tier"] == "C"
    assert connected["policy_was_clamped"] is True
    assert connected["provider"]["data_policy"] == "pseudonymous"


def test_raising_to_full_access_keeps_the_per_model_settings(client):
    _trust(client, {"tier": "D", "model_id": CN_MODEL})
    client.post(
        f"{API}/ai/providers/nvidia/override",
        json={"data_policy": "full", "allow_above_ceiling": True, "reason": "Signed a DPA"},
    )
    assert _model_tier(_nvidia(client), CN_MODEL) == "D"


def test_clearing_returns_to_the_default(client):
    _trust(client, {"tier": "C"})
    _trust(client, {"tier": "D", "model_id": US_MODEL})
    _trust(client, {"tier": "", "model_id": US_MODEL})
    _trust(client, {"tier": ""})
    row = _nvidia(client)
    assert row["effective_tier"] == "B"
    assert _model_tier(row, US_MODEL) == "B"


def test_a_model_the_provider_does_not_list_is_refused(client):
    answer = _trust(client, {"tier": "D", "model_id": "nobody/unknown-model"})
    assert answer.status_code == 400


def test_who_decided_is_the_login_not_what_the_request_claims(client):
    """The override route stored whatever `decided_by` the request sent, so any
    caller could put a colleague's name on a decision (D-152)."""
    client.post(
        f"{API}/ai/providers/nvidia/override",
        json={"data_policy": "full", "allow_above_ceiling": True, "reason": "Signed a DPA", "decided_by": "someone-else"},
    )
    assert _nvidia(client)["override"]["decided_by"] == "local"


def test_a_raise_without_a_reason_says_so_in_a_way_the_screen_can_act_on(client):
    """The screen asks for the reason only when the server says one is needed,
    so the raise-or-lower rule lives in one place (DD-65)."""
    detail = _trust(client, {"tier": "A"}).json()["detail"]
    assert detail["error"] == "reason_required"
    assert "Type why" in detail["message"]
