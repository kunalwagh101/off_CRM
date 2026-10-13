import { useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Button, Field, Modal, Panel, StatCard } from "../components";
import { useResource } from "../hooks";
import type { Campaign } from "../types";

export type CampaignPerformance = {
  campaign_id: string;
  kind: string;
  contacts: number;
  contacted: number;
  messages_sent: number;
  replied: number;
  replied_contacted: number;
  completed: number;
  stopped: number;
  awaiting_first_contact: number;
  reply_rate: number;
  reply_rate_denominator: "unique_contacts_sent";
  draft_status: Record<string, number>;
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function CampaignPerformancePanel({ campaign }: { campaign: Campaign }) {
  const performance = useResource(
    () => api.get<CampaignPerformance>(`/campaigns/${encodeURIComponent(campaign.id)}/performance`),
    [campaign.id]
  );
  if (performance.loading) return <Panel title="Campaign performance">Loading verified campaign data…</Panel>;
  if (performance.error) return <Panel title="Campaign performance">
    <p role="alert">{performance.error}</p>
    <Button onClick={performance.reload}>Retry</Button>
  </Panel>;
  const data = performance.data;
  if (!data) return null;
  const email = data.kind === "email";
  return <Panel title="Campaign performance" subtitle="Based on saved campaign records, not estimates">
    <div className="stats-grid compact-stats">
      <StatCard label="Contacts" value={data.contacts} />
      <StatCard label="Contacted" value={data.contacted} detail="distinct recipients with an outbound message" />
      <StatCard label="Outbound messages" value={data.messages_sent} />
      <StatCard label="Replies" value={data.replied} />
      <StatCard label="Reply rate" value={email ? `${data.reply_rate}%` : "N/A"} detail={email ? "Replies from contacted people ÷ unique contacts sent" : "Email-only metric"} />
      <StatCard label="Awaiting first contact" value={data.awaiting_first_contact} />
    </div>
    <p className="muted">Completed: {data.completed} · Stopped: {data.stopped}. Counts are recorded state; they do not claim delivery or inbox placement.</p>
    <h3>Draft review status</h3>
    {Object.keys(data.draft_status).length ? (
      <ul>{Object.entries(data.draft_status).sort(([a], [b]) => a.localeCompare(b)).map(([status, count]) => (
        <li key={status}>{status.replaceAll("_", " ")}: {count}</li>
      ))}</ul>
    ) : <p>No drafts recorded for this campaign.</p>}
    <Button tone="ghost" onClick={performance.reload}>Refresh performance</Button>
  </Panel>;
}

export function CampaignSettingsModal({
  campaign, close, changed, notify
}: {
  campaign: Campaign | null;
  close: () => void;
  changed: () => void;
  notify: (message: string, tone: "success" | "error") => void;
}) {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!campaign) return;
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = { name: String(form.get("name") || "").trim() };
    if (campaign.kind === "email") {
      const weekdays = form.getAll("send_weekdays").map(Number);
      if (!weekdays.length) {
        notify("Choose at least one sending weekday.", "error");
        return;
      }
      Object.assign(payload, {
        daily_send_limit: Number(form.get("daily_send_limit")),
        timezone: String(form.get("timezone") || "").trim(),
        send_window_start: String(form.get("send_window_start") || ""),
        send_window_end: String(form.get("send_window_end") || ""),
        send_weekdays: weekdays,
        followup1_working_days: Number(form.get("followup1_working_days")),
        followup2_working_days: Number(form.get("followup2_working_days")),
        approval_mode: String(form.get("approval_mode") || ""),
        experiment_hypothesis: String(form.get("experiment_hypothesis") || ""),
        experiment_min_sample: Number(form.get("experiment_min_sample")),
        control_variant: String(form.get("control_variant") || "")
      });
    }
    setBusy(true);
    try {
      await api.patch(`/campaigns/${encodeURIComponent(campaign.id)}`, payload);
      notify("Campaign configuration saved.", "success");
      changed();
      close();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Campaign update failed", "error");
    } finally {
      setBusy(false);
    }
  }

  return <Modal open={Boolean(campaign)} onClose={close} title="Edit campaign settings"
    description="Edits apply to future campaign decisions. Previously sent messages are not rewritten." wide>
    {campaign && <form key={campaign.id} className="form-stack" onSubmit={submit}>
      <Field label="Campaign name"><input name="name" defaultValue={campaign.name} maxLength={120} required /></Field>
      {campaign.kind === "email" && <>
      <div className="form-grid">
        <Field label="Daily send limit"><input name="daily_send_limit" type="number" min={1} max={500} required defaultValue={campaign.daily_send_limit} /></Field>
        <Field label="Timezone"><input name="timezone" required maxLength={80} defaultValue={campaign.timezone} /></Field>
      </div>
      <div className="form-grid">
        <Field label="Send window starts"><input name="send_window_start" type="time" required defaultValue={campaign.send_window_start} /></Field>
        <Field label="Send window ends"><input name="send_window_end" type="time" required defaultValue={campaign.send_window_end} /></Field>
      </div>
      <fieldset><legend>Sending weekdays</legend>
        <div className="toolbar">{WEEKDAYS.map((day, index) => (
          <label key={day}><input type="checkbox" name="send_weekdays" value={index} defaultChecked={campaign.send_weekdays.includes(index)} /> {day}</label>
        ))}</div>
      </fieldset>
      <div className="form-grid">
        <Field label="First follow-up (working days)"><input name="followup1_working_days" type="number" min={1} max={30} required defaultValue={campaign.followup1_working_days ?? 4} /></Field>
        <Field label="Second follow-up (working days)"><input name="followup2_working_days" type="number" min={1} max={30} required defaultValue={campaign.followup2_working_days ?? 6} /></Field>
      </div>
      <Field label="Approval rule"><select name="approval_mode" defaultValue={campaign.approval_mode}>
        <option value="each_message">Approve each message</option>
        <option value="whole_sequence">Approve whole sequence</option>
      </select></Field>
      <Field label="Experiment hypothesis"><textarea name="experiment_hypothesis" maxLength={1000} rows={2} defaultValue={campaign.experiment_hypothesis} /></Field>
      <div className="form-grid">
        <Field label="Minimum sample per variant"><input name="experiment_min_sample" type="number" min={10} max={100000} required defaultValue={campaign.experiment_min_sample} /></Field>
        <Field label="Control variant"><select name="control_variant" defaultValue={campaign.control_variant}>
          {campaign.variants.map((variant) => <option key={variant} value={variant}>{variant}</option>)}
        </select></Field>
      </div>
      <p className="muted">The campaign type and existing A/B assignments cannot be changed here. Pause the campaign before making major schedule changes.</p>
      </>}
      {campaign.kind !== "email" && <p className="muted">Only the name is editable for this campaign type. Its generation and distribution settings are managed in their own screens.</p>}
      <div className="modal-actions"><Button type="button" tone="ghost" onClick={close}>Cancel</Button><Button type="submit" busy={busy}>Save settings</Button></div>
    </form>}
  </Modal>;
}

export function CloneCampaignModal({
  campaign, close, created, notify
}: {
  campaign: Campaign | null;
  close: () => void;
  created: (id: string) => void;
  notify: (message: string, tone: "success" | "error") => void;
}) {
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => idempotencyKey("clone-campaign"));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!campaign) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const clone = await api.post<Campaign>(
        `/campaigns/${encodeURIComponent(campaign.id)}/clone`,
        { name: String(data.get("name") || "").trim() },
        key
      );
      notify("Campaign configuration copied. The new campaign is paused and empty.", "success");
      created(clone.id);
      close();
      setKey(idempotencyKey("clone-campaign"));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not copy campaign", "error");
    } finally {
      setBusy(false);
    }
  }
  return <Modal open={Boolean(campaign)} onClose={close} title="Duplicate campaign configuration"
    description="The copy starts paused with no recipients, drafts, messages, provider credentials or history.">
    {campaign && <form key={campaign.id} onSubmit={submit} className="form-stack">
      <Field label="New campaign name">
        <input name="name" required minLength={1} maxLength={120} defaultValue={`${campaign.name} copy`} onChange={() => setKey(idempotencyKey("clone-campaign"))} />
      </Field>
      <p className="muted">Daily cap, time zone, weekdays, follow-up timing, approval settings and A/B configuration are copied. Sending must be explicitly enabled later.</p>
      <div className="modal-actions"><Button type="button" tone="ghost" onClick={close}>Cancel</Button><Button type="submit" busy={busy}>Create paused copy</Button></div>
    </form>}
  </Modal>;
}
