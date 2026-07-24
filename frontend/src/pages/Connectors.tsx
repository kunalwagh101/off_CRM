import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { PROVIDER_CATALOG, REGIONS, type CatalogEntry } from "../providerCatalog";
import type { Paginated, ProviderProfile } from "../types";
import { Loadable } from "./shared";

export default function Connectors() {
  const { notify } = useApp();
  const [busy, setBusy] = useState("");
  const [catalogStep, setCatalogStep] = useState<"pick" | "configure">("pick");
  const [selectedEntry, setSelectedEntry] = useState<CatalogEntry | null>(null);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [catalogKey, setCatalogKey] = useState("");
  const [catalogName, setCatalogName] = useState("");
  const [providerType, setProviderType] = useState("openai");

  const profiles = useResource(() => api.get<Paginated<ProviderProfile>>("/provider-profiles"), []);

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
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not connect provider", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveCustomProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("custom-save");
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
      notify("Custom provider saved. Key encrypted locally.", "success");
      form.reset();
      setShowCustomForm(false);
      profiles.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider could not be saved", "error");
    } finally {
      setBusy("");
    }
  }

  async function testProvider(profile: ProviderProfile) {
    setBusy(`test-${profile.id}`);
    try {
      const result = await api.post<{ status: string }>(`/provider-profiles/${profile.id}/test`, { live_probe: true });
      notify(`${profile.name}: ${result.status}`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Provider test failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function removeProvider(profile: ProviderProfile) {
    if (!window.confirm(`Remove "${profile.name}"? This deletes the encrypted key.`)) return;
    setBusy(`delete-${profile.id}`);
    try {
      await api.post(`/provider-profiles/${profile.id}/delete`, {});
      profiles.reload();
      notify(`${profile.name} removed`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not remove provider", "error");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="AI Connectors"
        description="Connect AI providers. Keys are encrypted on this device and never leave it. The system tries providers in priority order and fails over automatically."
      />

      {/* ── Connected providers ─────────────────────────────────────────── */}
      <Panel title="Connected providers" subtitle="Lowest priority number runs first on failure">
        {profiles.loading || profiles.error
          ? <Loadable loading={profiles.loading} error={profiles.error ?? ""} />
          : profiles.data?.items.length
          ? (
            <div className="provider-list">
              {profiles.data.items.map((profile) => {
                const catalog = PROVIDER_CATALOG.find((c) =>
                  profile.provider_type === "openai" && c.id === "openai" ? true :
                  profile.provider_type === "anthropic" && c.id === "anthropic" ? true :
                  c.baseUrl === profile.base_url
                );
                return (
                  <div key={profile.id} className="provider-row">
                    <span className="provider-icon">{catalog?.flag || "⚡"}</span>
                    <div className="provider-row-info">
                      <strong>{profile.name}</strong>
                      <small>{profile.model || profile.provider_type} · priority {profile.priority} · {profile.data_policy} data</small>
                    </div>
                    <span className={`badge badge-${profile.credential_source === "none" ? "warning" : "success"}`}>{profile.credential_source.replaceAll("_", " ")}</span>
                    <span className={`badge badge-${profile.last_health_status === "healthy" ? "success" : profile.last_health_status === "unhealthy" ? "danger" : "neutral"}`}>{profile.last_health_status}</span>
                    <Button tone="ghost" busy={busy === `test-${profile.id}`} onClick={() => testProvider(profile)}>Test</Button>
                    <Button tone="ghost" busy={busy === `delete-${profile.id}`} onClick={() => removeProvider(profile)}>Remove</Button>
                  </div>
                );
              })}
            </div>
          )
          : <p className="muted-copy">No provider connected yet. Pick one from the catalog below.</p>
        }
      </Panel>

      {/* ── Catalog ─────────────────────────────────────────────────────── */}
      <Panel title="Add a provider" subtitle="Hover any card to see exactly where to get the API key and what it costs" className="settings-wide">
        {catalogStep === "pick" ? (
          <div className="catalog-section">
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
            <button type="button" className="custom-provider-toggle" onClick={() => setShowCustomForm((v) => !v)}>
              {showCustomForm ? "▲ Hide advanced / self-hosted" : "+ Add custom or self-hosted provider"}
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
              <a href={selectedEntry.keyUrl} target="_blank" rel="noopener noreferrer" className="howto-link">
                Open {selectedEntry.name} API key page →
              </a>
            </div>
            <form className="form-stack" onSubmit={saveCatalogProvider}>
              <div className="form-grid">
                <Field label="Profile label" hint="What you will see in the connected list above">
                  <input value={catalogName} onChange={(e) => setCatalogName(e.target.value)} placeholder={selectedEntry.defaultName} required />
                </Field>
                <Field label="Fallback priority" hint="1 runs before 2 — lowest number wins">
                  <input name="priority" type="number" min="1" max="1000" defaultValue="100" />
                </Field>
              </div>
              <Field label="API key" hint="Encrypted with Fernet before it touches disk. Never stored in the CRM database.">
                <input type="password" autoComplete="new-password" placeholder={selectedEntry.keyPlaceholder} value={catalogKey} onChange={(e) => setCatalogKey(e.target.value)} />
              </Field>
              <div className="configure-meta">
                <span>Model: <code>{selectedEntry.defaultModel}</code></span>
                {selectedEntry.baseUrl ? <span>Endpoint: <code>{selectedEntry.baseUrl}</code></span> : null}
                <span>Data policy: <code>minimal</code> (recipient identity stripped)</span>
              </div>
              <div className="button-row">
                <Button type="submit" busy={busy === "provider-save"}>Connect {selectedEntry.name}</Button>
                <Button tone="ghost" onClick={() => { setCatalogStep("pick"); setSelectedEntry(null); setCatalogKey(""); }}>Cancel</Button>
              </div>
            </form>
          </div>
        ) : null}

        {showCustomForm && catalogStep === "pick" ? (
          <form className="form-stack provider-form custom-provider-form" onSubmit={saveCustomProvider}>
            <p className="form-note"><strong>Advanced:</strong> <span>For self-hosted LLMs (Ollama, vLLM, LM Studio) or any OpenAI-compatible endpoint not in the catalog above.</span></p>
            <div className="form-grid">
              <Field label="Profile name"><input name="name" required placeholder="Local Ollama" /></Field>
              <Field label="Workspace user"><input name="owner" defaultValue="default" required /></Field>
            </div>
            <div className="form-grid">
              <Field label="Data policy"><select name="data_policy" defaultValue="minimal"><option value="minimal">Minimal</option><option value="standard">Standard</option><option value="full">Full context</option></select></Field>
              <Field label="Fallback strategy"><select name="fallback_strategy" defaultValue="priority"><option value="priority">Priority</option><option value="round_robin">Round robin</option><option value="parallel">Parallel</option></select></Field>
            </div>
            <div className="form-grid">
              <Field label="Provider type"><select value={providerType} onChange={(e) => setProviderType(e.target.value)}><option value="openai">OpenAI-compatible</option><option value="anthropic">Anthropic</option><option value="openai_compatible">Custom base URL</option><option value="template_engine_http">Template application</option></select></Field>
              <Field label="Priority"><input name="priority" type="number" min="1" max="1000" defaultValue="100" /></Field>
            </div>
            <div className="form-grid">
              <Field label="Model ID"><input name="model" placeholder="llama3:70b" /></Field>
              <Field label="Base URL" hint="Blank for OpenAI and Anthropic"><input name="base_url" type="url" placeholder="http://localhost:11434/v1" /></Field>
            </div>
            <div className="form-grid">
              <Field label="API key"><input name="api_key" type="password" autoComplete="new-password" /></Field>
              <Field label="Env variable"><input name="api_key_env" placeholder="MY_API_KEY" /></Field>
            </div>
            <div><Button type="submit" busy={busy === "custom-save"}>Save custom provider</Button></div>
          </form>
        ) : null}
      </Panel>
    </div>
  );
}
