import { useEffect, useState } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Modal, StatCard } from "../components";
import { useResource } from "../hooks";
import ContactConversation from "./ContactConversation";

export type RelationshipOverview = {
  campaign_id: string;
  contact: {
    id: string; full_name: string; email: string; company: string;
    title: string; category: string; status: string; current_stage: string;
    variant_id: string; recipient_timezone: string;
  };
  messages: { sent: number; received: number };
  latest_reply: { id: string; subject: string; received_at: string } | null;
  triage: { review_status: string; outcome: string };
  tasks: {
    total: number; open: number;
    next: { id: string; title: string; due_at: string; priority: string; assigned_to: string } | null;
  };
  sales_lead: {
    id: string; lead_name: string; lead_status: string; linked_at: string;
  } | null;
};

export function overviewPath(campaignId: string, membershipId: string): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/contacts/${encodeURIComponent(membershipId)}/overview`;
}

export default function Contact360({
  campaignId, membershipId, onClose
}: { campaignId: string; membershipId: string | null; onClose: () => void }) {
  const [showMessages, setShowMessages] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const summary = useResource(
    () => campaignId && membershipId
      ? api.get<RelationshipOverview>(overviewPath(campaignId, membershipId))
      : Promise.resolve(null),
    [campaignId, membershipId]
  );
  useEffect(() => { setShowMessages(false); setError(""); }, [campaignId, membershipId]);
  const d = membershipId ? summary.data : null;
  const qualified = d && d.triage.review_status === "triaged" &&
    ["positive", "meeting"].includes(d.triage.outcome) && d.messages.received > 0;

  async function promote() {
    if (!membershipId || !qualified || busy) return;
    if (!window.confirm(
      "Create or link a Sales Tracker opportunity for this qualified reply? Existing lead details will not be overwritten."
    )) return;
    setBusy(true);
    setError("");
    try {
      const key = idempotencyKey("sales-promotion");
      await api.post(
        `/campaigns/${encodeURIComponent(campaignId)}/contacts/${encodeURIComponent(membershipId)}/promote`,
        {}, key
      );
      summary.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not convert reply into sales");
    } finally { setBusy(false); }
  }

  return <>
    <Modal open={Boolean(membershipId)} onClose={onClose}
      title={`Contact 360 — ${d?.contact.full_name || "Contact"}`}
      description="Campaign-scoped relationship summary. Sensitive message bodies and provider metadata are not included."
      wide>
      {summary.loading ? <p>Loading relationship overview…</p>
        : summary.error ? <p role="alert">{summary.error} <Button tone="ghost" onClick={summary.reload}>Retry</Button></p>
        : d ? <div className="form-stack">
          <div>
            <strong>{d.contact.full_name}</strong>
            <p>{d.contact.title || "No title"} · {d.contact.company || "No company"}</p>
            <p className="muted">{d.contact.email} · {d.contact.category}</p>
            <Badge tone={d.contact.status === "replied" ? "success" : "neutral"}>{d.contact.status}</Badge>
          </div>
          <div className="stats-grid compact-stats">
            <StatCard label="Emails sent" value={d.messages.sent} />
            <StatCard label="Replies received" value={d.messages.received} />
            <StatCard label="Open tasks" value={d.tasks.open} />
          </div>
          <section>
            <h3>Latest reply</h3>
            {d.latest_reply ? <>
              <p>{d.latest_reply.subject || "(no subject)"} · {new Date(d.latest_reply.received_at).toLocaleString()}</p>
              <p>Review: {d.triage.review_status} · Outcome: {d.triage.outcome || "Unclassified"}</p>
            </> : <p className="muted">No received reply is recorded.</p>}
          </section>
          <section>
            <h3>Next human action</h3>
            {d.tasks.next ? <>
              <p>{d.tasks.next.title} · Due {new Date(d.tasks.next.due_at).toLocaleString()}</p>
              <p className="muted">Assigned to: {d.tasks.next.assigned_to || "Unassigned"}</p>
            </> : <p className="muted">No open follow-up is linked to this contact.</p>}
          </section>
          <section>
            <h3>Sales opportunity</h3>
            {d.sales_lead ? <>
              <p>{d.sales_lead.lead_name} · {d.sales_lead.lead_status.replaceAll("_", " ")}</p>
              <Button tone="ghost" onClick={() => { onClose(); window.location.hash = "sales"; }}>Open Sales Tracker</Button>
            </> : qualified ? <>
              <p className="muted">This reviewed positive reply can be promoted into the existing sales pipeline.</p>
              <Button busy={busy} onClick={() => void promote()}>Convert qualified reply to sales lead</Button>
            </> : <p className="muted">First review an incoming reply as Positive or Meeting in the Reply Inbox.</p>}
          </section>
          {error && <p role="alert">{error}</p>}
          <div className="toolbar">
            <Button tone="secondary" onClick={() => setShowMessages(true)}>Communication history</Button>
            <Button tone="ghost" onClick={() => { onClose(); window.location.hash = "followups"; }}>Human follow-ups</Button>
            <Button tone="ghost" onClick={summary.reload}>Refresh</Button>
          </div>
        </div> : <p>No contact selected.</p>}
    </Modal>
    <ContactConversation campaignId={campaignId}
      membershipId={showMessages ? membershipId : null}
      onClose={() => setShowMessages(false)} />
  </>;
}
