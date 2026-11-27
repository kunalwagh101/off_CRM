import { Field } from "../components";
import type { AIProviderRow } from "../types";

export function connectedDraftProviders(rows: Pick<AIProviderRow, "name" | "connected" | "enabled">[], unavailable: boolean): string[] {
  return unavailable ? [] : rows.filter(row => row.connected && row.enabled).map(row => row.name);
}

export function canSubmitDraftMode(mode: string, providers: string[]): boolean {
  return mode === "local" || (mode === "connectors" && providers.length > 0);
}

/** Setup remains discoverable even before a campaign or draft exists. */
export function DraftProviderSetup() {
  return <p className="muted-copy">Local templates work without a model. To personalise drafts with AI, <a href="#connectors">open Connectors</a> and connect a provider that permits campaign data.</p>;
}

export function DraftGenerationMode({ mode, onChange, connected }: { mode: string; onChange: (value: string) => void; connected: string[] }) {
  return <>
    <Field label="Generation mode"><select value={mode} onChange={(event) => onChange(event.target.value)}>
      <option value="local">Local templates only</option>
      <option value="connectors" disabled={!connected.length}>Connectors ({connected.length} connected)</option>
    </select></Field>
    {connected.length ? <p className="muted-copy">Connected and enabled: {connected.join(", ")}. The server checks the current policy, model and quota before generation.</p> : null}
    {mode === "connectors" && !connected.length ? <p role="alert">AI generation is unavailable. Reload Connectors or explicitly select local templates.</p> : null}
    <p className="muted-copy"><a href="#connectors">Open Connectors</a> to manage this workspace’s providers and data policy. Connected providers must also permit campaign data and have available quota.</p>
    {mode === "connectors" ? <div className="form-note"><strong>Workspace data policy applies.</strong><span>Drafts use the same trust rules, scanner and egress log as other AI actions. Review the results before approval.</span></div> : null}
  </>;
}

export type GenerationResult = { generated: number; blocked: number; failures: Array<{ error?: string }> };
export function generationOutcome(result: GenerationResult): { tone: "error" | "info" | "success"; message: string } {
  const base = `${result.generated} drafts generated, ${result.blocked} blocked by audit`;
  if (result.failures.length) {
    const error = result.failures.find((failure) => failure.error)?.error;
    return { tone: "error", message: `${base}, ${result.failures.length} failed.${error ? ` ${error}` : " Open Connectors to check access and retry explicitly."}` };
  }
  return { tone: result.blocked ? "info" : "success", message: base };
}
