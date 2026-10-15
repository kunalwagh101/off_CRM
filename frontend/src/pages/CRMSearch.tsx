import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";
import Contact360 from "./Contact360";

export type SearchContact = {
  id: string; full_name: string; email: string; company: string;
  title: string; category: string; campaign_count: number;
  campaign_id: string | null; campaign_contact_id: string | null;
};
export type SearchLead = {
  id: string; lead_name: string; email: string; company: string;
  lead_status: string; total_deal_value: number; cash_collected: number;
};
type CRMSearchResult = {
  items: Array<SearchContact | SearchLead>; total: number;
  kind: "contacts" | "leads"; query: string;
};
const PAGE_SIZE = 25;

export function crmSearchPath(query: string, kind: string, page: number): string {
  return `/crm/search?query=${encodeURIComponent(query)}&kind=${encodeURIComponent(kind)}&limit=${PAGE_SIZE}&offset=${Math.max(0,page)*PAGE_SIZE}`;
}

export default function CRMSearch() {
  const { selectCampaign } = useApp();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"contacts" | "leads">("contacts");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<{ campaignId: string; memberId: string } | null>(null);
  const results = useResource<CRMSearchResult>(
    () => query.length >= 2
      ? api.get<CRMSearchResult>(crmSearchPath(query, kind, page))
      : Promise.resolve({ items: [], total: 0, kind, query }),
    [query, kind, page],
  );
  const total = results.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (!results.loading && !results.error && results.data && page >= pages) setPage(pages - 1);
  }, [results.loading, results.error, results.data, page, pages]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(0);
    setQuery(input.trim());
  }

  return <>
    <PageHeader title="Unified CRM search" eyebrow="Relationship discovery"
      description="Find contacts across campaigns or existing sales opportunities. Only stored identity and pipeline metadata are searched—never private message bodies."
      actions={<Button tone="ghost" onClick={() => { setInput(""); setQuery(""); setPage(0); }}>Clear search</Button>} />
    <Panel title="Find a person or company">
      <form className="toolbar" onSubmit={submit}>
        <Field label="Name, email or company">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Enter at least 2 characters" minLength={2} maxLength={100} required />
        </Field>
        <Button type="submit">Search CRM</Button>
      </form>
      <div className="toolbar">
        <label htmlFor="search-record-type">Record type</label>
        <select id="search-record-type" value={kind}
          onChange={e => { setKind(e.target.value as "contacts" | "leads"); setPage(0); }}>
          <option value="contacts">Campaign contacts</option>
          <option value="leads">Sales opportunities</option>
        </select>
        {query && <span>{total} matching {kind === "contacts" ? "contacts" : "sales leads"}</span>}
      </div>
      {!query ? <StatePanel title="Search the CRM" description="Enter a name, email or company to find existing records across campaigns." /> :
        results.loading || results.error ? <Loadable loading={results.loading} error={results.error} /> :
        results.data?.items.length ? <div className="form-stack" aria-label="CRM search results">
          {kind === "contacts" ? (results.data.items as SearchContact[]).map(contact =>
            <article className="panel" key={contact.id}>
              <strong>{contact.full_name}</strong>
              <p className="muted">{contact.email} · {contact.company || "No company"} · {contact.title || "No title"}</p>
              <div className="toolbar">
                <Badge>{contact.campaign_count} campaigns</Badge>
                {contact.campaign_id && contact.campaign_contact_id ?
                  <Button tone="secondary" onClick={() => setSelected({
                    campaignId: contact.campaign_id!, memberId: contact.campaign_contact_id!
                  })}>Contact 360</Button> :
                  <span className="muted">Not yet linked to a campaign</span>}
                {contact.campaign_id && <Button tone="ghost" onClick={() => {
                  selectCampaign(contact.campaign_id!);
                  window.location.hash = "contacts";
                }}>Open campaign contacts</Button>}
              </div>
            </article>
          ) : (results.data.items as SearchLead[]).map(lead =>
            <article className="panel" key={lead.id}>
              <strong>{lead.lead_name}</strong>
              <p className="muted">{lead.email} · {lead.company || "No company"}</p>
              <div className="toolbar">
                <Badge>{lead.lead_status.replaceAll("_", " ")}</Badge>
                <Button tone="secondary" onClick={() => { window.location.hash = "sales"; }}>Open Sales Tracker</Button>
              </div>
            </article>
          )}
        </div> : <StatePanel title="No matching records"
          description="Try a different spelling, or switch between Contacts and Sales opportunities." />}
      {total > PAGE_SIZE && <nav className="toolbar" aria-label="CRM search pages">
        <span>Page {page + 1} of {pages}</span>
        <Button tone="ghost" disabled={page === 0} onClick={() => setPage(n => Math.max(0,n-1))}>Previous</Button>
        <Button tone="ghost" disabled={page+1 >= pages} onClick={() => setPage(n => n+1)}>Next</Button>
      </nav>}
    </Panel>
    <Contact360 campaignId={selected?.campaignId ?? ""} membershipId={selected?.memberId ?? null}
      onClose={() => setSelected(null)} />
  </>;
}
