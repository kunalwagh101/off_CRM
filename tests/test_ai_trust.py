"""Trust is the owner's to change, per provider and per model (S-06.02.33).

The rule (DD-65, amended): a model is trusted as much as its provider, or less —
its own setting, else the cap set by who built it, can only lower that. Lowering
needs nothing; raising needs a typed reason, stored with who and when. No trust
setting opens the mailbox. The owner's full-data grant reaches only models
trusted at their provider's default or higher (DD-67).

NVIDIA is the case throughout: tier B by default, hosting US-built models at B
and Chinese-built ones (``deepseek-ai/deepseek-v4.1-flash``) capped at C.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.api.app import create_app
from test_ai_api import API, _settings

US_MODEL = "meta/llama-3.2-90b-vision-instruct"
CN_MODEL = "deepseek-ai/deepseek-v4.1-flash"


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


def test_a_model_can_be_trusted_less_than_its_provider_never_more(client):
    """The host sees every byte a model on it is sent, so a model's own
    setting lowers it, or lifts it past its origin cap, but never above its
    provider (DD-65 as amended after the review of 2026-09-25)."""
    assert _trust(client, {"tier": "D", "model_id": US_MODEL}).status_code == 200
    row = _nvidia(client)
    assert row["effective_tier"] == "B"
    assert _model_tier(row, US_MODEL) == "D"

    _trust(client, {"tier": "", "model_id": US_MODEL})
    _trust(client, {"tier": "C"})
    above = _trust(client, {"tier": "B", "model_id": US_MODEL, "reason": "Llama is built in the US"})
    assert above.status_code == 400
    assert "provider" in above.json()["detail"]["message"]
    assert _model_tier(_nvidia(client), US_MODEL) == "C"


def test_blocking_a_provider_blocks_every_model_under_it(client):
    """A model's own setting kept it routable after its provider was blocked."""
    client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-test", "model_ids": [US_MODEL]})
    assert _trust(client, {"tier": "B", "model_id": US_MODEL}).status_code == 200
    _trust(client, {"tier": "D"})
    assert _model_tier(_nvidia(client), US_MODEL) == "D"
    app = client.app
    settings = app.state.ai_workspaces.egress_settings("local")
    permitted, _ = app.state.ai_registry.candidates_for(
        DataClass.PUBLIC, enabled_ids=["nvidia"], overrides=settings.overrides,
        enabled_models=settings.enabled_models,
    )
    assert permitted == []


def test_a_raise_never_stands_without_its_reason(client):
    """Raise the provider with a reason, set a model to match, clear the
    provider: the model must not keep the raised tier with no reason."""
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    assert _trust(client, {"tier": "A", "model_id": US_MODEL}).status_code == 200
    _trust(client, {"tier": ""})
    assert _model_tier(_nvidia(client), US_MODEL) == "B"


def test_withdrawing_full_access_keeps_the_trust_settings(client):
    """The card's reset link posted an empty override, which deleted the
    owner's blocks along with the grant."""
    granted = client.post(f"{API}/ai/providers/nvidia/override",
                          json={"data_policy": "full", "allow_above_ceiling": True, "reason": "Signed a DPA"})
    assert granted.status_code == 200, granted.text
    _trust(client, {"tier": "C"})
    _trust(client, {"tier": "D", "model_id": CN_MODEL})
    client.post(f"{API}/ai/providers/nvidia/override", json={})
    assert not _nvidia(client)["override"].get("allow_above_ceiling")
    row = _nvidia(client)
    assert row["effective_tier"] == "C"
    assert _model_tier(row, CN_MODEL) == "D"


def test_a_full_access_grant_never_lifts_what_a_limited_model_sends(client):
    client.post(f"{API}/ai/providers/nvidia/override",
                json={"data_policy": "full", "allow_above_ceiling": True, "reason": "Signed a DPA"})
    _trust(client, {"tier": "C", "model_id": US_MODEL})
    app = client.app
    override = app.state.ai_workspaces.egress_settings("local").overrides["nvidia"]
    resolve = app.state.ai_registry.resolve
    assert resolve("nvidia", model_id="nvidia/nemotron-3.5-lightning-30b-a3b", override=override).policy.value == "full"
    assert resolve("nvidia", model_id=US_MODEL, override=override).policy.value == "pseudonymous"
    assert resolve("nvidia", model_id=CN_MODEL, override=override).policy.value == "pseudonymous"


def test_every_trust_change_is_kept_with_who_when_and_why(client):
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    _trust(client, {"tier": ""})
    history = _nvidia(client)["override"]["trust_history"]
    assert [entry["tier"] for entry in history] == ["A", ""]
    assert history[0]["reason"] == "Our data agreement with NVIDIA covers this"
    assert all(entry["by"] == "local" and entry["at"] for entry in history)


def test_an_unknown_model_stays_blocked_whatever_its_own_setting(client):
    from offsetx_apollo_builder.ai.registry import ProviderOverride
    from offsetx_apollo_builder.ai.tiers import TrustTier

    override = ProviderOverride(provider_id="nvidia", model_tiers={"nobody/unknown-model": TrustTier.A})
    assert client.app.state.ai_registry.resolve("nvidia", model_id="nobody/unknown-model", override=override).tier.value == "D"


def test_a_developers_own_api_is_capped_by_where_its_models_were_built(client):
    """DeepSeek's own models listed no origin cap, so one provider raise lifted
    them to A while NVIDIA's copy of the same model stayed C."""
    client.post(f"{API}/ai/providers/deepseek/trust", json={"tier": "A", "reason": "Signed their enterprise terms"})
    rows = client.get(f"{API}/ai/providers").json()["providers"]
    deepseek = next(row for row in rows if row["id"] == "deepseek")
    assert {model["tier"] for model in deepseek["available_models"]} == {"C"}


def test_saving_the_model_list_keeps_the_caps_and_what_is_sent(client):
    """The Models panel posts only the models; Connect reset the caps to none."""
    client.post(f"{API}/ai/providers/nvidia/connect", json={
        "api_key": "nvapi-test", "data_policy": "minimal", "requests_per_day": 200, "max_spend_usd_per_day": 5})
    client.post(f"{API}/ai/providers/nvidia/connect", json={"model_ids": [US_MODEL, "nvidia/nemotron-3.5-lightning-30b-a3b"]})
    row = _nvidia(client)
    assert (row["requests_per_day"], row["max_spend_usd_per_day"], row["data_policy"]) == (200, 5.0, "minimal")


def test_a_model_connected_from_the_live_catalogue_can_have_its_trust_changed(client):
    discovered = "meta/llama-3.2-3b-instruct"
    client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-test", "model_ids": [US_MODEL, discovered]})
    assert discovered in [model["id"] for model in _nvidia(client)["trust_models"]]
    assert _trust(client, {"tier": "C", "model_id": discovered}).status_code == 200


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
    # What leaves follows the lowered trust; the owner's own choice is kept,
    # uncut, for when trust is restored — storing the cut value lost it
    # (D-176), so nothing was cut from the choice and none is reported.
    assert _nvidia(client)["sends"] == "pseudonymous"
    assert connected["provider"]["data_policy"] == "standard"
    assert connected["policy_was_clamped"] is False
    # A raise lifts what may be stored: DeepSeek's own Standard is kept.
    client.post(f"{API}/ai/providers/deepseek/trust", json={"tier": "B", "reason": "Signed their enterprise terms"})
    raised = client.post(f"{API}/ai/providers/deepseek/connect",
                         json={"api_key": "sk-test", "data_policy": "standard"}).json()
    assert (raised["provider"]["data_policy"], raised["policy_was_clamped"]) == ("standard", False)


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


def test_find_models_shows_the_owners_trust_not_the_default(client, monkeypatch):
    from offsetx_apollo_builder.ai.discovery import DiscoveredModel, DiscoveryResult
    from offsetx_apollo_builder.api import app as app_module

    monkeypatch.setattr(app_module, "discover_models", lambda *a, **k: DiscoveryResult(
        provider_id="nvidia", provider_name="NVIDIA NIM",
        models=[DiscoveredModel(id=US_MODEL, tier="B", known=True, in_config=True)],
    ))
    _trust(client, {"tier": "C"})
    found = client.post(f"{API}/ai/providers/nvidia/discover-models").json()
    assert [model["tier"] for model in found["models"]] == ["C"]


# ── Second review of 2026-09-25: the full-data grant, disconnect, history ──


def _connect(client, **body):
    answer = client.post(f"{API}/ai/providers/nvidia/connect",
                         json={"api_key": "nvapi-test", "model_ids": [US_MODEL, CN_MODEL], **body})
    assert answer.status_code == 200, answer.text
    return answer.json()


def _grant(client, **body):
    return client.post(f"{API}/ai/providers/nvidia/override", json={
        "data_policy": "full", "allow_above_ceiling": True, "reason": "Signed a DPA with NVIDIA", **body})


def _sends(client, model_id: str) -> tuple[str, str]:
    """(tier, policy) the broker's router gives this one model for person-level
    data. The plan screen hides lower-tier models from failover, so it is asked
    one model at a time, with the workspace's own stored settings."""
    app = client.app
    settings = app.state.ai_workspaces.egress_settings("local")
    permitted, _ = app.state.ai_registry.candidates_for(
        DataClass.PERSON_PUBLIC, enabled_ids=["nvidia"], overrides=settings.overrides,
        enabled_models={"nvidia": (model_id,)},
        policy_by_provider=settings.default_policy_by_provider,
    )
    [resolved] = permitted
    return resolved.tier.value, resolved.policy.value


def test_lowering_the_provider_never_raises_what_a_capped_model_is_sent(client):
    """D-167: the grant applied wherever a model's tier equalled its host's, so
    lowering NVIDIA to C handed the Chinese-built model the grant."""
    _connect(client, data_policy="standard")
    assert _grant(client).status_code == 200
    assert _sends(client, CN_MODEL) == ("C", "pseudonymous")
    assert _trust(client, {"tier": "C"}).status_code == 200
    assert _sends(client, CN_MODEL) == ("C", "pseudonymous")
    assert _sends(client, US_MODEL) == ("C", "pseudonymous")


def test_a_model_the_owner_lowered_never_gains_the_grant(client):
    _connect(client, data_policy="standard")
    _grant(client)
    _trust(client, {"tier": "C", "model_id": US_MODEL})
    assert _sends(client, US_MODEL) == ("C", "pseudonymous")
    _trust(client, {"tier": "C"})
    assert _sends(client, US_MODEL) == ("C", "pseudonymous")


def test_the_full_data_grant_really_sends_full_data(client):
    """D-171: Connect clamped what is sent to the tier's ceiling and ignored the
    grant, so "raised to full access" never sent more (BUILD_STATE §5.1). The
    grant decides what reaches the models it covers; the owner's own choice
    stays underneath it (D-176)."""
    _connect(client, data_policy="standard")
    assert _grant(client).status_code == 200
    assert _sends(client, US_MODEL) == ("B", "full")
    assert _sends(client, CN_MODEL) == ("C", "pseudonymous")
    row = _nvidia(client)
    assert (row["data_policy"], row["sends"], row["policy_ceiling"], row["grant_active"]) == (
        "standard", "full", "full", True)
    # The Models panel posts only the models; it must not undo the grant.
    kept = client.post(f"{API}/ai/providers/nvidia/connect", json={"model_ids": [US_MODEL, CN_MODEL]}).json()
    assert kept["policy_was_clamped"] is False and kept["provider"]["data_policy"] == "standard"
    assert _sends(client, US_MODEL) == ("B", "full")


def test_withdrawing_the_grant_returns_what_is_sent_to_the_ceiling(client):
    _connect(client, data_policy="standard")
    _grant(client)
    assert client.post(f"{API}/ai/providers/nvidia/override", json={}).status_code == 200
    row = _nvidia(client)
    assert (row["data_policy"], row["sends"], row["grant_active"]) == ("standard", "standard", False)
    assert _sends(client, US_MODEL) == ("B", "standard")


def test_lowering_the_provider_pauses_the_grant_and_its_default_resumes_it(client):
    _connect(client, data_policy="standard")
    _grant(client)
    _trust(client, {"tier": "C"})
    row = _nvidia(client)
    assert (row["grant_active"], row["sends"], row["policy_ceiling"]) == (False, "pseudonymous", "pseudonymous")
    _trust(client, {"tier": ""})
    assert _nvidia(client)["grant_active"] is True
    assert _sends(client, US_MODEL) == ("B", "full")


def test_a_grant_is_refused_where_it_could_change_nothing(client):
    _connect(client)
    _trust(client, {"tier": "D"})
    blocked = _grant(client)
    assert blocked.status_code == 400
    assert "blocked" in blocked.json()["detail"]["message"]
    _trust(client, {"tier": "C"})
    lowered = _grant(client)
    assert lowered.status_code == 400
    assert "default" in lowered.json()["detail"]["message"]
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    already = _grant(client)
    assert already.status_code == 400
    assert "already" in already.json()["detail"]["message"]
    assert not _nvidia(client)["override"].get("allow_above_ceiling")


def test_the_card_shows_the_limit_the_owners_trust_sets(client):
    """D-172: the card's ceiling and data classes came from the config tier,
    so after a trust change its "Tier C allows up to Standard" was false."""
    _trust(client, {"tier": "C"})
    row = _nvidia(client)
    assert (row["policy_ceiling"], row["permitted_data_classes"], row["receives_nothing"]) == (
        "pseudonymous", ["person_public", "public"], False)
    _trust(client, {"tier": "D"})
    assert _nvidia(client)["receives_nothing"] is True


def test_disconnect_takes_the_record_and_the_key_together(client, monkeypatch):
    """D-169: the record and the key went in two lock windows; a Models-panel
    save landing between them left a connected provider with no key. The save
    is run right after disconnect's first locked write returns — the gap, when
    there were two — so the test fails for two windows, whatever they call."""
    store = client.app.state.ai_workspaces
    _connect(client)
    real = store._update_workspace
    seen: dict[str, str] = {}

    def models_panel_save_in_the_gap(workspace_id, mutate):
        saved = real(workspace_id, mutate)
        if "fired" not in seen:
            seen["fired"] = "yes"
            try:
                store.connect_provider(workspace_id, "nvidia", model_ids=[US_MODEL])
                seen["save"] = "accepted"
            except ValueError as exc:
                seen["save"] = str(exc)
        return saved

    monkeypatch.setattr(store, "_update_workspace", models_panel_save_in_the_gap)
    store.disconnect_provider("local", "nvidia")
    monkeypatch.undo()
    row = _nvidia(client)
    assert (row["connected"], row["has_key"]) == (False, False)
    assert "API key first" in seen["save"]


def test_a_click_that_changes_nothing_records_nothing(client):
    """D-170: every withdraw click on an untouched provider added a history
    entry to a record holding nothing else."""
    for _ in range(5):
        assert client.post(f"{API}/ai/providers/nvidia/override", json={}).status_code == 200
        assert _trust(client, {"tier": ""}).status_code == 200
        assert _trust(client, {"tier": "", "model_id": US_MODEL}).status_code == 200
    assert "nvidia" not in (client.app.state.ai_workspaces.raw("local").get("overrides") or {})
    _trust(client, {"tier": "C"})
    _trust(client, {"tier": "C"})
    history = _nvidia(client)["override"]["trust_history"]
    assert [entry["tier"] for entry in history] == ["C"]
    assert _nvidia(client)["override"]["provider_id"] == "nvidia"


def test_trust_history_and_reasons_are_bounded(client):
    """D-170: 2,000-character reasons x 100 entries x every provider sat in a
    document parsed on every request."""
    long = _trust(client, {"tier": "A", "reason": "x" * 501})
    assert long.status_code == 422
    assert "reason" in long.json()["detail"]
    for index in range(30):
        _trust(client, {"tier": "C" if index % 2 else "D"})
    assert len(_nvidia(client)["override"]["trust_history"]) == 20


# ── Third review of 2026-09-26: the owner's choice, per-model truth, bounds ──


def _models_panel_save(client):
    # What ModelPicker.tsx posts: the models, and the stored level.
    answer = client.post(f"{API}/ai/providers/nvidia/connect", json={
        "model_ids": [US_MODEL, CN_MODEL], "data_policy": _nvidia(client)["data_policy"]})
    assert answer.status_code == 200, answer.text


def test_returning_to_the_default_resumes_the_grant_after_a_save_made_while_paused(client):
    """D-176: the grant overwrote the owner's level with full, and a save made
    while it was paused stored the cut value, so after resuming the card said
    "granted" while Pseudonymous was sent."""
    _connect(client, data_policy="standard")
    assert _grant(client).status_code == 200
    _trust(client, {"tier": "C"})
    _models_panel_save(client)
    _trust(client, {"tier": ""})
    assert _nvidia(client)["grant_active"] is True
    assert _sends(client, US_MODEL) == ("B", "full")


def test_withdrawing_the_grant_stops_full_data_even_after_a_raise(client):
    """D-176: grant at Default trust, raise NVIDIA to Highest, withdraw: the
    grant's "full" had become the stored choice, and Highest allows full."""
    _connect(client, data_policy="standard")
    _grant(client)
    assert _trust(client, {"tier": "A", "reason": "Signed NVIDIA's EU terms"}).status_code == 200
    assert client.post(f"{API}/ai/providers/nvidia/override", json={}).status_code == 200
    assert _sends(client, US_MODEL) == ("A", "standard")


def test_a_save_made_while_trust_is_lowered_keeps_the_owners_choice(client):
    """D-176: Connect stored the level cut to a lowered ceiling as the owner's
    choice, so restoring trust sent less than the owner had chosen."""
    _connect(client, data_policy="standard")
    _trust(client, {"tier": "C"})
    _models_panel_save(client)
    assert _sends(client, US_MODEL) == ("C", "pseudonymous")
    _trust(client, {"tier": ""})
    assert _sends(client, US_MODEL) == ("B", "standard")


def test_sends_is_what_the_switched_on_models_are_sent(client):
    """D-179: "Sends" was worked out for the provider, not its models: with the
    only model lowered, it read Standard while Pseudonymous was sent."""
    client.post(f"{API}/ai/providers/nvidia/connect",
                json={"api_key": "nvapi-test", "model_ids": [US_MODEL], "data_policy": "standard"})
    _trust(client, {"tier": "C", "model_id": US_MODEL})
    row = _nvidia(client)
    assert (row["sends"], row["sends_varies"]) == ("pseudonymous", False)
    _connect(client, data_policy="standard")  # both models on: they differ
    row = _nvidia(client)
    assert (row["sends"], row["sends_varies"]) == ("pseudonymous", False)
    _trust(client, {"tier": "", "model_id": US_MODEL})
    row = _nvidia(client)
    assert (row["sends"], row["sends_varies"]) == ("standard", True)


def test_the_grant_is_refused_and_not_offered_where_no_switched_on_model_can_use_it(client):
    """D-179: with only the Chinese-built model on, the grant could change
    nothing, yet it was accepted and the card read "Sends: Full access"."""
    client.post(f"{API}/ai/providers/nvidia/connect",
                json={"api_key": "nvapi-test", "model_ids": [CN_MODEL], "data_policy": "standard"})
    assert _nvidia(client)["grant_offer"] is False
    refused = _grant(client)
    assert refused.status_code == 400
    assert "none of the models you switched on" in refused.json()["detail"]["message"].lower()
    _connect(client, data_policy="standard")
    assert _nvidia(client)["grant_offer"] is True


def test_the_card_says_why_a_grant_is_not_in_force(client):
    """D-179: a grant that reached no model was reported "paused while you trust
    it less than its default", even where the provider was at its default."""
    _connect(client, data_policy="standard")
    _grant(client)
    assert _nvidia(client)["grant_state"] == "active"
    _trust(client, {"tier": "C", "model_id": US_MODEL})
    assert _nvidia(client)["grant_state"] == "no_model"
    _trust(client, {"tier": "", "model_id": US_MODEL})
    _trust(client, {"tier": "C"})
    assert _nvidia(client)["grant_state"] == "provider_lowered"
    _trust(client, {"tier": "D"})
    assert _nvidia(client)["grant_state"] == "provider_blocked"


def test_the_card_describes_the_trust_the_owner_set(client):
    """Nit from the third review: the tier's label and rank stayed the config's."""
    _trust(client, {"tier": "C"})
    row = _nvidia(client)
    assert (row["tier"], row["label"]) == ("C", "Restricted")
    assert row["trust_tier"] == "B"  # config's own tier, for the default marker


def test_disconnect_disconnects_when_the_stored_keys_cannot_be_read(client):
    """D-178: with the key file unreadable, disconnect answered 500 and the
    provider stayed connected, and nothing on screen said what to do."""
    from cryptography.fernet import Fernet

    _connect(client)
    store = client.app.state.ai_workspaces
    store.key_path.write_bytes(Fernet.generate_key())
    assert client.post(f"{API}/ai/providers/nvidia/disconnect").status_code == 200
    assert _nvidia(client)["connected"] is False
    stuck = client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-new"})
    assert stuck.status_code == 400
    assert "backup" in stuck.json()["detail"]["message"]


def test_the_models_a_provider_can_hold_are_bounded(client):
    """D-180: Connect took any number of model ids of any length, and every
    per-model trust setting was kept, so one login grew the shared document
    without limit."""
    too_many = [f"mistralai/m-{index}" for index in range(51)]
    assert client.post(f"{API}/ai/providers/nvidia/connect",
                       json={"api_key": "nvapi-test", "model_ids": too_many}).status_code == 422
    too_long = client.post(f"{API}/ai/providers/nvidia/connect",
                           json={"api_key": "nvapi-test", "model_ids": ["mistralai/" + "x" * 300]})
    assert too_long.status_code == 422
    assert "model ids" in too_long.json()["detail"]
    for batch in range(2):
        models = [f"mistralai/m{batch}-{index}" for index in range(30)]
        assert client.post(f"{API}/ai/providers/nvidia/connect",
                           json={"api_key": "nvapi-test", "model_ids": models}).status_code == 200
        answers = [_trust(client, {"tier": "C", "model_id": model}) for model in models]
    assert sum(answer.status_code == 200 for answer in answers) == 20
    last = answers[-1].json()["detail"]["message"]
    assert "50 models" in last


# ── Fourth review of 2026-09-26: what the card and Connect claim ────────────

GEMINI = "gemini-2.0-flash"


def _google_sends(client) -> tuple[str, str]:
    app = client.app
    settings = app.state.ai_workspaces.egress_settings("local")
    [resolved], _ = app.state.ai_registry.candidates_for(
        DataClass.PERSON_PUBLIC, enabled_ids=["google"], overrides=settings.overrides,
        enabled_models={"google": (GEMINI,)}, policy_by_provider=settings.default_policy_by_provider)
    return resolved.tier.value, resolved.policy.value


def test_the_card_never_claims_a_ceiling_no_switched_on_model_gets(client):
    """D-184: with the grant reaching no model, the form still read "Tier B
    allows up to Full access"."""
    _connect(client, data_policy="standard")
    _grant(client)
    client.post(f"{API}/ai/providers/nvidia/connect", json={"model_ids": [CN_MODEL], "data_policy": "standard"})
    row = _nvidia(client)
    assert row["grant_state"] == "no_model"
    assert (row["policy_ceiling"], row["standing_ceiling"]) == ("standard", "standard")


def test_a_save_that_is_cut_says_so(client):
    """D-184: choosing Full stored Standard and answered "connected" as if
    nothing was cut."""
    _connect(client, data_policy="standard")
    _grant(client)
    answer = client.post(f"{API}/ai/providers/nvidia/connect",
                         json={"model_ids": [US_MODEL, CN_MODEL], "data_policy": "full"}).json()
    assert answer["provider"]["data_policy"] == "standard"
    assert (answer["policy_was_clamped"], answer["policy_ceiling"]) == (True, "standard")


def test_the_form_offers_levels_up_to_the_providers_standing_trust(client):
    assert _nvidia(client)["standing_ceiling"] == "standard"
    _trust(client, {"tier": "C"})
    assert _nvidia(client)["standing_ceiling"] == "standard"  # a lowering is temporary
    _trust(client, {"tier": "A", "reason": "Our data agreement with NVIDIA covers this"})
    assert _nvidia(client)["standing_ceiling"] == "full"


def test_withdrawing_a_grant_never_raises_what_is_sent(client):
    """D-186: a grant below the owner's own level decided what was sent, so
    withdrawing it raised Minimal to Standard."""
    assert client.post(f"{API}/ai/providers/google/connect",
                       json={"api_key": "g-test", "model_ids": [GEMINI]}).status_code == 200
    assert client.post(f"{API}/ai/providers/google/override", json={
        "data_policy": "minimal", "allow_above_ceiling": True, "reason": "names are fine for Gemini"}).status_code == 200
    assert client.post(f"{API}/ai/providers/google/trust",
                       json={"tier": "B", "reason": "Workspace terms signed"}).status_code == 200
    client.post(f"{API}/ai/providers/google/connect", json={"model_ids": [GEMINI], "data_policy": "standard"})
    with_grant = _google_sends(client)
    client.post(f"{API}/ai/providers/google/override", json={})
    assert with_grant == _google_sends(client) == ("B", "standard")


def test_a_provider_whose_models_are_all_blocked_sends_nothing(client):
    """D-188: "Sends: Strict" for a provider whose only model was blocked."""
    client.post(f"{API}/ai/providers/nvidia/connect",
                json={"api_key": "nvapi-test", "model_ids": [US_MODEL], "data_policy": "standard"})
    _trust(client, {"tier": "D", "model_id": US_MODEL})
    row = _nvidia(client)
    assert (row["sends_nothing"], row["receives_nothing"]) == (True, False)
    _trust(client, {"tier": "", "model_id": US_MODEL})
    assert _nvidia(client)["sends_nothing"] is False


@pytest.mark.parametrize("damage", ["missing", "invalid", "other"])
def test_a_damaged_key_store_says_what_the_install_owner_can_do(client, damage):
    """D-189: only one of three key-store failures had a next step, and that
    one did not say the key file holds every workspace's keys."""
    from cryptography.fernet import Fernet

    _connect(client)
    store = client.app.state.ai_workspaces
    if damage == "missing":
        store.key_path.unlink()
    elif damage == "invalid":
        store.key_path.write_bytes(b"not a key")
    else:
        store.key_path.write_bytes(Fernet.generate_key())
    answer = client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-new"})
    assert answer.status_code == 400
    message = answer.json()["detail"]["message"]
    assert "backup" in message and "every workspace" in message and "install owner" in message


def test_a_damaged_master_key_is_fixed_by_the_step_the_message_gives(client):
    """D-192: removing the keys file was not enough for a damaged master key,
    which is only replaced when missing; every save kept failing."""
    _connect(client)
    store = client.app.state.ai_workspaces
    store.key_path.write_bytes(b"not a key")
    message = client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-new"}).json()["detail"]["message"]
    assert "remove ai_provider_keys.enc and .ai_master.key" in message
    store.secret_path.unlink()
    store.key_path.unlink()
    assert client.post(f"{API}/ai/providers/nvidia/connect", json={"api_key": "nvapi-new"}).status_code == 200
