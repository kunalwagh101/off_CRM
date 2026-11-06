import { Field } from "../components";

export function DraftGenerationMode({ mode, onChange, connected }: { mode: string; onChange: (value: string) => void; connected: number }) {
  return <>
    <Field label="Generation mode"><select value={mode} onChange={(event) => onChange(event.target.value)}>
      <option value="local">Local templates only</option>
      <option value="connectors" disabled={!connected}>Connectors ({connected} connected)</option>
    </select></Field>
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
