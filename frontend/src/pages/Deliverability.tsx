import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type {
  EmailCampaignSettings,
  EmailHealth,
  EmailIdentity,
  EmailJob,
  EmailPreflight,
  EmailSuppression,
  Paginated
} from "../types";
import { Loadable, NoCampaign, statusTone } from "./shared";

const streamLabel: Record<string, string> = {
  permission_marketing: "Permission marketing",
  targeted_outreach: "Targeted outreach",
  transactional: "Transactional"
};

function authTone(value: string): string {
  return value === "pass" ? "success" : value === "fail" ? "danger" : "warning";
}

export default function Deliverability() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [busy, setBusy] = useState("");
  const [identityOpen, setIdentityOpen] = useState(false);
  const [liveOpen, setLiveOpen] = useState(false);

  const identities = useResource(
    () => api.get<Paginated<EmailIdentity>>("/email-delivery/identities"),
    []
  );
  const settings = useResource(
    () => campaignId
      ? api.get<EmailCampaignSettings>(`/campaigns/${campaignId}/email-settings`)
      : Promise.resolve(null as never),
    [campaignId]
  );
  const preflight = useResource(
    () => campaignId
      ? api.get<EmailPreflight>(`/campaigns/${campaignId}/email-preflight`)
      : Promise.resolve(null as never),
    [campaignId]
  );
  const health = useResource(
    () => campaignId
      ? api.get<EmailHealth>(`/campaigns/${campaignId}/email-health`)
      : Promise.resolve(null as never),
    [campaignId]
  );
  const jobs = useResource(
    () => campaignId
      ? api.get<Paginated<EmailJob>>(`/email-delivery/jobs?campaign_id=${campaignId}&limit=100`)
      : Promise.resolve({ items: [], total: 0 }),
    [campaignId]
  );
  const suppressions = useResource(
    () => api.get<Paginated<EmailSuppression>>("/email-delivery/suppressions?limit=100"),
    []
  );

  if (!campaignId) return <><PageHeader title="Email deliverability" /><NoCampaign /></>;
  if (activeCampaign && activeCampaign.kind !== "email") {
    return <><PageHeader title="Email deliverability" /><StatePanel title="This is not an email campaign" description="Deliverability controls are isolated from image, video and distribution campaigns." /></>;
  }

  function reloadAll() {
    settings.reload();
    preflight.reload();
    health.reload();
    jobs.reload();
    identities.reload();
    suppressions.reload();
    refreshCampaigns();
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("settings");
    try {
      await api.patch(`/campaigns/${campaignId}/email-settings`, {
        stream: String(data.get("stream")),
        provider_type: String(data.get("provider_type")),
        identity_id: String(data.get("identity_id") || "") || null,
        daily_limit: Number(data.get("daily_limit")),
        frequency_cap_days: Number(data.get("frequency_cap_days")),
        frequency_cap_max: Number(data.get("frequency_cap_max")),
        require_unsubscribe: data.get("require_unsubscribe") === "on",
        auto_pause_enabled: data.get("auto_pause_enabled") === "on",
        health_sample_size: Number(data.get("health_sample_size")),
        max_hard_bounce_rate: Number(data.get("max_hard_bounce_rate")) / 100,
        max_complaint_rate: Number(data.get("max_complaint_rate")) / 100
      });
      notify("Email delivery rules saved", "success");
      reloadAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save delivery rules", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("identity");
    try {
      await api.post("/email-delivery/identities", {
        name: String(data.get("name")),
        provider_type: String(data.get("provider_type")),
        stream: String(data.get("stream")),
        from_email: String(data.get("from_email")),
        reply_to: String(data.get("reply_to") || ""),
        ses_identity: String(data.get("ses_identity") || ""),
        aws_region: String(data.get("aws_region") || ""),
        configuration_set: String(data.get("configuration_set") || ""),
        mail_from_domain: String(data.get("mail_from_domain") || ""),
        sns_topic_arn: String(data.get("sns_topic_arn") || ""),
        max_per_second: Number(data.get("max_per_second") || 1),
        max_batch_size: Number(data.get("max_batch_size") || 25),
        status: "active"
      });
      notify("Sending identity saved. Run its authentication check before live use.", "success");
      setIdentityOpen(false);
      identities.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save identity", "error");
    } finally {
      setBusy("");
    }
  }

  async function checkIdentity(id: string) {
    setBusy(`check-${id}`);
    try {
      await api.post(`/email-delivery/identities/${id}/check`, {});
      notify("Authentication check finished", "success");
      identities.reload();
      preflight.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Identity check failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function enqueue(confirmation = "") {
    setBusy("enqueue");
    try {
      const result = await api.post<{ queued_count: number; blocked_count: number }>(
        `/campaigns/${campaignId}/email-jobs`,
        { max_jobs: 5000, confirmation }
      );
      notify(`${result.queued_count} jobs queued; ${result.blocked_count} blocked by preflight.`, result.blocked_count ? "warning" : "success");
      setLiveOpen(false);
      reloadAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not queue email jobs", "error");
    } finally {
      setBusy("");
    }
  }

  function queueClicked() {
    if (settings.data?.provider_type === "gmail") {
      notify("Gmail is for small outreach. Use Send queue for the confirmed Gmail action.", "info");
      window.location.hash = "queue";
    } else if (settings.data?.provider_type === "local") void enqueue();
    else setLiveOpen(true);
  }

  async function runWorker() {
    setBusy("worker");
    try {
      const result = await api.post<{ processed: number; accepted: number; failed: number }>(
        "/email-delivery/work",
        { max_jobs: 25 }
      );
      notify(`${result.processed} jobs processed; ${result.accepted} accepted; ${result.failed} need attention.`, result.failed ? "warning" : "success");
      reloadAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Worker cycle failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function resumeHealth() {
    setBusy("resume");
    try {
      await api.post(`/campaigns/${campaignId}/email-health/resume`, {});
      notify("Deliverability pause cleared; sending is active again", "success");
      reloadAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not resume sending", "error");
    } finally {
      setBusy("");
    }
  }

  async function cancelJob(id: string) {
    setBusy(`cancel-${id}`);
    try {
      await api.post(`/email-delivery/jobs/${id}/cancel`, {});
      notify("Queued email cancelled", "success");
      jobs.reload();
      preflight.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not cancel email", "error");
    } finally {
      setBusy("");
    }
  }

  async function addPermission(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email"));
    setBusy("permission");
    try {
      await api.patch(`/email-delivery/permissions/${encodeURIComponent(email)}`, {
        status: "granted",
        basis: String(data.get("basis")),
        source: String(data.get("source")),
        evidence: String(data.get("evidence") || "")
      });
      notify("Permission evidence recorded", "success");
      preflight.reload();
      event.currentTarget.reset();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not record permission", "error");
    } finally {
      setBusy("");
    }
  }

  async function addSuppression(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("suppression");
    try {
      await api.post("/email-delivery/suppressions", {
        email: String(data.get("email")),
        reason: String(data.get("reason")),
        source: "operator"
      });
      notify("Address globally suppressed and queued jobs cancelled", "success");
      event.currentTarget.reset();
      suppressions.reload();
      preflight.reload();
      jobs.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not suppress address", "error");
    } finally {
      setBusy("");
    }
  }

  const blockers = Object.entries(preflight.data?.blocker_counts ?? {});
  const settingsState = <Loadable loading={settings.loading} error={settings.error} />;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Email deliverability"
        description="Permission, authentication, suppression, durable queueing and provider feedback. These controls improve delivery; they cannot guarantee inbox placement."
        actions={<><Button tone="secondary" busy={busy === "worker"} onClick={runWorker}>Process 25 jobs</Button><Button busy={busy === "enqueue"} onClick={queueClicked}>Queue eligible email</Button></>}
      />

      <div className="stats-grid compact-stats">
        <StatCard label="Preflight ready" value={preflight.data?.allowed ?? 0} detail={`${preflight.data?.blocked ?? 0} blocked`} accent="green" />
        <StatCard label="Accepted" value={health.data?.accepted ?? 0} detail={`${health.data?.delivered ?? 0} delivered`} />
        <StatCard label="Hard bounce" value={`${((health.data?.hard_bounce_rate ?? 0) * 100).toFixed(2)}%`} detail={`${health.data?.hard_bounces ?? 0} addresses`} accent="orange" />
        <StatCard label="Complaints" value={`${((health.data?.complaint_rate ?? 0) * 100).toFixed(3)}%`} detail={health.data?.status.replaceAll("_", " ") ?? "No sample"} accent="violet" />
      </div>

      {health.data?.paused_reason ? <div className="danger-note" role="alert"><strong>Sending auto-paused</strong><p>{health.data.paused_reason}</p><Button tone="danger" busy={busy === "resume"} onClick={resumeHealth}>Resume after review</Button></div> : null}

      <div className="settings-grid">
        <Panel title="Campaign delivery rules" subtitle="Every email campaign has one isolated traffic lane.">
          {settings.loading || settings.error || !settings.data ? settingsState : (
            <form className="form-stack" onSubmit={saveSettings} key={`${campaignId}-${settings.data.updated_at ?? "settings"}`}>
              <div className="form-grid">
                <Field label="Email stream"><select name="stream" defaultValue={settings.data.stream}><option value="targeted_outreach">Targeted outreach</option><option value="permission_marketing">Permission marketing</option><option value="transactional">Transactional</option></select></Field>
                <Field label="Provider"><select name="provider_type" defaultValue={settings.data.provider_type}><option value="local">Local test outbox</option><option value="gmail">Gmail · small outreach</option><option value="ses">Amazon SES · bulk</option></select></Field>
                <Field label="Sending identity"><select name="identity_id" defaultValue={settings.data.identity_id ?? ""}><option value="">No identity</option>{(identities.data?.items ?? []).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.from_email}</option>)}</select></Field>
                <Field label="Daily bulk cap"><input name="daily_limit" type="number" min={1} max={100000} defaultValue={settings.data.daily_limit} /></Field>
                <Field label="Contact cap window (days)"><input name="frequency_cap_days" type="number" min={1} max={365} defaultValue={settings.data.frequency_cap_days} /></Field>
                <Field label="Max emails per contact"><input name="frequency_cap_max" type="number" min={1} max={100} defaultValue={settings.data.frequency_cap_max} /></Field>
                <Field label="Health sample"><input name="health_sample_size" type="number" min={1} max={1000000} defaultValue={settings.data.health_sample_size} /></Field>
                <Field label="Hard-bounce stop (%)"><input name="max_hard_bounce_rate" type="number" min={0} max={100} step="0.01" defaultValue={settings.data.max_hard_bounce_rate * 100} /></Field>
                <Field label="Complaint stop (%)"><input name="max_complaint_rate" type="number" min={0} max={100} step="0.001" defaultValue={settings.data.max_complaint_rate * 100} /></Field>
              </div>
              <label className="check-line"><input name="require_unsubscribe" type="checkbox" defaultChecked={settings.data.require_unsubscribe} />Require unsubscribe for non-transactional mail</label>
              <label className="check-line"><input name="auto_pause_enabled" type="checkbox" defaultChecked={settings.data.auto_pause_enabled} />Auto-pause when health thresholds are breached</label>
              <Button type="submit" busy={busy === "settings"}>Save rules</Button>
            </form>
          )}
        </Panel>

        <Panel title="Preflight" subtitle="The same checks run again immediately before provider delivery.">
          {preflight.loading || preflight.error ? <Loadable loading={preflight.loading} error={preflight.error} /> : blockers.length ? (
            <div className="definition-list">{blockers.map(([code, count]) => <div key={code}><dt>{code.replaceAll("_", " ")}</dt><dd><Badge tone="danger">{count} blocked</Badge></dd></div>)}</div>
          ) : <StatePanel title="No policy blockers" description={preflight.data?.evaluated ? "All currently due, approved drafts passed preflight." : "Approve due drafts to evaluate them here."} />}
        </Panel>
      </div>

      <Panel title="Sending identities" subtitle="Use a separate identity for each stream; live SES needs verified DKIM, SPF, DMARC and alignment." action={<Button tone="secondary" onClick={() => setIdentityOpen((value) => !value)}>{identityOpen ? "Close" : "Add identity"}</Button>}>
        {identityOpen ? <form className="form-stack provider-form" onSubmit={saveIdentity}>
          <div className="form-grid">
            <Field label="Identity name"><input name="name" required maxLength={120} /></Field>
            <Field label="From email"><input name="from_email" type="email" required /></Field>
            <Field label="Provider"><select name="provider_type" defaultValue="ses"><option value="ses">Amazon SES</option><option value="gmail">Gmail</option><option value="local">Local test</option></select></Field>
            <Field label="Traffic stream"><select name="stream" defaultValue="permission_marketing"><option value="permission_marketing">Permission marketing</option><option value="targeted_outreach">Targeted outreach</option><option value="transactional">Transactional</option></select></Field>
            <Field label="Reply-To"><input name="reply_to" type="email" /></Field>
            <Field label="SES identity"><input name="ses_identity" placeholder="example.com" /></Field>
            <Field label="AWS region"><input name="aws_region" defaultValue="us-east-1" /></Field>
            <Field label="Configuration set"><input name="configuration_set" /></Field>
            <Field label="Custom MAIL FROM"><input name="mail_from_domain" placeholder="mail.example.com" /></Field>
            <Field label="SNS topic ARN"><input name="sns_topic_arn" /></Field>
            <Field label="Messages per second"><input name="max_per_second" type="number" min="0.1" step="0.1" defaultValue="1" /></Field>
            <Field label="Worker batch"><input name="max_batch_size" type="number" min="1" max="500" defaultValue="25" /></Field>
          </div>
          <Button type="submit" busy={busy === "identity"}>Save identity</Button>
        </form> : null}
        {identities.loading || identities.error ? <Loadable loading={identities.loading} error={identities.error} /> : identities.data?.items.length ? <div className="table-wrap"><table><thead><tr><th>Identity</th><th>Lane</th><th>Provider</th><th>SPF</th><th>DKIM</th><th>DMARC</th><th>Alignment</th><th>Action</th></tr></thead><tbody>{identities.data.items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.from_email}</small></td><td>{streamLabel[item.stream]}</td><td><Badge>{item.provider_type.toUpperCase()}</Badge></td><td><Badge tone={authTone(item.spf_status)}>{item.spf_status}</Badge></td><td><Badge tone={authTone(item.dkim_status)}>{item.dkim_status}</Badge></td><td><Badge tone={authTone(item.dmarc_status)}>{item.dmarc_status}</Badge></td><td><Badge tone={authTone(item.alignment_status)}>{item.alignment_status}</Badge></td><td><Button tone="ghost" busy={busy === `check-${item.id}`} onClick={() => checkIdentity(item.id)}>Check now</Button></td></tr>)}</tbody></table></div> : <StatePanel title="No sending identity" description="Local testing works without one. Add a verified SES identity before live bulk delivery." />}
      </Panel>

      <div className="settings-grid">
        <Panel title="Record permission" subtitle="Imported or scraped addresses stay unknown until evidence is recorded.">
          <form className="form-stack" onSubmit={addPermission}>
            <Field label="Email"><input name="email" type="email" required /></Field>
            <Field label="Basis"><select name="basis" required><option value="explicit_consent">Explicit consent</option><option value="existing_customer">Existing customer</option><option value="service_request">Service request</option><option value="contract">Contract</option></select></Field>
            <Field label="Source"><input name="source" required placeholder="Signup form, contract, support request" /></Field>
            <Field label="Evidence reference"><input name="evidence" placeholder="Record ID or internal note" /></Field>
            <Button type="submit" busy={busy === "permission"}>Record grant</Button>
          </form>
        </Panel>
        <Panel title="Global suppression" subtitle="A suppression cancels every queued job for the address.">
          <form className="form-stack" onSubmit={addSuppression}>
            <Field label="Email"><input name="email" type="email" required /></Field>
            <Field label="Reason"><input name="reason" required placeholder="Unsubscribe, complaint, operator request" /></Field>
            <Button type="submit" tone="danger" busy={busy === "suppression"}>Suppress everywhere</Button>
          </form>
          {(suppressions.data?.items ?? []).slice(0, 5).map((item) => <div className="connector-row" key={item.email}><div className="provider-row-info"><strong>{item.email}</strong><small>{item.reason} · {item.source}</small></div><Badge tone="danger">suppressed</Badge></div>)}
        </Panel>
      </div>

      <Panel title="Durable delivery jobs" subtitle="Ambiguous provider results are quarantined; they are never retried automatically.">
        {jobs.loading || jobs.error ? <Loadable loading={jobs.loading} error={jobs.error} /> : jobs.data?.items.length ? <div className="table-wrap"><table><thead><tr><th>Recipient</th><th>Lane</th><th>Status</th><th>Attempts</th><th>Created</th><th>Detail</th></tr></thead><tbody>{jobs.data.items.map((job) => <tr key={job.id}><td><strong>{job.full_name}</strong><small>{job.to_email} · {job.company}</small></td><td>{streamLabel[job.stream] ?? job.stream}<small>{job.provider_type.toUpperCase()}</small></td><td><Badge tone={statusTone(job.status)}>{job.status.replaceAll("_", " ")}</Badge></td><td>{job.attempt_count}</td><td>{formatDate(job.created_at)}</td><td><small>{job.last_error || "—"}</small>{["queued", "retry_wait"].includes(job.status) ? <Button tone="ghost" busy={busy === `cancel-${job.id}`} onClick={() => cancelJob(job.id)}>Cancel</Button> : null}</td></tr>)}</tbody></table></div> : <StatePanel title="No durable jobs yet" description="Run preflight, then queue eligible approved drafts." />}
      </Panel>

      <Modal open={liveOpen} onClose={() => setLiveOpen(false)} title="Queue live email" description="The worker can contact real recipients after this confirmation.">
        <form className="form-stack" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void enqueue(String(data.get("confirmation") || "")); }}>
          <div className="danger-note"><strong>Live external action</strong><p>Only preflight-approved jobs are queued. Inbox placement is never guaranteed.</p></div>
          <Field label="Type QUEUE LIVE EMAILS to continue"><input name="confirmation" required pattern="QUEUE LIVE EMAILS" autoComplete="off" /></Field>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setLiveOpen(false)}>Cancel</Button><Button type="submit" tone="danger" busy={busy === "enqueue"}>Queue live jobs</Button></div>
        </form>
      </Modal>
    </div>
  );
}
