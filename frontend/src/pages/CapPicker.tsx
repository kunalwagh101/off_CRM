import { useState } from "react";

export interface CapPreset {
  value: number;
  label: string;
}

// 0 is a real choice, not a blank: "the provider's own limit" for calls and
// "no cap" for spend, which is how the quota reads it (S-06.02.30).
export const CALL_CAP_PRESETS: CapPreset[] = [
  { value: 0, label: "Provider's own limit" },
  { value: 50, label: "50 a day" },
  { value: 200, label: "200 a day" },
  { value: 1000, label: "1,000 a day" }
];

export const SPEND_CAP_PRESETS: CapPreset[] = [
  { value: 0, label: "No cap" },
  { value: 1, label: "$1 a day" },
  { value: 5, label: "$5 a day" },
  { value: 20, label: "$20 a day" }
];

/** Which option a saved cap shows as: its preset, or "custom" for any other number. */
export function presetChoice(value: number, presets: CapPreset[]): string {
  return presets.some((preset) => preset.value === value) ? String(value) : "custom";
}

/**
 * A preset select, and a number box only when "Custom" is chosen. The value is
 * posted under `name` from a hidden input, so the form that holds this reads it
 * exactly as it read the plain number box before.
 */
export default function CapPicker({
  name,
  label,
  presets,
  defaultValue,
  step = 1
}: {
  name: string;
  label: string;
  presets: CapPreset[];
  defaultValue: number;
  step?: number;
}) {
  const [choice, setChoice] = useState(() => presetChoice(defaultValue, presets));
  const [custom, setCustom] = useState(String(defaultValue));
  const posted = choice === "custom" ? custom : choice;
  return (
    <>
      <select value={choice} onChange={(event) => setChoice(event.target.value)}>
        {presets.map((preset) => (
          <option key={preset.value} value={String(preset.value)}>
            {preset.label}
          </option>
        ))}
        <option value="custom">Custom…</option>
      </select>
      {choice === "custom" ? (
        <input
          type="number"
          min="0"
          step={step}
          aria-label={`Custom ${label.toLowerCase()}`}
          value={custom}
          onChange={(event) => setCustom(event.target.value)}
        />
      ) : null}
      <input type="hidden" name={name} value={posted} />
    </>
  );
}
