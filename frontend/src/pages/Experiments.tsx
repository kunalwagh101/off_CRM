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
};

export default function Experiments() {
  const { campaignId, activeCampaign } = useApp();
  const report = useResource(
    () => campaignId ? api.get<{ items: Variant[]; total: number }>(`/campaigns/${campaignId}/reports/ab`) : Promise.resolve({ items: [], total: 0 }),
    [campaignId]
  );
  if (!campaignId) return <><PageHeader title="Experiments" /><NoCampaign /></>;
  const state = <Loadable loading={report.loading} error={report.error} />;
  const enoughData = (report.data?.items.reduce((sum, item) => sum + item.initial_sent, 0) ?? 0) >= 40;
  const leading = [...(report.data?.items ?? [])].sort((a, b) => b.reply_rate - a.reply_rate)[0];

  return (
    <>
      <PageHeader eyebrow={activeCampaign?.name} title="A/B experiments" description="Stable assignment and reply-rate reporting without pretending small samples are conclusive." />
      {report.loading || report.error ? state : report.data?.items.length ? (
        <div className="experiment-grid">
          {report.data.items.map((variant) => (
            <Panel key={variant.variant_id} className="variant-panel">
              <div className="variant-title"><span>Variant</span><strong>{variant.variant_id}</strong>{enoughData && leading?.variant_id === variant.variant_id ? <Badge tone="success">Leading</Badge> : null}</div>
              <div className="rate-ring" style={{ "--rate": `${Math.min(100, variant.reply_rate)}%` } as React.CSSProperties}><div><strong>{variant.reply_rate}%</strong><span>reply rate</span></div></div>
              <div className="mini-stats horizontal"><span><strong>{variant.contacts}</strong>assigned</span><span><strong>{variant.initial_sent}</strong>sent</span><span><strong>{variant.replies}</strong>replies</span></div>
            </Panel>
          ))}
          <Panel title="How to read this" className="experiment-guidance">
            {enoughData ? <><strong>Directional signal available</strong><p>{leading ? `Variant ${leading.variant_id} currently has the higher observed reply rate.` : "No leader yet."} Keep the audience and send timing comparable before changing the template.</p></> : <><strong>Too early to call</strong><p>Wait for at least 40 first-touch sends across variants. This threshold is only a guardrail, not a statistical significance claim.</p></>}
            <ul><li>Assignment is deterministic per contact.</li><li>A reply counts once at the contact level.</li><li>Only first-touch sends are the denominator.</li></ul>
          </Panel>
        </div>
      ) : (
        <StatePanel title="No experiment data" description="Import contacts and send first-touch variants A and B to begin the report." />
      )}
    </>
  );
}
