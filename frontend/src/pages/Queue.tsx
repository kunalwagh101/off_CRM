import { useEffect, useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, stageLabel, useResource } from "../hooks";
import type { AutomationStatus, Paginated, QueueItem } from "../types";
import { Loadable, NoCampaign, statusTone } from "./shared";

type SendResult = {
  sent_count: number;
  daily_limit: number;
  already_sent_today: number;
  remaining_today: number;
  replies: { matched: number };
  failed: Array<{ error: string }>;
};

export type QueueView = "all" | "ready" | "approval" | "replied";
export type QueueSummary = { all: number; ready: number; approval: number; replied: number };
export type QueueResponse = Paginated<QueueItem> & { counts: QueueSummary; limit: number; offset: number };

export const QUEUE_PAGE_SIZE = 100;
export function queuePagePath(campaignId: string, page: number, view: QueueView): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/queue?limit=${QUEUE_PAGE_SIZE}&offset=${Math.max(0, page) * QUEUE_PAGE_SIZE}&view=${view}`;
}

export default function Queue() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [busy, setBusy] = useState("");
  const [gmailOpen, setGmailOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<QueueView>("all");
  const queue = useResource(
    () => campaignId
      ? api.get<QueueResponse>(queuePagePath(campaignId, page, view))
      : Promise.resolve({ items: [], total: 0, limit: QUEUE_PAGE_SIZE, offset: 0, counts: { all: 0, ready: 0, approval: 0, replied: 0 } }),
    [campaignId, page, view]
  );
  const automation = useResource(() => api.get<AutomationStatus>("/automation"), []);
  const counts = queue.data?.counts ?? { all: 0, ready: 0, approval: 0, replied: 0 };
  const total = queue.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / QUEUE_PAGE_SIZE));
  useEffect(() => {
    if (!queue.loading && !queue.error && queue.data && queue.data.offset === page * QUEUE_PAGE_SIZE && page >= pages) {
      setPage(pages - 1);
    }
  }, [queue.loading, queue.error, queue.data, page, pages]);

  if (!campaignId) return <><PageHeader title="Send queue" /><NoCampaign /></>;

  async function run(mode: "local" | "gmail", confirmation = "") {
    setBusy(mode);
    try {
      const result = await api.post<SendResult>(
        `/campaigns/${campaignId}/send`,
        { mode, confirmation, sync_replies_first: true, max_messages: null },
        idempotencyKey(`send-${mode}`)
      );
      notify(`${result.sent_count} messages sent. ${result.remaining_today} remain in today's cap.`, result.failed.length ? "info" : "success");
      if (result.replies.matched) notify(`${result.replies.matched} replies matched. Follow-ups stopped.`, "success");
      setGmailOpen(false);
      queue.reload();
      refreshCampaigns();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Send run failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function syncReplies() {
    setBusy("sync");
    try {
      const result = await api.post<{ scanned: number; matched: number }>(`/campaigns/${campaignId}/replies/sync`, { mode: "local" });
      notify(`${result.scanned} local replies scanned, ${result.matched} matched`, "success");
      queue.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Reply sync failed", "error");
    } finally {
      setBusy("");
    }
  }

  function confirmGmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void run("gmail", String(data.get("confirmation") ?? ""));
  }

  const state = <Loadable loading={queue.loading} error={queue.error} />;
  return (
    <>
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Send queue"
        description="Reply sync runs first. Daily caps, working-day timing and atomic send claims are enforced in the backend."
        actions={<><Badge tone={automation.data?.enabled ? "success" : "neutral"}>{automation.data?.enabled ? `Automation on · ${automation.data.mode}` : "Automation paused"}</Badge><Button tone="ghost" onClick={() => (window.location.hash = "deliverability")}>Bulk delivery</Button><Button tone="secondary" busy={busy === "sync"} onClick={syncReplies}>Sync local replies</Button><Button tone="secondary" busy={busy === "local"} onClick={() => run("local")}>Run local outbox</Button><Button onClick={() => setGmailOpen(true)}>Send with Gmail</Button></>}
      />
      <div className="stats-grid compact-stats">
        <StatCard label="Ready now" value={counts.ready} detail="approved and due; sending checks still apply" accent="green" />
        <StatCard label="Needs approval" value={counts.approval} detail="blocked from sending" accent="orange" />
        <StatCard label="Daily cap" value={activeCampaign?.daily_send_limit ?? 0} detail={activeCampaign?.timezone} />
        <StatCard label="Replies" value={counts.replied} detail="sequences stopped" accent="violet" />
      </div>
      <Panel title="Sequence state" subtitle="The next eligible draft for each contact in this view">
        <div className="toolbar">
          <label htmlFor="queue-view">Show</label>
          <select id="queue-view" aria-label="Filter queue" value={view} onChange={(event) => { setPage(0); setView(event.target.value as QueueView); }}>
            <option value="all">All contacts ({counts.all})</option>
            <option value="ready">Approved and due ({counts.ready})</option>
            <option value="approval">Needs approval ({counts.approval})</option>
            <option value="replied">Replied ({counts.replied})</option>
          </select>
          <span className="toolbar-count">{total} in this view</span>
        </div>
        {queue.loading || queue.error ? state : queue.data?.items.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Contact</th><th>Current stage</th><th>Next message</th><th>Due</th><th>Approval</th><th>Status</th></tr></thead>
              <tbody>
                {queue.data.items.map((item) => (
                  <tr key={item.campaign_contact_id}>
                    <td><strong>{item.full_name}</strong><small>{item.email || "Email missing"} · {item.company}</small></td>
                    <td>{stageLabel(item.current_stage)}</td>
                    <td>{item.draft_stage ? stageLabel(item.draft_stage) : "Sequence finished"}<small>{item.quality_score ? `Quality ${item.quality_score}/100` : "No eligible draft"}</small></td>
                    <td><Badge tone={item.is_due ? "warning" : "neutral"}>{item.is_due ? "Due now" : formatDate(item.effective_due_at)}</Badge>{item.scheduled_at ? <small>Manual not-before gate</small> : null}</td>
                    <td><Badge tone={statusTone(item.approval_status ?? "missing")}>{(item.approval_status ?? "missing").replaceAll("_", " ")}</Badge></td>
                    <td><Badge tone={statusTone(item.status)}>{item.status.replaceAll("_", " ")}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StatePanel title={view === "all" ? "Queue is empty" : "No contacts match this view"} description={view === "all" ? "Import contacts, generate drafts and approve the messages you want to send." : "Choose another queue view to see different contacts."} action={<Button onClick={() => (window.location.hash = "drafts")}>Open draft review</Button>} />
        )}
        {!queue.loading && !queue.error && total > QUEUE_PAGE_SIZE && (
          <nav className="toolbar" aria-label="Queue pages">
            <span role="status" aria-live="polite">Showing {page * QUEUE_PAGE_SIZE + 1}–{Math.min(total, (page + 1) * QUEUE_PAGE_SIZE)} of {total} · Page {page + 1} of {pages}</span>
            <Button tone="ghost" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous page</Button>
            <Button tone="ghost" disabled={page + 1 >= pages} onClick={() => setPage((value) => Math.min(pages - 1, value + 1))}>Next page</Button>
          </nav>
        )}
      </Panel>
      <Modal open={gmailOpen} onClose={() => setGmailOpen(false)} title="Confirm live Gmail send" description="This action can contact real people. Reply sync runs before any send.">
        <form className="form-stack" onSubmit={confirmGmail}>
          <div className="danger-note"><strong>Live action</strong><p>Only approved, sendable and due drafts will be sent, up to the campaign's remaining daily cap.</p></div>
          <Field label="Type SEND LIVE EMAILS to continue"><input name="confirmation" autoComplete="off" required pattern="SEND LIVE EMAILS" /></Field>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setGmailOpen(false)}>Cancel</Button><Button type="submit" tone="danger" busy={busy === "gmail"}>Send approved emails</Button></div>
        </form>
      </Modal>
    </>
  );
}
