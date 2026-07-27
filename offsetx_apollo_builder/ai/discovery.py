"""Model discovery.

Most OpenAI-compatible hosts expose ``GET /models``, listing everything the key
can reach.  One NVIDIA key reaches well over a hundred: Llama, DeepSeek, Qwen,
Microsoft Phi, Mistral, Nemotron, Gemma, Granite.  Hard-coding that list would go
stale within weeks — the exact failure the build brief warns about for public
"free LLM API" directories.

So off_CRM asks the provider for names, and **decides trust from its own config**
(``model_origin_rules``).  A discovered model whose name matches no rule is
untrusted and receives nothing until a rule is added for it.

Why this does not go through :class:`~offsetx_apollo_builder.ai.broker.EgressBroker`:
the broker exists to guard *payloads*, and discovery sends none — it is a GET
carrying only the API key.  It is still written to the egress log, so the log
remains a complete record of every time off_CRM contacted a provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from .registry import ProviderEntry, ProviderRegistry
from .tiers import TrustTier, coerce_tier, policy_ceiling_for_tier

#: Discovery should never hang a UI request.
DISCOVERY_TIMEOUT_SECONDS = 20

#: Guard against a provider returning a huge catalogue.
MAX_DISCOVERED_MODELS = 500


@dataclass(slots=True)
class DiscoveredModel:
    """One model the provider says it hosts, classified by our rules."""

    id: str
    origin: str = ""
    tier: str = TrustTier.D.value
    tier_cap: str = ""
    known: bool = False
    in_config: bool = False
    matched_prefix: str = ""

    @property
    def usable(self) -> bool:
        """Tier D receives nothing, so an unclassified model is not usable."""
        return self.known and self.tier != TrustTier.D.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "origin": self.origin,
            "tier": self.tier,
            "tier_cap": self.tier_cap,
            "known": self.known,
            "in_config": self.in_config,
            "matched_prefix": self.matched_prefix,
            "usable": self.usable,
            "policy_ceiling": policy_ceiling_for_tier(
                coerce_tier(self.tier, default=TrustTier.D)
            ).value,
        }


@dataclass(slots=True)
class DiscoveryResult:
    provider_id: str
    provider_name: str
    models: list[DiscoveredModel] = field(default_factory=list)
    source: str = "config"
    note: str = ""
    error: str = ""

    @property
    def unknown_count(self) -> int:
        return sum(1 for model in self.models if not model.known)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "models": [model.to_dict() for model in self.models],
            "source": self.source,
            "note": self.note,
            "error": self.error,
            "total": len(self.models),
            "usable": sum(1 for model in self.models if model.usable),
            "unknown": self.unknown_count,
        }


def _classify(
    registry: ProviderRegistry,
    entry: ProviderEntry,
    model_id: str,
) -> DiscoveredModel:
    """Config decides what a model is, never the provider's own description."""
    listed = entry.model(model_id)
    if listed is not None:
        tier = entry.tier_for_model(model_id)
        return DiscoveredModel(
            id=model_id,
            origin=listed.model_origin,
            tier=tier.value,
            tier_cap=listed.model_origin_tier_cap,
            known=True,
            in_config=True,
        )

    classification = registry.classify_model(model_id)
    if not classification["known"]:
        # Unmatched name: untrusted until a rule is written for it.
        return DiscoveredModel(id=model_id, tier=TrustTier.D.value, known=False)

    tier = entry.derived_tier
    cap = coerce_tier(classification["tier_cap"], default=TrustTier.D)
    if classification["tier_cap"] and cap.rank < tier.rank:
        tier = cap
    return DiscoveredModel(
        id=model_id,
        origin=classification["origin"],
        tier=tier.value,
        tier_cap=classification["tier_cap"],
        known=True,
        matched_prefix=classification["matched_prefix"],
    )


def _config_only(registry: ProviderRegistry, entry: ProviderEntry, note: str) -> DiscoveryResult:
    return DiscoveryResult(
        provider_id=entry.id,
        provider_name=entry.name,
        models=[_classify(registry, entry, model.id) for model in entry.models],
        source="config",
        note=note,
    )


def discover_models(
    registry: ProviderRegistry,
    provider_id: str,
    api_key: str,
    *,
    session: Any | None = None,
    logger: Any | None = None,
    workspace_id: str = "local",
) -> DiscoveryResult:
    """Ask the provider what it hosts, then classify against config rules.

    Degrades rather than failing: a provider with no catalogue endpoint, a bad
    key, or a network problem returns the config list with a note explaining
    what happened. The owner is never left with an empty screen and no reason.
    """
    entry = registry.require(provider_id)

    if entry.local_only:
        return _config_only(
            registry, entry, "Self-hosted server — the models listed here are the ones you run."
        )
    if not entry.base_url:
        return _config_only(registry, entry, "This provider has no catalogue endpoint.")
    if not api_key:
        return _config_only(
            registry,
            entry,
            "No API key stored yet. Add one to see everything this key can reach.",
        )

    url = f"{entry.base_url.rstrip('/')}/models"
    http = session or requests
    result = DiscoveryResult(provider_id=entry.id, provider_name=entry.name, source="provider")

    try:
        response = http.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=DISCOVERY_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - any transport failure degrades
        fallback = _config_only(registry, entry, "")
        fallback.error = f"Could not reach {entry.name}: {str(exc)[:200]}"
        fallback.note = "Showing the models listed in config instead."
        _log(logger, workspace_id, entry, "failed", fallback.error, 0)
        return fallback

    if not getattr(response, "ok", False):
        fallback = _config_only(registry, entry, "")
        status = getattr(response, "status_code", "?")
        fallback.error = (
            f"{entry.name} returned {status}. The key may be wrong, or this provider "
            "may not publish a model list."
        )
        fallback.note = "Showing the models listed in config instead."
        _log(logger, workspace_id, entry, "failed", fallback.error, 0)
        return fallback

    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        fallback = _config_only(registry, entry, "")
        fallback.error = f"{entry.name} returned something that is not JSON."
        _log(logger, workspace_id, entry, "failed", fallback.error, 0)
        return fallback

    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        fallback = _config_only(registry, entry, "")
        fallback.error = f"{entry.name} did not return a model list in the expected shape."
        _log(logger, workspace_id, entry, "failed", fallback.error, 0)
        return fallback

    seen: set[str] = set()
    for item in raw_models[:MAX_DISCOVERED_MODELS]:
        model_id = (
            str(item.get("id", "")).strip() if isinstance(item, dict) else str(item).strip()
        )
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        result.models.append(_classify(registry, entry, model_id))

    # Anything in config the provider did not mention still belongs on the list.
    for model in entry.models:
        if model.id not in seen:
            result.models.append(_classify(registry, entry, model.id))

    # Usable first, then unknown; alphabetical within each group.
    result.models.sort(key=lambda item: (not item.usable, item.id))

    if result.unknown_count:
        result.note = (
            f"{result.unknown_count} model(s) do not match any rule in "
            "config/providers.yaml, so they are untrusted and cannot be enabled. "
            "Add a model_origin_rules entry for them if you want to use them."
        )
    _log(logger, workspace_id, entry, "succeeded", "", len(result.models))
    return result


def _log(
    logger: Any | None,
    workspace_id: str,
    entry: ProviderEntry,
    status: str,
    error: str,
    count: int,
) -> None:
    """Record the contact in the egress log.

    Discovery sends no owner data, so the payload is deliberately empty — but it
    still appears in "What was sent", because the log is meant to be a complete
    record of every time off_CRM talked to a provider.
    """
    if logger is None:
        return
    try:
        logger(
            workspace_id=workspace_id,
            provider_id=entry.id,
            provider_name=entry.name,
            model_id="",
            jurisdiction=entry.jurisdiction,
            tier=entry.derived_tier.value,
            policy="none",
            data_class="none",
            task_type="model_discovery",
            status=status,
            error=error,
            findings=[],
            duration_ms=0,
            payload={},
            payload_summary={
                "fields": [],
                "note": "Model catalogue request. No owner data was sent.",
                "models_returned": count,
            },
            response_text="",
        )
    except Exception:  # noqa: BLE001 - logging must never break discovery
        pass
