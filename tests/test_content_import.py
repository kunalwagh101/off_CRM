"""Owner-approved, archive-first metadata migration through the real CLI."""

import sqlite3
import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder import db_cli
from offsetx_apollo_builder.imagery.store import ImageStore


def setup_source(tmp_path, monkeypatch):
    data = tmp_path / "local"
    source = data / "imagery.db"
    store = ImageStore(source, assets_dir=data / "assets")
    item = store.create_brief(
        campaign_id="campaign", brief="Keep this brief", workspace_id="alpha"
    )
    store.close()
    target = tmp_path / "hosted.db"
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(target))
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", Fernet.generate_key().decode())
    archive = tmp_path / "private" / "original.sqlite"
    return source, target, archive, item


def command(source, archive, *extra):
    return [
        "import-content",
        "--kind",
        "imagery",
        "--source",
        str(source),
        "--archive",
        str(archive),
        *extra,
    ]


def test_cli_migrates_verified_metadata_and_keeps_complete_private_archive(
    tmp_path, monkeypatch
):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    assert db_cli.main(command(source, archive, "--yes")) == 0
    with sqlite3.connect(target) as conn:
        assert (
            conn.execute(
                "SELECT brief FROM image_briefs WHERE id=?", (item,)
            ).fetchone()[0]
            == "Keep this brief"
        )
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT count(*) FROM image_briefs").fetchone()[0] == 0
    with sqlite3.connect(archive) as conn:
        assert conn.execute("SELECT count(*) FROM image_briefs").fetchone()[0] == 1
    assert archive.stat().st_mode & 0o777 == 0o600
    assert archive.parent.stat().st_mode & 0o777 == 0o700


def test_cli_requires_explicit_owner_approval(tmp_path, monkeypatch):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    assert db_cli.main(command(source, archive)) == 2
    assert not target.exists() and not archive.exists()
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchone()[0] == item


def test_conflicting_target_preserves_source_and_existing_hosted_rows(
    tmp_path, monkeypatch
):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    existing = ImageStore(target, assets_dir=tmp_path / "other-assets")
    foreign = existing.create_brief(
        campaign_id="other", brief="Do not overwrite", workspace_id="beta"
    )
    existing.close()
    assert db_cli.main(command(source, archive, "--yes")) == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchone()[0] == item
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(foreign,)]


def test_symlink_archive_and_same_source_archive_are_refused(tmp_path, monkeypatch):
    source, _, archive, _ = setup_source(tmp_path, monkeypatch)
    assert db_cli.main(command(source, source, "--yes")) == 2
    archive.parent.mkdir(mode=0o700)
    other = tmp_path / "untouched"
    other.write_text("keep")
    archive.symlink_to(other)
    assert db_cli.main(command(source, archive, "--yes")) == 2
    assert other.read_text() == "keep"


def test_archive_mismatch_cannot_erase_source(tmp_path, monkeypatch):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    archive.parent.mkdir(mode=0o700)
    archive.write_bytes(b"not a matching private archive")
    archive.chmod(0o600)
    assert db_cli.main(command(source, archive, "--yes")) == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchone()[0] == item


def test_source_cannot_also_be_the_hosted_target(tmp_path, monkeypatch):
    source, _, archive, item = setup_source(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", str(source))
    assert db_cli.main(command(source, archive, "--yes")) == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchone()[0] == item


def test_retry_after_hosted_commit_accepts_identical_rows(tmp_path, monkeypatch):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    # Simulate a crash after target commit by restoring only the source rows
    # from the retained archive. No original/private data is discarded.
    assert db_cli.main(command(source, archive, "--yes")) == 0
    with sqlite3.connect(archive) as original, sqlite3.connect(source) as local:
        original.backup(local)
    assert db_cli.main(command(source, archive, "--yes")) == 0
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]


def test_active_workspace_prevents_migration(tmp_path, monkeypatch):
    from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock

    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    with WorkspaceLock(source.parent):
        assert db_cli.main(command(source, archive, "--yes")) == 2
    assert not archive.exists()
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchone()[0] == item


def test_hardlinked_archive_is_refused_before_source_or_archive_rows_change(
    tmp_path, monkeypatch
):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    source.chmod(0o600)
    archive.parent.mkdir(mode=0o700)
    archive.hardlink_to(source)
    assert db_cli.main(command(source, archive, "--yes")) == 2
    for path in (source, archive):
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]


def test_hardlinked_hosted_target_is_refused_before_mutation(tmp_path, monkeypatch):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    target.hardlink_to(source)
    with sqlite3.connect(source) as conn:
        before = conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    assert db_cli.main(command(source, archive, "--yes")) == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]
        assert (
            conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
            == before
        )


def test_hardlinked_target_archive_is_refused_without_changing_either(
    tmp_path, monkeypatch
):
    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    archive.parent.mkdir(mode=0o700)
    with sqlite3.connect(source) as original, sqlite3.connect(archive) as backup:
        original.backup(backup)
    archive.chmod(0o600)
    target.hardlink_to(archive)
    before = archive.read_bytes()
    assert db_cli.main(command(source, archive, "--yes")) == 2
    assert archive.read_bytes() == before
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]


def test_actual_process_crash_after_hosted_commit_can_retry_without_duplicates(
    tmp_path, monkeypatch
):
    import subprocess
    import sys

    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    child = """
import os, sys
from pathlib import Path
from offsetx_apollo_builder.db.hosted import HostedStorage
import offsetx_apollo_builder.db.content_import as module
storage = HostedStorage.configured(os.environ['OFFSETX_SECRETS_KEY'])
module._clear_source = lambda *args: os._exit(97)
module.import_content(Path(sys.argv[1]), storage, Path(sys.argv[2]), kind='imagery')
"""
    crashed = subprocess.run(
        [sys.executable, "-c", child, str(source), str(archive)], timeout=20
    )
    assert crashed.returncode == 97
    for path in (source, archive, target):
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]
    assert db_cli.main(command(source, archive, "--yes")) == 0
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT count(*) FROM image_briefs").fetchone()[0] == 1


def test_insert_failure_rolls_back_target_and_keeps_source(tmp_path, monkeypatch):
    from offsetx_apollo_builder.db.hosted import HostedStorage
    from offsetx_apollo_builder.db.content_import import import_content

    source, target, archive, item = setup_source(tmp_path, monkeypatch)
    with sqlite3.connect(source) as conn:
        conn.execute(
            "INSERT INTO image_generator_stats(id,workspace_id,provider_id,model_id,updated_at) VALUES('stats','alpha','p','m','2026-11-06')"
        )
    storage = HostedStorage.configured(os.environ["OFFSETX_SECRETS_KEY"])
    database = storage.connection
    real_execute = database.execute

    def fail_late(statement, params=None):
        if statement.startswith('INSERT INTO "image_generator_stats"'):
            raise RuntimeError("simulated late write failure")
        return real_execute(statement, params)

    monkeypatch.setattr(database, "execute", fail_late)
    try:
        with pytest.raises(RuntimeError, match="late write"):
            import_content(source, storage, archive, kind="imagery")
        assert (
            database.execute("SELECT count(*) AS n FROM image_briefs").fetchone()["n"]
            == 0
        )
        with sqlite3.connect(source) as conn:
            assert conn.execute("SELECT id FROM image_briefs").fetchall() == [(item,)]
    finally:
        storage.close()
