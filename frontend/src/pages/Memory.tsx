import { useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";

type TemplateScore = {
  id: string;
  template_id: string;
  variant_id: string;
  label: string;
  sends: number;
  replies: number;
  reply_rate: number;
  is_winner: boolean;
  retired: boolean;
  judged: boolean;
  weak: boolean;
  min_sends_to_judge: number;
};

type Task = {
  id: string;
  title: string;
  kind: string;
  status: string;
  summary: string;
  done_count: number;
  total_steps: number;
  next_step: { name: string } | null;
  decisions: Array<{ text: string; at: string }>;
};

type ContextOverview = {
  stats: {
    templates: number;
    total_sends: number;
    total_replies: number;
    judged: number;
    weak: number;
    winner: TemplateScore | null;
    open_tasks: number;
    min_sends_to_judge: number;
  };
  templates: TemplateScore[];
  tasks: Task[];
  reference: string;
};

type Rewrite = {
  current: TemplateScore;
  suggested_text: string;
  written_by: string;
  model_id: string;
};

/**
 * The memory screen.
 *
 * Two things live here: which templates earn replies, and where each job has
 * got to. Both are plain counting — no AI writes anything on this page, which is
 * why the numbers can be trusted and why keeping them costs nothing.
 */
export default function Memory() {
  const { notify } = useApp();
  const [busy, setBusy] = useState("");
  const [rewrite, setRewrite] = useState<Rewrite | null>(null);
  const [edited, setEdited] = useState("");

  const overview = useResource(() => api.get<ContextOverview>("/ai/context"), []);

  async function askForRewrite(score: TemplateScore) {
    setBusy(`rewrite-${score.id}`);
    try {
      const result = await api.post<Rewrite>(
        `/ai/context/templates/${encodeURIComponent(score.template_id)}/rewrite`,
        { variant_id: score.variant_id, use_winner: true }
      );
      setRewrite(result);
      setEdited(result.suggested_text);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not get a new version", "error");
    } finally {
      setBusy("");
    }
  }

  async function approve() {
    if (!rewrite || !edited.trim()) return;
    setBusy("approve");
    try {
      await api.post(
        `/ai/context/templates/${encodeURIComponent(rewrite.current.template_id)}/approve`,
        {
          template_text: edited.trim(),
          variant_id: `${rewrite.current.variant_id || "a"}-new`,
          label: `${rewrite.current.label || "Template"} (new)`,
          parent_variant_id: rewrite.current.variant_id
        }
      );
      notify("Saved. It will now be tested against the old one.", "success");
      setRewrite(null);
      overview.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save", "error");
    } finally {
      setBusy("");
    }
  }

  const data = overview.data;

  return (
    <div className="page-stack">
      <PageHeader
        title="Memory"
        description="Which emails get replies, and where each job has got to. All of it is counted by off_CRM, not guessed by an AI."
      />

      {overview.loading || overview.error ? (
        <Loadable loading={overview.loading} error={overview.error ?? ""} />
      ) : !data ? null : (
        <>
          <div className="stat-row">
            <StatCard label="Emails sent" value={String(data.stats.total_sends)} />
            <StatCard label="Replies" value={String(data.stats.total_replies)} accent="green" />
            <StatCard
              label="Weak templates"
              value={String(data.stats.weak)}
              accent={data.stats.weak > 0 ? "orange" : "blue"}
            />
            <StatCard label="Jobs open" value={String(data.stats.open_tasks)} accent="violet" />
          </div>

          {/* ── templates ────────────────────────────────────────────────── */}
          <Panel
            title="Templates"
            subtitle={`A template needs ${data.stats.min_sends_to_judge} sends before the number means anything`}
            className="settings-wide"
          >
            {data.templates.length === 0 ? (
              <StatePanel
                title="Nothing counted yet"
                description="Once you send emails, each template appears here with how many replies it earned."
              />
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Template</th>
                      <th scope="col">Sent</th>
                      <th scope="col">Replies</th>
                      <th scope="col">Reply rate</th>
                      <th scope="col">
                        <span className="visually-hidden">Action</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.templates.map((score) => (
                      <tr key={score.id}>
                        <td>
                          <strong>{score.label || score.template_id}</strong>
                          {score.variant_id ? (
                            <>
                              {" "}
                              <small className="muted-copy">({score.variant_id})</small>
                            </>
                          ) : null}
                          {score.is_winner ? (
                            <>
                              {" "}
                              <Badge tone="success">Best</Badge>
                            </>
                          ) : null}
                        </td>
                        <td>{score.sends}</td>
                        <td>{score.replies}</td>
                        <td>
                          <strong>{score.reply_rate}%</strong>
                          <br />
                          {score.judged ? (
                            score.weak ? (
                              <Badge tone="warning">Weak</Badge>
                            ) : (
                              <Badge tone="success">Working</Badge>
                            )
                          ) : (
                            <small className="muted-copy">
                              too early — {score.min_sends_to_judge - score.sends} more sends
                            </small>
                          )}
                        </td>
                        <td>
                          {score.weak ? (
                            <Button
                              tone="ghost"
                              busy={busy === `rewrite-${score.id}`}
                              onClick={() => askForRewrite(score)}
                            >
                              Get a better version
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="form-note">
              When a template is weak, off_CRM sends an AI <strong>only</strong> the template
              wording and the reply number. No names. No email addresses. Nobody's details. That is
              why this is cheap and safe — and it is not training an AI on your data.
            </p>
          </Panel>

          {/* ── the rewrite, waiting for approval ────────────────────────── */}
          {rewrite ? (
            <Panel
              title="New version — you decide"
              subtitle={`Written by ${rewrite.written_by} · ${rewrite.model_id}`}
              className="settings-wide"
            >
              <p className="muted-copy">
                The old one earns {rewrite.current.reply_rate}%. Nothing changes until you save.
              </p>
              <textarea
                className="rewrite-box"
                value={edited}
                onChange={(event) => setEdited(event.target.value)}
                rows={10}
                aria-label="New template wording"
              />
              <div className="button-row">
                <Button busy={busy === "approve"} onClick={approve} disabled={!edited.trim()}>
                  Save and test it
                </Button>
                <Button tone="ghost" onClick={() => setRewrite(null)}>
                  Throw it away
                </Button>
              </div>
            </Panel>
          ) : null}

          {/* ── the reference other models are shown ─────────────────────── */}
          {data.reference ? (
            <Panel
              title="What other models are told"
              subtitle="Your best template, offered as a example they can follow or beat"
            >
              <pre className="payload-block">{data.reference}</pre>
            </Panel>
          ) : null}

          {/* ── jobs ─────────────────────────────────────────────────────── */}
          <Panel title="Jobs in progress" subtitle="So swapping models mid-job does not lose your place">
            {data.tasks.length === 0 ? (
              <StatePanel
                title="No job open"
                description="When a long job runs, its progress and your decisions are kept here."
              />
            ) : (
              <div className="task-list">
                {data.tasks.map((task) => (
                  <article key={task.id} className="task-card">
                    <header>
                      <strong>{task.title || task.kind}</strong>
                      <small className="muted-copy">
                        {task.done_count} of {task.total_steps} steps done
                      </small>
                    </header>
                    {task.next_step ? <p className="task-next">Next: {task.next_step.name}</p> : null}
                    {task.decisions.length > 0 ? (
                      <ul className="task-decisions">
                        {task.decisions.slice(-3).map((decision, index) => (
                          <li key={index}>{decision.text}</li>
                        ))}
                      </ul>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
