import type { Companion, Procedure } from "./AgentTeam";

export type ContextPreview = {
  companion: Companion;
  skills: Procedure[];
  tools: Array<{ id: string; name: string }>;
  memory: Array<{ id?: string; content: string }>;
};
export type RoleOutcome = {
  role: string;
  status: string;
  topics?: Array<{ terms: string[]; titles: string[]; views: number; channels: number }>;
  project?: { title?: string; name?: string };
  drafts?: { assets_considered: number; posts_created: number; skipped: unknown[]; warnings: string[] };
  progress?: { totals: Record<string, number>; measured_posts: number; goals: Array<{ id: string; metric: string; achieved: number; target: number; percent: number }> };
  plan?: { title?: string; name?: string; source?: string };
};
export type DelegationOutcome = { result: string; children: Array<{ companion_id: string; name: string; result: string }> };

export function ContextPreviewView({ value }: { value: ContextPreview }) {
  return <section aria-label="Context preview" className="agent-team-result">
    <h3>{value.companion.name}: available context</h3>
    <p>Connectors applies its data policy and scanner before any model request.</p>
    <h4>Profile instructions</h4><p className="preserve-lines">{value.companion.instructions}</p>
    <h4>Selected procedures</h4>{value.skills.length ? value.skills.map((p) => <article key={p.id}><strong>{p.name}</strong><p className="preserve-lines">{p.content}</p></article>) : <p>No procedures selected.</p>}
    <h4>Granted tools</h4>{value.tools.length ? <ul>{value.tools.map((t) => <li key={t.id}>{t.name}</li>)}</ul> : <p>No tools granted.</p>}
    <h4>Approved memory</h4>{value.memory.length ? <ul>{value.memory.map((m, i) => <li key={m.id ?? i}>{m.content}</li>)}</ul> : <p>No matching approved facts.</p>}
  </section>;
}

export function RoleResultView({ value, open }: { value: RoleOutcome; open: (page: string) => void }) {
  return <section aria-label="Role result" className="agent-team-result" aria-live="polite">
    {value.role === "Scout" && <><h3>Observed topics</h3>{value.topics?.length ? <ul>{value.topics.map((t, i) => <li key={i}><strong>{t.terms.join(", ")}</strong><p>{t.views.toLocaleString()} observed views across {t.channels} channels.</p>{t.titles.map((title, j) => <p key={j}>{title}</p>)}</li>)}</ul> : <p>No topics currently meet the source and recency requirements. Add public channels in Posting to collect observations.</p>}<button className="button button-secondary" type="button" onClick={() => open("posting")}>Open observed sources</button></>}
    {value.role === "Maker" && <><h3>Timeline ready for review</h3><p>{value.project?.title || value.project?.name || "Review the new timeline in the video editor before approving it."}</p><button className="button button-secondary" type="button" onClick={() => open("videoeditor")}>Review video timeline</button></>}
    {value.role === "Poster" && <><h3>Drafting finished</h3><p>{value.drafts?.posts_created ?? "No count returned for"} posts created from {value.drafts?.assets_considered ?? "unreported"} approved assets. None were approved or published by this action.</p>{Boolean(value.drafts?.skipped.length || value.drafts?.warnings.length) && <p>Some items need attention. Check approved images and posting prerequisites before trying again.</p>}<button className="button button-secondary" type="button" onClick={() => open("posting")}>Review draft posts</button></>}
    {value.role === "Analyst" && <><h3>Measured campaign performance</h3>{value.progress ? <><p>{value.progress.measured_posts} posts have recorded measurements.</p><dl>{Object.entries(value.progress.totals).map(([metric, count]) => <div key={metric}><dt>{metric}</dt><dd>{count.toLocaleString()}</dd></div>)}</dl>{value.progress.goals.map((goal) => <p key={goal.id}>{goal.metric}: {goal.achieved.toLocaleString()} of {goal.target.toLocaleString()} ({goal.percent}%).</p>)}</> : <p>No measurement report was returned.</p>}</>}
    {value.role === "Director" && <><h3>Strategy draft saved</h3><p>{value.plan?.title || value.plan?.name || "Open strategy plans to review the saved draft."}</p>{value.plan?.source === "rules" && <p>This draft used planning rules; it was not written by a model.</p>}<p>No campaigns were applied or activated.</p><button className="button button-secondary" type="button" onClick={() => open("strategy")}>Review strategy plans</button></>}
  </section>;
}

export function DelegationResultView({ value }: { value: DelegationOutcome }) {
  return <section aria-label="Delegation result" className="agent-team-result" aria-live="polite"><h3>Parent review</h3><p className="preserve-lines">{value.result}</p><h4>Child findings</h4><p>These are model findings for you to verify, not confirmed facts.</p>{value.children.map((child) => <article key={child.companion_id}><strong>{child.name}</strong><p className="preserve-lines">{child.result}</p></article>)}</section>;
}
