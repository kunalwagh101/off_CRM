"""Per-workspace AI settings and encrypted provider keys.

off_CRM is multi-user and heading for a shared server, so nothing here is
global.  Two colleagues can enable different providers, sit at different
policies, and hold different keys, without either one's choice changing what the
other's calls send.

Keys are encrypted with Fernet outside the CRM database, reusing the pattern
already proven in ``outreach/provider_profiles.py``.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ..outreach.models import to_utc_iso
from ..workspaces import workspace_id as checked_workspace, workspace_directory, workspace_env, workspace_lock, private_read
from .broker import WorkspaceEgressSettings
from .errors import RegistryError
from .quota import QuotaLimits
from .registry import ProviderOverride, ProviderRegistry
from .tiers import (
    MAILBOX_UNLOCK_PHRASE,
    DataPolicy,
    TrustTier,
    coerce_policy,
    coerce_tier,
    default_policy_for_tier,
    policy_ceiling_for_tier,
)

DEFAULT_WORKSPACE = "local"


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, path)


#: The public name. Every store in off_CRM that keeps a JSON document needs
#: exactly this — write beside the target, then rename — and a second copy of it
#: is a second place for the "write then crash" bug to be fixed only once.
atomic_json = _atomic_json


class WorkspaceAISettingsStore:
    """Private settings and keys, optionally bound to one trusted workspace."""

    def __init__(self, data_dir: Path | str, registry: ProviderRegistry, *, workspace_id: str | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.registry = registry
        self.workspace_id = checked_workspace(workspace_id) if workspace_id is not None else None
        self.settings_path = self.data_dir / "ai_workspaces.json"
        self.secret_path = self.data_dir / "ai_provider_keys.enc"
        self.key_path = self.data_dir / ".ai_master.key"
        self._lock = threading.RLock()

    # ── encrypted keys ──────────────────────────────────────────────────────

    def _directory(self, workspace_id: str) -> Path:
        identity = checked_workspace(workspace_id)
        if self.workspace_id is not None and identity != self.workspace_id:
            raise RegistryError("This credential store belongs to another workspace.")
        return workspace_directory(self.data_dir, 'local' if self.workspace_id is not None else identity)

    def _fernet(self, *, create: bool, workspace_id: str = DEFAULT_WORKSPACE) -> Fernet:
        directory = self._directory(workspace_id)
        path = directory / '.ai_master.key'
        if create and not path.exists():
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            except FileExistsError:
                fd = None
            if fd is not None:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(Fernet.generate_key())
                    handle.flush()
                    os.fsync(handle.fileno())
        try:
            return Fernet(private_read(path, limit=256).strip())
        except (OSError, ValueError) as exc:
            raise RegistryError("AI provider encryption key is missing or invalid.") from exc

    def _secrets(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, str]:
        path = self._directory(workspace_id)/'ai_provider_keys.enc'
        if path.is_symlink():
            raise RegistryError('Workspace state must not be a symbolic link.')
        if not path.exists():
            return {}
        try:
            decrypted = self._fernet(create=False, workspace_id=workspace_id).decrypt(private_read(path))
            payload = json.loads(decrypted.decode('utf-8'))
            if not isinstance(payload, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k,v in payload.items()):
                raise ValueError('invalid secret document')
        except (OSError, ValueError, InvalidToken) as exc:
            raise RegistryError("Stored AI provider keys cannot be decrypted. Restore the workspace backup; no fallback key was used.") from exc
        return payload

    def _write_secrets(self, secrets: dict[str, str], workspace_id: str = DEFAULT_WORKSPACE) -> None:
        directory = self._directory(workspace_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        token = self._fernet(create=True, workspace_id=workspace_id).encrypt(json.dumps(secrets, ensure_ascii=False).encode())
        with NamedTemporaryFile('wb', dir=directory, delete=False) as handle:
            handle.write(token)
            temporary = Path(handle.name)
        os.replace(temporary, directory/'ai_provider_keys.enc')

    @staticmethod
    def _secret_key(workspace_id: str, provider_id: str) -> str:
        checked_workspace(workspace_id)
        if not isinstance(provider_id, str) or not provider_id or '::' in provider_id:
            raise ValueError('Provider IDs must be nonempty and cannot contain a workspace separator.')
        return f'{workspace_id}::{provider_id}'

    def set_key(self, workspace_id: str, provider_id: str, api_key: str) -> None:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            secrets = self._secrets(workspace_id)
            slot = self._secret_key(workspace_id, provider_id)
            if api_key.strip():
                secrets[slot] = api_key.strip()
            else:
                secrets.pop(slot, None)
            self._write_secrets(secrets, workspace_id)

    def key_for(self, workspace_id: str, provider_id: str) -> str:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            stored = self._secrets(workspace_id).get(self._secret_key(workspace_id, provider_id), '')
        if stored:
            return stored
        return os.environ.get(workspace_env(workspace_id, f'AI_{provider_id.upper()}_KEY'), '').strip()

    def credential_resolver(self, workspace_id: str):
        self._directory(workspace_id)
        def resolve(provider_id: str) -> str:
            return self.key_for(workspace_id, provider_id)
        return resolve

    # ── settings document ───────────────────────────────────────────────────

    def _document(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        path = self._directory(workspace_id)/'ai_workspaces.json'
        if path.is_symlink():
            raise RegistryError('Workspace state must not be a symbolic link.')
        if not path.exists():
            return {}
        try:
            payload = json.loads(private_read(path).decode())
            if not isinstance(payload, dict):
                raise ValueError('invalid settings document')
            return payload
        except (OSError, ValueError) as exc:
            raise RegistryError('Workspace settings cannot be read safely. Restore a valid backup.') from exc

    def _blank(self, workspace_id: str) -> dict[str, Any]:
        return {'workspace_id':workspace_id, 'providers':{}, 'positioning_line':'',
                'owner_domains':[], 'owner_addresses':[], 'mailbox_unlock_phrase':'',
                'created_at':to_utc_iso(), 'updated_at':to_utc_iso()}

    def raw(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            return dict(self._document(workspace_id).get(workspace_id) or self._blank(workspace_id))

    def save(self, workspace_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            document = self._document(workspace_id)
            current = dict(document.get(workspace_id) or self._blank(workspace_id))
            current.update(values)
            current['workspace_id'] = workspace_id
            current['updated_at'] = to_utc_iso()
            document[workspace_id] = current
            _atomic_json(self._directory(workspace_id)/'ai_workspaces.json', document)
            return current

    def migrate_legacy_workspace(self, workspace_id: str) -> dict[str, Any]:
        """Owner-only offline copy of one named legacy record into private storage.

        The original files are retained as a rollback backup, never exposed by
        the bound per-workspace API. Existing destination files are not replaced.
        """
        identity = checked_workspace(workspace_id)
        if self.workspace_id is not None or identity == 'local':
            raise RegistryError('Legacy migration requires the unbound owner store and a nonlocal workspace.')
        with self._lock, workspace_lock(self.data_dir), workspace_lock(self._directory(identity)):
            directory = self._directory(identity)
            if (directory/'ai_provider_keys.enc').exists() or (directory/'ai_workspaces.json').exists():
                raise RegistryError('Workspace destination already exists. Preserve it instead of overwriting it.')
            prefix = identity+'::'
            selected = {k:v for k,v in self._secrets('local').items() if k.startswith(prefix)}
            settings = self._document('local').get(identity)
            if not selected and not isinstance(settings, dict):
                raise RegistryError('The legacy store has no record for this workspace.')
            artifacts = [directory/name for name in ('ai_provider_keys.enc', 'ai_workspaces.json', '.ai_master.key')]
            existing = {path for path in artifacts if path.exists() or path.is_symlink()}
            try:
                if selected:
                    self._write_secrets(selected, identity)
                if isinstance(settings, dict):
                    _atomic_json(directory/'ai_workspaces.json', {identity: settings})
            except Exception:
                for path in artifacts:
                    if path not in existing:
                        path.unlink(missing_ok=True)
                raise
            return {'workspace_id':identity,'providers_migrated':len(selected),'settings_migrated':isinstance(settings, dict)}

    # ── provider enable / configure ─────────────────────────────────────────

    def connect_provider(
        self,
        workspace_id: str,
        provider_id: str,
        *,
        api_key: str = "",
        model_id: str = "",
        model_ids: list[str] | None = None,
        data_policy: str = "",
        enabled: bool = True,
        requests_per_minute: int | None = None,
        requests_per_day: int | None = None,
        max_spend_usd_per_day: float | None = None,
    ) -> dict[str, Any]:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            entry = self.registry.require(provider_id)
            tier = entry.derived_tier
            policy = (
                coerce_policy(data_policy, default=default_policy_for_tier(tier))
                if data_policy
                else default_policy_for_tier(tier)
            )
            ceiling = policy_ceiling_for_tier(tier)
            clamped = policy.rank > ceiling.rank
            if clamped:
                policy = ceiling

            # A key unlocks many models. `model_id` is kept for older stored records
            # and single-model callers; `model_ids` is the list the UI sends.
            chosen: list[str] = [str(item).strip() for item in (model_ids or []) if str(item).strip()]
            if not chosen:
                chosen = [model_id.strip() or entry.default_model]

            # Refuse a model the trust rules cannot place. Unknown is not safe, and
            # failing here is far better than failing at call time (§5.5.7).
            unusable: list[str] = []
            for candidate in chosen:
                if entry.model(candidate) is not None:
                    continue
                if not self.registry.classify_model(candidate)["known"]:
                    unusable.append(candidate)
            if unusable:
                raise ValueError(
                    "These models do not match any rule in config/providers.yaml, so "
                    "off_CRM cannot tell who built them and will not use them: "
                    + ", ".join(unusable)
                    + ". Add a model_origin_rules entry for them first."
                )

            free = entry.free_tier
            record = {
                "provider_id": provider_id,
                "enabled": bool(enabled),
                "model_id": chosen[0],
                "model_ids": chosen,
                "data_policy": policy.value,
                "requests_per_minute": (
                    requests_per_minute
                    if requests_per_minute is not None
                    else (free.requests_per_minute if free else 0)
                ),
                "requests_per_day": (
                    requests_per_day
                    if requests_per_day is not None
                    else (free.requests_per_day if free else 0)
                ),
                "max_spend_usd_per_day": float(max_spend_usd_per_day or 0.0),
                "connected_at": to_utc_iso(),
            }

            document = self.raw(workspace_id)
            providers = dict(document.get("providers") or {})
            existing = dict(providers.get(provider_id) or {})
            existing.update(record)
            providers[provider_id] = existing
            saved = self.save(workspace_id, {"providers": providers})

            if api_key:
                self.set_key(workspace_id, provider_id, api_key)

            return {
                "provider": existing,
                "policy_was_clamped": clamped,
                "tier": tier.value,
                "policy_ceiling": ceiling.value,
                "workspace": saved["workspace_id"],
            }

    def disconnect_provider(self, workspace_id: str, provider_id: str) -> None:
        with self._lock, workspace_lock(self._directory(workspace_id)):
            document = self.raw(workspace_id)
            providers = dict(document.get("providers") or {})
            providers.pop(provider_id, None)
            self.save(workspace_id, {"providers": providers})
            self.set_key(workspace_id, provider_id, "")

    def set_override(
        self,
        workspace_id: str,
        provider_id: str,
        *,
        trust_tier: str = "",
        data_policy: str = "",
        allow_above_ceiling: bool = False,
        reason: str = "",
        decided_by: str = "",
    ) -> dict[str, Any]:
        """Record an explicit decision to depart from the config default.

        Raising a provider above its ceiling is allowed — the owner asked to keep
        that freedom — but it is never silent: a reason is required and the
        decision is stored with who made it and when.
        """
        with self._lock, workspace_lock(self._directory(workspace_id)):
            self.registry.require(provider_id)
            if allow_above_ceiling and not reason.strip():
                raise ValueError(
                    "Raising a provider above its trust ceiling needs a reason. "
                    "It is recorded so you can see later why the decision was made."
                )
            document = self.raw(workspace_id)
            overrides = dict(document.get("overrides") or {})
            if not (trust_tier or data_policy or allow_above_ceiling):
                overrides.pop(provider_id, None)
            else:
                overrides[provider_id] = ProviderOverride(
                    provider_id=provider_id,
                    trust_tier=coerce_tier(trust_tier) if trust_tier else None,
                    data_policy=coerce_policy(data_policy) if data_policy else None,
                    allow_above_ceiling=bool(allow_above_ceiling),
                    reason=reason.strip(),
                    decided_by=decided_by or workspace_id,
                    decided_at=to_utc_iso(),
                ).to_dict()
            return self.save(workspace_id, {"overrides": overrides})

    def unlock_mailbox(self, workspace_id: str, phrase: str) -> dict[str, Any]:
        cleaned = str(phrase or "").strip()
        if cleaned and cleaned != MAILBOX_UNLOCK_PHRASE:
            raise ValueError(
                f'To let mailbox content reach an AI provider, type exactly: "{MAILBOX_UNLOCK_PHRASE}"'
            )
        return self.save(workspace_id, {"mailbox_unlock_phrase": cleaned})

    # ── the shape the broker wants ──────────────────────────────────────────

    def egress_settings(self, workspace_id: str = DEFAULT_WORKSPACE) -> WorkspaceEgressSettings:
        document = self.raw(workspace_id)
        providers = dict(document.get("providers") or {})
        enabled = tuple(
            provider_id
            for provider_id, record in providers.items()
            if bool(record.get("enabled", True))
        )
        overrides = {
            provider_id: ProviderOverride.from_dict(payload)
            for provider_id, payload in (document.get("overrides") or {}).items()
            if isinstance(payload, dict)
        }
        quota_limits = {
            provider_id: QuotaLimits(
                requests_per_minute=int(record.get("requests_per_minute", 0) or 0),
                requests_per_day=int(record.get("requests_per_day", 0) or 0),
                max_spend_usd_per_day=float(record.get("max_spend_usd_per_day", 0.0) or 0.0),
            )
            for provider_id, record in providers.items()
        }
        policies = {
            provider_id: coerce_policy(record.get("data_policy"))
            for provider_id, record in providers.items()
            if record.get("data_policy")
        }
        # Previously the chosen model was stored and displayed but never reached
        # the broker, so every call silently used the provider's default. Older
        # records hold a single `model_id`; both shapes are read here.
        enabled_models = {
            provider_id: tuple(
                str(item)
                for item in (
                    record.get("model_ids")
                    or ([record["model_id"]] if record.get("model_id") else [])
                )
            )
            for provider_id, record in providers.items()
        }
        return WorkspaceEgressSettings(
            workspace_id=workspace_id,
            enabled_provider_ids=enabled,
            overrides=overrides,
            quota_limits=quota_limits,
            owner_domains=tuple(document.get("owner_domains") or ()),
            owner_addresses=tuple(document.get("owner_addresses") or ()),
            positioning_line=str(document.get("positioning_line", "")),
            mailbox_unlock_phrase=str(document.get("mailbox_unlock_phrase", "")),
            default_policy_by_provider=policies,
            enabled_models=enabled_models,
        )

    def describe(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        """Everything the Connectors screen needs, in one call."""
        document = self.raw(workspace_id)
        connected = dict(document.get("providers") or {})
        overrides = dict(document.get("overrides") or {})
        rows: list[dict[str, Any]] = []
        for entry in self.registry.all():
            record = connected.get(entry.id)
            override = overrides.get(entry.id)
            tier = coerce_tier(override.get("trust_tier"), default=entry.derived_tier) if override else entry.derived_tier
            payload = entry.to_dict()
            payload.update(
                {
                    "connected": record is not None,
                    "enabled": bool(record.get("enabled", False)) if record else False,
                    "has_key": bool(self.key_for(workspace_id, entry.id)),
                    "model_id": (record or {}).get("model_id", entry.default_model),
                    "model_ids": list(
                        (record or {}).get("model_ids")
                        or ([record["model_id"]] if record and record.get("model_id") else [])
                    ),
                    "supports_model_discovery": entry.supports_model_discovery,
                    # Every model this key could run, each with its own tier, so
                    # the card can show that one key spans several trust levels.
                    "available_models": [
                        {
                            **model.to_dict(),
                            "tier": entry.tier_for_model(model.id).value,
                        }
                        for model in entry.models
                    ],
                    "data_policy": (record or {}).get(
                        "data_policy", default_policy_for_tier(tier).value
                    ),
                    "effective_tier": tier.value,
                    "override": override,
                    "requests_per_minute": (record or {}).get("requests_per_minute", 0),
                    "requests_per_day": (record or {}).get("requests_per_day", 0),
                    "max_spend_usd_per_day": (record or {}).get("max_spend_usd_per_day", 0.0),
                }
            )
            rows.append(payload)
        return {
            "workspace_id": workspace_id,
            "positioning_line": document.get("positioning_line", ""),
            "owner_domains": document.get("owner_domains") or [],
            "owner_addresses": document.get("owner_addresses") or [],
            "mailbox_unlocked": str(document.get("mailbox_unlock_phrase", "")).strip()
            == MAILBOX_UNLOCK_PHRASE,
            "mailbox_unlock_phrase_required": MAILBOX_UNLOCK_PHRASE,
            "providers": rows,
            "policy_levels": [
                {
                    "value": policy.value,
                    "label": policy.label,
                    "description": policy.description,
                }
                for policy in DataPolicy
            ],
            "tiers": [
                {
                    "tier": tier.value,
                    "label": tier.label,
                    "policy_ceiling": policy_ceiling_for_tier(tier).value,
                }
                for tier in TrustTier
            ],
        }
