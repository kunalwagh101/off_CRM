"""F-04.01: no procedure enters a broker payload without owner selection."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = "companion-skill-owner-" + "x" * 35
HEADERS = {"X-Offsetx-Token": TOKEN}


class Memory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


@pytest.fixture
def registry(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    return CompanionRegistry(tmp_path, tools=tools, memory_backend=Memory())


def test_unselected_procedures_never_enter_context_or_model_instructions(registry):
    profile = registry.create(
        workspace_id="alpha", name="Researcher", instructions="Research public facts.",
    )
    picked = registry.create_skill(
        workspace_id="alpha", name="Owner-approved sourcing",
        content="Use two independent public sources.",
    )
    unused = registry.create_skill(
        workspace_id="alpha", name="Unused playbook",
        content="SECRET-UNSELECTED-PROCEDURE-MUST-NOT-APPEAR",
    )
    empty = registry.start(profile.id, workspace_id="alpha", memory_limit=0)
    assert empty.skills == ()
    assert unused.content not in empty.model_instructions()
    assert picked.content not in empty.model_instructions()

    selected = registry.start(
        profile.id, workspace_id="alpha", skill_ids=[picked.id], memory_limit=0,
    )
    assert [item.id for item in selected.skills] == [picked.id]
    assert picked.content in selected.model_instructions()
    assert unused.content not in selected.model_instructions()


def test_foreign_disabled_deleted_duplicate_and_unknown_selection_fail_closed(registry):
    profile = registry.create(
        workspace_id="alpha", name="Researcher", instructions="Use approved notes.",
    )
    own = registry.create_skill(workspace_id="alpha", name="Own", content="Permitted.")
    foreign = registry.create_skill(
        workspace_id="beta", name="Other", content="OTHER PRIVATE PROCEDURE",
    )
    for selected in ([foreign.id], ["unknown"], [own.id, own.id], [own.id] * 4):
        with pytest.raises(CompanionError):
            registry.start(profile.id, workspace_id="alpha", skill_ids=selected, memory_limit=0)
    registry.update_skill(own.id, workspace_id="alpha", enabled=False)
    with pytest.raises(CompanionError, match="disabled"):
        registry.start(profile.id, workspace_id="alpha", skill_ids=[own.id], memory_limit=0)
    registry.update_skill(own.id, workspace_id="alpha", enabled=True)
    assert registry.start(profile.id, workspace_id="alpha", skill_ids=[own.id]).skills
    assert registry.delete_skill(own.id, workspace_id="alpha")
    with pytest.raises(CompanionError):
        registry.start(profile.id, workspace_id="alpha", skill_ids=[own.id])
    assert registry.get_skill(foreign.id, workspace_id="alpha") is None


def test_procedures_survive_registry_restart_and_limit_text(registry, tmp_path):
    saved = registry.create_skill(
        workspace_id="w", name="Trusted review", content="Check evidence before action.",
    )
    reopened = CompanionRegistry(tmp_path, tools=registry.tools, memory_backend=Memory())
    assert reopened.require_skill(saved.id, workspace_id="w").content == saved.content
    with pytest.raises(CompanionError, match="characters"):
        reopened.create_skill(workspace_id="w", name="Too long", content="A" * 2001)
    with pytest.raises(CompanionError, match="control"):
        reopened.create_skill(workspace_id="w", name="Control", content="Bad\x00code")
    with pytest.raises(CompanionError, match="already exists"):
        reopened.create_skill(workspace_id="w", name="trusted review", content="Duplicate")


def test_companion_model_prompt_fails_instead_of_silently_truncating(registry):
    profile = registry.create(
        workspace_id="w", name="Very long", instructions="A" * 5900,
    )
    procedure = registry.create_skill(
        workspace_id="w", name="Too much", content="B" * 400,
    )
    context = registry.start(profile.id, workspace_id="w", skill_ids=[procedure.id])
    with pytest.raises(CompanionError, match="model limit"):
        context.model_instructions()


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1", api_token=TOKEN, allowed_hosts=("testserver",),
    )


def test_owner_api_lifecycle_and_broker_payload_selection(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        assert client.get("/api/v1/companion-skills").status_code == 401
        assert client.post(
            "/api/v1/companion-skills", json={"name": "No auth", "content": "No"}
        ).status_code == 401
        companion = client.post(
            "/api/v1/companions",
            json={"name": "Scoped", "instructions": "Only use authorised procedures."},
            headers=HEADERS,
        )
        assert companion.status_code == 201, companion.text
        companion_id = companion.json()["id"]
        skill = client.post(
            "/api/v1/companion-skills",
            json={"name": "Public review", "content": "Check the original public source."},
            headers=HEADERS,
        )
        assert skill.status_code == 201, skill.text
        skill_id = skill.json()["id"]
        untouched = client.post(
            "/api/v1/companion-skills",
            json={"name": "Never sent", "content": "DO-NOT-EGRESS-UNSELECTED-TEXT"},
            headers=HEADERS,
        )
        assert untouched.status_code == 201, untouched.text

        context = client.post(
            f"/api/v1/companions/{companion_id}/context",
            json={"skill_ids": [skill_id], "memory_limit": 0},
            headers=HEADERS,
        )
        assert context.status_code == 200, context.text
        assert [skill["id"] for skill in context.json()["skills"]] == [skill_id]

        sent_requests = []
        class Broker:
            def with_credential_resolver(self, resolver):
                return self

            def call(self, request, settings, **kwargs):
                sent_requests.append(request)
                return SimpleNamespace(text="A test-only reply.", provider_name="fake", model_id="fake-v1")

        client.app.state.ai_broker = Broker()
        chat = client.post("/api/v1/ai/chats", json={"title": "Test"}, headers=HEADERS)
        assert chat.status_code == 200, chat.text
        chat_id = chat.json()["id"]
        run = client.post(
            f"/api/v1/ai/chats/{chat_id}/messages",
            json={"content": "Give a sourced answer", "companion_id": companion_id,
                  "skill_ids": [skill_id], "data_class": "campaign"},
            headers=HEADERS,
        )
        assert run.status_code == 200, run.text
        assert len(sent_requests) == 1
        assert "Check the original public source." in sent_requests[0].instructions
        assert "DO-NOT-EGRESS-UNSELECTED-TEXT" not in sent_requests[0].instructions

        no_selection = client.post(
            f"/api/v1/ai/chats/{chat_id}/messages",
            json={"content": "Continue without the companion"},
            headers=HEADERS,
        )
        assert no_selection.status_code == 200, no_selection.text
        assert sent_requests[-1].instructions == ""

        blocked = client.post(
            f"/api/v1/ai/chats/{chat_id}/messages",
            json={"content": "Do not send", "companion_id": companion_id,
                  "skill_ids": [untouched.json()["id"]], "data_class": "public"},
            headers=HEADERS,
        )
        assert blocked.status_code == 400
        assert len(sent_requests) == 2
        disabled = client.patch(
            f"/api/v1/companion-skills/{skill_id}",
            json={"enabled": False}, headers=HEADERS,
        )
        assert disabled.status_code == 200, disabled.text
        refused = client.post(
            f"/api/v1/ai/chats/{chat_id}/messages",
            json={"content": "Do not send", "companion_id": companion_id,
                  "skill_ids": [skill_id]},
            headers=HEADERS,
        )
        assert refused.status_code == 400, refused.text
        assert len(sent_requests) == 2
        assert client.delete(f"/api/v1/companion-skills/{skill_id}",
                             headers=HEADERS).status_code == 200
        deleted = client.post(
            f"/api/v1/ai/chats/{chat_id}/messages",
            json={"content": "Do not send", "companion_id": companion_id,
                  "skill_ids": [skill_id]},
            headers=HEADERS,
        )
        assert deleted.status_code == 404, deleted.text
        assert len(sent_requests) == 2
