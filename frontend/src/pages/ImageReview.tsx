import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import type { ImageAsset, ImageSummary } from "../types";

/**
 * The swipe.
 *
 * One picture at a time, three ways out: keep it, discard it, or ask for
 * another against the same brief. Those are the owner's quality judgements,
 * and they are the entire benchmark — every decision here scores the generator
 * that made the picture, and `ai/bandit.py` allocates the next batch on those
 * scores.
 *
 * Which is why the screen shows one candidate rather than a grid. A grid
 * invites picking a favourite and ignoring the rest, and "ignored" is not a
 * label. One at a time forces a verdict on each, and a verdict on each is what
 * the benchmark is made of.
 */
export default function ImageReview() {
  const { campaignId, notify } = useApp();
  const [queue, setQueue] = useState<ImageAsset[]>([]);
  const [summary, setSummary] = useState<ImageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!campaignId) return;
    setLoading(true);
    setError("");
    try {
      const [pending, stats] = await Promise.all([
        api.get<{ items: ImageAsset[] }>(`/campaigns/${campaignId}/image-queue`),
        api.get<ImageSummary>(`/campaigns/${campaignId}/image-summary`)
      ]);
      setQueue(pending.items);
      setSummary(stats);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the queue");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    load();
  }, [load]);

  const current = queue[0];

  const decide = useCallback(
    async (decision: "approve" | "reject" | "regenerate") => {
      if (!current || busy) return;
      setBusy(true);
      try {
        await api.post(`/image-assets/${current.id}/decide`, { decision });
        // Drop it locally so the next picture appears without a round trip,
        // then reconcile. A swipe that pauses is a swipe that gets skipped.
        setQueue((items) => items.slice(1));
        load();
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "That did not go through", "error");
      } finally {
        setBusy(false);
      }
    },
    [current, busy, load, notify]
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "ArrowRight") decide("approve");
      if (event.key === "ArrowLeft") decide("reject");
      if (event.key.toLowerCase() === "r") decide("regenerate");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide]);

  if (!campaignId) {
    return <StatePanel title="Pick a campaign" description="Choose an image campaign to review." />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Image campaign"
        title="Review"
        description="Keep it, discard it, or ask for another. Every decision scores the generator that made the picture."
        actions={<Button tone="ghost" onClick={load} busy={loading}>Refresh queue</Button>}
      />

      {summary ? (
        <Panel>
          <div className="mini-stats">
            <span><strong>{summary.assets.pending}</strong>waiting</span>
            <span><strong>{summary.assets.approved}</strong>kept</span>
            <span><strong>{summary.assets.rejected}</strong>discarded</span>
          </div>
          {summary.generators.length ? (
            <div className="card-meta">
              {summary.generators.map((row) => (
                <span key={`${row.provider_id}:${row.model_id}`}>
                  {row.model_id || row.provider_id}: {row.approval_rate}% kept
                  {row.decided < summary.min_decisions_to_judge ? " (too early to judge)" : ""}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">
              No decisions yet. After {summary.min_decisions_to_judge} per generator, off_CRM
              starts sending more work to whichever one you keep most often.
            </p>
          )}
        </Panel>
      ) : null}

      {error ? <StatePanel title="Could not load" description={error} /> : null}

      {!loading && !current && !error ? (
        <StatePanel
          title="Nothing waiting"
          description="Generate candidates against a brief, and they will appear here one at a time."
        />
      ) : null}

      {current ? (
        <Panel className="image-review">
          <div className="campaign-card-top">
            <Badge tone="neutral">{current.model_id || current.provider_id}</Badge>
            <Badge tone="neutral">{current.width}×{current.height}</Badge>
          </div>
          <img
            className="image-review-canvas"
            src={api.url(`/image-assets/${current.id}/file`)}
            alt="Generated candidate awaiting review"
          />
          <div className="card-actions">
            <Button tone="ghost" onClick={() => decide("reject")} busy={busy}>
              ← Discard
            </Button>
            <Button tone="ghost" onClick={() => decide("regenerate")} busy={busy}>
              ↻ Another
            </Button>
            <Button onClick={() => decide("approve")} busy={busy}>
              Keep →
            </Button>
          </div>
          <p className="muted">
            Arrow keys work too: ← discard, → keep, R for another. {queue.length - 1} more waiting.
          </p>
        </Panel>
      ) : null}
    </>
  );
}
