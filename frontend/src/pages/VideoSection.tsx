import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../components";
import { useApp } from "../context";
import { formatTimecode } from "../video/document";
import type { VideoProjectRow, VideoSummary } from "../types";

/**
 * The video editor's section of the command centre.
 *
 * A timeline belongs to an image campaign — the same one its pictures came
 * from — so this panel follows the campaign switcher rather than showing a
 * workspace-wide total that would mean nothing.
 *
 * When the active campaign is a different kind, it says so and offers the way
 * across, rather than showing an error or an empty state. A campaign of the
 * wrong kind is not a failure, it is simply a campaign that does not have
 * video in it.
 */
export default function VideoSection() {
  const { campaignId, activeCampaign } = useApp();
  const [summary, setSummary] = useState<VideoSummary | null>(null);
  const [projects, setProjects] = useState<VideoProjectRow[]>([]);
  const [loading, setLoading] = useState(false);
  const isImageCampaign = activeCampaign?.kind === "image";

  const load = useCallback(async () => {
    if (!campaignId || !isImageCampaign) {
      setSummary(null);
      setProjects([]);
      return;
    }
    setLoading(true);
    try {
      const [stats, list] = await Promise.all([
        api.get<VideoSummary>(`/campaigns/${campaignId}/video-summary`),
        api.get<{ items: VideoProjectRow[] }>(`/campaigns/${campaignId}/video-projects`)
      ]);
      setSummary(stats);
      setProjects(list.items);
    } catch {
      // A dashboard panel that cannot load is a quiet empty state, not an
      // alert over the whole page. The editor itself reports its own errors.
      setSummary(null);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [campaignId, isImageCampaign]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isImageCampaign) {
    return (
      <Panel
        title="Video"
        subtitle="Cut generated pictures into something postable"
        className="video-section"
      >
        <p className="muted">
          Video lives in image campaigns, alongside the pictures it is cut from.
          {activeCampaign
            ? ` “${activeCampaign.name}” is an ${activeCampaign.kind} campaign.`
            : ""}
        </p>
        <Button tone="secondary" onClick={() => (window.location.hash = "campaigns")}>
          Switch campaign
        </Button>
      </Panel>
    );
  }

  const minutes = summary ? summary.total_duration_seconds / 60 : 0;

  return (
    <Panel
      title="Video"
      subtitle="Cut generated pictures into something postable"
      className="video-section"
      action={
        <Button tone="secondary" onClick={() => (window.location.hash = "videoeditor")}>
          Open editor
        </Button>
      }
    >
      <div className="video-figures">
        <span>
          <strong>{summary?.projects ?? 0}</strong>
          <small>timelines</small>
        </span>
        <span>
          <strong>{minutes >= 1 ? `${minutes.toFixed(1)}m` : `${(summary?.total_duration_seconds ?? 0).toFixed(0)}s`}</strong>
          <small>edited</small>
        </span>
        <span>
          <strong>{summary?.renders_passed ?? 0}</strong>
          <small>exports ready</small>
        </span>
        {summary?.renders_failed ? (
          <span className="video-figure-warn">
            <strong>{summary.renders_failed}</strong>
            <small>failed their gates</small>
          </span>
        ) : null}
      </div>

      {loading && !projects.length ? <p className="muted">Loading…</p> : null}

      {projects.length ? (
        <ul className="video-project-rows">
          {projects.slice(0, 4).map((project) => (
            <li key={project.id}>
              <button onClick={() => (window.location.hash = "videoeditor")}>
                <span className="video-project-main">
                  <strong>{project.name}</strong>
                  <small>
                    {project.width}×{project.height} · {project.fps}fps
                  </small>
                </span>
                <span className="video-project-length">{formatTimecode(project.duration_ticks)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : !loading ? (
        <p className="muted">
          No timelines yet. Keep some pictures in Image review, then open the editor and
          drop them on a timeline.
        </p>
      ) : null}

      <div className="principle-card">
        <strong>Captions are a draft</strong>
        <p>
          Auto-captions come out as editable text clips. A transcript is a guess, and it
          goes out under your name — read it before you publish.
        </p>
      </div>
    </Panel>
  );
}
