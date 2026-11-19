"""Encrypted browser-session vault. Trusted host code only; never a model tool.

S-03.02.02 keeps browser session material outside prompts and protects each
connected account with its own random data-encryption key. The account key is
wrapped by a master key sourced from the operating-system credential store; when
that store is unavailable, an explicitly supplied passphrase derives the master
key with scrypt. No raw master or account key is written beside the data.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ..workspaces import workspace_id as checked_workspace, workspace_lock, private_read

VAULT_VERSION = 2
KEYCHAIN_SERVICE = "off_CRM browser vault"
KEYCHAIN_ACCOUNT = "master"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_COOKIE_FIELDS = (
    "name", "value", "domain", "path", "secure", "httpOnly", "sameSite",
    "expires", "priority", "sameParty", "sourceScheme", "sourcePort", "partitionKey",
)


class VaultError(RuntimeError):
    """The vault refused an operation rather than weakening its guarantees."""


class VaultLocked(VaultError):
    """No usable master-key source was available, or decryption failed."""


@dataclass(frozen=True)
class VaultMetadata:
    workspace_id: str
    platform_id: str
    key_id: str
    key_source: str
    cookie_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "platform_id": self.platform_id,
            "key_id": self.key_id,
            "key_source": self.key_source,
            "cookie_count": self.cookie_count,
        }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        temporary = Path(handle.name)
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _workspace_identity(value: str) -> str:
    try:
        return checked_workspace(value)
    except ValueError as exc:
        raise VaultError(f'Invalid workspace id. {exc}') from exc


def _checked(value: str, label: str) -> str:
    cleaned = str(value or "").strip().lower()
    if not _IDENTIFIER.fullmatch(cleaned):
        raise VaultError(
            f"{label} must start with a letter or digit and contain only letters, "
            "digits, dot, dash or underscore."
        )
    return cleaned


def _decode_root(encoded: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None
    return raw if len(raw) == 32 else None


def _encode_root(raw: bytes) -> str:
    if len(raw) != 32:
        raise VaultError("Vault master material must be exactly 32 bytes.")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _command(args: list[str], *, input_text: str = "") -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            input=input_text or None,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _macos_keychain(create: bool) -> tuple[bytes | None, str]:
    security = shutil.which("security")
    if not security:
        return None, ""
    found = _command([
        security, "find-generic-password", "-a", KEYCHAIN_ACCOUNT,
        "-s", KEYCHAIN_SERVICE, "-w",
    ])
    if found and found.returncode == 0:
        raw = _decode_root(found.stdout.strip())
        if raw:
            return raw, "macos-keychain"
    if not create:
        return None, ""
    raw = secrets.token_bytes(32)
    # Apple's `security` CLI has no stdin form for -w. The value is handed only
    # to the local Keychain process and is never written to off_CRM storage.
    stored = _command([
        security, "add-generic-password", "-U", "-a", KEYCHAIN_ACCOUNT,
        "-s", KEYCHAIN_SERVICE, "-w", _encode_root(raw),
    ])
    if stored and stored.returncode == 0:
        return raw, "macos-keychain"
    return None, ""


def _linux_keychain(create: bool) -> tuple[bytes | None, str]:
    secret_tool = shutil.which("secret-tool")
    if not secret_tool:
        return None, ""
    found = _command([
        secret_tool, "lookup", "service", "offcrm-browser-vault",
        "account", KEYCHAIN_ACCOUNT,
    ])
    if found and found.returncode == 0:
        raw = _decode_root(found.stdout.strip())
        if raw:
            return raw, "linux-secret-service"
    if not create:
        return None, ""
    raw = secrets.token_bytes(32)
    stored = _command([
        secret_tool, "store", "--label", KEYCHAIN_SERVICE,
        "service", "offcrm-browser-vault", "account", KEYCHAIN_ACCOUNT,
    ], input_text=_encode_root(raw) + "\n")
    if stored and stored.returncode == 0:
        return raw, "linux-secret-service"
    return None, ""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _windows_dpapi_dir() -> Path | None:
    base = os.environ.get("LOCALAPPDATA", "").strip()
    return Path(base) / "off_CRM" / "browser_vault" if base else None


def _windows_dpapi(create: bool) -> tuple[bytes | None, str]:
    if os.name != "nt":
        return None, ""
    directory = _windows_dpapi_dir()
    if directory is None:
        return None, ""
    path = directory / "master.dpapi"
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
    except (AttributeError, OSError):
        return None, ""

    if path.exists():
        try:
            protected = path.read_bytes()
            source, _source_buffer = _blob(protected)
            output = _DataBlob()
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
            )
            if not ok:
                return None, ""
            try:
                raw = ctypes.string_at(output.pbData, output.cbData)
            finally:
                kernel32.LocalFree(output.pbData)
            if len(raw) == 32:
                return raw, "windows-dpapi"
        except OSError:
            return None, ""
    if not create:
        return None, ""

    raw = secrets.token_bytes(32)
    source, _source_buffer = _blob(raw)
    output = _DataBlob()
    ok = crypt32.CryptProtectData(
        ctypes.byref(source), ctypes.c_wchar_p("off_CRM browser vault"), None, None, None, 0,
        ctypes.byref(output),
    )
    if not ok:
        return None, ""
    try:
        protected = ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(protected)
    return raw, "windows-dpapi"


def _keychain_lock_directory() -> Path:
    # The OS account's master is shared across vault directories. A lock inside
    # either workspace cannot serialize its first creation for the other one.
    return Path.home() / '.off_crm' / 'browser_vault_keychain'


def _keychain_backend(create: bool) -> tuple[bytes | None, str]:
    if sys.platform == "darwin":
        return _macos_keychain(create)
    if os.name == "nt":
        return _windows_dpapi(create)
    return _linux_keychain(create)


def _keychain_master(create: bool) -> tuple[bytes | None, str]:
    found = _keychain_backend(False)
    if found[0] is not None or not create:
        return found
    try:
        with workspace_lock(_keychain_lock_directory()):
            # Each backend reads again before creating. A different workspace
            # may have installed the durable master while this caller waited.
            return _keychain_backend(True)
    except (OSError, ValueError):
        # Without a common lock, choosing a new root could destroy access to
        # another vault. The caller must use its explicit passphrase instead.
        return None, ''


def _derive_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    phrase = str(passphrase or "")
    if len(phrase) < 12:
        raise VaultLocked(
            "The browser vault passphrase must be at least 12 characters. "
            "It is a fallback for an unavailable OS credential store, not a PIN."
        )
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(phrase.encode("utf-8"))


class SessionVault:
    """Per-account encrypted browser sessions, inaccessible to model-facing code.

    The model-facing Page API never receives this object. Trusted orchestration
    may call `capture` after an attended login and `restore` before opening the
    platform. Both return metadata only; plaintext cookies stay inside this
    module long enough to move between Chrome and authenticated encryption.
    """

    def __init__(self, data_dir: Path | str, *, passphrase: str = "", workspace_id: str | None = None) -> None:
        self.directory = Path(data_dir) / "browser_vault"
        self.metadata_path = self.directory / "metadata.json"
        self.workspace_id = _workspace_identity(workspace_id) if workspace_id is not None else None
        with workspace_lock(self.directory):
            self._root, self.key_source = self._master(passphrase)

    def _master(self, passphrase: str) -> tuple[bytes, str]:
        root, source = _keychain_master(create=True)
        if root is not None:
            return root, source
        if not passphrase:
            raise VaultLocked(
                "No OS credential store is available. Supply the browser-vault "
                "passphrase for this process; off_CRM will derive the master key "
                "with scrypt and will not store the passphrase."
            )
        metadata = self._metadata()
        encoded_salt = str(metadata.get("passphrase_salt") or "")
        if encoded_salt:
            try:
                salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
            except (ValueError, UnicodeEncodeError) as exc:
                raise VaultLocked("The browser-vault passphrase salt is invalid.") from exc
        else:
            salt = secrets.token_bytes(16)
            metadata["version"] = VAULT_VERSION
            metadata["passphrase_salt"] = base64.urlsafe_b64encode(salt).decode("ascii")
            _atomic_json(self.metadata_path, metadata)
        return _derive_from_passphrase(passphrase, salt), "passphrase-scrypt"

    def _metadata(self) -> dict[str, Any]:
        if not self.metadata_path.exists():
            return {}
        try:
            payload = json.loads(private_read(self.metadata_path).decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VaultLocked("The browser-vault metadata cannot be read safely.") from exc
        if not isinstance(payload, dict):
            raise VaultLocked("The browser-vault metadata has the wrong shape.")
        return payload

    @property
    def _master_fernet(self) -> Fernet:
        if len(self._root) != 32:
            raise VaultLocked("The browser vault is locked in this process.")
        return Fernet(base64.urlsafe_b64encode(self._root))

    def _path(self, workspace_id: str, platform_id: str) -> Path:
        workspace = _workspace_identity(workspace_id)
        if self.workspace_id is not None and workspace != self.workspace_id:
            raise VaultLocked("This vault belongs to another workspace.")
        platform = _checked(platform_id, "platform id")
        digest = hashlib.sha256(f"{workspace}\0{platform}".encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{digest}.vault.json"

    def _read_envelope(self, workspace_id: str, platform_id: str, *, allow_legacy: bool = False) -> dict[str, Any]:
        path = self._path(workspace_id, platform_id)
        if not path.exists():
            raise VaultLocked(f"No vaulted session exists for {platform_id!r}.")
        try:
            payload = json.loads(private_read(path).decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VaultLocked("The vaulted session cannot be read safely.") from exc
        if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload.get('version') not in (1, VAULT_VERSION):
            raise VaultLocked("The vaulted session has an unsupported format.")
        if payload['version'] == 1 and not allow_legacy:
            raise VaultLocked("This legacy session needs explicit owner migration before use. Back up and migrate it or reconnect the workspace.")
        if payload.get("workspace_id") != _checked(workspace_id, "workspace id"):
            raise VaultLocked("The vaulted session belongs to a different workspace.")
        if payload.get("platform_id") != _checked(platform_id, "platform id"):
            raise VaultLocked("The vaulted session belongs to a different platform.")
        return payload

    def _envelope_fernet(self, workspace_id: str, platform_id: str) -> Fernet:
        if len(self._root) != 32:
            raise VaultLocked('The browser vault is locked in this process.')
        context = f'offcrm-vault-v2\0{workspace_id}\0{platform_id}'.encode()
        key = hmac.new(self._root, context, hashlib.sha256).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    def _page_context(self, page: Any, workspace_id: str) -> str:
        if len(self._root) != 32:
            raise VaultLocked('The browser vault is locked in this process.')
        identity = _workspace_identity(workspace_id)
        self._path(identity, 'context-check')
        bound = getattr(page, 'workspace_id', 'local')
        context = str(getattr(page, 'browser_context_id', '') or '')
        if bound != identity:
            raise VaultError('The browser page belongs to another workspace.')
        if identity != 'local' and not context:
            raise VaultError('A nonlocal workspace requires an isolated browser context.')
        return context

    def _account_key(self, envelope: dict[str, Any] | None = None) -> bytes:
        if envelope is None:
            return Fernet.generate_key()
        wrapped = str(envelope.get("wrapped_key") or "").encode("ascii", "strict")
        try:
            wrapper = self._master_fernet if envelope.get('version') == 1 else self._envelope_fernet(
                str(envelope['workspace_id']), str(envelope['platform_id']))
            key = wrapper.decrypt(wrapped)
            Fernet(key)
            return key
        except (InvalidToken, ValueError, TypeError) as exc:
            raise VaultLocked(
                "The account key cannot be opened with this OS credential or passphrase."
            ) from exc

    def seal(self, workspace_id: str, platform_id: str, material: dict[str, Any]) -> VaultMetadata:
        with workspace_lock(self.directory):
            if set(material) != {"cookies"} or not isinstance(material.get("cookies"), list):
                raise VaultError("Browser-vault material must contain only a cookies list.")
            workspace = _workspace_identity(workspace_id)
            platform = _checked(platform_id, "platform id")
            path = self._path(workspace, platform)
            existing = self._read_envelope(workspace, platform) if path.exists() else None
            account_key = self._account_key(existing)
            encoded = json.dumps(material, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ciphertext = Fernet(account_key).encrypt(encoded).decode("ascii")
            wrapped_key = (
                str(existing["wrapped_key"])
                if existing is not None
                else self._envelope_fernet(workspace, platform).encrypt(account_key).decode("ascii")
            )
            cookies = material.get("cookies") if isinstance(material, dict) else None
            cookie_count = len(cookies) if isinstance(cookies, list) else 0
            envelope = {
                "version": VAULT_VERSION,
                "workspace_id": workspace,
                "platform_id": platform,
                "key_source": self.key_source,
                "key_id": hashlib.sha256(account_key).hexdigest()[:16],
                "wrapped_key": wrapped_key,
                "ciphertext": ciphertext,
                "cookie_count": cookie_count,
            }
            _atomic_json(path, envelope)
            return VaultMetadata(
                workspace_id=workspace,
                platform_id=platform,
                key_id=str(envelope["key_id"]),
                key_source=self.key_source,
                cookie_count=cookie_count,
            )

    def unseal(self, workspace_id: str, platform_id: str) -> dict[str, Any]:
        envelope = self._read_envelope(workspace_id, platform_id)
        account_key = self._account_key(envelope)
        try:
            plaintext = Fernet(account_key).decrypt(str(envelope["ciphertext"]).encode("ascii"))
            payload = json.loads(plaintext.decode("utf-8"))
        except (InvalidToken, ValueError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
            raise VaultLocked("The vaulted session failed authenticated decryption.") from exc
        if not isinstance(payload, dict):
            raise VaultLocked("The decrypted session has the wrong shape.")
        return payload

    def inspect(self, workspace_id: str, platform_id: str) -> VaultMetadata:
        envelope = self._read_envelope(workspace_id, platform_id)
        return VaultMetadata(
            workspace_id=str(envelope["workspace_id"]),
            platform_id=str(envelope["platform_id"]),
            key_id=str(envelope["key_id"]),
            key_source=str(envelope["key_source"]),
            cookie_count=int(envelope.get("cookie_count", 0) or 0),
        )

    def migrate_legacy(self, workspace_id: str, platform_id: str, *, confirmation: str) -> VaultMetadata:
        """Owner-only offline conversion; a v1 identity cannot be authenticated."""
        if confirmation != 'MIGRATE VERIFIED WORKSPACE SESSION':
            raise VaultLocked('Verify the legacy workspace/account and type MIGRATE VERIFIED WORKSPACE SESSION.')
        with workspace_lock(self.directory):
            envelope = self._read_envelope(workspace_id, platform_id, allow_legacy=True)
            if envelope['version'] == VAULT_VERSION:
                return self.inspect(workspace_id, platform_id)
            key = self._account_key(envelope)
            try:
                material = json.loads(Fernet(key).decrypt(envelope['ciphertext'].encode()).decode())
            except (ValueError, InvalidToken) as exc:
                raise VaultLocked('The legacy session could not be authenticated.') from exc
            path = self._path(workspace_id, platform_id)
            backup = path.with_suffix(path.suffix+'.v1.bak')
            if backup.exists():
                raise VaultLocked('A migration backup already exists. Preserve it and resolve the earlier migration first.')
            _atomic_json(backup, envelope)
            path.unlink()
            try:
                return self.seal(workspace_id, platform_id, material)
            except Exception:
                _atomic_json(path, envelope)
                raise

    def lock(self) -> None:
        """Drop this process's reference to the master material."""
        self._root = b""

    async def capture(self, page: Any, target: Any, workspace_id: str) -> VaultMetadata:
        """Copy only this platform's cookies from Chrome into encrypted storage.

        This method is trusted orchestration, not a Page action and not an AI
        tool. Its return value is metadata only; cookie names and values never
        cross the boundary back to a model-facing caller.
        """
        self._page_context(page, workspace_id)
        session_id = str(getattr(page, 'session_id', '') or '')
        if not session_id:
            raise VaultError('Session capture requires an attached workspace page.')
        answer = await page.connection.send('Network.getCookies',
            {'urls': [target.login_url, target.home_url]}, session_id=session_id)
        raw = answer.get("cookies") if isinstance(answer, dict) else []
        cookies = [
            cleaned for cookie in (raw or [])
            if isinstance(cookie, dict)
            and _cookie_belongs(cookie, target)
            and (cleaned := _cookie_param(cookie)) is not None
        ]
        if not cookies:
            raise VaultError(
                f"Chrome returned no session cookies for {getattr(target, 'id', 'this platform')}. "
                "The vault will not record an empty session and call it protected."
            )
        return self.seal(workspace_id, str(target.id), {"cookies": cookies})

    async def restore(self, page: Any, target: Any, workspace_id: str) -> VaultMetadata:
        """Restore a platform's cookies directly into Chrome and return no secret."""
        self._page_context(page, workspace_id)
        payload = self.unseal(workspace_id, str(target.id))
        raw = payload.get("cookies")
        if not isinstance(raw, list) or not raw:
            raise VaultLocked("The vaulted session contains no cookies to restore.")
        cookies: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict) or not _cookie_belongs(item, target):
                raise VaultLocked("The vaulted session contains a cookie for another platform.")
            cleaned = _cookie_param(item)
            if cleaned is None:
                raise VaultLocked("The vaulted session contains an invalid cookie record.")
            cookies.append(cleaned)
        session_id = str(getattr(page, 'session_id', '') or '')
        if not session_id:
            raise VaultError('Session restore requires an attached workspace page.')
        await page.connection.send('Network.setCookies', {'cookies': cookies}, session_id=session_id)
        return self.inspect(workspace_id, str(target.id))


def _platform_domains(target: Any) -> frozenset[str]:
    domains: set[str] = set()
    for attribute in ("home_url", "login_url"):
        host = (urlparse(str(getattr(target, attribute, "") or "")).hostname or "").lower().strip(".")
        if not host:
            continue
        domains.add(host.removeprefix("www."))
        parts = host.split(".")
        if len(parts) >= 2:
            domains.add(".".join(parts[-2:]))
    return frozenset(domains)


def _cookie_belongs(cookie: dict[str, Any], target: Any) -> bool:
    domain = str(cookie.get("domain") or "").lower().strip().lstrip(".")
    if not domain:
        return False
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in _platform_domains(target))


def _cookie_param(cookie: dict[str, Any]) -> dict[str, Any] | None:
    """Build a CDP CookieParam from an empty allow-list, never copy wholesale."""
    name = str(cookie.get("name") or "")
    value = str(cookie.get("value") or "")
    domain = str(cookie.get("domain") or "")
    if not name or not domain:
        return None
    result: dict[str, Any] = {}
    for key in _COOKIE_FIELDS:
        if key not in cookie:
            continue
        value_at_key = cookie[key]
        if value_at_key is None:
            continue
        result[key] = value_at_key
    result["name"] = name
    result["value"] = value
    result["domain"] = domain
    result.setdefault("path", "/")
    return result
