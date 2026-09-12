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
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .models import to_utc_iso


# Keep the original envelope magic so existing encrypted backups remain
# recoverable. The manifest schema version identifies the payload format.
MAGIC = b"OFFSETXBACKUP1\n"
ITERATIONS = 600_000
DEFAULT_MAX_BACKUP_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
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
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Backup database is damaged: {path.name}") from exc
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
    for source in sorted(data.rglob("*")):
        if source.is_symlink():
            raise ValueError("Backup cannot include symbolic links; move durable files into the workspace")
        if source.is_dir():
            continue
        if not source.is_file():
            raise ValueError("Backup can include only regular workspace files")
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
    if source.suffix in (".db", ".sqlite", ".sqlite3") and not _looks_like_sqlite(source):
        raise ValueError(f"Backup database is damaged: {source.name}")
    if _looks_like_sqlite(source):
        kind = "sqlite"
        staged = temporary / (hashlib.sha256(archive_name.encode("utf-8")).hexdigest() + ".db")
        _sqlite_copy(source, staged)
        _integrity(staged)
    if staged.stat().st_size > MAX_MEMBER_BYTES:
        raise ValueError("Backup member is too large")
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
    _integrity(database)

    try:
        database_relative = database.relative_to(data).as_posix()
    except ValueError:
        database_relative = ""

    with TemporaryDirectory(prefix="offsetx-backup-") as temporary_dir:
        temporary = Path(temporary_dir)
        archive_buffer = TemporaryFile()
        # Fernet base64/envelope expansion is predictable; refuse while ZIP is
        # being written, before allocating encryption buffers.
        archive_limit = ((max_bytes - len(MAGIC) - 16) // 4) * 3 - 73
        bounded = _BoundedArchive(archive_buffer, archive_limit)
        entries: list[dict[str, Any]] = []
        with zipfile.ZipFile(bounded, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            entries.append(
                _archive_source(
                    archive,
                    source=database,
                    archive_name="database/outreach.db",
                    temporary=temporary,
                )
            )
            sources = _workspace_files(data, database)
            if len(sources) + 2 > MAX_MEMBERS:
                raise ValueError("Backup has too many files")
            if database.stat().st_size + sum(path.stat().st_size for path, _ in sources) > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError("Backup expands beyond the permitted recovery size")
            for source, relative in sources:
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
                "source_data_dir": str(data),
                "entries": entries,
                "excluded_rebuildable": sorted(REBUILDABLE_FILES),
                "excluded_prefixes": list(REBUILDABLE_PREFIXES),
            }
            manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("Backup manifest is too large")
            archive.writestr("manifest.json", manifest_bytes)

        salt = secrets.token_bytes(16)
        archive_buffer.seek(0)
        try:
            encrypted = MAGIC + salt + Fernet(_key(passphrase, salt)).encrypt(archive_buffer.read(archive_limit + 1))
        finally:
            archive_buffer.close()
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


class _BoundedArchive:
    def __init__(self, file, limit):
        self.file, self.limit = file, limit

    def write(self, content):
        if self.file.tell() + len(content) > self.limit:
            raise ValueError("Backup exceeds the configured backup limit")
        return self.file.write(content)

    def __getattr__(self, name):
        return getattr(self.file, name)


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (not value or len(value) > 1024 or path.is_absolute() or ".." in path.parts
            or "\\" in value or ":" in value or "\x00" in value
            or path.as_posix() != value or value == "."):
        raise ValueError("Backup contains an unsafe file path")
    return path


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_MEMBERS:
        raise ValueError("Backup has too many files")
    total, seen = 0, set()
    for member in members:
        _safe_relative(member.filename)
        if member.filename in seen:
            raise ValueError("Backup contains duplicate file paths")
        seen.add(member.filename)
        mode = (member.external_attr >> 16) & 0o170000
        if mode not in (0, stat.S_IFREG) or member.is_dir():
            raise ValueError("Backup may contain only regular files, never symbolic links")
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
    if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
        raise ValueError("Backup manifest is too large")
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Backup manifest is damaged") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Backup manifest is invalid")
    return manifest


def _verify_v2_archive(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 2:
        raise ValueError("Unsupported backup manifest version")
    relative = manifest.get("database_relative_to_data", "")
    if not isinstance(relative, str):
        raise ValueError("Backup database location is invalid")
    if relative:
        _safe_relative(relative)
    if manifest.get("database") != "database/outreach.db":
        raise ValueError("Backup CRM database location is invalid")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Backup manifest has no state entries")
    names = {member.filename for member in _safe_members(archive)}
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Backup manifest entry is invalid")
        name = entry.get("path", "")
        if not isinstance(name, str):
            raise ValueError("Backup manifest path is invalid")
        _safe_relative(name)
        if (name in declared or name not in names
                or not (name == "database/outreach.db" or name.startswith("data/"))):
            raise ValueError("Backup manifest references a missing, duplicate or invalid state file")
        if entry.get("kind") not in ("file", "sqlite"):
            raise ValueError("Backup manifest file kind is invalid")
        if name == "database/outreach.db" and entry["kind"] != "sqlite":
            raise ValueError("CRM backup must be a SQLite database")
        if name.endswith(SQLITE_SIDECAR_SUFFIXES):
            raise ValueError("Backup contains a live SQLite sidecar")
        if name.startswith("data/") and relative and name == "data/" + relative:
            raise ValueError("Backup declares the CRM database twice")
        if any(name.startswith(other + "/") or other.startswith(name + "/") for other in declared):
            raise ValueError("Backup contains conflicting file paths")
        declared.add(name)
        if type(entry.get("size")) is not int or entry["size"] != archive.getinfo(name).file_size:
            raise ValueError(f"Backup size check failed for {name}")
        digest = hashlib.sha256()
        with archive.open(name) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != entry.get("sha256"):
            raise ValueError(f"Backup integrity hash failed for {name}")
    if "database/outreach.db" not in declared or names != declared | {"manifest.json"}:
        raise ValueError("Backup contains undeclared state or lacks its CRM database")


def _validate_encrypted_backup(
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
        version = manifest.get("schema_version", 1)
        if type(version) is not int or version not in (1, 2):
            raise ValueError("Unsupported backup manifest version")
        if version == 1:
            if "outreach.db" not in {member.filename for member in archive.infolist()}:
                raise ValueError("Legacy backup does not contain the CRM database")
            allowed = {"outreach.db", "manifest.json"} | {f"settings/{name}" for name in LEGACY_BACKUP_FILES}
            if set(archive.namelist()) - allowed:
                raise ValueError("Legacy backup contains unsupported files")
            with TemporaryDirectory(prefix="offcrm-legacy-validate-") as temporary_dir:
                database = Path(temporary_dir) / "outreach.db"
                database.write_bytes(archive.read("outreach.db"))
                _integrity(database)
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


def validate_encrypted_backup(content: bytes, *, passphrase: str, max_bytes: int = DEFAULT_MAX_BACKUP_BYTES) -> dict[str, Any]:
    try:
        return _validate_encrypted_backup(content, passphrase=passphrase, max_bytes=max_bytes)
    except (zipfile.BadZipFile, EOFError, RuntimeError, TypeError) as exc:
        raise ValueError("Backup archive or manifest is damaged; use another recovery copy") from exc


def _rebase_asset_paths(staged: Path, old_root: str, destination: Path) -> None:
    """Relocate only known asset columns; never rewrite user text or prompts."""
    if not old_root:
        return
    old = Path(old_root)
    if not old.is_absolute():
        raise ValueError("Backup source root must be absolute")
    for name, tables in (("imagery.db", ("image_assets",)), ("video.db", ("video_media", "video_renders"))):
        database = staged / name
        if not database.exists():
            continue
        with sqlite3.connect(database) as connection:
            existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in tables:
                if table not in existing:
                    continue
                for identifier, value in connection.execute(f"SELECT id, path FROM {table}").fetchall():
                    if not value:
                        continue
                    try:
                        relative = Path(value).relative_to(old)
                    except ValueError as exc:
                        raise ValueError("Backup refers to an asset outside its workspace") from exc
                    _safe_relative(relative.as_posix())
                    if not (staged / relative).is_file():
                        raise ValueError("Backup is missing a referenced asset")
                    connection.execute(f"UPDATE {table} SET path=? WHERE id=?", (str(destination / relative), identifier))


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree(path: Path) -> None:
    for child in path.rglob("*"):
        if child.is_file():
            child.chmod(0o600)
            with child.open("rb") as handle:
                os.fsync(handle.fileno())
        elif child.is_dir():
            child.chmod(0o700)
            _fsync_directory(child)
    _fsync_directory(path)


def _journal_path(data: Path) -> Path:
    return data.parent / f".{data.name}.restore-journal.json"


def _write_journal(path: Path, journal: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(journal, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _read_journal(data: Path, database: Path) -> dict[str, Any] | None:
    path = _journal_path(data)
    if not path.exists():
        return None
    journal = json.loads(path.read_text())
    root = Path(journal["root"])
    allowed = {str(data), str(database)}
    if (root.parent != data.parent or not root.name.startswith(f".{data.name}.recovery-")
            or journal.get("state") not in ("pending", "committed")
            or not isinstance(journal.get("targets"), list)):
        raise ValueError("Recovery journal is invalid; retain the workspace and inspect the recovery log")
    for target in journal["targets"]:
        if (target["live"] not in allowed or Path(target["saved"]).parent != root
                or Path(target["staged"]).parent != root):
            raise ValueError("Recovery journal contains an invalid destination")
    return journal


def recover_interrupted_restore(*, database_path: Path | str, data_dir: Path | str) -> bool:
    """Run before opening any store. An uncommitted swap always rolls back.

    The journal and both generations live on the same persistent filesystem.
    Each rename and the commit decision are synced before proceeding, including
    the gap between moving the old directory and installing the new one.
    """
    data, database = Path(data_dir).resolve(), Path(database_path).resolve()
    journal = _read_journal(data, database)
    if journal is None:
        return False
    if journal["state"] == "pending":
        for target in reversed(journal["targets"]):
            live, saved = Path(target["live"]), Path(target["saved"])
            if saved.exists():
                if live.exists():
                    _remove_path(live)
                os.replace(saved, live)
                _fsync_directory(live.parent)
            elif not target["existed"] and live.exists():
                _remove_path(live)
                _fsync_directory(live.parent)
    _remove_path(Path(journal["root"]))
    _journal_path(data).unlink()
    _fsync_directory(data.parent)
    return True


def restore_encrypted_backup(
    content: bytes, *, database_path: Path | str, data_dir: Path | str,
    passphrase: str, max_bytes: int = DEFAULT_MAX_BACKUP_BYTES,
) -> dict[str, Any]:
    """Install an authenticated staged workspace; caller commits after health.

    All writers must be drained by the caller. Call discard_restore_safety only
    after reopening and checking services, or rollback_restored_backup on error.
    The next application startup rolls back a swap that never reached commit.
    """
    manifest = validate_encrypted_backup(content, passphrase=passphrase, max_bytes=max_bytes)
    data, database = Path(data_dir).resolve(), Path(database_path).resolve()
    if _journal_path(data).exists():
        raise ValueError("An unfinished restore exists; restart to recover it before trying again")
    data.parent.mkdir(parents=True, exist_ok=True)
    root = data.parent / f".{data.name}.recovery-{uuid.uuid4().hex}"
    root.mkdir(mode=0o700)
    staged, previous = root / "workspace", root / "previous"
    targets = []
    try:
        legacy = manifest.get("schema_version", 1) == 1
        if legacy and data.exists():
            _workspace_files(data, database)  # refuses links/special files
            shutil.copytree(data, staged)
        else:
            staged.mkdir(mode=0o700)
        with zipfile.ZipFile(io.BytesIO(_decrypt(content, passphrase, max_bytes=max_bytes))) as archive:
            if legacy:
                entries = [(f"settings/{name}", name, "file") for name in LEGACY_BACKUP_FILES if f"settings/{name}" in archive.namelist()]
                database_name = "outreach.db"
            else:
                entries = [(entry["path"], entry["path"][5:], entry["kind"]) for entry in manifest["entries"] if entry["path"].startswith("data/")]
                database_name = "database/outreach.db"
            for name, relative, kind in entries:
                destination = staged.joinpath(*_safe_relative(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                if kind == "sqlite":
                    _integrity(destination)
            try:
                database_relative = database.relative_to(data)
                staged_database = staged / database_relative
            except ValueError:
                staged_database = root / "database"
                targets.append({"live": str(database), "staged": str(staged_database), "saved": str(root / "previous-database"), "existed": database.exists()})
            staged_database.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(database_name) as source, staged_database.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            for suffix in SQLITE_SIDECAR_SUFFIXES:
                Path(str(staged_database) + suffix).unlink(missing_ok=True)
            _integrity(staged_database)
        _rebase_asset_paths(staged, manifest.get("source_data_dir", ""), data)
        _fsync_tree(root)
        targets.append({"live": str(data), "staged": str(staged), "saved": str(previous), "existed": data.exists()})
        journal = {"state": "pending", "root": str(root), "targets": targets}
        _write_journal(_journal_path(data), journal)
        for target in targets:
            live, saved = Path(target["live"]), Path(target["saved"])
            live.parent.mkdir(parents=True, exist_ok=True)
            if target["existed"]:
                os.replace(live, saved)
                _fsync_directory(live.parent)
                _fsync_directory(root)
            os.replace(target["staged"], live)
            _fsync_directory(live.parent)
            _fsync_directory(root)
        # Preserve the old public safety-copy layout for external CRM databases.
        if len(targets) > 1 and (root / "previous-database").exists():
            previous.mkdir(exist_ok=True)
            if not (previous / "outreach.db").exists():
                shutil.copy2(root / "previous-database", previous / "outreach.db")
        return {"restored": True, "schema_version": 1 if legacy else 2,
                "database": str(database), "data_dir": str(data),
                "entries": len(entries) + 1, "safety_copy": str(previous),
                "excluded_rebuildable": manifest.get("excluded_rebuildable", []),
                "legacy_partial": legacy}
    except BaseException:
        if _journal_path(data).exists():
            recover_interrupted_restore(database_path=database, data_dir=data)
        else:
            shutil.rmtree(root, ignore_errors=True)
        raise


def rollback_restored_backup(result: dict[str, Any], *, database_path: Path | str, data_dir: Path | str) -> None:
    recover_interrupted_restore(database_path=database_path, data_dir=data_dir)


def discard_restore_safety(result: dict[str, Any]) -> None:
    data, database = Path(result["data_dir"]), Path(result["database"])
    journal = _read_journal(data, database)
    if journal is not None:
        journal["state"] = "committed"
        _write_journal(_journal_path(data), journal)
        # A cleanup failure leaves a committed journal: startup preserves the
        # restored generation and retries cleanup, never rolls back good data.
        try:
            recover_interrupted_restore(database_path=database, data_dir=data)
        except OSError:
            import logging
            logging.getLogger(__name__).exception("Committed restore cleanup needs retry at startup")
