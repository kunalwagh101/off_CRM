import { useMemo, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { AIProviderRow, AIProvidersPayload, StatusPayload } from "../types";
import { Loadable } from "./shared";

/** Tier → how the badge reads. Colour alone never carries the meaning. */
const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };
const TIER_WORD: Record<string, string> = {
  A: "Highest trust",
  B: "Default trust",
  C: "Restricted",
  D: "Blocked"
};

function policyWord(value: string): string {
  return { strict: "Strict", minimal: "Minimal", standard: "Standard", full: "Full access" }[value] ?? value;
}

/** Groups providers by tier so the safest options are read first. */
const TIER_ORDER = ["A", "B", "C", "D"] as const;

export default function Connectors() {
  const { notify } = useApp();
  const [busy, setBusy] = useState("");
  const [openProvider, setOpenProvider] = useState<string>("");
  const [showBlocked, setShowBlocked] = useState(false);

  const providers = useResource(() => api.get<AIProvidersPayload>("/ai/providers"), []);
  const status = useResource(() => api.get<StatusPayload>("/status"), []);

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
    setBusy(`connect-${row.id}`);
    try {
      const result = await api.post<{ policy_was_clamped: boolean; tier: string; policy_ceiling: string }>(
        `/ai/providers/${row.id}/connect`,
        {
          api_key: String(data.get("api_key") ?? ""),
          model_id: String(data.get("model_id") ?? ""),
          data_policy: String(data.get("data_policy") ?? ""),
          requests_per_day: Number(data.get("requests_per_day") ?? 0),
          max_spend_usd_per_day: Number(data.get("max_spend_usd_per_day") ?? 0)
        }
      );
      if (result.policy_was_clamped) {
        notify(
          `${row.name} connected at ${policyWord(result.policy_ceiling)}. Tier ${result.tier} does not allow more than that by default.`,
          "warning"
        );
      } else {
        notify(`${row.name} connected. Key encrypted on this machine.`, "success");
      }
      setOpenProvider("");
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
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not disconnect", "error");
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
      notify(`${row.name} raised to full access. The reason is recorded.`, "success");
      providers.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not change trust", "error");
    } finally {
      setBusy("");
    }
  }

  async function clearOverride(row: AIProviderRow) {
    setBusy(`override-${row.id}`);
    try {
      await api.post(`/ai/providers/${row.id}/override`, {});
      notify(`${row.name} returned to its default trust level`, "success");
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
                        onToggle={() => setOpenProvider(openProvider === row.id ? "" : row.id)}
                        onConnect={(event) => connect(row, event)}
                        onDisconnect={() => disconnect(row)}
                        onRaise={() => raiseTrust(row)}
                        onClearOverride={() => clearOverride(row)}
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
  onToggle,
  onConnect,
  onDisconnect,
  onRaise,
  onClearOverride
}: {
  row: AIProviderRow;
  open: boolean;
  busy: string;
  onToggle: () => void;
  onConnect: (event: FormEvent<HTMLFormElement>) => void;
  onDisconnect: () => void;
  onRaise: () => void;
  onClearOverride: () => void;
}) {
  const blocked = row.effective_tier === "D";
  const usage = row.usage;

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
            <Badge tone={TIER_TONE[row.effective_tier]}>{TIER_WORD[row.effective_tier]}</Badge>
          </dd>
        </div>
        <div>
          <dt>Sends</dt>
          <dd>{policyWord(row.data_policy)}</dd>
        </div>
      </dl>

      <p className="provider-retention">
        <strong>Data terms:</strong> {row.retention}
        {row.trains_on_input ? <em className="provider-warn"> Trains on what you send.</em> : null}
      </p>

      {row.override ? (
        <p className="provider-override">
          Trust changed by you: {row.override.reason}
          <button type="button" className="link-button" onClick={onClearOverride}>
            reset
          </button>
        </p>
      ) : null}

      {usage && (usage.day_limit > 0 || usage.minute_limit > 0) ? (
        <p className="provider-usage">
          Used today: {usage.day_used}
          {usage.day_limit > 0 ? ` / ${usage.day_limit}` : ""} · counted on this machine
          {usage.exhausted ? <em className="provider-warn"> Out of quota — skipped until it resets.</em> : null}
        </p>
      ) : null}

      {row.self_hostable && row.effective_tier === "C" ? (
        <p className="provider-tip">{row.self_host_note}</p>
      ) : null}

      <footer className="provider-card-actions">
        {blocked ? (
          <>
            <span className="muted-copy">Blocked by default.</span>
            <Button tone="ghost" busy={busy === `override-${row.id}`} onClick={onRaise}>
              Allow anyway…
            </Button>
          </>
        ) : row.connected ? (
          <>
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

      {open && !blocked ? (
        <form className="provider-connect-form" onSubmit={onConnect}>
          <p className="provider-howto">{row.how_to_get}</p>
          <a href={row.key_url} target="_blank" rel="noopener noreferrer" className="howto-link">
            Open the {row.name} key page →
          </a>

          <Field label="API key" hint="Encrypted on this machine before it touches disk.">
            <input
              name="api_key"
              type="password"
              autoComplete="new-password"
              placeholder={row.has_key ? "Key already stored — leave blank to keep it" : row.key_placeholder}
            />
          </Field>

          <div className="form-grid">
            <Field label="Model">
              <select name="model_id" defaultValue={row.model_id}>
                {row.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.id}
                    {model.is_free ? " (free)" : ""}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="How much to send" hint={`Tier ${row.effective_tier} allows up to ${policyWord(row.policy_ceiling)}.`}>
              <select name="data_policy" defaultValue={row.data_policy}>
                {["strict", "minimal", "standard", "full"].map((value) => (
                  <option key={value} value={value}>
                    {policyWord(value)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="form-grid">
            <Field label="Daily call cap" hint="0 means use the provider's own limit.">
              <input name="requests_per_day" type="number" min="0" defaultValue={row.requests_per_day ?? 0} />
            </Field>
            <Field label="Daily spend cap (USD)" hint="0 means no cap.">
              <input
                name="max_spend_usd_per_day"
                type="number"
                min="0"
                step="0.5"
                defaultValue={row.max_spend_usd_per_day ?? 0}
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
