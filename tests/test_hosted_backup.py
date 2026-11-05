"""F-06.03 hosted-backup acceptance. No live account or customer database touched."""
from __future__ import annotations

import base64
import json
import os
import struct
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from offsetx_apollo_builder.db import hosted_backup as backup


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict]] = {}

    def upload_file(self, source, bucket, name, ExtraArgs):
        self.objects[bucket, name] = (Path(source).read_bytes(), ExtraArgs["Metadata"])

    def head_object(self, *, Bucket, Key):
        payload, meta = self.objects[Bucket, Key]
        return {"ContentLength": len(payload), "Metadata": dict(meta)}

    def download_file(self, bucket, key, destination):
        Path(destination).write_bytes(self.objects[bucket, key][0])


@pytest.fixture
def backup_key():
    return base64.urlsafe_b64decode(backup.new_backup_key())


def _envelope(path: Path, key: bytes, manifest: dict, data: bytes = b"PGDMP") -> None:
    nonce = b"n" * backup.NONCE_BYTES
    enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    enc.authenticate_additional_data(backup.MAGIC)
    payload = json.dumps(manifest).encode()
    path.write_bytes(
        backup.MAGIC + nonce +
        enc.update(struct.pack(">I", len(payload)) + payload + data) +
        enc.finalize() + enc.tag
    )


def test_backup_key_is_separate_and_bad_lengths_fail(monkeypatch, backup_key):
    assert len(backup_key) == 32
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", "not-the-backup-key")
    monkeypatch.setenv(backup.BACKUP_KEY_ENV, base64.urlsafe_b64encode(backup_key).decode())
    assert backup._backup_key() == backup_key
    with pytest.raises(backup.HostedBackupError, match="32 random bytes"):
        backup._backup_key(base64.urlsafe_b64encode(b"short").decode())
    with pytest.raises(backup.HostedBackupError, match="32-byte base64"):
        backup._backup_key("!invalid")
    assert backup._backup_key() != base64.urlsafe_b64decode(backup.new_backup_key())


def test_pg_credentials_are_not_placed_into_child_process_arguments():
    url = "postgresql://owned_user:p%40ssw0rd@db.example.com:5432/app?sslmode=require"
    env = backup._pg_environment(url)
    assert env["PGPASSWORD"] == "p@ssw0rd"
    assert env["PGDATABASE"] == "app"
    assert env["PGSSLMODE"] == "require"
    assert "p@ssw0rd" not in " ".join(["pg_dump", "--format=custom"])
    with pytest.raises(backup.HostedBackupError, match="unsupported"):
        backup._pg_environment(url + "&unexpected=insecure")


def test_authenticated_backup_rejects_wrong_key_and_altered_ciphertext(tmp_path, backup_key):
    path = tmp_path / "ciphertext"
    plain = tmp_path / "plaintext"
    expected = {json.dumps(["public", "contacts"], separators=(",", ":")): 2}
    _envelope(path, backup_key, {"version": 1, "counts": expected})
    assert backup._decrypt_snapshot(path, plain, backup_key) == expected
    assert plain.read_bytes().endswith(b"PGDMP")
    plain.unlink()
    with pytest.raises(backup.HostedBackupError, match="authentication failed"):
        backup._decrypt_snapshot(path, plain, b"z" * 32)
    content = bytearray(path.read_bytes())
    content[-17] ^= 1
    path.write_bytes(content)
    with pytest.raises(backup.HostedBackupError, match="authentication failed"):
        backup._decrypt_snapshot(path, plain, backup_key)


def test_s3_export_uploads_ciphertext_then_checks_remote_hash(tmp_path, backup_key, monkeypatch):
    store = FakeS3()
    calls = []

    def fake_dump(path, url, key, *, maximum_bytes):
        calls.append(url)
        _envelope(path, key, {"version": 1, "counts": {"test": 3}})
        return {"test": 3}

    monkeypatch.setattr(backup, "_write_encrypted_snapshot", fake_dump)
    result = backup.export_to_s3("postgresql://db/hosted", bucket="backups-private",
                                 prefix="offcrm/nightly", key=backup_key, client=store)
    assert calls == ["postgresql://db/hosted"]
    assert result["encrypted_bytes"] > 30
    assert result["tables"] == 1
    assert store.head_object(Bucket="backups-private", Key=result["key"])["Metadata"]["sha256"] == result["sha256"]
    downloaded = backup.download_ciphertext(result["key"], tmp_path / "download.enc",
                                             bucket="backups-private", client=store)
    assert backup._decrypt_snapshot(downloaded, tmp_path / "decrypted", backup_key) == {"test": 3}
    with pytest.raises(backup.HostedBackupError, match="already exists"):
        backup.download_ciphertext(result["key"], downloaded, bucket="backups-private", client=store)


def test_s3_refuses_unverified_or_tampered_remote_objects(tmp_path, backup_key, monkeypatch):
    store = FakeS3()
    def fake_dump(path, url, key, *, maximum_bytes):
        _envelope(path, key, {"version": 1, "counts": {}})
        return {}
    monkeypatch.setattr(backup, "_write_encrypted_snapshot", fake_dump)
    result = backup.export_to_s3("postgresql://db/hosted", bucket="backups-private",
                                 key=backup_key, client=store)
    encoded, meta = store.objects["backups-private", result["key"]]
    store.objects["backups-private", result["key"]] = (encoded + b"!", meta)
    with pytest.raises(backup.HostedBackupError, match="checksum"):
        backup.download_ciphertext(result["key"], tmp_path / "altered.enc",
                                   bucket="backups-private", client=store)
    assert not (tmp_path / "altered.enc").exists()


def test_s3_keys_refuse_traversal_or_unapproved_destination():
    for key in ("../other/secret", "/absolute", "a/../../b", ""):
        with pytest.raises(backup.HostedBackupError):
            backup._object_key(key)
    with pytest.raises(backup.HostedBackupError):
        backup._bucket("")


def test_restore_rejects_views_functions_types_schemas_and_extensions_without_dropping():
    """D-380: no table rows does not mean a PostgreSQL database is empty."""
    class FakeConnection:
        def __init__(self, existing):
            self.existing = existing
            self.sql = []

        def execute(self, query):
            self.sql.append(query)
            return self

        def fetchone(self):
            return (self.existing,)

    for existing in (True, False):
        conn = FakeConnection(existing)
        if existing:
            with pytest.raises(backup.HostedBackupError, match="not empty"):
                backup._ensure_empty_restore_target(conn)
        else:
            backup._ensure_empty_restore_target(conn)
        sql = " ".join(conn.sql)
        assert "pg_catalog.pg_class" in sql
        assert "pg_catalog.pg_proc" in sql
        assert "pg_catalog.pg_type" in sql
        assert "pg_catalog.pg_namespace" in sql
        assert "pg_catalog.pg_extension" in sql


@pytest.mark.skipif(
    not os.getenv("OFF_CRM_TEST_POSTGRES_URL"),
    reason="requires disposable PostgreSQL with CREATEDB and pg_dump/pg_restore",
)
def test_real_postgres_snapshot_survives_object_copy_and_restores_equal_counts(
    tmp_path, backup_key,
):
    import uuid
    from urllib.parse import urlsplit, urlunsplit
    import psycopg
    from psycopg import sql

    url = os.environ["OFF_CRM_TEST_POSTGRES_URL"]
    parts = urlsplit(url)
    seed = uuid.uuid4().hex[:12]
    source_name, destination_name = "backup_src_" + seed, "backup_dst_" + seed

    def named(database):
        return urlunsplit((parts.scheme, parts.netloc, "/" + database, parts.query, ""))

    # Administration uses the test's authorised CREATEDB role, never customer DB.
    with psycopg.connect(url, autocommit=True) as admin:
        for name in (source_name, destination_name):
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with psycopg.connect(named(source_name)) as conn:
            conn.execute("CREATE TABLE test_customer (workspace TEXT NOT NULL, n INTEGER NOT NULL)")
            conn.execute("INSERT INTO test_customer VALUES ('alpha', 1), ('beta', 2)")
            conn.commit()

        store = FakeS3()
        result = backup.export_to_s3(named(source_name), bucket="backups-private",
                                     client=store, key=backup_key)
        encrypted = backup.download_ciphertext(
            result["key"], tmp_path / "encrypted.enc", bucket="backups-private", client=store
        )
        # A database with no tables can still contain customer objects.
        # Reject those before pg_restore can create/drop anything.
        for create, drop in (
            ("CREATE VIEW protected_view AS SELECT 42 AS confidential",
             "DROP VIEW protected_view"),
            ("CREATE FUNCTION protected_function() RETURNS integer "
             "LANGUAGE SQL AS $SELECT 42$",
             "DROP FUNCTION protected_function()"),
            ("CREATE TYPE protected_status AS ENUM (\'active\')",
             "DROP TYPE protected_status"),
            ("CREATE SCHEMA protected_schema",
             "DROP SCHEMA protected_schema"),
        ):
            with psycopg.connect(named(destination_name)) as conn:
                conn.execute(create)
                conn.commit()
            with pytest.raises(backup.HostedBackupError, match="not empty"):
                backup.restore_to_empty_postgres(
                    encrypted, named(destination_name), key=backup_key
                )
            with psycopg.connect(named(destination_name)) as conn:
                conn.execute(drop)
                conn.commit()

        restored = backup.restore_to_empty_postgres(encrypted, named(destination_name), key=backup_key)
        assert restored[json.dumps(["public", "test_customer"], separators=(",", ":"))] == 2
        with psycopg.connect(named(destination_name)) as conn:
            assert conn.execute("SELECT workspace, n FROM test_customer ORDER BY n").fetchall() == [
                ("alpha", 1), ("beta", 2),
            ]
        with pytest.raises(backup.HostedBackupError, match="not empty"):
            backup.restore_to_empty_postgres(encrypted, named(destination_name), key=backup_key)
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            for name in (source_name, destination_name):
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
