import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import type { Clip, ProjectDoc, ProjectState, RenderManifest } from "../video/document";
import { TICKS_PER_SECOND, formatTimecode, ticksPerFrame } from "../video/document";
import { frameAt, projectDuration } from "../video/resolve";
import { paintFrame, type AssetTable } from "../video/render";
import { ExportUnsupported, exportProject, exportSupport, loadAssets } from "../video/export";
import { FootageLibrary } from "../video/footage";

/**
 * The editor.
 *
 * Everything on this screen is a view of one document that lives on the server.
 * Nothing here changes a timeline directly: a drag becomes a named operation,
 * the server validates it and returns the new document, and the screen redraws
 * from that. It is slower than editing in place by exactly one round trip, and
 * it buys the property the whole feature rests on — there is one place that
 * decides whether an edit is legal, and it is the same place the export is
 * checked against.
 *
 * The preview is drawn by `video/render.ts` from a frame resolved by
 * `video/resolve.ts`, and the export uses those same two functions. A preview
 * painted by different code than the export is a preview that lies.
 */

const ZOOM_STEPS = [20, 40, 80, 160, 320, 640];
const TRACK_HEIGHT = 56;
/** Width of the sticky track header. Must match `.vtrack-head` in styles.css —
 *  the playhead and the click-to-scrub arithmetic are measured from its edge. */
const HEAD_WIDTH = 120;

type ImageAsset = { id: string; width: number; height: number; media_type: string; model_id: string };
type MediaItem = {
  id: string;
  name: string;
  kind: "audio" | "video";
  media_type: string;
  duration_ticks: number;
  has_audio: boolean;
};
type CaptionResult = {
  captions: number;
  too_fast: number;
  warnings: string[];
  reused_transcript: boolean;
  model_id: string;
};

export default function VideoEditor() {
  const { campaignId, notify } = useApp();
  const [projects, setProjects] = useState<Array<{ id: string; name: string; duration_ticks: number }>>([]);
  const [state, setState] = useState<ProjectState | null>(null);
  const [manifest, setManifest] = useState<RenderManifest | null>(null);
  const [assets, setAssets] = useState<ImageAsset[]>([]);
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [table, setTable] = useState<AssetTable>(new Map());
  const [selected, setSelected] = useState("");
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [zoom, setZoom] = useState(80);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<{ frame: number; frames: number; stage: string } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const footageRef = useRef<FootageLibrary | null>(null);
  /** Bumped when something off-screen changes what the canvas should show —
   *  a decoder opening, for one. */
  const [repaint, setRepaint] = useState(0);
  const support = useMemo(() => exportSupport(), []);

  const project = state?.document ?? null;
  const duration = project ? projectDuration(project) : 0;
  const pxPerTick = zoom / TICKS_PER_SECOND;

  // ── loading ───────────────────────────────────────────────────────────────

  const loadProjects = useCallback(async () => {
    if (!campaignId) return;
    setLoading(true);
    setError("");
    try {
      const [list, kept, imported] = await Promise.all([
        api.get<{ items: typeof projects }>(`/campaigns/${campaignId}/video-projects`),
        api.get<{ items: ImageAsset[] }>(`/campaigns/${campaignId}/image-assets?status=approved`),
        api.get<{ items: MediaItem[] }>(`/campaigns/${campaignId}/video-media`)
      ]);
      setProjects(list.items);
      setAssets(kept.items);
      setMedia(imported.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load projects");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const openProject = useCallback(async (projectId: string) => {
    setBusy(true);
    try {
      const next = await api.get<ProjectState>(`/video-projects/${projectId}`);
      setState(next);
      setSelected("");
      setPlayhead(0);
      setManifest(await api.get<RenderManifest>(`/video-projects/${projectId}/manifest`));
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Could not open the project", "error");
    } finally {
      setBusy(false);
    }
  }, [notify]);

  /** Which assets are drawable, as a value that only changes when the set does.
   *  `manifest` is a fresh object after every edit, and decoding a picture on
   *  each keystroke would make the editor slower the more it is used. */
  const assetKey = useMemo(
    () =>
      (manifest?.assets ?? [])
        .filter((item) => item.available && item.source === "image")
        .map((item) => item.id)
        .join(","),
    [manifest]
  );

  /** Decode every still the document needs, once, and keep it for drawing.
   *  Footage does not come through here — a picture decoder cannot open a video
   *  container, and a video's frame changes with the playhead where a still's
   *  never does. `footage.ts` handles those. */
  useEffect(() => {
    let live = true;
    const ids = assetKey ? assetKey.split(",") : [];
    loadAssets(ids, (id) => api.url(`/image-assets/${id}/file`)).then((loaded) => {
      if (live) setTable(loaded);
    });
    return () => {
      live = false;
    };
  }, [assetKey]);

  /** Which clips need footage, as a value that only changes when the set does —
   *  `project` is a fresh object after every edit, and re-demuxing a video on
   *  each nudge of a clip would make the editor unusable. */
  const footageKey = useMemo(
    () =>
      project
        ? FootageLibrary.needs(project)
            .map((item) => `${item.clipId}:${item.assetId}`)
            .join(",")
        : "",
    [project]
  );

  /** Open a decoder for every piece of footage on the timeline. */
  useEffect(() => {
    let live = true;
    footageRef.current?.close();
    footageRef.current = null;
    if (!footageKey) return;
    const needs = footageKey.split(",").map((pair) => {
      const [clipId, assetId] = pair.split(":");
      return { clipId, assetId };
    });
    FootageLibrary.load(needs, (id) => api.url(`/video-media/${id}/file`)).then((library) => {
      if (!live) {
        library.close();
        return;
      }
      footageRef.current = library;
      if (library.problems.length) {
        notify(`${library.problems[0].assetId}: ${library.problems[0].reason}`, "warning");
      }
      // Frames exist now that did not a moment ago, so the canvas is stale.
      setRepaint((value) => value + 1);
    });
    return () => {
      live = false;
      footageRef.current?.close();
      footageRef.current = null;
    };
  }, [footageKey, notify]);

  // ── editing ───────────────────────────────────────────────────────────────

  const edit = useCallback(
    async (op: string, params: Record<string, unknown>) => {
      if (!state) return null;
      setBusy(true);
      try {
        const next = await api.post<ProjectState>(`/video-projects/${state.id}/edit`, { op, params });
        setState(next);
        setManifest(await api.get<RenderManifest>(`/video-projects/${state.id}/manifest`));
        return next;
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "That edit was refused", "error");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [state, notify]
  );

  const step = useCallback(
    async (direction: "undo" | "redo") => {
      if (!state) return;
      setBusy(true);
      try {
        const next = await api.post<ProjectState>(`/video-projects/${state.id}/${direction}`, {});
        setState(next);
        setManifest(await api.get<RenderManifest>(`/video-projects/${state.id}/manifest`));
      } catch {
        notify(direction === "undo" ? "Nothing to undo" : "Nothing to redo", "info");
      } finally {
        setBusy(false);
      }
    },
    [state, notify]
  );

  // ── playback ──────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!playing || !project) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const advance = ((now - last) / 1000) * TICKS_PER_SECOND;
      last = now;
      setPlayhead((current) => {
        const next = current + advance;
        if (next >= duration) {
          setPlaying(false);
          return duration > 0 ? duration - 1 : 0;
        }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, project, duration]);

  /** Redraw whenever the document, the playhead or the decoded assets change.
   *
   *  Stills paint straight away. Footage cannot: a frame has to be decoded
   *  first, and by the time it arrives the playhead may have moved — so a
   *  superseded paint is dropped rather than drawn late, which is the
   *  difference between a preview that scrubs and one that appears to lag
   *  behind its own playhead. */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !project) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    canvas.width = project.width;
    canvas.height = project.height;
    const resolved = frameAt(project, Math.round(playhead));
    const library = footageRef.current;
    if (!library || !library.size) {
      paintFrame(context, project, resolved, table);
      return;
    }
    let live = true;
    // The table is a draw cache rather than a rendered value: `apply` puts this
    // instant's video frames into it in place, and this effect is the only
    // thing that reads it.
    library
      .apply(resolved, table)
      .catch(() => undefined)
      .then(() => {
        if (live) paintFrame(context, project, resolved, table);
      });
    return () => {
      live = false;
    };
  }, [project, playhead, table, repaint]);

  // ── keyboard ──────────────────────────────────────────────────────────────

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (!project) return;
      const frame = ticksPerFrame(project.fps);
      if (event.key === " ") {
        event.preventDefault();
        setPlaying((value) => !value);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        setPlayhead((value) => Math.min(duration - 1, value + (event.shiftKey ? frame * 10 : frame)));
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        setPlayhead((value) => Math.max(0, value - (event.shiftKey ? frame * 10 : frame)));
      } else if (event.key.toLowerCase() === "s" && selected) {
        edit("split_clip", { clip_id: selected, at: Math.round(playhead) });
      } else if ((event.key === "Delete" || event.key === "Backspace") && selected) {
        event.preventDefault();
        edit(event.shiftKey ? "ripple_delete" : "remove_clip", { clip_id: selected });
        setSelected("");
      } else if (event.key.toLowerCase() === "z" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        step(event.shiftKey ? "redo" : "undo");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [project, duration, selected, playhead, edit, step]);

  // ── dragging a clip ───────────────────────────────────────────────────────

  const dragClip = useCallback(
    (event: React.PointerEvent, clip: Clip, mode: "move" | "head" | "tail") => {
      event.preventDefault();
      event.stopPropagation();
      setSelected(clip.id);
      const originX = event.clientX;
      const element = (event.currentTarget as HTMLElement).closest(".vclip") as HTMLElement | null;
      const startLeft = clip.start * pxPerTick;
      const startWidth = clip.duration * pxPerTick;

      const onMove = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientX - originX;
        if (!element) return;
        // Move the element directly during the drag. Waiting for the server on
        // every pointer event would make dragging feel like a network graph.
        if (mode === "move") element.style.left = `${Math.max(0, startLeft + delta)}px`;
        if (mode === "head") {
          element.style.left = `${Math.max(0, startLeft + delta)}px`;
          element.style.width = `${Math.max(4, startWidth - delta)}px`;
        }
        if (mode === "tail") element.style.width = `${Math.max(4, startWidth + delta)}px`;
      };

      const onUp = async (upEvent: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        const deltaTicks = Math.round((upEvent.clientX - originX) / pxPerTick);
        if (Math.abs(deltaTicks) < 1) return;
        if (mode === "move") {
          await edit("move_clip", { clip_id: clip.id, start: Math.max(0, clip.start + deltaTicks) });
        } else if (mode === "head") {
          await edit("trim_clip", { clip_id: clip.id, head: deltaTicks });
        } else {
          await edit("trim_clip", { clip_id: clip.id, tail: -deltaTicks });
        }
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [pxPerTick, edit]
  );

  const refreshProject = useCallback(async () => {
    if (!state) return;
    setState(await api.get<ProjectState>(`/video-projects/${state.id}`));
    setManifest(await api.get<RenderManifest>(`/video-projects/${state.id}/manifest`));
  }, [state]);

  /** Bring in a voiceover or a clip, and drop it straight onto the timeline.
   *  Two steps rather than one because the file belongs to the campaign and the
   *  clip belongs to this project — the same recording can be used in several. */
  const importMedia = useCallback(
    async (file: File) => {
      if (!campaignId || !state) return;
      setBusy(true);
      try {
        const form = new FormData();
        form.append("file", file, file.name);
        const item = await api.upload<MediaItem>(`/campaigns/${campaignId}/video-media`, form);
        setMedia((current) => (current.some((row) => row.id === item.id) ? current : [item, ...current]));
        await api.post(`/video-projects/${state.id}/place-media`, { media_id: item.id });
        await refreshProject();
        notify(`Added ${item.name}`, "success");
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "That file was refused", "error");
      } finally {
        setBusy(false);
      }
    },
    [campaignId, state, refreshProject, notify]
  );

  const placeMedia = useCallback(
    async (mediaId: string) => {
      if (!state) return;
      setBusy(true);
      try {
        await api.post(`/video-projects/${state.id}/place-media`, {
          media_id: mediaId,
          start: Math.round(playhead)
        });
        await refreshProject();
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "Could not place that", "error");
      } finally {
        setBusy(false);
      }
    },
    [state, playhead, refreshProject, notify]
  );

  /** Transcribe the selected clip and lay the words out as text clips.
   *  The result is editable like anything else, which is the point: a
   *  transcript is a guess, and it goes out under your name. */
  const runCaptions = useCallback(
    async (clipId: string) => {
      if (!state) return;
      setBusy(true);
      try {
        const result = await api.post<CaptionResult>(`/video-projects/${state.id}/captions`, {
          clip_id: clipId
        });
        await refreshProject();
        const reused = result.reused_transcript ? " (transcript reused)" : "";
        notify(`${result.captions} captions from ${result.model_id}${reused}`, "success");
        if (result.warnings.length) notify(result.warnings[0], "warning");
      } catch (reason) {
        notify(reason instanceof Error ? reason.message : "Captions failed", "error");
      } finally {
        setBusy(false);
      }
    },
    [state, refreshProject, notify]
  );

  // ── export ────────────────────────────────────────────────────────────────

  const runExport = useCallback(async () => {
    if (!state || !project) return;
    if (!manifest?.renderable) {
      notify(manifest?.warnings[0] ?? "This project cannot be exported yet", "warning");
      return;
    }
    setBusy(true);
    setProgress({ frame: 0, frames: manifest.frames, stage: "encoding" });
    try {
      const result = await exportProject({
        project,
        assets: table,
        // Footage and audio both come from imported material, which is the
        // only store that serves whole files rather than pictures.
        mediaUrlFor: (id) => api.url(`/video-media/${id}/file`),
        onProgress: (value) => setProgress(value)
      });
      setProgress({ frame: manifest.frames, frames: manifest.frames, stage: "uploading" });
      const form = new FormData();
      form.append("file", result.blob, `${project.name || "export"}.webm`);
      form.append("renderer", result.renderer);
      const stored = await api.upload<{ passed: boolean; summary: string }>(
        `/video-projects/${state.id}/renders`,
        form
      );
      notify(
        stored.passed ? `Exported — ${stored.summary}` : `Export stored with problems: ${stored.summary}`,
        stored.passed ? "success" : "warning"
      );
      // Said separately from the gate result, and only when there is something
      // to say: a file that came out quieter or shorter of a track than the
      // timeline asked for is still a file, and the person who exported it is
      // the one who needs to know.
      if (result.footage.problems.length) {
        const first = result.footage.problems[0];
        notify(`${first.assetId} could not be drawn: ${first.reason}`, "warning");
      } else if (!result.audio.present && !manifest.mix.silent) {
        notify(result.audio.reason || "The export came out silent.", "warning");
      } else if (result.audio.missing.length) {
        notify(
          `${result.audio.missing.length} audio file(s) would not decode and are missing from the mix.`,
          "warning"
        );
      } else if (result.audio.limitedBy > 1) {
        notify(
          `The mix was turned down ${result.audio.limitedBy.toFixed(2)}× to stop it clipping.`,
          "info"
        );
      }
    } catch (reason) {
      const message =
        reason instanceof ExportUnsupported
          ? reason.message
          : reason instanceof Error
            ? reason.message
            : "The export failed";
      notify(message, "error");
    } finally {
      setProgress(null);
      setBusy(false);
    }
  }, [state, project, manifest, table, notify]);

  // ── screens ───────────────────────────────────────────────────────────────

  if (!campaignId) {
    return (
      <StatePanel
        title="Pick a campaign"
        description="A timeline belongs to an image campaign — the same one its pictures came from."
      />
    );
  }
  if (loading) return <StatePanel tone="loading" title="Loading" description="Fetching your projects." />;
  if (error) {
    return (
      <StatePanel
        tone="error"
        title="Could not load the editor"
        description={error}
        action={<Button onClick={loadProjects}>Try again</Button>}
      />
    );
  }

  if (!state || !project) {
    return (
      <>
        <PageHeader
          eyebrow="Video"
          title="Video editor"
          description="Cut the pictures this campaign generated into something that can be posted."
          actions={
            <Button
              busy={busy}
              onClick={async () => {
                const created = await api.post<ProjectState>(
                  `/campaigns/${campaignId}/video-projects`,
                  { name: `Reel ${projects.length + 1}`, preset: "vertical", fps: "30" }
                );
                await loadProjects();
                openProject(created.id);
              }}
            >
              New project
            </Button>
          }
        />
        <Panel title="Projects" subtitle={`${projects.length} in this campaign`}>
          {!projects.length ? (
            <StatePanel
              title="Nothing here yet"
              description="Make a project, then drop the pictures you kept onto its timeline."
            />
          ) : (
            <ul className="vproject-list">
              {projects.map((item) => (
                <li key={item.id}>
                  <button onClick={() => openProject(item.id)}>
                    <strong>{item.name}</strong>
                    <span>{formatTimecode(item.duration_ticks)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </>
    );
  }

  const selectedClip = selected
    ? project.tracks.flatMap((track) => track.clips).find((clip) => clip.id === selected) ?? null
    : null;

  return (
    <div className="veditor">
      <PageHeader
        eyebrow="Video"
        title={project.name}
        description={`${project.width}×${project.height} · ${project.fps}fps · ${formatTimecode(duration)}`}
        actions={
          <>
            <Button tone="ghost" onClick={() => setState(null)}>
              Projects
            </Button>
            <Button tone="ghost" disabled={!state.can_undo || busy} onClick={() => step("undo")}>
              Undo
            </Button>
            <Button tone="ghost" disabled={!state.can_redo || busy} onClick={() => step("redo")}>
              Redo
            </Button>
            <Button busy={busy} disabled={!support.supported} onClick={runExport}>
              Export
            </Button>
          </>
        }
      />

      {!support.supported ? (
        <p className="veditor-note" role="status">
          {support.reason}
        </p>
      ) : null}
      {manifest?.warnings.length ? (
        <p className="veditor-note veditor-warning" role="alert">
          {manifest.warnings.join(" ")}
        </p>
      ) : null}
      {manifest?.mix?.notes?.length ? (
        <p className="veditor-note" role="status">
          {manifest.mix.notes.join(" ")}
        </p>
      ) : null}
      {progress ? (
        <p className="veditor-note" role="status">
          {progress.stage === "encoding"
            ? `Encoding frame ${progress.frame} of ${progress.frames}`
            : progress.stage === "mixing"
              ? "Mixing the audio…"
              : `${progress.stage}…`}
        </p>
      ) : null}

      <div className="veditor-stage">
        <div className="veditor-preview">
          <canvas ref={canvasRef} style={{ aspectRatio: `${project.width} / ${project.height}` }} />
          <div className="veditor-transport">
            <Button tone="ghost" onClick={() => setPlaying((value) => !value)}>
              {playing ? "Pause" : "Play"}
            </Button>
            <span className="veditor-timecode">
              {formatTimecode(playhead)} / {formatTimecode(duration)}
            </span>
          </div>
        </div>

        <aside className="veditor-inspector">
          <Inspector
            clip={selectedClip}
            project={project}
            assets={assets}
            media={media}
            busy={busy}
            onEdit={edit}
            onImport={importMedia}
            onPlaceMedia={placeMedia}
            onCaption={runCaptions}
            onPlace={async (assetId) => {
              const next = await api.post<ProjectState>(`/video-projects/${state.id}/place-asset`, {
                asset_id: assetId,
                start: Math.round(playhead)
              });
              setState(next);
              setManifest(await api.get<RenderManifest>(`/video-projects/${state.id}/manifest`));
            }}
          />
        </aside>
      </div>

      <Panel
        title="Timeline"
        subtitle="Space plays · S splits · Delete removes · Shift+Delete closes the gap"
        action={
          <div className="veditor-zoom">
            <Button
              tone="ghost"
              onClick={() => setZoom(ZOOM_STEPS[Math.max(0, ZOOM_STEPS.indexOf(zoom) - 1)] ?? 20)}
            >
              −
            </Button>
            <Button
              tone="ghost"
              onClick={() =>
                setZoom(ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, ZOOM_STEPS.indexOf(zoom) + 1)] ?? 640)
              }
            >
              +
            </Button>
          </div>
        }
      >
        <div
          className="vtimeline"
          onPointerDown={(event) => {
            const bounds = event.currentTarget.getBoundingClientRect();
            const at =
              (event.clientX - bounds.left + event.currentTarget.scrollLeft - HEAD_WIDTH) / pxPerTick;
            setPlayhead(Math.max(0, Math.min(duration, at)));
          }}
        >
          <div className="vtimeline-inner" style={{ width: `${Math.max(600, duration * pxPerTick + 240)}px` }}>
            <div className="vplayhead" style={{ left: `${HEAD_WIDTH + playhead * pxPerTick}px` }} />
            {project.markers.map((marker) => (
              <div
                key={marker.id}
                className="vmarker"
                style={{ left: `${HEAD_WIDTH + marker.at * pxPerTick}px`, background: marker.colour || "#ffcc00" }}
                title={marker.label}
              />
            ))}
            {project.tracks.map((track) => (
              <div className="vtrack" key={track.id} style={{ height: TRACK_HEIGHT }}>
                <div className="vtrack-head">
                  <strong>{track.name || track.kind}</strong>
                  <div>
                    <button
                      title={track.hidden ? "Show" : "Hide"}
                      onClick={() => edit("set_track", { track_id: track.id, hidden: !track.hidden })}
                    >
                      {track.hidden ? "◌" : "◉"}
                    </button>
                    <button
                      title={track.muted ? "Unmute" : "Mute"}
                      onClick={() => edit("set_track", { track_id: track.id, muted: !track.muted })}
                    >
                      {track.muted ? "⊘" : "♪"}
                    </button>
                    <button
                      title={track.locked ? "Unlock" : "Lock"}
                      onClick={() => edit("set_track", { track_id: track.id, locked: !track.locked })}
                    >
                      {track.locked ? "🔒" : "🔓"}
                    </button>
                  </div>
                </div>
                <div className="vtrack-lane">
                  {track.clips.map((clip) => (
                    <div
                      key={clip.id}
                      className={`vclip vclip-${clip.kind} ${selected === clip.id ? "vclip-selected" : ""}`}
                      style={{ left: `${clip.start * pxPerTick}px`, width: `${clip.duration * pxPerTick}px` }}
                      onPointerDown={(event) => dragClip(event, clip, "move")}
                    >
                      <span
                        className="vclip-handle vclip-head"
                        onPointerDown={(event) => dragClip(event, clip, "head")}
                      />
                      <span className="vclip-label">{clip.label || clip.text || clip.kind}</span>
                      <span
                        className="vclip-handle vclip-tail"
                        onPointerDown={(event) => dragClip(event, clip, "tail")}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="veditor-tracks-actions">
          <Button tone="ghost" onClick={() => edit("add_track", { kind: "video" })}>
            Add video track
          </Button>
          <Button tone="ghost" onClick={() => edit("add_track", { kind: "audio" })}>
            Add audio track
          </Button>
          <Button tone="ghost" onClick={() => edit("add_marker", { at: Math.round(playhead), label: "mark" })}>
            Marker here
          </Button>
        </div>
      </Panel>
    </div>
  );
}

/** The right-hand column: what is selected, and what can be added. */
function Inspector({
  clip,
  project,
  assets,
  media,
  busy,
  onEdit,
  onPlace,
  onImport,
  onPlaceMedia,
  onCaption
}: {
  clip: Clip | null;
  project: ProjectDoc;
  assets: ImageAsset[];
  media: MediaItem[];
  busy: boolean;
  onEdit: (op: string, params: Record<string, unknown>) => Promise<unknown>;
  onPlace: (assetId: string) => Promise<void>;
  onImport: (file: File) => Promise<void>;
  onPlaceMedia: (mediaId: string) => Promise<void>;
  onCaption: (clipId: string) => Promise<void>;
}) {
  const videoTrack = project.tracks.find((track) => track.kind === "video" && !track.locked);
  const end = project.tracks.flatMap((track) => track.clips).reduce((last, item) => Math.max(last, item.start + item.duration), 0);

  if (!clip) {
    return (
      <Panel title="Add" subtitle="Pictures you kept, and the layers that go over them">
        <div className="vinspector-actions">
          <Button
            tone="ghost"
            disabled={!videoTrack || busy}
            onClick={() =>
              onEdit("add_clip", {
                track_id: videoTrack?.id,
                kind: "text",
                start: end,
                duration: 3 * TICKS_PER_SECOND,
                text: "Your caption",
                style: { size: 84, colour: "#ffffff", stroke: 6, align: "center" }
              })
            }
          >
            Text
          </Button>
          <Button
            tone="ghost"
            disabled={!videoTrack || busy}
            onClick={() =>
              onEdit("add_clip", {
                track_id: videoTrack?.id,
                kind: "solid",
                start: end,
                duration: 2 * TICKS_PER_SECOND,
                style: { colour: "#101014" }
              })
            }
          >
            Colour
          </Button>
        </div>
        <ul className="vasset-grid">
          {assets.map((asset) => (
            <li key={asset.id}>
              <button disabled={busy} onClick={() => onPlace(asset.id)} title={asset.model_id}>
                <img src={api.url(`/image-assets/${asset.id}/file`)} alt="" loading="lazy" />
              </button>
            </li>
          ))}
        </ul>
        {!assets.length ? (
          <p className="vinspector-empty">
            No kept pictures yet. Generate some in Image review and swipe right on the ones you want.
          </p>
        ) : null}

        <div className="vinspector-divider" />
        <p className="vinspector-heading">Sound</p>
        <p className="vinspector-empty">
          Nothing here generates speech, so captions need a recording. Add a voiceover
          or a clip and its words can be laid out on the timeline.
        </p>
        <label className={`vupload ${busy ? "vupload-busy" : ""}`}>
          <input
            type="file"
            accept="audio/*,video/*"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void onImport(file);
            }}
          />
          <span>Add audio or video</span>
        </label>
        {media.length ? (
          <ul className="vmedia-list">
            {media.map((item) => (
              <li key={item.id}>
                <button disabled={busy} onClick={() => void onPlaceMedia(item.id)}>
                  <strong>{item.name || item.kind}</strong>
                  <span>
                    {item.kind} · {formatTimecode(item.duration_ticks)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </Panel>
    );
  }

  const hasSound = clip.kind === "video" || clip.kind === "audio";

  return (
    <Panel title="Clip" subtitle={`${clip.kind} · ${formatTimecode(clip.duration)}`}>
      <div className="vinspector-row">
        <Badge tone="neutral">{clip.label || clip.kind}</Badge>
      </div>
      {hasSound ? (
        <>
          <Button disabled={busy} onClick={() => void onCaption(clip.id)}>
            Auto captions
          </Button>
          <p className="vinspector-empty">
            Transcribes this clip and lays the words out as text clips you can edit.
            Read them before anything goes out — a transcript is a guess.
          </p>
          <div className="vinspector-divider" />
        </>
      ) : null}
      {clip.kind === "text" ? (
        <label className="vinspector-field">
          <span>Text</span>
          <textarea
            defaultValue={clip.text}
            rows={3}
            onBlur={(event) => onEdit("set_text", { clip_id: clip.id, text: event.target.value })}
          />
        </label>
      ) : null}
      {(
        [
          ["scale", "Scale", 0.1, 4, 0.01],
          ["x", "Position X", -1200, 1200, 1],
          ["y", "Position Y", -1200, 1200, 1],
          ["rotation", "Rotation", -180, 180, 1],
          ["opacity", "Opacity", 0, 1, 0.01],
          ["brightness", "Brightness", -1, 1, 0.01],
          ["saturation", "Saturation", -1, 1, 0.01]
        ] as const
      ).map(([name, label, min, max, stepSize]) => (
        <label className="vinspector-field" key={name}>
          <span>{label}</span>
          <input
            type="range"
            min={min}
            max={max}
            step={stepSize}
            defaultValue={clip.properties[name] ?? (name === "scale" || name === "opacity" ? 1 : 0)}
            onMouseUp={(event) =>
              onEdit("set_property", {
                clip_id: clip.id,
                name,
                value: Number((event.target as HTMLInputElement).value)
              })
            }
          />
        </label>
      ))}
      <div className="vinspector-actions">
        <Button
          tone="ghost"
          disabled={busy}
          onClick={() =>
            onEdit("set_fade", {
              clip_id: clip.id,
              fade_in: Math.min(TICKS_PER_SECOND / 2, Math.floor(clip.duration / 4)),
              fade_out: Math.min(TICKS_PER_SECOND / 2, Math.floor(clip.duration / 4))
            })
          }
        >
          Fade both ends
        </Button>
        <Button tone="ghost" disabled={busy} onClick={() => onEdit("duplicate_clip", { clip_id: clip.id })}>
          Duplicate
        </Button>
        <Button tone="ghost" disabled={busy} onClick={() => onEdit("reset_properties", { clip_id: clip.id })}>
          Reset
        </Button>
      </div>
    </Panel>
  );
}
