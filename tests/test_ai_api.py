"""API-level tests for the AI module surface.

Covers the endpoints the Connectors and Egress screens depend on, and proves the
chat path that used to leak now refuses rather than sends.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

API = "/api/v1"


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as test_client:
        yield test_client


def test_provider_list_exposes_jurisdiction_tier_and_retention(client):
    """§4B: each provider card must show these at a glance, never buried."""
    response = client.get(f"{API}/ai/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"], "registry should not be empty"
    for provider in payload["providers"]:
        assert provider["jurisdiction"]
        assert provider["trust_tier"] in {"A", "B", "C", "D"}
        assert provider["retention"]
        assert provider["verified_on"]
        assert "policy_ceiling" in provider

    by_id = {item["id"]: item for item in payload["providers"]}
    assert by_id["mistral"]["trust_tier"] == "A"
    assert by_id["openai"]["trust_tier"] == "B"
    assert by_id["deepseek"]["trust_tier"] == "C"
    assert by_id["openrouter"]["trust_tier"] == "D"
    # Nothing is connected until the owner connects it.
    assert all(item["connected"] is False for item in payload["providers"])


def test_policy_levels_and_tiers_are_described_for_the_ui(client):
    payload = client.get(f"{API}/ai/providers").json()
    assert [item["value"] for item in payload["policy_levels"]] == [
        "strict",
        "pseudonymous",
        "minimal",
        "standard",
        "full",
    ]
    assert all(item["description"] for item in payload["policy_levels"])
    assert payload["mailbox_unlocked"] is False


def test_connecting_a_chinese_provider_clamps_the_policy_to_pseudonymous(client):
    response = client.post(
        f"{API}/ai/providers/deepseek/connect",
        json={"api_key": "sk-test", "data_policy": "full"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_was_clamped"] is True
    assert payload["provider"]["data_policy"] == "pseudonymous"
    assert payload["tier"] == "C"


def test_connecting_a_european_provider_keeps_the_requested_policy(client):
    response = client.post(
        f"{API}/ai/providers/mistral/connect",
        json={"api_key": "k", "data_policy": "full"},
    )
    payload = response.json()
    assert payload["policy_was_clamped"] is False
    assert payload["provider"]["data_policy"] == "full"


def test_connecting_an_unlisted_provider_is_refused(client):
    response = client.post(
        f"{API}/ai/providers/mystery-ai/connect", json={"api_key": "k"}
    )
    assert response.status_code == 400
    assert "registry" in response.json()["detail"]["error"]


def test_override_above_ceiling_requires_a_reason(client):
    client.post(f"{API}/ai/providers/deepseek/connect", json={"api_key": "k"})
    refused = client.post(
        f"{API}/ai/providers/deepseek/override",
        json={"data_policy": "full", "allow_above_ceiling": True},
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["error"] == "invalid_request"
    assert "reason" in refused.json()["detail"]["message"].lower()

    accepted = client.post(
        f"{API}/ai/providers/deepseek/override",
        json={
            "data_policy": "full",
            "allow_above_ceiling": True,
            "reason": "Coding tasks only, exposure accepted",
        },
    )
    assert accepted.status_code == 200
    stored = accepted.json()["overrides"]["deepseek"]
    assert stored["reason"] == "Coding tasks only, exposure accepted"
    assert stored["decided_at"]


def test_plan_endpoint_explains_who_would_run_and_who_was_excluded(client):
    client.post(f"{API}/ai/providers/mistral/connect", json={"api_key": "k"})
    client.post(f"{API}/ai/providers/deepseek/connect", json={"api_key": "k"})

    response = client.post(
        f"{API}/ai/plan", json={"data_class": "person_public", "task_type": "draft_email"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["would_use"]["id"] == "mistral"
    excluded = {item["provider_id"]: item["reason"] for item in payload["excluded"]}
    assert excluded["deepseek"] == "lower_tier_not_used_for_failover"


def test_plan_for_campaign_data_excludes_tier_c_entirely(client):
    client.post(f"{API}/ai/providers/deepseek/connect", json={"api_key": "k"})
    response = client.post(f"{API}/ai/plan", json={"data_class": "campaign"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "no_permitted_provider"
    assert "deepseek" in str(detail).lower()


def test_chat_with_no_provider_connected_explains_the_next_step(client):
    """§4L: no dead ends. An empty state must say what to do."""
    chat = client.post(f"{API}/ai/chats", json={"title": "New chat"}).json()
    response = client.post(
        f"{API}/ai/chats/{chat['id']}/messages", json={"content": "hello"}
    )
    assert response.status_code == 409
    message = response.json()["detail"]["message"]
    assert "Connectors" in message


def test_chat_refuses_mailbox_and_internal_data_classes(client):
    chat = client.post(f"{API}/ai/chats", json={"title": "New chat"}).json()
    for data_class in ("mailbox", "internal"):
        response = client.post(
            f"{API}/ai/chats/{chat['id']}/messages",
            json={"content": "hello", "data_class": data_class},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_data_class"


def test_workspace_positioning_line_and_owner_domains_round_trip(client):
    response = client.post(
        f"{API}/ai/workspace",
        json={
            "positioning_line": "OffsetX helps exporters cut customs cost.",
            "owner_domains": ["OffsetX.example", "  "],
            "owner_addresses": ["Owner@OffsetX.example"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["positioning_line"] == "OffsetX helps exporters cut customs cost."
    assert payload["owner_domains"] == ["offsetx.example"]
    assert payload["owner_addresses"] == ["owner@offsetx.example"]


def test_mailbox_unlock_requires_the_exact_phrase(client):
    bad = client.post(f"{API}/ai/workspace/mailbox-unlock", json={"phrase": "yes please"})
    assert bad.status_code == 400
    assert "ALLOW MAILBOX CONTENT TO LEAVE" in bad.json()["detail"]["message"]

    good = client.post(
        f"{API}/ai/workspace/mailbox-unlock",
        json={"phrase": "ALLOW MAILBOX CONTENT TO LEAVE"},
    )
    assert good.status_code == 200
    assert good.json()["mailbox_unlocked"] is True


def test_egress_log_starts_empty_and_reports_stats(client):
    listing = client.get(f"{API}/ai/egress-log")
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

    stats = client.get(f"{API}/ai/egress-log/stats")
    assert stats.status_code == 200
    assert stats.json()["calls"] == 0


def test_missing_egress_log_entry_returns_404(client):
    assert client.get(f"{API}/ai/egress-log/does-not-exist").status_code == 404


def test_draft_generation_defaults_to_a_guarded_data_policy(client):
    """A request-supplied provider cannot opt out of the guard by omission."""
    from offsetx_apollo_builder.api.schemas import DraftGenerate

    assert DraftGenerate().data_policy == "minimal"


# ── run modes ───────────────────────────────────────────────────────────────


def test_modes_endpoint_says_which_modes_are_usable_and_why_not(client):
    """§4L: a mode the user cannot use must explain itself before they commit."""
    payload = client.get(f"{API}/ai/modes").json()
    by_value = {item["value"]: item for item in payload["modes"]}
    assert set(by_value) == {"simple", "verified", "compare", "orchestrated"}
    # Nothing connected yet, so every mode is blocked with a reason.
    for mode in by_value.values():
        assert mode["available"] is False
        assert mode["blocked_reason"]
        assert mode["label"] and mode["description"]
    assert payload["connected_count"] == 0


def test_compare_needs_two_models_and_orchestration_needs_a_trusted_one(client):
    client.post(f"{API}/ai/providers/deepseek/connect", json={"api_key": "k"})
    payload = client.get(f"{API}/ai/modes").json()
    by_value = {item["value"]: item for item in payload["modes"]}

    assert by_value["simple"]["available"] is True
    # Verified needs only one model: it repairs against rules, not against a
    # second opinion, so a lone provider can still write-check-fix.
    assert by_value["verified"]["available"] is True
    assert by_value["compare"]["available"] is False
    assert "two models" in by_value["compare"]["blocked_reason"]
    # DeepSeek is tier C, so it cannot lead a plan.
    assert by_value["orchestrated"]["available"] is False
    assert "Highest or Default trust" in by_value["orchestrated"]["blocked_reason"]
    assert payload["planner_provider_ids"] == []

    client.post(f"{API}/ai/providers/mistral/connect", json={"api_key": "k"})
    payload = client.get(f"{API}/ai/modes").json()
    by_value = {item["value"]: item for item in payload["modes"]}
    assert by_value["compare"]["available"] is True
    assert by_value["orchestrated"]["available"] is True
    assert payload["planner_provider_ids"] == ["mistral"]


def test_modes_endpoint_reports_usage_per_provider(client):
    client.post(
        f"{API}/ai/providers/groq/connect", json={"api_key": "k", "requests_per_day": 100}
    )
    usage = client.get(f"{API}/ai/modes").json()["usage"]
    assert len(usage) == 1
    assert usage[0]["provider_id"] == "groq"
    assert usage[0]["day_limit"] == 100
    assert usage[0]["source"] == "counted_locally"


def test_run_rejects_an_unknown_mode(client):
    response = client.post(f"{API}/ai/run", json={"mode": "telepathy", "instructions": "hi"})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_mode"


def test_run_rejects_mailbox_and_internal_data_classes(client):
    for data_class in ("mailbox", "internal"):
        response = client.post(
            f"{API}/ai/run",
            json={"mode": "simple", "data_class": data_class, "instructions": "hi"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_data_class"


def test_run_requires_instructions(client):
    response = client.post(f"{API}/ai/run", json={"mode": "compare", "instructions": "  "})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "empty_instructions"


def test_run_with_nothing_connected_points_at_connectors(client):
    response = client.post(
        f"{API}/ai/run", json={"mode": "simple", "instructions": "write something"}
    )
    assert response.status_code == 409
    assert "Connectors" in response.json()["detail"]["message"]


def test_verified_run_can_load_a_named_checks_suite(client):
    """A named suite used to call an undefined ``_evals_path`` at runtime."""
    response = client.post(
        f"{API}/ai/run",
        json={
            "mode": "verified",
            "instructions": "Write a short first-contact email.",
            "checks_suite": "email_first_contact",
        },
    )
    # Verified mode reports provider refusal inside its normal result envelope.
    # Reaching that envelope proves the suite path resolved instead of crashing.
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "verified"
    assert payload["branches"][0]["ok"] is False
    assert "No AI provider is connected" in payload["branches"][0]["error"]


# ── per-model connectors ────────────────────────────────────────────────────


def test_connect_accepts_a_model_list_and_reports_it_back(client):
    response = client.post(
        f"{API}/ai/providers/nvidia/connect",
        json={
            "api_key": "nvapi-test",
            "model_ids": ["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"],
        },
    )
    assert response.status_code == 200
    assert response.json()["provider"]["model_ids"] == [
        "meta/llama-3.3-70b-instruct",
        "deepseek-ai/deepseek-r1",
    ]

    row = next(
        item for item in client.get(f"{API}/ai/providers").json()["providers"]
        if item["id"] == "nvidia"
    )
    assert row["model_ids"] == ["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"]
    assert row["supports_model_discovery"] is True
    # Every model the key could run, each carrying its own tier.
    tiers = {m["id"]: m["tier"] for m in row["available_models"]}
    assert tiers["meta/llama-3.3-70b-instruct"] == "B"
    assert tiers["deepseek-ai/deepseek-r1"] == "C"


def test_plan_separates_two_models_on_the_same_key_by_tier(client):
    """The heart of it: one NVIDIA key, two models, two different trust levels."""
    client.post(
        f"{API}/ai/providers/nvidia/connect",
        json={
            "api_key": "k",
            "model_ids": ["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"],
        },
    )
    payload = client.post(f"{API}/ai/plan", json={"data_class": "campaign"}).json()
    assert payload["would_use"]["model_id"] == "meta/llama-3.3-70b-instruct"
    excluded = {item.get("model_id"): item["reason"] for item in payload["excluded"]}
    assert excluded["deepseek-ai/deepseek-r1"] == "tier_forbids_data_class"


def test_connecting_an_unclassifiable_model_is_refused_with_a_reason(client):
    response = client.post(
        f"{API}/ai/providers/nvidia/connect",
        json={"api_key": "k", "model_ids": ["mystery-lab/secret-9b"]},
    )
    assert response.status_code == 400
    assert "model_origin_rules" in response.json()["detail"]["message"]


def test_discover_models_without_a_key_falls_back_to_config(client):
    response = client.post(f"{API}/ai/providers/nvidia/discover-models", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "config"
    # Count is deliberately not pinned — adding a model to config is a routine
    # edit and should not break a test about the fallback path.
    assert payload["total"] >= 5
    assert all(model["known"] for model in payload["models"])
    assert "No API key stored" in payload["note"]


def test_discover_models_on_an_unlisted_provider_is_refused(client):
    response = client.post(f"{API}/ai/providers/nope/discover-models", json={})
    assert response.status_code == 400


# ── recall over sent mail ───────────────────────────────────────────────────


def test_recall_starts_empty_and_reports_how_it_works(client):
    """The screen states the safety properties, so the API has to carry them."""
    payload = client.get(f"{API}/ai/recall").json()
    assert payload["stats"]["indexed"] == 0
    assert payload["stats"]["searchable_locally"] is True
    assert payload["stats"]["embeddings_used"] is False
    assert payload["stats"]["stored_redacted"] is True


def test_recall_search_reports_that_it_sent_nothing(client):
    """Search is local. The flag exists so the UI can say so without guessing."""
    response = client.post(f"{API}/ai/recall/search", json={"query": "customs"})
    assert response.status_code == 200
    assert response.json()["sent_anywhere"] is False


def test_recall_preview_shows_the_real_outbound_payload(client):
    """Not a description of the payload — the payload, through the real builder
    and the real scanner."""
    response = client.post(f"{API}/ai/recall/preview", json={"query": "customs"})
    assert response.status_code == 200
    preview = response.json()
    assert preview["data_class"] == "campaign", "never 'public' — that would skip the tier rule"
    assert preview["scan"]["clean"] is True
    assert "recipient" not in preview["payload"]


def test_recall_preview_under_a_restricted_policy_carries_no_snippets(client):
    """The second barrier, visible through the API: a minimal policy drops the
    past emails entirely rather than trimming them."""
    preview = client.post(
        f"{API}/ai/recall/preview", json={"query": "customs", "data_policy": "minimal"}
    ).json()
    assert "prior_drafts" not in preview["payload"]


def test_recall_forget_needs_something_named(client):
    response = client.post(f"{API}/ai/recall/forget", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "nothing_named"


def test_recall_forget_everything_is_allowed(client):
    response = client.post(f"{API}/ai/recall/forget", json={"everything": True})
    assert response.status_code == 200
    assert response.json()["removed"] == 0


def test_recall_rebuild_runs_without_a_campaign(client):
    response = client.post(f"{API}/ai/recall/rebuild", json={})
    assert response.status_code == 200
    assert response.json()["indexed"] == 0
