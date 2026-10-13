import { useMemo, useState, type FormEvent } from "react";
import { ApiError, api } from "../api";
import { Badge, Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { AIProviderRow, AIProvidersPayload, ProviderBalance, StatusPayload } from "../types";
import CapPicker, { CALL_CAP_PRESETS, SPEND_CAP_PRESETS, readCap } from "./CapPicker";
import ModelPicker from "./ModelPicker";
import {
  ModelTrustSelect,
  POLICY_ORDER,
  ProviderTrustSelect,
  TRUST_WORD,
  canGrantFullData,
  grantLine,
  policyWord
} from "./TrustSelect";

export { POLICY_ORDER, policyWord };
import { Loadable } from "./shared";

/** Tier → how the badge reads. Colour alone never carries the meaning. */
const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };
const TIER_WORD: Record<string, string> = {
  A: "Highest trust",
  B: "Default trust",
  C: "Restricted",
  D: "Blocked"
};

/** "Sends" on the card: the most any switched-on model is sent (D-179) —
 * "Nothing" when every one of them is blocked (D-188). */
export function sendsWord(row: {
  receives_nothing: boolean;
  sends_nothing?: boolean;
  sends?: string;
  sends_varies?: boolean;
  data_policy: string;
}): string {
  if (row.receives_nothing || row.sends_nothing) return "Nothing";
  return `${row.sends_varies ? "Up to " : ""}${policyWord(row.sends || row.data_policy)}`;
}

/** The levels "How much to send" offers: none above what the provider's
 * standing trust allows, so nothing chosen is cut when saved (D-184). Above
 * it is the grant's job, offered below the form. */
export function levelsUpTo(standing: string): readonly string[] {
  const top = POLICY_ORDER.indexOf(standing as (typeof POLICY_ORDER)[number]);
  return top < 0 ? POLICY_ORDER : POLICY_ORDER.slice(0, top + 1);
}

/** The saved level as the form shows it: within the offered levels. */
export function formLevel(saved: string, standing: string): string {
  const offered = levelsUpTo(standing);
  return offered.includes(saved) ? saved : offered[offered.length - 1];
}


/** Groups providers by tier so the safest options are read first. */
const TIER_ORDER = ["A", "B", "C", "D"] as const;

export default function Connectors() {
  const { notify } = useApp();
  const [busy, setBusy] = useState("");
  const [openProvider, setOpenProvider] = useState<string>("");
  const [modelsFor, setModelsFor] = useState<string>("");
  // Kept here, not in the card: a trust change reloads the list, and a card
  // remounted with its own state closed the section after every change.
  const [trustFor, setTrustFor] = useState<string>("");
  const [showBlocked, setShowBlocked] = useState(false);
  const [balances, setBalances] = useState<Record<string, ProviderBalance>>({});

  const providers = useResource(() => api.get<AIProvidersPayload>("/ai/providers"), []);
  const status = useResource(() => api.get<StatusPayload>("/settings/status"), []);

  const grouped = useMemo(() => {
    const rows = providers.data?.providers ?? [];
    return TIER_ORDER.map((tier) => ({
      tier,
      rows: rows.filter((row) => row.effective_tier === tier)
    })).filter((group) => group.rows.length > 0);
  }, [providers.data]);

  const connectedCount = (providers.data?.providers ?? []).filter((row) => row.connected).length;

  async function connect(row: AIProviderRow, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const requestsPerDay = readCap(data.get("requests_per_day"));
    const spendPerDay = readCap(data.get("max_spend_usd_per_day"));
    if (requestsPerDay === null || spendPerDay === null) {
      notify("Type a number of 0 or more for the custom cap, or pick a preset. Nothing was saved.", "warning");
      return;
    }
    setBusy(`connect-${row.id}`);
    try {
      const result = await api.post<{ policy_was_clamped: boolean; tier: string; policy_ceiling: string }>(
        `/ai/providers/${row.id}/connect`,
        {
          api_key: String(data.get("api_key") ?? ""),
          model_ids: [String(data.get("model_id") ?? (row.model_id || row.default_model))],
          data_policy: String(data.get("data_policy") ?? ""),
          requests_per_day: requestsPerDay,
          max_spend_usd_per_day: spendPerDay
        }
      );
      if (result.policy_was_clamped) {
        notify(
          `${row.name} connected. Its level was saved as ${policyWord(result.policy_ceiling)}, the most its trust allows.`,
          "warning"
        );
      } else {
        notify(`${row.name} connected. Its key is encrypted before it is saved.`, "success");
      }
      setOpenProvider("");
      // The next saved key may have a different balance; never show its old
      // predecessor's provider-reported amount as if it belongs to this key.
      setBalances((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not connect this provider", "error");
    } finally {
      setBusy("");
    }
  }

  async function disconnect(row: AIProviderRow) {
    if (!window.confirm(`Disconnect ${row.name}? This deletes the stored key. Your chats and drafts stay.`)) return;
    setBusy(`disconnect-${row.id}`);
    try {
      await api.post(`/ai/providers/${row.id}/disconnect`, {});
      notify(`${row.name} disconnected`, "success");
      setBalances((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not disconnect", "error");
    } finally {
      setBusy("");
    }
  }

  async function checkBalance(row: AIProviderRow) {
    setBusy(`balance-${row.id}`);
    try {
      const result = await api.post<ProviderBalance>(
        `/ai/providers/${row.id}/balance`, {}
      );
      setBalances((current) => ({ ...current, [row.id]: result }));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not check provider balance", "error");
    } finally {
      setBusy("");
    }
  }

  async function raiseTrust(row: AIProviderRow) {
    const reason = window.prompt(
      `Let ${row.name} receive more than tier ${row.effective_tier} normally allows.\n\n` +
        `${row.name} is in ${row.jurisdiction}. Its terms: ${row.retention}\n\n` +
        `Type why you are making this exception. It is stored with the decision.`
    );
    if (reason === null) return;
    if (!reason.trim()) {
      notify("A reason is required. Nothing was changed.", "warning");
      return;
    }
    setBusy(`override-${row.id}`);
    try {
      await api.post(`/ai/providers/${row.id}/override`, {
        data_policy: "full",
        allow_above_ceiling: true,
        reason: reason.trim()
      });
      notify(`${row.name} may now receive full data. The reason is recorded.`, "success");
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not change trust", "error");
    } finally {
      setBusy("");
    }
  }

  // The server says when a change is a raise that needs a reason (DD-65):
  // try without one, and ask only when it answers `reason_required`.
  async function setTrust(row: AIProviderRow, tier: string, modelId = "") {
    const target = modelId ? `${modelId} on ${row.name}` : row.name;
    const send = (reason = "") =>
      api.post(`/ai/providers/${row.id}/trust`, { tier, model_id: modelId, reason });
    setBusy(`trust-${row.id}`);
    try {
      try {
        await send();
      } catch (error) {
        if (!(error instanceof ApiError) || error.detail?.error !== "reason_required") throw error;
        const reason = window.prompt(`${error.message}\n\nWhy are you raising ${target}?`);
        if (!reason?.trim()) {
          notify("A reason is required. Nothing was changed.", "warning");
          return;
        }
        await send(reason.trim());
      }
      notify(
        tier ? `${target} is now ${TRUST_WORD[tier]}.` : `${target} is back to its default trust.`,
        "success"
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not change trust", "error");
    } finally {
      // Reloaded either way: a refused change must show the tier that stands.
      providers.reload();
      setBusy("");
    }
  }

  async function clearOverride(row: AIProviderRow) {
    setBusy(`override-${row.id}`);
    try {
      await api.post(`/ai/providers/${row.id}/override`, {});
      notify(`Full access to ${row.name} withdrawn. Its trust settings stay as they are.`, "success");
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not reset trust", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("workspace");
    try {
      await api.post("/ai/workspace", {
        positioning_line: String(data.get("positioning_line") ?? ""),
        owner_domains: String(data.get("owner_domains") ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        owner_addresses: String(data.get("owner_addresses") ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      });
      notify("Saved", "success");
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save", "error");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Connectors"
        description="Everything off_CRM talks to. AI providers are grouped by how far they are trusted with your data — that grouping decides what each one is allowed to receive."
      />

      {/* ── Gmail ───────────────────────────────────────────────────────── */}
      <Panel
        title="Gmail"
        subtitle="Sending only. No AI provider can read this mailbox."
      >
        {status.loading || status.error ? (
          <Loadable loading={status.loading} error={status.error ?? ""} />
        ) : (
          <div className="connector-row">
            <span className="provider-icon" aria-hidden="true">
              ✉
            </span>
            <div className="provider-row-info">
              <strong>Gmail</strong>
              <small>
                {status.data?.gmail_configured
                  ? `Connected as ${status.data.own_email}`
                  : "Not connected — drafts are written to the local outbox instead"}
              </small>
            </div>
            <Badge tone={status.data?.gmail_configured ? "success" : "warning"}>
              {status.data?.gmail_configured ? "Connected" : "Not connected"}
            </Badge>
            <Button tone="ghost" onClick={() => (window.location.hash = "settings")}>
              {status.data?.gmail_configured ? "Manage" : "Connect"}
            </Button>
          </div>
        )}
        <p className="form-note">
          The Gmail token is held only by off_CRM's mail module. It is never placed in a payload, a log, or a
          prompt. Mailbox content reaching an AI provider is blocked by default for every provider, in every
          country.
        </p>
      </Panel>

      {/* ── What leaves ─────────────────────────────────────────────────── */}
      <Panel
        title="What is allowed to leave"
        subtitle="Your one-line pitch is the only thing about you that any model ever sees"
      >
        {providers.loading || providers.error ? (
          <Loadable loading={providers.loading} error={providers.error ?? ""} />
        ) : (
          <form className="form-stack" onSubmit={saveWorkspace}>
            <Field
              label="Your positioning line"
              hint="One sentence describing what you do. Models need this to write a relevant email."
            >
              <input
                name="positioning_line"
                defaultValue={providers.data?.positioning_line ?? ""}
                placeholder="We help exporters cut customs cost."
                maxLength={500}
              />
            </Field>
            <div className="form-grid">
              <Field label="Your domains" hint="Comma separated. Blocked from every payload.">
                <input
                  name="owner_domains"
                  defaultValue={(providers.data?.owner_domains ?? []).join(", ")}
                  placeholder="offsetx.com, offsetx.io"
                />
              </Field>
              <Field label="Your email addresses" hint="Comma separated. Blocked from every payload.">
                <input
                  name="owner_addresses"
                  defaultValue={(providers.data?.owner_addresses ?? []).join(", ")}
                  placeholder="you@offsetx.com"
                />
              </Field>
            </div>
            <div className="button-row">
              <Button type="submit" busy={busy === "workspace"}>
                Save
              </Button>
              <Button tone="ghost" onClick={() => (window.location.hash = "egress")}>
                See exactly what was sent →
              </Button>
            </div>
          </form>
        )}
      </Panel>

      {/* ── AI providers ────────────────────────────────────────────────── */}
      <Panel
        title="AI providers"
        subtitle={
          connectedCount
            ? `${connectedCount} connected. Work goes to the most trusted one that can do the job.`
            : "None connected yet. Start with one from Highest trust."
        }
        className="settings-wide"
      >
        {providers.loading || providers.error ? (
          <Loadable loading={providers.loading} error={providers.error ?? ""} />
        ) : (
          <div className="tier-groups">
            {grouped
              .filter((group) => showBlocked || group.tier !== "D")
              .map((group) => (
                <section key={group.tier} className={`tier-group tier-group-${group.tier}`}>
                  <header className="tier-group-head">
                    <Badge tone={TIER_TONE[group.tier]}>{TIER_WORD[group.tier]}</Badge>
                    <p className="tier-group-note">{tierNote(group.tier)}</p>
                  </header>

                  <div className="provider-cards">
                    {group.rows.map((row) => (
                      <ProviderCard
                        key={row.id}
                        row={row}
                        open={openProvider === row.id}
                        busy={busy}
                        balance={balances[row.id]}
                        onCheckBalance={() => checkBalance(row)}
                        showModels={modelsFor === row.id}
                        onToggle={() => setOpenProvider(openProvider === row.id ? "" : row.id)}
                        onModels={() => setModelsFor(modelsFor === row.id ? "" : row.id)}
                        onModelsSaved={() => { setModelsFor(""); providers.reload(); }}
                        onConnect={(event) => connect(row, event)}
                        onDisconnect={() => disconnect(row)}
                        onRaise={() => raiseTrust(row)}
                        onClearOverride={() => clearOverride(row)}
                        onTrust={(tier, modelId) => setTrust(row, tier, modelId)}
                        showModelTrust={trustFor === row.id}
                        onModelTrustToggle={(open) => setTrustFor(open ? row.id : trustFor === row.id ? "" : trustFor)}
                      />
                    ))}
                  </div>
                </section>
              ))}

            <button type="button" className="custom-provider-toggle" onClick={() => setShowBlocked((v) => !v)}>
              {showBlocked ? "▲ Hide blocked providers" : "Show blocked providers (routers and aggregators)"}
            </button>
          </div>
        )}
      </Panel>
    </div>
  );
}

/** What the level below the form means right now — each sentence true of
 * the card as it stands (D-184). */
function levelHint(row: AIProviderRow): string {
  const tiers = ["D", "C", "B", "A"];
  if (row.grant_active) {
    return `Your grant sends ${policyWord(row.policy_ceiling)} to the models it covers. This level is for the rest, and for all of them once you withdraw it.`;
  }
  if (tiers.indexOf(row.effective_tier) < tiers.indexOf(row.default_tier ?? row.trust_tier)) {
    return `You trust ${row.name} less than its default, so it is sent at most ${policyWord(row.policy_ceiling)} for now. This level applies again when you restore it.`;
  }
  return `Tier ${row.effective_tier} allows up to ${policyWord(row.policy_ceiling)}. A model built elsewhere may be sent less; the card shows what is sent.`;
}

function tierNote(tier: string): string {
  if (tier === "A")
    return "European or running on your own machine. May receive your templates, drafts and CRM notes.";
  if (tier === "B")
    return "United States and allied. May receive a person's public details, your template and your positioning — never your email address.";
  if (tier === "C")
    return "Restricted. May receive a person's public name, company and title so it can personalise, plus public and coding work. Never your template, notes, addresses or mailbox.";
  return "Routers and aggregators. The company that actually processes your data is not knowable, so nothing is sent.";
}

function ProviderCard({
  row,
  open,
  busy,
  balance,
  onCheckBalance,
  showModels,
  onToggle,
  onModels,
  onModelsSaved,
  onConnect,
  onDisconnect,
  onRaise,
  onClearOverride,
  onTrust,
  showModelTrust,
  onModelTrustToggle
}: {
  row: AIProviderRow;
  open: boolean;
  busy: string;
  balance?: ProviderBalance;
  onCheckBalance: () => void;
  showModels: boolean;
  onToggle: () => void;
  onModels: () => void;
  onModelsSaved: () => void;
  onConnect: (event: FormEvent<HTMLFormElement>) => void;
  onDisconnect: () => void;
  onRaise: () => void;
  onClearOverride: () => void;
  onTrust: (tier: string, modelId?: string) => void;
  showModelTrust: boolean;
  onModelTrustToggle: (open: boolean) => void;
}) {
  const blocked = row.effective_tier === "D";
  const usage = row.usage;
  const grant = grantLine(row);

  return (
    <article className={row.connected ? "provider-card provider-card-on" : "provider-card"}>
      <header className="provider-card-head">
        <span className="catalog-flag" aria-hidden="true">
          {row.flag || "⚡"}
        </span>
        <div className="provider-card-title">
          <strong>{row.name}</strong>
          <small>{row.models[0]?.id ?? row.default_model}</small>
        </div>
        {row.connected ? <Badge tone="success">On</Badge> : null}
      </header>

      {/* The three facts §4B requires at a glance. */}
      <dl className="provider-facts">
        <div>
          <dt>Country</dt>
          <dd>{row.jurisdiction}</dd>
        </div>
        <div>
          <dt>Trust</dt>
          <dd>
            <ProviderTrustSelect
              name={row.name}
              value={row.effective_tier}
              defaultTier={row.default_tier ?? row.trust_tier}
              disabled={busy === `trust-${row.id}`}
              onChange={(tier) => onTrust(tier)}
            />
          </dd>
        </div>
        <div>
          <dt>Sends</dt>
          <dd>{sendsWord(row)}</dd>
        </div>
      </dl>

      <p className="provider-retention">
        <strong>Data terms:</strong> {row.retention}
        {row.trains_on_input ? <em className="provider-warn"> Trains on what you send.</em> : null}
      </p>

      {row.override?.trust_tier ? (
        <p className="provider-override">
          Set to {TRUST_WORD[row.override.trust_tier]} by {row.override.trust_decided_by}
          {row.override.trust_reason ? `: ${row.override.trust_reason}` : ""}
        </p>
      ) : null}
      <details
        className="provider-model-trust"
        open={showModelTrust}
        onToggle={(event) => onModelTrustToggle((event.currentTarget as HTMLDetailsElement).open)}
      >
        <summary>Trust per model ({(row.trust_models ?? row.available_models).length})</summary>
        <p className="muted-copy">
          A model is trusted as much as {row.name}, or less: the provider sees everything sent to
          it. A model built elsewhere stays capped until its own setting lifts it, with a reason.
        </p>
        <ul>
          {(row.trust_models ?? row.available_models).map((model) => (
            <li key={model.id}>
              <span>
                {model.id} <Badge tone={TIER_TONE[model.tier]}>{TIER_WORD[model.tier]}</Badge>
              </span>
              <ModelTrustSelect
                modelId={model.id}
                providerName={row.name}
                value={row.override?.model_tiers?.[model.id]?.tier ?? ""}
                disabled={busy === `trust-${row.id}`}
                onChange={(tier) => onTrust(tier, model.id)}
              />
            </li>
          ))}
        </ul>
      </details>
      {grant ? (
        <p className="provider-override">
          {grant}{" "}
          <button type="button" className="link-button" onClick={onClearOverride}>
            withdraw
          </button>
        </p>
      ) : null}

      {row.connected ? (
        <div className="provider-usage" aria-label={`Usage for ${row.name}`}>
          {usage ? (
            <p>
              Used today: {usage.day_used}
              {usage.day_limit > 0 ? ` / ${usage.day_limit}` : " · no local daily cap configured"}
              {" "}· counted by off_CRM (UTC day)
              {usage.exhausted ? <em className="provider-warn"> Local cap reached; calls are paused.</em> : null}
            </p>
          ) : <p>Local usage counter is not available for this provider.</p>}
          {row.usage_report === "balance_endpoint" ? (
            <>
              <Button tone="secondary" busy={busy === `balance-${row.id}`} onClick={onCheckBalance}>Check provider balance</Button>
              {balance?.supported ? (
                <p role="status">
                  {balance.available && balance.remaining != null
                    ? `Provider-reported ${balance.kind === "key_spend_limit" ? "remaining key spend limit" : "account balance"}: ${balance.remaining} ${balance.unit}`
                    : balance.description || "No provider balance is available"}
                  {balance.checked_at ? ` · checked ${new Date(balance.checked_at).toLocaleString()}` : ""}
                </p>
              ) : null}
            </>
          ) : row.usage_report === "rate_limit_headers" ? (
            <p>Provider reports rate limits in response headers; off_CRM does not yet display a verified remaining amount.</p>
          ) : (
            <p>{row.name} does not report a supported remaining quota to off_CRM.</p>
          )}
        </div>
      ) : null}

      {row.self_hostable && row.effective_tier === "C" ? (
        <p className="provider-tip">{row.self_host_note}</p>
      ) : null}

      <footer className="provider-card-actions">
        {blocked ? (
          <>
            {/* "Allow anyway…" lifted what may be sent, and a blocked provider
                receives nothing at any level, so it changed nothing (D-171).
                Raising its trust, above, is what unblocks it. */}
            <span className="muted-copy">
              {row.override?.trust_tier === "D"
                ? "Blocked by you."
                : "Blocked by default. Raise its trust above to use it."}
            </span>
            {row.connected ? (
              <Button tone="ghost" busy={busy === `disconnect-${row.id}`} onClick={onDisconnect}>
                Disconnect
              </Button>
            ) : null}
          </>
        ) : row.connected ? (
          <>
            <Button tone="ghost" onClick={onModels}>
              {showModels ? "Hide models" : `Models (${row.model_ids?.length || 1})`}
            </Button>
            <Button tone="ghost" onClick={onToggle}>
              {open ? "Close" : "Change settings"}
            </Button>
            <Button tone="ghost" busy={busy === `disconnect-${row.id}`} onClick={onDisconnect}>
              Disconnect
            </Button>
          </>
        ) : (
          <Button onClick={onToggle}>{open ? "Close" : "Connect"}</Button>
        )}
      </footer>

      {showModels && row.connected ? (
        <ModelPicker provider={row} onSaved={onModelsSaved} />
      ) : null}

      {open && !blocked ? (
        <form className="provider-connect-form" onSubmit={onConnect}>
          <p className="provider-howto">{row.how_to_get}</p>
          <a href={row.key_url} target="_blank" rel="noopener noreferrer" className="howto-link">
            Open the {row.name} key page →
          </a>

          <Field label="API key" hint="Encrypted before it is saved, wherever this install keeps its data.">
            <input
              name="api_key"
              type="password"
              autoComplete="new-password"
              placeholder={row.has_key ? "Key already stored — leave blank to keep it" : row.key_placeholder}
            />
          </Field>

          <div className="form-grid">
            <Field label="Starting model" hint="Add more after connecting — one key can run several.">
              <select name="model_id" defaultValue={row.model_id}>
                {row.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.id}
                    {model.is_free ? " (free)" : ""}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="How much to send" hint={levelHint(row)}>
              <select
                name="data_policy"
                defaultValue={formLevel(row.data_policy, row.standing_ceiling ?? row.policy_ceiling)}
              >
                {levelsUpTo(row.standing_ceiling ?? row.policy_ceiling).map((value) => (
                  <option key={value} value={value}>
                    {policyWord(value)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {canGrantFullData(row) ? (
            <p className="provider-grant">
              <button
                type="button"
                className="link-button"
                disabled={busy === `override-${row.id}`}
                onClick={onRaise}
              >
                Send full data to {row.name} anyway…
              </button>
            </p>
          ) : null}

          <div className="form-grid">
            <Field label="Daily call cap" hint="Counted by off_CRM. The provider's own limit still applies.">
              <CapPicker
                name="requests_per_day"
                label="Daily call cap"
                presets={CALL_CAP_PRESETS}
                defaultValue={row.requests_per_day ?? 0}
              />
            </Field>
            <Field label="Daily spend cap (USD)" hint="Stops calls once today's estimated spend reaches it.">
              <CapPicker
                name="max_spend_usd_per_day"
                label="Daily spend cap"
                presets={SPEND_CAP_PRESETS}
                defaultValue={row.max_spend_usd_per_day ?? 0}
                step={0.5}
              />
            </Field>
          </div>

          <Button type="submit" busy={busy === `connect-${row.id}`}>
            {row.connected ? "Save changes" : `Connect ${row.name}`}
          </Button>
        </form>
      ) : null}
    </article>
  );
}
