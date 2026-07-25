import { useState } from "react";
import { api } from "../api";
import { Badge, Button, StatePanel } from "../components";
import { useApp } from "../context";
import type { AIProviderRow, AIRunResult, AIModesPayload } from "../types";

/**
 * The two non-chat run modes, plus the model strip that both share.
 *
 * UX intent: one obvious action per screen. Compare is "ask everyone, read the
 * answers". Plan is "let a lead model break it up, watch the steps". Neither
 * screen asks the user to understand routing — the consequences of each choice
 * are written out in plain words next to the control.
 */

const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };
const TIER_WORD: Record<string, string> = {
  A: "Highest trust",
  B: "Default trust",
  C: "Restricted",
  D: "Blocked"
};

/** Shows every connected model and how close each is to its limit. */
export function ModelStrip({
  providers,
  modes,
  compact = false
}: {
  providers: AIProviderRow[];
  modes?: AIModesPayload | null;
  compact?: boolean;
}) {
  const connected = providers.filter((row) => row.connected && row.enabled);
  const usageById = new Map((modes?.usage ?? []).map((row) => [row.provider_id, row]));

  if (connected.length === 0) {
    return (
      <div className="model-strip model-strip-empty">
        <p>No AI connected yet.</p>
        <Button onClick={() => (window.location.hash = "connectors")}>Connect one</Button>
      </div>
    );
  }

  return (
    <div className={compact ? "model-strip model-strip-compact" : "model-strip"}>
      <p className="model-strip-count">
        <strong>{connected.length}</strong> AI{connected.length === 1 ? "" : "s"} connected
      </p>
      <ul className="model-chips">
        {connected.map((row) => {
          const usage = usageById.get(row.id) ?? row.usage ?? null;
          const limit = usage?.day_limit ?? 0;
          const used = usage?.day_used ?? 0;
          const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
          const near = limit > 0 && pct >= 80;
          const out = Boolean(usage?.exhausted);

          return (
            <li
              key={row.id}
              className={out ? "model-chip model-chip-out" : near ? "model-chip model-chip-near" : "model-chip"}
            >
              <span className="model-chip-head">
                <span aria-hidden="true">{row.flag}</span>
                <strong>{row.name}</strong>
                <Badge tone={TIER_TONE[row.effective_tier] ?? "neutral"}>{row.effective_tier}</Badge>
              </span>
              <span className="model-chip-model">{row.model_id}</span>

              {limit > 0 ? (
                <>
                  <span
                    className="model-meter"
                    role="progressbar"
                    aria-valuenow={used}
                    aria-valuemin={0}
                    aria-valuemax={limit}
                    aria-label={`${row.name} daily usage`}
                  >
                    <span className="model-meter-fill" style={{ width: `${pct}%` }} />
                  </span>
                  <span className="model-chip-usage">
                    {out ? "Out of calls today" : `${used} of ${limit} calls today`}
                  </span>
                </>
              ) : (
                <span className="model-chip-usage">{used} calls today · no set limit</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Ask every permitted model the same thing, read the answers side by side. */
export function CompareView({ providers, modes }: { providers: AIProviderRow[]; modes: AIModesPayload | null }) {
  const { notify } = useApp();
  const [instructions, setInstructions] = useState("");
  const [dataClass, setDataClass] = useState<"public" | "person_public" | "campaign">("public");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AIRunResult | null>(null);
  const [kept, setKept] = useState("");

  const mode = modes?.modes.find((item) => item.value === "compare");
  const blocked = mode && !mode.available;

  async function run() {
    if (!instructions.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      setResult(
        await api.post<AIRunResult>("/ai/run", {
          mode: "compare",
          data_class: dataClass,
          instructions: instructions.trim(),
          task_type: "compare_run"
        })
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not run", "error");
    } finally {
      setRunning(false);
    }
  }

  const answers = result?.branches ?? [];
  const ok = answers.filter((item) => item.ok);

  return (
    <div className="studio">
      <ModelStrip providers={providers} modes={modes} compact />

      {blocked ? (
        <StatePanel
          title="Compare needs at least two models"
          description={mode?.blocked_reason ?? ""}
          action={<Button onClick={() => (window.location.hash = "connectors")}>Open Connectors</Button>}
        />
      ) : null}

      <div className="studio-composer">
        <label className="studio-field">
          <span>What do you want them all to do?</span>
          <textarea
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            rows={4}
            placeholder="Write a first-contact email opening for a European customs consultancy."
            disabled={running}
          />
        </label>

        <div className="studio-controls">
          <label className="ai-control">
            <span>Information needed</span>
            <select
              value={dataClass}
              onChange={(event) => setDataClass(event.target.value as typeof dataClass)}
            >
              <option value="public">Nothing personal — every model can answer</option>
              <option value="person_public">A person's public details</option>
              <option value="campaign">My template and campaign notes</option>
            </select>
          </label>
          <p className="ai-control-note">
            {dataClass === "public"
              ? "All connected models can take part, including restricted ones."
              : dataClass === "person_public"
              ? "Restricted models can take part, but they see only the person's public name, company and title."
              : "Only trusted models can take part. Restricted ones are left out."}
          </p>
          <Button onClick={run} busy={running} disabled={!instructions.trim() || Boolean(blocked)}>
            Ask all models
          </Button>
        </div>
      </div>

      {running ? (
        <div className="studio-answers">
          {providers
            .filter((row) => row.connected && row.enabled)
            .slice(0, 6)
            .map((row) => (
              <article key={row.id} className="answer-card answer-card-loading" aria-hidden="true">
                <header>
                  <strong>{row.name}</strong>
                </header>
                <div className="skeleton-line" />
                <div className="skeleton-line" />
                <div className="skeleton-line skeleton-short" />
              </article>
            ))}
        </div>
      ) : null}

      {result ? (
        <>
          <div className="studio-summary">
            <p>
              <strong>{ok.length}</strong> of {answers.length} model{answers.length === 1 ? "" : "s"} answered
              in {(result.total_duration_ms / 1000).toFixed(1)}s.
            </p>
            {result.notes.map((note, index) => (
              <p key={index} className="studio-note">
                {note}
              </p>
            ))}
            {result.excluded.length > 0 ? (
              <details className="studio-excluded">
                <summary>{result.excluded.length} model(s) were left out — why?</summary>
                <ul>
                  {result.excluded.map((item, index) => (
                    <li key={index}>{item.detail ?? item.reason}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>

          <div className="studio-answers">
            {answers.map((branch) => (
              <article
                key={branch.provider_id}
                className={
                  kept === branch.provider_id ? "answer-card answer-card-kept" : "answer-card"
                }
              >
                <header className="answer-card-head">
                  <span aria-hidden="true">{branch.flag}</span>
                  <div>
                    <strong>{branch.provider_name}</strong>
                    <small>{branch.model_id}</small>
                  </div>
                  <Badge tone={TIER_TONE[branch.tier] ?? "neutral"}>
                    {TIER_WORD[branch.tier] ?? branch.tier}
                  </Badge>
                </header>

                {branch.ok ? (
                  <>
                    <p className="answer-body">{branch.text}</p>
                    <footer className="answer-meta">
                      <span>{(branch.duration_ms / 1000).toFixed(1)}s</span>
                      <span>
                        {branch.estimated_cost_usd > 0
                          ? `~$${branch.estimated_cost_usd.toFixed(4)}`
                          : "free"}
                      </span>
                      <span title={`Fields sent: ${branch.payload_fields.join(", ")}`}>
                        saw: {branch.policy}
                      </span>
                      <Button
                        tone="ghost"
                        onClick={() => {
                          navigator.clipboard?.writeText(branch.text);
                          setKept(branch.provider_id);
                          notify(`${branch.provider_name}'s answer copied`, "success");
                        }}
                      >
                        {kept === branch.provider_id ? "Copied ✓" : "Use this"}
                      </Button>
                    </footer>
                  </>
                ) : (
                  <p className="answer-error">{branch.error || "No answer returned."}</p>
                )}
              </article>
            ))}
          </div>
        </>
      ) : null}

      {!result && !running ? (
        <StatePanel
          title="Compare answers side by side"
          description="Ask every model you have connected the same thing at once, then keep whichever answer is best. Each model only receives what its own trust level allows, so a restricted model can help without seeing more than it should."
        />
      ) : null}
    </div>
  );
}

/** A lead model breaks the job into steps; each step runs where it fits best. */
export function PlanView({ providers, modes }: { providers: AIProviderRow[]; modes: AIModesPayload | null }) {
  const { notify } = useApp();
  const [instructions, setInstructions] = useState("");
  const [dataClass, setDataClass] = useState<"public" | "person_public" | "campaign">("public");
  const [planner, setPlanner] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AIRunResult | null>(null);

  const mode = modes?.modes.find((item) => item.value === "orchestrated");
  const blocked = mode && !mode.available;
  const planners = providers.filter(
    (row) => row.connected && row.enabled && ["A", "B"].includes(row.effective_tier)
  );

  async function run() {
    if (!instructions.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      setResult(
        await api.post<AIRunResult>("/ai/run", {
          mode: "orchestrated",
          data_class: dataClass,
          instructions: instructions.trim(),
          planner_provider_id: planner,
          task_type: "planned_run"
        })
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not run", "error");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="studio">
      <ModelStrip providers={providers} modes={modes} compact />

      {blocked ? (
        <StatePanel
          title="Planning needs a trusted lead model"
          description={mode?.blocked_reason ?? ""}
          action={<Button onClick={() => (window.location.hash = "connectors")}>Open Connectors</Button>}
        />
      ) : null}

      <div className="studio-composer">
        <label className="studio-field">
          <span>Describe the whole job</span>
          <textarea
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            rows={4}
            placeholder="Design a three-email sequence for EU importers affected by the new customs rules."
            disabled={running}
          />
        </label>

        <div className="studio-controls">
          <label className="ai-control">
            <span>Lead model</span>
            <select value={planner} onChange={(event) => setPlanner(event.target.value)}>
              <option value="">Pick the best one for me</option>
              {planners.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.flag} {row.name}
                </option>
              ))}
            </select>
          </label>

          <label className="ai-control">
            <span>Information needed</span>
            <select
              value={dataClass}
              onChange={(event) => setDataClass(event.target.value as typeof dataClass)}
            >
              <option value="public">Nothing personal</option>
              <option value="person_public">A person's public details</option>
              <option value="campaign">My template and campaign notes</option>
            </select>
          </label>

          <p className="ai-control-note">
            Only models at Highest or Default trust can lead. Deciding the plan means seeing the whole job, so
            restricted models get given steps to do — never the job to split.
          </p>

          <Button onClick={run} busy={running} disabled={!instructions.trim() || Boolean(blocked)}>
            Plan and run
          </Button>
        </div>
      </div>

      {result ? (
        <div className="plan-result">
          <p className="studio-summary">
            <strong>{result.planner_provider_name}</strong> planned this in{" "}
            {result.steps.length} step{result.steps.length === 1 ? "" : "s"} ·{" "}
            {(result.total_duration_ms / 1000).toFixed(1)}s total
          </p>

          {result.notes.map((note, index) => (
            <p key={index} className="studio-note">
              {note}
            </p>
          ))}

          <ol className="plan-steps">
            {result.steps.map((step) => (
              <li key={step.index} className={step.ok ? "plan-step" : "plan-step plan-step-failed"}>
                <header className="plan-step-head">
                  <strong>{step.title}</strong>
                  {step.assigned_provider_name ? (
                    <span className="plan-step-who">→ {step.assigned_provider_name}</span>
                  ) : null}
                </header>
                <p className="plan-step-instructions">{step.instructions}</p>
                {step.ok ? (
                  <p className="plan-step-output">{step.text}</p>
                ) : (
                  <p className="answer-error">{step.error || "This step did not run."}</p>
                )}
              </li>
            ))}
          </ol>
        </div>
      ) : !running ? (
        <StatePanel
          title="Let a lead model break the job up"
          description="Good for big jobs. A trusted model writes a short plan, then each step goes to whichever model suits it — research to a reasoning model, drafting to a fast one. You see the plan and every step's output."
        />
      ) : null}
    </div>
  );
}
