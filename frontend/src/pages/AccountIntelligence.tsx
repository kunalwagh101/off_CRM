import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";
import Contact360 from "./Contact360";

type AccountSummary = {
  company_key: string; company_name: string;
  contacts: number; campaigns: number; sales_leads: number; won_leads: number;
};
type AccountPerson = {
  id: string; full_name: string; email: string; title: string;
  category: string; campaign_count: number;
  campaign_id: string | null; campaign_contact_id: string | null;
};
type AccountLead = {
  id: string; lead_name: string; lead_status: string; email: string;
  total_deal_value: number; cash_collected: number; last_touch_at: string | null;
};
type AccountDetail = {
  company_key: string; company_name: string;
  contacts: { items: AccountPerson[]; total: number };
  sales_leads: { items: AccountLead[]; total: number };
  coverage: {
    campaigns: number; replied_memberships: number; outbound_messages: number;
    inbound_messages: number; open_contact_tasks: number;
  };
  identity_rule: string;
};
const SIZE = 25;
export function accountsPath(query: string, page: number): string {
  return `/crm/accounts?search=${encodeURIComponent(query)}&limit=${SIZE}&offset=${Math.max(0,page)*SIZE}`;
}
export function accountDetailPath(key: string, page: number): string {
  return `/crm/account?company_key=${encodeURIComponent(key)}&limit=${SIZE}&offset=${Math.max(0,page)*SIZE}`;
}

export default function AccountIntelligence() {
  const { selectCampaign } = useApp();
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [account, setAccount] = useState<AccountSummary | null>(null);
  const [detailPage, setDetailPage] = useState(0);
  const [contact, setContact] = useState<{ campaignId: string; memberId: string } | null>(null);
  const result = useResource(
    () => api.get<{ items: AccountSummary[]; total: number; identity_rule: string }>(
      accountsPath(search, page)
    ), [search, page],
  );
  const detail = useResource<AccountDetail | null>(
    () => account ? api.get<AccountDetail>(accountDetailPath(account.company_key, detailPage))
      : Promise.resolve(null), [account?.company_key, detailPage],
  );
  const total = result.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / SIZE));
  useEffect(() => {
    if (!result.loading && !result.error && result.data && page >= pages) setPage(pages - 1);
  }, [result.loading, result.error, result.data, page, pages]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPage(0); setSearch(input.trim());
  }
  function choose(item: AccountSummary) { setAccount(item); setDetailPage(0); }

  const d = detail.data;
  const dPages = Math.max(1, Math.ceil(Math.max(
    d?.contacts.total ?? 0, d?.sales_leads.total ?? 0
  ) / SIZE));

  return <>
    <PageHeader title="Account intelligence" eyebrow="Company relationships"
      description="Group existing people and sales records by company name. This is not a verified legal-entity registry."
      actions={<Button tone="secondary" onClick={result.reload}>Refresh accounts</Button>} />
    <Panel title="Companies and relationship coverage"
      subtitle="Companies are matched by their case-insensitive, trimmed name; different subsidiaries or spelling variants are not automatically merged.">
      <form className="toolbar" onSubmit={submit}>
        <Field label="Filter companies"><input value={input} maxLength={100}
          onChange={e => setInput(e.target.value)} placeholder="Company name" /></Field>
        <Button type="submit">Filter accounts</Button>
        <Button tone="ghost" type="button" onClick={() => { setInput(""); setSearch(""); setPage(0); }}>Clear</Button>
      </form>
      {result.loading || result.error ? <Loadable loading={result.loading} error={result.error} /> :
        result.data?.items.length ? <div className="form-stack" aria-label="Company accounts">
          <p className="muted">{total} companies</p>
          {result.data.items.map(item => <article className="panel" key={item.company_key}>
            <div className="toolbar">
              <strong>{item.company_name}</strong>
              <Badge>{item.contacts} contacts</Badge>
              <Badge>{item.campaigns} campaigns</Badge>
              <Badge>{item.sales_leads} sales leads</Badge>
              <Badge tone={item.won_leads ? "success" : "neutral"}>{item.won_leads} won</Badge>
            </div>
            <Button tone="secondary" onClick={() => choose(item)}>Open company overview</Button>
          </article>)}
        </div> : <StatePanel title="No companies found"
          description="Add company names to campaign contacts or existing sales leads to build relationship coverage." />}
      {total > SIZE && <nav className="toolbar" aria-label="Account pages">
        <span>Page {page+1} of {pages}</span>
        <Button tone="ghost" disabled={page===0} onClick={() => setPage(n => Math.max(0,n-1))}>Previous</Button>
        <Button tone="ghost" disabled={page+1>=pages} onClick={() => setPage(n=>n+1)}>Next</Button>
      </nav>}
    </Panel>
    <Modal open={Boolean(account)} wide
      title={`Company overview — ${account?.company_name ?? ""}`}
      description="Relationships derived from stored CRM records, not a corporate-identity verification service."
      onClose={() => { setAccount(null); setDetailPage(0); }}>
      {!account ? null : detail.loading ? <p>Loading company relationships…</p> :
        detail.error ? <p role="alert">{detail.error} <Button tone="ghost" onClick={detail.reload}>Retry</Button></p> :
        d ? <div className="form-stack">
          <div className="stats-grid compact-stats">
            <StatCard label="Campaigns covered" value={d.coverage.campaigns} />
            <StatCard label="Received messages" value={d.coverage.inbound_messages} />
            <StatCard label="Sent messages" value={d.coverage.outbound_messages} />
            <StatCard label="Open contact tasks" value={d.coverage.open_contact_tasks} />
          </div>
          <section><h3>People ({d.contacts.total})</h3>
            {d.contacts.items.length ? d.contacts.items.map(person => <div className="toolbar" key={person.id}>
              <strong>{person.full_name}</strong>
              <span className="muted">{person.title || "No title"} · {person.email}</span>
              {person.campaign_id && person.campaign_contact_id &&
                <Button tone="ghost" onClick={() => {
                  setAccount(null);
                  setContact({
                    campaignId: person.campaign_id!, memberId: person.campaign_contact_id!
                  });
                }}>Contact 360</Button>}
              {person.campaign_id && <Button tone="ghost" onClick={() => {
                selectCampaign(person.campaign_id!); setAccount(null); window.location.hash = "contacts";
              }}>Open campaign</Button>}
            </div>) : <p className="muted">No campaign contacts recorded.</p>}
          </section>
          <section><h3>Opportunities ({d.sales_leads.total})</h3>
            {d.sales_leads.items.length ? d.sales_leads.items.map(lead => <div className="toolbar" key={lead.id}>
              <strong>{lead.lead_name}</strong>
              <Badge>{lead.lead_status.replaceAll("_", " ")}</Badge>
              <Button tone="ghost" onClick={() => { setAccount(null); window.location.hash = "sales"; }}>Open Sales Tracker</Button>
            </div>) : <p className="muted">No sales opportunities recorded.</p>}
          </section>
          {Math.max(d.contacts.total,d.sales_leads.total) > SIZE && <nav className="toolbar" aria-label="Company detail pages">
            <span>Page {detailPage+1} of {dPages}</span>
            <Button tone="ghost" disabled={detailPage===0} onClick={() => setDetailPage(n=>Math.max(0,n-1))}>Previous</Button>
            <Button tone="ghost" disabled={detailPage+1>=dPages} onClick={() => setDetailPage(n=>n+1)}>Next</Button>
          </nav>}
          <p className="muted">{d.identity_rule}. Company-level tasks without an associated CRM contact are not included in the open-contact-task count.</p>
        </div> : null}
    </Modal>
    <Contact360 campaignId={contact?.campaignId ?? ""} membershipId={contact?.memberId ?? null}
      onClose={() => setContact(null)} />
  </>;
}
