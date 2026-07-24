from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.off_ai.broker import EgressBroker
from offsetx_apollo_builder.off_ai.parsers import CampaignIntakeParser
from offsetx_apollo_builder.off_ai.policy import PolicyViolation, SandboxPolicy
from offsetx_apollo_builder.off_ai.store import OffAIStore
from offsetx_apollo_builder.off_ai.tools import BringYourOwnToolRegistry
from offsetx_apollo_builder.outreach.provider_profiles import ProviderProfileStore
from offsetx_apollo_builder.outreach.providers import ProviderError


def _profile(
    store: ProviderProfileStore,
    *,
    profile_id: str,
    tier: str,
    model: str = "fixed",
    fallback_profile_ids: list[str] | None = None,
    public_tasks_enabled: bool = False,
    allowed_task_types: list[str] | None = None,
):
    return store.upsert(
        {
            "id": profile_id,
            "owner": "Kunal",
            "name": profile_id,
            "provider_type": "openai",
            "model": model,
            "priority": 10,
            "enabled": True,
            "jurisdiction": "US" if tier != "C" else "China",
            "retention_policy": (
                "no_training_no_retention" if tier == "A" else "may_train"
            ),
            "trust_tier": tier,
            "host_origin": "Test host",
            "model_origin": "Test model",
            "terms_checked_at": "2026-07-24",
            "fallback_profile_ids": fallback_profile_ids or [],
            "public_tasks_enabled": public_tasks_enabled,
            "allowed_task_types": allowed_task_types or [],
        },
        api_key=f"secret-{profile_id}",
    )


class _FixedProvider:
    def __init__(self, output: str, *, error: Exception | None = None):
        self.output = output
        self.error = error
        self.calls: list[dict[str, str]] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt}
        )
        if self.error:
            raise self.error
        return self.output


def _broker(tmp_path: Path) -> tuple[EgressBroker, ProviderProfileStore, OffAIStore]:
    profiles = ProviderProfileStore(tmp_path / "profiles")
    ai_store = OffAIStore(tmp_path / "off-ai.db")
    ai_store.initialize()
    return EgressBroker(store=ai_store, profiles=profiles), profiles, ai_store


def test_projects_chats_messages_and_runtime_state_persist(tmp_path):
    store = OffAIStore(tmp_path / "off-ai.db")
    store.initialize()
    project = store.create_project(name="CBAM outreach", description="Pilot")
    conversation = store.create_conversation(
        title="New chat", project_id=project["id"]
    )
    user = store.add_message(
        conversation_id=conversation["id"],
        role="user",
        content="Map public CBAM sources.",
        egress_approved=True,
    )
    store.append_context_event(
        conversation["id"], role="user", content=user["content"]
    )

    assert store.list_projects()[0]["conversation_count"] == 1
    assert store.list_messages(conversation["id"])[0]["content"].startswith("Map")
    context = store.get_context("conversation", conversation["id"])
    assert context["current_task"] == "Map public CBAM sources."
    assert "User:" in context["rolling_summary"]
    store.close()


@pytest.mark.parametrize("tier", ["B", "C", "D"])
def test_private_person_task_is_refused_for_non_tier_a_provider(tmp_path, tier):
    broker, profiles, store = _broker(tmp_path)
    _profile(
        profiles,
        profile_id=f"tier-{tier.lower()}",
        tier=tier,
        public_tasks_enabled=True,
        allowed_task_types=["outreach_draft"],
    )

    with pytest.raises(PolicyViolation, match="denied by trust"):
        broker.dispatch(
            task_type="outreach_draft",
            fields={
                "public_profile": {
                    "name": "Public Person",
                    "company": "Public Company",
                },
                "template_text": "Hello {first_name}",
                "sender_positioning": "Public positioning",
            },
            selected_profile_id=f"tier-{tier.lower()}",
        )

    calls, total = store.list_egress()
    assert total == 1
    assert calls[0]["status"] == "blocked"
    assert calls[0]["trust_tier"] == tier


def test_declared_tier_a_is_downgraded_for_aggregator_or_china_host(tmp_path):
    broker, profiles, _ = _broker(tmp_path)
    aggregator = _profile(profiles, profile_id="router", tier="A")
    profiles.upsert(
        {
            **aggregator,
            "id": "router",
            "name": "OpenRouter route",
            "host_origin": "Opaque aggregator",
            "provider_type": "openai",
        }
    )
    china_host = _profile(profiles, profile_id="china-host", tier="A")
    profiles.upsert(
        {
            **china_host,
            "id": "china-host",
            "jurisdiction": "China",
            "provider_type": "openai",
        }
    )

    assert broker.policy.effective_tier(profiles.get("router")) == "D"
    assert broker.policy.effective_tier(profiles.get("china-host")) == "C"


def test_legacy_host_local_command_provider_is_refused(tmp_path):
    broker, profiles, _ = _broker(tmp_path)
    profile = profiles.upsert(
        {
            "id": "legacy-command",
            "owner": "owner",
            "name": "Legacy local command",
            "provider_type": "local_command",
            "model": "host-process",
            "jurisdiction": "Owner controlled",
            "retention_policy": "no_training_no_retention",
            "trust_tier": "A",
            "terms_checked_at": "2026-07-24",
            "extra": {"command": ["python", "unsafe.py"]},
        }
    )

    with pytest.raises(PolicyViolation, match="local-command"):
        broker.dispatch(
            task_type="public_general",
            fields={"prompt": "Explain public CBAM rules.", "approved_context": []},
            selected_profile_id=profile["id"],
        )


def test_email_credentials_mailbox_and_context_requests_are_blocked_before_provider(tmp_path):
    broker, profiles, store = _broker(tmp_path)
    _profile(profiles, profile_id="safe", tier="A")

    unsafe_prompts = [
        "Summarise anita@example.com for me",
        "Read my Gmail and tell me who replied",
        "Retrieve my context store and continue the task",
        "Use this token sk-abcdefghijklmnopqrstuvwxyz",
    ]
    for prompt in unsafe_prompts:
        with pytest.raises(PolicyViolation, match="pre-flight"):
            broker.dispatch(
                task_type="public_general",
                fields={"prompt": prompt, "approved_context": []},
                selected_profile_id="safe",
            )

    calls, total = store.list_egress(status="blocked")
    assert total == len(unsafe_prompts)
    assert all(call["response_text"] == "" for call in calls)


def test_single_broker_sends_only_constructed_allowlist_payload(monkeypatch, tmp_path):
    broker, profiles, store = _broker(tmp_path)
    _profile(profiles, profile_id="safe", tier="A")
    fixed = _FixedProvider('{"subject":"Hello","body":"Public-only body"}')
    monkeypatch.setattr(
        "offsetx_apollo_builder.off_ai.broker.create_provider",
        lambda *_args, **_kwargs: fixed,
    )

    result = broker.dispatch(
        task_type="outreach_draft",
        fields={
            "public_profile": {
                "name": "Anita Rao",
                "company": "Example Exports",
                "title": "Climate lead",
                "email": "must-never-leave@example.com",
                "deal_value": 999999,
            },
            "template_text": "A public template",
            "sender_positioning": "Carbon-market infrastructure in India",
        },
        selected_profile_id="safe",
    )

    sent = json.loads(fixed.calls[0]["user_prompt"])
    assert "email" not in json.dumps(sent).lower()
    assert "deal_value" not in json.dumps(sent)
    assert sent["public_profile"]["name"] == "Anita Rao"
    assert result.profile_id == "safe"
    call = store.get_egress(result.call_id)
    assert call["status"] == "succeeded"
    assert call["payload"]["input"] == sent


def test_pii_backstop_redacts_phone_and_national_id_before_provider(monkeypatch, tmp_path):
    broker, profiles, store = _broker(tmp_path)
    _profile(profiles, profile_id="safe", tier="A")
    fixed = _FixedProvider("Public answer")
    monkeypatch.setattr(
        "offsetx_apollo_builder.off_ai.broker.create_provider",
        lambda *_args, **_kwargs: fixed,
    )

    result = broker.dispatch(
        task_type="public_general",
        fields={
            "prompt": (
                "Explain this public example without repeating +91 98765 43210 "
                "or ABCDE1234F."
            ),
            "approved_context": [],
        },
        selected_profile_id="safe",
    )

    sent = fixed.calls[0]["user_prompt"]
    assert "98765" not in sent
    assert "ABCDE1234F" not in sent
    assert "[PHONE_REDACTED]" in sent
    assert "[NATIONAL_ID_REDACTED]" in sent
    call = store.get_egress(result.call_id)
    assert call["payload"]["input"]["task"].count("_REDACTED]") == 2


def test_failover_stays_inside_the_same_trust_tier(monkeypatch, tmp_path):
    broker, profiles, _ = _broker(tmp_path)
    _profile(
        profiles,
        profile_id="primary-a",
        tier="A",
        model="fail",
        fallback_profile_ids=["unsafe-b", "backup-a"],
    )
    _profile(profiles, profile_id="unsafe-b", tier="B", model="must-not-run")
    _profile(profiles, profile_id="backup-a", tier="A", model="works")
    providers: dict[str, _FixedProvider] = {}

    def factory(config, **_kwargs):
        provider = _FixedProvider(
            "backup answer",
            error=ProviderError("quota exhausted") if config.model == "fail" else None,
        )
        providers[config.model] = provider
        return provider

    monkeypatch.setattr(
        "offsetx_apollo_builder.off_ai.broker.create_provider", factory
    )
    result = broker.dispatch(
        task_type="public_general",
        fields={"prompt": "Explain this public regulation.", "approved_context": []},
        selected_profile_id="primary-a",
        allow_failover=True,
    )

    assert result.profile_id == "backup-a"
    assert "must-not-run" not in providers
    assert [item["profile_id"] for item in result.attempts] == [
        "primary-a",
        "backup-a",
    ]


def test_sandbox_policy_denies_arbitrary_network_and_builds_networkless_container():
    sandbox = SandboxPolicy(allowed_hosts={"gate.internal"})
    sandbox.assert_host("gate.internal")
    with pytest.raises(PolicyViolation, match="Sandbox egress blocked"):
        sandbox.assert_host("example.com")
    command = sandbox.docker_command(
        image="off-crm-tool:1.0",
        command=["python", "run.py"],
        source_dir="/tmp/tool-source",
    )
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--pull=never" in command
    assert "--user=65534:65534" in command


def test_bring_your_own_tool_requires_pinned_github_commit_and_public_input(tmp_path):
    registry = BringYourOwnToolRegistry(tmp_path / "tools")
    with pytest.raises(ValueError, match="40-character"):
        registry.register(
            name="Crawler",
            repository_url="https://github.com/example/crawler",
            commit_sha="main",
            image="python:3.12.10-slim-bookworm",
            command=["python", "main.py"],
        )
    tool = registry.register(
        name="Crawler",
        repository_url="https://github.com/example/crawler",
        commit_sha="a" * 40,
        image="python:3.12.10-slim-bookworm",
        command=["python", "main.py"],
    )
    source = tmp_path / "tools" / "sources" / tool["id"] / ("a" * 40)
    source.mkdir(parents=True)
    registry._update(
        tool["id"],
        {"status": "prepared", "source_path": str(source)},
    )
    command = registry.execution_command(tool["id"])
    assert "--network=none" in command
    assert "--read-only" in command
    assert str(source.resolve()) in " ".join(command)
    with pytest.raises(PolicyViolation, match="pre-flight"):
        registry.execute(tool["id"], public_input="Contact anita@example.com")


def test_deterministic_intake_parser_handles_extra_header_and_masks_emails(tmp_path):
    source = tmp_path / "prewritten.csv"
    source.write_text(
        "Campaign export,,,,\n"
        "Recipient Name,Email Address,Company,Subject Line,Email Body\n"
        "Anita Rao,anita@example.com,Example Exports,CBAM evidence,Hello Anita\n",
        encoding="utf-8",
    )

    result = CampaignIntakeParser().inspect(source)

    assert result["status"] == "ready"
    assert result["detected_mode"] == "parse_send"
    assert result["private_result"]["rows"][0]["email"] == "anita@example.com"
    preview = json.dumps(result["public_preview"])
    assert "anita@example.com" not in preview
    assert "RECIPIENT_1" in preview


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        database_path=tmp_path / "off-crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        public_positioning="Carbon-market infrastructure in India",
    )


def test_ai_api_creates_projects_chats_and_deterministic_campaign_intake(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        project = client.post(
            "/api/v1/ai/projects",
            json={"name": "CBAM research", "description": "Public sources"},
        )
        assert project.status_code == 201
        conversation = client.post(
            "/api/v1/ai/conversations",
            json={"project_id": project.json()["id"], "title": "New chat"},
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]
        source = (
            b"Recipient Name,Email Address,Company,Subject Line,Email Body\n"
            b"Anita Rao,anita@example.com,Example Exports,CBAM evidence,Hello Anita\n"
        )
        inspection = client.post(
            "/api/v1/ai/intakes/inspect",
            files={"file": ("emails.csv", source, "text/csv")},
            data={"conversation_id": conversation_id},
        )
        assert inspection.status_code == 201
        assert inspection.json()["detected_mode"] == "parse_send"
        assert "anita@example.com" not in inspection.text

        committed = client.post(
            f"/api/v1/ai/intakes/{inspection.json()['id']}/commit",
            json={
                "campaign_name": "Imported pre-written pilot",
                "daily_send_limit": 20,
                "selected_mode": "parse_send",
                "selected_profile_id": "",
            },
        )
        assert committed.status_code == 200
        assert committed.json()["contacts_added"] == 1
        assert committed.json()["drafts_created"] == 1
        campaign_id = committed.json()["campaign_id"]
        drafts = client.get(
            f"/api/v1/campaigns/{campaign_id}/drafts"
        ).json()["items"]
        assert len(drafts) == 1
        assert drafts[0]["approval_status"] == "pending"
        assert drafts[0]["sendable"] is True

        bootstrap = client.get("/api/v1/ai/bootstrap").json()
        assert bootstrap["projects"][0]["conversation_count"] == 1
        assert bootstrap["privacy"]["mailbox_access"] is False
        assert client.get("/api/v1/connectors").status_code == 200

        owner_export = client.get(
            "/api/v1/ai/owner-record/export", params={"format": "json"}
        )
        assert owner_export.status_code == 200
        owner_record = owner_export.json()
        assert owner_record["schema_version"] == 2
        activity = owner_record["crm_activity"]
        assert activity["campaigns"][0]["name"] == "Imported pre-written pilot"
        assert activity["contacts"][0]["full_name"] == "Anita Rao"
        assert activity["contacts"][0]["variant_id"] in {"A", "B"}
        assert activity["contacts"][0]["reply_received"] is False
        assert activity["messages"] == []
        assert activity["content_included"] is False
        assert "body" not in json.dumps(activity)


def test_generate_intake_fails_before_campaign_without_tier_a_provider(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        source = (
            b"Name,Email,Company,Title\n"
            b"Anita Rao,anita@example.com,Example Exports,Climate lead\n"
        )
        inspection = client.post(
            "/api/v1/ai/intakes/inspect",
            files={"file": ("pois.csv", source, "text/csv")},
            data={
                "selected_mode": "generate",
                "template_text": "Hello {first_name}",
                "public_positioning": "Public carbon-market infrastructure",
            },
        )
        assert inspection.status_code == 201
        assert inspection.json()["status"] == "ready"

        committed = client.post(
            f"/api/v1/ai/intakes/{inspection.json()['id']}/commit",
            json={
                "campaign_name": "Must not be created",
                "daily_send_limit": 20,
                "selected_mode": "generate",
                "selected_profile_id": "",
            },
        )
        assert committed.status_code == 422
        assert "eligible Tier A provider" in committed.json()["detail"]
        campaigns = client.get("/api/v1/campaigns").json()
        assert campaigns["total"] == 0


def test_project_instructions_are_pushed_as_approved_context_not_pulled(monkeypatch, tmp_path):
    fixed = _FixedProvider("Public answer")
    monkeypatch.setattr(
        "offsetx_apollo_builder.off_ai.broker.create_provider",
        lambda *_args, **_kwargs: fixed,
    )
    with TestClient(create_app(_settings(tmp_path))) as client:
        profile = client.post(
            "/api/v1/provider-profiles",
            json={
                "name": "Verified model",
                "owner": "owner",
                "provider_type": "openai",
                "model": "fixed",
                "api_key": "test-provider-secret",
                "jurisdiction": "United States",
                "retention_policy": "no_training_no_retention",
                "trust_tier": "A",
                "host_origin": "Test host",
                "model_origin": "Test model",
                "terms_checked_at": "2026-07-24",
                "allowed_task_types": ["public_general", "health_check"],
            },
        )
        assert profile.status_code == 201
        project = client.post(
            "/api/v1/ai/projects",
            json={
                "name": "Public research",
                "instructions": "Use concise public analysis and state uncertainty.",
            },
        ).json()
        conversation = client.post(
            "/api/v1/ai/conversations",
            json={
                "project_id": project["id"],
                "selected_profile_id": profile.json()["id"],
            },
        ).json()

        response = client.post(
            f"/api/v1/ai/conversations/{conversation['id']}/messages",
            json={
                "prompt": "Explain this public regulation.",
                "selected_profile_id": profile.json()["id"],
            },
        )
        assert response.status_code == 201
        exact_packet = json.loads(fixed.calls[0]["user_prompt"])
        approved = exact_packet["approved_public_context"]
        assert approved[0]["role"] == "user"
        assert "Approved public project instructions" in approved[0]["content"]
        assert "Use concise public analysis" in approved[0]["content"]
        assert "database" not in json.dumps(exact_packet).lower()


def test_reply_rate_rewrite_uses_only_template_and_number_then_waits_for_review(
    monkeypatch, tmp_path
):
    fixed = _FixedProvider("Revised public template")
    monkeypatch.setattr(
        "offsetx_apollo_builder.off_ai.broker.create_provider",
        lambda *_args, **_kwargs: fixed,
    )
    with TestClient(create_app(_settings(tmp_path))) as client:
        profile = client.post(
            "/api/v1/provider-profiles",
            json={
                "name": "Verified rewrite model",
                "owner": "owner",
                "provider_type": "openai",
                "model": "fixed",
                "api_key": "test-provider-secret",
                "jurisdiction": "United States",
                "retention_policy": "no_training_no_retention",
                "trust_tier": "A",
                "host_origin": "Test host",
                "model_origin": "Test model",
                "terms_checked_at": "2026-07-24",
                "allowed_task_types": ["template_rewrite", "health_check"],
            },
        ).json()
        suggestion = client.post(
            "/api/v1/ai/template-recommendations",
            json={
                "template_id": "initial-client-A",
                "variant_id": "A",
                "current_template": "Subject: Public evidence\n\nA public template.",
                "sample_size": 20,
                "reply_rate": 0,
                "selected_profile_id": profile["id"],
            },
        )
        assert suggestion.status_code == 201
        assert suggestion.json()["status"] == "pending_review"
        sent = json.loads(fixed.calls[0]["user_prompt"])
        assert sent["performance"] == {
            "sample_size": 20,
            "reply_rate_percent": 0.0,
        }
        assert set(sent) == {
            "schema_version",
            "task",
            "template_text",
            "performance",
        }

        queue = client.get("/api/v1/ai/template-recommendations").json()
        assert queue["total"] == 1
        reviewed = client.patch(
            f"/api/v1/ai/template-recommendations/{suggestion.json()['id']}",
            json={"approved": True},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "approved"
