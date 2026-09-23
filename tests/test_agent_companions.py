from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
import pytest

from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.ai.errors import PolicyViolation
from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.outreach.store import OutreachStore


SHA = "a" * 40


class Memory:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def add_memory_item(self, **values):
        item = {"id": f"m{self.next_id}", **values}
        self.next_id += 1
        self.rows.append(item)
        return item["id"]

    def search_memory_items(
        self,
        query="",
        *,
        workspace_id="local",
        scope="",
        approved_only=False,
        limit=100,
        offset=0,
        **_filters,
    ):
        rows = [
            item
            for item in self.rows
            if item.get("workspace_id") == workspace_id
            and (not scope or item.get("scope") == scope)
            and (not approved_only or item.get("approved"))
            and (not query or query.lower() in str(item.get("content", "")).lower())
        ]
        return rows[offset: offset + limit], len(rows)


def _tool(registry: ToolRegistry, name: str, workspace_id: str = "w"):
    return registry.register(
        name=name,
        repository_url="https://github.com/example/example",
        commit_sha=SHA,
        # The sandbox accepts name:tag or name@sha256:<digest>, not both at once.
        image="python@sha256:" + "b" * 64,
        command=("python", "tool.py"),
        description=f"{name} tool",
        workspace_id=workspace_id,
    )


def test_run_context_contains_only_its_granted_tools_and_memory_scope(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    granted = _tool(tools, "granted")
    _tool(tools, "other")
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)

    profile = registry.create(
        workspace_id="w",
        name="Sales Sally",
        instructions="Qualify leads conservatively.",
        granted_tool_ids=[granted.id],
    )
    memory.add_memory_item(
        workspace_id="w", scope=profile.memory_scope, kind="fact",
        content="Use MEDDIC", approved=True,
    )
    memory.add_memory_item(
        workspace_id="w", scope="global", kind="fact",
        content="GLOBAL SECRET", approved=True,
    )
    memory.add_memory_item(
        workspace_id="other", scope=profile.memory_scope, kind="fact",
        content="OTHER WORKSPACE", approved=True,
    )

    context = registry.start(profile.id, workspace_id="w")

    assert [tool["id"] for tool in context.tools] == [granted.id]
    assert [item["content"] for item in context.memory] == ["Use MEDDIC"]
    assert context.profile.instructions == "Qualify leads conservatively."


def test_production_memory_backend_keeps_global_memory_out_of_companion_run(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    store = OutreachStore(tmp_path / "crm.db")
    store.initialize()
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=store)
    profile = registry.create(
        workspace_id="w",
        name="Scoped",
        instructions="Use only my scoped memory.",
    )
    store.add_memory_item(
        workspace_id="w",
        scope="global",
        kind="fact",
        content="GLOBAL MUST NOT ENTER COMPANION",
        approved=True,
    )
    store.add_memory_item(
        workspace_id="w",
        scope=profile.memory_scope,
        kind="fact",
        content="COMPANION ONLY",
        approved=True,
    )

    context = registry.start(profile.id, workspace_id="w")

    assert [item["content"] for item in context.memory] == ["COMPANION ONLY"]


def test_default_memory_scope_is_unique_and_companion_owned(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)

    one = registry.create(workspace_id="w", name="One", instructions="One job")
    two = registry.create(workspace_id="w", name="Two", instructions="Two job")

    assert one.memory_scope == f"companion:{one.id}"
    assert two.memory_scope == f"companion:{two.id}"
    assert one.memory_scope != two.memory_scope

    with pytest.raises(CompanionError, match="already belongs"):
        registry.create(
            workspace_id="w",
            name="Three",
            instructions="Three job",
            memory_scope=one.memory_scope,
        )


def test_grant_must_exist_in_the_same_workspace(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    foreign = _tool(tools, "foreign", workspace_id="other")
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)

    with pytest.raises(CompanionError, match="not registered"):
        registry.create(
            workspace_id="w",
            name="Nope",
            instructions="Do not cross workspaces",
            granted_tool_ids=[foreign.id],
        )


def test_disabled_or_removed_granted_tool_disappears_immediately(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    tool = _tool(tools, "one")
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    profile = registry.create(
        workspace_id="w", name="One", instructions="Use one", granted_tool_ids=[tool.id]
    )

    assert len(registry.start(profile.id, workspace_id="w").tools) == 1
    tools.set_enabled(tool.id, False, workspace_id="w")
    assert registry.start(profile.id, workspace_id="w").tools == ()


def test_execution_rechecks_the_grant_not_just_the_prompt_catalogue(tmp_path, monkeypatch):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    allowed = _tool(tools, "allowed")
    denied = _tool(tools, "denied")
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    profile = registry.create(
        workspace_id="w",
        name="Runner",
        instructions="Run only what I granted",
        granted_tool_ids=[allowed.id],
    )

    called = []

    def fake_run(tool_id, **kwargs):
        called.append((tool_id, kwargs["workspace_id"]))
        return SimpleNamespace(tool_id=tool_id)

    monkeypatch.setattr(tools, "run", fake_run)
    workspace = SimpleNamespace()

    with pytest.raises(PolicyViolation, match="not granted"):
        registry.run_tool(
            profile.id, denied.id, workspace_id="w", workspace=workspace
        )
    assert called == []

    result = registry.run_tool(
        profile.id, allowed.id, workspace_id="w", workspace=workspace
    )
    assert result.tool_id == allowed.id
    assert called == [(allowed.id, "w")]


def test_companion_persists_and_owner_updates_do_not_retype_the_profile(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    profile = registry.create(
        workspace_id="w", name="Researcher", instructions="Find sourced facts."
    )

    reopened = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    loaded = reopened.require(profile.id, workspace_id="w")
    assert loaded.name == "Researcher"
    assert loaded.instructions == "Find sourced facts."

    changed = reopened.update(
        profile.id, workspace_id="w", instructions="Find two sourced facts."
    )
    assert changed.id == profile.id
    assert reopened.require(profile.id, workspace_id="w").instructions == "Find two sourced facts."


def test_companion_memory_writes_only_to_its_scope_and_requires_approval_to_recall(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    profile = registry.create(workspace_id="w", name="Memo", instructions="Remember carefully.")

    registry.remember(profile.id, workspace_id="w", content="unapproved")
    registry.remember(
        profile.id, workspace_id="w", content="approved", approved=True
    )

    context = registry.start(profile.id, workspace_id="w")
    assert [item["content"] for item in context.memory] == ["approved"]
    assert all(item["scope"] == profile.memory_scope for item in memory.rows)


def test_duplicate_name_is_rejected_by_persistent_store(tmp_path):
    tools = ToolRegistry(tmp_path / "tools.db")
    memory = Memory()
    registry = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    registry.create(workspace_id="w", name="Researcher", instructions="First")

    reopened = CompanionRegistry(tmp_path, tools=tools, memory_backend=memory)
    with pytest.raises(CompanionError, match="already exists"):
        reopened.create(workspace_id="w", name="researcher", instructions="Second")


def test_companion_api_is_authenticated_persistent_and_memory_scoped(tmp_path):
    token = "c" * 40
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=token,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/companions").status_code == 401
        headers = {"X-Offsetx-Token": token}

        created = client.post(
            "/api/v1/companions",
            json={
                "name": "Sales Sally",
                "instructions": "Qualify leads carefully.",
                "granted_tool_ids": [],
            },
            headers=headers,
        )
        assert created.status_code == 201
        profile = created.json()
        assert profile["memory_scope"] == f"companion:{profile['id']}"

        memory = client.post(
            f"/api/v1/companions/{profile['id']}/memory",
            json={"content": "Use MEDDIC", "approved": True},
            headers=headers,
        )
        assert memory.status_code == 201

        client.app.state.engine.store.add_memory_item(
            workspace_id="local",
            scope="global",
            kind="fact",
            content="GLOBAL SHOULD NOT LEAK",
            approved=True,
            confidence=1.0,
            source_type="test",
        )
        context = client.post(
            f"/api/v1/companions/{profile['id']}/context",
            json={},
            headers=headers,
        )
        assert context.status_code == 200
        payload = context.json()
        assert [item["content"] for item in payload["memory"]] == ["Use MEDDIC"]
        assert payload["tools"] == []

        disabled = client.patch(
            f"/api/v1/companions/{profile['id']}",
            json={"enabled": False},
            headers=headers,
        )
        assert disabled.status_code == 200
        refused = client.post(
            f"/api/v1/companions/{profile['id']}/context",
            json={},
            headers=headers,
        )
        assert refused.status_code == 400


def test_backup_restore_reopens_companion_and_tool_store(tmp_path):
    token = "r" * 40
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=token,
        allowed_hosts=("testserver",),
    )
    headers = {"X-Offsetx-Token": token}
    passphrase = "restore-companion-test-passphrase"
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/v1/companions",
            json={"name": "Restored", "instructions": "Survive the backup."},
            headers=headers,
        )
        assert created.status_code == 201
        companion_id = created.json()["id"]

        backup = client.post(
            "/api/v1/backups/export",
            json={"passphrase": passphrase},
            headers=headers,
        )
        assert backup.status_code == 200

        deleted = client.delete(
            f"/api/v1/companions/{companion_id}", headers=headers
        )
        assert deleted.status_code == 200
        assert client.get(
            f"/api/v1/companions/{companion_id}", headers=headers
        ).status_code == 404

        restored = client.post(
            "/api/v1/backups/restore",
            files={
                "file": (
                    "backup.oxbackup",
                    backup.content,
                    "application/octet-stream",
                )
            },
            data={"passphrase": passphrase},
            headers=headers,
        )
        assert restored.status_code == 200

        profile = client.get(
            f"/api/v1/companions/{companion_id}", headers=headers
        )
        assert profile.status_code == 200
        assert profile.json()["name"] == "Restored"

        # The post-restore registry is live, not a stale connection to the old DB.
        context = client.post(
            f"/api/v1/companions/{companion_id}/context",
            json={},
            headers=headers,
        )
        assert context.status_code == 200
