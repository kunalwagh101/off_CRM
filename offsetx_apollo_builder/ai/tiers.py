"""Trust tiers, data classes and data policies.

Two independent axes decide what a provider may receive:

* **Trust tier** — how much the owner trusts the company, derived from its
  jurisdiction and its published data-retention terms.
* **Data policy** — how much of the available material the payload builder is
  allowed to include for a given call.

The tier sets a *ceiling* on the policy.  The owner picks the policy under that
ceiling.  Raising a provider above its ceiling is possible but requires an
explicit, recorded override — it never happens by accident or by failover.

Owner's trust ordering (confirmed 2026-07-25):
    Europe  → highest trust
    USA     → default
    China   → below default
    routers/aggregators and anything unlisted → nothing
"""
from __future__ import annotations

from enum import Enum


class TrustTier(str, Enum):
    """How far a provider is trusted.  ``A`` is highest, ``D`` receives nothing."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"

    @property
    def label(self) -> str:
        return {
            TrustTier.A: "Highest trust",
            TrustTier.B: "Default trust",
            TrustTier.C: "Restricted",
            TrustTier.D: "Untrusted (receives nothing)",
        }[self]

    @property
    def rank(self) -> int:
        """Higher number means more trusted.  Used to forbid cross-tier failover."""
        return {TrustTier.D: 0, TrustTier.C: 1, TrustTier.B: 2, TrustTier.A: 3}[self]


class DataClass(str, Enum):
    """What kind of material a task needs to send out."""

    PUBLIC = "public"
    PERSON_PUBLIC = "person_public"
    CAMPAIGN = "campaign"
    INTERNAL = "internal"
    MAILBOX = "mailbox"

    @property
    def label(self) -> str:
        return {
            DataClass.PUBLIC: "Public, non-personal content",
            DataClass.PERSON_PUBLIC: "A person's public professional profile",
            DataClass.CAMPAIGN: "Template text and campaign drafts",
            DataClass.INTERNAL: "CRM records and internal notes",
            DataClass.MAILBOX: "Mailbox content (received mail, replies, threads)",
        }[self]


class DataPolicy(str, Enum):
    """How much the payload builder may include, from least to most."""

    STRICT = "strict"
    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"

    @property
    def rank(self) -> int:
        return {
            DataPolicy.STRICT: 0,
            DataPolicy.MINIMAL: 1,
            DataPolicy.STANDARD: 2,
            DataPolicy.FULL: 3,
        }[self]

    @property
    def label(self) -> str:
        return {
            DataPolicy.STRICT: "Strict — no names at all, category and role only",
            DataPolicy.MINIMAL: "Minimal — the person's public name, company and title",
            DataPolicy.STANDARD: "Standard — minimal plus your template and positioning",
            DataPolicy.FULL: "Full — no field restrictions (explicit opt-in)",
        }[self]

    @property
    def description(self) -> str:
        return {
            DataPolicy.STRICT: (
                "Sends the category, route and question structure only. No person "
                "is identifiable in the payload."
            ),
            DataPolicy.MINIMAL: (
                "Sends the person's public professional identity — name, company, "
                "title, public hook — so the model can personalise. Email addresses "
                "are replaced by tokens. Your own identity is limited to the "
                "positioning line."
            ),
            DataPolicy.STANDARD: (
                "Everything in Minimal, plus your template text and campaign "
                "instructions. Email addresses are still replaced by tokens."
            ),
            DataPolicy.FULL: (
                "No field restrictions. Real email addresses and internal notes can "
                "leave. Only choose this for a provider you trust with everything."
            ),
        }[self]


#: Ordered lowest → highest, for building UI dropdowns.
POLICY_ORDER: tuple[DataPolicy, ...] = (
    DataPolicy.STRICT,
    DataPolicy.MINIMAL,
    DataPolicy.STANDARD,
    DataPolicy.FULL,
)

#: Legacy ``data_policy`` values stored on provider profiles before the AI module
#: existed.  ``minimal`` kept its name but widened: it now permits the person's
#: public name so enrichment can personalise (owner's instruction, 2026-07-25).
#: The old behaviour — identity stripped entirely — is now called ``strict``.
LEGACY_POLICY_ALIASES: dict[str, DataPolicy] = {
    "minimal": DataPolicy.MINIMAL,
    "standard": DataPolicy.STANDARD,
    "full": DataPolicy.FULL,
}

#: Jurisdiction code → default tier.  Codes are ISO-3166 alpha-2 plus two
#: pseudo-codes: ``EU`` for the union as a whole and ``XX`` for router or
#: aggregator services whose real processing location is not knowable.
JURISDICTION_TIERS: dict[str, TrustTier] = {
    # Europe / EEA — highest trust
    "EU": TrustTier.A,
    "FR": TrustTier.A,
    "DE": TrustTier.A,
    "NL": TrustTier.A,
    "IE": TrustTier.A,
    "ES": TrustTier.A,
    "IT": TrustTier.A,
    "SE": TrustTier.A,
    "FI": TrustTier.A,
    "NO": TrustTier.A,
    "CH": TrustTier.A,
    # North America and allied — default trust
    "US": TrustTier.B,
    "CA": TrustTier.B,
    "GB": TrustTier.B,
    "AU": TrustTier.B,
    "NZ": TrustTier.B,
    "JP": TrustTier.B,
    "KR": TrustTier.B,
    "IL": TrustTier.B,
    "IN": TrustTier.B,
    # Restricted
    "CN": TrustTier.C,
    "HK": TrustTier.C,
    "RU": TrustTier.C,
    # Aggregators and routers — real processor unknown
    "XX": TrustTier.D,
}

#: Tier → the most permissive policy allowed without an explicit owner override.
TIER_POLICY_CEILING: dict[TrustTier, DataPolicy] = {
    TrustTier.A: DataPolicy.FULL,
    TrustTier.B: DataPolicy.STANDARD,
    TrustTier.C: DataPolicy.MINIMAL,
    TrustTier.D: DataPolicy.STRICT,
}

#: Tier → the policy a newly connected provider starts on.
TIER_DEFAULT_POLICY: dict[TrustTier, DataPolicy] = {
    TrustTier.A: DataPolicy.STANDARD,
    TrustTier.B: DataPolicy.STANDARD,
    TrustTier.C: DataPolicy.MINIMAL,
    TrustTier.D: DataPolicy.STRICT,
}

#: Tier → data classes it may receive without an explicit owner override.
#: ``MAILBOX`` is absent from every tier on purpose: reaching mailbox content
#: always needs the separate unlock described in :func:`tier_permits_class`.
TIER_PERMITTED_CLASSES: dict[TrustTier, frozenset[DataClass]] = {
    TrustTier.A: frozenset(
        {DataClass.PUBLIC, DataClass.PERSON_PUBLIC, DataClass.CAMPAIGN, DataClass.INTERNAL}
    ),
    TrustTier.B: frozenset({DataClass.PUBLIC, DataClass.PERSON_PUBLIC, DataClass.CAMPAIGN}),
    TrustTier.C: frozenset({DataClass.PUBLIC, DataClass.PERSON_PUBLIC}),
    TrustTier.D: frozenset(),
}

#: Typed confirmation required before any provider may receive mailbox content.
MAILBOX_UNLOCK_PHRASE = "ALLOW MAILBOX CONTENT TO LEAVE"


def coerce_tier(value: object, *, default: TrustTier | None = None) -> TrustTier:
    """Parse a tier from config or the database, failing closed on nonsense."""
    if isinstance(value, TrustTier):
        return value
    text = str(value or "").strip().upper()
    if text in {tier.value for tier in TrustTier}:
        return TrustTier(text)
    if default is not None:
        return default
    return TrustTier.D


def coerce_policy(value: object, *, default: DataPolicy = DataPolicy.STRICT) -> DataPolicy:
    """Parse a policy, accepting the pre-AI-module legacy spellings."""
    if isinstance(value, DataPolicy):
        return value
    text = str(value or "").strip().lower()
    if text in {policy.value for policy in DataPolicy}:
        return DataPolicy(text)
    if text in LEGACY_POLICY_ALIASES:
        return LEGACY_POLICY_ALIASES[text]
    return default


def coerce_data_class(value: object, *, default: DataClass = DataClass.INTERNAL) -> DataClass:
    """Parse a data class.  Unknown values fall back to the *most* restricted."""
    if isinstance(value, DataClass):
        return value
    text = str(value or "").strip().lower()
    if text in {item.value for item in DataClass}:
        return DataClass(text)
    return default


def tier_for_jurisdiction(
    jurisdiction: str,
    *,
    is_aggregator: bool = False,
    trains_on_input: bool = False,
) -> TrustTier:
    """Derive a default tier from the two axes the brief requires.

    Jurisdiction alone is not enough.  A provider in an otherwise trusted country
    that reserves the right to train on submitted content cannot hold restricted
    payloads, so it drops a tier.  Aggregators go straight to D because the real
    processor is whoever they route to that day.
    """
    if is_aggregator:
        return TrustTier.D
    base = JURISDICTION_TIERS.get(str(jurisdiction or "").strip().upper(), TrustTier.D)
    if trains_on_input and base.rank > TrustTier.C.rank:
        # Demote one step: acceptable country, unacceptable data terms.
        return TrustTier(
            {TrustTier.A: TrustTier.B, TrustTier.B: TrustTier.C}[base].value
        )
    return base


def policy_ceiling_for_tier(tier: TrustTier) -> DataPolicy:
    return TIER_POLICY_CEILING[tier]


def default_policy_for_tier(tier: TrustTier) -> DataPolicy:
    return TIER_DEFAULT_POLICY[tier]


def tier_permits_class(
    tier: TrustTier,
    data_class: DataClass,
    *,
    mailbox_unlocked: bool = False,
) -> bool:
    """Hard filter applied before cost, speed or availability are considered.

    Mailbox content is the one class no tier carries by default.  It becomes
    reachable only for tier A or B, and only once the owner has typed the unlock
    phrase for the workspace.
    """
    if data_class is DataClass.MAILBOX:
        return mailbox_unlocked and tier.rank >= TrustTier.B.rank
    return data_class in TIER_PERMITTED_CLASSES[tier]


def effective_policy(
    *,
    tier: TrustTier,
    requested: DataPolicy,
    override_allowed: bool = False,
) -> DataPolicy:
    """Clamp a requested policy to the tier ceiling unless overridden.

    Returning the clamped value rather than raising keeps the common case quiet:
    a tier C provider asked for ``standard`` simply runs at ``minimal``.  The
    broker records both values so the owner can see the clamp happened.
    """
    if override_allowed:
        return requested
    ceiling = policy_ceiling_for_tier(tier)
    return requested if requested.rank <= ceiling.rank else ceiling


def describe_tier(tier: TrustTier) -> dict[str, object]:
    """Shape used by the Connectors screen so tier rules are visible, not buried."""
    return {
        "tier": tier.value,
        "label": tier.label,
        "rank": tier.rank,
        "policy_ceiling": policy_ceiling_for_tier(tier).value,
        "default_policy": default_policy_for_tier(tier).value,
        "permitted_data_classes": sorted(
            item.value for item in TIER_PERMITTED_CLASSES[tier]
        ),
        "receives_nothing": tier is TrustTier.D,
    }
