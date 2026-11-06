"""Actual PostgreSQL cutover, numeric range and reconnect acceptance."""

from cryptography.fernet import Fernet

from offsetx_apollo_builder.db.content_import import import_content
from offsetx_apollo_builder.db.hosted import HostedStorage
from offsetx_apollo_builder.distribution.trends import TrendWatcher
from offsetx_apollo_builder.distribution.store import DistributionStore


def test_real_postgres_migrates_large_trend_counts_and_survives_reconnect(
    tmp_path, isolated_postgres_target
):
    source = tmp_path / "local" / "trends.db"
    local = TrendWatcher(database_path=source, workspace_id="alpha")
    local.connection.execute(
        "INSERT INTO yt_channels(id,workspace_id,channel_id,title,subscribers,created_at) VALUES(?,?,?,?,?,?)",
        ("channel", "alpha", "public-source", "Source", 3_000_000_000, "2026-11-06"),
    )
    local.connection.execute(
        "INSERT INTO yt_videos(id,workspace_id,video_id,channel_id,views,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
        (
            "video",
            "alpha",
            "video",
            "public-source",
            3_000_000_000,
            "2026-11-06",
            "2026-11-06",
        ),
    )
    local.close()
    storage = HostedStorage(isolated_postgres_target, Fernet.generate_key().decode())
    try:
        counts = import_content(
            source, storage, tmp_path / "private" / "trends.sqlite", kind="trends"
        )
        assert counts == {"yt_channels": 1, "yt_videos": 1}
    finally:
        storage.close()
    remote = TrendWatcher(database_path=isolated_postgres_target, workspace_id="alpha")
    try:
        assert remote.watched()[0]["subscribers"] == 3_000_000_000
        assert (
            remote.connection.execute("SELECT views FROM yt_videos").fetchone()["views"]
            == 3_000_000_000
        )
        other = TrendWatcher(
            database_path=isolated_postgres_target, workspace_id="beta"
        )
        try:
            assert other.watched() == []
        finally:
            other.close()
    finally:
        remote.close()


def test_real_postgres_can_record_large_post_metrics(
    tmp_path, isolated_postgres_target
):
    store = DistributionStore(isolated_postgres_target, outbox_dir=tmp_path / "outbox")
    try:
        store.record_metrics(
            post_id="p",
            campaign_id="campaign",
            views=3_000_000_000,
            workspace_id="alpha",
        )
        row = store.connection.execute("SELECT views FROM dist_metrics").fetchone()
        assert row["views"] == 3_000_000_000
    finally:
        store.close()


def test_real_postgres_upgrades_version_one_without_losing_counter_rows(
    tmp_path, isolated_postgres_target
):
    from offsetx_apollo_builder.db import open_database
    from offsetx_apollo_builder.db.schema import ensure_schema
    from offsetx_apollo_builder.distribution.trends import SCHEMA

    database = open_database(isolated_postgres_target)
    try:

        def legacy_schema(target):
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    target.execute(statement)

        ensure_schema(database, "trends", [legacy_schema])
        database.execute(
            "INSERT INTO yt_channels(id,workspace_id,channel_id,subscribers,created_at) VALUES(?,?,?,?,?)",
            ("one", "alpha", "source", 42, "2026-11-06"),
        )
    finally:
        database.close()
    current = TrendWatcher(database_path=isolated_postgres_target, workspace_id="alpha")
    try:
        assert current.watched()[0]["subscribers"] == 42
        current.connection.execute(
            "UPDATE yt_channels SET subscribers=? WHERE id=?", (3_000_000_000, "one")
        )
        assert current.watched()[0]["subscribers"] == 3_000_000_000
        assert (
            current.connection.execute(
                "SELECT version FROM offcrm_schema WHERE component='trends'"
            ).fetchone()["version"]
            == 2
        )
    finally:
        current.close()
