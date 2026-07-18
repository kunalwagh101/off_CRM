import { api } from "../api";
import { Badge, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable, NoCampaign } from "./shared";

type Variant = {
  variant_id: string;
  contacts: number;
  initial_sent: number;
  replies: number;
  reply_rate: number;
  ci_low: number;
  ci_high: number;
  lift_percentage_points: number;
  relative_lift: number | null;
  control_variant: string;
  minimum_sample: number;
  sample_status: "collecting" | "ready";
  hypothesis: string;
  primary_metric: string;
};

export default function Experiments() {
  const { campaignId, activeCampaign } = useApp();
  const report = useResource(
    () => campaignId ? api.get<{ items: Variant[]; total: number }>(`/campaigns/${campaignId}/reports/ab`) : Promise.resolve({ items: [], total: 0 }),
    [campaignId]
  );
  if (!campaignId) return <><PageHeader title="Experiments" /><NoCampaign /></>;
  const state = <Loadable loading={report.loading} error={report.error} />;
  const enoughData = Boolean(report.data?.items.length && report.data.items.every((item) => item.sample_status === "ready"));
  const leading = [...(report.data?.items ?? [])].sort((a, b) => b.reply_rate - a.reply_rate)[0];

  return (
    <>
      <PageHeader eyebrow={activeCampaign?.name} title="A/B experiments" description={activeCampaign?.experiment_hypothesis || "Stable assignment, exposure tracking and uncertainty-aware reply-rate reporting."} />
      {report.loading || report.error ? state : report.data?.items.length ? (
        <div className="experiment-grid">
          {report.data.items.map((variant) => (
            <Panel key={variant.variant_id} className="variant-panel">
              <div className="variant-title"><span>Variant</span><strong>{variant.variant_id}</strong>{enoughData && leading?.variant_id === variant.variant_id ? <Badge tone="success">Leading</Badge> : null}</div>
              <div className="rate-ring" style={{ "--rate": `${Math.min(100, variant.reply_rate)}%` } as React.CSSProperties}><div><strong>{variant.reply_rate}%</strong><span>reply rate</span></div></div>
              <div className="mini-stats horizontal"><span><strong>{variant.contacts}</strong>assigned</span><span><strong>{variant.initial_sent}</strong>sent</span><span><strong>{variant.replies}</strong>replies</span></div>
              <p className="muted-copy">95% interval {variant.ci_low}%–{variant.ci_high}% · {variant.variant_id === variant.control_variant ? "Control" : `${variant.lift_percentage_points > 0 ? "+" : ""}${variant.lift_percentage_points} pp vs control`}</p>
              <Badge tone={variant.sample_status === "ready" ? "success" : "warning"}>{variant.initial_sent}/{variant.minimum_sample} minimum sample</Badge>
            </Panel>
          ))}
          <Panel title="How to read this" className="experiment-guidance">
            {enoughData ? <><strong>Directional signal available</strong><p>{leading ? `Variant ${leading.variant_id} currently has the higher observed reply rate.` : "No leader yet."} Check interval overlap and keep audience and timing comparable before promoting a winner.</p></> : <><strong>Still collecting</strong><p>Each variant must reach its configured minimum. The 95% interval shows uncertainty; the minimum is not itself a significance claim.</p></>}
            <ul><li>Assignment is deterministic per contact.</li><li>Variant A is the default control.</li><li>A reply counts once at contact level.</li><li>Only first-touch sends are the denominator.</li></ul>
          </Panel>
        </div>
      ) : (
        <StatePanel title="No experiment data" description="Import contacts and send first-touch variants A and B to begin the report." />
      )}
    </>
  );
}
