import { useEffect, useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, Progress, StatePanel } from "../components";
import { useApp } from "../context";
import { stageLabel, useResource } from "../hooks";
import type { ConnectorsStatus, Draft, Paginated } from "../types";
import { Loadable, NoCampaign, statusTone } from "./shared";

export default function Drafts() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [stage, setStage] = useState("");
  const [approval, setApproval] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Draft | null>(null);
  const [generationOpen, setGenerationOpen] = useState(false);
  const [generationTarget, setGenerationTarget] = useState<Draft | null>(null);
  const [generationMode, setGenerationMode] = useState("local");
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [findText, setFindText] = useState("");
  const [replaceText, setReplaceText] = useState("");
  const [correctionPreview, setCorrectionPreview] = useState<{ matched_drafts: number; occurrences: number } | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const [busy, setBusy] = useState("");
  const drafts = useResource(
    () =>
      campaignId
        ? api.get<Paginated<Draft>>(
            `/campaigns/${campaignId}/drafts?limit=500&stage=${encodeURIComponent(stage)}&approval_status=${encodeURIComponent(approval)}`
          )
        : Promise.resolve({ items: [], total: 0 }),
    [campaignId, stage, approval]
  );
  const connectors = useResource<ConnectorsStatus>(() => api.get("/connectors"), []);
  useEffect(() => setSelected(new Set()), [campaignId, stage, approval]);

  if (!campaignId) return <><PageHeader title="Draft review" /><NoCampaign /></>;

  async function generate(profileId = "") {
    const useBroker = generationMode !== "local";
    setBusy("generate");
    try {
      const result = await api.post<{ generated: number; blocked: number; failures: unknown[] }>(
        `/campaigns/${campaignId}/drafts/generate`,
        {
          campaign_contact_ids: generationTarget ? [generationTarget.campaign_contact_id] : [],
          stages: generationTarget ? [generationTarget.stage] : ["initial", "followup1", "followup2"],
          provider: null,
          use_provider_fallback: useBroker,
          provider_profile_ids: profileId ? [profileId] : [],
          provider_owner: "",
          fallback_strategy: "priority"
        },
        idempotencyKey("drafts")
      );
      notify(`${result.generated} drafts generated, ${result.blocked} blocked by audit`, result.blocked ? "info" : "success");
      setGenerationOpen(false);
      setGenerationTarget(null);
      setEditing(null);
      drafts.reload();
      refreshCampaigns();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Draft generation failed", "error");
    } finally {
      setBusy("");
    }
  }

  function generateFromForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void generate(generationMode === "auto" || generationMode === "local" ? "" : generationMode);
  }

  async function approveSelected() {
    if (!selected.size) return;
    setBusy("approve");
    try {
      const result = await api.post<{ approved: number; blocked: number }>(
        `/campaigns/${campaignId}/drafts/approve`,
        { draft_ids: [...selected], stages: [] }
      );
      notify(`${result.approved} drafts approved${result.blocked ? `, ${result.blocked} blocked` : ""}`, result.blocked ? "info" : "success");
      setSelected(new Set());
      drafts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Approval failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = new FormData(event.currentTarget);
    setBusy("edit");
    try {
      const updated = await api.patch<Draft>(`/campaigns/${campaignId}/drafts/${editing.id}`, {
        subject: data.get("subject"),
        body: data.get("body")
      });
      notify(updated.sendable ? `Draft saved. Quality score ${updated.quality_score}.` : "Draft saved but blocked by audit.", updated.sendable ? "success" : "info");
      setEditing(null);
      drafts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Draft update failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function runBulkCorrection(previewOnly: boolean) {
    if (!selected.size || !findText) return;
    setBusy(previewOnly ? "correction-preview" : "correction-apply");
    try {
      const result = await api.post<{ matched_drafts?: number; occurrences?: number; changed?: number; blocked?: number }>(
        `/campaigns/${campaignId}/drafts/bulk-replace`,
        { find: findText, replace: replaceText, draft_ids: [...selected], stages: [], fields: ["subject", "body"], preview_only: previewOnly }
      );
      if (previewOnly) {
        setCorrectionPreview({ matched_drafts: result.matched_drafts ?? 0, occurrences: result.occurrences ?? 0 });
      } else {
        notify(`${result.changed ?? 0} drafts corrected and re-audited${result.blocked ? `; ${result.blocked} blocked` : ""}`, result.blocked ? "info" : "success");
        setCorrectionOpen(false);
        setCorrectionPreview(null);
        setFindText("");
        setReplaceText("");
        setSelected(new Set());
        drafts.reload();
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : "Bulk correction failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function scheduleSelected(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("schedule");
    try {
      const result = await api.post<{ scheduled: number }>(`/campaigns/${campaignId}/drafts/schedule`, {
        draft_ids: [...selected],
        scheduled_at: scheduleAt ? new Date(scheduleAt).toISOString() : null
      });
      notify(`${result.scheduled} drafts scheduled`, "success");
      setScheduleOpen(false);
      setSelected(new Set());
      drafts.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Scheduling failed", "error");
    } finally {
      setBusy("");
    }
  }

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const state = <Loadable loading={drafts.loading} error={drafts.error} />;
  return (
    <>
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Draft review"
        description="Every email is audited and requires human approval. Replies automatically cancel unsent follow-ups."
        actions={<><Button tone="secondary" busy={busy === "generate"} onClick={() => { setGenerationTarget(null); setGenerationOpen(true); }}>Generate sequence</Button><Button tone="ghost" disabled={!selected.size} onClick={() => setCorrectionOpen(true)}>Correct all</Button><Button tone="ghost" disabled={!selected.size} onClick={() => setScheduleOpen(true)}>Schedule</Button><Button busy={busy === "approve"} disabled={!selected.size} onClick={approveSelected}>Approve selected ({selected.size})</Button></>}
      />
      <Panel>
        <div className="toolbar">
          <select aria-label="Filter by stage" value={stage} onChange={(event) => setStage(event.target.value)}>
            <option value="">All stages</option><option value="initial">First touch</option><option value="followup1">Follow-up 1</option><option value="followup2">Follow-up 2</option>
          </select>
          <select aria-label="Filter by approval" value={approval} onChange={(event) => setApproval(event.target.value)}>
            <option value="">All review states</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="sent">Sent</option><option value="send_failed_review">Send failed</option><option value="cancelled_reply">Cancelled after reply</option>
          </select>
          <span className="toolbar-count">{drafts.data?.total ?? 0} drafts</span>
        </div>
        {drafts.loading || drafts.error ? state : drafts.data?.items.length ? (
          <div className="draft-list">
            {drafts.data.items.map((draft) => (
              <article className={`draft-card ${selected.has(draft.id) ? "draft-selected" : ""}`} key={draft.id}>
                <div className="draft-select"><input type="checkbox" checked={selected.has(draft.id)} disabled={!draft.sendable || !["pending", "send_failed_review"].includes(draft.approval_status)} onChange={() => toggle(draft.id)} aria-label={`Select email for ${draft.full_name}`} /></div>
                <div className="draft-person"><span className="avatar">{draft.full_name.slice(0, 2).toUpperCase()}</span><div><strong>{draft.full_name}</strong><small>{draft.company} · {draft.email}</small></div></div>
                <div className="draft-tags"><Badge tone={draft.variant_id === "A" ? "blue" : "violet"}>Variant {draft.variant_id}</Badge><Badge>{stageLabel(draft.stage)}</Badge><Badge tone={statusTone(draft.approval_status)}>{draft.approval_status.replaceAll("_", " ")}</Badge>{draft.generation_meta?.mode === "ai_personalized" ? <Badge tone="blue">AI · {draft.generation_meta.provider_profile_id?.slice(0, 8) || "provider"}</Badge> : <Badge>Template</Badge>}{draft.scheduled_at ? <Badge tone="warning">Scheduled {new Date(draft.scheduled_at).toLocaleString()}</Badge> : null}</div>
                <div className="draft-copy"><strong>{draft.subject}</strong><p>{draft.body.split("\n").slice(0, 3).join(" ")}</p></div>
                <div className="quality"><div><span>Quality</span><strong className={draft.sendable ? "quality-good" : "quality-bad"}>{draft.quality_score}</strong></div><Progress value={draft.quality_score} />{draft.audit.errors.length ? <small className="error-text">{draft.audit.errors[0]}</small> : draft.audit.warnings.length ? <small>{draft.audit.warnings[0]}</small> : <small>All hard checks passed</small>}</div>
                <div className="draft-actions"><Button tone="ghost" onClick={() => { setGenerationTarget(draft); setGenerationOpen(true); }}>Regenerate</Button><Button tone="ghost" onClick={() => setEditing(draft)}>Review and edit</Button></div>
              </article>
            ))}
          </div>
        ) : (
          <StatePanel title="No drafts found" description="Generate a three-stage sequence from the local OFF_CRM templates, or change your filters." action={<Button onClick={() => { setGenerationTarget(null); setGenerationOpen(true); }} busy={busy === "generate"}>Generate sequence</Button>} />
        )}
      </Panel>
      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Review email" description="Saving reruns every hard safety and quality check." wide>
        {editing ? (
          <form className="form-stack" onSubmit={saveDraft}>
            <div className="review-meta"><div><span>Recipient</span><strong>{editing.full_name}</strong></div><div><span>Stage</span><strong>{stageLabel(editing.stage)}</strong></div><div><span>Variant</span><strong>{editing.variant_id}</strong></div><div><span>Quality</span><strong>{editing.quality_score}/100</strong></div></div>
            <div className="form-note"><strong>Generation trace</strong><span>{editing.generation_meta?.mode === "ai_personalized" ? `AI provider ${editing.generation_meta.provider_profile_id || "fallback chain"}` : "Local template only"} · {editing.retrieval_refs.length} context references</span></div>
            <Field label="Subject"><input name="subject" defaultValue={editing.subject} required maxLength={500} /></Field>
            <Field label="Body"><textarea name="body" defaultValue={editing.body} rows={18} required /></Field>
            {editing.audit.errors.length || editing.audit.warnings.length ? <div className="audit-box"><strong>Current audit</strong>{editing.audit.errors.map((item) => <p className="error-text" key={item}>Blocked: {item}</p>)}{editing.audit.warnings.map((item) => <p key={item}>Review: {item}</p>)}</div> : <div className="form-note success-note"><strong>All hard checks passed</strong><span>The draft still needs your approval before sending.</span></div>}
            <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setEditing(null)}>Cancel</Button><Button type="submit" busy={busy === "edit"}>Save and re-audit</Button></div>
          </form>
        ) : null}
      </Modal>
      <Modal open={correctionOpen} onClose={() => setCorrectionOpen(false)} title="Apply correction to selected drafts" description="Preview the exact replacement first. Every changed email is re-audited and returned to pending approval.">
        <div className="form-stack">
          <Field label="Find exact text"><textarea value={findText} onChange={(event) => { setFindText(event.target.value); setCorrectionPreview(null); }} rows={4} required /></Field>
          <Field label="Replace with"><textarea value={replaceText} onChange={(event) => { setReplaceText(event.target.value); setCorrectionPreview(null); }} rows={4} /></Field>
          {correctionPreview ? <div className="form-note"><strong>{correctionPreview.matched_drafts} drafts match</strong><span>{correctionPreview.occurrences} exact replacements will be made.</span></div> : null}
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setCorrectionOpen(false)}>Cancel</Button><Button type="button" tone="secondary" busy={busy === "correction-preview"} disabled={!findText} onClick={() => runBulkCorrection(true)}>Preview</Button><Button type="button" busy={busy === "correction-apply"} disabled={!correctionPreview?.matched_drafts} onClick={() => runBulkCorrection(false)}>Apply to all</Button></div>
        </div>
      </Modal>
      <Modal open={scheduleOpen} onClose={() => setScheduleOpen(false)} title="Schedule selected drafts" description="This time is an additional not-before gate. Campaign timezone and send-window rules still apply.">
        <form className="form-stack" onSubmit={scheduleSelected}>
          <Field label="Do not send before"><input type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)} required /></Field>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setScheduleOpen(false)}>Cancel</Button><Button type="submit" busy={busy === "schedule"}>Schedule {selected.size}</Button></div>
        </form>
      </Modal>
      <Modal open={generationOpen} onClose={() => { setGenerationOpen(false); setGenerationTarget(null); }} title={generationTarget ? `Regenerate ${stageLabel(generationTarget.stage)} draft` : "Generate three-stage sequence"} description={generationTarget ? `Only the draft for ${generationTarget.full_name} will be replaced and returned to pending review.` : "The template rules stay constant. An AI provider is optional and can only personalise within those rules."}>
        <form className="form-stack" onSubmit={generateFromForm}>
          <Field label="Generation mode">
            <select value={generationMode} onChange={(event) => setGenerationMode(event.target.value)}>
              <option value="local">Local templates only</option>
              <option value="auto" disabled={!connectors.data?.ai_providers.some((profile) => (profile.effective_trust_tier || profile.trust_tier) === "A")}>
                Automatic eligible Tier A routing
              </option>
              {connectors.data?.ai_providers
                .filter((profile) => (profile.effective_trust_tier || profile.trust_tier) === "A" && profile.allowed_task_types.includes("outreach_draft"))
                .map((profile) => (
                  <option key={profile.id} value={profile.id}>{profile.name} · {profile.model}</option>
                ))}
            </select>
          </Field>
          {generationMode !== "local" ? <div className="form-note success-note"><strong>OFF_AI broker enforced</strong><span>The provider receives only public professional facts, positioning, and the template. Email addresses and CRM fields stay local. Failover remains inside the same trust tier.</span></div> : null}
          {generationMode !== "local" && !connectors.data?.ai_providers.some((profile) => (profile.effective_trust_tier || profile.trust_tier) === "A" && profile.allowed_task_types.includes("outreach_draft")) ? <div className="danger-note"><strong>No eligible outreach model</strong><span>Classify a provider under Connectors with verified Tier A terms and the outreach-draft task enabled.</span></div> : null}
          <div className="form-note"><strong>Human review remains mandatory.</strong><span>Generated output is re-audited. Missing sources, invented fields and unsafe language stay blocked.</span></div>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => { setGenerationOpen(false); setGenerationTarget(null); }}>Cancel</Button><Button type="submit" busy={busy === "generate"}>{generationTarget ? "Regenerate draft" : "Generate drafts"}</Button></div>
        </form>
      </Modal>
    </>
  );
}
