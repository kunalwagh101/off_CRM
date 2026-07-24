import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type {
  AIEgressCall,
  ConnectorsStatus,
  Paginated,
  ProviderProfile
} from "../types";
import { Loadable } from "./shared";

const PROVIDER_DEFAULTS: Record<string, { model: string; env: string; host: string; jurisdiction: string }> = {
  openai: {
    model: "",
    env: "OPENAI_API_KEY",
    host: "OpenAI",
    jurisdiction: "United States"
  },
  anthropic: {
    model: "",
    env: "ANTHROPIC_API_KEY",
    host: "Anthropic",
    jurisdiction: "United States"
  },
  openai_compatible: {
    model: "",
    env: "AI_PROVIDER_API_KEY",
    host: "",
    jurisdiction: "Unknown"
  },
  template_engine_http: {
    model: "",
    env: "TEMPLATE_ENGINE_API_KEY",
    host: "Owner-operated template service",
    jurisdiction: "Owner controlled"
  }
};

type RegisteredTool = {
  id: string;
  name: string;
  description: string;
  repository_url: string;
  commit_sha: string;
  image: string;
  command: string[];
  status: string;
  network_policy: "none";
  data_policy: "public_input_only";
  last_prepared_at: string;
  last_run_at: string;
  last_error: string;
};

function tierTone(tier: string): string {
  if (tier === "A") return "success";
  if (tier === "B") return "blue";
  if (tier === "C") return "warning";
  return "danger";
}

function healthTone(status: string): string {
  if (status === "healthy") return "success";
  if (status === "unhealthy") return "danger";
  return "neutral";
}

function retentionLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export default function Connections() {
  const { notify } = useApp();
  const [busy, setBusy] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ProviderProfile | null>(null);
  const [providerType, setProviderType] = useState("openai");
  const [audit, setAudit] = useState<AIEgressCall | null>(null);
  const [toolOpen, setToolOpen] = useState(false);
  const [runTool, setRunTool] = useState<RegisteredTool | null>(null);
  const [toolResult, setToolResult] = useState<{ status: string; output: string; error: string } | null>(null);
  const connectors = useResource<ConnectorsStatus>(() => api.get("/connectors"), []);
  const egress = useResource<Paginated<AIEgressCall>>(
    () => api.get("/ai/egress?limit=30"),
    []
  );
  const tools = useResource<Paginated<RegisteredTool>>(
    () => api.get("/ai/tools"),
    []
  );

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const data = event.data as { type?: string; success?: boolean };
      if (data?.type !== "off-crm-gmail-connector") return;
      connectors.reload();
      notify(
        data.success ? "Gmail connected to OFF_CRM" : "Gmail connection failed",
        data.success ? "success" : "error"
      );
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [connectors.reload, notify]);

  function openNewProvider() {
    setEditing(null);
    setProviderType("openai");
    setFormOpen(true);
  }

  function openEditProvider(profile: ProviderProfile) {
    setEditing(profile);
    setProviderType(profile.provider_type);
    setFormOpen(true);
  }

  async function connectGmail() {
    setBusy("gmail-connect");
    try {
      const result = await api.post<{ authorization_url: string }>("/connectors/gmail/start", {});
      const popup = window.open(
        result.authorization_url,
        "off-crm-gmail",
        "popup=yes,width=620,height=760"
      );
      if (!popup) {
        window.location.assign(result.authorization_url);
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : "Gmail connection could not start", "error");
    } finally {
      setBusy("");
    }
  }

  async function disconnectGmail() {
    if (!window.confirm("Disconnect Gmail and remove the local OAuth token?")) return;
    setBusy("gmail-disconnect");
    try {
      await api.post("/connectors/gmail/disconnect", {});
      connectors.reload();
      notify("Gmail disconnected and its local token removed", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Gmail could not be disconnected", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const allowed = data
      .getAll("allowed_task_types")
      .map(String)
      .filter(Boolean);
    const fallbackIds = data
      .getAll("fallback_profile_ids")
      .map(String)
      .filter(Boolean);
    setBusy("provider-save");
    try {
      await api.post<ProviderProfile>("/provider-profiles", {
        id: editing?.id || "",
        owner: String(data.get("owner") || "default"),
        name: data.get("name"),
        provider_type: providerType,
        model: data.get("model"),
        api_key_env: data.get("api_key_env"),
        api_key: data.get("api_key"),
        base_url: data.get("base_url"),
        timeout_seconds: Number(data.get("timeout_seconds") || 60),
        priority: Number(data.get("priority") || 100),
        enabled: data.get("enabled") === "on",
        data_policy: "minimal",
        audit_payloads: false,
        fallback_strategy: "priority",
        jurisdiction: data.get("jurisdiction"),
        retention_policy: data.get("retention_policy"),
        trust_tier: data.get("trust_tier"),
        host_origin: data.get("host_origin"),
        model_origin: data.get("model_origin"),
        model_origin_jurisdiction: data.get("model_origin_jurisdiction"),
        model_origin_input_isolation_verified:
          data.get("model_origin_input_isolation_verified") === "on",
        terms_checked_at: data.get("terms_checked_at"),
        rpm_limit: Number(data.get("rpm_limit") || 0),
        rpd_limit: Number(data.get("rpd_limit") || 0),
        context_window: Number(data.get("context_window") || 0),
        input_cost_per_million: Number(data.get("input_cost_per_million") || 0),
        output_cost_per_million: Number(data.get("output_cost_per_million") || 0),
        daily_cost_cap: Number(data.get("daily_cost_cap") || 0),
        monthly_cost_cap: Number(data.get("monthly_cost_cap") || 0),
        allowed_task_types: allowed,
        fallback_profile_ids: fallbackIds,
        public_tasks_enabled: data.get("public_tasks_enabled") === "on",
        extra: {}
      });
      setFormOpen(false);
      setEditing(null);
      form.reset();
      connectors.reload();
      notify("AI provider saved to the local encrypted registry", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "AI provider could not be saved", "error");
    } finally {
      setBusy("");
    }
  }

  async function testProvider(profile: ProviderProfile) {
    setBusy(`test-${profile.id}`);
    try {
      const result = await api.post<{ status: string }>(
        `/provider-profiles/${profile.id}/test`,
        { live_probe: true }
      );
      connectors.reload();
      notify(`${profile.name}: ${result.status}`, "success");
    } catch (error) {
      connectors.reload();
      notify(error instanceof Error ? error.message : "Provider test failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function removeProvider(profile: ProviderProfile) {
    if (!window.confirm(`Remove ${profile.name} and its locally stored key?`)) return;
    setBusy(`delete-${profile.id}`);
    try {
      await api.post(`/provider-profiles/${profile.id}/delete`, {});
      connectors.reload();
      notify(`${profile.name} removed`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider could not be removed", "error");
    } finally {
      setBusy("");
    }
  }

  async function inspectAudit(id: string) {
    setBusy(`audit-${id}`);
    try {
      setAudit(await api.get<AIEgressCall>(`/ai/egress/${id}`));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Audit record unavailable", "error");
    } finally {
      setBusy("");
    }
  }

  async function registerTool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    let command: unknown;
    try {
      command = JSON.parse(String(data.get("command") || "[]"));
    } catch {
      notify("Tool command must be a JSON array, for example [\"python\",\"main.py\"]", "error");
      return;
    }
    if (!Array.isArray(command) || !command.every((part) => typeof part === "string")) {
      notify("Tool command must be a JSON array of strings", "error");
      return;
    }
    setBusy("tool-register");
    try {
      await api.post("/ai/tools", {
        name: data.get("name"),
        description: data.get("description"),
        repository_url: data.get("repository_url"),
        commit_sha: data.get("commit_sha"),
        image: data.get("image"),
        command
      });
      form.reset();
      setToolOpen(false);
      tools.reload();
      notify("Pinned GitHub tool registered; prepare it before first use", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Tool could not be registered", "error");
    } finally {
      setBusy("");
    }
  }

  async function prepareTool(tool: RegisteredTool) {
    if (!window.confirm(`Fetch the exact pinned public commit for ${tool.name}? No credentials or submodules will be used.`)) return;
    setBusy(`tool-prepare-${tool.id}`);
    try {
      await api.post(`/ai/tools/${tool.id}/prepare`, {});
      tools.reload();
      notify(`${tool.name} prepared from its pinned commit`, "success");
    } catch (error) {
      tools.reload();
      notify(error instanceof Error ? error.message : "Tool preparation failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function executeRegisteredTool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runTool) return;
    const data = new FormData(event.currentTarget);
    setBusy(`tool-run-${runTool.id}`);
    setToolResult(null);
    try {
      const result = await api.post<{ status: string; output: string; error: string }>(
        `/ai/tools/${runTool.id}/execute`,
        {
          public_input: data.get("public_input"),
          timeout_seconds: Number(data.get("timeout_seconds") || 60)
        }
      );
      setToolResult(result);
      tools.reload();
      notify(`${runTool.name}: ${result.status}`, result.status === "succeeded" ? "success" : "error");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Sandbox tool failed", "error");
    } finally {
      setBusy("");
    }
  }

  const providerDefaults = PROVIDER_DEFAULTS[providerType];
  const profiles = connectors.data?.ai_providers ?? [];
  const formKey = `${editing?.id || "new"}-${providerType}`;

  return (
    <>
      <PageHeader
        eyebrow="Security boundary"
        title="Connectors"
        description="Gmail and AI providers are connected here. Each credential has one purpose, stays server-side, and can be revoked independently."
        actions={<Button onClick={openNewProvider}>Add AI provider</Button>}
      />

      <div className="connections-grid">
        <Panel
          title="Gmail"
          subtitle="Mail transport and CRM-owned thread reply checks only"
          action={
            connectors.data?.gmail.connected ? (
              <Badge tone="success">Connected</Badge>
            ) : (
              <Badge tone="warning">Not connected</Badge>
            )
          }
        >
          {connectors.loading || connectors.error ? (
            <Loadable loading={connectors.loading} error={connectors.error} />
          ) : connectors.data ? (
            <div className="connector-card">
              <div className="connector-identity">
                <span className="connector-logo gmail-logo">M</span>
                <div>
                  <strong>
                    {connectors.data.gmail.connected
                      ? connectors.data.gmail.account || "Connected Gmail account"
                      : "Connect a Gmail account"}
                  </strong>
                  <small>{connectors.data.gmail.reply_sync_boundary}</small>
                </div>
              </div>
              <dl className="connector-facts">
                <div><dt>Token</dt><dd>{connectors.data.gmail.token_location || "Not stored"}</dd></div>
                <div><dt>AI access</dt><dd><Badge tone="success">None</Badge></dd></div>
                <div><dt>Reply content sent to AI</dt><dd><Badge tone="success">Never</Badge></dd></div>
                <div><dt>Scopes</dt><dd>{connectors.data.gmail.scopes.length || 0} active</dd></div>
              </dl>
              {!connectors.data.gmail.configured ? (
                <div className="form-note">
                  <strong>Google OAuth client is not configured yet</strong>
                  <span>
                    Add the OAuth client-secret JSON path and token path to the backend environment,
                    then return here. Gmail permission remains separate from CRM sign-in.
                  </span>
                </div>
              ) : null}
              <div className="button-row">
                {connectors.data.gmail.connected ? (
                  <Button
                    tone="danger"
                    busy={busy === "gmail-disconnect"}
                    onClick={disconnectGmail}
                  >
                    Disconnect Gmail
                  </Button>
                ) : (
                  <Button
                    busy={busy === "gmail-connect"}
                    disabled={!connectors.data.gmail.configured}
                    onClick={connectGmail}
                  >
                    Connect Gmail
                  </Button>
                )}
              </div>
            </div>
          ) : null}
        </Panel>

        <Panel title="Zero-access boundary" subtitle="What a provider can and cannot do">
          <div className="zero-access-list">
            <div><span>✓</span><p><strong>Push only</strong><small>OFF_CRM constructs and sends a minimal approved packet.</small></p></div>
            <div><span>✓</span><p><strong>No pull tools</strong><small>Providers receive no Gmail, database, memory, file, or browser connector.</small></p></div>
            <div><span>✓</span><p><strong>Preflight inspection</strong><small>Email addresses, secrets, local paths, and private-access instructions are blocked.</small></p></div>
            <div><span>✓</span><p><strong>Same-tier failover</strong><small>A fallback can never silently cross into a less trusted provider tier.</small></p></div>
          </div>
          <Button
            tone="secondary"
            onClick={() =>
              void api.download("/ai/owner-record/export?format=md", "OFF_CRM_owner_record.md")
            }
          >
            Export NotebookLM Markdown
          </Button>
          <Button
            tone="ghost"
            onClick={() =>
              void api.download("/ai/owner-record/export?format=json", "OFF_CRM_owner_record.json")
            }
          >
            Export Notion-ready JSON
          </Button>
        </Panel>

        <Panel
          title="AI providers"
          subtitle="Flat quota-aware registry; routing is default-deny"
          className="connections-wide"
          action={<Badge tone={profiles.some((item) => item.ai_eligible) ? "success" : "warning"}>
            {profiles.filter((item) => item.ai_eligible).length} eligible
          </Badge>}
        >
          {connectors.loading || connectors.error ? (
            <Loadable loading={connectors.loading} error={connectors.error} />
          ) : profiles.length ? (
            <div className="connection-provider-list">
              {profiles.map((profile) => (
                <article key={profile.id}>
                  <span className="provider-icon">
                    {profile.provider_type === "openai"
                      ? "O"
                      : profile.provider_type === "anthropic"
                        ? "A"
                        : "↔"}
                  </span>
                  <div className="provider-primary">
                    <strong>{profile.name}</strong>
                    <small>{profile.model || profile.provider_type} · {profile.host_origin || "Host not declared"}</small>
                    <span>
                      <Badge tone={tierTone(profile.effective_trust_tier || profile.trust_tier)}>
                        Tier {profile.effective_trust_tier || profile.trust_tier}
                      </Badge>
                      <Badge tone={profile.ai_eligible ? "success" : "danger"}>
                        {profile.ai_eligible ? "Chat eligible" : "Chat blocked"}
                      </Badge>
                      <Badge tone={profile.task_eligibility?.outreach_draft ? "success" : "neutral"}>
                        {profile.task_eligibility?.outreach_draft
                          ? "Outreach eligible"
                          : "Outreach blocked"}
                      </Badge>
                      <Badge tone={healthTone(profile.last_health_status)}>
                        {profile.last_health_status || "unknown"}
                      </Badge>
                    </span>
                  </div>
                  <dl>
                    <div><dt>Jurisdiction</dt><dd>{profile.jurisdiction}</dd></div>
                    <div><dt>Retention</dt><dd>{retentionLabel(profile.retention_policy)}</dd></div>
                    <div><dt>Credential</dt><dd>{profile.credential_source.replaceAll("_", " ")}</dd></div>
                    <div>
                      <dt>Usage today</dt>
                      <dd>
                        {profile.usage?.today.requests || 0}
                        {profile.rpd_limit ? ` / ${profile.rpd_limit}` : ""}
                      </dd>
                    </div>
                  </dl>
                  <div className="connection-provider-actions">
                    <Button
                      tone="ghost"
                      busy={busy === `test-${profile.id}`}
                      onClick={() => void testProvider(profile)}
                    >
                      Test
                    </Button>
                    <Button tone="ghost" onClick={() => openEditProvider(profile)}>Edit</Button>
                    <Button
                      tone="ghost"
                      busy={busy === `delete-${profile.id}`}
                      onClick={() => void removeProvider(profile)}
                    >
                      Remove
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="connection-empty">
              <strong>No AI provider is configured</strong>
              <p>Local templates and CRM features still work. Add a provider only when you are ready to verify its terms and trust tier.</p>
              <Button onClick={openNewProvider}>Add first provider</Button>
            </div>
          )}
        </Panel>

        <Panel
          title="Bring-your-own tools"
          subtitle="Pinned public GitHub code; read-only container; no network, credentials, mailbox, or CRM access"
          className="connections-wide"
          action={<Button tone="secondary" onClick={() => setToolOpen(true)}>Register GitHub tool</Button>}
        >
          {tools.loading || tools.error ? (
            <Loadable loading={tools.loading} error={tools.error} />
          ) : tools.data?.items.length ? (
            <div className="registered-tool-list">
              {tools.data.items.map((tool) => (
                <article key={tool.id}>
                  <span className="tool-logo">&lt;/&gt;</span>
                  <div>
                    <strong>{tool.name}</strong>
                    <small>{tool.repository_url} · {tool.commit_sha.slice(0, 12)}</small>
                    {tool.description ? <p>{tool.description}</p> : null}
                    <span>
                      <Badge tone={tool.status === "prepared" ? "success" : tool.status.includes("failed") ? "danger" : "warning"}>{tool.status.replaceAll("_", " ")}</Badge>
                      <Badge tone="success">network none</Badge>
                      <Badge tone="blue">public input only</Badge>
                    </span>
                    {tool.last_error ? <p className="error-text">{tool.last_error}</p> : null}
                  </div>
                  <dl>
                    <div><dt>Image</dt><dd>{tool.image}</dd></div>
                    <div><dt>Command</dt><dd><code>{JSON.stringify(tool.command)}</code></dd></div>
                  </dl>
                  <div>
                    {tool.status !== "prepared" ? (
                      <Button
                        tone="secondary"
                        busy={busy === `tool-prepare-${tool.id}`}
                        onClick={() => void prepareTool(tool)}
                      >
                        Prepare pinned commit
                      </Button>
                    ) : (
                      <Button
                        onClick={() => {
                          setRunTool(tool);
                          setToolResult(null);
                        }}
                      >
                        Run sandboxed
                      </Button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="connection-empty">
              <strong>No external tools registered</strong>
              <p>Register only a public GitHub repository at an immutable commit. OFF_CRM fetches no submodules and executes it with Docker network disabled.</p>
              <Button onClick={() => setToolOpen(true)}>Register first tool</Button>
            </div>
          )}
        </Panel>

        <Panel
          title="Provider egress audit"
          subtitle="Exact packets, blocked calls, quota use, and model identity"
          className="connections-wide"
          action={<Button tone="ghost" onClick={egress.reload}>Refresh</Button>}
        >
          {egress.loading || egress.error ? (
            <Loadable loading={egress.loading} error={egress.error} />
          ) : egress.data?.items.length ? (
            <div className="table-wrap">
              <table className="connection-audit-table">
                <thead>
                  <tr>
                    <th>Time</th><th>Status</th><th>Provider</th><th>Task</th>
                    <th>Data class</th><th>Trust</th><th>Tokens</th><th>Cost</th><th />
                  </tr>
                </thead>
                <tbody>
                  {egress.data.items.map((call) => (
                    <tr key={call.id}>
                      <td>{new Date(call.created_at).toLocaleString()}</td>
                      <td><Badge tone={call.status === "succeeded" ? "success" : call.status === "blocked" ? "danger" : "warning"}>{call.status}</Badge></td>
                      <td><strong>{call.provider_name || "Unresolved"}</strong><small>{call.model || call.provider_type}</small></td>
                      <td>{call.task_type}</td>
                      <td>{call.data_class}</td>
                      <td><Badge tone={tierTone(call.trust_tier)}>Tier {call.trust_tier}</Badge></td>
                      <td>{call.input_tokens + call.output_tokens}</td>
                      <td>{call.estimated_cost ? `$${call.estimated_cost.toFixed(5)}` : "—"}</td>
                      <td><Button tone="ghost" busy={busy === `audit-${call.id}`} onClick={() => void inspectAudit(call.id)}>Inspect</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted-copy">No OFF_AI provider calls are recorded yet.</p>
          )}
        </Panel>
      </div>

      <Modal
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
        title={editing ? `Edit ${editing.name}` : "Add AI provider"}
        description="Classify the host, model, jurisdiction, retention, quotas, and allowed work before the broker can use it."
        wide
      >
        <form className="form-stack provider-connection-form" onSubmit={saveProvider} key={formKey}>
          <div className="lead-form-section">
            <div className="lead-form-heading">
              <span>1</span><div><strong>Connection</strong><small>Server-side credential and endpoint</small></div>
            </div>
            <div className="form-grid">
              <Field label="Profile name"><input name="name" required defaultValue={editing?.name || ""} /></Field>
              <Field label="Workspace owner"><input name="owner" required defaultValue={editing?.owner || "default"} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Provider">
                <select
                  value={providerType}
                  disabled={Boolean(editing)}
                  onChange={(event) => setProviderType(event.target.value)}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="openai_compatible">OpenAI-compatible</option>
                  <option value="template_engine_http">Template service</option>
                </select>
              </Field>
              <Field label="Model ID"><input name="model" required={providerType !== "template_engine_http"} defaultValue={editing?.model || providerDefaults.model} /></Field>
            </div>
            <Field label="Base URL" hint="Use the official endpoint or an owner-controlled gateway.">
              <input
                name="base_url"
                type="url"
                required={["openai_compatible", "template_engine_http"].includes(providerType)}
                defaultValue={editing?.base_url || ""}
                placeholder="https://…"
              />
            </Field>
            <div className="form-grid">
              <Field label={editing ? "Replace API key" : "API key"} hint={editing ? "Leave blank to keep the stored key." : "Encrypted locally before storage."}>
                <input name="api_key" type="password" autoComplete="new-password" />
              </Field>
              <Field label="Environment variable" hint="Alternative to storing a key.">
                <input name="api_key_env" defaultValue={editing?.api_key_env || providerDefaults.env} />
              </Field>
            </div>
          </div>

          <div className="lead-form-section">
            <div className="lead-form-heading">
              <span>2</span><div><strong>Trust classification</strong><small>Default deny unless every required fact is declared</small></div>
            </div>
            <div className="form-grid three-up">
              <Field label="Trust tier">
                <select name="trust_tier" defaultValue={editing?.trust_tier || "D"}>
                  <option value="D">D · Untrusted / blocked</option>
                  <option value="C">C · Explicit public tasks only</option>
                  <option value="B">B · Public non-personal only</option>
                  <option value="A">A · Approved personal-public tasks</option>
                </select>
              </Field>
              <Field label="Jurisdiction"><input name="jurisdiction" required defaultValue={editing?.jurisdiction || providerDefaults.jurisdiction} /></Field>
              <Field label="Terms checked"><input name="terms_checked_at" type="date" defaultValue={editing?.terms_checked_at || ""} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Retention policy">
                <select name="retention_policy" defaultValue={editing?.retention_policy || "unknown"}>
                  <option value="unknown">Unknown</option>
                  <option value="no_training_no_retention">No training, no retention</option>
                  <option value="no_training_limited_retention">No training, limited retention</option>
                  <option value="may_train">May train or retain</option>
                </select>
              </Field>
              <Field label="Host origin"><input name="host_origin" defaultValue={editing?.host_origin || providerDefaults.host} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Model origin"><input name="model_origin" defaultValue={editing?.model_origin || ""} placeholder="Model developer / family" /></Field>
              <Field label="Model-origin jurisdiction"><input name="model_origin_jurisdiction" defaultValue={editing?.model_origin_jurisdiction || ""} /></Field>
            </div>
            <label className="check-line">
              <input
                name="model_origin_input_isolation_verified"
                type="checkbox"
                defaultChecked={editing?.model_origin_input_isolation_verified || false}
              />
              Verified that the host isolates inputs from the model developer
            </label>
          </div>

          <div className="lead-form-section">
            <div className="lead-form-heading">
              <span>3</span><div><strong>Allowed work and failover</strong><small>Explicit task allowlist; same-tier profiles only</small></div>
            </div>
            <div className="provider-task-grid">
              {[
                ["public_general", "Public general chat"],
                ["outreach_draft", "Public-profile outreach draft"],
                ["template_rewrite", "Template rewrite"],
                ["masked_parse_fallback", "Masked parse fallback"],
                ["health_check", "Connection health check"]
              ].map(([value, label]) => (
                <label key={value}>
                  <input
                    name="allowed_task_types"
                    value={value}
                    type="checkbox"
                    defaultChecked={editing?.allowed_task_types.includes(value) || value === "health_check"}
                  />
                  {label}
                </label>
              ))}
            </div>
            <label className="check-line">
              <input name="public_tasks_enabled" type="checkbox" defaultChecked={editing?.public_tasks_enabled || false} />
              Owner explicitly enables public tasks for Tier C
            </label>
            <Field label="Fallback profiles" hint="Only profiles in the same effective trust tier can run.">
              <select name="fallback_profile_ids" multiple defaultValue={editing?.fallback_profile_ids || []}>
                {profiles.filter((profile) => profile.id !== editing?.id).map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} · Tier {profile.effective_trust_tier || profile.trust_tier}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="lead-form-section">
            <div className="lead-form-heading">
              <span>4</span><div><strong>Quota and spend guardrails</strong><small>Zero means no declared provider limit</small></div>
            </div>
            <div className="form-grid three-up">
              <Field label="Requests / minute"><input name="rpm_limit" type="number" min={0} defaultValue={editing?.rpm_limit || 0} /></Field>
              <Field label="Requests / day"><input name="rpd_limit" type="number" min={0} defaultValue={editing?.rpd_limit || 0} /></Field>
              <Field label="Context window"><input name="context_window" type="number" min={0} defaultValue={editing?.context_window || 0} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Input $ / million tokens"><input name="input_cost_per_million" type="number" min={0} step="0.000001" defaultValue={editing?.input_cost_per_million || 0} /></Field>
              <Field label="Output $ / million tokens"><input name="output_cost_per_million" type="number" min={0} step="0.000001" defaultValue={editing?.output_cost_per_million || 0} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Daily cost cap"><input name="daily_cost_cap" type="number" min={0} step="0.01" defaultValue={editing?.daily_cost_cap || 0} /></Field>
              <Field label="Monthly cost cap"><input name="monthly_cost_cap" type="number" min={0} step="0.01" defaultValue={editing?.monthly_cost_cap || 0} /></Field>
            </div>
            <div className="form-grid">
              <Field label="Priority"><input name="priority" type="number" min={1} max={1000} defaultValue={editing?.priority || 100} /></Field>
              <Field label="Timeout seconds"><input name="timeout_seconds" type="number" min={5} max={300} defaultValue={editing?.timeout_seconds || 60} /></Field>
            </div>
            <label className="check-line">
              <input name="enabled" type="checkbox" defaultChecked={editing?.enabled ?? true} />
              Provider profile enabled
            </label>
          </div>

          <div className="danger-note">
            <strong>Tier A is not a self-certification shortcut</strong>
            Tier A remains blocked unless no-training/no-retention terms and a check date are recorded.
            Chinese-origin models hosted elsewhere are downgraded unless input isolation is verified.
          </div>
          <div className="modal-actions sticky-actions">
            <Button type="button" tone="ghost" onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button type="submit" busy={busy === "provider-save"}>Save classified provider</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={toolOpen}
        onClose={() => setToolOpen(false)}
        title="Register a GitHub tool"
        description="Public repository only. A full immutable commit SHA and version-pinned local container image are required."
        wide
      >
        <form className="form-stack" onSubmit={registerTool}>
          <div className="form-grid">
            <Field label="Tool name"><input name="name" required maxLength={120} /></Field>
            <Field label="Public GitHub repository"><input name="repository_url" type="url" required placeholder="https://github.com/owner/repository" /></Field>
          </div>
          <Field label="Full commit SHA" hint="Exactly 40 hexadecimal characters; branches and tags are refused.">
            <input name="commit_sha" required pattern="[0-9a-fA-F]{40}" />
          </Field>
          <div className="form-grid">
            <Field label="Pinned local image" hint="The image must already exist locally; latest is refused.">
              <input name="image" required defaultValue="python:3.12.10-slim-bookworm" />
            </Field>
            <Field label="Command as JSON array">
              <input name="command" required defaultValue={'["python","main.py"]'} />
            </Field>
          </div>
          <Field label="Description"><textarea name="description" rows={3} maxLength={2000} /></Field>
          <div className="danger-note">
            <strong>Intentionally strict</strong>
            The checkout is public and credential-free. At run time the source is mounted read-only,
            Linux capabilities are dropped, the filesystem is read-only, resources are capped, and
            network access is disabled. Only public, non-sensitive input is accepted.
          </div>
          <div className="modal-actions">
            <Button type="button" tone="ghost" onClick={() => setToolOpen(false)}>Cancel</Button>
            <Button type="submit" busy={busy === "tool-register"}>Register pinned tool</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(runTool)}
        onClose={() => setRunTool(null)}
        title={`Run ${runTool?.name || "tool"}`}
        description="Input is preflight-scanned, sent over stdin, and never passed to an AI model."
        wide
      >
        {runTool ? (
          <form className="form-stack" onSubmit={executeRegisteredTool}>
            <Field label="Public input" hint="Email addresses, credentials, local paths, and private-data access instructions are blocked.">
              <textarea name="public_input" rows={9} maxLength={100000} />
            </Field>
            <Field label="Timeout seconds"><input name="timeout_seconds" type="number" min={1} max={120} defaultValue={60} /></Field>
            {toolResult ? (
              <div className={toolResult.status === "succeeded" ? "form-note success-note" : "danger-note"}>
                <strong>{toolResult.status}</strong>
                {toolResult.output ? <pre className="tool-output">{toolResult.output}</pre> : null}
                {toolResult.error ? <pre className="tool-output">{toolResult.error}</pre> : null}
              </div>
            ) : null}
            <div className="modal-actions">
              <Button type="button" tone="ghost" onClick={() => setRunTool(null)}>Close</Button>
              <Button type="submit" busy={busy === `tool-run-${runTool.id}`}>Run with network disabled</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(audit)}
        onClose={() => setAudit(null)}
        title="Exact egress record"
        description="Stored locally so the owner can prove what was sent, why it was allowed or blocked, and which model received it."
        wide
      >
        {audit ? (
          <div className="ai-egress">
            <div className="review-meta">
              <div><span>Provider</span><strong>{audit.provider_name || "Unresolved"}</strong></div>
              <div><span>Model</span><strong>{audit.model || "—"}</strong></div>
              <div><span>Trust</span><strong>Tier {audit.trust_tier}</strong></div>
              <div><span>Status</span><strong>{audit.status}</strong></div>
            </div>
            {audit.blocked_reasons.length ? (
              <div className="danger-note">
                <strong>Blocked reasons</strong>
                {audit.blocked_reasons.map((reason) => <p key={reason}>{reason}</p>)}
              </div>
            ) : null}
            <Field label="Exact constructed payload">
              <textarea readOnly rows={18} value={JSON.stringify(audit.payload, null, 2)} />
            </Field>
            {audit.response_text ? (
              <Field label="Provider response">
                <textarea readOnly rows={10} value={audit.response_text} />
              </Field>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </>
  );
}
