from __future__ import annotations

import hmac
import json
import os
import re
import threading
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterable

from cryptography.fernet import Fernet, InvalidToken

from .models import ProviderConfig, to_utc_iso
from .providers import DATA_POLICIES, FallbackAIProvider, PolicyAIProvider, ProviderError, create_provider


PROFILE_TYPES = {
    "openai",
    "anthropic",
    "openai_compatible",
    "template_engine_http",
    "local_command",
}


def create_guarded_provider(
    config: ProviderConfig,
    *,
    data_policy: str = "minimal",
    audit_callback: Any | None = None,
    profile_id: str = "ad-hoc",
) -> PolicyAIProvider:
    """Build a provider that is always wrapped in the data-policy guard.

    Callers outside this module and the AI broker must use this rather than
    ``create_provider``: §5.5.1 requires that no code path can obtain an
    unguarded provider, and an ad-hoc provider supplied in a request body is
    exactly the path that used to skip the guard.
    """
    raw_provider = create_provider(config)
    return PolicyAIProvider(
        raw_provider,
        profile_id=profile_id,
        provider_type=config.provider_type,
        model=config.model,
        data_policy=data_policy,
        audit_callback=audit_callback,
    )


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, path)


class ProfileOwnedElsewhere(ValueError):
    """A confirmed profile belongs to another workspace; it is never taken over."""


class ProfileUnconfirmed(ValueError):
    """A profile saved before ownership was recorded: confirm it or remove it."""


def _confirmed(profile: dict[str, Any]) -> bool:
    # Recorded only by the server, from the login that saved the profile.
    # Older profiles carry an `owner` any caller could type — "default" from
    # the old form, or any name — so it says nothing about who saved them.
    return profile.get("owner_confirmed") is True


class ProviderProfileStore:
    """Local provider profiles with API keys encrypted outside SQLite."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.profile_path = self.data_dir / "provider_profiles.json"
        self.secret_path = self.data_dir / "provider_secrets.enc"
        self.key_path = self.data_dir / ".provider_master.key"
        self._lock = threading.RLock()

    def _profiles(self) -> list[dict[str, Any]]:
        if not self.profile_path.exists():
            return []
        try:
            payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError("Provider profile file is invalid") from exc
        if not isinstance(payload, list):
            raise ProviderError("Provider profile file must contain a list")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _fernet(self, *, create: bool) -> Fernet:
        if not self.key_path.exists():
            if not create:
                raise ProviderError("Provider encryption key is missing")
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass
        try:
            return Fernet(self.key_path.read_bytes().strip())
        except (OSError, ValueError) as exc:
            raise ProviderError("Provider encryption key is invalid") from exc

    def _secrets(self) -> dict[str, str]:
        if not self.secret_path.exists():
            return {}
        try:
            decrypted = self._fernet(create=False).decrypt(self.secret_path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
        except (OSError, InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("Stored provider credentials cannot be decrypted") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Stored provider credentials are invalid")
        return {str(key): str(value) for key, value in payload.items()}

    def _write_secrets(self, secrets: dict[str, str]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        token = self._fernet(create=True).encrypt(
            json.dumps(secrets, ensure_ascii=False).encode("utf-8")
        )
        with NamedTemporaryFile("wb", dir=self.data_dir, delete=False) as handle:
            handle.write(token)
            temporary = Path(handle.name)
        os.replace(temporary, self.secret_path)
        try:
            self.secret_path.chmod(0o600)
        except OSError:
            pass

    def _public(self, profile: dict[str, Any], secrets: dict[str, str]) -> dict[str, Any]:
        result = dict(profile)
        result.setdefault("data_policy", "minimal")
        result.setdefault("audit_payloads", False)
        result.setdefault("fallback_strategy", "priority")
        result.setdefault("last_health_status", "never")
        result.setdefault("last_checked_at", "")
        result.setdefault("last_error", "")
        has_secret = bool(secrets.get(str(profile.get("id", ""))))
        result["has_stored_secret"] = has_secret
        # A named variable is never read (D-154): without a typed key there is none.
        result["credential_source"] = "encrypted_local" if has_secret else "none"
        result["owner_confirmed"] = _confirmed(profile)
        return result

    def list(self, *, owner: str = "", include_unconfirmed: bool = False) -> list[dict[str, Any]]:
        """Every profile, or one workspace's.

        A workspace's list holds only profiles the server recorded as its own,
        unless `include_unconfirmed` — the install owner looking for strays.
        """
        with self._lock:
            secrets = self._secrets()
            items = self._profiles()
            if owner:
                items = [
                    item
                    for item in items
                    if str(item.get("owner", "")) == owner
                    and (include_unconfirmed or _confirmed(item))
                ]
            items.sort(
                key=lambda item: (
                    int(item.get("priority", 100)),
                    str(item.get("name", "")),
                )
            )
            return [self._public(item, secrets) for item in items]

    def upsert(
        self,
        values: dict[str, Any],
        *,
        owner: str,
        api_key: str = "",
        must_own: bool = False,
        keep_owner: bool = False,
    ) -> dict[str, Any]:
        """Save a profile for `owner`, the workspace the server decided on.

        Never the request's own `owner`: that let any login label a profile
        as someone else's (D-165, D-166). Whose an existing profile is, is
        checked under the same lock as the write (D-182): `must_own` refuses
        one that is not `owner`'s own; `keep_owner` leaves a confirmed one
        with its workspace and refuses one saved before ownership was.
        """
        with self._lock:
            return self._upsert(
                values, owner=owner, api_key=api_key, must_own=must_own, keep_owner=keep_owner
            )

    def _upsert(
        self,
        values: dict[str, Any],
        *,
        owner: str,
        api_key: str = "",
        must_own: bool = False,
        keep_owner: bool = False,
    ) -> dict[str, Any]:
        provider_type = str(values.get("provider_type", "")).strip().lower()
        if provider_type not in PROFILE_TYPES:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        profile_id = str(values.get("id", "")).strip()
        if profile_id and not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", profile_id):
            raise ValueError("Provider profile id contains unsupported characters")
        profile_id = profile_id or uuid.uuid4().hex
        profiles = self._profiles()
        current = next((item for item in profiles if item.get("id") == profile_id), None)
        if must_own and (
            current is None
            or (str(current.get("owner", "")), _confirmed(current)) != (owner, True)
        ):
            raise KeyError("Provider profile not found")
        if keep_owner and current is not None:
            if not _confirmed(current):
                # Saving over it would make it the saver's, with whatever key
                # and address it holds.
                raise ProfileUnconfirmed(
                    "This profile was saved before off_CRM recorded whose each one is. "
                    "Confirm it or remove it first; it cannot be saved over."
                )
            owner = str(current.get("owner", ""))
        now = to_utc_iso()
        profile = {
            "id": profile_id,
            "owner": str(owner or "").strip(),
            "owner_confirmed": True,
            "name": str(values.get("name") or "").strip(),
            "provider_type": provider_type,
            "model": str(values.get("model") or "").strip(),
            "api_key_env": str(values.get("api_key_env") or "").strip(),
            "base_url": str(values.get("base_url") or "").strip(),
            "timeout_seconds": max(5, min(int(values.get("timeout_seconds", 60)), 300)),
            "priority": max(1, min(int(values.get("priority", 100)), 1000)),
            "enabled": bool(values.get("enabled", True)),
            "data_policy": str(values.get("data_policy") or "minimal").strip(),
            "audit_payloads": bool(values.get("audit_payloads", False)),
            "fallback_strategy": str(values.get("fallback_strategy") or "priority").strip(),
            "extra": dict(values.get("extra") or {}),
            "last_health_status": str(current.get("last_health_status", "never")) if current else "never",
            "last_checked_at": str(current.get("last_checked_at", "")) if current else "",
            "last_error": str(current.get("last_error", "")) if current else "",
            "created_at": str(current.get("created_at")) if current else now,
            "updated_at": now,
        }
        if not profile["name"]:
            raise ValueError("Provider profile name is required")
        if not profile["owner"]:
            raise ValueError("Provider profile owner is required")
        if profile["data_policy"] not in DATA_POLICIES:
            raise ValueError("data_policy must be minimal, standard, or full")
        if profile["fallback_strategy"] not in {"priority", "round_robin", "parallel"}:
            raise ValueError("fallback_strategy must be priority, round_robin, or parallel")
        profiles = [item for item in profiles if item.get("id") != profile_id]
        profiles.append(profile)
        _atomic_json(self.profile_path, profiles)
        secrets = self._secrets()
        if api_key.strip():
            secrets[profile_id] = api_key.strip()
            self._write_secrets(secrets)
        return self._public(profile, secrets)

    def ownership(self, profile_id: str) -> tuple[str, bool] | None:
        """(owner, whether the server recorded it), or None when absent."""
        with self._lock:
            for item in self._profiles():
                if item.get("id") == profile_id:
                    return str(item.get("owner", "")), _confirmed(item)
        return None

    def confirm(
        self,
        profile_id: str,
        *,
        caller: str,
        owner_for: Callable[[str], str],
        api_key: str,
    ) -> dict[str, Any]:
        """Record whose a profile saved before ownership was is (D-166, D-177).

        The caller proves it by typing the key the profile holds: its label
        proves nothing, as every login's saves were once labelled "default"
        (D-185). `owner_for` turns the label into the workspace it goes to, so
        confirming never moves a profile into the caller's chain by default. A
        confirmed profile of another workspace stays theirs, key and all.
        """
        with self._lock:
            profiles = self._profiles()
            profile = next((item for item in profiles if item.get("id") == profile_id), None)
            if profile is None:
                raise KeyError("Provider profile not found")
            current = str(profile.get("owner", ""))
            secrets = self._secrets()
            if _confirmed(profile):
                if current == caller:
                    return self._public(profile, secrets)
                raise ProfileOwnedElsewhere(
                    f"This profile belongs to workspace {current}. It stays theirs; "
                    "remove it instead if it should not exist."
                )
            stored = secrets.get(profile_id, "")
            if not stored:
                # Some types need no key, but without one nothing proves whose
                # the profile is — and each is sent the drafts (D-191).
                raise ProfileOwnedElsewhere(
                    "No key is stored in this profile, so nothing proves it is yours, and it "
                    "cannot be confirmed. Remove it."
                )
            if not hmac.compare_digest(stored.encode("utf-8"), api_key.strip().encode("utf-8")):
                raise ProfileOwnedElsewhere(
                    "That is not the key this profile holds, so off_CRM cannot tell it is yours. "
                    "Type the API key saved in it, or remove it if you did not set it up."
                )
            profile.update(owner=owner_for(current), owner_confirmed=True, updated_at=to_utc_iso())
            _atomic_json(self.profile_path, profiles)
            return self._public(profile, secrets)

    def unconfirmed_count(self) -> int:
        """Profiles saved before ownership was recorded: the owner's to settle."""
        with self._lock:
            return sum(1 for item in self._profiles() if not _confirmed(item))

    def delete(self, profile_id: str) -> None:
        with self._lock:
            profiles = self._profiles()
            if not any(item.get("id") == profile_id for item in profiles):
                raise KeyError("Provider profile not found")
            _atomic_json(
                self.profile_path,
                [item for item in profiles if item.get("id") != profile_id],
            )
            secrets = self._secrets()
            if profile_id in secrets:
                del secrets[profile_id]
                self._write_secrets(secrets)

    def _provider(self, profile: dict[str, Any], secrets: dict[str, str]):
        config = ProviderConfig(
            provider_type=str(profile["provider_type"]),
            model=str(profile.get("model", "")),
            api_key_env=str(profile.get("api_key_env", "")),
            base_url=str(profile.get("base_url", "")),
            timeout_seconds=int(profile.get("timeout_seconds", 60)),
            extra=dict(profile.get("extra") or {}),
        )
        stored = secrets.get(str(profile["id"]), "")
        # Only the key typed into the app, never the server's environment —
        # whatever variable an older profile still names (D-154, DD-64).
        config.api_key_env = "OFFSETX_PROVIDER_PROFILE_KEY" if stored else ""
        return create_provider(config, environ={config.api_key_env: stored} if stored else {})

    def router(
        self,
        *,
        owner: str,
        profile_ids: Iterable[str] = (),
        strategy: str = "",
        audit_callback: Any | None = None,
        may_confirm: bool = False,
    ) -> FallbackAIProvider:
        """One workspace's chain. There is no "every profile" chain: the install
        owner's used to be one, so a client's planted profile received the
        owner's contacts and wrote the owner's drafts (D-165)."""
        if not str(owner or "").strip():
            raise ValueError("A fallback chain belongs to one workspace; none was named")
        with self._lock:
            selected_ids = set(profile_ids)
            everything = self._profiles()
            profiles = [
                item
                for item in everything
                if bool(item.get("enabled", True))
                and _confirmed(item)
                and str(item.get("owner", "")) == owner
            ]
            if selected_ids:
                profiles = [item for item in profiles if str(item.get("id")) in selected_ids]
            profiles.sort(
                key=lambda item: (
                    int(item.get("priority", 100)),
                    str(item.get("name", "")),
                )
            )
            secrets = self._secrets()
            waiting = sum(1 for item in everything if not _confirmed(item))
        if not profiles:
            if may_confirm and waiting:
                # A count, not names: a label anyone could type is no evidence
                # the profile is the reader's (D-177).
                raise ProviderError(
                    f"{waiting} provider profile(s) saved before off_CRM recorded whose each one "
                    "is are waiting in Settings, under \"Provider profiles to confirm\". Drafts use "
                    "none of them until you confirm them. Or generate with local templates."
                )
            raise ProviderError(
                "No provider profile is set up for your workspace, so there is nothing to "
                "personalise with. Generate with local templates instead."
            )
        providers: list[tuple[str, Any]] = []
        configuration_errors: list[str] = []
        for profile in profiles:
            try:
                raw_provider = self._provider(profile, secrets)
                providers.append(
                    (
                        str(profile["id"]),
                        PolicyAIProvider(
                            raw_provider,
                            profile_id=str(profile["id"]),
                            provider_type=str(profile["provider_type"]),
                            model=str(profile.get("model", "")),
                            data_policy=str(profile.get("data_policy", "minimal")),
                            audit_payloads=bool(profile.get("audit_payloads", False)),
                            audit_callback=audit_callback,
                        ),
                    )
                )
            except Exception as exc:
                configuration_errors.append(f"{profile.get('name', profile.get('id'))}: {exc}")
        if not providers and configuration_errors:
            raise ProviderError("No usable provider profiles. " + "; ".join(configuration_errors))
        selected_strategy = strategy or (
            str(profiles[0].get("fallback_strategy", "priority")) if profiles else "priority"
        )
        return FallbackAIProvider(providers, strategy=selected_strategy)

    def health(self, profile_id: str, *, probe: bool = False) -> dict[str, Any]:
        with self._lock:
            profile = next(
                (item for item in self._profiles() if item.get("id") == profile_id), None
            )
            if not profile:
                raise KeyError("Provider profile not found")
            try:
                provider = self._provider(profile, self._secrets())
            except Exception as exc:
                error = str(exc)[:1000]
                profiles = self._profiles()
                for item in profiles:
                    if item.get("id") == profile_id:
                        item["last_health_status"] = "unhealthy"
                        item["last_checked_at"] = to_utc_iso()
                        item["last_error"] = error
                _atomic_json(self.profile_path, profiles)
                return {
                    "status": "unhealthy",
                    "profile_id": profile_id,
                    "error": error,
                }
        status = "configured"
        error = ""
        try:
            if probe:
                provider.generate(
                    system_prompt="Return JSON with subject and body only.",
                    user_prompt='Return {"subject":"health check","body":"ok"}.',
                )
                status = "healthy"
        except Exception as exc:
            status = "unhealthy"
            error = str(exc)[:1000]
        with self._lock:
            profiles = self._profiles()
            for item in profiles:
                if item.get("id") == profile_id:
                    item["last_health_status"] = status
                    item["last_checked_at"] = to_utc_iso()
                    item["last_error"] = error
            _atomic_json(self.profile_path, profiles)
        result = {"status": status, "profile_id": profile_id}
        if error:
            result["error"] = error
        return result
