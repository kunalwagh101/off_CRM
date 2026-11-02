"""S-06.03.06: AI task memory and template counts survive a wiped app disk.

No hosted fallback to local files. Existing local data needs explicit migration.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.context import ContextLayer
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def test_hosted_context_survives_restart_and_ephemeral_folder_removal(tmp_path):
    db = tmp_path / "durable" / "shared.db"
    db.parent.mkdir()
    transient = tmp_path / "transient"
    transient.mkdir()
    first = ContextLayer(transient / "ai_context.db", database_target=str(db))
    task = first.start_task(workspace_id="alpha", title="Win importers", steps=["Find", "Send"])
    first.finish_step(task.id, 0, note="approved")
    first.record_decision(task.id, "Use opt-in only")
    first.register_template(workspace_id="alpha", template_id="intro", template_text="Hi there")
    first.record_send(workspace_id="alpha", template_id="intro")
    first.record_reply(workspace_id="alpha", template_id="intro")
    first.close()
    assert not (transient / "ai_context.db").exists()
    shutil.rmtree(transient)
    transient.mkdir()

    second = ContextLayer(transient / "ai_context.db", database_target=str(db))
    assert second.get_task(task.id).done_count == 1
    assert second.get_task(task.id).decisions[-1]["text"] == "Use opt-in only"
    assert second.score_for("alpha", "intro").sends == 1
    assert second.score_for("alpha", "intro").replies == 1
    second.close()


def test_hosted_context_is_workspace_scoped(tmp_path):
    db = str(tmp_path / "shared.db")
    context = ContextLayer(tmp_path / "local.db", database_target=db)
    context.start_task(workspace_id="alpha", title="private")
    context.start_task(workspace_id="beta", title="other")
    context.register_template(workspace_id="alpha", template_id="intro", template_text="alpha")
    context.register_template(workspace_id="beta", template_id="intro", template_text="beta")
    assert len(context.open_tasks("alpha")) == 1
    assert len(context.open_tasks("beta")) == 1
    assert context.score_for("beta", "intro").template_text == "beta"
    assert context.score_for("alpha", "intro").template_text == "alpha"
    context.close()


def test_hosted_context_does_not_fall_back_to_a_local_database_on_error(tmp_path):
    invalid_target = tmp_path / "missing" / "database.db"
    invalid_target.parent.mkdir()
    invalid_target.write_text("not an sqlite file", encoding="utf-8")
    local = tmp_path / "ephemeral" / "ai_context.db"
    context = ContextLayer(local, database_target=str(invalid_target))
    with pytest.raises(Exception):
        context.start_task(workspace_id="alpha", title="this must fail")
    assert not local.exists()
    context.close()


def test_hosted_app_uses_database_for_ai_context_and_survives_restart(tmp_path, monkeypatch):
    target = str(tmp_path / "durable" / "shared.db")
    Path(target).parent.mkdir()
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("OFFSETX_DATABASE_URL", target)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    data = tmp_path / "ephemeral"
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=data / "outreach.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=tmp_path / "missing",
        host="127.0.0.1",
        secrets_key=key,
        api_token="hosted-context-test-" + "a" * 36,
        allowed_hosts=("testserver",),
    )
    first = create_app(settings)
    with TestClient(first, headers={"X-Offsetx-Token": settings.api_token}) as client:
        task = first.state.ai_context.start_task(workspace_id="team", title="persist")
        assert client.get("/health/ready").status_code == 200
        first.state.ai_context.register_template(
            workspace_id="team", template_id="v1", template_text="Hello"
        )
    assert not (data / "ai_context.db").exists()
    shutil.rmtree(data)
    second = create_app(settings)
    with TestClient(second, headers={"X-Offsetx-Token": settings.api_token}) as client:
        assert client.get("/health/ready").status_code == 200
        assert second.state.ai_context.get_task(task.id).title == "persist"
        assert second.state.ai_context.score_for("team", "v1").template_text == "Hello"


def test_hosted_app_does_not_silently_ignore_old_local_context(tmp_path, monkeypatch):
    target = str(tmp_path / "durable" / "shared.db")
    Path(target).parent.mkdir()
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("OFFSETX_DATABASE_URL", target)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    data = tmp_path / "ephemeral"
    data.mkdir()
    old = ContextLayer(data / "ai_context.db")
    old.start_task(workspace_id="alpha", title="old owner task")
    old.close()
    settings = AppSettings(
        project_root=Path.cwd(), database_path=data / "outreach.db",
        data_dir=data, export_dir=data / "exports", frontend_dist=tmp_path / "none",
        host="127.0.0.1", secrets_key=key, api_token="context-migration-test-"+"b"*36,
    )
    with pytest.raises(ValueError, match="AI context|ai_context"):
        create_app(settings)


@pytest.mark.skipif(
    not __import__("os").getenv("OFF_CRM_TEST_POSTGRES_URL"),
    reason="disposable PostgreSQL connection only in isolated Render QA",
)
def test_hosted_context_on_disposable_postgres_after_reconnect(tmp_path):
    import os
    import uuid
    import psycopg
    base = os.environ["OFF_CRM_TEST_POSTGRES_URL"]
    schema = "context_" + uuid.uuid4().hex[:12]
    with psycopg.connect(base, autocommit=True) as con:
        con.execute(f'CREATE SCHEMA "{schema}"')
    url = base + ("&" if "?" in base else "?") + "options=-csearch_path%3D" + schema
    try:
        first = ContextLayer(tmp_path / "local.db", database_target=url)
        t = first.start_task(workspace_id="alpha", title="PG survives")
        first.record_decision(t.id, "Owner confirms")
        first.register_template(workspace_id="alpha", template_id="pg")
        first.record_send(workspace_id="alpha", template_id="pg")
        first.close()
        reopened = ContextLayer(tmp_path / "local.db", database_target=url)
        assert reopened.get_task(t.id).decisions[0]["text"] == "Owner confirms"
        assert reopened.score_for("alpha", "pg").sends == 1
        assert not (tmp_path / "local.db").exists()
        reopened.close()
    finally:
        with psycopg.connect(base, autocommit=True) as con:
            con.execute(f'DROP SCHEMA "{schema}" CASCADE')
