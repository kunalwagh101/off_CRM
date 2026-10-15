import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";

export type CampaignAttribution = {
  campaign_id: string; campaign_name: string; kind: string; status: string;
  contacts: number; replied: number; qualified_replies: number;
  converted_memberships: number; attributed_leads: number;
  won_deals: number; lost_deals: number;
  booked_value: number; recorded_cash: number; cash_less_clawbacks: number;
};
export type AttributionResponse = {
  items: CampaignAttribution[]; total: number;
  overall: {
    attributed_leads: number; won_deals: number;
    booked_value: number; recorded_cash: number; cash_less_clawbacks: number;
  };
  attribution_rule: string; value_units: string;
};
const PAGE_SIZE = 25;
export function revenueAttributionPath(page: number): string {
  return `/crm/attribution?limit=${PAGE_SIZE}&offset=${Math.max(0,page)*PAGE_SIZE}`;
}
function money(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

export default function RevenueAttribution() {
  const { selectCampaign } = useApp();
  const [page, setPage] = useState(0);
  const results = useResource(
    () => api.get<AttributionResponse>(revenueAttributionPath(page)), [page]
  );
  const d = results.data;
  const total = d?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (!results.loading && !results.error && d && page >= pages) setPage(pages - 1);
  }, [results.loading, results.error, d, page, pages]);
  return <>
    <PageHeader title="Campaign-to-revenue attribution" eyebrow="Sales intelligence"
      description="Understand which campaigns are linked to recorded sales outcomes, without double-counting shared leads or claiming causal credit."
      actions={<Button tone="secondary" onClick={results.reload}>Refresh attribution</Button>} />
    {results.loading || results.error ? <Loadable loading={results.loading} error={results.error} /> :
      d ? <>
        <div className="stats-grid compact-stats">
          <StatCard label="Attributed leads" value={d.overall.attributed_leads} />
          <StatCard label="Won deals" value={d.overall.won_deals} />
          <StatCard label="Won deal value" value={money(d.overall.booked_value)} />
          <StatCard label="Recorded cash" value={money(d.overall.recorded_cash)} />
          <StatCard label="Cash less clawbacks" value={money(d.overall.cash_less_clawbacks)} />
        </div>
        <Panel title="Attribution method">
          <p><strong>First-linked CRM campaign:</strong> {d.attribution_rule}</p>
          <p className="muted">{d.value_units}. Counts reflect recorded CRM status and money fields, not verified external payments or proven campaign causality.</p>
        </Panel>
        <Panel title="Campaign outcomes" subtitle="All campaigns, including ones with no linked sales lead.">
          {d.items.length ? <div className="form-stack" aria-label="Campaign revenue outcomes">
            {d.items.map(item => <article key={item.campaign_id} className="panel">
              <div className="toolbar">
                <strong>{item.campaign_name}</strong>
                <Badge>{item.kind}</Badge>
                <Badge>{item.status}</Badge>
              </div>
              <div className="stats-grid compact-stats">
                <StatCard label="Campaign contacts" value={item.contacts} />
                <StatCard label="Replied" value={item.replied} />
                <StatCard label="Qualified replies" value={item.qualified_replies} />
                <StatCard label="Linked contacts" value={item.converted_memberships} />
                <StatCard label="Attributed leads" value={item.attributed_leads} />
                <StatCard label="Won deals" value={item.won_deals} />
                <StatCard label="Won deal value" value={money(item.booked_value)} />
                <StatCard label="Recorded cash" value={money(item.recorded_cash)} />
              </div>
              <div className="toolbar">
                <span className="muted">Lost deals: {item.lost_deals} · Cash less clawbacks: {money(item.cash_less_clawbacks)}</span>
                <Button tone="ghost" onClick={() => {
                  selectCampaign(item.campaign_id); window.location.hash = "campaigns";
                }}>Open campaign</Button>
              </div>
            </article>)}
          </div> : <StatePanel title="No campaigns yet"
            description="Create a campaign, record qualified replies and link sales leads to see source-backed outcomes." />}
          {total > PAGE_SIZE && <nav className="toolbar" aria-label="Revenue attribution pages">
            <span>Page {page+1} of {pages} · {total} campaigns</span>
            <Button tone="ghost" disabled={page===0} onClick={() => setPage(n=>Math.max(0,n-1))}>Previous</Button>
            <Button tone="ghost" disabled={page+1>=pages} onClick={() => setPage(n=>n+1)}>Next</Button>
          </nav>}
        </Panel>
      </> : <StatePanel title="Attribution unavailable" description="Refresh to retrieve saved sales outcomes." />}
  </>;
}
