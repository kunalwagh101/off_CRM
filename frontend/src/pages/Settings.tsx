import { useState, type FormEvent } from "react";
import { api, getToken, setToken } from "../api";
import { Button, Field, PageHeader, Panel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type {
  AutomationStatus,
  MemoryItem,
  NotionDatabase,
  NotionExportResult,
  NotionStatus,
  Paginated,
  SettingsStatus
} from "../types";
import { Loadable } from "./shared";

type Template = { id: string; name: string; stage: string; route: string; variant_id: string; version_no: number; active: boolean };

export default function Settings() {
  const { campaignId, notify } = useApp();
  const [busy, setBusy] = useState("");
  const [tokenValue, setTokenValue] = useState(getToken());
  const status = useResource(() => api.get<SettingsStatus>("/settings/status"), []);
  const templates = useResource(() => api.get<Paginated<Template>>("/templates?limit=100"), []);
  const automation = useResource(() => api.get<AutomationStatus>("/automation"), []);
  const memory = useResource(() => api.get<Paginated<MemoryItem>>("/memory?limit=50"), []);
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
      if (!payload.items.length) {
        notify("No databases visible. Share the target database with your Notion integration.", "info");
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not list Notion databases", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveNotionTarget(
    key: "contacts_database_id" | "sales_database_id",
    value: string
  ) {
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
      notify(
        `Notion: ${result.created} created, ${result.updated} updated${result.failed ? `, ${result.failed} failed` : ""}`,
        result.failed ? "error" : "success"
      );
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
      await api.download(`/campaigns/${campaignId}/export?format=${format}`, `off-crm.${format}`);
      notify(`CRM ${format.toUpperCase()} export created`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Export failed", "error");
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
      await api.postDownload("/backups/export", { passphrase: data.get("passphrase") }, "off-crm-backup.oxbackup");
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
      <PageHeader title="Settings" description="Manage local storage, approved learning, automation, backups, expert sources, and templates. Gmail and AI models are managed under Connectors." />
      <div className="settings-grid">
        <Panel title="Local storage" subtitle="SQLite is the source of truth">
          {status.loading || status.error ? <Loadable loading={status.loading} error={status.error} /> : status.data ? (
            <dl className="definition-list">
              <div><dt>Database</dt><dd><code>{status.data.database_path}</code></dd></div>
              <div><dt>Local outbox</dt><dd><code>{status.data.local_outbox}</code></dd></div>
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

        <Panel title="Notion sync" subtitle="One-way export: OFF_CRM stays the source of truth" className="settings-wide">
          {notion.loading ? <Loadable loading error={notion.error ?? ""} /> : notion.data?.connected ? (
            <div className="form-stack">
              <div className="form-note">
                <strong>Connected.</strong>
                <span>Only matching properties in an existing Notion database are filled. Other fields are skipped and reported.</span>
              </div>
              <div className="form-grid">
                <Field label="Contacts go to" hint="Database for the selected campaign's contacts">
                  <select
                    value={notion.data.contacts_database_id}
                    onChange={(event) => saveNotionTarget("contacts_database_id", event.target.value)}
                  >
                    <option value="">Choose a database…</option>
                    {notionDbs.map((db) => <option key={db.id} value={db.id}>{db.title}</option>)}
                    {notion.data.contacts_database_id && !notionDbs.some((db) => db.id === notion.data?.contacts_database_id) ? (
                      <option value={notion.data.contacts_database_id}>Saved database</option>
                    ) : null}
                  </select>
                </Field>
                <Field label="Sales leads go to" hint="Database for sales Kanban leads">
                  <select
                    value={notion.data.sales_database_id}
                    onChange={(event) => saveNotionTarget("sales_database_id", event.target.value)}
                  >
                    <option value="">Choose a database…</option>
                    {notionDbs.map((db) => <option key={db.id} value={db.id}>{db.title}</option>)}
                    {notion.data.sales_database_id && !notionDbs.some((db) => db.id === notion.data?.sales_database_id) ? (
                      <option value={notion.data.sales_database_id}>Saved database</option>
                    ) : null}
                  </select>
                </Field>
              </div>
              <div className="button-row">
                <Button tone="secondary" busy={busy === "notion-dbs"} onClick={loadNotionDatabases}>Load my databases</Button>
                <Button
                  busy={busy === "notion-export-contacts"}
                  disabled={!campaignId || !notion.data.contacts_database_id}
                  onClick={() => exportToNotion("contacts")}
                >
                  Export campaign contacts
                </Button>
                <Button
                  busy={busy === "notion-export-sales"}
                  disabled={!notion.data.sales_database_id}
                  onClick={() => exportToNotion("sales")}
                >
                  Export sales leads
                </Button>
                <Button tone="ghost" onClick={disconnectNotion}>Disconnect</Button>
              </div>
              {notionResult ? (
                <div className="form-note">
                  <strong>Last export: {notionResult.created} created, {notionResult.updated} updated, {notionResult.failed} failed.</strong>
                  {notionResult.skipped_fields.length ? (
                    <span>Skipped fields: {notionResult.skipped_fields.join(", ")}.</span>
                  ) : <span>Every mapped field matched a Notion property.</span>}
                </div>
              ) : null}
            </div>
          ) : (
            <form className="form-stack" onSubmit={connectNotion}>
              <div className="form-note">
                <strong>Connect an internal Notion integration.</strong>
                <span>Share each target database with that integration before loading databases here.</span>
              </div>
              <Field label="Notion integration token" hint="Encrypted on this device. It is never written to the CRM database.">
                <input
                  type="password"
                  value={notionToken}
                  onChange={(event) => setNotionToken(event.target.value)}
                  placeholder="ntn_…"
                  required
                  autoComplete="off"
                />
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
