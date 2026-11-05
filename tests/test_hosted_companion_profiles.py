"""F-06.03.06: profile and owner-selected procedure rows survive ephemeral restarts."""
from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.db.hosted import HostedStorage


class EmptyMemory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


def _open(data: Path, *, target: str, key: str):
    data.mkdir(parents=True, exist_ok=True)
    tools = ToolRegistry(data / "ai_tools.db")
    storage = HostedStorage(target, key)
    companions = CompanionRegistry(
        data, tools=tools, memory_backend=EmptyMemory(), hosted_storage=storage
    )
    return companions, tools, storage


def test_companions_and_skills_survive_deleting_the_disposable_folder(tmp_path):
    key = Fernet.generate_key().decode()
    permanent = str(tmp_path / "durable" / "hosted.db")
    disposable = tmp_path / "throwaway"
    first, tools, storage = _open(disposable, target=permanent, key=key)
    owner = first.create(workspace_id="a", name="Scout", instructions="Find facts.")
    kept = first.create_skill(workspace_id="a", name="Review", content="Verify one source.")
    foreign = first.create_skill(workspace_id="b", name="Other", content="Private rules.")
    first.close()
    tools.close()
    storage.close()
    shutil.rmtree(disposable)

    new, new_tools, new_storage = _open(disposable, target=permanent, key=key)
    try:
        assert new.require(owner.id, workspace_id="a").name == "Scout"
        context = new.start(owner.id, workspace_id="a", skill_ids=[kept.id], memory_limit=0)
        assert "Verify one source." in context.model_instructions()
        assert "Private rules." not in context.model_instructions()
        with pytest.raises(CompanionError):
            new.start(owner.id, workspace_id="a", skill_ids=[foreign.id], memory_limit=0)
        new.update_skill(kept.id, workspace_id="a", enabled=False)
        with pytest.raises(CompanionError, match="disabled"):
            new.start(owner.id, workspace_id="a", skill_ids=[kept.id], memory_limit=0)
    finally:
        new.close()
        new_tools.close()
        new_storage.close()


def test_two_live_registries_observe_owner_revocation_without_cached_prompt(tmp_path):
    key = Fernet.generate_key().decode()
    target = str(tmp_path / "hosted" / "db.sqlite")
    one, tools1, storage1 = _open(tmp_path / "a", target=target, key=key)
    two, tools2, storage2 = _open(tmp_path / "b", target=target, key=key)
    try:
        owner = one.create(workspace_id="w", name="Director", instructions="Review.")
        skill = one.create_skill(workspace_id="w", name="Vetting", content="Cite evidence.")
        assert "Cite evidence." in two.start(
            owner.id, workspace_id="w", skill_ids=[skill.id], memory_limit=0
        ).model_instructions()
        one.update_skill(skill.id, workspace_id="w", enabled=False)
        with pytest.raises(CompanionError, match="disabled"):
            two.start(owner.id, workspace_id="w", skill_ids=[skill.id], memory_limit=0)
    finally:
        one.close()
        two.close()
        tools1.close()
        tools2.close()
        storage1.close()
        storage2.close()


@pytest.mark.skipif(
    not os.getenv("OFF_CRM_TEST_POSTGRES_URL"),
    reason="real PostgreSQL schema required",
)
def test_companion_profiles_and_skills_survive_real_postgres_instance_reconnect(tmp_path):
    import psycopg
    url = os.environ["OFF_CRM_TEST_POSTGRES_URL"]
    schema = "t_companion_" + uuid.uuid4().hex[:10]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    try:
        scoped = url + ("&" if "?" in url else "?") + "options=-csearch_path%3D" + schema
        key = Fernet.generate_key().decode()
        first, tools, storage = _open(tmp_path / "ephemeral", target=scoped, key=key)
        owner = first.create(workspace_id="workspace", name="Scout", instructions="See sources.")
        skill = first.create_skill(
            workspace_id="workspace", name="Owner procedure", content="Two citations.",
        )
        tools.close()
        storage.close()
        shutil.rmtree(tmp_path / "ephemeral")
        second, tools2, storage2 = _open(tmp_path / "ephemeral", target=scoped, key=key)
        try:
            assert second.require(owner.id, workspace_id="workspace").name == "Scout"
            assert second.start(
                owner.id, workspace_id="workspace", skill_ids=[skill.id],
            ).skills[0].content == "Two citations."
            assert second.list_skills(workspace_id="someone-else") == []
        finally:
            tools2.close()
            storage2.close()
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
