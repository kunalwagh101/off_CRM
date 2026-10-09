import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import DraftedPosts, { type DraftedPost } from "./DraftedPosts";

/**
 * How much gets posted, and who decides.
 *
 * The engine is better at the arithmetic — it can see the goal, the deadline,
 * how many views a post is actually worth and what the platform allows. The
 * owner is the one whose name is on the account. So this screen is arranged
 * around that split and nothing else:
 *
 * **The cap is yours.** A number per handle that nothing may cross — not the
 * goal, not the pacer, not a good week. Empty means no cap, which is not the
 * same as zero: with no cap the platform's own published limit still binds.
 *
 * **The rate is a recommendation.** The machine works out the ideal number
 * every cycle and shows it here with its reasoning. It changes nothing until
 * you press the button, unless you have explicitly told it it may.
 *
 * The same shape as the video review queue, and for the same reason: a machine
 * that makes things unattended must not also be the thing that decides they go
 * out.
 */

type Account = {
  id: string;
  platform: string;
  handle: string;
  label: string;
  enabled: number;
  daily_cap: number;
};

type Pair = { distribution_campaign_id: string; image_campaign_id: string; plan_id?: string; posts_per_day?: number; enabled?: boolean; account_ids: string[] };

type Automation = {
  enabled: boolean;
  plan: boolean;
  draft: boolean;
  publish_due: boolean;
  pipelines: Pair[];
  last_error: string;
  posts_per_day: number;
  pace_mode: "off" | "suggest" | "auto";
  pending_paces: Record<string, Automation["pending_pace"]>;
  pending_pace: {
    suggestion_id?: string;
    distribution_campaign_id?: string;
    suggested_per_day?: number;
    current_per_day?: number;
    reason?: string;
    action?: string;
    capped_by?: string;
  };
};

type Pacing = {
  posts_per_day: number;
  previous_per_day: number;
  action: string;
  reason: string;
  capped_by: string;
  owner_cap: number;
  steering: boolean;
  measured_posts: number;
  required_per_day: number;
};

const MODES: Array<{ id: Automation["pace_mode"]; label: string; note: string }> = [
  { id: "off", label: "Leave it alone", note: "The rate is whatever you set. Nothing moves it." },
  {
    id: "suggest",
    label: "Tell me what you'd do",
    note: "Works out the ideal rate every cycle and waits for you. The default."
  },
  {
    id: "auto",
    label: "Move it yourself",
    note: "Changes the rate on its own — never past your cap."
  }
];

export default function Posting() {
  const { campaignId, campaigns, activeCampaign, selectCampaign, refreshCampaigns, notify } = useApp();
  const postingId = activeCampaign?.kind === "distribution" ? campaignId : "";
  const [posts, setPosts] = useState<DraftedPost[]>([]);
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);
  const [handle, setHandle] = useState("");
  const [actionError, setActionError] = useState("");
  const generation = useRef(0);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [pacing, setPacing] = useState<Pacing | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const [connected, config, drafts, approved, suggestion] = await Promise.all([
        api.get<{ items: Account[] }>("/distribution/accounts"),
        api.get<Automation>("/content-automation"),
        postingId ? api.get<{ items: DraftedPost[] }>(`/campaigns/${postingId}/posts?status=draft`) : Promise.resolve({ items: [] }),
        postingId ? api.get<{ items: DraftedPost[] }>(`/campaigns/${postingId}/posts?status=approved`) : Promise.resolve({ items: [] }),
        postingId ? api.get<Pacing>(`/campaigns/${postingId}/pacing`) : Promise.resolve(null)
      ]);
      if (request !== generation.current) return;
      setAccounts(connected.items);
      setAutomation(config);
      setPosts([...drafts.items, ...approved.items]);
      setPacing(suggestion);
    } catch (reason) {
      if (request === generation.current) setError(reason instanceof Error ? reason.message : "Could not load posting. Try again.");
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, [postingId]);

  useEffect(() => {
    void load();
    return () => { generation.current += 1; };
  }, [load]);

  const act = async (operation: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setActionError("");
    try {
      await operation();
      notify(message, "success");
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Could not finish this action. Check its status and try again.");
    } finally {
      await load();
      setBusy(false);
    }
  };

  const setCap = useCallback(
    async (accountId: string, value: string) => {
      setBusy(true);
      try {
        // An empty box means "no cap", not zero. They are different states and
        // the server treats them differently.
        const cap = value.trim() === "" ? 0 : Math.max(0, Number(value));
        await api.patch(`/distribution/accounts/${accountId}`, { daily_cap: cap });
        await load();
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "Could not set the cap", "error");
      } finally {
        setBusy(false);
      }
    },
    [load, notify]
  );

  const answer = useCallback(
    async (decision: "accept" | "dismiss") => {
      setBusy(true);
      try {
        const pending = automation?.pending_paces[postingId] ?? automation?.pending_pace;
        await api.post("/content-automation/pace", { decision, campaign_id: postingId, suggestion_id: pending?.suggestion_id });
        await load();
        notify(
          decision === "accept" ? "Rate changed." : "Left as it was.",
          decision === "accept" ? "success" : "info"
        );
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "Could not answer", "error");
      } finally {
        setBusy(false);
      }
    },
    [load, notify, automation, postingId]
  );

  const setMode = useCallback(
    async (mode: Automation["pace_mode"]) => {
      setBusy(true);
      try {
        setAutomation(await api.patch<Automation>("/content-automation", { pace_mode: mode }));
        await load();
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "Could not change that", "error");
      } finally {
        setBusy(false);
      }
    },
    [load, notify]
  );

  if (loading) {
    return <StatePanel tone="loading" title="Loading" description="Reading your posting settings." />;
  }
  if (error) {
    return (
      <StatePanel
        tone="error"
        title="Could not load this"
        description={error}
        action={<Button onClick={load}>Try again</Button>}
      />
    );
  }

  const pending = automation?.pending_paces[postingId] ?? automation?.pending_pace ?? {};
  const pair = automation?.pipelines.find(row => row.distribution_campaign_id === postingId);
  const waiting = typeof pending.suggested_per_day === "number" && pending.distribution_campaign_id === postingId;

  return (
    <>
      <PageHeader
        eyebrow="Posting"
        title="How much goes out"
        description="You set the ceiling. The engine works out the ideal rate and asks."
      />

      {actionError ? <StatePanel tone="error" title="Action needs attention" description={actionError} /> : null}
      <Panel title="Start a plan" subtitle="Apply your plan on Strategy first. Starting enables this plan's timer. Choose its work below; only approved, scheduled posts can go out.">
        <label>Posting campaign <select value={postingId} disabled={busy} onChange={event => selectCampaign(event.target.value)}>
          <option value="">Choose a posting campaign</option>
          {campaigns.filter(campaign => campaign.kind === "distribution").map(campaign => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
        </select></label>
        {pair?.plan_id ? <>
          <p>{automation?.enabled && pair.enabled !== false ? "Posting work is enabled. Both campaigns must stay active." : "This plan is waiting to start."} Keep its pictures on Image review before approving posts here.</p>
          <fieldset disabled={busy}><legend>Accounts for this plan</legend>
            {accounts.filter(account => account.enabled).map(account => <label key={account.id} style={{ display: "block" }}>
              <input type="checkbox" checked={selectedAccounts.includes(account.id)} onChange={event => setSelectedAccounts(previous => event.target.checked ? [...previous, account.id] : previous.filter(id => id !== account.id))} />
              {account.label || account.handle}
            </label>)}
          </fieldset>
          <Button disabled={busy || !selectedAccounts.length || !pair.posts_per_day} onClick={() => void act(async () => {
            await api.post(`/gtm/plans/${pair.plan_id}/start-posting`, { account_ids: selectedAccounts });
            refreshCampaigns();
          }, "Posting started. Review pictures and then drafted posts.")}>Start posting for this plan</Button>
          {!pair.posts_per_day ? <p>This plan has a zero posting rate. Revise and apply a plan with a positive daily rate.</p> : null}
          <p>Planning, drafting and publishing switches apply to every enabled plan.</p>
          {(["plan", "draft", "publish_due"] as const).map(step => <label key={step} style={{ display: "block" }}>
            <input type="checkbox" checked={automation?.[step] ?? false} disabled={busy} onChange={event => void act(() => api.patch("/content-automation", { [step]: event.target.checked }), "Posting step updated.")} />
            {step === "plan" ? "Plan pictures" : step === "draft" ? "Draft posts from kept pictures" : "Publish approved scheduled posts"}
          </label>)}
          <Button tone="ghost" disabled={busy} onClick={() => void act(() => api.post("/content-automation/run", {}), "Posting cycle finished. Check its status below.")}>Run posting cycle now</Button>
        </> : <p>Choose a campaign from an applied plan with both posting and picture channels. Apply a plan on Strategy to create the pair.</p>}
      </Panel>
      <Panel title="Connect a posting account" subtitle="Local outbox is the supported destination today. It saves posts on this install; it does not send to a social network.">
        <form onSubmit={event => { event.preventDefault(); void act(async () => {
          const account = await api.post<Account>("/distribution/accounts", { platform: "local_outbox", handle: handle.trim() });
          setSelectedAccounts(previous => [...new Set([...previous, account.id])]);
          setHandle("");
        }, "Local outbox account connected."); }}>
          <label>Account name <input required maxLength={200} value={handle} disabled={busy} onChange={event => setHandle(event.target.value)} /></label>
          <Button type="submit" disabled={busy || !handle.trim()}>Connect local outbox</Button>
        </form>
      </Panel>
      <DraftedPosts posts={posts} busy={busy} emptyAction={<Button disabled={busy} onClick={() => void load()}>Refresh drafted posts</Button>}
        onApprove={id => void act(async () => { await api.post(`/posts/${id}/approve`, {}); await api.post(`/posts/${id}/schedule-next`, {}); }, "Post approved and scheduled.")}
        onSkip={id => void act(() => api.post(`/posts/${id}/skip`, {}), "Post skipped. It will not be published.")}
        onSchedule={id => void act(() => api.post(`/posts/${id}/schedule-next`, {}), "Approved post scheduled.")} />
      {posts.length >= 200 ? <p>The queue shows up to 200 drafts and 200 approved posts. Refresh after reviewing to see the next posts.</p> : null}

      {automation?.last_error ? <StatePanel tone="error" title="Some posting work could not finish" description={automation.last_error} /> : null}

      {waiting ? (
        <Panel title="A suggestion is waiting" subtitle="Nothing has changed yet.">
          <p className="posting-rate">
            <strong>{pending.current_per_day?.toFixed(2)}</strong> → <strong>{pending.suggested_per_day?.toFixed(2)}</strong> posts a day
          </p>
          <p className="posting-reason">{pending.reason}</p>
          <div className="vinspector-actions">
            <Button busy={busy} onClick={() => void answer("accept")}>
              Use {pending.suggested_per_day?.toFixed(2)} a day
            </Button>
            <Button tone="ghost" busy={busy} onClick={() => void answer("dismiss")}>
              Not now
            </Button>
          </div>
        </Panel>
      ) : null}

      <Panel
        title="The rate"
        subtitle={`Running at ${(pair?.posts_per_day ?? automation?.posts_per_day ?? 0).toFixed(2)} posts a day`}
      >
        <p>These pacing permissions apply to every posting plan.</p>
        <ul className="posting-modes">
          {MODES.map((mode) => (
            <li key={mode.id}>
              <label>
                <input
                  type="radio"
                  name="pace_mode"
                  checked={automation?.pace_mode === mode.id}
                  disabled={busy}
                  onChange={() => void setMode(mode.id)}
                />
                <span>
                  <strong>{mode.label}</strong>
                  <em>{mode.note}</em>
                </span>
              </label>
            </li>
          ))}
        </ul>

        {pacing ? (
          <div className="posting-live">
            <p>
              <Badge tone={pacing.steering ? "info" : "neutral"}>
                {pacing.steering ? pacing.action : "holding"}
              </Badge>{" "}
              {pacing.capped_by ? `capped by ${pacing.capped_by}` : "nothing is capping it"}
            </p>
            <p className="posting-reason">{pacing.reason}</p>
          </div>
        ) : (
          <p className="vinspector-empty">
            Pick a distribution campaign to see what the engine would suggest for it.
          </p>
        )}
      </Panel>

      <Panel
        title="Your caps"
        subtitle="The most any one account may post in a day. Leave empty for no cap."
      >
        {!accounts.length ? (
          <StatePanel
            title="No accounts connected"
            description="Connect a handle to post to, and it will show up here with a cap you can set."
          />
        ) : (
          <ul className="posting-accounts">
            {accounts.map((account) => (
              <li key={account.id}>
                <div className="posting-who">
                  <strong>{account.label || account.handle}</strong>
                  <span>
                    {account.platform} · {account.handle}
                  </span>
                </div>
                <label className="posting-cap">
                  <span>posts a day</span>
                  <input
                    type="number"
                    min={0}
                    max={200}
                    placeholder="no cap"
                    defaultValue={account.daily_cap || ""}
                    disabled={busy}
                    onBlur={(event) => void setCap(account.id, event.target.value)}
                  />
                </label>
              </li>
            ))}
          </ul>
        )}
        <p className="vinspector-empty">
          A cap is never invented for you. With none set, the platform's own
          published limit is what binds — Instagram allows 25 a day, and nobody
          sane posts 25 a day.
        </p>
      </Panel>
    </>
  );
}
