from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import shutil
import sqlite3
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .models import to_utc_iso


# Keep the original envelope magic so existing encrypted backups remain
# recoverable. The manifest schema version identifies the payload format.
MAGIC = b"OFFSETXBACKUP1\n"
ITERATIONS = 600_000
DEFAULT_MAX_BACKUP_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
SQLITE_HEADER = b"SQLite format 3\x00"

# Schema-v1 compatibility only. Schema v2 inventories the workspace instead of
# relying on this list, which is how new durable stores were silently omitted.
LEGACY_BACKUP_FILES = (
    "provider_profiles.json",
    "provider_secrets.enc",
    ".provider_master.key",
    "automation.json",
)

# These are reconstructible accelerators or old restore scratch space. They are
# named in the manifest so exclusion is explicit rather than accidental.
REBUILDABLE_FILES = frozenset({"ai_cache.db"})
REBUILDABLE_PREFIXES = ("restore_safety/",)
SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _key(passphrase: str, salt: bytes) -> bytes:
    derived = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    ).derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_copy(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _integrity(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if not result or str(result[0]).lower() != "ok":
        raise ValueError(f"Backup database failed SQLite integrity check: {path.name}")


def _looks_like_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER
    except OSError:
        return False


def _excluded_relative(relative: str) -> bool:
    normalized = relative.replace("\\", "/").lstrip("./")
    if normalized in REBUILDABLE_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in REBUILDABLE_PREFIXES)


def _workspace_files(data: Path, database: Path) -> list[tuple[Path, str]]:
    if not data.exists():
        return []
    database_resolved = database.resolve()
    found: list[tuple[Path, str]] = []
    for source in sorted(path for path in data.rglob("*") if path.is_file()):
        try:
            if source.resolve() == database_resolved:
                continue
        except OSError:
            pass
        relative = source.relative_to(data).as_posix()
        if _excluded_relative(relative):
            continue
        if source.name.endswith(SQLITE_SIDECAR_SUFFIXES):
            continue
        found.append((source, relative))
    return found


def _archive_source(
    archive: zipfile.ZipFile,
    *,
    source: Path,
    archive_name: str,
    temporary: Path,
) -> dict[str, Any]:
    staged = source
    kind = "file"
    if _looks_like_sqlite(source):
        kind = "sqlite"
        staged = temporary / (hashlib.sha256(archive_name.encode("utf-8")).hexdigest() + ".db")
        _sqlite_copy(source, staged)
        _integrity(staged)
    archive.write(staged, archive_name)
    return {
        "path": archive_name,
        "kind": kind,
        "size": staged.stat().st_size,
        "sha256": _sha256_file(staged),
    }


def create_encrypted_backup(
    *,
    database_path: Path | str,
    data_dir: Path | str,
    passphrase: str,
    max_bytes: int = DEFAULT_MAX_BACKUP_BYTES,
) -> bytes:
    """Create one encrypted, versioned recovery image of all durable local state.

    Every file beneath ``data_dir`` is included by default. The only exclusions
    are explicitly rebuildable cache/scratch paths above. SQLite files are copied
    through SQLite's backup API so an active WAL database is captured
    consistently rather than copied byte-for-byte while it is changing.
    """
    if len(passphrase) < 12:
        raise ValueError("Backup passphrase must be at least 12 characters")
    if max_bytes < 1024 * 1024:
        raise ValueError("Backup maximum must be at least 1 MiB")
    database = Path(database_path).resolve()
    data = Path(data_dir).resolve()
    if not database.exists():
        raise ValueError("CRM database does not exist")

    try:
        database_relative = database.relative_to(data).as_posix()
    except ValueError:
        database_relative = ""

    with TemporaryDirectory(prefix="offsetx-backup-") as temporary_dir:
        temporary = Path(temporary_dir)
        archive_buffer = io.BytesIO()
        entries: list[dict[str, Any]] = []
        with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            entries.append(
                _archive_source(
                    archive,
                    source=database,
                    archive_name="database/outreach.db",
                    temporary=temporary,
                )
            )
            for source, relative in _workspace_files(data, database):
                entries.append(
                    _archive_source(
                        archive,
                        source=source,
                        archive_name=f"data/{relative}",
                        temporary=temporary,
                    )
                )
            manifest = {
                "schema_version": 2,
                "created_at": to_utc_iso(),
                "database": "database/outreach.db",
                "database_relative_to_data": database_relative,
                "entries": entries,
                "excluded_rebuildable": sorted(REBUILDABLE_FILES),
                "excluded_prefixes": list(REBUILDABLE_PREFIXES),
            }
            manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
            archive.writestr("manifest.json", manifest_bytes)

        salt = secrets.token_bytes(16)
        encrypted = MAGIC + salt + Fernet(_key(passphrase, salt)).encrypt(archive_buffer.getvalue())
        if len(encrypted) > max_bytes:
            raise ValueError(
                f"Backup is {len(encrypted)} bytes, above the configured {max_bytes}-byte backup limit"
            )
        return encrypted


def _decrypt(content: bytes, passphrase: str, *, max_bytes: int) -> bytes:
    if len(content) > max_bytes:
        raise ValueError("Encrypted backup exceeds the configured backup limit")
    if not content.startswith(MAGIC) or len(content) <= len(MAGIC) + 16:
        raise ValueError("Not a valid off_CRM encrypted backup")
    salt_offset = len(MAGIC)
    salt = content[salt_offset : salt_offset + 16]
    token = content[salt_offset + 16 :]
    try:
        return Fernet(_key(passphrase, salt)).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Backup passphrase is incorrect or the backup is damaged") from exc


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    total = 0
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Backup contains an unsafe file path")
        mode = (member.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise ValueError("Backup may not contain symbolic links")
        if member.file_size > MAX_MEMBER_BYTES:
            raise ValueError("Backup member is too large")
        total += member.file_size
        if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("Backup expands beyond the permitted recovery size")
    return members


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    names = {member.filename for member in _safe_members(archive)}
    if "manifest.json" not in names:
        # Original v1 archives had a manifest in practice, but fail explicitly
        # rather than guessing when handed an unrelated zip.
        raise ValueError("Backup does not contain a manifest")
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Backup manifest is damaged") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Backup manifest is invalid")
    return manifest


def _verify_v2_archive(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> None:
    if int(manifest.get("schema_version") or 0) != 2:
        raise ValueError("Unsupported backup manifest version")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Backup manifest has no state entries")
    names = {member.filename for member in archive.infolist()}
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Backup manifest entry is invalid")
        name = str(entry.get("path") or "")
        if not name or name in declared or name not in names:
            raise ValueError("Backup manifest references a missing or duplicate state file")
        declared.add(name)
        content = archive.read(name)
        if len(content) != int(entry.get("size") or -1):
            raise ValueError(f"Backup size check failed for {name}")
        if _sha256_bytes(content) != str(entry.get("sha256") or ""):
            raise ValueError(f"Backup integrity hash failed for {name}")
    database_name = str(manifest.get("database") or "")
    if database_name not in declared:
        raise ValueError("Backup manifest does not contain the CRM database")


def validate_encrypted_backup(
    content: bytes,
    *,
    passphrase: str,
    max_bytes: int = DEFAULT_MAX_BACKUP_BYTES,
) -> dict[str, Any]:
    """Fully authenticate and validate a backup without touching live state."""
    decrypted = _decrypt(content, passphrase, max_bytes=max_bytes)
    try:
        archive = zipfile.ZipFile(io.BytesIO(decrypted), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Backup archive is damaged") from exc
    with archive:
        manifest = _read_manifest(archive)
        if int(manifest.get("schema_version") or 1) == 1:
            if "outreach.db" not in {member.filename for member in archive.infolist()}:
                raise ValueError("Legacy backup does not contain the CRM database")
            return manifest
        _verify_v2_archive(archive, manifest)
        # Prove every declared sqlite database opens and passes integrity before
        # maintenance begins. The files are temporary and never become live.
        with TemporaryDirectory(prefix="offsetx-backup-validate-") as temporary_dir:
            root = Path(temporary_dir)
            for entry in manifest["entries"]:
                if entry.get("kind") != "sqlite":
                    continue
                target = root / hashlib.sha256(str(entry["path"]).encode()).hexdigest()
                target.write_bytes(archive.read(str(entry["path"])))
                _integrity(target)
        return manifest


def _restore_legacy(
    archive: zipfile.ZipFile,
    *,
    database: Path,
    data: Path,
) -> dict[str, Any]:
    names = {member.filename for member in archive.infolist()}
    if "outreach.db" not in names:
        raise ValueError("Backup does not contain the CRM database")
    restored_settings: list[str] = []
    safety_directory = data.parent / f".{data.name}.legacy-restore-safety-{uuid.uuid4().hex}"
    safety_directory.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory(prefix="offsetx-restore-legacy-") as temporary_dir:
        temporary = Path(temporary_dir)
        (temporary / "outreach.db").write_bytes(archive.read("outreach.db"))
        _integrity(temporary / "outreach.db")
        database_existed = database.exists()
        settings_existed = {name: (data / name).is_file() for name in LEGACY_BACKUP_FILES}
        if database_existed:
            shutil.copy2(database, safety_directory / "outreach.db")
        for name in LEGACY_BACKUP_FILES:
            current = data / name
            if current.is_file():
                shutil.copy2(current, safety_directory / name)
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
            replacement = database.with_suffix(database.suffix + ".restore")
            shutil.copy2(temporary / "outreach.db", replacement)
            os.replace(replacement, database)
            for name in LEGACY_BACKUP_FILES:
                archive_name = f"settings/{name}"
                if archive_name not in names:
                    continue
                data.mkdir(parents=True, exist_ok=True)
                destination = data / name
                replacement = destination.with_name(destination.name + ".restore")
                replacement.write_bytes(archive.read(archive_name))
                os.replace(replacement, destination)
                restored_settings.append(name)
        except Exception:
            saved_database = safety_directory / "outreach.db"
            if saved_database.exists():
                shutil.copy2(saved_database, database)
            elif not database_existed:
                database.unlink(missing_ok=True)
            for name in LEGACY_BACKUP_FILES:
                saved = safety_directory / name
                if saved.exists():
                    shutil.copy2(saved, data / name)
                elif not settings_existed[name]:
                    (data / name).unlink(missing_ok=True)
            raise
    return {
        "restored": True,
        "schema_version": 1,
        "database": str(database),
        "settings": restored_settings,
        "safety_copy": str(safety_directory),
        "safety_database": "",
    }


def restore_encrypted_backup(
    content: bytes,
    *,
    database_path: Path | str,
    data_dir: Path | str,
    passphrase: str,
    max_bytes: int = DEFAULT_MAX_BACKUP_BYTES,
) -> dict[str, Any]:
    """Restore a validated workspace with a rollback copy outside live data.

    Callers should run :func:`validate_encrypted_backup` before entering
    maintenance. This function validates again because recovery must stay safe
    when used outside the web application too.
    """
    decrypted = _decrypt(content, passphrase, max_bytes=max_bytes)
    database = Path(database_path).resolve()
    data = Path(data_dir).resolve()
    try:
        archive = zipfile.ZipFile(io.BytesIO(decrypted), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Backup archive is damaged") from exc

    with archive:
        manifest = _read_manifest(archive)
        if int(manifest.get("schema_version") or 1) == 1:
            return _restore_legacy(archive, database=database, data=data)
        _verify_v2_archive(archive, manifest)

        replacement_data = data.parent / f".{data.name}.restore-{uuid.uuid4().hex}"
        safety_data = data.parent / f".{data.name}.restore-safety-{uuid.uuid4().hex}"
        safety_database = ""
        replacement_data.mkdir(parents=True, exist_ok=False)
        try:
            entries = {str(entry["path"]): entry for entry in manifest["entries"]}
            for name, entry in entries.items():
                if not name.startswith("data/"):
                    continue
                relative = PurePosixPath(name).relative_to("data")
                destination = replacement_data.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
                if entry.get("kind") == "sqlite":
                    _integrity(destination)

            restored_database = archive.read(str(manifest["database"]))
            database_relative = str(manifest.get("database_relative_to_data") or "")
            if database_relative:
                destination = replacement_data.joinpath(*PurePosixPath(database_relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(restored_database)
                _integrity(destination)
            else:
                with TemporaryDirectory(prefix="offsetx-db-restore-") as database_temp:
                    staged_database = Path(database_temp) / "outreach.db"
                    staged_database.write_bytes(restored_database)
                    _integrity(staged_database)
                    database.parent.mkdir(parents=True, exist_ok=True)
                    if database.exists():
                        safety_db_path = database.with_name(
                            f".{database.name}.restore-safety-{uuid.uuid4().hex}"
                        )
                        shutil.copy2(database, safety_db_path)
                        safety_database = str(safety_db_path)
                    replacement_db = database.with_name(database.name + ".restore")
                    shutil.copy2(staged_database, replacement_db)
                    os.replace(replacement_db, database)

            data.parent.mkdir(parents=True, exist_ok=True)
            if data.exists():
                os.replace(data, safety_data)
            os.replace(replacement_data, data)
        except Exception:
            if replacement_data.exists():
                shutil.rmtree(replacement_data, ignore_errors=True)
            if safety_data.exists() and not data.exists():
                os.replace(safety_data, data)
            if safety_database:
                saved = Path(safety_database)
                if saved.exists():
                    shutil.copy2(saved, database)
            raise

    return {
        "restored": True,
        "schema_version": 2,
        "database": str(database),
        "entries": len(manifest["entries"]),
        "safety_copy": str(safety_data) if safety_data.exists() else "",
        "safety_database": safety_database,
        "excluded_rebuildable": manifest.get("excluded_rebuildable", []),
    }


def rollback_restored_backup(
    result: dict[str, Any], *, database_path: Path | str, data_dir: Path | str
) -> None:
    """Put the pre-restore workspace back after a failed service health check."""
    data = Path(data_dir).resolve()
    database = Path(database_path).resolve()
    safety_copy = Path(str(result.get("safety_copy") or "")) if result.get("safety_copy") else None
    safety_database = (
        Path(str(result.get("safety_database") or "")) if result.get("safety_database") else None
    )
    failed = data.parent / f".{data.name}.failed-restore-{uuid.uuid4().hex}"
    if safety_copy and safety_copy.exists():
        if data.exists():
            os.replace(data, failed)
        os.replace(safety_copy, data)
        shutil.rmtree(failed, ignore_errors=True)
    if safety_database and safety_database.exists():
        shutil.copy2(safety_database, database)


def discard_restore_safety(result: dict[str, Any]) -> None:
    """Delete the pre-restore copy only after the caller's health checks pass."""
    value = str(result.get("safety_copy") or "")
    if value:
        path = Path(value)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
    value = str(result.get("safety_database") or "")
    if value:
        Path(value).unlink(missing_ok=True)
