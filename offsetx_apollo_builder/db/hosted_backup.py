"""Encrypted, off-database PostgreSQL backups (F-06.03 / S-06.03.04).

The application never sends plaintext backups to object storage. The dedicated
backup key is independent of provider-key encryption. No live restore, overwrite,
or external account creation happens without an explicit operator command.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidTag

MAGIC = b"OFFCRM1\x00"
NONCE_BYTES = 12
TAG_BYTES = 16
CHUNK_BYTES = 1024 * 1024
MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024
BACKUP_KEY_ENV = "OFFSETX_BACKUP_KEY"
BUCKET_ENV = "OFFSETX_BACKUP_S3_BUCKET"
PREFIX_ENV = "OFFSETX_BACKUP_S3_PREFIX"
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_\-.]{0,200}$")


class HostedBackupError(ValueError):
    """An operator-actionable failure without credentials in its message."""


def _backup_key(value: str | None = None) -> bytes:
    encoded = value if value is not None else os.getenv(BACKUP_KEY_ENV, "")
    try:
        decoded = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise HostedBackupError(f"Set {BACKUP_KEY_ENV} to a separately saved 32-byte base64 key") from exc
    if len(decoded) != 32:
        raise HostedBackupError(f"{BACKUP_KEY_ENV} must contain exactly 32 random bytes")
    return decoded


def new_backup_key() -> str:
    """An independent, 256-bit backup key; do not store it in the database."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def _pg_environment(database_url: str) -> dict[str, str]:
    """Keep connection credentials out of pg_dump/pg_restore process arguments."""
    url = urlsplit(database_url)
    if url.scheme not in {"postgresql", "postgres"} or not url.hostname or not url.path.strip("/"):
        raise HostedBackupError("Set a complete PostgreSQL connection URL")
    allowed = {
        "sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY", "options": "PGOPTIONS", "connect_timeout": "PGCONNECT_TIMEOUT",
        "target_session_attrs": "PGTARGETSESSIONATTRS",
    }
    params = parse_qs(url.query, strict_parsing=True, keep_blank_values=True)
    if any(name not in allowed or len(values) != 1 for name, values in params.items()):
        raise HostedBackupError("The PostgreSQL URL has an unsupported or repeated connection option")
    env = dict(os.environ)
    env.update({
        "PGHOST": url.hostname,
        "PGDATABASE": unquote(url.path.lstrip("/")),
        "PGPORT": str(url.port or 5432),
        "PGUSER": unquote(url.username or ""),
        "PGPASSWORD": unquote(url.password or ""),
    })
    env.update({allowed[name]: values[0] for name, values in params.items()})
    return env


def _row_counts(connection) -> dict[str, int]:
    from psycopg import sql

    rows = connection.execute(
        "SELECT schemaname, tablename FROM pg_catalog.pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog', 'information_schema') "
        "AND schemaname NOT LIKE 'pg_toast%' ORDER BY schemaname, tablename"
    ).fetchall()
    counts = {}
    for schema, table in rows:
        key = json.dumps([schema, table], separators=(",", ":"))
        counts[key] = int(connection.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
        ).fetchone()[0])
    return counts


def _write_encrypted_snapshot(output: Path, database_url: str, key: bytes,
                              *, maximum_bytes: int) -> dict[str, int]:
    """Use pg_export_snapshot so the manifest counts match the exact pg_dump view."""
    if not shutil.which("pg_dump"):
        raise HostedBackupError("pg_dump is required; install the PostgreSQL client on the backup runner")
    import psycopg

    env = _pg_environment(database_url)
    proc = None
    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = str(conn.execute("SELECT pg_export_snapshot()").fetchone()[0])
            counts = _row_counts(conn)
            manifest = json.dumps({"version": 1, "counts": counts}, sort_keys=True).encode("utf-8")
            if len(manifest) > 1024 * 1024:
                raise HostedBackupError("The database table manifest is too large")
            nonce = secrets.token_bytes(NONCE_BYTES)
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            encryptor.authenticate_additional_data(MAGIC)
            with output.open("wb") as encrypted:
                encrypted.write(MAGIC + nonce)
                encrypted.write(encryptor.update(struct.pack(">I", len(manifest)) + manifest))
                proc = subprocess.Popen(
                    ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                     "--snapshot=" + snapshot],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
                )
                if proc.stdout is None:
                    raise HostedBackupError("pg_dump did not open its output")
                processed = 0
                for chunk in iter(lambda: proc.stdout.read(CHUNK_BYTES), b""):
                    processed += len(chunk)
                    if processed > maximum_bytes:
                        raise HostedBackupError("The export exceeds the configured backup size limit")
                    encrypted.write(encryptor.update(chunk))
                if proc.wait() != 0:
                    raise HostedBackupError("PostgreSQL export failed; no backup was published")
                encrypted.write(encryptor.finalize())
                encrypted.write(encryptor.tag)
            conn.execute("ROLLBACK")
            return counts
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            proc.wait()


def _decrypt_snapshot(source: Path, output: Path, key: bytes) -> dict[str, int]:
    total = source.stat().st_size
    if total < len(MAGIC) + NONCE_BYTES + TAG_BYTES + 5 or total > MAX_BACKUP_BYTES + 1024 * 1024:
        raise HostedBackupError("The encrypted backup has an invalid size")
    with source.open("rb") as encrypted:
        header = encrypted.read(len(MAGIC) + NONCE_BYTES)
        if not header.startswith(MAGIC):
            raise HostedBackupError("Unknown encrypted backup version")
        encrypted.seek(total - TAG_BYTES)
        tag = encrypted.read(TAG_BYTES)
        encrypted.seek(len(MAGIC) + NONCE_BYTES)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(header[len(MAGIC):], tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        remaining = total - len(MAGIC) - NONCE_BYTES - TAG_BYTES
        with output.open("wb") as plain:
            while remaining:
                chunk = encrypted.read(min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise HostedBackupError("The encrypted backup is incomplete")
                remaining -= len(chunk)
                plain.write(decryptor.update(chunk))
            try:
                plain.write(decryptor.finalize())
            except InvalidTag as exc:
                raise HostedBackupError("Backup authentication failed: wrong key or altered bytes") from exc

    with output.open("rb") as plain:
        length_bytes = plain.read(4)
        if len(length_bytes) != 4:
            raise HostedBackupError("The backup manifest is missing")
        length = struct.unpack(">I", length_bytes)[0]
        if not (0 < length <= 1024 * 1024):
            raise HostedBackupError("The backup manifest is invalid")
        try:
            manifest = json.loads(plain.read(length))
        except (ValueError, UnicodeError) as exc:
            raise HostedBackupError("The backup manifest cannot be read") from exc
        if manifest.get("version") != 1 or not isinstance(manifest.get("counts"), dict):
            raise HostedBackupError("The backup manifest has an unsupported version")
        if any(not isinstance(k, str) or type(v) is not int or v < 0
               for k, v in manifest["counts"].items()):
            raise HostedBackupError("The backup row counts are invalid")
        return manifest["counts"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise HostedBackupError("S3 support requires the existing 'email' dependency extra") from exc
    return boto3.client("s3")


def _bucket(value: str | None) -> str:
    bucket = str(value if value is not None else os.getenv(BUCKET_ENV, "")).strip()
    if not bucket or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
        raise HostedBackupError(f"Set {BUCKET_ENV} to a private bucket name")
    return bucket


def _object_key(value: str) -> str:
    if not _KEY_RE.fullmatch(value) or ".." in value.split("/") or value.startswith("/"):
        raise HostedBackupError("Invalid backup object key")
    return value


def _new_temp_path() -> Path:
    fd, name = tempfile.mkstemp(prefix="offcrm-hosted-backup-", suffix=".tmp")
    os.close(fd)
    return Path(name)


def export_to_s3(database_url: str, *, bucket: str | None = None, prefix: str | None = None,
                 key: bytes | None = None, client=None,
                 maximum_bytes: int = MAX_BACKUP_BYTES) -> dict[str, object]:
    """Publish only authenticated ciphertext, never a partially written backup."""
    if not (0 < maximum_bytes <= MAX_BACKUP_BYTES):
        raise HostedBackupError("Invalid backup size limit")
    destination = _bucket(bucket)
    scope = str(prefix if prefix is not None else os.getenv(PREFIX_ENV, "offcrm")).strip("/")
    if not scope or not _KEY_RE.fullmatch(scope):
        raise HostedBackupError("Invalid backup prefix")
    stamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%Y%m%dT%H%M%SZ")
    object_key = _object_key(f"{scope}/{stamp}-{uuid.uuid4().hex}.offcrm.enc")
    secret = key or _backup_key()
    temporary = _new_temp_path()
    try:
        counts = _write_encrypted_snapshot(
            temporary, database_url, secret, maximum_bytes=maximum_bytes
        )
        digest = _sha256(temporary)
        remote = client or _s3_client()
        remote.upload_file(str(temporary), destination, object_key, ExtraArgs={
            "Metadata": {"sha256": digest, "format": "offcrm-pgbackup-v1"},
        })
        head = remote.head_object(Bucket=destination, Key=object_key)
        if (head.get("Metadata", {}).get("sha256") != digest
                or int(head.get("ContentLength", -1)) != temporary.stat().st_size):
            raise HostedBackupError("Remote backup verification failed; do not rely on this export")
        return {"bucket": destination, "key": object_key, "sha256": digest,
                "encrypted_bytes": temporary.stat().st_size, "tables": len(counts)}
    finally:
        temporary.unlink(missing_ok=True)


def download_ciphertext(object_key: str, destination: Path, *, bucket: str | None = None,
                        client=None) -> Path:
    """Owner downloads ciphertext; refuses overwrite and unsafe output links."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise HostedBackupError("Download destination already exists; choose a new private path")
    remote = client or _s3_client()
    origin = _bucket(bucket)
    object_key = _object_key(object_key)
    head = remote.head_object(Bucket=origin, Key=object_key)
    digest = head.get("Metadata", {}).get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise HostedBackupError("The remote object lacks a valid checksum")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        remote.download_file(origin, object_key, str(destination))
        if destination.stat().st_size != int(head["ContentLength"]) or _sha256(destination) != digest:
            raise HostedBackupError("Downloaded backup failed checksum verification")
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def restore_to_empty_postgres(ciphertext: Path, destination_url: str, *,
                              key: bytes | None = None) -> dict[str, int]:
    """Restore only into a newly empty database; never touch a live install."""
    if not shutil.which("pg_restore"):
        raise HostedBackupError("pg_restore is required on the recovery runner")
    import psycopg

    with psycopg.connect(destination_url) as conn:
        existing = _row_counts(conn)
        if existing:
            raise HostedBackupError("Restore refused: the destination already has application tables")
    plain = _new_temp_path()
    try:
        expected = _decrypt_snapshot(Path(ciphertext), plain, key or _backup_key())
        with plain.open("rb") as snapshot:
            length = struct.unpack(">I", snapshot.read(4))[0]
            snapshot.seek(4 + length)
            proc = subprocess.Popen(
                ["pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
                 "--clean", "--if-exists", "--single-transaction",
                 "--dbname=" + unquote(urlsplit(destination_url).path.lstrip("/"))],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=_pg_environment(destination_url),
            )
            try:
                if proc.stdin is None:
                    raise HostedBackupError("pg_restore could not read the verified backup")
                for chunk in iter(lambda: snapshot.read(CHUNK_BYTES), b""):
                    proc.stdin.write(chunk)
                proc.stdin.close()
                if proc.wait() != 0:
                    raise HostedBackupError("Restore failed; discard the test database before retrying")
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()

        with psycopg.connect(destination_url) as conn:
            actual = _row_counts(conn)
        if actual != expected:
            raise HostedBackupError("Restored table counts differ; do not use this database")
        return actual
    finally:
        plain.unlink(missing_ok=True)
