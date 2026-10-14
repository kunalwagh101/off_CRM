import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { Contact, Paginated } from "../types";
import { Loadable, NoCampaign, statusTone } from "./shared";
import { ManualContactModal, StopContactsModal } from "./AudienceOperations";

const DEFAULT_CATEGORY = "Sustainability / ESG / Climate";
export const CONTACTS_PAGE_SIZE = 100;

export function contactPageBounds(page: number, total: number) {
  const pages = Math.max(1, Math.ceil(total / CONTACTS_PAGE_SIZE));
  const safePage = Math.max(0, Math.min(page, pages - 1));
  return {
    pages,
    first: total === 0 ? 0 : safePage * CONTACTS_PAGE_SIZE + 1,
    last: Math.min(total, (safePage + 1) * CONTACTS_PAGE_SIZE),
  };
}

export type ContactFilters = { category?: string; variant_id?: string; selected_only?: boolean };

function filterQuery(search: string, status: string, filters: ContactFilters = {}): string {
  const query = `search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`;
  const extras = [
    filters.category ? `category=${encodeURIComponent(filters.category)}` : "",
    filters.variant_id ? `variant_id=${encodeURIComponent(filters.variant_id)}` : "",
    filters.selected_only ? "selected_only=true" : ""
  ].filter(Boolean);
  return extras.length ? `${query}&${extras.join("&")}` : query;
}

export function contactsPagePath(campaignId: string, page: number, search: string, status: string, filters: ContactFilters = {}): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/contacts?limit=${CONTACTS_PAGE_SIZE}&offset=${Math.max(0, page) * CONTACTS_PAGE_SIZE}&${filterQuery(search, status, filters)}`;
}

export function contactsDownloadPath(campaignId: string, search: string, status: string, filters: ContactFilters = {}): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/contacts/download?${filterQuery(search, status, filters)}`;
}

export default function Contacts() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [variant, setVariant] = useState("");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [importOpen, setImportOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [stopOpen, setStopOpen] = useState(false);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [editContact, setEditContact] = useState<Contact | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const facets = useResource(
    () => campaignId
      ? api.get<{ categories: string[]; variants: string[] }>(`/campaigns/${encodeURIComponent(campaignId)}/contacts/facets`)
      : Promise.resolve({ categories: [], variants: [] }),
    [campaignId]
  );
  const lockedCategories = useResource(() => api.get<{ categories: string[] }>("/meta"), []);
  const filters = { category, variant_id: variant, selected_only: selectedOnly };
  const contacts = useResource(
    () =>
      campaignId
        ? api.get<Paginated<Contact>>(
            contactsPagePath(campaignId, page, search, status, filters)
          )
        : Promise.resolve({ items: [], total: 0 }),
    [campaignId, search, status, page, category, variant, selectedOnly]
  );

  // Batch selection is transient; persistent "Marked" is a distinct CRM field.
  useEffect(() => setChosen(new Set()), [campaignId]);
  const total = contacts.data?.total ?? 0;
  const range = contactPageBounds(page, total);
  useEffect(() => {
    if (!contacts.loading && !contacts.error && contacts.data && page >= range.pages) {
      setPage(range.pages - 1);
    }
  }, [contacts.loading, contacts.error, contacts.data, page, range.pages]);

  if (!campaignId) return <><PageHeader title="Contacts" /><NoCampaign /></>;

  function toggleBatch(id: string) {
    setChosen((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else if (next.size < 100) next.add(id);
      else notify("A batch can contain at most 100 contacts.", "info");
      return next;
    });
  }

  function selectVisible() {
    const ids = contacts.data?.items.map((contact) => contact.id) ?? [];
    const next = new Set(chosen);
    for (const id of ids) {
      if (next.size >= 100 && !next.has(id)) break;
      next.add(id);
    }
    setChosen(next);
    if (next.size < chosen.size + ids.filter((id) => !chosen.has(id)).length) {
      notify("A batch can contain at most 100 contacts.", "info");
    }
  }

  async function applyBulk(action: "mark" | "unmark" | "stop") {
    if (!chosen.size) return;
    setBulkBusy(true);
    try {
      const result = await api.post<{ changed: number; requested: number }>(
        `/campaigns/${encodeURIComponent(campaignId)}/contacts/bulk`,
        { contact_ids: [...chosen], action }
      );
      notify(`${result.changed} of ${result.requested} contacts updated.`, "success");
      setChosen(new Set());
      setStopOpen(false);
      contacts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Bulk update failed", "error");
    } finally {
      setBulkBusy(false);
    }
  }

  async function toggleCheckbox(contact: Contact) {
    try {
      await api.patch(`/campaigns/${campaignId}/contacts/${contact.id}`, {
        checkbox: !contact.checkbox
      });
      contacts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Update failed", "error");
    }
  }

  async function importFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const input = formElement.elements.namedItem("contacts-file") as HTMLInputElement;
    if (!input.files?.[0]) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.set("file", input.files[0]);
      form.set("default_category", DEFAULT_CATEGORY);
      const result = await api.upload<{ added: number; updated_or_existing: number; skipped: number }>(
        `/campaigns/${campaignId}/contacts/import`,
        form
      );
      notify(`${result.added} contacts added to ${activeCampaign?.name ?? "the selected campaign"}, ${result.skipped} skipped`, result.skipped ? "info" : "success");
      setImportOpen(false);
      contacts.reload();
      refreshCampaigns();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Import failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editContact) return;
    setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      await api.patch(`/campaigns/${campaignId}/contacts/${editContact.id}`, {
        full_name: data.get("full_name"),
        email: data.get("email"),
        company: data.get("company"),
        title: data.get("title"),
        public_hook: data.get("public_hook"),
        hook_source: data.get("hook_source"),
        notes: data.get("notes"),
        recipient_timezone: data.get("recipient_timezone"),
        outcome_label: data.get("outcome_label")
      });
      notify("Contact updated. Regenerate drafts to use the changes.", "success");
      setEditContact(null);
      contacts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Update failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function downloadFilteredContacts() {
    setExporting(true);
    try {
      await api.download(
        contactsDownloadPath(campaignId, search, status, filters),
        "offcrm-filtered-contacts.csv"
      );
      notify("Contact CSV downloaded with the current filters.", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Contact export failed", "error");
    } finally {
      setExporting(false);
    }
  }

  const state = <Loadable loading={contacts.loading} error={contacts.error} />;
  return (
    <>
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Contacts"
        description="One clean CRM table. No assignment engine, no owner field and no hidden server."
        actions={<><Button tone="secondary" busy={exporting} onClick={downloadFilteredContacts}>Export filtered CSV</Button> <Button tone="secondary" onClick={() => setManualOpen(true)}>Add contact</Button> <Button onClick={() => setImportOpen(true)}>Import CSV / Excel</Button></>}
      />
      <Panel>
        <div className="toolbar">
          <form
            className="search-box"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(0);
              setSearch(searchInput);
            }}
          >
            <span aria-hidden="true">⌕</span>
            <input aria-label="Search contacts" placeholder="Search name, email or company" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
            <Button type="submit" tone="ghost">Search</Button>
          </form>
          <select aria-label="Filter by status" value={status} onChange={(event) => { setPage(0); setStatus(event.target.value); }}>
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="drafted">Drafted</option>
            <option value="waiting_followup">Waiting follow-up</option>
            <option value="replied">Replied</option>
            <option value="completed">Completed</option>
          </select>
          <select aria-label="Filter by category" value={category} onChange={(event) => { setPage(0); setCategory(event.target.value); }}>
            <option value="">All categories</option>
            {(facets.data?.categories ?? []).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
          <select aria-label="Filter by variant" value={variant} onChange={(event) => { setPage(0); setVariant(event.target.value); }}>
            <option value="">All variants</option>
            {(facets.data?.variants ?? activeCampaign?.variants ?? []).map((name) => <option key={name} value={name}>Variant {name}</option>)}
          </select>
          <label className="checkbox-label">
            <input type="checkbox" checked={selectedOnly} onChange={(event) => { setPage(0); setSelectedOnly(event.target.checked); }} />
            Marked only
          </label>
          <span className="toolbar-count">{total} contacts</span>
        </div>
        <div className="toolbar" aria-label="Audience bulk operations">
          <span>{chosen.size} selected for batch</span>
          <Button tone="ghost" disabled={contacts.loading || !contacts.data?.items.length} onClick={selectVisible}>Select visible page</Button>
          <Button tone="ghost" disabled={!chosen.size} onClick={() => setChosen(new Set())}>Clear batch</Button>
          <Button tone="secondary" disabled={!chosen.size || bulkBusy} onClick={() => void applyBulk("mark")}>Mark selected</Button>
          <Button tone="secondary" disabled={!chosen.size || bulkBusy} onClick={() => void applyBulk("unmark")}>Unmark selected</Button>
          <Button tone="danger" disabled={!chosen.size || bulkBusy} onClick={() => setStopOpen(true)}>Stop outreach</Button>
        </div>
        {contacts.loading || contacts.error ? state : contacts.data?.items.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="checkbox-cell"><span className="sr-only">Marked</span></th><th className="checkbox-cell">Batch</th><th>Contact</th><th>Company</th><th>Category</th><th>Sequence</th><th>Next action</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {contacts.data.items.map((contact) => (
                  <tr key={contact.id}>
                    <td className="checkbox-cell"><input type="checkbox" checked={contact.checkbox} onChange={() => toggleCheckbox(contact)} aria-label={`Mark ${contact.full_name}`} /></td>
                    <td className="checkbox-cell"><input type="checkbox" checked={chosen.has(contact.id)} onChange={() => toggleBatch(contact.id)} aria-label={`Include ${contact.full_name} in batch`} /></td>
                    <td><button className="text-button contact-name" onClick={() => setEditContact(contact)}>{contact.full_name}</button><small>{contact.email || "Email missing"}</small></td>
                    <td><strong>{contact.company || "Not provided"}</strong><small>{contact.title}</small></td>
                    <td><span className="category-text">{contact.category}</span><small>{contact.route === "expert_validation" ? "Expert validation" : "Future client"}</small></td>
                    <td><Badge tone={contact.variant_id === "A" ? "blue" : "violet"}>Variant {contact.variant_id}</Badge><small>{contact.sent_count} sent</small></td>
                    <td><span>{formatDate(contact.next_action_at)}</span><small>{contact.current_stage || "Not started"}</small></td>
                    <td><Badge tone={statusTone(contact.status)}>{contact.status.replaceAll("_", " ")}</Badge></td>
                    <td><Button tone="ghost" onClick={() => setEditContact(contact)}>Edit</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StatePanel title="No contacts found" description={search || status || category || variant || selectedOnly ? "Clear the filters or import more contacts." : "Import a CSV or Excel file to create the first outreach records."} action={!search && !status && !category && !variant && !selectedOnly ? <Button onClick={() => setImportOpen(true)}>Import contacts</Button> : undefined} />
        )}
        {!contacts.loading && !contacts.error && total > CONTACTS_PAGE_SIZE && (
          <nav className="toolbar" aria-label="Contacts pages">
            <span role="status" aria-live="polite">Showing {range.first}–{range.last} of {total} · Page {page + 1} of {range.pages}</span>
            <Button tone="ghost" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous page</Button>
            <Button tone="ghost" disabled={page + 1 >= range.pages} onClick={() => setPage((value) => Math.min(range.pages - 1, value + 1))}>Next page</Button>
          </nav>
        )}
      </Panel>

      <ManualContactModal campaignId={campaignId} open={manualOpen} onClose={() => setManualOpen(false)}
        categories={lockedCategories.data?.categories ?? []} notify={notify}
        onSaved={() => { setPage(0); contacts.reload(); facets.reload(); refreshCampaigns(); }} />
      <StopContactsModal open={stopOpen} total={chosen.size} busy={bulkBusy}
        onClose={() => setStopOpen(false)} onConfirm={() => applyBulk("stop")} />
      <Modal open={importOpen} onClose={() => setImportOpen(false)} title="Import contacts" description="Files are processed on your application host. Contacts are saved only in the selected campaign.">
        <form className="form-stack" onSubmit={importFile}>
          <Field label="CSV or Excel file" hint="Maximum 10 MB. Name is required. Email and a verified public hook are required before sending.">
            <input name="contacts-file" type="file" accept=".csv,.xlsx,.xls" required />
          </Field>
          <div className="form-note"><strong>Recommended columns</strong><span>Full Name, Email, Company, Title, Category, Public Hook, Hook Source and three prepared questions.</span></div>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setImportOpen(false)}>Cancel</Button><Button type="submit" busy={busy}>Import contacts</Button></div>
        </form>
      </Modal>

      <Modal open={Boolean(editContact)} onClose={() => setEditContact(null)} title="Edit contact" description="Drafts are never silently rewritten after a contact changes." wide>
        {editContact ? (
          <form className="form-stack" onSubmit={saveContact}>
            <div className="form-grid"><Field label="Full name"><input name="full_name" defaultValue={editContact.full_name} required /></Field><Field label="Email"><input name="email" type="email" defaultValue={editContact.email} /></Field></div>
            <div className="form-grid"><Field label="Company"><input name="company" defaultValue={editContact.company} /></Field><Field label="Title"><input name="title" defaultValue={editContact.title} /></Field></div>
            <Field label="Verified public hook"><textarea name="public_hook" rows={3} defaultValue={editContact.public_hook} /></Field>
            <Field label="Hook source URL"><input name="hook_source" type="url" defaultValue={editContact.hook_source} /></Field>
            <div className="form-grid"><Field label="Recipient timezone"><input name="recipient_timezone" defaultValue={editContact.recipient_timezone} placeholder="Europe/London" /></Field><Field label="Human outcome label"><select name="outcome_label" defaultValue={editContact.outcome_label || ""}><option value="">Not labelled</option><option value="positive">Positive</option><option value="meeting">Meeting</option><option value="neutral">Neutral</option><option value="negative">Negative</option><option value="not_interested">Not interested</option><option value="wrong_person">Wrong person</option></select></Field></div>
            <Field label="Internal notes"><textarea name="notes" rows={3} defaultValue={editContact.notes} /></Field>
            <div className="form-note"><strong>Learning control</strong><span>Choosing an outcome label turns these notes into approved, de-identified memory. Unlabelled replies remain observations only.</span></div>
            <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setEditContact(null)}>Cancel</Button><Button type="submit" busy={busy}>Save changes</Button></div>
          </form>
        ) : null}
      </Modal>
    </>
  );
}
