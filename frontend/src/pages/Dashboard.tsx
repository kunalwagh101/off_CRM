import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { DashboardStats } from "../types";
import { Loadable, statusTone } from "./shared";
import VideoSection from "./VideoSection";

export default function Dashboard() {
  const { campaigns, selectCampaign } = useApp();
  const stats = useResource(() => api.get<DashboardStats>("/dashboard"), []);
  const state = <Loadable loading={stats.loading} error={stats.error} />;
  if (stats.loading || stats.error || !stats.data) return <><PageHeader title="Command centre" />{state}</>;

  return (
    <>
      <PageHeader
        eyebrow="Local-first outreach"
        title="Command centre"
        description="Review drafts, control daily volume and stop follow-ups the moment a reply arrives."
        actions={<Button onClick={() => (window.location.hash = "campaigns")}>New campaign</Button>}
      />
      <div className="stats-grid">
        <StatCard label="Active campaigns" value={stats.data.active_campaigns} detail="currently running" />
        <StatCard label="Contacts" value={stats.data.total_contacts} detail="across all campaigns" accent="violet" />
        <StatCard label="Emails sent" value={stats.data.sent} detail={`${stats.data.due_now} due now`} accent="orange" />
        <StatCard label="Reply rate" value={`${stats.data.reply_rate}%`} detail={`${stats.data.replies} replies`} accent="green" />
      </div>

      <Panel title="How your outreach flows" subtitle="Every lead moves left to right. Click any step to jump straight there." className="pipeline-panel">
        <ol className="pipeline-steps">
          {[
            { key: "discovery", label: "Discover", detail: "Find people on public pages", hash: "discovery" },
            { key: "contacts", label: "Enrich", detail: `${stats.data.total_contacts} contacts ready`, hash: "contacts" },
            { key: "campaigns", label: "Draft", detail: "AI writes, you own the words", hash: "campaigns" },
            { key: "drafts", label: "Approve", detail: `${stats.data.pending_review} waiting for you`, hash: "drafts", attention: stats.data.pending_review > 0 },
            { key: "queue", label: "Send", detail: `${stats.data.due_now} due now`, hash: "queue" },
            { key: "sales", label: "Track replies", detail: `${stats.data.replies} replies · follow-ups stop on reply`, hash: "sales" },
            { key: "video", label: "Cut video", detail: "Timeline, captions, export", hash: "videoeditor" }
          ].map((step, index) => (
            <li key={step.key}>
              <button
                type="button"
                className={step.attention ? "pipeline-step step-attention" : "pipeline-step"}
                onClick={() => (window.location.hash = step.hash)}
              >
                <span className="step-index">{index + 1}</span>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </button>
            </li>
          ))}
        </ol>
      </Panel>
      <VideoSection />
      <div className="dashboard-grid">
        <Panel title="Campaign pulse" subtitle="Most recently updated workspaces">
          {campaigns.length ? (
            <div className="campaign-list">
              {campaigns.slice(0, 5).map((campaign) => (
                <button
                  className="campaign-row"
                  key={campaign.id}
                  onClick={() => {
                    selectCampaign(campaign.id);
                    window.location.hash = "contacts";
                  }}
                >
                  <span className="campaign-mark">{campaign.name.slice(0, 2).toUpperCase()}</span>
                  <span className="campaign-main">
                    <strong>{campaign.name}</strong>
                    <small>Updated {formatDate(campaign.updated_at)}</small>
                  </span>
                  <span className="campaign-metric"><strong>{campaign.contact_count ?? 0}</strong><small>contacts</small></span>
                  <span className="campaign-metric"><strong>{campaign.sent_count ?? 0}</strong><small>sent</small></span>
                  <Badge tone={statusTone(campaign.status)}>{campaign.status}</Badge>
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">No campaigns yet. Create one to start importing contacts.</p>
          )}
        </Panel>
        <Panel title="Review queue" subtitle="Messages still waiting for a human decision">
          <div className="review-callout">
            <span className="review-number">{stats.data.pending_review}</span>
            <p>drafts need review before they can enter the send queue.</p>
            <Button tone="secondary" onClick={() => (window.location.hash = "drafts")}>Review drafts</Button>
          </div>
          <div className="principle-card">
            <strong>Safe default</strong>
            <p>Send runs write to a local outbox until Gmail is connected and explicitly confirmed.</p>
          </div>
        </Panel>
      </div>
    </>
  );
}
