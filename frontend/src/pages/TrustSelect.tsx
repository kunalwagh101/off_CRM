// Trust is the owner's to change, per provider and per model (S-06.02.33).
// Whether a change is a raise that needs a reason is the server's call
// (DD-65): these controls only send what was chosen.

export const TIER_ORDER = ["A", "B", "C", "D"] as const;

export const TRUST_WORD: Record<string, string> = {
  A: "Highest trust",
  B: "Default trust",
  C: "Restricted",
  D: "Blocked"
};

const RANK: Record<string, number> = { A: 3, B: 2, C: 1, D: 0 };

type GrantRow = {
  name: string;
  connected: boolean;
  effective_tier: string;
  default_tier?: string;
  trust_tier: string;
  policy_ceiling: string;
  grant_active?: boolean;
  override: { allow_above_ceiling?: boolean; reason?: string } | null;
};

/** Whether "Send full data anyway…" can change what is sent (DD-67). Not
 * offered where the server would refuse it: a blocked provider receives
 * nothing at any level, a lowered one would hold the grant paused, and tier
 * A already allows full. */
export function canGrantFullData(row: GrantRow): boolean {
  const defaultTier = row.default_tier ?? row.trust_tier;
  return (
    row.connected &&
    row.effective_tier !== "D" &&
    RANK[row.effective_tier] >= RANK[defaultTier] &&
    row.policy_ceiling !== "full" &&
    !row.override?.allow_above_ceiling
  );
}

/** The card's line for the owner's grant. "Granted" is said only while it
 * lifts what is sent: the card used to say so while nothing more was. */
export function grantLine(row: GrantRow): string {
  if (!row.override?.allow_above_ceiling) return "";
  const reason = row.override.reason ? `: ${row.override.reason}` : "";
  return row.grant_active
    ? `Full data granted by you${reason}. Not for models trusted less than ${row.name}'s default.`
    : `Full data paused while you trust ${row.name} less than its default${reason}.`;
}

/** Choosing a provider's default tier returns it to the default ("") rather
 * than storing a setting that merely repeats it. */
export function providerTierToSend(chosen: string, defaultTier: string): string {
  return chosen === defaultTier ? "" : chosen;
}

export function ProviderTrustSelect({
  name,
  value,
  defaultTier,
  disabled,
  onChange
}: {
  name: string;
  value: string;
  defaultTier: string;
  disabled?: boolean;
  onChange: (tier: string) => void;
}) {
  return (
    <select
      aria-label={`Trust for ${name}`}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(providerTierToSend(event.target.value, defaultTier))}
    >
      {TIER_ORDER.map((tier) => (
        <option key={tier} value={tier}>
          {TRUST_WORD[tier]}
          {tier === defaultTier ? " (default)" : ""}
        </option>
      ))}
    </select>
  );
}

/** "" follows the provider. A tier is the model's own setting: lower than the
 * provider, or past the cap from who built it — never above the provider,
 * which sees everything sent to it (DD-65, amended). */
export function ModelTrustSelect({
  modelId,
  providerName,
  value,
  disabled,
  onChange
}: {
  modelId: string;
  providerName: string;
  value: string;
  disabled?: boolean;
  onChange: (tier: string) => void;
}) {
  return (
    <select
      aria-label={`Trust for ${modelId} on ${providerName}`}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Same as provider</option>
      {TIER_ORDER.map((tier) => (
        <option key={tier} value={tier}>
          {TRUST_WORD[tier]}
        </option>
      ))}
    </select>
  );
}
