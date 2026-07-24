import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { ConnectorsStatus, Paginated } from "../types";
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

type Template = {
  id: string;
  name: string;
  stage: string;
  variant_id: string;
  subject_template: string;
  body_template: string;
  version_no: number;
};

type Recommendation = {
  id: string;
  template_id: string;
  variant_id: string;
  sample_size: number;
  reply_rate: number;
  status: "pending_review" | "approved" | "rejected";
  current_template: string;
  suggested_template: string;
  egress_call_id: string;
  created_at: string;
  reviewed_at: string | null;
};

export default function Experiments() {
  const { campaignId, activeCampaign, notify } = useApp();
  const [rewriteVariant, setRewriteVariant] = useState<Variant | null>(null);
  const [busy, setBusy] = useState("");
  const report = useResource(
    () => campaignId ? api.get<{ items: Variant[]; total: number }>(`/campaigns/${campaignId}/reports/ab`) : Promise.resolve({ items: [], total: 0 }),
    [campaignId]
  );
  const templates = useResource<Paginated<Template>>(
    () => api.get("/templates?limit=200"),
    []
  );
  const connectors = useResource<ConnectorsStatus>(() => api.get("/connectors"), []);
  const recommendations = useResource<Paginated<Recommendation>>(
    () => api.get("/ai/template-recommendations?limit=100"),
    []
  );

  async function suggestRewrite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!rewriteVariant) return;
    const data = new FormData(event.currentTarget);
    const template = templates.data?.items.find(
      (item) => item.id === String(data.get("template_id"))
    );
    if (!template) {
      notify("Choose a source template", "info");
      return;
    }
    setBusy("rewrite");
    try {
      await api.post("/ai/template-recommendations", {
        template_id: template.id,
        variant_id: rewriteVariant.variant_id,
        current_template: `Subject: ${template.subject_template}\n\n${template.body_template}`,
        sample_size: rewriteVariant.initial_sent,
        reply_rate: rewriteVariant.reply_rate,
        selected_profile_id: data.get("selected_profile_id")
      });
      recommendations.reload();
      setRewriteVariant(null);
      notify("Template suggestion created and held for human review", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Template suggestion failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function reviewRecommendation(item: Recommendation, approved: boolean) {
    setBusy(`review-${item.id}`);
    try {
      await api.patch(`/ai/template-recommendations/${item.id}`, { approved });
      recommendations.reload();
      notify(
        approved
          ? "Suggestion approved as a candidate; it is not live or sending"
          : "Suggestion rejected",
        "success"
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Review could not be saved", "error");
    } finally {
      setBusy("");
    }
  }
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
              <div className="experiment-card-actions">
                <Badge tone={variant.sample_status === "ready" ? "success" : "warning"}>{variant.initial_sent}/{variant.minimum_sample} minimum sample</Badge>
                <Button
                  tone="ghost"
                  disabled={variant.initial_sent < 20}
                  onClick={() => setRewriteVariant(variant)}
                >
                  Suggest rewrite
                </Button>
              </div>
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

      <Panel
        title="Template improvement queue"
        subtitle="Uses template text plus numeric reply rate only; reply bodies never leave OFF_CRM"
        className="experiment-recommendations"
      >
        {recommendations.loading || recommendations.error ? (
          <Loadable loading={recommendations.loading} error={recommendations.error} />
        ) : recommendations.data?.items.length ? (
          <div className="recommendation-list">
            {recommendations.data.items.map((item) => (
              <article key={item.id}>
                <header>
                  <span>
                    <strong>Variant {item.variant_id}</strong>
                    <small>{item.sample_size} sends · {item.reply_rate}% replies · {new Date(item.created_at).toLocaleDateString()}</small>
                  </span>
                  <Badge tone={item.status === "approved" ? "success" : item.status === "rejected" ? "danger" : "warning"}>
                    {item.status.replaceAll("_", " ")}
                  </Badge>
                </header>
                <div className="recommendation-compare">
                  <section><strong>Current</strong><pre>{item.current_template}</pre></section>
                  <section><strong>Suggested</strong><pre>{item.suggested_template}</pre></section>
                </div>
                {item.status === "pending_review" ? (
                  <footer>
                    <Button tone="ghost" busy={busy === `review-${item.id}`} onClick={() => void reviewRecommendation(item, false)}>Reject</Button>
                    <Button busy={busy === `review-${item.id}`} onClick={() => void reviewRecommendation(item, true)}>Approve candidate</Button>
                  </footer>
                ) : item.status === "approved" ? (
                  <p className="form-note">Approved for template-library review. It is not automatically live and cannot send until the normal campaign approval flow uses it.</p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="connection-empty">
            <strong>No template suggestions yet</strong>
            <p>Once a variant has at least 20 first-touch sends, request a rewrite from its card. The model sees only the template and the numeric rate.</p>
          </div>
        )}
      </Panel>

      <Modal
        open={Boolean(rewriteVariant)}
        onClose={() => setRewriteVariant(null)}
        title={`Suggest a rewrite for variant ${rewriteVariant?.variant_id || ""}`}
        description="This creates a review candidate only. It does not edit a live template or approve any email."
        wide
      >
        {rewriteVariant ? (
          <form className="form-stack" onSubmit={suggestRewrite}>
            <div className="review-meta">
              <div><span>Sample</span><strong>{rewriteVariant.initial_sent} sends</strong></div>
              <div><span>Replies</span><strong>{rewriteVariant.replies}</strong></div>
              <div><span>Rate</span><strong>{rewriteVariant.reply_rate}%</strong></div>
              <div><span>Mailbox content</span><strong>Not included</strong></div>
            </div>
            <Field label="Source template">
              <select name="template_id" required>
                <option value="">Choose template</option>
                {templates.data?.items
                  .filter((template) => template.variant_id === rewriteVariant.variant_id)
                  .map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} · {template.stage} · v{template.version_no}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Eligible Tier A model">
              <select name="selected_profile_id" required>
                <option value="">Choose model</option>
                {connectors.data?.ai_providers
                  .filter(
                    (profile) =>
                      (profile.effective_trust_tier || profile.trust_tier) === "A" &&
                      profile.allowed_task_types.includes("template_rewrite")
                  )
                  .map((profile) => (
                    <option key={profile.id} value={profile.id}>{profile.name} · {profile.model}</option>
                  ))}
              </select>
            </Field>
            <div className="form-note">
              <strong>Exact model input</strong>
              <span>Selected template text, sample size {rewriteVariant.initial_sent}, and reply rate {rewriteVariant.reply_rate}%. No contact list, addresses, replies, CRM notes, or campaign values.</span>
            </div>
            <div className="modal-actions">
              <Button type="button" tone="ghost" onClick={() => setRewriteVariant(null)}>Cancel</Button>
              <Button
                type="submit"
                busy={busy === "rewrite"}
                disabled={
                  !connectors.data?.ai_providers.some(
                    (profile) =>
                      (profile.effective_trust_tier || profile.trust_tier) === "A" &&
                      profile.allowed_task_types.includes("template_rewrite")
                  )
                }
              >
                Create review candidate
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </>
  );
}
