"""The single egress gate.

Every outbound AI provider call in off_CRM goes through :meth:`EgressBroker.call`
— enrichment, personalisation, chat, summarisation, parsing fallback, code work,
orchestration.  No other module talks to a provider (§5.5.1), and
``tests/test_ai_egress_wall.py`` fails the build if one starts to.

Order of operations, and the order matters:

1. **Tier filter.** Providers that may not hold this data class are removed
   first.  Cost, speed and availability are only considered afterwards, so a
   cheap model can never win a task it is not allowed to see.
2. **Quota filter.** Providers with no budget left are skipped, not called.
3. **Payload construction.** Built from empty against the resolved policy.
4. **Pre-flight scan.** A hit blocks the call and raises.
5. **Call and log.** Every attempt is recorded with what was sent.

Failover walks the remaining candidates *within the same trust tier only*.  A
task carrying restricted data fails closed rather than dropping to a lower tier.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

# The provider SDK/HTTP adapters are imported here and nowhere else outside this
# package. This import is the structural enforcement of §5.5.1.
from ..outreach.providers import (
    ProviderError,
    create_provider,
    normalize_generation_output,
)
from ..outreach.models import ProviderConfig
from .errors import EgressBlocked, NoPermittedProvider, PolicyViolation, RegistryError
from .payload import EgressRequest, build_payload, payload_summary
from .quota import QuotaLimits, QuotaTracker
from .registry import ProviderOverride, ProviderRegistry, ResolvedProvider
from .scanner import scan_payload
from .tiers import (
    MAILBOX_UNLOCK_PHRASE,
    DataClass,
    DataPolicy,
    TrustTier,
)

#: Task types that may never reach a provider at all, whatever the tier.
#: Nothing currently maps to this, but the hook exists so a future feature has an
#: obvious place to declare "this is local-only".
LOCAL_ONLY_TASKS: frozenset[str] = frozenset()


@dataclass(slots=True)
class WorkspaceEgressSettings:
    """Per-workspace egress configuration.

    off_CRM is multi-user, so these are never global: one user raising a
    provider above its ceiling cannot change what another user's calls send.
    """

    workspace_id: str = "local"
    enabled_provider_ids: tuple[str, ...] = ()
    overrides: dict[str, ProviderOverride] = field(default_factory=dict)
    quota_limits: dict[str, QuotaLimits] = field(default_factory=dict)
    owner_domains: tuple[str, ...] = ()
    owner_addresses: tuple[str, ...] = ()
    positioning_line: str = ""
    mailbox_unlock_phrase: str = ""
    default_policy_by_provider: dict[str, DataPolicy] = field(default_factory=dict)

    @property
    def mailbox_unlocked(self) -> bool:
        """Mailbox egress needs the exact phrase, matching the pattern the CRM
        already uses for enabling live Gmail sending."""
        return self.mailbox_unlock_phrase.strip() == MAILBOX_UNLOCK_PHRASE


@dataclass(slots=True)
class EgressDecision:
    """Why the broker chose (or refused) a provider — recorded for the log."""

    provider_id: str
    provider_name: str
    model_id: str
    tier: str
    policy: str
    data_class: str
    permitted: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "tier": self.tier,
            "policy": self.policy,
            "data_class": self.data_class,
            "permitted": self.permitted,
            "reason": self.reason,
        }


@dataclass(slots=True)
class EgressResult:
    text: str
    provider_id: str
    provider_name: str
    model_id: str
    tier: str
    policy: str
    data_class: str
    duration_ms: int
    payload_fields: list[str]
    attempts: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    log_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "tier": self.tier,
            "policy": self.policy,
            "data_class": self.data_class,
            "duration_ms": self.duration_ms,
            "payload_fields": self.payload_fields,
            "attempts": self.attempts,
            "rejected": self.rejected,
            "log_id": self.log_id,
        }


#: ``(provider_id) -> api_key``.  Returning "" means "no credential stored".
CredentialResolver = Callable[[str], str]

#: Called once per outbound attempt with the full record.  The API layer points
#: this at the egress log so the owner can inspect exactly what was sent.
EgressLogger = Callable[..., str]


class EgressBroker:
    """The only object in off_CRM that may call an AI provider."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        credential_resolver: CredentialResolver,
        quota: QuotaTracker | None = None,
        logger: EgressLogger | None = None,
        timeout_seconds: int = 60,
        failure_threshold: int = 2,
        cooldown_seconds: int = 60,
    ) -> None:
        self.registry = registry
        self.credential_resolver = credential_resolver
        self.quota = quota
        self.logger = logger
        self.timeout_seconds = timeout_seconds
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1, cooldown_seconds)
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    # ── candidate selection ─────────────────────────────────────────────────

    def plan(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        provider_id: str = "",
    ) -> tuple[list[ResolvedProvider], list[dict[str, Any]]]:
        """Resolve the ordered candidate list without calling anything.

        Exposed separately so the UI can show *before* a run which model would
        be used and which were filtered out, and why.
        """
        if request.data_class is DataClass.MAILBOX and not settings.mailbox_unlocked:
            raise PolicyViolation(
                "Mailbox content cannot be sent to any AI provider. No model has access "
                "to the mailbox unless you explicitly unlock it for this workspace.",
                data_class=request.data_class.value,
            )
        if request.task_type in LOCAL_ONLY_TASKS:
            raise PolicyViolation(
                f"Task {request.task_type!r} runs locally and never reaches a provider.",
                data_class=request.data_class.value,
            )

        enabled = (provider_id,) if provider_id else settings.enabled_provider_ids
        if not enabled:
            raise NoPermittedProvider(
                "No AI provider is connected for this workspace. Open Connectors and "
                "add one before running AI work."
            )

        permitted, rejected = self.registry.candidates_for(
            request.data_class,
            enabled_ids=enabled,
            overrides=settings.overrides,
            mailbox_unlocked=settings.mailbox_unlocked,
            task_tags=request.task_tags,
        )

        # Apply the workspace's chosen policy per provider, clamped by tier.
        adjusted: list[ResolvedProvider] = []
        for candidate in permitted:
            requested = settings.default_policy_by_provider.get(candidate.id)
            if requested is None:
                adjusted.append(candidate)
                continue
            try:
                adjusted.append(
                    self.registry.resolve(
                        candidate.id,
                        model_id=candidate.model_id,
                        requested_policy=requested,
                        override=settings.overrides.get(candidate.id),
                    )
                )
            except RegistryError:
                adjusted.append(candidate)

        # Quota filter: skip providers with nothing left rather than calling
        # them and eating a 429.
        with_budget: list[ResolvedProvider] = []
        for candidate in adjusted:
            limits = settings.quota_limits.get(candidate.id)
            if self.quota is None or limits is None or limits.unlimited:
                with_budget.append(candidate)
                continue
            allowed, reason = self.quota.check(candidate.id, limits)
            if allowed:
                with_budget.append(candidate)
            else:
                rejected.append(
                    {
                        "provider_id": candidate.id,
                        "reason": "quota_exhausted",
                        "detail": f"{candidate.name}: {reason}",
                    }
                )

        if not with_budget:
            raise NoPermittedProvider(
                self._explain_empty(request.data_class, rejected), considered=rejected
            )

        # Never fail over across a tier boundary: keep only the highest tier
        # present, so an error cannot silently demote restricted data.
        best_rank = max(candidate.tier.rank for candidate in with_budget)
        same_tier = [c for c in with_budget if c.tier.rank == best_rank]
        running_tier = same_tier[0].tier.value
        for candidate in with_budget:
            if candidate.tier.rank != best_rank:
                rejected.append(
                    {
                        "provider_id": candidate.id,
                        "reason": "lower_tier_not_used_for_failover",
                        "detail": (
                            f"{candidate.name} is tier {candidate.tier.value}; this task is "
                            f"running at tier {running_tier}. off_CRM never fails over to a "
                            "lower trust tier."
                        ),
                    }
                )
        return same_tier, rejected

    @staticmethod
    def _explain_empty(data_class: DataClass, rejected: list[dict[str, Any]]) -> str:
        if not rejected:
            return (
                f"No connected provider may handle {data_class.label.lower()}. "
                "Connect one whose trust tier permits it."
            )
        lines = "; ".join(str(item.get("detail") or item.get("reason")) for item in rejected[:4])
        return (
            f"No connected provider may handle {data_class.label.lower()}. {lines}. "
            "off_CRM stops rather than sending this to a provider that is not permitted."
        )

    # ── the gate ────────────────────────────────────────────────────────────

    def call(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        system_prompt: str,
        provider_id: str = "",
        expect_json: bool = False,
    ) -> EgressResult:
        candidates, rejected = self.plan(request, settings, provider_id=provider_id)
        attempts: list[dict[str, Any]] = []
        now = time.monotonic()

        for candidate in candidates:
            with self._lock:
                open_until = self._open_until.get(candidate.id, 0.0)
            if open_until > now:
                attempts.append(
                    {
                        "provider_id": candidate.id,
                        "status": "circuit_open",
                        "detail": "Recent failures; cooling down.",
                    }
                )
                continue

            # 3. Construct — from empty, against this provider's resolved policy.
            payload = build_payload(request, candidate.policy)

            # 4. Scan — block and alert, never silently redact.
            report = scan_payload(
                payload,
                policy=candidate.policy,
                owner_domains=settings.owner_domains,
                owner_addresses=settings.owner_addresses,
                allow_addresses=candidate.policy is DataPolicy.FULL,
            )
            if not report.clean:
                self._log(
                    settings=settings,
                    candidate=candidate,
                    request=request,
                    payload=payload,
                    status="blocked",
                    error=report.summary(),
                    findings=[item.to_dict() for item in report.findings],
                    duration_ms=0,
                    response_text="",
                )
                raise EgressBlocked(
                    (
                        f"Blocked before sending to {candidate.name}. "
                        f"{report.findings[0].detail} "
                        "Nothing was sent. This is a payload-construction bug worth fixing, "
                        "not something to redact and retry."
                    ),
                    findings=[item.to_dict() for item in report.findings],
                )

            # 5. Call.
            started = time.monotonic()
            status = "succeeded"
            error = ""
            text = ""
            try:
                provider = self._instantiate(candidate)
                raw = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=json.dumps(payload, ensure_ascii=False),
                )
                text = normalize_generation_output(raw) if expect_json else str(raw)
            except Exception as exc:  # noqa: BLE001 - recorded, then failover
                status = "failed"
                error = str(exc)[:500]
            duration_ms = int((time.monotonic() - started) * 1000)

            if self.quota is not None:
                self.quota.record(
                    candidate.id,
                    spend_usd=0.0,
                    rate_limited="429" in error,
                )

            log_id = self._log(
                settings=settings,
                candidate=candidate,
                request=request,
                payload=payload,
                status=status,
                error=error,
                findings=[],
                duration_ms=duration_ms,
                response_text=text,
            )

            if status == "failed":
                with self._lock:
                    failures = self._failures.get(candidate.id, 0) + 1
                    self._failures[candidate.id] = failures
                    if failures >= self.failure_threshold:
                        self._open_until[candidate.id] = time.monotonic() + self.cooldown_seconds
                attempts.append(
                    {"provider_id": candidate.id, "status": "failed", "detail": error}
                )
                continue

            with self._lock:
                self._failures[candidate.id] = 0
                self._open_until.pop(candidate.id, None)
            attempts.append({"provider_id": candidate.id, "status": "used"})

            return EgressResult(
                text=text,
                provider_id=candidate.id,
                provider_name=candidate.name,
                model_id=candidate.model_id,
                tier=candidate.tier.value,
                policy=candidate.policy.value,
                data_class=request.data_class.value,
                duration_ms=duration_ms,
                payload_fields=sorted(payload.keys()),
                attempts=attempts,
                rejected=rejected,
                log_id=log_id,
            )

        detail = "; ".join(
            f"{item['provider_id']}: {item.get('detail', item['status'])}" for item in attempts
        )
        raise NoPermittedProvider(
            f"Every permitted provider failed for this task. {detail}",
            considered=rejected + attempts,
        )

    # ── internals ───────────────────────────────────────────────────────────

    def _instantiate(self, candidate: ResolvedProvider) -> Any:
        entry = candidate.entry
        api_key = self.credential_resolver(candidate.id)
        env_name = f"OFFSETX_AI_{candidate.id.upper()}_KEY"
        config = ProviderConfig(
            provider_type=entry.adapter,
            model=candidate.model_id,
            api_key_env=env_name if api_key else "",
            base_url=entry.base_url,
            timeout_seconds=self.timeout_seconds,
            extra={},
        )
        if api_key:
            return create_provider(config, environ={env_name: api_key})
        if entry.local_only:
            # A local Ollama-style server needs no key.
            return create_provider(config, environ={})
        raise ProviderError(
            f"No API key stored for {entry.name}. Add one in Connectors before using it."
        )

    def _log(
        self,
        *,
        settings: WorkspaceEgressSettings,
        candidate: ResolvedProvider,
        request: EgressRequest,
        payload: dict[str, Any],
        status: str,
        error: str,
        findings: list[dict[str, Any]],
        duration_ms: int,
        response_text: str,
    ) -> str:
        if self.logger is None:
            return ""
        try:
            return self.logger(
                workspace_id=settings.workspace_id,
                provider_id=candidate.id,
                provider_name=candidate.name,
                model_id=candidate.model_id,
                jurisdiction=candidate.entry.jurisdiction,
                tier=candidate.tier.value,
                policy=candidate.policy.value,
                data_class=request.data_class.value,
                task_type=request.task_type,
                status=status,
                error=error,
                findings=findings,
                duration_ms=duration_ms,
                payload=payload,
                payload_summary=payload_summary(payload),
                response_text=response_text,
            )
        except Exception:  # noqa: BLE001 - logging must never break a call
            return ""

    def usage(self, settings: WorkspaceEgressSettings) -> list[dict[str, Any]]:
        """Usage against limits for every enabled provider, for the UI."""
        if self.quota is None:
            return []
        rows: list[dict[str, Any]] = []
        for provider_id in settings.enabled_provider_ids:
            limits = settings.quota_limits.get(provider_id)
            entry = self.registry.get(provider_id)
            if limits is None and entry is not None and entry.free_tier is not None:
                limits = QuotaLimits(
                    requests_per_minute=entry.free_tier.requests_per_minute,
                    requests_per_day=entry.free_tier.requests_per_day,
                )
            rows.append(self.quota.usage(provider_id, limits or QuotaLimits()))
        return rows
