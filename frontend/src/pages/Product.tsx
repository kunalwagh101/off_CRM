import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { GtmProduct } from "../types";
import { Loadable } from "./shared";

/** The editable shape of a product: lists are typed one item per line. */
type Draft = {
  name: string;
  one_liner: string;
  audience: string;
  problem: string;
  outcome: string;
  offer: string;
  proof: string;
  differentiators: string;
  forbidden_claims: string;
  voice: string;
  website: string;
};

const EMPTY: Draft = {
  name: "",
  one_liner: "",
  audience: "",
  problem: "",
  outcome: "",
  offer: "",
  proof: "",
  differentiators: "",
  forbidden_claims: "",
  voice: "",
  website: ""
};

const LIST_FIELDS = ["proof", "differentiators", "forbidden_claims"] as const;

function toDraft(product: GtmProduct): Draft {
  return {
    name: product.name,
    one_liner: product.one_liner,
    audience: product.audience,
    problem: product.problem,
    outcome: product.outcome,
    offer: product.offer,
    proof: product.proof.join("\n"),
    differentiators: product.differentiators.join("\n"),
    forbidden_claims: product.forbidden_claims.join("\n"),
    voice: product.voice,
    website: product.website
  };
}

function toBody(draft: Draft): Record<string, unknown> {
  const body: Record<string, unknown> = { ...draft };
  for (const field of LIST_FIELDS) {
    body[field] = draft[field].split("\n").map((line) => line.trim()).filter(Boolean);
  }
  return body;
}

export default function Product() {
  const { notify } = useApp();
  const products = useResource(() => api.get<{ items: GtmProduct[] }>("/gtm/products"), []);
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<{ field: string; message: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const items = products.data?.items ?? [];
  const selected = items.find((item) => item.id === selectedId) ?? null;

  // Open the first product once the list arrives. Most owners have one.
  useEffect(() => {
    if (!selectedId && items.length) {
      setSelectedId(items[0].id);
      setDraft(toDraft(items[0]));
    }
  }, [items, selectedId]);

  function set(field: keyof Draft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function open(product: GtmProduct | null) {
    setSelectedId(product?.id ?? "");
    setDraft(product ? toDraft(product) : EMPTY);
    setRefusal(null);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setRefusal(null);
    try {
      const saved = selected
        ? await api.patch<GtmProduct>(`/gtm/products/${selected.id}`, toBody(draft))
        : await api.post<GtmProduct>("/gtm/products", toBody(draft));
      notify(selected ? `Saved as version ${saved.version}.` : "Product saved.", "success");
      setSelectedId(saved.id);
      setDraft(toDraft(saved));
      products.reload();
    } catch (caught) {
      const detail = caught instanceof ApiError ? (caught.detail as { field?: string } | undefined) : undefined;
      const message = caught instanceof Error ? caught.message : "The product could not be saved.";
      setRefusal({ field: detail?.field ?? "", message });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!selected) return;
    setBusy(true);
    try {
      await api.delete<{ deleted: boolean }>(`/gtm/products/${selected.id}`);
      notify("Product deleted. Plans written against it keep their own copy.", "success");
      setConfirmDelete(false);
      open(null);
      products.reload();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "The product could not be deleted.", "error");
    } finally {
      setBusy(false);
    }
  }

  // Points assistive technology at the field the server refused; the note
  // above the form names it in words for everyone else.
  const flag = (field: string) => refusal?.field === field;

  return (
    <>
      <PageHeader
        eyebrow="Strategy"
        title="Your product, described once"
        description="Every email, caption and plan off_CRM writes for a linked campaign starts here. Change it once and the next thing written uses the new version."
        actions={<Button tone="secondary" onClick={() => open(null)}>New product</Button>}
      />
      <div className="settings-grid">
        <Panel title="Products" subtitle="Most workspaces have one.">
          <Loadable loading={products.loading} error={products.error} />
          {!products.loading && !products.error && items.length === 0 ? (
            <StatePanel title="No product yet" description="Describe it on the right. The strategy brain has nothing to plan with until you do." />
          ) : null}
          <div className="memory-list">
            {items.map((item) => (
              <div key={item.id}>
                <p>
                  <strong>{item.name}</strong>
                  <span>{item.one_liner}</span>
                  <small>version {item.version} · updated {formatDate(item.updated_at)}</small>
                </p>
                {item.id === selectedId ? (
                  <Badge tone="success">Editing</Badge>
                ) : (
                  <Button tone="ghost" onClick={() => open(item)}>Open</Button>
                )}
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title={selected ? `${selected.name} · version ${selected.version}` : "A new product"}
          subtitle="Anything here may be sent to a model as campaign material, so email addresses are refused — put those in Settings."
        >
          <form className="form-stack" onSubmit={save} noValidate>
            {refusal ? <p className="danger-note" role="alert">{refusal.message}</p> : null}
            <Field label="Name">
              <input id="gtm-name" aria-invalid={flag("name")} value={draft.name} maxLength={80} onChange={(e) => set("name", e.target.value)} required />
            </Field>
            <Field label="One-liner" hint="The public pitch, 10–200 characters. The only part sent to a provider you have set to a minimal data policy.">
              <input id="gtm-one-liner" aria-invalid={flag("one_liner")} value={draft.one_liner} maxLength={200} onChange={(e) => set("one_liner", e.target.value)} required />
            </Field>
            <Field label="Who it is for">
              <textarea id="gtm-audience" aria-invalid={flag("audience")} value={draft.audience} maxLength={600} rows={2} onChange={(e) => set("audience", e.target.value)} required />
            </Field>
            <Field label="The problem it solves" hint="In the customer's words, not yours.">
              <textarea id="gtm-problem" aria-invalid={flag("problem")} value={draft.problem} maxLength={600} rows={2} onChange={(e) => set("problem", e.target.value)} required />
            </Field>
            <Field label="What changes for them">
              <textarea id="gtm-outcome" aria-invalid={flag("outcome")} value={draft.outcome} maxLength={600} rows={2} onChange={(e) => set("outcome", e.target.value)} />
            </Field>
            <Field label="The offer" hint="The one thing you ask them to do.">
              <input id="gtm-offer" aria-invalid={flag("offer")} value={draft.offer} maxLength={200} onChange={(e) => set("offer", e.target.value)} required />
            </Field>
            <Field label="Proof" hint="One result per line, up to 8.">
              <textarea id="gtm-proof" aria-invalid={flag("proof")} value={draft.proof} rows={3} onChange={(e) => set("proof", e.target.value)} />
            </Field>
            <Field label="What makes it different" hint="One per line, up to 6.">
              <textarea id="gtm-differentiators" aria-invalid={flag("differentiators")} value={draft.differentiators} rows={2} onChange={(e) => set("differentiators", e.target.value)} />
            </Field>
            <Field label="Never claim" hint="One phrase per line. Anything the strategy brain writes is checked against these, and a plan that uses one has that line removed.">
              <textarea id="gtm-forbidden" aria-invalid={flag("forbidden_claims")} value={draft.forbidden_claims} rows={3} onChange={(e) => set("forbidden_claims", e.target.value)} />
            </Field>
            <Field label="Voice" hint="How it should sound.">
              <input id="gtm-voice" aria-invalid={flag("voice")} value={draft.voice} maxLength={300} onChange={(e) => set("voice", e.target.value)} />
            </Field>
            <Field label="Website">
              <input id="gtm-website" aria-invalid={flag("website")} type="url" value={draft.website} maxLength={300} onChange={(e) => set("website", e.target.value)} />
            </Field>
            <div className="modal-actions">
              <Button type="submit" busy={busy}>{selected ? "Save a new version" : "Save product"}</Button>
              {selected ? <Button type="button" tone="danger" onClick={() => setConfirmDelete(true)}>Delete</Button> : null}
            </div>
          </form>
        </Panel>
      </div>

      <Modal
        open={confirmDelete && selected !== null}
        title={`Delete ${selected?.name ?? "this product"}?`}
        description="Plans already written keep their own copy of this product. Campaigns linked to it stop using it."
        onClose={() => setConfirmDelete(false)}
      >
        <div className="modal-actions">
          <Button tone="secondary" onClick={() => setConfirmDelete(false)}>Keep it</Button>
          <Button tone="danger" busy={busy} onClick={remove}>Delete product</Button>
        </div>
      </Modal>
    </>
  );
}
