"""off_CRM AI module.

A self-contained package (see ``docs/AI_MODULE.md``) holding the provider
registry, trust-tier policy, egress broker and audit log.  The rest of the CRM
talks to it only through :class:`~offsetx_apollo_builder.ai.broker.EgressBroker`
and :class:`~offsetx_apollo_builder.ai.registry.ProviderRegistry`, so the module
can be lifted into its own repository without rewriting it.

Import rule enforced by ``tests/test_ai_egress_wall.py``: HTTP provider classes
and ``create_provider`` may only be reached from inside this package.  No other
part of off_CRM may talk to an AI provider directly.
"""
from __future__ import annotations

from .broker import (
    EgressBroker,
    EgressDecision,
    EgressResult,
    ImageResult,
    WorkspaceEgressSettings,
)
from .context import ContextLayer, TaskState, TemplateScore
from .errors import (
    AIModuleError,
    EgressBlocked,
    NoPermittedProvider,
    PolicyViolation,
    RegistryError,
)
from .log import EgressLog
from .modes import Branch, ModeRunner, PlanStep, RunMode, RunResult
from .payload import EgressRequest, PersonPublic, build_payload, describe_policy_for_class
from .quota import QuotaLimits, QuotaTracker
from .registry import ProviderEntry, ProviderOverride, ProviderRegistry, ResolvedProvider
from .scanner import ScanFinding, ScanReport, scan_payload
from .tiers import (
    MAILBOX_UNLOCK_PHRASE,
    POLICY_ORDER,
    DataClass,
    DataPolicy,
    TrustTier,
    coerce_data_class,
    coerce_policy,
    coerce_tier,
    default_policy_for_tier,
    describe_tier,
    policy_ceiling_for_tier,
    tier_for_jurisdiction,
    tier_permits_class,
)

__all__ = [
    "AIModuleError",
    "ContextLayer",
    "Branch",
    "DataClass",
    "DataPolicy",
    "EgressBlocked",
    "EgressBroker",
    "EgressDecision",
    "EgressLog",
    "EgressRequest",
    "EgressResult",
    "ImageResult",
    "ModeRunner",
    "PlanStep",
    "RunMode",
    "RunResult",
    "MAILBOX_UNLOCK_PHRASE",
    "NoPermittedProvider",
    "POLICY_ORDER",
    "PersonPublic",
    "PolicyViolation",
    "ProviderEntry",
    "ProviderOverride",
    "ProviderRegistry",
    "QuotaLimits",
    "QuotaTracker",
    "RegistryError",
    "ResolvedProvider",
    "ScanFinding",
    "ScanReport",
    "TaskState",
    "TemplateScore",
    "TrustTier",
    "WorkspaceEgressSettings",
    "build_payload",
    "coerce_data_class",
    "coerce_policy",
    "coerce_tier",
    "default_policy_for_tier",
    "describe_policy_for_class",
    "describe_tier",
    "policy_ceiling_for_tier",
    "scan_payload",
    "tier_for_jurisdiction",
    "tier_permits_class",
]
