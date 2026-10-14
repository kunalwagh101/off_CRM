import { useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Button, Field, Modal } from "../components";

export type ManualContactResult = { id: string; added: boolean; reused_contact: boolean };

export function ManualContactModal({
  campaignId, open, onClose, onSaved, notify, categories
}: {
  campaignId: string;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  notify: (message: string, tone: "success" | "error" | "info") => void;
  categories: string[];
}) {
  const [busy, setBusy] = useState(false);
  const [requestKey, setRequestKey] = useState(() => idempotencyKey("manual-contact"));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const result = await api.post<ManualContactResult>(
        `/campaigns/${encodeURIComponent(campaignId)}/contacts/manual`,
        {
          full_name: String(data.get("full_name") ?? ""),
          email: String(data.get("email") ?? ""),
          company: String(data.get("company") ?? ""),
          title: String(data.get("title") ?? ""),
          category: String(data.get("category") ?? ""),
          public_hook: String(data.get("public_hook") ?? ""),
          hook_source: String(data.get("hook_source") ?? ""),
          recipient_timezone: String(data.get("recipient_timezone") ?? "")
        },
        requestKey
      );
      notify(result.added
        ? "Contact added to this campaign. No draft was generated or sent."
        : "This email already belongs to the campaign; no duplicate was created.",
        result.added ? "success" : "info");
      setRequestKey(idempotencyKey("manual-contact"));
      onSaved();
      onClose();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not add contact", "error");
    } finally {
      setBusy(false);
    }
  }

  const options = [...new Set(["Sustainability / ESG / Climate", ...categories])];
  return <Modal open={open} onClose={onClose} title="Add a contact"
    description="Manual entry links existing emails instead of duplicating them. Nothing is generated, approved or sent automatically.">
    <form className="form-stack" onSubmit={submit}>
      <Field label="Full name"><input name="full_name" required minLength={1} maxLength={200} autoComplete="name" /></Field>
      <Field label="Work email"><input name="email" type="email" required maxLength={254} autoComplete="email" /></Field>
      <div className="form-grid">
        <Field label="Company"><input name="company" maxLength={200} /></Field>
        <Field label="Job title"><input name="title" maxLength={200} /></Field>
      </div>
      <Field label="Category"><select name="category" defaultValue={options[0]}>
        {options.map((item) => <option key={item} value={item}>{item}</option>)}
      </select></Field>
      <Field label="Verified public research hook"><textarea name="public_hook" maxLength={1000} rows={2} /></Field>
      <Field label="Source URL"><input name="hook_source" type="url" maxLength={1000} placeholder="https://..." /></Field>
      <Field label="Recipient timezone"><input name="recipient_timezone" maxLength={80} placeholder="Europe/London" /></Field>
      <div className="modal-actions">
        <Button type="button" tone="ghost" onClick={onClose}>Cancel</Button>
        <Button type="submit" busy={busy}>Add contact</Button>
      </div>
    </form>
  </Modal>;
}

export function StopContactsModal({
  open, total, busy, onClose, onConfirm
}: {
  open: boolean;
  total: number;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (data.get("confirmation") === "STOP") void onConfirm();
  }
  return <Modal open={open} onClose={onClose} title="Stop outreach to selected contacts"
    description="Stops current and future campaign sends for these contacts. It does not erase their history.">
    <form key={open ? "active" : "closed"} className="form-stack" onSubmit={submit}>
      <p>{total} selected campaign contacts. Replied or completed contacts are left unchanged.</p>
      <Field label="Type STOP to confirm"><input name="confirmation" required pattern="STOP" autoComplete="off" /></Field>
      <div className="modal-actions">
        <Button type="button" tone="ghost" onClick={onClose}>Cancel</Button>
        <Button type="submit" tone="danger" busy={busy}>Stop selected outreach</Button>
      </div>
    </form>
  </Modal>;
}
