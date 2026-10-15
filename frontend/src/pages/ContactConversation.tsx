import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Modal, StatePanel } from "../components";
import { useResource } from "../hooks";

export type Correspondence = {
  id: string;
  direction: "inbound" | "outbound";
  stage: string;
  subject: string;
  body_preview: string;
  truncated: number;
  sent_at?: string | null;
  received_at?: string | null;
  created_at: string;
};
type ConversationResult = {
  campaign_contact_id: string;
  contact: { full_name: string; email: string; company: string };
  items: Correspondence[];
  total: number;
};

const SIZE = 25;
export function contactMessagePath(campaign: string, member: string, page: number): string {
  return `/campaigns/${encodeURIComponent(campaign)}/contacts/${encodeURIComponent(member)}/messages?limit=${SIZE}&offset=${Math.max(0,page)*SIZE}`;
}

export default function ContactConversation({ campaignId, membershipId, onClose }: {
  campaignId: string;
  membershipId: string | null;
  onClose: () => void;
}) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [campaignId, membershipId]);
  const result = useResource(
    () => campaignId && membershipId
      ? api.get<ConversationResult>(contactMessagePath(campaignId, membershipId, page))
      : Promise.resolve({ campaign_contact_id: "", contact: { full_name: "", email: "", company: "" }, items: [], total: 0 }),
    [campaignId, membershipId, page]
  );
  const total = result.data?.total ?? 0;
  return <Modal open={Boolean(membershipId)} title={`Communication history — ${result.data?.contact?.full_name || "Contact"}`}
    description="Campaign-scoped correspondence. Message previews are limited to 2,000 characters; raw provider metadata is not shown."
    onClose={() => { setPage(0); onClose(); }} wide>
    {result.loading ? <p>Loading correspondence…</p>
      : result.error ? <p role="alert">{result.error} <Button tone="ghost" onClick={result.reload}>Retry</Button></p>
      : total ? <>
        <div className="form-stack">
          {result.data?.items.map((item) => <article className="panel" key={item.id}>
            <p><strong>{item.direction === "inbound" ? "Received" : "Sent"}</strong>
              {" · "}{new Date(item.received_at || item.sent_at || item.created_at).toLocaleString()}
              {item.stage ? ` · ${item.stage}` : ""}
            </p>
            <strong>{item.subject || "(no subject)"}</strong>
            <p className="muted" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.body_preview}</p>
            {item.truncated ? <small>Preview truncated to 2,000 characters.</small> : null}
          </article>)}
        </div>
        {total > SIZE && <nav className="toolbar" aria-label="Conversation pages">
          <span>Page {page + 1} of {Math.ceil(total / SIZE)} · {total} messages</span>
          <Button tone="ghost" disabled={page === 0} onClick={() => setPage(n => Math.max(0,n-1))}>Previous</Button>
          <Button tone="ghost" disabled={(page+1)*SIZE>=total} onClick={() => setPage(n => n+1)}>Next</Button>
        </nav>}
      </> : <StatePanel title="No correspondence saved" description="This contact has no recorded sent or received campaign messages." />}
  </Modal>;
}
