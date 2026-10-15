import { useEffect, useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable, NoCampaign } from "./shared";
import ContactConversation from "./ContactConversation";
import Contact360 from "./Contact360";

export type FollowupTask = {
  id: string;
  campaign_id: string;
  campaign_contact_id?: string | null;
  contact_name?: string;
  contact_email?: string;
  title: string;
  description: string;
  assigned_to: string;
  due_at: string;
  priority: "normal" | "high";
  status: "open" | "done";
  revision: number;
  completed_at?: string | null;
};

export const FOLLOWUPS_PAGE_SIZE = 50;
export function followupsPath(campaignId: string, page: number, status: string, overdue: boolean): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/followups?limit=${FOLLOWUPS_PAGE_SIZE}&offset=${Math.max(0, page)*FOLLOWUPS_PAGE_SIZE}&status=${status}&overdue_only=${overdue}`;
}

function dueISO(local: string): string {
  const date = new Date(local);
  if (!local || Number.isNaN(date.getTime())) throw new Error("Enter a valid due date and time.");
  return date.toISOString();
}

export function TaskComposer({ campaignId, onClose, onSaved, contactId = null }: {
  campaignId: string;
  onClose: () => void;
  onSaved: () => void;
  contactId?: string | null;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestKey, setRequestKey] = useState(() => idempotencyKey("followup"));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api.post(
        `/campaigns/${encodeURIComponent(campaignId)}/followups`,
        {
          title: String(data.get("title") || "").trim(),
          description: String(data.get("description") || ""),
          assigned_to: String(data.get("assigned_to") || "").trim(),
          due_at: dueISO(String(data.get("due_at") || "")),
          priority: String(data.get("priority") || "normal"),
          campaign_contact_id: contactId
        }, requestKey
      );
      setRequestKey(idempotencyKey("followup"));
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create task");
    } finally { setBusy(false); }
  }
  return <form className="form-stack" onSubmit={submit}>
    <Field label="Task title"><input name="title" required maxLength={160} placeholder="Call prospect to discuss response" /></Field>
    <Field label="Due date and time"><input name="due_at" type="datetime-local" required /></Field>
    <div className="form-grid">
      <Field label="Assigned to (label only)"><input name="assigned_to" maxLength={100} placeholder="Team member" /></Field>
      <Field label="Priority"><select name="priority"><option value="normal">Normal</option><option value="high">High</option></select></Field>
    </div>
    <Field label="Notes"><textarea name="description" maxLength={2000} rows={3} /></Field>
    <p className="muted">Assignment is a tracking label, not an access-control permission. Creating a task never sends a message.</p>
    {error && <p role="alert">{error}</p>}
    <div className="modal-actions">
      <Button type="button" tone="ghost" onClick={onClose}>Cancel</Button>
      <Button type="submit" busy={busy}>Create follow-up</Button>
    </div>
  </form>;
}

export default function Followups() {
  const { campaignId, activeCampaign, notify } = useApp();
  const [status, setStatus] = useState("open");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<FollowupTask | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [overviewId, setOverviewId] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const tasks = useResource(
    () => campaignId
      ? api.get<{ items: FollowupTask[]; total: number }>(followupsPath(campaignId, page, status, overdueOnly))
      : Promise.resolve({ items: [], total: 0 }),
    [campaignId, page, status, overdueOnly]
  );
  const total = tasks.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / FOLLOWUPS_PAGE_SIZE));
  useEffect(() => {
    if (!tasks.loading && !tasks.error && tasks.data && page >= pages) setPage(pages - 1);
  }, [tasks.loading, tasks.error, tasks.data, page, pages]);

  if (!campaignId) return <><PageHeader title="Follow-up tasks" /><NoCampaign /></>;

  async function update(task: FollowupTask, payload: Record<string, unknown>) {
    setBusy(task.id);
    try {
      await api.patch(`/campaigns/${encodeURIComponent(campaignId)}/followups/${encodeURIComponent(task.id)}`,
        { revision: task.revision, ...payload });
      notify("Follow-up task updated.", "success");
      setEditing(null);
      tasks.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Task update failed; refresh and retry", "error");
      tasks.reload();
    } finally { setBusy(""); }
  }

  function editSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = new FormData(event.currentTarget);
    try {
      void update(editing, {
        title: String(data.get("title") || "").trim(),
        description: String(data.get("description") || ""),
        assigned_to: String(data.get("assigned_to") || "").trim(),
        priority: String(data.get("priority") || "normal"),
        due_at: dueISO(String(data.get("due_at") || "")),
      });
    } catch (e) {
      notify(e instanceof Error ? e.message : "Invalid due time", "error");
    }
  }
  function localDateTime(value: string): string {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    const adjusted = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return adjusted.toISOString().slice(0, 16);
  }

  return <>
    <PageHeader eyebrow={activeCampaign?.name} title="Human follow-up tasks"
      description="Schedule and track real human actions. No automatic email or outreach."
      actions={<Button onClick={() => setCreateOpen(true)}>New task</Button>} />
    <Panel title="Follow-up worklist">
      <div className="toolbar">
        <select aria-label="Task status" value={status} onChange={e => { setPage(0); setStatus(e.target.value); }}>
          <option value="open">Open tasks</option><option value="done">Completed</option><option value="all">All tasks</option>
        </select>
        <label><input type="checkbox" checked={overdueOnly} onChange={e => { setPage(0); setOverdueOnly(e.target.checked); }} /> Overdue only</label>
        <span>{total} tasks</span>
        <Button tone="ghost" onClick={tasks.reload}>Refresh</Button>
      </div>
      {tasks.loading || tasks.error ? <Loadable loading={tasks.loading} error={tasks.error} /> :
        tasks.data?.items.length ? <div className="form-stack">
          {tasks.data.items.map(task => <article key={task.id} className="panel">
            <div className="toolbar">
              <strong>{task.title}</strong>
              <Badge tone={task.status === "done" ? "success" : task.priority === "high" ? "warning" : "neutral"}>
                {task.status === "done" ? "Completed" : task.priority === "high" ? "High priority" : "Open"}
              </Badge>
              {task.status === "open" && new Date(task.due_at).getTime() < Date.now() ? <Badge tone="warning">Overdue</Badge> : null}
            </div>
            <p className="muted">Due {new Date(task.due_at).toLocaleString()} · Assigned: {task.assigned_to || "Unassigned"}
              {task.contact_name ? ` · ${task.contact_name}` : ""}</p>
            {task.description && <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{task.description}</p>}
            <div className="toolbar">
              <Button tone="secondary" disabled={busy === task.id} onClick={() => update(task, {
                status: task.status === "done" ? "open" : "done"
              })}>{task.status === "done" ? "Reopen" : "Complete"}</Button>
              <Button tone="ghost" onClick={() => setEditing(task)}>Edit</Button>
              {task.campaign_contact_id && <Button tone="ghost" onClick={() => setConversationId(task.campaign_contact_id || null)}>Conversation</Button>}
              {task.campaign_contact_id && <Button tone="ghost" onClick={() => setOverviewId(task.campaign_contact_id || null)}>Contact 360</Button>}
            </div>
          </article>)}
        </div> : <StatePanel title="No follow-ups match"
          description="Create a task for a reply, call or meeting that needs a human response."
          action={<Button onClick={() => setCreateOpen(true)}>Create task</Button>} />}
      {total > FOLLOWUPS_PAGE_SIZE && !tasks.loading && !tasks.error && <nav className="toolbar" aria-label="Follow-up pages">
        <span>Page {page + 1} of {pages}</span>
        <Button tone="ghost" disabled={page === 0} onClick={() => setPage(v => Math.max(0,v-1))}>Previous</Button>
        <Button tone="ghost" disabled={page+1 >= pages} onClick={() => setPage(v => v+1)}>Next</Button>
      </nav>}
    </Panel>
    <Modal open={createOpen} title="New follow-up task" onClose={() => setCreateOpen(false)}>
      <TaskComposer campaignId={campaignId} onClose={() => setCreateOpen(false)} onSaved={tasks.reload} />
    </Modal>
    <Modal open={Boolean(editing)} title="Edit follow-up task" onClose={() => setEditing(null)}>
      {editing && <form key={editing.id} className="form-stack" onSubmit={editSubmit}>
        <Field label="Task title"><input name="title" required maxLength={160} defaultValue={editing.title} /></Field>
        <Field label="Due date and time"><input name="due_at" type="datetime-local" required defaultValue={localDateTime(editing.due_at)} /></Field>
        <div className="form-grid">
          <Field label="Assigned to"><input name="assigned_to" maxLength={100} defaultValue={editing.assigned_to} /></Field>
          <Field label="Priority"><select name="priority" defaultValue={editing.priority}><option value="normal">Normal</option><option value="high">High</option></select></Field>
        </div>
        <Field label="Notes"><textarea name="description" maxLength={2000} rows={3} defaultValue={editing.description} /></Field>
        <div className="modal-actions">
          <Button type="button" tone="ghost" onClick={() => setEditing(null)}>Cancel</Button>
          <Button type="submit" busy={busy === editing.id}>Save task</Button>
        </div>
      </form>}
    </Modal>
    <Contact360 campaignId={campaignId} membershipId={overviewId} onClose={() => setOverviewId(null)} />
    <ContactConversation campaignId={campaignId} membershipId={conversationId} onClose={() => setConversationId(null)} />
  </>;
}
