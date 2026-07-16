import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { Contact, Paginated } from "../types";
import { Loadable, NoCampaign, statusTone } from "./shared";

const DEFAULT_CATEGORY = "Sustainability / ESG / Climate";

export default function Contacts() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [editContact, setEditContact] = useState<Contact | null>(null);
  const [busy, setBusy] = useState(false);
  const contacts = useResource(
    () =>
      campaignId
        ? api.get<Paginated<Contact>>(
            `/campaigns/${campaignId}/contacts?limit=500&search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`
          )
        : Promise.resolve({ items: [], total: 0 }),
    [campaignId, search, status]
  );

  if (!campaignId) return <><PageHeader title="Contacts" /><NoCampaign /></>;

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
      notify(`${result.added} contacts added, ${result.skipped} skipped`, result.skipped ? "info" : "success");
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
        notes: data.get("notes")
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

  const state = <Loadable loading={contacts.loading} error={contacts.error} />;
  return (
    <>
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Contacts"
        description="One clean CRM table. No assignment engine, no owner field and no hidden server."
        actions={<Button onClick={() => setImportOpen(true)}>Import CSV / Excel</Button>}
      />
      <Panel>
        <div className="toolbar">
          <form
            className="search-box"
            onSubmit={(event) => {
              event.preventDefault();
              setSearch(searchInput);
            }}
          >
            <span aria-hidden="true">⌕</span>
            <input aria-label="Search contacts" placeholder="Search name, email or company" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
            <Button type="submit" tone="ghost">Search</Button>
          </form>
          <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="drafted">Drafted</option>
            <option value="waiting_followup">Waiting follow-up</option>
            <option value="replied">Replied</option>
            <option value="completed">Completed</option>
          </select>
          <span className="toolbar-count">{contacts.data?.total ?? 0} contacts</span>
        </div>
        {contacts.loading || contacts.error ? state : contacts.data?.items.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="checkbox-cell"><span className="sr-only">Selected</span></th><th>Contact</th><th>Company</th><th>Category</th><th>Sequence</th><th>Next action</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {contacts.data.items.map((contact) => (
                  <tr key={contact.id}>
                    <td className="checkbox-cell"><input type="checkbox" checked={contact.checkbox} onChange={() => toggleCheckbox(contact)} aria-label={`Select ${contact.full_name}`} /></td>
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
          <StatePanel title="No contacts found" description={search || status ? "Clear the filters or import more contacts." : "Import a CSV or Excel file to create the first outreach records."} action={!search && !status ? <Button onClick={() => setImportOpen(true)}>Import contacts</Button> : undefined} />
        )}
      </Panel>

      <Modal open={importOpen} onClose={() => setImportOpen(false)} title="Import contacts" description="Files stay on this device and are deleted from the upload area after import.">
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
            <Field label="Internal notes"><textarea name="notes" rows={3} defaultValue={editContact.notes} /></Field>
            <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setEditContact(null)}>Cancel</Button><Button type="submit" busy={busy}>Save changes</Button></div>
          </form>
        ) : null}
      </Modal>
    </>
  );
}
