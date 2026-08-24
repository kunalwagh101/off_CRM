import { Button, StatePanel } from "../components";
import { useApp } from "../context";

export function NoCampaign() {
  const { campaigns, selectCampaign } = useApp();
  if (campaigns.length) {
    return (
      <StatePanel
        title="Choose a campaign"
        description="Select a campaign from the top bar to open this workspace."
        action={<Button onClick={() => selectCampaign(campaigns[0].id)}>Open {campaigns[0].name}</Button>}
      />
    );
  }
  return (
    <StatePanel
      title="Create your first campaign"
      description="A campaign holds contacts, three-stage sequences, approvals and A/B results."
      action={<Button onClick={() => (window.location.hash = "campaigns")}>Go to campaigns</Button>}
    />
  );
}

export function Loadable({ loading, error }: { loading: boolean; error: string }) {
  if (loading) return <StatePanel tone="loading" title="Loading" description="Reading the local workspace." />;
  if (error) return <StatePanel tone="error" title="Could not load this view" description={error} />;
  return null;
}

export function statusTone(status: string): string {
  if (["active", "approved", "sent", "accepted", "delivered", "replied", "completed"].includes(status)) return "success";
  if (["pending", "drafted", "queued", "retry_wait", "deferred", "waiting_followup", "new"].includes(status)) return "warning";
  if (["blocked", "failed", "delivery_unknown", "send_failed_review", "stopped", "cancelled_reply", "cancelled_policy"].includes(status)) return "danger";
  return "neutral";
}
