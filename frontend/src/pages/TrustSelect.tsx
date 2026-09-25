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

/** "" follows the provider; a tier is the model's own setting, which wins. */
export function ModelTrustSelect({
  modelId,
  value,
  disabled,
  onChange
}: {
  modelId: string;
  value: string;
  disabled?: boolean;
  onChange: (tier: string) => void;
}) {
  return (
    <select
      aria-label={`Trust for ${modelId}`}
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
