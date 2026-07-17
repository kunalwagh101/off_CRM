import { useState, type FormEvent } from "react";
import { api, getToken, setToken } from "../api";
import { Badge, Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { AutomationStatus, Paginated, ProviderProfile, SettingsStatus } from "../types";
import { Loadable } from "./shared";

type Template = { id: string; name: string; stage: string; route: string; variant_id: string; version_no: number; active: boolean };

export default function Settings() {
  const { campaignId, notify } = useApp();
  const [busy, setBusy] = useState("");
  const [tokenValue, setTokenValue] = useState(getToken());
  const [providerType, setProviderType] = useState("openai");
  const status = useResource(() => api.get<SettingsStatus>("/settings/status"), []);
  const templates = useResource(() => api.get<Paginated<Template>>("/templates?limit=100"), []);
  const profiles = useResource(() => api.get<Paginated<ProviderProfile>>("/provider-profiles"), []);
  const automation = useResource(() => api.get<AutomationStatus>("/automation"), []);

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
      await api.download(`/campaigns/${campaignId}/export?format=${format}`, `offsetx-crm.${format}`);
      notify(`CRM ${format.toUpperCase()} export created`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Export failed", "error");
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
        extra: {}
      });
      notify("Provider profile saved. The key is encrypted locally.", "success");
      form.reset();
      setProviderType("openai");
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
      await api.postDownload("/backups/export", { passphrase: data.get("passphrase") }, "offsetx-backup.oxbackup");
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

        <Panel title="AI fallback chain" subtitle="Lowest priority number runs first; failures automatically move to the next provider" className="settings-wide">
          <div className="provider-list">
            {profiles.loading || profiles.error ? <Loadable loading={profiles.loading} error={profiles.error} /> : profiles.data?.items.length ? profiles.data.items.map((profile) => (
              <div key={profile.id}>
                <span className="provider-icon">{profile.provider_type === "openai" ? "O" : profile.provider_type === "anthropic" ? "A" : "↔"}</span>
                <p><strong>{profile.name}</strong><small>{profile.owner} · {profile.model || profile.provider_type} · priority {profile.priority}</small></p>
                <Badge tone={profile.credential_source === "none" ? "warning" : "success"}>{profile.credential_source.replaceAll("_", " ")}</Badge>
                <Button tone="ghost" busy={busy === `provider-test-${profile.id}`} onClick={() => testProvider(profile)}>Test</Button>
                <Button tone="ghost" busy={busy === `provider-delete-${profile.id}`} onClick={() => removeProvider(profile)}>Remove</Button>
              </div>
            )) : <p className="muted-copy">No AI provider configured. Local templates continue to work without one.</p>}
          </div>
          <form className="form-stack provider-form" onSubmit={saveProvider}>
            <div className="form-grid">
              <Field label="Profile name"><input name="name" required placeholder="Primary OpenAI" /></Field>
              <Field label="Workspace user"><input name="owner" defaultValue="default" required placeholder="Kunal" /></Field>
            </div>
            <div className="form-grid">
              <Field label="Provider"><select value={providerType} onChange={(event) => setProviderType(event.target.value)}><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="openai_compatible">NVIDIA / compatible</option><option value="template_engine_http">Template application</option></select></Field>
              <Field label="Fallback priority" hint="1 runs before 2"><input name="priority" type="number" min="1" max="1000" defaultValue="100" /></Field>
            </div>
            <div className="form-grid">
              <Field label="Model ID"><input name="model" required={providerType !== "template_engine_http"} placeholder="Provider model ID" /></Field>
              <Field label="Base URL"><input name="base_url" type="url" required={["openai_compatible", "template_engine_http"].includes(providerType)} placeholder="Official endpoint or local gateway" /></Field>
            </div>
            <div className="form-grid">
              <Field label="API key" hint="Encrypted before it is stored"><input name="api_key" type="password" autoComplete="new-password" /></Field>
              <Field label="Or environment variable"><input name="api_key_env" placeholder="OPENAI_API_KEY" /></Field>
            </div>
            <div><Button type="submit" busy={busy === "provider-save"}>Save provider</Button></div>
          </form>
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
