import { useState, type FormEvent } from "react";
import { api, getToken, setToken } from "../api";
import { Badge, Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { Paginated, SettingsStatus } from "../types";
import { Loadable } from "./shared";

type Template = { id: string; name: string; stage: string; route: string; variant_id: string; version_no: number; active: boolean };

export default function Settings() {
  const { campaignId, notify } = useApp();
  const [busy, setBusy] = useState("");
  const [tokenValue, setTokenValue] = useState(getToken());
  const status = useResource(() => api.get<SettingsStatus>("/settings/status"), []);
  const templates = useResource(() => api.get<Paginated<Template>>("/templates?limit=100"), []);

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

  return (
    <>
      <PageHeader title="Settings" description="Credentials and data stay on this device. API keys are read from environment variables, never stored in the CRM database." />
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

        <Panel title="AI provider boundary" subtitle="Optional personalisation, never required for template mode">
          <div className="provider-list">
            <div><span className="provider-icon">O</span><p><strong>OpenAI Responses</strong><small>Uses OPENAI_API_KEY from your local environment.</small></p><Badge>Adapter ready</Badge></div>
            <div><span className="provider-icon">A</span><p><strong>Anthropic Messages</strong><small>Uses ANTHROPIC_API_KEY from your local environment.</small></p><Badge>Adapter ready</Badge></div>
            <div><span className="provider-icon">↔</span><p><strong>Compatible endpoint</strong><small>Nvidia, a local gateway or any Chat Completions-compatible API.</small></p><Badge>Adapter ready</Badge></div>
            <div><span className="provider-icon">T</span><p><strong>Future template application</strong><small>Normalized /v1/generate contract keeps this CRM independent.</small></p><Badge tone="blue">Contract ready</Badge></div>
          </div>
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
