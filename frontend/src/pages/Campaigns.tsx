import { useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate } from "../hooks";
import type { Campaign } from "../types";
import { statusTone } from "./shared";

export default function Campaigns() {
  const { campaigns, campaignId, selectCampaign, refreshCampaigns, notify } = useApp();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [limit, setLimit] = useState(25);
  const [timezone, setTimezone] = useState("Asia/Kolkata");

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const campaign = await api.post<Campaign>(
        "/campaigns",
        { name, daily_send_limit: limit, timezone, variants: ["A", "B"] },
        idempotencyKey("campaign")
      );
      selectCampaign(campaign.id);
      refreshCampaigns();
      setOpen(false);
      setName("");
      notify("Campaign created", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Campaign creation failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(campaign: Campaign) {
    try {
      await api.patch(`/campaigns/${campaign.id}`, {
        status: campaign.status === "active" ? "paused" : "active"
      });
      refreshCampaigns();
      notify(campaign.status === "active" ? "Campaign paused" : "Campaign resumed", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Update failed", "error");
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
            <Panel key={campaign.id} className={campaign.id === campaignId ? "selected-card" : ""}>
              <div className="campaign-card-top">
                <span className="campaign-mark large">{campaign.name.slice(0, 2).toUpperCase()}</span>
                <Badge tone={statusTone(campaign.status)}>{campaign.status}</Badge>
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
                <span>Variants {campaign.variants.join(" / ")}</span>
              </div>
              <div className="card-actions">
                <Button
                  onClick={() => {
                    selectCampaign(campaign.id);
                    window.location.hash = "contacts";
                  }}
                >Open workspace</Button>
                <Button tone="ghost" onClick={() => toggle(campaign)}>
                  {campaign.status === "active" ? "Pause" : "Resume"}
                </Button>
              </div>
            </Panel>
          ))}
        </div>
      ) : (
        <StatePanel
          title="No campaigns yet"
          description="Create one, then import a CSV or Excel file with verified contacts and public hooks."
          action={<Button onClick={() => setOpen(true)}>Create campaign</Button>}
        />
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Create campaign" description="Start small. The daily cap can be changed later.">
        <form onSubmit={create} className="form-stack">
          <Field label="Campaign name"><input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} autoFocus /></Field>
          <div className="form-grid">
            <Field label="Daily send limit"><input type="number" value={limit} min={1} max={500} onChange={(event) => setLimit(Number(event.target.value))} required /></Field>
            <Field label="Timezone"><input value={timezone} onChange={(event) => setTimezone(event.target.value)} required /></Field>
          </div>
          <div className="form-note"><strong>A/B testing is on.</strong><span>Contacts are assigned deterministically to A or B, so reruns stay stable.</span></div>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" busy={busy}>Create campaign</Button></div>
        </form>
      </Modal>
    </>
  );
}
