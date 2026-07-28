"""Config-driven provider registry.

Everything the router needs to know about a provider lives in
``config/providers.yaml``.  Adding, removing or re-tiering a provider is a
config edit — never a code change (§4E).  Nothing here imports an HTTP client;
the registry only describes providers, the broker calls them.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .errors import RegistryError
from .tiers import (
    DataClass,
    DataPolicy,
    TrustTier,
    coerce_policy,
    coerce_tier,
    default_policy_for_tier,
    describe_tier,
    policy_ceiling_for_tier,
    tier_for_jurisdiction,
    tier_permits_class,
)

#: Where the registry is looked for, in order.
#:
#: 1. ``OFFSETX_PROVIDER_REGISTRY`` — explicit override, used on servers.
#: 2. ``<cwd>/config/providers.yaml`` — the file a human edits in a source
#:    checkout. This is the one the docs tell you to change.
#: 3. ``config/providers.yaml`` beside the package root — same file, found via
#:    the source tree rather than the working directory.
#: 4. ``providers.yaml`` shipped inside the package — the fallback for a
#:    pip-installed deployment with no source tree (Render, Docker).
#:
#: ``tests/test_ai_registry_packaging.py`` fails if 2 and 4 ever drift apart.
_PACKAGE_DIR = Path(__file__).resolve().parent
_SOURCE_ROOT = _PACKAGE_DIR.parents[1]
PACKAGED_REGISTRY_PATH = _PACKAGE_DIR / "providers.yaml"
SOURCE_REGISTRY_PATH = _SOURCE_ROOT / "config" / "providers.yaml"


def default_registry_path() -> Path:
    """First readable candidate, so a deploy cannot silently start with none."""
    override = os.environ.get("OFFSETX_PROVIDER_REGISTRY", "").strip()
    if override:
        return Path(override)
    for candidate in (
        Path.cwd() / "config" / "providers.yaml",
        SOURCE_REGISTRY_PATH,
        PACKAGED_REGISTRY_PATH,
    ):
        if candidate.exists():
            return candidate
    # Nothing found: return the packaged path so the error names something real.
    return PACKAGED_REGISTRY_PATH



#: Adapters the broker knows how to drive.  A registry entry naming anything
#: else is a config error, caught at load time rather than at call time.
SUPPORTED_ADAPTERS = {"openai", "anthropic", "openai_compatible", "template_engine_http"}


@dataclass(frozen=True, slots=True)
class OriginRule:
    """Classifies a model id by prefix.

    A host serves models built by other companies. The host's jurisdiction says
    nothing about who made the model, so provenance is decided here — from
    config — rather than from whatever the provider reports (§5.4).
    """

    prefix: str
    origin: str
    tier_cap: str = ""

    def matches(self, model_id: str) -> bool:
        return str(model_id).strip().lower().startswith(self.prefix.lower())

    def to_dict(self) -> dict[str, Any]:
        return {"prefix": self.prefix, "origin": self.origin, "tier_cap": self.tier_cap}


@dataclass(slots=True)
class ModelEntry:
    """One model offered by a provider."""

    id: str
    context_window: int = 0
    cost_per_1m_input_usd: float = 0.0
    cost_per_1m_output_usd: float = 0.0
    good_at: tuple[str, ...] = ()
    model_origin: str = ""
    model_origin_tier_cap: str = ""
    #: Extra body sent with every call to this model — max_tokens, temperature,
    #: and any provider-specific keys such as NVIDIA's reasoning_budget. Some
    #: models need these to answer properly: a reasoning model with no
    #: max_tokens can be cut off mid-thought by the provider's own default.
    request_options: dict[str, Any] = field(default_factory=dict)

    @property
    def is_free(self) -> bool:
        return self.cost_per_1m_input_usd == 0.0 and self.cost_per_1m_output_usd == 0.0

    @property
    def blended_cost(self) -> float:
        """Rough cost signal for ranking. Output is weighted higher because
        drafting produces far more output tokens than it consumes."""
        return self.cost_per_1m_input_usd + (self.cost_per_1m_output_usd * 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "context_window": self.context_window,
            "cost_per_1m_input_usd": self.cost_per_1m_input_usd,
            "cost_per_1m_output_usd": self.cost_per_1m_output_usd,
            "good_at": list(self.good_at),
            "is_free": self.is_free,
            "model_origin": self.model_origin,
            "model_origin_tier_cap": self.model_origin_tier_cap,
            "request_options": dict(self.request_options),
        }


@dataclass(frozen=True, slots=True)
class FreeTier:
    requests_per_minute: int = 0
    requests_per_day: int = 0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests_per_minute": self.requests_per_minute,
            "requests_per_day": self.requests_per_day,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ProviderEntry:
    """A provider as described by config, before any owner override is applied."""

    id: str
    name: str
    jurisdiction: str
    adapter: str
    base_url: str
    default_model: str
    models: tuple[ModelEntry, ...]
    retention: str
    trains_on_input: bool = False
    is_aggregator: bool = False
    local_only: bool = False
    self_hostable: bool = False
    self_host_note: str = ""
    #: True when the provider exposes GET /models, so "Find models" can
    #: list everything this key reaches rather than only what config names.
    supports_model_discovery: bool = False
    flag: str = ""
    key_url: str = ""
    key_placeholder: str = ""
    how_to_get: str = ""
    verified_on: str = ""
    free_tier: FreeTier | None = None
    configured_tier: TrustTier | None = None

    @property
    def derived_tier(self) -> TrustTier:
        """Tier from the two axes, unless config pins one explicitly."""
        if self.configured_tier is not None:
            return self.configured_tier
        return tier_for_jurisdiction(
            self.jurisdiction,
            is_aggregator=self.is_aggregator,
            trains_on_input=self.trains_on_input,
        )

    def model(self, model_id: str = "") -> ModelEntry | None:
        wanted = model_id or self.default_model
        return next((item for item in self.models if item.id == wanted), None)

    def tier_for_model(self, model_id: str = "") -> TrustTier:
        """Provenance caveat (§5.4): a trusted host serving a model built
        elsewhere is capped at the model's own tier when pass-through to the
        original developer is undocumented."""
        tier = self.derived_tier
        entry = self.model(model_id)
        if entry and entry.model_origin_tier_cap:
            cap = coerce_tier(entry.model_origin_tier_cap, default=TrustTier.D)
            if cap.rank < tier.rank:
                return cap
        return tier

    def to_dict(self) -> dict[str, Any]:
        tier = self.derived_tier
        return {
            "id": self.id,
            "name": self.name,
            "flag": self.flag,
            "jurisdiction": self.jurisdiction,
            "adapter": self.adapter,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "models": [item.to_dict() for item in self.models],
            "retention": self.retention,
            "trains_on_input": self.trains_on_input,
            "is_aggregator": self.is_aggregator,
            "local_only": self.local_only,
            "self_hostable": self.self_hostable,
            "self_host_note": self.self_host_note,
            "supports_model_discovery": self.supports_model_discovery,
            "key_url": self.key_url,
            "key_placeholder": self.key_placeholder,
            "how_to_get": self.how_to_get,
            "verified_on": self.verified_on,
            "free_tier": self.free_tier.to_dict() if self.free_tier else None,
            "trust_tier": tier.value,
            "trust_tier_source": "config" if self.configured_tier else "derived",
            **describe_tier(tier),
        }


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _load_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RegistryError(f"Provider registry not found at {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise RegistryError(
                "PyYAML is required to read a YAML provider registry. "
                "Install requirements.txt or use a .json registry instead."
            ) from exc
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise RegistryError(f"Provider registry is not valid YAML: {exc}") from exc
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"Provider registry is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryError("Provider registry must be a mapping at the top level")
    return payload


def _parse_entry(raw: dict[str, Any]) -> ProviderEntry:
    provider_id = str(raw.get("id", "")).strip()
    if not provider_id:
        raise RegistryError("Every provider entry needs an id")
    adapter = str(raw.get("adapter", "")).strip().lower()
    if adapter not in SUPPORTED_ADAPTERS:
        raise RegistryError(
            f"Provider {provider_id!r} uses unsupported adapter {adapter!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_ADAPTERS))}"
        )
    jurisdiction = str(raw.get("jurisdiction", "")).strip().upper()
    if not jurisdiction:
        raise RegistryError(
            f"Provider {provider_id!r} has no jurisdiction. Unknown jurisdiction "
            "cannot be treated as safe, so the entry is rejected."
        )
    retention = str(raw.get("retention", "")).strip()
    if not retention:
        raise RegistryError(
            f"Provider {provider_id!r} has no retention note. Unknown data terms "
            "cannot be treated as safe, so the entry is rejected."
        )

    models: list[ModelEntry] = []
    for item in raw.get("models") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        models.append(
            ModelEntry(
                id=model_id,
                context_window=_as_int(item.get("context_window")),
                cost_per_1m_input_usd=_as_float(item.get("cost_per_1m_input_usd")),
                cost_per_1m_output_usd=_as_float(item.get("cost_per_1m_output_usd")),
                good_at=tuple(str(tag) for tag in item.get("good_at") or ()),
                model_origin=str(item.get("model_origin", "")).strip().upper(),
                model_origin_tier_cap=str(item.get("model_origin_tier_cap", "")).strip().upper(),
                request_options=dict(item.get("request_options") or {}),
            )
        )
    if not models:
        raise RegistryError(f"Provider {provider_id!r} lists no models")

    default_model = str(raw.get("default_model", "")).strip() or models[0].id
    if not any(item.id == default_model for item in models):
        raise RegistryError(
            f"Provider {provider_id!r} default_model {default_model!r} is not in its models list"
        )

    free_raw = raw.get("free_tier")
    free_tier = None
    if isinstance(free_raw, dict):
        free_tier = FreeTier(
            requests_per_minute=_as_int(free_raw.get("requests_per_minute")),
            requests_per_day=_as_int(free_raw.get("requests_per_day")),
            notes=str(free_raw.get("notes", "")).strip(),
        )

    configured_tier = None
    if raw.get("trust_tier"):
        configured_tier = coerce_tier(raw.get("trust_tier"), default=TrustTier.D)

    return ProviderEntry(
        id=provider_id,
        name=str(raw.get("name", provider_id)).strip(),
        jurisdiction=jurisdiction,
        adapter=adapter,
        base_url=str(raw.get("base_url", "")).strip(),
        default_model=default_model,
        models=tuple(models),
        retention=retention,
        trains_on_input=bool(raw.get("trains_on_input", False)),
        is_aggregator=bool(raw.get("is_aggregator", False)),
        local_only=bool(raw.get("local_only", False)),
        self_hostable=bool(raw.get("self_hostable", False)),
        self_host_note=str(raw.get("self_host_note", "")).strip(),
        supports_model_discovery=bool(raw.get("supports_model_discovery", False)),
        flag=str(raw.get("flag", "")).strip(),
        key_url=str(raw.get("key_url", "")).strip(),
        key_placeholder=str(raw.get("key_placeholder", "")).strip(),
        how_to_get=str(raw.get("how_to_get", "")).strip(),
        verified_on=str(raw.get("verified_on", "")).strip(),
        free_tier=free_tier,
        configured_tier=configured_tier,
    )


@dataclass(slots=True)
class ProviderOverride:
    """An owner decision that departs from the config default.

    Overrides are stored per workspace, never in the shared config file, so one
    user raising a provider cannot change what another user's calls do.
    """

    provider_id: str
    trust_tier: TrustTier | None = None
    data_policy: DataPolicy | None = None
    allow_above_ceiling: bool = False
    reason: str = ""
    decided_by: str = ""
    decided_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "trust_tier": self.trust_tier.value if self.trust_tier else "",
            "data_policy": self.data_policy.value if self.data_policy else "",
            "allow_above_ceiling": self.allow_above_ceiling,
            "reason": self.reason,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderOverride":
        return cls(
            provider_id=str(payload.get("provider_id", "")),
            trust_tier=(
                coerce_tier(payload["trust_tier"]) if payload.get("trust_tier") else None
            ),
            data_policy=(
                coerce_policy(payload["data_policy"]) if payload.get("data_policy") else None
            ),
            allow_above_ceiling=bool(payload.get("allow_above_ceiling", False)),
            reason=str(payload.get("reason", "")),
            decided_by=str(payload.get("decided_by", "")),
            decided_at=str(payload.get("decided_at", "")),
        )


@dataclass(slots=True)
class ResolvedProvider:
    """A registry entry combined with the owner's overrides for one workspace."""

    entry: ProviderEntry
    model_id: str
    tier: TrustTier
    policy: DataPolicy
    policy_ceiling: DataPolicy
    override: ProviderOverride | None = None

    @property
    def id(self) -> str:
        return self.entry.id

    @property
    def name(self) -> str:
        return self.entry.name

    @property
    def model(self) -> ModelEntry | None:
        return self.entry.model(self.model_id)

    @property
    def cost(self) -> float:
        model = self.model
        return model.blended_cost if model else 0.0

    def permits(self, data_class: DataClass, *, mailbox_unlocked: bool = False) -> bool:
        return tier_permits_class(self.tier, data_class, mailbox_unlocked=mailbox_unlocked)

    def to_dict(self) -> dict[str, Any]:
        payload = self.entry.to_dict()
        payload.update(
            {
                "model_id": self.model_id,
                "effective_tier": self.tier.value,
                "effective_policy": self.policy.value,
                "policy_ceiling": self.policy_ceiling.value,
                "override": self.override.to_dict() if self.override else None,
                "cost_signal": self.cost,
            }
        )
        return payload


class ProviderRegistry:
    """Reads the config file and resolves providers for a workspace.

    Thread-safe and cached by file mtime, so an owner editing the YAML sees the
    change without restarting the app.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_registry_path()
        self._lock = threading.RLock()
        self._entries: dict[str, ProviderEntry] = {}
        self._defaults: dict[str, Any] = {}
        self._origin_rules: tuple[OriginRule, ...] = ()
        self._mtime: float = -1.0

    def _refresh(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError as exc:
            raise RegistryError(f"Provider registry not readable at {self.path}") from exc
        if mtime == self._mtime and self._entries:
            return
        document = _load_document(self.path)
        raw_providers = document.get("providers")
        if not isinstance(raw_providers, list) or not raw_providers:
            raise RegistryError("Provider registry must contain a non-empty 'providers' list")
        entries: dict[str, ProviderEntry] = {}
        for raw in raw_providers:
            if not isinstance(raw, dict):
                raise RegistryError("Each provider entry must be a mapping")
            entry = _parse_entry(raw)
            if entry.id in entries:
                raise RegistryError(f"Duplicate provider id {entry.id!r} in registry")
            entries[entry.id] = entry
        self._entries = entries
        self._defaults = dict(document.get("defaults") or {})
        rules: list[OriginRule] = []
        for raw_rule in document.get("model_origin_rules") or []:
            if not isinstance(raw_rule, dict):
                continue
            prefix = str(raw_rule.get("prefix", "")).strip()
            origin = str(raw_rule.get("origin", "")).strip().upper()
            if not prefix or not origin:
                continue
            rules.append(
                OriginRule(
                    prefix=prefix,
                    origin=origin,
                    tier_cap=str(raw_rule.get("tier_cap", "")).strip().upper(),
                )
            )
        # Longest prefix first: 'meta-llama/' must beat 'meta/'.
        self._origin_rules = tuple(sorted(rules, key=lambda r: -len(r.prefix)))
        self._mtime = mtime

    def all(self) -> list[ProviderEntry]:
        with self._lock:
            self._refresh()
            return sorted(self._entries.values(), key=lambda item: (-item.derived_tier.rank, item.name))

    def get(self, provider_id: str) -> ProviderEntry | None:
        with self._lock:
            self._refresh()
            return self._entries.get(str(provider_id))

    def classify_model(self, model_id: str) -> dict[str, Any]:
        """Work out who built a model, from config rules only.

        Used for models discovered live from a provider's catalogue, which are
        not listed in this file. A model matching no rule is ``known: False`` —
        it is untrusted and receives nothing until a rule is added for it.
        Unknown is never treated as safe (§5.4, §5.5.7).
        """
        with self._lock:
            self._refresh()
            rules = self._origin_rules
        cleaned = str(model_id or "").strip()
        for rule in rules:
            if rule.matches(cleaned):
                return {
                    "model_id": cleaned,
                    "origin": rule.origin,
                    "tier_cap": rule.tier_cap,
                    "known": True,
                    "matched_prefix": rule.prefix,
                }
        return {
            "model_id": cleaned,
            "origin": "",
            "tier_cap": TrustTier.D.value,
            "known": False,
            "matched_prefix": "",
        }

    def origin_rules(self) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh()
            return [rule.to_dict() for rule in self._origin_rules]

    def require(self, provider_id: str) -> ProviderEntry:
        entry = self.get(provider_id)
        if entry is None:
            # Default-deny: an unlisted provider is untrusted, not assumed fine.
            raise RegistryError(
                f"Provider {provider_id!r} is not in the registry. Unlisted providers "
                "are untrusted and receive nothing. Add it to config/providers.yaml first."
            )
        return entry

    def resolve(
        self,
        provider_id: str,
        *,
        model_id: str = "",
        requested_policy: DataPolicy | str | None = None,
        override: ProviderOverride | None = None,
    ) -> ResolvedProvider:
        """Combine config, model provenance and owner override into one decision."""
        entry = self.require(provider_id)
        chosen_model = model_id or entry.default_model

        if entry.model(chosen_model) is not None:
            # Listed in config: its declared origin and cap win.
            tier = entry.tier_for_model(chosen_model)
        else:
            # Discovered from the provider's live catalogue. Config rules decide
            # what it is, never the provider — and an unmatched name is untrusted.
            classification = self.classify_model(chosen_model)
            tier = entry.derived_tier
            cap = coerce_tier(classification["tier_cap"], default=TrustTier.D)
            if classification["tier_cap"] and cap.rank < tier.rank:
                tier = cap
            if not classification["known"]:
                tier = TrustTier.D

        if override and override.trust_tier is not None:
            tier = override.trust_tier

        ceiling = policy_ceiling_for_tier(tier)
        if requested_policy is None:
            policy = (
                override.data_policy
                if override and override.data_policy is not None
                else default_policy_for_tier(tier)
            )
        else:
            policy = coerce_policy(requested_policy, default=default_policy_for_tier(tier))

        allow_above = bool(override and override.allow_above_ceiling)
        if not allow_above and policy.rank > ceiling.rank:
            policy = ceiling

        return ResolvedProvider(
            entry=entry,
            model_id=chosen_model,
            tier=tier,
            policy=policy,
            policy_ceiling=ceiling,
            override=override,
        )

    def candidates_for(
        self,
        data_class: DataClass,
        *,
        enabled_ids: Iterable[str],
        overrides: dict[str, ProviderOverride] | None = None,
        mailbox_unlocked: bool = False,
        task_tags: Iterable[str] = (),
        prefer_free: bool = True,
        enabled_models: dict[str, tuple[str, ...]] | None = None,
        policy_by_provider: dict[str, Any] | None = None,
    ) -> tuple[list[ResolvedProvider], list[dict[str, Any]]]:
        """Return every permitted **provider + model** pair, cheapest first.

        A key unlocks many models, and a model carries its own trust tier: one
        NVIDIA key reaches Llama at tier B and DeepSeek at tier C. So the unit of
        routing is a provider *and* a model, not a provider alone.

        The tier filter runs *first* and cost never overrides it (§4E rule c).
        The second return value explains every rejection, so the UI can tell the
        owner why a model they enabled did not run.
        """
        overrides = overrides or {}
        enabled_models = enabled_models or {}
        policy_by_provider = policy_by_provider or {}
        wanted_tags = {str(tag).strip().lower() for tag in task_tags if str(tag).strip()}
        permitted: list[ResolvedProvider] = []
        rejected: list[dict[str, Any]] = []

        for provider_id in enabled_ids:
            entry = self.get(provider_id)
            if entry is None:
                rejected.append(
                    {
                        "provider_id": provider_id,
                        "reason": "not_in_registry",
                        "detail": (
                            f"Provider {provider_id!r} is not in the registry. Unlisted "
                            "providers are untrusted and receive nothing."
                        ),
                    }
                )
                continue

            # No explicit choice means the provider's default model only.
            model_ids = tuple(enabled_models.get(provider_id) or ()) or (entry.default_model,)
            for model_id in model_ids:
                try:
                    resolved = self.resolve(
                        provider_id,
                        model_id=model_id,
                        requested_policy=policy_by_provider.get(provider_id),
                        override=overrides.get(provider_id),
                    )
                except RegistryError as exc:
                    rejected.append(
                        {
                            "provider_id": provider_id,
                            "model_id": model_id,
                            "reason": "model_not_in_registry",
                            "detail": str(exc),
                        }
                    )
                    continue
                if not resolved.permits(data_class, mailbox_unlocked=mailbox_unlocked):
                    rejected.append(
                        {
                            "provider_id": provider_id,
                            "model_id": model_id,
                            "reason": "tier_forbids_data_class",
                            "detail": (
                                f"{resolved.name} running {model_id} is tier "
                                f"{resolved.tier.value} ({resolved.tier.label}) and may not "
                                f"receive {data_class.value} data."
                            ),
                            "tier": resolved.tier.value,
                            "data_class": data_class.value,
                        }
                    )
                    continue
                permitted.append(resolved)

        def sort_key(item: ResolvedProvider) -> tuple[int, int, float, str]:
            model = item.model
            tag_match = 0
            if wanted_tags and model:
                tag_match = 0 if wanted_tags & {tag.lower() for tag in model.good_at} else 1
            free_first = 0 if (prefer_free and model and model.is_free) else 1
            return (tag_match, free_first, item.cost, item.name)

        permitted.sort(key=sort_key)
        return permitted, rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "defaults": dict(self._defaults),
            "providers": [entry.to_dict() for entry in self.all()],
        }
