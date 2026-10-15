import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel, StatePanel, StatCard } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";

const SIZE = 25;
type PageResult<T> = { items: T[]; total: number };
function pagePath(path: string, parameters: Record<string, string>, page: number): string {
  const q = new URLSearchParams(parameters);
  q.set("limit", String(SIZE));
  q.set("offset", String(Math.max(0, page) * SIZE));
  return path + "?" + q.toString();
}
export function qualityPath(issue: string, search: string, page: number): string {
  return pagePath("/crm/quality", { issue, search }, page);
}
export function comparePath(search: string, page: number): string {
  return pagePath("/crm/compare", { search }, page);
}
export function workloadPath(campaignId: string, page: number): string {
  return pagePath("/crm/followup-performance", { campaign_id: campaignId }, page);
}

function Pages({ page, setPage, total }: {
  page: number; setPage: (value: number) => void; total: number;
}) {
  const count = Math.max(1, Math.ceil(total / SIZE));
  if (total <= SIZE) return null;
  return <nav className="toolbar" aria-label="Result pages">
    <span>Page {page + 1} of {count}</span>
    <Button tone="ghost" disabled={page === 0} onClick={() => setPage(Math.max(0, page - 1))}>Previous</Button>
    <Button tone="ghost" disabled={page + 1 >= count} onClick={() => setPage(page + 1)}>Next</Button>
  </nav>;
}

function useSafePage(page: number, setPage: (value: number) => void, total: number | undefined, loading: boolean, error: string) {
  useEffect(() => {
    if (loading || error || total === undefined) return;
    const last = Math.max(0, Math.ceil(total / SIZE) - 1);
    if (page > last) setPage(last);
  }, [page, setPage, total, loading, error]);
}

type QualityItem = {
  id: string; full_name: string; email: string; company: string; title: string;
  campaign_count: number; campaign_id: string | null;
  campaign_contact_id: string | null; issues: string[];
};
type QualityResult = PageResult<QualityItem> & { identity_note: string };
const issueLabels: Record<string, string> = {
  missing_email: "Missing email", missing_company: "Missing company",
  missing_title: "Missing title", not_in_campaign: "Not in a campaign",
  sales_overlap: "Also in Sales Tracker"
};

export function CRMDataQuality() {
  const { selectCampaign } = useApp();
  const [issue, setIssue] = useState("all");
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const data = useResource(
    () => api.get<QualityResult>(qualityPath(issue, search, page)), [issue, search, page]
  );
  useSafePage(page, setPage, data.data?.total, data.loading, data.error);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSearch(input.trim()); setPage(0);
  }
  return <>
    <PageHeader title="CRM data quality" eyebrow="Contact review"
      description="Find incomplete records and possible Sales Tracker overlaps. Nothing is merged or changed automatically."
      actions={<Button tone="secondary" onClick={data.reload}>Refresh</Button>} />
    <Panel title="Records needing a human review" subtitle="Filters use stored contact fields; no messages or notes are exposed.">
      <form onSubmit={submit} className="toolbar">
        <Field label="Quality issue"><select value={issue} onChange={e => { setIssue(e.target.value); setPage(0); }}>
          <option value="all">Any issue</option>
          {Object.entries(issueLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select></Field>
        <Field label="Find contact"><input value={input} maxLength={100}
          onChange={e => setInput(e.target.value)} placeholder="Name, email or company" /></Field>
        <Button type="submit">Find records</Button>
      </form>
      {data.loading || data.error ? <Loadable loading={data.loading} error={data.error} /> :
        data.data?.items.length ? <div className="form-stack">
          <p className="muted">{data.data.total} matching records</p>
          {data.data.items.map(row => <article key={row.id} className="panel">
            <div className="toolbar">
              <strong>{row.full_name}</strong>
              <span className="muted">{row.email || "No email"} · {row.company || "No company"} · {row.title || "No title"}</span>
            </div>
            <div className="toolbar">
              {row.issues.map(issue => <Badge key={issue}>{issueLabels[issue]}</Badge>)}
            </div>
            <div className="toolbar">
              {row.campaign_id && row.campaign_contact_id ? <Button tone="secondary"
                onClick={() => { selectCampaign(row.campaign_id!); window.location.hash = "contacts"; }}>
                Review campaign contact
              </Button> : <Button tone="secondary" onClick={() => { window.location.hash = "campaigns"; }}>
                Choose campaign to link
              </Button>}
              {row.issues.includes("sales_overlap") && <Button tone="ghost" onClick={() => { window.location.hash = "sales"; }}>
                Review Sales Tracker
              </Button>}
            </div>
          </article>)}
        </div> : <StatePanel title="No matching issues" description="Try a different issue filter or search term." />}
      <Pages page={page} setPage={setPage} total={data.data?.total ?? 0} />
      {data.data && <p className="muted">{data.data.identity_note}</p>}
    </Panel>
  </>;
}

type CampaignResult = {
  campaign_id: string; campaign_name: string; kind: string; status: string;
  contacts: number; contacted: number; replied_after_outreach: number;
  inbound_contacts: number; qualified: number; sales_links: number;
  reply_rate_percent: number | null;
};
type Comparison = PageResult<CampaignResult> & { rate_note: string; sales_note: string };
export function CampaignComparison() {
  const { selectCampaign } = useApp();
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const data = useResource(
    () => api.get<Comparison>(comparePath(search, page)), [search, page]
  );
  useSafePage(page, setPage, data.data?.total, data.loading, data.error);
  return <>
    <PageHeader title="Compare campaigns" eyebrow="Recorded outreach performance"
      description="Compare saved sends and replies using the same definitions across campaigns. No predicted numbers."
      actions={<Button tone="secondary" onClick={data.reload}>Refresh</Button>} />
    <Panel title="Campaign performance side by side"
      subtitle="Reply rate = members with both saved outbound and inbound messages, divided by members with outbound. This does not establish message order.">
      <form className="toolbar" onSubmit={event => { event.preventDefault(); setSearch(input.trim()); setPage(0); }}>
        <Field label="Campaign name"><input value={input} maxLength={100} onChange={e => setInput(e.target.value)} /></Field>
        <Button type="submit">Compare</Button>
      </form>
      {data.loading || data.error ? <Loadable loading={data.loading} error={data.error} /> :
        data.data?.items.length ? <div className="form-stack">
          <p className="muted">{data.data.total} campaigns</p>
          {data.data.items.map(row => <article className="panel" key={row.campaign_id}>
            <div className="toolbar">
              <strong>{row.campaign_name}</strong><Badge>{row.kind}</Badge><Badge>{row.status}</Badge>
            </div>
            <div className="stats-grid compact-stats">
              <StatCard label="Contacts" value={row.contacts} />
              <StatCard label="Contacted" value={row.contacted} />
              <StatCard label="Inbound contacts" value={row.inbound_contacts} />
              <StatCard label="Qualified replies" value={row.qualified} />
              <StatCard label="Reply rate" value={row.reply_rate_percent === null ? "N/A" : String(row.reply_rate_percent) + "%"} />
              <StatCard label="Sales links" value={row.sales_links} />
            </div>
            <Button tone="secondary" onClick={() => { selectCampaign(row.campaign_id); window.location.hash = "activity"; }}>
              Open campaign activity
            </Button>
          </article>)}
        </div> : <StatePanel title="No campaigns found" description="Create a campaign or clear the name filter to see comparisons." />}
      <Pages page={page} setPage={setPage} total={data.data?.total ?? 0} />
      {data.data && <p className="muted">{data.data.rate_note} {data.data.sales_note}</p>}
    </Panel>
  </>;
}

type TaskMetrics = { tasks: number; open: number; done: number; overdue: number; on_time: number };
type OwnerMetrics = TaskMetrics & { owner_key: string; owner: string };
type Workload = PageResult<OwnerMetrics> & { overall: TaskMetrics; owner_note: string };
export function FollowupPerformance() {
  const { campaigns } = useApp();
  const [campaignId, setCampaignId] = useState("");
  const [page, setPage] = useState(0);
  const data = useResource(
    () => api.get<Workload>(workloadPath(campaignId, page)), [campaignId, page]
  );
  useSafePage(page, setPage, data.data?.total, data.loading, data.error);
  const all = data.data?.overall;
  return <>
    <PageHeader title="Follow-up performance" eyebrow="Human task reporting"
      description="See who has outstanding work and how many saved follow-ups were completed on time."
      actions={<Button tone="secondary" onClick={data.reload}>Refresh</Button>} />
    <Panel title="Task coverage by assigned label"
      subtitle="Reports are read-only. Assigned names are text labels and do not grant permissions.">
      <Field label="Campaign"><select value={campaignId} onChange={e => { setCampaignId(e.target.value); setPage(0); }}>
        <option value="">All campaigns</option>
        {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></Field>
      {data.loading || data.error ? <Loadable loading={data.loading} error={data.error} /> :
        <>
          <div className="stats-grid compact-stats">
            <StatCard label="Total tasks" value={all?.tasks ?? 0} />
            <StatCard label="Open" value={all?.open ?? 0} />
            <StatCard label="Overdue" value={all?.overdue ?? 0} />
            <StatCard label="Done" value={all?.done ?? 0} />
            <StatCard label="Completed on time" value={all?.on_time ?? 0} />
          </div>
          {data.data?.items.length ? <div className="form-stack">
            <p className="muted">{data.data.total} owner labels</p>
            {data.data.items.map(row => <article className="panel" key={row.owner_key}>
              <div className="toolbar"><strong>{row.owner}</strong><Badge>{row.tasks} tasks</Badge></div>
              <div className="toolbar">
                <Badge>{row.open} open</Badge><Badge tone={row.overdue ? "warning" : "neutral"}>{row.overdue} overdue</Badge>
                <Badge>{row.done} done</Badge><Badge>{row.on_time} on time</Badge>
              </div>
            </article>)}
          </div> : <StatePanel title="No follow-up tasks" description="Create human follow-up tasks from a campaign's Follow-ups screen." />}
          <Pages page={page} setPage={setPage} total={data.data?.total ?? 0} />
          <Button tone="secondary" onClick={() => { if (campaignId) { window.location.hash = "followups"; } else { window.location.hash = "campaigns"; } }}>
            {campaignId ? "Open campaign follow-ups" : "Choose a campaign"}
          </Button>
          {data.data && <p className="muted">{data.data.owner_note}</p>}
        </>}
    </Panel>
  </>;
}
