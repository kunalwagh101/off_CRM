"""F-06.03.06: archive-first cutover of legacy local companion rows."""
from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.agent.companions import SCHEMA, CompanionRegistry, CompanionError
from offsetx_apollo_builder.db.companion_import import (
    CompanionImportError, import_companions,
)
from offsetx_apollo_builder.db.hosted import HostedStorage


class Memory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


def _start(tmp_path):
    local = tmp_path / "data"
    local.mkdir(exist_ok=True)
    tools = ToolRegistry(local / "ai_tools.db")
    companions = CompanionRegistry(local, tools=tools, memory_backend=Memory())
    key = Fernet.generate_key().decode()
    storage = HostedStorage(str(tmp_path / "hosted.db"), key)
    return local, tools, companions, storage


def _archive(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700, exist_ok=True)
    return folder / "local-tools-full.sqlite"


def test_import_preserves_profiles_and_skills_while_retaining_tool_database(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    own = registry.create(workspace_id="one", name="Scout", instructions="Owner text.")
    skill = registry.create_skill(workspace_id="one", name="Sourcing", content="Check sources.")
    registry.create_skill(workspace_id="two", name="Private", content="Another workspace.")
    tool = tools.register(
        name="read-only-check", repository_url="https://github.com/kunalwagh101/off_CRM",
        commit_sha="a" * 40, image="python:3.12-slim",
        command=["pytest", "-q"], workspace_id="one",
    )
    source, archive = local / "ai_tools.db", _archive(tmp_path)
    tools.close()

    counts = import_companions(source, hosted, archive)
    assert counts == {"agent_companions": 1, "agent_companion_skills": 2}
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM agent_companion_skills").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM ai_tools").fetchone()[0] == 1
    with sqlite3.connect(archive) as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM agent_companion_skills").fetchone()[0] == 2

    tools2 = ToolRegistry(source)
    fresh = CompanionRegistry(local, tools=tools2, memory_backend=Memory(), hosted_storage=hosted)
    assert tools2.get(tool.id, workspace_id="one") is not None
    assert fresh.require(own.id, workspace_id="one").name == "Scout"
    assert fresh.start(own.id, workspace_id="one", skill_ids=[skill.id]).skills[0].content == "Check sources."
    assert fresh.list_skills(workspace_id="two")[0].name == "Private"
    tools2.close()
    hosted.close()


def test_conflicting_hosted_data_does_not_destroy_original(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="Local text.")
    source, archive = local / "ai_tools.db", _archive(tmp_path)
    tools.close()
    remote_tools = ToolRegistry(tmp_path / "temp-tools.db")
    remote = CompanionRegistry(tmp_path, tools=remote_tools, memory_backend=Memory(), hosted_storage=hosted)
    remote.create(workspace_id="w", name="Director", instructions="Other text.")
    with pytest.raises(CompanionImportError, match="different"):
        import_companions(source, hosted, archive)
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1
    with sqlite3.connect(archive) as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1
    remote_tools.close()
    hosted.close()


def test_source_with_executable_tool_grants_is_refused_until_tool_home_is_durable(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    profile = registry.create(workspace_id="w", name="Scout", instructions="No tool.")
    tools.connection().execute(
        "UPDATE agent_companions SET granted_tool_ids='[\"external-runner\"]' WHERE id=?",
        (profile.id,),
    )
    tools.close()
    with pytest.raises(CompanionImportError, match="tool grants"):
        import_companions(local / "ai_tools.db", hosted, _archive(tmp_path))
    with sqlite3.connect(local / "ai_tools.db") as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1
    hosted.close()


def test_archive_cannot_be_inside_old_data_directory(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="Keep.")
    tools.close()
    with pytest.raises(CompanionImportError, match="outside"):
        import_companions(local / "ai_tools.db", hosted, local / "bad-archive.sqlite")
    hosted.close()


def test_target_that_resolves_to_the_same_sqlite_file_is_refused(tmp_path):
    local, tools, registry, unused = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="Keep.")
    unused.close()
    tools.close()
    source = local / "ai_tools.db"
    # The database target is deliberately relative to cwd, to catch aliasing.
    alias = os.path.relpath(source, Path.cwd())
    bad = HostedStorage(alias, Fernet.generate_key().decode())
    try:
        with pytest.raises(CompanionImportError, match="different"):
            import_companions(source, bad, _archive(tmp_path))
        with sqlite3.connect(source) as con:
            assert con.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1
    finally:
        bad.close()


def test_missing_legacy_source_fails_closed(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    tools.close()
    with pytest.raises(CompanionImportError, match="existing"):
        import_companions(tmp_path / "absent.db", hosted, _archive(tmp_path))
    hosted.close()


def test_retry_after_hosted_commit_before_local_cleanup_is_safe(tmp_path, monkeypatch):
    local, tools, registry, hosted = _start(tmp_path)
    owner = registry.create(workspace_id="w", name="Scout", instructions="Keep.")
    tools.close()
    source, archive = local / "ai_tools.db", _archive(tmp_path)

    import offsetx_apollo_builder.db.companion_import as module
    real_cleanup = module._clear_local_rows
    first = {"remaining": 1}

    def fail_once(*args, **kwargs):
        if first["remaining"]:
            first["remaining"] = 0
            raise OSError("simulated interruption before local cleanup")
        return real_cleanup(*args, **kwargs)

    monkeypatch.setattr(module, "_clear_local_rows", fail_once)
    with pytest.raises(OSError):
        import_companions(source, hosted, archive)
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 1

    result = import_companions(source, hosted, archive)
    assert result["agent_companions"] == 1
    tools2 = ToolRegistry(source)
    fresh = CompanionRegistry(local, tools=tools2, memory_backend=Memory(), hosted_storage=hosted)
    assert fresh.require(owner.id, workspace_id="w").name == "Scout"
    tools2.close()
    hosted.close()


def test_operator_cli_requires_explicit_yes_and_private_archive(tmp_path, monkeypatch):
    from offsetx_apollo_builder.db_cli import main

    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="CLI.")
    tools.close()
    archive = _archive(tmp_path)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(tmp_path / "hosted.db"))
    # Approval validation runs before reading any hosted credentials.
    assert main(["import-companions", "--archive", str(archive)]) == 2
    hosted.close()


def test_old_companion_schema_without_procedures_imports_without_data_loss(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="Historic.")
    tools.close()
    source = local / "ai_tools.db"
    with sqlite3.connect(source) as db:
        db.execute("DROP TABLE agent_companion_skills")
    try:
        result = import_companions(source, hosted, _archive(tmp_path))
        assert result == {"agent_companions": 1, "agent_companion_skills": 0}
        with sqlite3.connect(source) as db:
            assert db.execute("SELECT count(*) FROM agent_companions").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM ai_tools").fetchone()[0] == 0
    finally:
        hosted.close()


def test_existing_different_private_archive_never_gets_overwritten(tmp_path):
    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="New.")
    tools.close()
    archive = _archive(tmp_path)
    with sqlite3.connect(archive) as db:
        db.executescript(SCHEMA)
        db.execute(
            "INSERT INTO agent_companions VALUES (?,?,?,?,?,?,?,?,?)",
            ("old", "w", "Scout", "Old.", "companion:old", "[]", 1, "then", "then"),
        )
    archive.chmod(0o600)
    try:
        with pytest.raises(CompanionImportError, match="differs"):
            import_companions(local / "ai_tools.db", hosted, archive)
        with sqlite3.connect(archive) as db:
            assert db.execute("SELECT instructions FROM agent_companions").fetchone()[0] == "Old."
    finally:
        hosted.close()


def test_uncooperative_writer_prevents_cleanup_of_changed_source(tmp_path, monkeypatch):
    local, tools, registry, hosted = _start(tmp_path)
    registry.create(workspace_id="w", name="Scout", instructions="Original.")
    tools.close()
    source = local / "ai_tools.db"
    import offsetx_apollo_builder.db.companion_import as module
    actual = module._clear_local_rows

    def change_after_copy(path, expected):
        with sqlite3.connect(path) as con:
            con.execute(
                "UPDATE agent_companions SET instructions='Changed after copy'"
            )
        return actual(path, expected)

    monkeypatch.setattr(module, "_clear_local_rows", change_after_copy)
    try:
        with pytest.raises(CompanionImportError, match="source changed|source changed during|The source changed"):
            import_companions(source, hosted, _archive(tmp_path))
        with sqlite3.connect(source) as con:
            assert con.execute("SELECT instructions FROM agent_companions").fetchone()[0] == "Changed after copy"
        assert hosted.connection.execute(
            "SELECT instructions FROM agent_companions"
        ).fetchone()["instructions"] == "Original."
    finally:
        hosted.close()


@pytest.mark.skipif(not os.getenv("OFF_CRM_TEST_POSTGRES_URL"), reason="disposable real PostgreSQL not configured")
def test_real_postgres_import_reconciles_and_survives_restart(tmp_path):
    import uuid
    import psycopg

    local, tools, registry, unused = _start(tmp_path)
    unused.close()
    own = registry.create(workspace_id="workspace", name="Scout", instructions="Persist.")
    tools.close()
    url = os.environ["OFF_CRM_TEST_POSTGRES_URL"]
    schema = "t_import_" + uuid.uuid4().hex[:10]
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    scoped = url + ("&" if "?" in url else "?") + "options=-csearch_path%3D" + schema
    key = Fernet.generate_key().decode()
    hosted = HostedStorage(scoped, key)
    try:
        imported = import_companions(local / "ai_tools.db", hosted, _archive(tmp_path))
        assert imported["agent_companions"] == 1
        hosted.close()
        hosted2 = HostedStorage(scoped, key)
        tools2 = ToolRegistry(local / "ai_tools.db")
        try:
            assert CompanionRegistry(local, tools=tools2, memory_backend=Memory(), hosted_storage=hosted2).require(
                own.id, workspace_id="workspace"
            ).name == "Scout"
        finally:
            tools2.close()
            hosted2.close()
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
