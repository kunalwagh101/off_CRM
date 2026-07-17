from __future__ import annotations

import base64
import io
import json
import os
import secrets
import shutil
import sqlite3
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .models import to_utc_iso


MAGIC = b"OFFSETXBACKUP1\n"
ITERATIONS = 600_000
BACKUP_FILES = (
    "provider_profiles.json",
    "provider_secrets.enc",
    ".provider_master.key",
    "automation.json",
)


def _key(passphrase: str, salt: bytes) -> bytes:
    derived = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    ).derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def _sqlite_copy(source_path: Path, destination_path: Path) -> None:
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
        raise ValueError("Backup database failed SQLite integrity check")


def create_encrypted_backup(
    *,
    database_path: Path | str,
    data_dir: Path | str,
    passphrase: str,
) -> bytes:
    if len(passphrase) < 12:
        raise ValueError("Backup passphrase must be at least 12 characters")
    database = Path(database_path)
    data = Path(data_dir)
    if not database.exists():
        raise ValueError("CRM database does not exist")
    with TemporaryDirectory(prefix="offsetx-backup-") as temporary_dir:
        database_copy = Path(temporary_dir) / "outreach.db"
        _sqlite_copy(database, database_copy)
        _integrity(database_copy)
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "created_at": to_utc_iso(),
                        "database": "outreach.db",
                        "included_local_settings": [
                            name for name in BACKUP_FILES if (data / name).is_file()
                        ],
                        "excluded": ["Gmail OAuth tokens", "local mail inbox/outbox"],
                    },
                    indent=2,
                ),
            )
            archive.write(database_copy, "outreach.db")
            for name in BACKUP_FILES:
                source = data / name
                if source.is_file():
                    archive.write(source, f"settings/{name}")
        salt = secrets.token_bytes(16)
        encrypted = Fernet(_key(passphrase, salt)).encrypt(archive_buffer.getvalue())
        return MAGIC + salt + encrypted


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Backup contains an unsafe file path")
        if member.file_size > 250 * 1024 * 1024:
            raise ValueError("Backup member is too large")
    if "outreach.db" not in {member.filename for member in members}:
        raise ValueError("Backup does not contain the CRM database")
    return members


def restore_encrypted_backup(
    content: bytes,
    *,
    database_path: Path | str,
    data_dir: Path | str,
    passphrase: str,
) -> dict[str, Any]:
    if not content.startswith(MAGIC) or len(content) <= len(MAGIC) + 16:
        raise ValueError("Not a valid OffsetX encrypted backup")
    salt_offset = len(MAGIC)
    salt = content[salt_offset : salt_offset + 16]
    token = content[salt_offset + 16 :]
    try:
        decrypted = Fernet(_key(passphrase, salt)).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Backup passphrase is incorrect or the backup is damaged") from exc

    database = Path(database_path)
    data = Path(data_dir)
    restored_settings: list[str] = []
    safety_directory = data / "restore_safety" / uuid.uuid4().hex
    with TemporaryDirectory(prefix="offsetx-restore-") as temporary_dir:
        temporary = Path(temporary_dir)
        try:
            archive = zipfile.ZipFile(io.BytesIO(decrypted), "r")
        except zipfile.BadZipFile as exc:
            raise ValueError("Backup archive is damaged") from exc
        with archive:
            _safe_members(archive)
            archive.extract("outreach.db", temporary)
            restored_database = temporary / "outreach.db"
            _integrity(restored_database)
            database.parent.mkdir(parents=True, exist_ok=True)
            names = {member.filename for member in archive.infolist()}
            database_existed = database.exists()
            settings_existed = {name: (data / name).is_file() for name in BACKUP_FILES}
            safety_directory.mkdir(parents=True, exist_ok=False)
            if database_existed:
                shutil.copy2(database, safety_directory / "outreach.db")
            for name in BACKUP_FILES:
                current = data / name
                if current.is_file():
                    shutil.copy2(current, safety_directory / name)
            try:
                replacement = database.with_suffix(database.suffix + ".restore")
                shutil.copy2(restored_database, replacement)
                os.replace(replacement, database)
                for name in BACKUP_FILES:
                    archive_name = f"settings/{name}"
                    if archive_name not in names:
                        continue
                    data.mkdir(parents=True, exist_ok=True)
                    destination = data / name
                    replacement = destination.with_name(destination.name + ".restore")
                    replacement.write_bytes(archive.read(archive_name))
                    os.replace(replacement, destination)
                    if name in {".provider_master.key", "provider_secrets.enc"}:
                        try:
                            destination.chmod(0o600)
                        except OSError:
                            pass
                    restored_settings.append(name)
            except Exception:
                saved_database = safety_directory / "outreach.db"
                if saved_database.exists():
                    shutil.copy2(saved_database, database)
                elif not database_existed:
                    database.unlink(missing_ok=True)
                for name in BACKUP_FILES:
                    saved = safety_directory / name
                    if saved.exists():
                        shutil.copy2(saved, data / name)
                    elif not settings_existed[name]:
                        (data / name).unlink(missing_ok=True)
                raise
    return {
        "restored": True,
        "database": str(database),
        "settings": restored_settings,
        "safety_copy": str(safety_directory),
    }
