import { useState, type FormEvent } from "react";
import { PROVIDER_CATALOG, REGIONS, type CatalogEntry } from "../providerCatalog";
import { api, getToken, setToken } from "../api";
import { Badge, Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { AutomationStatus, MemoryItem, NotionDatabase, NotionExportResult, NotionStatus, Paginated, ProviderCall, ProviderProfile, SettingsStatus } from "../types";
import { Loadable } from "./shared";

type Template = { id: string; name: string; stage: string; route: string; variant_id: string; version_no: number; active: boolean };

export default function Settings() {
  const { campaignId, notify } = useApp();
  const [busy, setBusy] = useState("");
  const [tokenValue, setTokenValue] = useState(getToken());
  const [providerType, setProviderType] = useState("openai");
  const [catalogStep, setCatalogStep] = useState<"pick" | "configure">("pick");
  const [selectedEntry, setSelectedEntry] = useState<CatalogEntry | null>(null);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [catalogKey, setCatalogKey] = useState("");
  const [catalogName, setCatalogName] = useState("");
  const status = useResource(() => api.get<SettingsStatus>("/settings/status"), []);
  const templates = useResource(() => api.get<Paginated<Template>>("/templates?limit=100"), []);
  const profiles = useResource(() => api.get<Paginated<ProviderProfile>>("/provider-profiles"), []);
  const automation = useResource(() => api.get<AutomationStatus>("/automation"), []);
  const memory = useResource(() => api.get<Paginated<MemoryItem>>("/memory?limit=50"), []);
  const providerCalls = useResource(() => api.get<Paginated<ProviderCall>>("/provider-calls?limit=25"), []);
  const notion = useResource(() => api.get<NotionStatus>("/notion/settings"), []);
  const [notionToken, setNotionToken] = useState("");
  const [notionDbs, setNotionDbs] = useState<NotionDatabase[]>([]);
  const [notionResult, setNotionResult] = useState<NotionExportResult | null>(null);

  async function connectNotion(event: FormEvent) {
    event.preventDefault();
    setBusy("notion-connect");
    try {
      await api.post("/notion/settings", { token: notionToken });
      const check = await api.post<{ ok: boolean; bot_name: string }>("/notion/test", {});
      notify(`Notion connected${check.bot_name ? ` as ${check.bot_name}` : ""}`, "success");
      setNotionToken("");
      await notion.reload();
      await loadNotionDatabases();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Notion connection failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function loadNotionDatabases() {
    setBusy("notion-dbs");
    try {
      const payload = await api.get<{ items: NotionDatabase[] }>("/notion/databases");
      setNotionDbs(payload.items);
      if (!payload.items.length) notify("No databases visible. In Notion, open the database, Share, and invite your integration.", "info");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not list Notion databases", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveNotionTarget(key: "contacts_database_id" | "sales_database_id", value: string) {
    try {
      await api.post("/notion/settings", { [key]: value });
      await notion.reload();
      notify("Notion target saved", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save Notion target", "error");
    }
  }

  async function exportToNotion(scope: "contacts" | "sales") {
    setBusy(`notion-export-${scope}`);
    setNotionResult(null);
    try {
      const result = await api.post<NotionExportResult>("/notion/export", {
        scope,
        campaign_id: scope === "contacts" ? campaignId : ""
      });
      setNotionResult(result);
      notify(`Notion: ${result.created} created, ${result.updated} updated${result.failed ? `, ${result.failed} failed` : ""}`, result.failed ? "error" : "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Notion export failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function disconnectNotion() {
    if (!window.confirm("Disconnect Notion? The stored token is deleted from this device.")) return;
    await api.post("/notion/disconnect", {});
    setNotionDbs([]);
    setNotionResult(null);
    await notion.reload();
    notify("Notion disconnected", "success");
  }

  function saveToken(event: FormEvent) {
    event.preventDefault();
    setToken(tokenValue);
    notify(tokenValue ? "Local API token saved for this browser session" : "Local API token cleared", "success");
    status.reload();
  }

  async function importSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const data = new FormData(formElement);
    setBusy("source");
    try {
      const result = await api.upload<{ documents: number; chunks_added: number; chunks_skipped: number }>("/expert-sources/import", data);
      notify(`${result.chunks_added} expert-guidance chunks added, ${result.chunks_skipped} duplicates skipped`, "success");
      formElement.reset();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Source import failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function exportCrm(format: "xlsx" | "csv") {
    if (!campaignId) {
      notify("Choose a campaign first", "info");
      return;
    }
    setBusy(format);
    try {
      await api.download(`/campaigns/${campaignId}/export?format=${format}`, `off_crm.${format}`);
      notify(`CRM ${format.toUpperCase()} export created`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Export failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveCatalogProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEntry) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("provider-save");
    try {
      await api.post<ProviderProfile>("/provider-profiles", {
        owner: "default",
        name: catalogName || selectedEntry.defaultName,
        provider_type: selectedEntry.providerType,
        model: selectedEntry.defaultModel,
        api_key: catalogKey,
        base_url: selectedEntry.baseUrl || "",
        timeout_seconds: 60,
        priority: Number(data.get("priority") || 100),
        enabled: true,
        data_policy: "minimal",
        audit_payloads: false,
        fallback_strategy: "priority",
        extra: {}
      });
      notify(`${selectedEntry.name} connected. Key encrypted locally.`, "success");
      form.reset();
      setCatalogKey("");
      setCatalogName("");
      setSelectedEntry(null);
      setCatalogStep("pick");
      profiles.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider could not be saved", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("provider-save");
    try {
      await api.post<ProviderProfile>("/provider-profiles", {
        owner: String(data.get("owner") || "default"),
        name: data.get("name"),
        provider_type: providerType,
        model: data.get("model"),
        api_key_env: data.get("api_key_env"),
        api_key: data.get("api_key"),
        base_url: data.get("base_url"),
        timeout_seconds: 60,
        priority: Number(data.get("priority") || 100),
        enabled: true,
        data_policy: data.get("data_policy"),
        audit_payloads: data.get("audit_payloads") === "on",
        fallback_strategy: data.get("fallback_strategy"),
        extra: {}
      });
      notify("Provider profile saved. The key is encrypted locally.", "success");
      form.reset();
      setProviderType("openai");
      setShowCustomForm(false);
      profiles.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider profile could not be saved", "error");
    } finally {
      setBusy("");
    }
  }

  async function testProvider(profile: ProviderProfile) {
    setBusy(`provider-test-${profile.id}`);
    try {
      const result = await api.post<{ status: string }>(`/provider-profiles/${profile.id}/test`, { live_probe: true });
      notify(`${profile.name}: ${result.status}`, "success");
      profiles.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider test failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function removeProvider(profile: ProviderProfile) {
    if (!window.confirm(`Remove ${profile.name}?`)) return;
    setBusy(`provider-delete-${profile.id}`);
    try {
      await api.post(`/provider-profiles/${profile.id}/delete`, {});
      notify(`${profile.name} removed`, "success");
      profiles.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider could not be removed", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveAutomation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("automation-save");
    try {
      const updated = await api.patch<AutomationStatus>("/automation", {
        enabled: data.get("enabled") === "on",
        mode: data.get("mode"),
        interval_seconds: Number(data.get("interval_seconds") || 300),
        max_messages_per_campaign: Number(data.get("max_messages_per_campaign") || 25),
        sync_replies_first: data.get("sync_replies_first") === "on",
        gmail_confirmation: data.get("gmail_confirmation")
      });
      notify(updated.enabled ? "Automation enabled" : "Automation paused", "success");
      automation.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Automation settings could not be saved", "error");
    } finally {
      setBusy("");
    }
  }

  async function runAutomation() {
    setBusy("automation-run");
    try {
      const result = await api.post<{ total: number }>("/automation/run", {});
      notify(`Automation checked ${result.total} active campaigns`, "success");
      automation.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Automation run failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function exportBackup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("backup-export");
    try {
      await api.postDownload("/backups/export", { passphrase: data.get("passphrase") }, "off_crm-backup.oxbackup");
      notify("Encrypted backup created", "success");
      event.currentTarget.reset();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Backup failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function restoreBackup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("Restore this backup and replace the current local workspace?")) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("backup-restore");
    try {
      await api.upload("/backups/restore", data);
      notify("Backup restored. Reloading the workspace.", "success");
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Restore failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function addMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("memory-add");
    try {
      await api.post("/memory", {
        content: data.get("content"),
        kind: data.get("kind"),
        scope: data.get("scope"),
        tags: String(data.get("tags") || "").split(",").map((item) => item.trim()).filter(Boolean)
      });
      notify("Approved memory added", "success");
      form.reset();
      memory.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Memory could not be added", "error");
    } finally {
      setBusy("");
    }
  }

  async function toggleMemory(item: MemoryItem) {
    try {
      await api.patch(`/memory/${item.id}`, { approved: !item.approved });
      memory.reload();
      status.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Memory approval failed", "error");
    }
  }

  return (
    <>
      <PageHeader title="Settings" description="Credentials and data stay on this device. Stored provider keys are encrypted locally and never written to the CRM database." />
      <div className="settings-grid">
        <Panel title="Local storage" subtitle="SQLite is the source of truth">
          {status.loading || status.error ? <Loadable loading={status.loading} error={status.error} /> : status.data ? (
            <dl className="definition-list">
              <div><dt>Database</dt><dd><code>{status.data.database_path}</code></dd></div>
              <div><dt>Local outbox</dt><dd><code>{status.data.local_outbox}</code></dd></div>
              <div><dt>Gmail</dt><dd><Badge tone={status.data.gmail_configured ? "success" : "warning"}>{status.data.gmail_configured ? `Connected as ${status.data.own_email}` : "Not connected"}</Badge></dd></div>
              <div><dt>Expert library</dt><dd>{Object.values(status.data.expert_sources).reduce((sum, value) => sum + value, 0)} indexed chunks</dd></div>
              <div><dt>Memory</dt><dd>{status.data.memory.approved}/{status.data.memory.total} approved items</dd></div>
            </dl>
          ) : null}
          <div className="button-row"><Button busy={busy === "xlsx"} onClick={() => exportCrm("xlsx")}>Export CRM XLSX</Button><Button tone="secondary" busy={busy === "csv"} onClick={() => exportCrm("csv")}>Export CSV</Button></div>
        </Panel>

        <Panel title="Local API security" subtitle="Required when the backend is configured with a token">
          <form className="form-stack" onSubmit={saveToken}>
            <Field label="Session token" hint="Saved in session storage and removed when this browser session ends."><input type="password" value={tokenValue} onChange={(event) => setTokenValue(event.target.value)} autoComplete="off" /></Field>
            <div><Button type="submit">Save token</Button></div>
          </form>
        </Panel>

        <Panel title="AI providers" subtitle="Connect one or more AI providers. The system tries them in priority order and switches automatically on failure." className="settings-wide">

          {/* ── Active providers ─────────────────────────────────────────── */}
          {profiles.loading || profiles.error ? <Loadable loading={profiles.loading} error={profiles.error ?? ""} /> : profiles.data?.items.length ? (
            <div className="provider-list">
              {profiles.data.items.map((profile) => {
                const catalog = PROVIDER_CATALOG.find((c) => {
                  if (profile.provider_type === "openai" && c.id === "openai") return true;
                  if (profile.provider_type === "anthropic" && c.id === "anthropic") return true;
                  return c.baseUrl === profile.base_url;
                });
                return (
                  <div key={profile.id} className="provider-row">
                    <span className="provider-icon">{catalog?.flag || (profile.provider_type === "openai" ? "🤖" : profile.provider_type === "anthropic" ? "🧠" : "⚡")}</span>
                    <div className="provider-row-info">
                      <strong>{profile.name}</strong>
                      <small>{profile.model || profile.provider_type} · priority {profile.priority} · {profile.data_policy} data</small>
                    </div>
                    <Badge tone={profile.credential_source === "none" ? "warning" : "success"}>{profile.credential_source.replaceAll("_", " ")}</Badge>
                    <Badge tone={profile.last_health_status === "healthy" ? "success" : profile.last_health_status === "unhealthy" ? "danger" : "neutral"}>{profile.last_health_status}</Badge>
                    <Button tone="ghost" busy={busy === `provider-test-${profile.id}`} onClick={() => testProvider(profile)}>Test</Button>
                    <Button tone="ghost" busy={busy === `provider-delete-${profile.id}`} onClick={() => removeProvider(profile)}>Remove</Button>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="muted-copy">No provider connected yet. Pick one below — the system works fine with templates only until you do.</p>
          )}

          {/* ── Catalog picker ───────────────────────────────────────────── */}
          {catalogStep === "pick" ? (
            <div className="catalog-section">
              <h4 className="catalog-heading">Add a provider</h4>
              {REGIONS.map((region) => (
                <div key={region} className="catalog-region">
                  <p className="catalog-region-label">{region}</p>
                  <div className="catalog-grid">
                    {PROVIDER_CATALOG.filter((e) => e.region === region).map((entry) => (
                      <div key={entry.id} className="catalog-card-wrapper">
                        <button
                          type="button"
                          className={selectedEntry?.id === entry.id ? "catalog-card catalog-card-active" : "catalog-card"}
                          onClick={() => { setSelectedEntry(entry); setCatalogStep("configure"); setCatalogName(entry.defaultName); }}
                        >
                          <span className="catalog-flag">{entry.flag}</span>
                          <span className="catalog-name">{entry.name}</span>
                          <span className="catalog-tagline">{entry.tagline}</span>
                        </button>
                        <div className="catalog-tooltip" role="tooltip">
                          <strong>How to get the API key</strong>
                          <p>{entry.howToGet}</p>
                          <a href={entry.keyUrl} target="_blank" rel="noopener noreferrer">Get API key →</a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              <button type="button" className="custom-provider-toggle" onClick={() => { setShowCustomForm((v) => !v); setSelectedEntry(null); }}>
                {showCustomForm ? "▲ Hide advanced / custom provider" : "+ Add custom or self-hosted provider"}
              </button>
            </div>
          ) : selectedEntry ? (
            <div className="catalog-configure">
              <button type="button" className="back-link" onClick={() => { setCatalogStep("pick"); setSelectedEntry(null); setCatalogKey(""); }}>← Back to provider list</button>
              <div className="configure-hero">
                <span className="configure-flag">{selectedEntry.flag}</span>
                <div>
                  <strong>{selectedEntry.name}</strong>
                  <small>{selectedEntry.tagline}</small>
                </div>
              </div>
              <div className="configure-howto">
                <strong>How to get your API key</strong>
                <p>{selectedEntry.howToGet}</p>
                <a href={selectedEntry.keyUrl} target="_blank" rel="noopener noreferrer" className="howto-link">Open {selectedEntry.name} API key page →</a>
              </div>
              <form className="form-stack" onSubmit={saveCatalogProvider}>
                <div className="form-grid">
                  <Field label="Profile label" hint="What you will see in the fallback chain above">
                    <input value={catalogName} onChange={(e) => setCatalogName(e.target.value)} placeholder={selectedEntry.defaultName} required />
                  </Field>
                  <Field label="Fallback priority" hint="1 runs before 2 — lowest number wins">
                    <input name="priority" type="number" min="1" max="1000" defaultValue="100" />
                  </Field>
                </div>
                <Field label="API key" hint="Encrypted with Fernet before it touches disk. Never stored in the CRM database.">
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={selectedEntry.keyPlaceholder}
                    value={catalogKey}
                    onChange={(e) => setCatalogKey(e.target.value)}
                  />
                </Field>
                <div className="configure-meta">
                  <span>Model: <code>{selectedEntry.defaultModel}</code></span>
                  {selectedEntry.baseUrl ? <span>Endpoint: <code>{selectedEntry.baseUrl}</code></span> : null}
                  <span>Data policy: <code>minimal</code> (recipient identity stripped before every call)</span>
                </div>
                <div className="button-row">
                  <Button type="submit" busy={busy === "provider-save"}>Connect {selectedEntry.name}</Button>
                  <Button tone="ghost" onClick={() => { setCatalogStep("pick"); setSelectedEntry(null); setCatalogKey(""); }}>Cancel</Button>
                </div>
              </form>
            </div>
          ) : null}

          {/* ── Advanced / custom provider form ──────────────────────────── */}
          {showCustomForm && catalogStep === "pick" ? (
            <form className="form-stack provider-form custom-provider-form" onSubmit={saveProvider}>
              <p className="form-note"><strong>Advanced:</strong> <span>Use this for self-hosted LLMs (Ollama, vLLM, LM Studio) or any OpenAI-compatible endpoint not in the list above.</span></p>
              <div className="form-grid">
                <Field label="Profile name"><input name="name" required placeholder="Local Ollama" /></Field>
                <Field label="Workspace user"><input name="owner" defaultValue="default" required placeholder="Kunal" /></Field>
              </div>
              <div className="form-grid">
                <Field label="Data sent to provider" hint="Minimal removes recipient identity; standard removes direct contact data."><select name="data_policy" defaultValue="minimal"><option value="minimal">Minimal</option><option value="standard">Standard</option><option value="full">Full context</option></select></Field>
                <Field label="Fallback strategy"><select name="fallback_strategy" defaultValue="priority"><option value="priority">Priority</option><option value="round_robin">Round robin</option><option value="parallel">Parallel first-success</option></select></Field>
              </div>
              <label className="check-line"><input name="audit_payloads" type="checkbox" /> Store redacted request/response bodies locally (metadata only by default)</label>
              <div className="form-grid">
                <Field label="Provider type"><select value={providerType} onChange={(event) => setProviderType(event.target.value)}><option value="openai">OpenAI-compatible</option><option value="anthropic">Anthropic</option><option value="openai_compatible">Custom base URL</option><option value="template_engine_http">Template application</option></select></Field>
                <Field label="Fallback priority" hint="1 runs before 2"><input name="priority" type="number" min="1" max="1000" defaultValue="100" /></Field>
              </div>
              <div className="form-grid">
                <Field label="Model ID" hint="Exact model string your provider expects"><input name="model" required={providerType !== "template_engine_http"} placeholder="e.g. llama3:70b" /></Field>
                <Field label="Base URL" hint="Leave blank for OpenAI and Anthropic — they use official endpoints"><input name="base_url" type="url" required={["openai_compatible", "template_engine_http"].includes(providerType)} placeholder="http://localhost:11434/v1" /></Field>
              </div>
              <div className="form-grid">
                <Field label="API key" hint="Encrypted before it is stored — blank is fine for local providers"><input name="api_key" type="password" autoComplete="new-password" /></Field>
                <Field label="Or environment variable" hint="Name of an env var already set on this machine"><input name="api_key_env" placeholder="MY_API_KEY" /></Field>
              </div>
              <div><Button type="submit" busy={busy === "provider-save"}>Save custom provider</Button></div>
            </form>
          ) : null}
        </Panel>

        <Panel title="Learning memory" subtitle="Human edits are approved; reply observations wait for review" className="settings-wide">
          <form className="form-stack" onSubmit={addMemory}>
            <Field label="Reusable instruction"><textarea name="content" rows={4} required placeholder="Use this as an approved rule during generation..." /></Field>
            <div className="form-grid"><Field label="Kind"><input name="kind" defaultValue="playbook" /></Field><Field label="Scope"><input name="scope" defaultValue="global" /></Field></div>
            <Field label="Tags"><input name="tags" placeholder="cta, concise, followup1" /></Field>
            <div><Button type="submit" busy={busy === "memory-add"}>Add approved memory</Button></div>
          </form>
          <div className="memory-list">
            {memory.loading || memory.error ? <Loadable loading={memory.loading} error={memory.error} /> : memory.data?.items.map((item) => <div key={item.id}><p><strong>{item.kind}</strong><small>{item.scope} · {Math.round(item.confidence * 100)}% confidence</small><span>{item.content}</span></p><Button tone="ghost" onClick={() => toggleMemory(item)}>{item.approved ? "Unapprove" : "Approve"}</Button></div>)}
          </div>
        </Panel>

        <Panel title="AI request audit" subtitle="Inspect exactly what was sent; payload bodies are off unless explicitly enabled" className="settings-wide">
          {providerCalls.loading || providerCalls.error ? <Loadable loading={providerCalls.loading} error={providerCalls.error} /> : providerCalls.data?.items.length ? <div className="audit-call-list">{providerCalls.data.items.map((call) => <details key={call.id}><summary><Badge tone={call.status === "succeeded" ? "success" : "danger"}>{call.status}</Badge> {call.provider_type} · {call.model || "default"} · {call.data_policy} · {call.duration_ms} ms</summary><pre>{JSON.stringify({ request: call.request, response: call.response, error: call.error }, null, 2)}</pre></details>)}</div> : <p className="muted-copy">No provider calls recorded yet.</p>}
        </Panel>

        <Panel title="Campaign automation" subtitle="Runs reply sync first, then sends only approved and due drafts">
          {automation.loading || automation.error ? <Loadable loading={automation.loading} error={automation.error} /> : automation.data ? (
            <form className="form-stack" onSubmit={saveAutomation}>
              <div className="form-grid">
                <Field label="Execution mode"><select name="mode" defaultValue={automation.data.mode}><option value="local">Local outbox safe mode</option><option value="gmail">Live Gmail</option></select></Field>
                <Field label="Check every (seconds)"><input name="interval_seconds" type="number" min="60" max="86400" defaultValue={automation.data.interval_seconds} /></Field>
              </div>
              <Field label="Maximum messages per campaign per cycle"><input name="max_messages_per_campaign" type="number" min="1" max="500" defaultValue={automation.data.max_messages_per_campaign} /></Field>
              <label className="check-line"><input name="enabled" type="checkbox" defaultChecked={automation.data.enabled} /> Enable background automation</label>
              <label className="check-line"><input name="sync_replies_first" type="checkbox" defaultChecked={automation.data.sync_replies_first} /> Check replies before every send cycle</label>
              <Field label="Live Gmail confirmation" hint="Only needed when first enabling Gmail mode"><input name="gmail_confirmation" placeholder="ENABLE AUTOMATED GMAIL" autoComplete="off" /></Field>
              {automation.data.last_error ? <p className="error-text">{automation.data.last_error}</p> : null}
              <div className="button-row"><Button type="submit" busy={busy === "automation-save"}>Save automation</Button><Button type="button" tone="secondary" busy={busy === "automation-run"} onClick={runAutomation}>Run one cycle now</Button></div>
            </form>
          ) : null}
        </Panel>

        <Panel title="Notion sync" subtitle="One-way export: the CRM stays the source of truth, Notion gets a live copy" className="settings-wide">
          {notion.loading ? <Loadable loading error={notion.error ?? ""} /> : notion.data?.connected ? (
            <div className="form-stack">
              <div className="form-note"><strong>Connected.</strong><span>Pick where each export goes. Only properties that already exist in your Notion database are filled; everything else is skipped and listed after the export.</span></div>
              <div className="form-grid">
                <Field label="Contacts go to" hint="Notion database for campaign contacts">
                  <select value={notion.data.contacts_database_id} onChange={(event) => saveNotionTarget("contacts_database_id", event.target.value)}>
                    <option value="">Choose a database…</option>
                    {notionDbs.map((db) => <option key={db.id} value={db.id}>{db.title}</option>)}
                    {notion.data.contacts_database_id && !notionDbs.some((db) => db.id === notion.data?.contacts_database_id) ? <option value={notion.data.contacts_database_id}>Saved database</option> : null}
                  </select>
                </Field>
                <Field label="Sales leads go to" hint="Notion database for Kanban leads">
                  <select value={notion.data.sales_database_id} onChange={(event) => saveNotionTarget("sales_database_id", event.target.value)}>
                    <option value="">Choose a database…</option>
                    {notionDbs.map((db) => <option key={db.id} value={db.id}>{db.title}</option>)}
                    {notion.data.sales_database_id && !notionDbs.some((db) => db.id === notion.data?.sales_database_id) ? <option value={notion.data.sales_database_id}>Saved database</option> : null}
                  </select>
                </Field>
              </div>
              <div className="button-row">
                <Button tone="secondary" busy={busy === "notion-dbs"} onClick={loadNotionDatabases}>Load my databases</Button>
                <Button busy={busy === "notion-export-contacts"} disabled={!campaignId || !notion.data.contacts_database_id} onClick={() => exportToNotion("contacts")}>Export campaign contacts</Button>
                <Button busy={busy === "notion-export-sales"} disabled={!notion.data.sales_database_id} onClick={() => exportToNotion("sales")}>Export sales leads</Button>
                <Button tone="ghost" onClick={disconnectNotion}>Disconnect</Button>
              </div>
              {notionResult ? (
                <div className="form-note">
                  <strong>Last export: {notionResult.created} created, {notionResult.updated} updated, {notionResult.failed} failed.</strong>
                  {notionResult.skipped_fields.length ? <span>Not in your Notion database, so skipped: {notionResult.skipped_fields.join(", ")}. Add these as properties in Notion if you want them filled.</span> : <span>Every mapped field matched a Notion property.</span>}
                </div>
              ) : null}
            </div>
          ) : (
            <form className="form-stack" onSubmit={connectNotion}>
              <div className="form-note"><strong>Two-minute setup.</strong><span>In Notion: Settings → Connections → Develop or manage integrations → New integration. Copy the secret token here. Then open the target database in Notion and share it with the integration.</span></div>
              <Field label="Notion integration token" hint="Stored encrypted on this device only. Never written to the CRM database.">
                <input type="password" value={notionToken} onChange={(event) => setNotionToken(event.target.value)} placeholder="ntn_…" required autoComplete="off" />
              </Field>
              <div><Button type="submit" busy={busy === "notion-connect"}>Connect and test</Button></div>
            </form>
          )}
        </Panel>

        <Panel title="Encrypted backup" subtitle="Portable local backup of CRM, provider profiles and automation settings">
          <form className="form-stack" onSubmit={exportBackup}>
            <Field label="Backup passphrase" hint="Minimum 12 characters. It cannot be recovered."><input name="passphrase" type="password" minLength={12} required autoComplete="new-password" /></Field>
            <div><Button type="submit" busy={busy === "backup-export"}>Create encrypted backup</Button></div>
          </form>
          <hr />
          <form className="form-stack" onSubmit={restoreBackup}>
            <Field label="Backup file"><input name="file" type="file" accept=".oxbackup" required /></Field>
            <Field label="Backup passphrase"><input name="passphrase" type="password" minLength={12} required /></Field>
            <div><Button type="submit" tone="danger" busy={busy === "backup-restore"}>Restore backup</Button></div>
          </form>
        </Panel>

        <Panel title="Email expert sources" subtitle="Import owned, licensed or permissioned notes only">
          <form className="form-stack" onSubmit={importSource}>
            <Field label="Markdown or text notes"><input name="file" type="file" accept=".md,.txt" required /></Field>
            <div className="form-grid"><Field label="Expert / source name"><input name="expert_name" placeholder="Source name" /></Field><Field label="Tags"><input name="tags" placeholder="cold-email, CTA" /></Field></div>
            <Field label="Public source URL"><input name="source_url" type="url" placeholder="https://..." /></Field>
            <div className="form-grid">
              <Field label="Source type"><select name="source_type" defaultValue="notes"><option value="notes">Notes</option><option value="transcript">Transcript</option><option value="course_notes">Course notes</option><option value="owned_notes">Owned notes</option></select></Field>
              <Field label="Rights basis"><select name="rights_basis" defaultValue="user_provided"><option value="user_provided">User provided</option><option value="owned">Owned</option><option value="licensed">Licensed</option><option value="permission_granted">Permission granted</option><option value="public_domain">Public domain</option><option value="fair_use_notes">Fair-use notes</option></select></Field>
            </div>
            <div className="form-note"><strong>Do not upload copied paid courses.</strong><span>Use your licensed notes, permitted transcripts or public material with provenance.</span></div>
            <div><Button type="submit" busy={busy === "source"}>Index source</Button></div>
          </form>
        </Panel>

        <Panel title="Template library" subtitle={`${templates.data?.total ?? 0} active versioned templates`} className="settings-wide">
          {templates.loading || templates.error ? <Loadable loading={templates.loading} error={templates.error} /> : (
            <div className="template-grid">{templates.data?.items.map((template) => <div key={template.id}><span className="template-stage">{template.stage}</span><strong>{template.name}</strong><small>{template.route} · Variant {template.variant_id} · v{template.version_no}</small></div>)}</div>
          )}
        </Panel>
      </div>
    </>
  );
}
