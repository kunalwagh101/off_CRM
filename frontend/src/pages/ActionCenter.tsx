import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable, NoCampaign } from "./shared";
import Contact360 from "./Contact360";

export type WorkAction = {
  action_type: "overdue_task" | "reply_review" | "sales_attention";
  item_id: string;
  campaign_contact_id: string | null;
  sales_lead_id: string | null;
  headline: string;
  occurred_at: string;
  due_at: string | null;
  priority: string;
  reason: string;
};
export type ActionReport = {
  items: WorkAction[];
  total: number;
  counts: { overdue_task: number; reply_review: number; sales_attention: number };
  evaluated_at: string;
  sales_attention_rule: string;
};
export const ACTION_PAGE_SIZE = 50;

export function actionCenterPath(campaign: string, kind: string, page: number): string {
  return `/campaigns/${encodeURIComponent(campaign)}/actions?action_type=${encodeURIComponent(kind)}&limit=${ACTION_PAGE_SIZE}&offset=${Math.max(0,page)*ACTION_PAGE_SIZE}`;
}
const LABELS: Record<WorkAction["action_type"], string> = {
  overdue_task: "Overdue task",
  reply_review: "Unreviewed reply",
  sales_attention: "Sales follow-up"
};

export default function ActionCenter() {
  const { campaignId, activeCampaign } = useApp();
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(0);
  const [contactId, setContactId] = useState<string | null>(null);
  const report = useResource(
    () => campaignId ? api.get<ActionReport>(actionCenterPath(campaignId, kind, page))
      : Promise.resolve({
          items: [], total: 0,
          counts: { overdue_task: 0, reply_review: 0, sales_attention: 0 },
          evaluated_at: "", sales_attention_rule: ""
        }),
    [campaignId, kind, page]
  );
  const data = report.data;
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / ACTION_PAGE_SIZE));
  useEffect(() => {
    if (!report.loading && !report.error && data && page >= pages) setPage(pages - 1);
  }, [report.loading, report.error, data, page, pages]);
  if (!campaignId) return <><PageHeader title="Today's priorities" /><NoCampaign /></>;

  function navigate(action: WorkAction) {
    if (action.action_type === "overdue_task") window.location.hash = "followups";
    else if (action.action_type === "reply_review") window.location.hash = "replies";
    else window.location.hash = "sales";
  }

  return <>
    <PageHeader eyebrow={activeCampaign?.name} title="Today's priorities"
      description="One read-only worklist for replies, follow-ups and neglected opportunities. Nothing here sends or approves messages."
      actions={<Button tone="secondary" onClick={report.reload}>Recheck priorities</Button>} />
    {report.loading || report.error ? <Loadable loading={report.loading} error={report.error} />
      : data ? <>
        <div className="stats-grid compact-stats">
          <StatCard label="Overdue tasks" value={data.counts.overdue_task} />
          <StatCard label="Replies to review" value={data.counts.reply_review} />
          <StatCard label="Sales needing attention" value={data.counts.sales_attention} />
        </div>
        <Panel title="Prioritised worklist"
          subtitle="Overdue human work first; then unanswered review decisions, then unworked sales opportunities.">
          <div className="toolbar">
            <label htmlFor="priority-filter">Show</label>
            <select id="priority-filter" value={kind}
              onChange={e => { setKind(e.target.value); setPage(0); }}>
              <option value="all">All actions</option>
              <option value="overdue_task">Overdue tasks</option>
              <option value="reply_review">Replies to review</option>
              <option value="sales_attention">Sales needing attention</option>
            </select>
            <span className="toolbar-count">{total} actions</span>
          </div>
          {data.items.length ? <div className="form-stack" aria-label="Daily action worklist">
            {data.items.map(action => <article key={`${action.action_type}:${action.item_id}`} className="panel">
              <div className="toolbar">
                <Badge tone={action.action_type === "overdue_task" ? "warning" : "neutral"}>
                  {LABELS[action.action_type]}
                </Badge>
                {action.priority === "high" && <Badge tone="warning">High priority</Badge>}
              </div>
              <strong>{action.headline}</strong>
              <p className="muted">{action.reason} · {new Date(action.occurred_at).toLocaleString()}</p>
              <div className="toolbar">
                <Button tone="secondary" onClick={() => navigate(action)}>
                  {action.action_type === "overdue_task" ? "Open tasks"
                    : action.action_type === "reply_review" ? "Review replies" : "Open Sales Tracker"}
                </Button>
                {action.campaign_contact_id && <Button tone="ghost"
                  onClick={() => setContactId(action.campaign_contact_id)}>Contact 360</Button>}
              </div>
            </article>)}
          </div> : <StatePanel title="Nothing needs action in this view"
            description="The report is based on saved CRM records, not on AI estimates or live provider checks." />}
          {total > ACTION_PAGE_SIZE && <nav className="toolbar" aria-label="Action pages">
            <span>Page {page + 1} of {pages} · {total} actions</span>
            <Button tone="ghost" disabled={page === 0}
              onClick={() => setPage(n => Math.max(0,n-1))}>Previous</Button>
            <Button tone="ghost" disabled={page+1 >= pages}
              onClick={() => setPage(n => n+1)}>Next</Button>
          </nav>}
          <p className="muted">Sales attention rule: {data.sales_attention_rule}. Counts cover the selected campaign only; a saved record is not proof of external delivery.</p>
        </Panel>
      </> : <StatePanel title="Priorities unavailable" description="Refresh to retrieve the latest saved CRM state." />}
    <Contact360 campaignId={campaignId} membershipId={contactId} onClose={() => setContactId(null)} />
  </>;
}
