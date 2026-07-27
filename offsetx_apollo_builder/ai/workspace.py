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


class WorkspaceAISettingsStore:
    """Reads and writes one JSON document per install, keyed by workspace."""

    def __init__(self, data_dir: Path | str, registry: ProviderRegistry) -> None:
        self.data_dir = Path(data_dir)
        self.registry = registry
        self.settings_path = self.data_dir / "ai_workspaces.json"
        self.secret_path = self.data_dir / "ai_provider_keys.enc"
        self.key_path = self.data_dir / ".ai_master.key"
        self._lock = threading.RLock()

    # ── encrypted keys ──────────────────────────────────────────────────────

    def _fernet(self, *, create: bool) -> Fernet:
        if not self.key_path.exists():
            if not create:
                raise RegistryError("AI provider encryption key is missing")
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass
        try:
            return Fernet(self.key_path.read_bytes().strip())
        except (OSError, ValueError) as exc:
            raise RegistryError("AI provider encryption key is invalid") from exc

    def _secrets(self) -> dict[str, str]:
        if not self.secret_path.exists():
            return {}
        try:
            decrypted = self._fernet(create=False).decrypt(self.secret_path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
        except (OSError, InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryError("Stored AI provider keys cannot be decrypted") from exc
        return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}

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

    @staticmethod
    def _secret_key(workspace_id: str, provider_id: str) -> str:
        return f"{workspace_id}::{provider_id}"

    def set_key(self, workspace_id: str, provider_id: str, api_key: str) -> None:
        with self._lock:
            secrets = self._secrets()
            slot = self._secret_key(workspace_id, provider_id)
            if api_key.strip():
                secrets[slot] = api_key.strip()
            else:
                secrets.pop(slot, None)
            self._write_secrets(secrets)

    def key_for(self, workspace_id: str, provider_id: str) -> str:
        """Resolution order: stored key, then a named environment variable.

        The env fallback keeps server deployments simple — on Render the key can
        live in the dashboard rather than in an uploaded file.
        """
        with self._lock:
            try:
                stored = self._secrets().get(self._secret_key(workspace_id, provider_id), "")
            except RegistryError:
                stored = ""
        if stored:
            return stored
        return os.environ.get(f"OFFSETX_AI_{provider_id.upper()}_KEY", "").strip()

    def credential_resolver(self, workspace_id: str):
        def resolve(provider_id: str) -> str:
            return self.key_for(workspace_id, provider_id)

        return resolve

    # ── settings document ───────────────────────────────────────────────────

    def _document(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _blank(self, workspace_id: str) -> dict[str, Any]:
        return {
            "workspace_id": workspace_id,
            "providers": {},
            "positioning_line": "",
            "owner_domains": [],
            "owner_addresses": [],
            "mailbox_unlock_phrase": "",
            "created_at": to_utc_iso(),
            "updated_at": to_utc_iso(),
        }

    def raw(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        with self._lock:
            return dict(self._document().get(workspace_id) or self._blank(workspace_id))

    def save(self, workspace_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            document = self._document()
            current = dict(document.get(workspace_id) or self._blank(workspace_id))
            current.update(values)
            current["workspace_id"] = workspace_id
            current["updated_at"] = to_utc_iso()
            document[workspace_id] = current
            _atomic_json(self.settings_path, document)
            return current

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
