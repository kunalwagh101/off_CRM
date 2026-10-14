import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable, NoCampaign } from "./shared";

export type ReadinessCheck = {
  id: string;
  passed: boolean;
  message: string;
  screen: string;
};
export type ReadinessReport = {
  campaign_id: string;
  kind: string;
  eligible_for_local_review: boolean;
  checks: ReadinessCheck[];
  candidate_count: number;
  remaining_today: number | null;
  needs_approval?: number;
  sent_today?: number;
  external_delivery_verified: boolean;
  limitations?: string;
};

export default function LaunchReadiness() {
  const { campaignId, activeCampaign } = useApp();
  const report = useResource(
    () => campaignId
      ? api.get<ReadinessReport>(`/campaigns/${encodeURIComponent(campaignId)}/launch-readiness`)
      : Promise.resolve(null),
    [campaignId]
  );
  if (!campaignId) return <><PageHeader title="Launch readiness" /><NoCampaign /></>;
  const state = <Loadable loading={report.loading} error={report.error} />;
  const data = report.data;
  return <>
    <PageHeader eyebrow={activeCampaign?.name} title="Launch readiness"
      description="A read-only check of the saved CRM state. Nothing is sent, generated or approved here."
      actions={<Button onClick={report.reload} tone="secondary">Recheck</Button>} />
    {report.loading || report.error ? state : data ? <>
      <Panel title="Current review state">
        <Badge tone={data.eligible_for_local_review ? "success" : "warning"}>
          {data.eligible_for_local_review ? "Candidate ready for local review" : "Preparation needed"}
        </Badge>
        <div className="stats-grid compact-stats">
          <StatCard label="Approved and due" value={data.candidate_count} />
          <StatCard label="Needs approval" value={data.needs_approval ?? 0} />
          <StatCard label="Remaining daily allowance" value={data.remaining_today ?? "N/A"} />
        </div>
        <p className="muted" role="note">{data.limitations ??
          "This review does not verify external delivery credentials, provider availability or recipient consent."}</p>
      </Panel>
      <Panel title="Checks and next actions" subtitle="Every check comes from the selected campaign's stored state">
        {data.checks.map((check) => (
          <div className="toolbar" key={check.id}>
            <Badge tone={check.passed ? "success" : "warning"}>{check.passed ? "Passed" : "Needs action"}</Badge>
            <span>{check.message}</span>
            {!check.passed && <Button tone="ghost" onClick={() => { window.location.hash = check.screen; }}>
              Open {check.screen.replaceAll("_", " ")}
            </Button>}
          </div>
        ))}
      </Panel>
    </> : <StatePanel title="Readiness unavailable" description="No readiness data was returned." />}
  </>;
}
