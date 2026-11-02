"""S-06.03.06: manual migration of old AI context records without silent loss."""
import sqlite3
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.context import ContextLayer
from offsetx_apollo_builder.db.context_import import ContextImportError, import_context


def _source(path):
    store = ContextLayer(path)
    task = store.start_task(workspace_id="alpha", title="A saved plan", steps=["Review"])
    store.record_decision(task.id, "Requires owner approval")
    store.register_template(workspace_id="alpha", template_id="intro", template_text="Hello")
    store.record_send(workspace_id="alpha", template_id="intro")
    store.record_reply(workspace_id="alpha", template_id="intro")
    store.close()
    return task


def test_import_preserves_history_and_workspace_scope(tmp_path):
    source = tmp_path / "local" / "ai_context.db"
    task = _source(source)
    destination = tmp_path / "hosted.db"
    archive = tmp_path / "private-archive" / "ai_context.db"
    assert import_context(source, str(destination), archive) == {
        "ai_task_state": 1, "ai_template_stats": 1
    }
    assert archive.is_file() and not source.exists()
    reopened = ContextLayer(tmp_path / "unused.db", database_target=str(destination))
    assert reopened.get_task(task.id).decisions[0]["text"] == "Requires owner approval"
    assert reopened.score_for("alpha", "intro").sends == 1
    assert reopened.score_for("alpha", "intro").replies == 1
    assert reopened.open_tasks("beta") == []
    reopened.close()


def test_existing_hosted_rows_refuse_merge_and_keep_original(tmp_path):
    source = tmp_path / "local" / "ai_context.db"
    _source(source)
    destination = str(tmp_path / "hosted.db")
    prior = ContextLayer(tmp_path / "unused.db", database_target=destination)
    prior.start_task(workspace_id="beta", title="existing")
    prior.close()
    with pytest.raises(ContextImportError, match="already contains"):
        import_context(source, destination, tmp_path / "archive" / "ai_context.db")
    assert source.exists()


def test_invalid_source_refused_without_initialising_a_new_source(tmp_path):
    source = tmp_path / "missing" / "ai_context.db"
    with pytest.raises(ContextImportError, match="source"):
        import_context(source, str(tmp_path / "hosted.db"), tmp_path / "archive" / "ai_context.db")
    assert not source.exists()


def test_sqlite_wal_data_is_included_in_archive(tmp_path):
    source = tmp_path / "local" / "ai_context.db"
    task = _source(source)
    archive = tmp_path / "archive" / "ai_context.db"
    import_context(source, str(tmp_path / "hosted.db"), archive)
    with sqlite3.connect(archive) as connection:
        assert connection.execute(
            "SELECT title FROM ai_task_state WHERE id=?", (task.id,)
        ).fetchone()[0] == "A saved plan"


def test_skip_preserves_old_history_in_archive_without_hosted_import(tmp_path):
    source = tmp_path / "local" / "ai_context.db"
    _source(source)
    archive = tmp_path / "archive" / "ai_context.db"
    destination = str(tmp_path / "hosted.db")
    assert import_context(source, destination, archive, skip=True) == {
        "ai_task_state": 1, "ai_template_stats": 1
    }
    assert archive.is_file() and not source.exists()
    hosted = ContextLayer(tmp_path / "unused.db", database_target=destination)
    assert hosted.open_tasks("alpha") == []
    hosted.close()


def test_archive_must_be_outside_ephemeral_source_dir(tmp_path):
    source = tmp_path / "local" / "ai_context.db"
    _source(source)
    with pytest.raises(ContextImportError, match="outside"):
        import_context(source, str(tmp_path / "hosted.db"), source.parent / "archive.db")
    assert source.exists()


def test_busy_workspace_blocks_migration(tmp_path):
    from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock
    source = tmp_path / "data" / "ai_context.db"
    _source(source)
    with WorkspaceLock(source.parent):
        with pytest.raises(ContextImportError, match="busy"):
            import_context(source, str(tmp_path / "target.db"), tmp_path / "archive" / "ai_context.db")
    assert source.exists()


def test_archive_is_private_and_can_restore_original_history(tmp_path):
    import stat
    source = tmp_path / "data" / "ai_context.db"
    task = _source(source)
    archive = tmp_path / "archive" / "ai_context.db"
    import_context(source, str(tmp_path / "target.db"), archive)
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert stat.S_IMODE(archive.parent.stat().st_mode) == 0o700
    recovered_path = tmp_path / "recovery" / "ai_context.db"
    recovered_path.parent.mkdir()
    recovered_path.write_bytes(archive.read_bytes())
    recovered = ContextLayer(recovered_path)
    assert recovered.get_task(task.id).title == "A saved plan"
    recovered.close()


def test_retry_after_database_commit_before_local_cleanup(tmp_path, monkeypatch):
    source = tmp_path / "data" / "ai_context.db"
    task = _source(source)
    destination = str(tmp_path / "target.db")
    archive = tmp_path / "archive" / "ai_context.db"
    original = Path.unlink
    def interrupt(path, *args, **kwargs):
        if path == source:
            raise OSError("simulated interrupted cleanup")
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", interrupt)
        with pytest.raises(OSError, match="interrupted cleanup"):
            import_context(source, destination, archive)
    assert archive.exists() and source.exists()
    import_context(source, destination, archive)
    assert not source.exists()
    hosted = ContextLayer(tmp_path / "unused.db", database_target=destination)
    assert hosted.get_task(task.id).title == "A saved plan"
    hosted.close()
