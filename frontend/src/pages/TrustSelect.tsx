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

/** Every level the server has (ai/tiers.py `DataPolicy`), lowest first.
 * "pseudonymous" was missing, so a restricted provider's form showed "Strict"
 * and saving it lowered what was sent without saying so (D-174). */
export const POLICY_ORDER = ["strict", "pseudonymous", "minimal", "standard", "full"] as const;

export function policyWord(value: string): string {
  return (
    {
      strict: "Strict",
      pseudonymous: "Pseudonymous",
      minimal: "Minimal",
      standard: "Standard",
      full: "Full access"
    }[value] ?? value
  );
}

type GrantRow = {
  name: string;
  connected: boolean;
  grant_offer?: boolean;
  grant_state?: string;
  override: { allow_above_ceiling?: boolean; reason?: string; data_policy?: string } | null;
};

/** Whether "Send full data anyway…" can change what is sent (DD-67). The
 * server decides, by the rule it refuses the grant with — blocked, lowered,
 * tier A, or no switched-on model at the provider's default (D-179) — so the
 * screen never offers what the server would refuse. */
export function canGrantFullData(row: GrantRow): boolean {
  return row.connected && Boolean(row.grant_offer) && !row.override?.allow_above_ceiling;
}

/** The card's line for the owner's grant. "Granted" is said only while it
 * decides what is sent, and a paused grant says why: the card used to say
 * "less than its default" of a provider blocked at its default. */
export function grantLine(row: GrantRow): string {
  if (!row.override?.allow_above_ceiling) return "";
  const reason = row.override.reason ?? "";
  // The screen grants full; one made for less through the API says so.
  const level = row.override.data_policy && row.override.data_policy !== "full" ? row.override.data_policy : "full";
  const what = `${level[0].toUpperCase()}${level.slice(1)} data`;
  switch (row.grant_state) {
    case "active":
      return `${what} granted by you${reason ? `: ${reason}` : ""}. Not for models trusted less than ${row.name}'s default.`;
    case "provider_lowered":
      return `${what} paused while you trust ${row.name} less than its default${reason ? `: ${reason}` : ""}.`;
    case "provider_blocked":
      return `${what} paused: ${row.name} is blocked, so it receives nothing.${reason ? ` ${reason}.` : ""}`;
    default:
      return `${what} paused: no model you switched on is trusted at ${row.name}'s default.${reason ? ` ${reason}.` : ""}`;
  }
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
