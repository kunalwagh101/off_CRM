import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { ApolloExclusion, ApolloRejection, DiscoveryCandidate, DiscoveryRun, Paginated, ResearchGraph } from "../types";
import { Loadable, NoCampaign } from "./shared";

const DEFAULT_CATEGORY = "Sustainability / ESG / Climate";

function candidateTone(status: DiscoveryCandidate["status"]): string {
  if (status === "approved" || status === "imported") return "success";
  if (status === "excluded" || status === "rejected") return "danger";
  if (status === "apollo_queued") return "violet";
  return "blue";
}

export default function Discovery() {
  const { campaignId, activeCampaign, notify, refreshCampaigns } = useApp();
  const [runId, setRunId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [engine, setEngine] = useState<"safe_http" | "crawl4ai_public_js">("safe_http");
  const [workers, setWorkers] = useState(1);
  const [maxPages, setMaxPages] = useState(20);
  const runs = useResource(
    () => campaignId
      ? api.get<Paginated<DiscoveryRun>>(`/campaigns/${campaignId}/discovery/runs?limit=50`)
      : Promise.resolve({ items: [], total: 0 }),
    [campaignId]
  );
  const candidates = useResource(
    () => runId
      ? api.get<Paginated<DiscoveryCandidate>>(`/discovery/runs/${runId}/candidates?limit=1000`)
      : Promise.resolve({ items: [], total: 0 }),
    [runId]
  );
  const graph = useResource(
    () => runId
      ? api.get<ResearchGraph>(`/research/graph?run_id=${encodeURIComponent(runId)}&limit=300`)
      : Promise.resolve({ nodes: [], edges: [], stats: { nodes: 0, edges: 0, by_type: {}, by_relation: {} } }),
    [runId]
  );
  const rejections = useResource(
    () => api.get<Paginated<ApolloRejection>>("/apollo/rejections?limit=100"),
    []
  );
  const exclusions = useResource(
    () => api.get<Paginated<ApolloExclusion>>("/apollo/exclusions?limit=100"),
    []
  );

  useEffect(() => {
    const first = runs.data?.items[0]?.id ?? "";
    if (first && !runs.data?.items.some((item) => item.id === runId)) setRunId(first);
  }, [runs.data, runId]);

  useEffect(() => setSelected(new Set()), [runId]);

  const currentRun = runs.data?.items.find((item) => item.id === runId) ?? null;
  const actionable = useMemo(
    () => candidates.data?.items.filter((item) => !["excluded", "rejected"].includes(item.status)) ?? [],
    [candidates.data]
  );

  if (!campaignId) return <><PageHeader title="Lead discovery" /><NoCampaign /></>;

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const data = new FormData(event.currentTarget);
    const lines = (name: string) => String(data.get(name) ?? "")
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    try {
      const result = await api.post<DiscoveryRun>(`/campaigns/${campaignId}/discovery/runs`, {
        seed_urls: lines("seed_urls"),
        allowed_domains: lines("allowed_domains"),
        objective_prompt: String(data.get("objective_prompt") ?? ""),
        engine,
        parallel_workers: workers,
        target_count: Number(data.get("target_count") ?? 100),
        category: String(data.get("category") ?? DEFAULT_CATEGORY),
        max_pages: maxPages,
        max_depth: Number(data.get("max_depth") ?? 1),
        obey_robots: true,
        request_delay_seconds: 0.75
      });
      setRunId(result.id);
      await runs.reload();
      await candidates.reload();
      await graph.reload();
      notify(`${result.fresh_count} fresh POIs found from ${result.pages_crawled} public pages`, result.status === "failed" ? "error" : "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Discovery failed", "error");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected((current) => current.size === actionable.length
      ? new Set()
      : new Set(actionable.map((item) => item.id)));
  }

  async function decide(decision: "approve" | "reject") {
    if (!selected.size) return;
    setBusy(true);
    try {
      const result = await api.post<{ updated: number }>(`/discovery/runs/${runId}/decision`, {
        candidate_ids: [...selected], decision
      });
      notify(`${result.updated} POIs ${decision === "approve" ? "approved" : "rejected"}`, "success");
      setSelected(new Set());
      candidates.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Update failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function queueApollo() {
    if (!selected.size) return;
    setBusy(true);
    try {
      const result = await api.post<{ queued: number; skipped: unknown[]; file: string }>(`/discovery/runs/${runId}/apollo-queue`, {
        candidate_ids: [...selected]
      });
      notify(`${result.queued} POIs placed in the Apollo enrichment inbox`, result.queued ? "success" : "info");
      setSelected(new Set());
      candidates.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Apollo queue failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function importCrm() {
    if (!selected.size) return;
    setBusy(true);
    try {
      const result = await api.post<{ added: number; existing: number }>(`/campaigns/${campaignId}/discovery/runs/${runId}/import`, {
        candidate_ids: [...selected]
      });
      notify(`${result.added} POIs added to CRM, ${result.existing} already existed`, "success");
      setSelected(new Set());
      candidates.reload();
      refreshCampaigns();
    } catch (error) {
      notify(error instanceof Error ? error.message : "CRM import failed", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={activeCampaign?.name}
        title="Lead discovery"
        description="Find public POIs, remove old contacts, review the evidence, then send approved people to Apollo or the CRM."
      />
      <div className="discovery-layout">
        <Panel title="Start a public-web run" subtitle="Prompt-compiled research plan, guarded Crawl4AI option, evidence review and no logged-in social sessions.">
          <form className="form-stack" onSubmit={startRun}>
            <Field label="Research prompt" hint="Describe the companies, roles, handles and evidence you want. The CRM converts this into bounded controls.">
              <textarea name="objective_prompt" rows={5} required defaultValue="Find 100 competitor companies, identify relevant sales team employees and collect public social handles. Show whether interaction evidence is available." />
            </Field>
            <Field label="Public seed URLs" hint="One company team page, event speaker page, association directory or public bio page per line.">
              <textarea name="seed_urls" rows={5} required placeholder={"https://example.org/team\nhttps://conference.example.org/speakers"} />
            </Field>
            <Field label="Allowed domains" hint="Optional. Leave empty to use only the seed URL domains.">
              <textarea name="allowed_domains" rows={3} placeholder={"example.org\nconference.example.org"} />
            </Field>
            <Field label="POI category"><input name="category" defaultValue={DEFAULT_CATEGORY} /></Field>

            <fieldset className="choice-group">
              <legend>Crawler engine</legend>
              <div className="choice-cards" role="radiogroup" aria-label="Crawler engine">
                <button
                  type="button"
                  role="radio"
                  aria-checked={engine === "safe_http"}
                  className={engine === "safe_http" ? "choice-card choice-active" : "choice-card"}
                  onClick={() => setEngine("safe_http")}
                >
                  <strong>Standard crawler</strong>
                  <span>Fast and light. Reads normal public pages. Best first choice.</span>
                  <small className="choice-cost">Load: low</small>
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={engine === "crawl4ai_public_js"}
                  className={engine === "crawl4ai_public_js" ? "choice-card choice-active" : "choice-card"}
                  onClick={() => setEngine("crawl4ai_public_js")}
                >
                  <strong>Browser rendering</strong>
                  <span>Opens a real browser (Crawl4AI) for JavaScript-heavy pages. Slower and heavier.</span>
                  <small className="choice-cost">Load: high — each worker runs its own browser</small>
                </button>
              </div>
            </fieldset>

            <fieldset className="choice-group">
              <legend>Parallel workers — you control the resource use</legend>
              <div className="segmented" role="radiogroup" aria-label="Number of parallel workers">
                {[1, 2, 3, 4].map((count) => (
                  <button
                    key={count}
                    type="button"
                    role="radio"
                    aria-checked={workers === count}
                    className={workers === count ? "segment segment-active" : "segment"}
                    onClick={() => setWorkers(count)}
                  >
                    {count}
                  </button>
                ))}
              </div>
              <small className="workers-estimate">
                {workers === 1
                  ? "1 worker: slowest, lightest on this machine."
                  : `${workers} workers: up to ${workers}× faster across different sites, roughly ${workers}× the ${engine === "crawl4ai_public_js" ? "browser memory and CPU" : "CPU and bandwidth"}.`}
                {" "}Politeness per site never changes — extra workers never hit one site harder.
              </small>
            </fieldset>

            <div className="form-grid">
              <Field label="Target POIs"><input name="target_count" type="number" min="1" max="1000" defaultValue="100" /></Field>
              <Field label="Maximum pages" hint={`~${Math.ceil(maxPages / workers)} fetch rounds at ${workers} worker${workers > 1 ? "s" : ""}`}>
                <input name="max_pages" type="number" min="1" max="100" value={maxPages} onChange={(event) => setMaxPages(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} />
              </Field>
              <Field label="Link depth"><input name="max_depth" type="number" min="0" max="3" defaultValue="1" /></Field>
            </div>
            <div className="form-note"><strong>Social account boundary</strong><span>Public profile links can enter the graph, but LinkedIn and Instagram are not crawled. Interaction evidence needs an official API or manual import. Cloudflare/CAPTCHA bypass is not enabled.</span></div>
            <Button type="submit" busy={busy}>Find POIs</Button>
          </form>
        </Panel>

        <Panel title="Discovery runs" subtitle={`${runs.data?.total ?? 0} runs for this campaign`}>
          {runs.loading || runs.error ? <Loadable loading={runs.loading} error={runs.error} /> : runs.data?.items.length ? (
            <div className="run-list">
              {runs.data.items.map((run) => (
                <button key={run.id} className={run.id === runId ? "run-card run-selected" : "run-card"} onClick={() => setRunId(run.id)}>
                  <span><strong>{run.fresh_count} fresh POIs</strong><small>{run.pages_crawled} pages · {run.category}</small></span>
                  <Badge tone={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "warning"}>{run.status}</Badge>
                </button>
              ))}
            </div>
          ) : <StatePanel title="No discovery runs" description="Add public seed pages to run the first guarded crawl." />}
        </Panel>
      </div>

      {currentRun ? <Panel title="Compiled research plan" subtitle={currentRun.objective_prompt}>
        <div className="research-summary">
          <div><strong>{currentRun.target_count}</strong><small>target POIs</small></div>
          <div><strong>{currentRun.engine === "crawl4ai_public_js" ? "Crawl4AI" : "Safe HTTP"}</strong><small>engine</small></div>
          <div><strong>{currentRun.plan?.role_groups?.join(", ") || "all relevant roles"}</strong><small>role focus</small></div>
          <div><strong>{currentRun.plan?.source_adapters?.join(", ") || "public web"}</strong><small>source adapters</small></div>
        </div>
        {currentRun.plan?.blocked_requirements?.length ? <div className="form-note"><strong>Connector required</strong><span>{currentRun.plan.blocked_requirements.join(" ")}</span></div> : null}
      </Panel> : null}

      <Panel
        title="Discovered POIs"
        subtitle={currentRun ? `${currentRun.fresh_count} fresh, ${currentRun.excluded_count} excluded automatically` : "Choose a run"}
        action={selected.size ? <div className="button-row"><Button tone="ghost" busy={busy} onClick={() => decide("reject")}>Reject</Button><Button tone="secondary" busy={busy} onClick={() => decide("approve")}>Approve</Button><Button tone="secondary" busy={busy} onClick={queueApollo}>Queue for Apollo</Button><Button busy={busy} onClick={importCrm}>Add to CRM</Button></div> : undefined}
      >
        {candidates.loading || candidates.error ? <Loadable loading={candidates.loading} error={candidates.error} /> : candidates.data?.items.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="checkbox-cell"><input type="checkbox" checked={Boolean(actionable.length) && selected.size === actionable.length} onChange={selectAll} aria-label="Select all usable POIs" /></th><th>POI</th><th>Company</th><th>Public evidence</th><th>Confidence</th><th>Status</th></tr></thead>
              <tbody>{candidates.data.items.map((candidate) => (
                <tr key={candidate.id}>
                  <td className="checkbox-cell"><input type="checkbox" disabled={candidate.status === "excluded" || candidate.status === "rejected"} checked={selected.has(candidate.id)} onChange={() => toggle(candidate.id)} aria-label={`Select ${candidate.full_name}`} /></td>
                  <td><strong>{candidate.full_name}</strong><small>{candidate.email || "Email pending Apollo"}</small></td>
                  <td><strong>{candidate.company || "Company missing"}</strong><small>{candidate.title}</small></td>
                  <td><a className="source-link" href={candidate.source_url} target="_blank" rel="noreferrer">Open source</a><small>{candidate.public_hook || "Structured profile found; hook needs review"}</small></td>
                  <td><strong>{Math.round(candidate.confidence * 100)}%</strong><small>structured evidence</small></td>
                  <td><Badge tone={candidateTone(candidate.status)}>{candidate.status.replaceAll("_", " ")}</Badge><small>{candidate.exclusion_reason.replaceAll("_", " ")}</small></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <StatePanel title="No POIs in this run" description="The pages may not contain Schema.org Person data, may be blocked by robots.txt, or may require a different public source." />}
      </Panel>

      <div className="discovery-layout">
        <Panel title="Research memory graph" subtitle={`${graph.data?.stats.nodes ?? 0} entities · ${graph.data?.stats.edges ?? 0} relationships`}>
          {graph.loading || graph.error ? <Loadable loading={graph.loading} error={graph.error} /> : graph.data?.nodes.length ? (
            <>
              <div className="research-summary">
                {Object.entries(graph.data.stats.by_type).map(([kind, count]) => <div key={kind}><strong>{count}</strong><small>{kind.replaceAll("_", " ")}</small></div>)}
              </div>
              <div className="graph-edge-list">
                {graph.data.edges.slice(0, 12).map((edge) => {
                  const source = graph.data?.nodes.find((node) => node.id === edge.source_entity_id);
                  const target = graph.data?.nodes.find((node) => node.id === edge.target_entity_id);
                  return <div key={edge.id}><strong>{source?.name || "Entity"}</strong><Badge tone="blue">{edge.relation_type.replaceAll("_", " ")}</Badge><span>{target?.name || "Entity"}</span></div>;
                })}
              </div>
            </>
          ) : <StatePanel title="No graph evidence yet" description="A completed discovery run will add people, companies, public pages and reference-only social profiles." />}
        </Panel>

        <Panel title="Apollo suppression ledger" subtitle="Accepted exclusions and rejected outcomes are kept separate" action={<Button tone="ghost" onClick={() => { exclusions.reload(); rejections.reload(); }}>Refresh</Button>}>
          {rejections.loading || exclusions.loading || rejections.error || exclusions.error ? <Loadable loading={rejections.loading || exclusions.loading} error={rejections.error || exclusions.error} /> : (
            <>
              <div className="research-summary">
                <div><strong>{exclusions.data?.total ?? 0}</strong><small>accepted · permanently excluded</small></div>
                <div><strong>{rejections.data?.total ?? 0}</strong><small>rejected · retry policy recorded</small></div>
              </div>
              {exclusions.data?.items.length ? <div className="rejection-list">
                {exclusions.data.items.slice(0, 6).map((item, index) => <div key={`${item.apollo_person_id}:${item.email}:${index}`}>
                  <span><strong>{item.full_name || item.email || "Accepted POI"}</strong><small>{item.company || item.email}</small></span>
                  <span><Badge tone="success">permanent exclusion</Badge><small>prevents duplicate Apollo use</small></span>
                </div>)}
              </div> : null}
              {rejections.data?.items.length ? <div className="rejection-list">
                {rejections.data.items.slice(0, 14).map((item) => <div key={`${item.identity}:${item.reason}`}>
                  <span><strong>{item.full_name || item.email || "Unnamed POI"}</strong><small>{item.company || item.outcome_class}</small></span>
                  <span><Badge tone={item.permanent_exclusion ? "danger" : item.blocks_automatic_retry ? "warning" : "blue"}>{item.reason.replaceAll("_", " ")}</Badge><small>{item.retry_policy.replaceAll("_", " ")}</small></span>
                </div>)}
              </div> : null}
              {!exclusions.data?.items.length && !rejections.data?.items.length ? <StatePanel title="No Apollo outcomes yet" description="After a live Apollo run, accepted contacts and rejected/no-match outcomes appear here automatically." /> : null}
            </>
          )}
        </Panel>
      </div>
    </>
  );
}
