import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable, NoCampaign } from "./shared";
import ContactConversation from "./ContactConversation";
import Contact360 from "./Contact360";
import { TaskComposer } from "./Followups";

type ReplyItem = {
  campaign_contact_id: string;
  full_name: string;
  email: string;
  company: string;
  status: string;
  subject: string;
  reply_preview: string;
  received_at: string;
  review_status: "unreviewed" | "triaged";
  outcome: string;
  triage_note: string;
};
export const REPLIES_PAGE_SIZE = 50;
export function inboxPath(campaignId: string, page: number, review: string, outcome: string): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/replies/inbox?limit=${REPLIES_PAGE_SIZE}&offset=${Math.max(0,page)*REPLIES_PAGE_SIZE}&review_status=${review}&outcome=${outcome}`;
}

const OUTCOMES = [
  ["", "Unclassified"], ["positive", "Positive"], ["neutral", "Neutral"],
  ["negative", "Negative"], ["meeting", "Meeting"], ["not_interested", "Not interested"],
  ["wrong_person", "Wrong person"]
] as const;

export default function ReplyInbox() {
  const { campaignId, activeCampaign, notify } = useApp();
  const [review, setReview] = useState("unreviewed");
  const [outcome, setOutcome] = useState("");
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<ReplyItem | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [overviewId, setOverviewId] = useState<string | null>(null);
  const [taskFor, setTaskFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inbox = useResource(
    () => campaignId
      ? api.get<{ items: ReplyItem[]; total: number }>(inboxPath(campaignId, page, review, outcome))
      : Promise.resolve({ items: [], total: 0 }),
    [campaignId, page, review, outcome]
  );
  const total = inbox.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / REPLIES_PAGE_SIZE));
  useEffect(() => {
    if (!inbox.loading && !inbox.error && inbox.data && page >= pages) setPage(pages - 1);
  }, [inbox.loading, inbox.error, inbox.data, page, pages]);
  if (!campaignId) return <><PageHeader title="Reply inbox" /><NoCampaign /></>;

  async function triage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api.patch(
        `/campaigns/${encodeURIComponent(campaignId)}/replies/${encodeURIComponent(editing.campaign_contact_id)}/triage`,
        {
          review_status: String(form.get("review_status") || "unreviewed"),
          outcome: String(form.get("outcome") || ""),
          note: String(form.get("note") || "")
        }
      );
      notify("Reply review saved. Sending status was not changed.", "success");
      setEditing(null);
      inbox.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save reply review", "error");
    } finally { setBusy(false); }
  }

  return <>
    <PageHeader eyebrow={activeCampaign?.name} title="Reply inbox"
      description="Review incoming responses and plan human actions. Triage never starts, resumes or sends a campaign."
      actions={<Button tone="secondary" onClick={inbox.reload}>Refresh replies</Button>} />
    <Panel>
      <div className="toolbar">
        <select aria-label="Review status" value={review} onChange={e => { setPage(0); setReview(e.target.value); }}>
          <option value="unreviewed">Needs review</option>
          <option value="triaged">Reviewed</option>
          <option value="all">All replies</option>
        </select>
        <select aria-label="Reply outcome" value={outcome} onChange={e => { setPage(0); setOutcome(e.target.value); }}>
          <option value="">All outcomes</option>
          {OUTCOMES.filter(([id]) => id).map(([id,label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <span>{total} conversations</span>
      </div>
      {inbox.loading || inbox.error ? <Loadable loading={inbox.loading} error={inbox.error} /> :
        inbox.data?.items.length ? <div className="form-stack">
          {inbox.data.items.map(item => <article className="panel" key={item.campaign_contact_id}>
            <div className="toolbar"><strong>{item.full_name}</strong>
              <Badge tone={item.review_status === "triaged" ? "success" : "warning"}>{item.review_status === "triaged" ? "Reviewed" : "Needs review"}</Badge>
              {item.outcome && <Badge>{item.outcome.replaceAll("_", " ")}</Badge>}
            </div>
            <p className="muted">{item.company} · {item.email} · {new Date(item.received_at).toLocaleString()}</p>
            <strong>{item.subject || "(no subject)"}</strong>
            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.reply_preview}</p>
            {item.triage_note && <p className="muted">Review note: {item.triage_note}</p>}
            <div className="toolbar">
              <Button tone="secondary" onClick={() => setEditing(item)}>Review outcome</Button>
              <Button tone="ghost" onClick={() => setConversationId(item.campaign_contact_id)}>Full conversation</Button>
              <Button tone="ghost" onClick={() => setOverviewId(item.campaign_contact_id)}>Contact 360</Button>
              <Button tone="ghost" onClick={() => setTaskFor(item.campaign_contact_id)}>Create follow-up</Button>
            </div>
          </article>)}
        </div> : <StatePanel title="No replies match these filters"
          description="Sync replies from the Send queue, or switch to All replies to see previously reviewed conversations." />}
      {!inbox.loading && !inbox.error && total > REPLIES_PAGE_SIZE && <nav className="toolbar" aria-label="Reply inbox pages">
        <span>Page {page + 1} of {pages}</span>
        <Button tone="ghost" disabled={page===0} onClick={() => setPage(v => Math.max(0,v-1))}>Previous</Button>
        <Button tone="ghost" disabled={page+1>=pages} onClick={() => setPage(v=>v+1)}>Next</Button>
      </nav>}
    </Panel>
    <Modal open={Boolean(editing)} title="Triage received reply"
      description="Outcome labels are campaign-specific. This does not change reply-stop protection or send permissions."
      onClose={() => setEditing(null)}>
      {editing && <form key={editing.campaign_contact_id} className="form-stack" onSubmit={triage}>
        <Field label="Review status"><select name="review_status" defaultValue={editing.review_status}>
          <option value="unreviewed">Needs review</option><option value="triaged">Reviewed</option>
        </select></Field>
        <Field label="Outcome"><select name="outcome" defaultValue={editing.outcome}>
          {OUTCOMES.map(([value,label]) => <option key={value} value={value}>{label}</option>)}
        </select></Field>
        <Field label="Internal review note"><textarea name="note" rows={4} maxLength={1000} defaultValue={editing.triage_note} /></Field>
        <div className="modal-actions">
          <Button type="button" tone="ghost" onClick={() => setEditing(null)}>Cancel</Button>
          <Button type="submit" busy={busy}>Save review</Button>
        </div>
      </form>}
    </Modal>
    <Modal open={Boolean(taskFor)} title="Create human follow-up task" onClose={() => setTaskFor(null)}>
      {taskFor && <TaskComposer key={taskFor} campaignId={campaignId} contactId={taskFor}
        onClose={() => setTaskFor(null)} onSaved={() => notify("Follow-up created. Review it in Follow-up tasks.", "success")} />}
    </Modal>
    <Contact360 campaignId={campaignId} membershipId={overviewId} onClose={() => setOverviewId(null)} />
    <ContactConversation campaignId={campaignId} membershipId={conversationId} onClose={() => setConversationId(null)} />
  </>;
}
