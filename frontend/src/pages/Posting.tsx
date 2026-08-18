import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";

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

type Automation = {
  posts_per_day: number;
  pace_mode: "off" | "suggest" | "auto";
  pending_pace: {
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
  const { campaignId, notify } = useApp();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [pacing, setPacing] = useState<Pacing | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [connected, config] = await Promise.all([
        api.get<{ items: Account[] }>("/distribution/accounts"),
        api.get<Automation>("/content-automation")
      ]);
      setAccounts(connected.items);
      setAutomation(config);
      // The live suggestion needs a distribution campaign to pace against, and
      // there may not be one selected. Its absence is not an error.
      if (campaignId) {
        try {
          setPacing(await api.get<Pacing>(`/campaigns/${campaignId}/pacing`));
        } catch {
          setPacing(null);
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the posting settings");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    load();
  }, [load]);

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
        await api.post("/content-automation/pace", { decision });
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
    [load, notify]
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

  const pending = automation?.pending_pace ?? {};
  const waiting = typeof pending.suggested_per_day === "number";

  return (
    <>
      <PageHeader
        eyebrow="Posting"
        title="How much goes out"
        description="You set the ceiling. The engine works out the ideal rate and asks."
      />

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
        subtitle={`Running at ${(automation?.posts_per_day ?? 0).toFixed(2)} posts a day`}
      >
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
