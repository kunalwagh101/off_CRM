import { Fragment, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { Campaign, CampaignKind } from "../types";
import { statusTone } from "./shared";
import { CampaignPerformancePanel, CampaignSettingsModal, CloneCampaignModal } from "./CampaignOperations";

export default function Campaigns() {
  const { campaigns, campaignId, selectCampaign, createCampaign, refreshCampaigns, notify } = useApp();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Campaign | null>(null);
  const [cloning, setCloning] = useState<Campaign | null>(null);
  const [archiving, setArchiving] = useState<Campaign | null>(null);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [performanceId, setPerformanceId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("email");
  const [limit, setLimit] = useState(25);
  // Kinds that cannot run yet are shown rather than hidden. A picker that omits
  // them looks like the feature was never planned; one that shows them with the
  // reason says where the product is going.
  const kinds = useResource<{ items: CampaignKind[] }>(
    () => api.get<{ items: CampaignKind[] }>("/campaign-kinds"),
    []
  );
  const selectedKind = kinds.data?.items.find((item) => item.id === kind);
  // Email's settings live in real columns; other kinds leave them at defaults,
  // so showing send windows for a picture campaign would be a lie in a form.
  const emailShaped = selectedKind?.uses_email_columns ?? true;
  const runnable = selectedKind?.implemented ?? true;
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [windowStart, setWindowStart] = useState("09:00");
  const [windowEnd, setWindowEnd] = useState("17:00");
  const [hypothesis, setHypothesis] = useState("");
  const [minimumSample, setMinimumSample] = useState(40);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      // The store creates, selects and refreshes as one step, so the stale list
      // that arrives after the save cannot select an older campaign (A33).
      await createCampaign(
        {
          name,
          kind,
          daily_send_limit: limit,
          timezone,
          variants: ["A", "B"],
          send_window_start: windowStart,
          send_window_end: windowEnd,
          send_weekdays: [0, 1, 2, 3, 4],
          experiment_hypothesis: hypothesis,
          experiment_min_sample: minimumSample,
          control_variant: "A"
        }
      );
      setOpen(false);
      setName("");
      setKind("email");
      notify("Campaign created", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Campaign creation failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(campaign: Campaign) {
    const next = campaign.status === "active" ? "paused" : campaign.status === "archived" ? "paused" : "active";
    setLifecycleBusy(true);
    try {
      await api.patch(`/campaigns/${encodeURIComponent(campaign.id)}`, { status: next });
      refreshCampaigns();
      notify(next === "active" ? "Campaign resumed" : next === "paused" && campaign.status === "archived" ? "Campaign restored as paused" : "Campaign paused", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Update failed", "error");
    } finally {
      setLifecycleBusy(false);
    }
  }

  async function archiveCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!archiving) return;
    const value = new FormData(event.currentTarget).get("confirmation");
    if (value !== "ARCHIVE") {
      notify("Type ARCHIVE to confirm.", "error");
      return;
    }
    setLifecycleBusy(true);
    try {
      await api.patch(`/campaigns/${encodeURIComponent(archiving.id)}`, { status: "archived" });
      notify("Campaign archived. No messages were deleted.", "success");
      setArchiving(null);
      refreshCampaigns();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Archive failed", "error");
    } finally {
      setLifecycleBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspaces"
        title="Campaigns"
        description="Each campaign has its own daily cap, A/B split, review queue and reply-stop state."
        actions={<Button onClick={() => setOpen(true)}>Create campaign</Button>}
      />
      {campaigns.length ? (
        <div className="card-grid">
          {campaigns.map((campaign) => (
            <Fragment key={campaign.id}>
            <Panel className={campaign.id === campaignId ? "selected-card" : ""}>
              <div className="campaign-card-top">
                <span className="campaign-mark large">{campaign.name.slice(0, 2).toUpperCase()}</span>
                <span className="campaign-card-tags">
                  <Badge tone="neutral">{campaign.kind}</Badge>
                  <Badge tone={statusTone(campaign.status)}>{campaign.status}</Badge>
                </span>
              </div>
              <h2>{campaign.name}</h2>
              <p className="muted">Updated {formatDate(campaign.updated_at)}</p>
              <div className="mini-stats">
                <span><strong>{campaign.contact_count ?? 0}</strong>contacts</span>
                <span><strong>{campaign.sent_count ?? 0}</strong>sent</span>
                <span><strong>{campaign.replied_count ?? 0}</strong>replies</span>
              </div>
              <div className="card-meta">
                <span>{campaign.daily_send_limit} emails/day</span>
                <span>{campaign.timezone}</span>
                <span>{campaign.send_window_start}–{campaign.send_window_end}</span>
                <span>Variants {campaign.variants.join(" / ")}</span>
              </div>
              <div className="card-actions">
                <Button
                  onClick={() => {
                    selectCampaign(campaign.id);
                    window.location.hash = "contacts";
                  }}
                >Open workspace</Button>
                <Button tone="ghost" disabled={lifecycleBusy} onClick={() => toggle(campaign)}>
                  {campaign.status === "active" ? "Pause" : campaign.status === "archived" ? "Restore paused" : "Resume"}
                </Button>
                <Button tone="ghost" onClick={() => setEditing(campaign)}>Edit settings</Button>
                <Button tone="ghost" onClick={() => setCloning(campaign)}>Duplicate settings</Button>
                <Button tone="ghost" onClick={() => setPerformanceId(performanceId === campaign.id ? "" : campaign.id)}>
                  {performanceId === campaign.id ? "Hide performance" : "Performance"}
                </Button>
                {campaign.status !== "archived" && <Button tone="ghost" onClick={() => setArchiving(campaign)}>Archive</Button>}
              </div>
            </Panel>
            {performanceId === campaign.id && <CampaignPerformancePanel campaign={campaign} />}
            </Fragment>
          ))}
        </div>
      ) : (
        <StatePanel
          title="No campaigns yet"
          description="Create one, then import a CSV or Excel file with verified contacts and public hooks."
          action={<Button onClick={() => setOpen(true)}>Create campaign</Button>}
        />
      )}
      <CampaignSettingsModal campaign={editing} close={() => setEditing(null)} changed={refreshCampaigns} notify={notify} />
      <CloneCampaignModal campaign={cloning} close={() => setCloning(null)}
        notify={notify} created={(id) => { refreshCampaigns(); selectCampaign(id); }} />
      <Modal open={Boolean(archiving)} onClose={() => setArchiving(null)} title="Archive campaign"
        description="Archiving stops this campaign from running. Existing contacts, drafts and reports are retained.">
        <form className="form-stack" onSubmit={archiveCampaign}>
          <p>Archive <strong>{archiving?.name}</strong>? You can restore it later as paused.</p>
          <Field label="Type ARCHIVE to confirm"><input name="confirmation" pattern="ARCHIVE" autoComplete="off" required /></Field>
          <div className="modal-actions">
            <Button type="button" tone="ghost" onClick={() => setArchiving(null)}>Cancel</Button>
            <Button type="submit" tone="danger" busy={lifecycleBusy}>Archive campaign</Button>
          </div>
        </form>
      </Modal>
      <Modal open={open} onClose={() => setOpen(false)} title="Create campaign" description="Start small. The daily cap can be changed later.">
        <form onSubmit={create} className="form-stack">
          <Field label="Campaign name"><input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} autoFocus /></Field>
          <Field label="Kind" hint={selectedKind?.summary ?? "What this campaign sends."}>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {(kinds.data?.items ?? [{ id: "email", label: "Email outreach", implemented: true } as CampaignKind]).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}{item.implemented ? "" : " — not built yet"}
                </option>
              ))}
            </select>
          </Field>
          {selectedKind && !selectedKind.implemented ? (
            <div className="form-note">
              <strong>{selectedKind.label} campaigns are not built yet.</strong>
              <span>Still missing: {selectedKind.missing}</span>
            </div>
          ) : null}
          {emailShaped ? (
            <>
              <div className="form-grid">
                <Field label="Daily send limit"><input type="number" value={limit} min={1} max={500} onChange={(event) => setLimit(Number(event.target.value))} required /></Field>
                <Field label="Timezone"><input value={timezone} onChange={(event) => setTimezone(event.target.value)} required /></Field>
              </div>
              <div className="form-grid">
                <Field label="Send window starts"><input type="time" value={windowStart} onChange={(event) => setWindowStart(event.target.value)} required /></Field>
                <Field label="Send window ends"><input type="time" value={windowEnd} onChange={(event) => setWindowEnd(event.target.value)} required /></Field>
              </div>
              <Field label="Experiment hypothesis" hint="Example: a specific operational hook will increase replies."><input value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} maxLength={1000} /></Field>
              <Field label="Minimum sends per variant"><input type="number" value={minimumSample} min={10} max={100000} onChange={(event) => setMinimumSample(Number(event.target.value))} /></Field>
              <div className="form-note"><strong>A/B testing is on.</strong><span>Contacts are assigned deterministically to A or B, so reruns stay stable.</span></div>
            </>
          ) : null}
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" busy={busy} disabled={!runnable}>Create campaign</Button></div>
        </form>
      </Modal>
    </>
  );
}
