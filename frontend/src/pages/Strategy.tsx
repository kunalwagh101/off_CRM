import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { GtmApplyResult, GtmDescribe, GtmNextStep, GtmPlan, GtmProduct, GtmReview } from "../types";
import { Loadable } from "./shared";

type GoalForm = {
  product_id: string;
  goal_kind: string;
  goal_target: string;
  horizon_days: string;
  contact_budget: string;
  channels: string[];
  assumed_reply_percent: string;
  per_identity_daily_cap: string;
  notes: string;
  use_model: boolean;
};

const statusTone: Record<string, string> = {
  draft: "warning",
  applied: "success",
  superseded: "neutral",
  discarded: "neutral"
};

const sourceLabel: Record<string, string> = {
  apollo_search: "Apollo search",
  public_discovery: "Public web discovery",
  existing_contacts: "Contacts you already have"
};

/** One plan, read back exactly as it was stored — every correction included. */
export function PlanView({ plan, actions }: { plan: GtmPlan; actions?: ReactNode }) {
  const { summary, audience, channels } = plan.plan;
  const feasible = plan.feasibility.feasible;
  return (
    <div className="form-stack">
      <div className="modal-actions">
        <Badge tone={statusTone[plan.status]}>{plan.status}</Badge>
        <Badge tone="neutral">version {plan.version}</Badge>
        <span className="muted-copy">
          {plan.source === "model"
            ? `Written by ${plan.model_id || "a model"} on ${plan.provider_id || "a provider"} at the ${plan.policy || "unknown"} data policy`
            : "Rules-based plan"}
          {" · "}
          {formatDate(plan.created_at)}
        </span>
      </div>
      {plan.product_stale ? (
        <p className="danger-note">
          {plan.product_deleted
            ? "The product this plan was written for has been deleted. The plan keeps its own copy."
            : `The product has changed since this plan was written against version ${plan.product_version}. Draft a new plan to use the current product.`}
        </p>
      ) : null}
      {summary ? <p>{summary}</p> : <p className="muted-copy">No summary survived the checks — the notes below say why.</p>}

      <div className="definition-list">
        <div><dt>Goal</dt><dd>{plan.request.goal_target} {plan.request.goal_kind} in {plan.request.horizon_days} days</dd></div>
        <div><dt>Audience</dt><dd>{audience.description || "—"}</dd></div>
        <div><dt>Found through</dt><dd>{sourceLabel[audience.source] ?? audience.source}</dd></div>
        {audience.titles.length ? <div><dt>Titles</dt><dd>{audience.titles.join(", ")}</dd></div> : null}
        {audience.industries.length ? <div><dt>Industries</dt><dd>{audience.industries.join(", ")}</dd></div> : null}
        {audience.company_sizes.length ? <div><dt>Company size</dt><dd>{audience.company_sizes.join(", ")}</dd></div> : null}
        {audience.regions.length ? <div><dt>Regions</dt><dd>{audience.regions.join(", ")}</dd></div> : null}
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>Channel</th><th>Angle and hypothesis</th><th>How much</th></tr></thead>
          <tbody>
            {channels.map((item) => (
              <tr key={item.kind}>
                <td><strong>{item.kind}</strong><small>{item.role}</small></td>
                <td>
                  {item.angle || <span className="muted-copy">No angle survived the checks.</span>}
                  <small>{item.hypothesis}</small>
                </td>
                <td>
                  {item.kind === "email" ? (
                    <>
                      {item.daily_volume} a day
                      <small>{item.send_window?.join("–")} · {item.weekdays} · {item.timezone || "campaign timezone"} · {item.stream?.replaceAll("_", " ")}</small>
                    </>
                  ) : item.kind === "distribution" ? (
                    <>
                      {item.daily_volume} post(s) a day
                      <small>{item.platforms?.join(", ") || "no platform connected"}</small>
                    </>
                  ) : (
                    <>{item.recipe_family ? `${item.recipe_family} videos` : "pictures for the posts"}</>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className={feasible === false ? "danger-note" : "muted-copy"}>
        <Badge tone={feasible === null ? "neutral" : feasible ? "success" : "danger"}>
          {feasible === null ? "no estimate yet" : feasible ? "reachable" : "short of the goal"}
        </Badge>{" "}
        {plan.feasibility.explanation}
      </p>

      {plan.notes.length ? (
        <div className="memory-list">
          {plan.notes.map((note, index) => (
            <div key={index}><p><small>How this plan was made</small><span>{note}</span></p></div>
          ))}
        </div>
      ) : null}
      {actions ? <div className="modal-actions">{actions}</div> : null}
    </div>
  );
}

/** A finding that stops the walk before the copy is judged. */
const blocking = new Set(["delivery_unhealthy", "not_started", "no_contacts", "no_account", "no_campaign", "nothing_published"]);

function findingTone(code: string): string {
  if (blocking.has(code)) return "danger";
  if (["on_track", "ahead_of_target", "supporting"].includes(code)) return "success";
  if (code === "behind_target") return "warning";
  return "neutral";
}

/**
 * One review: what was wrong on each channel, then what to do about it.
 *
 * The findings come first and are never a model's words — they are arithmetic
 * over what was measured. A remedy with no screen belongs in the next version
 * of the plan, so it gets no "Open" link that would lead nowhere.
 */
export function ReviewView({ review }: { review: GtmReview }) {
  return (
    <div className="form-stack">
      <p className="muted-copy">
        {review.source === "model"
          ? `Remedies chosen by ${review.model_id || "a model"} on ${review.provider_id || "a provider"}`
          : "Rules-based remedies"}
        {" · reviewed "}
        {formatDate(review.created_at)}
      </p>
      {review.summary ? <p>{review.summary}</p> : null}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Channel</th><th>What is wrong</th></tr></thead>
          <tbody>
            {review.findings.map((finding) => (
              <tr key={finding.channel}>
                <td><strong>{finding.channel}</strong><small><Badge tone={findingTone(finding.code)}>{finding.code.replaceAll("_", " ")}</Badge></small></td>
                <td>{finding.sentence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {review.remedies.length ? (
        <div className="memory-list">
          {review.remedies.map((remedy) => (
            <div key={`${remedy.channel}-${remedy.action}`}>
              <p>
                <small>{remedy.channel}</small>
                <strong>{remedy.label}</strong>
                <span>{remedy.why}</span>
                {remedy.proposal ? <span>Proposed: {remedy.proposal}</span> : null}
              </p>
              {remedy.page ? <a className="button button-secondary" href={`#${remedy.page}`}>Open</a> : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="muted-copy">Nothing to do yet: no finding has a remedy.</p>
      )}
      {review.notes.length ? (
        <div className="memory-list">
          {review.notes.map((note, index) => (
            <div key={index}><p><small>How this review was made</small><span>{note}</span></p></div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** What to do after Apply, each step a link to the screen that does it. */
export function NextSteps({ steps, notes = [] }: { steps: GtmNextStep[]; notes?: string[] }) {
  return (
    <div className="form-stack">
      {notes.map((note) => <p key={note} className="danger-note">{note}</p>)}
      <div className="memory-list">
        {steps.map((step) => (
          <div key={`${step.page}-${step.label}`}>
            <p><strong>{step.label}</strong><span>{step.why}</span></p>
            {step.page ? <a className="button button-secondary" href={`#${step.page}`}>Open</a> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Strategy() {
  const { notify } = useApp();
  const described = useResource(() => api.get<GtmDescribe>("/gtm/envelope"), []);
  const products = useResource(() => api.get<{ items: GtmProduct[] }>("/gtm/products"), []);
  const [form, setForm] = useState<GoalForm>({
    product_id: "",
    goal_kind: "replies",
    goal_target: "20",
    horizon_days: "30",
    contact_budget: "0",
    channels: [],
    assumed_reply_percent: "3.4",
    per_identity_daily_cap: "30",
    notes: "",
    use_model: true
  });
  const [busy, setBusy] = useState("");
  const [refusal, setRefusal] = useState("");
  const [planId, setPlanId] = useState("");
  const [confirming, setConfirming] = useState<GtmPlan | null>(null);
  const [applied, setApplied] = useState<GtmApplyResult | null>(null);
  const plans = useResource(
    () => form.product_id
      ? api.get<{ items: GtmPlan[] }>(`/gtm/plans?product_id=${encodeURIComponent(form.product_id)}`)
      : Promise.resolve({ items: [] as GtmPlan[] }),
    [form.product_id]
  );

  const kinds = described.data?.vocabulary.kinds ?? [];
  const productItems = products.data?.items ?? [];
  const planItems = plans.data?.items ?? [];
  const selected = planItems.find((item) => item.id === planId) ?? planItems[0] ?? null;

  // Default to the first product, and to every channel off_CRM can run.
  useEffect(() => {
    if (!form.product_id && productItems.length) setForm((current) => ({ ...current, product_id: productItems[0].id }));
  }, [productItems, form.product_id]);
  // Once, when the vocabulary arrives — not whenever the list is empty, or
  // unticking the last box would tick every box again.
  const [channelsSeeded, setChannelsSeeded] = useState(false);
  useEffect(() => {
    if (!channelsSeeded && kinds.length) {
      setForm((current) => ({ ...current, channels: kinds }));
      setChannelsSeeded(true);
    }
  }, [kinds, channelsSeeded]);

  function set<K extends keyof GoalForm>(key: K, value: GoalForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleChannel(kind: string) {
    set("channels", form.channels.includes(kind) ? form.channels.filter((item) => item !== kind) : [...form.channels, kind]);
  }

  async function draft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("draft");
    setRefusal("");
    try {
      const plan = await api.post<GtmPlan>("/gtm/plans", {
        product_id: form.product_id,
        goal_kind: form.goal_kind,
        goal_target: Number(form.goal_target),
        horizon_days: Number(form.horizon_days),
        contact_budget: Number(form.contact_budget),
        channels: form.channels,
        assumed_reply_rate: Number(form.assumed_reply_percent) / 100,
        per_identity_daily_cap: Number(form.per_identity_daily_cap),
        notes: form.notes,
        use_model: form.use_model
      });
      notify(plan.source === "model" ? "Plan drafted. Read how it was made before applying it." : "Rules-based plan drafted.", "success");
      setPlanId(plan.id);
      setApplied(null);
      plans.reload();
    } catch (caught) {
      setRefusal(caught instanceof ApiError || caught instanceof Error ? caught.message : "The plan could not be drafted.");
    } finally {
      setBusy("");
    }
  }

  async function apply(plan: GtmPlan) {
    setBusy(`apply-${plan.id}`);
    try {
      const result = await api.post<GtmApplyResult>(`/gtm/plans/${plan.id}/apply`, {});
      setApplied(result);
      setConfirming(null);
      notify(`${result.campaigns.length} campaign(s) ready and paused. Nothing has sent.`, "success");
      plans.reload();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "The plan could not be applied.", "error");
    } finally {
      setBusy("");
    }
  }

  async function review(plan: GtmPlan) {
    setBusy(`review-${plan.id}`);
    try {
      const result = await api.post<GtmReview>(`/gtm/plans/${plan.id}/review`, { use_model: form.use_model });
      notify(result.source === "model" ? "Reviewed. The findings are measured; the remedies were chosen by a model." : "Reviewed with the rules.", "success");
      plans.reload();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "The plan could not be reviewed.", "error");
    } finally {
      setBusy("");
    }
  }

  async function revise(plan: GtmPlan) {
    setBusy(`revise-${plan.id}`);
    try {
      const next = await api.post<GtmPlan>(`/gtm/plans/${plan.id}/revise`, { use_model: form.use_model });
      notify(`Version ${next.version} drafted from the review. Read what changed, then apply it.`, "success");
      setPlanId(next.id);
      // The steps shown belong to the version applied before; this one is a draft.
      setApplied(null);
      plans.reload();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "The plan could not be revised.", "error");
    } finally {
      setBusy("");
    }
  }

  async function act(plan: GtmPlan, action: "discard") {
    setBusy(`${action}-${plan.id}`);
    try {
      await api.post<GtmPlan>(`/gtm/plans/${plan.id}/${action}`, {});
      notify("Plan discarded.", "success");
      plans.reload();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "That did not work.", "error");
    } finally {
      setBusy("");
    }
  }

  const envelope = described.data?.envelope;

  return (
    <>
      <PageHeader
        eyebrow="Strategy"
        title="Plan the go-to-market"
        description="Set a goal for a product. The brain picks channels from what off_CRM can run and fits them to what is connected. Applying a plan creates paused campaigns, so nothing sends until you start it."
      />
      <div className="settings-grid">
        <Panel title="Goal" subtitle="Replies are measured on email; views on posts. Those are the two outcomes a review can check.">
          <form className="form-stack" onSubmit={draft} noValidate>
            {refusal ? <p className="danger-note" role="alert">{refusal}</p> : null}
            <Field label="Product" hint={productItems.length ? undefined : "Describe a product on the Product screen first."}>
              <select id="gtm-plan-product" value={form.product_id} onChange={(e) => set("product_id", e.target.value)}>
                <option value="">Choose a product</option>
                {productItems.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>
            <Field label="Goal">
              <select id="gtm-plan-goal" value={form.goal_kind} onChange={(e) => set("goal_kind", e.target.value)}>
                <option value="replies">Replies to email</option>
                <option value="views">Views on posts</option>
              </select>
            </Field>
            <Field label="Target">
              <input id="gtm-plan-target" type="number" min={1} max={100000} value={form.goal_target} onChange={(e) => set("goal_target", e.target.value)} />
            </Field>
            <Field label="Days" hint="7 to 180.">
              <input id="gtm-plan-days" type="number" min={7} max={180} value={form.horizon_days} onChange={(e) => set("horizon_days", e.target.value)} />
            </Field>
            <Field label="New contacts" hint="How many Apollo credits the plan may assume. Applying a plan never spends them.">
              <input id="gtm-plan-contacts" type="number" min={0} max={10000} value={form.contact_budget} onChange={(e) => set("contact_budget", e.target.value)} />
            </Field>
            <Field label="Channels">
              <span className="settings-grid">
                {kinds.map((kind) => (
                  <label key={kind} className="check-line">
                    <input id={`gtm-plan-channel-${kind}`} type="checkbox" checked={form.channels.includes(kind)} onChange={() => toggleChannel(kind)} />
                    <span>{kind}</span>
                  </label>
                ))}
              </span>
            </Field>
            <Field label="Assumed reply rate, %" hint="3.4% is the published average for plain-text cold email. The first review replaces it with your own number.">
              <input id="gtm-plan-rate" type="number" min={0.1} max={50} step={0.1} value={form.assumed_reply_percent} onChange={(e) => set("assumed_reply_percent", e.target.value)} />
            </Field>
            <Field label="Cold emails per mailbox a day" hint="Warm-up is not automatic yet, so this is the ceiling per sending identity.">
              <input id="gtm-plan-cap" type="number" min={1} max={500} value={form.per_identity_daily_cap} onChange={(e) => set("per_identity_daily_cap", e.target.value)} />
            </Field>
            <Field label="Anything the brain should know" hint="Sent as campaign material. No email addresses.">
              <textarea id="gtm-plan-notes" rows={2} maxLength={1000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
            </Field>
            <label className="check-line">
              <input id="gtm-plan-use-model" type="checkbox" checked={form.use_model} onChange={(e) => set("use_model", e.target.checked)} />
              <span>Ask a model (without one, the rules-based plan is used)</span>
            </label>
            <div className="modal-actions">
              <Button type="submit" busy={busy === "draft"} disabled={!form.product_id}>Draft a plan</Button>
            </div>
          </form>
        </Panel>

        <Panel title="What is connected" subtitle="A plan never proposes more than this.">
          <Loadable loading={described.loading} error={described.error} />
          {envelope ? (
            <>
              <div className="definition-list">
                <div><dt>Email a day</dt><dd>{envelope.email_daily_capacity} across {envelope.email_identities || "no"} sending identit{envelope.email_identities === 1 ? "y" : "ies"}</dd></div>
                <div><dt>Posts a day</dt><dd>{envelope.post_daily_capacity} on {envelope.platforms.join(", ") || "nothing connected"}</dd></div>
                <div><dt>Apollo</dt><dd><Badge tone={envelope.apollo_ready ? "success" : "warning"}>{envelope.apollo_ready ? "connected" : "not connected"}</Badge></dd></div>
              </div>
              {envelope.blockers.map((blocker) => <p key={blocker} className="danger-note">{blocker}</p>)}
            </>
          ) : null}
        </Panel>
      </div>

      <Panel title="Plans" subtitle="Newest first. A plan keeps its own copy of the product it was written against.">
        <Loadable loading={plans.loading} error={plans.error} />
        {!plans.loading && !planItems.length ? (
          <StatePanel title="No plan yet" description="Set a goal above and draft one." />
        ) : null}
        {planItems.length > 1 ? (
          <div className="modal-actions">
            {planItems.map((item) => (
              <Button key={item.id} tone={item.id === selected?.id ? "secondary" : "ghost"} onClick={() => setPlanId(item.id)}>
                v{item.version} · {item.status}
              </Button>
            ))}
          </div>
        ) : null}
        {selected ? (
          <PlanView
            plan={selected}
            actions={selected.status === "draft" ? (
              <>
                <Button onClick={() => setConfirming(selected)} disabled={selected.product_deleted}>Apply</Button>
                <Button tone="secondary" busy={busy === `discard-${selected.id}`} onClick={() => act(selected, "discard")}>Discard</Button>
              </>
            ) : selected.status === "applied" ? (
              <>
                <Button busy={busy === `review-${selected.id}`} onClick={() => review(selected)}>Review against what was measured</Button>
                {/* A revision is written from a review, so there is nothing to revise from until one exists. */}
                <Button tone="secondary" busy={busy === `revise-${selected.id}`} disabled={!selected.review} onClick={() => revise(selected)}>
                  {selected.review ? "Write the next version from this review" : "Review first, then revise"}
                </Button>
              </>
            ) : null}
          />
        ) : null}
      </Panel>

      {selected?.review ? (
        <Panel title="Where it is going wrong" subtitle="Checked in a fixed order: delivery, then whether it is running, then volume, and only then the copy.">
          <ReviewView review={selected.review} />
        </Panel>
      ) : null}

      {applied ? (
        <Panel title="Next steps" subtitle="Apply created or updated these campaigns and left every one paused.">
          <NextSteps steps={applied.next_steps} notes={applied.notes} />
        </Panel>
      ) : null}

      <Modal
        open={confirming !== null}
        title="Apply this plan?"
        description={confirming
          ? `This creates or updates ${confirming.plan.channels.length} campaign(s) — ${confirming.plan.channels.map((item) => item.kind).join(", ")} — and leaves every one paused. It imports nobody and spends no Apollo credit. Nothing sends until you resume a campaign.`
          : ""}
        onClose={() => setConfirming(null)}
      >
        <div className="modal-actions">
          <Button tone="secondary" onClick={() => setConfirming(null)}>Not yet</Button>
          <Button busy={confirming !== null && busy === `apply-${confirming.id}`} onClick={() => confirming && apply(confirming)}>Apply plan</Button>
        </div>
      </Modal>
    </>
  );
}
