/**
 * Turning a timeline into a file, in the browser.
 *
 * Every frame is painted onto a canvas by the same function the preview uses,
 * handed to a `VideoEncoder`, and muxed into WebM by `webm.ts`. The server then
 * checks the result against the project it claims to be a render of — shape,
 * length, and whether it muxed a video track at all.
 *
 * **WebCodecs is required, and there is no fallback.** The obvious fallback is
 * `MediaRecorder` on a captured canvas stream, and it was left out on purpose.
 * It records in real time, so a two-minute video takes two minutes; it drops
 * frames when the tab is busy, silently; and it writes a WebM with no Duration
 * field, because a streaming muxer does not know the length in advance. That
 * last one means the export gate could never do the check it exists to do. A
 * fallback whose output cannot be verified is not a fallback, it is a quieter
 * failure — so an old browser is told plainly what it needs instead.
 */

import { AudioUnsupported, buildAudioTrack, type AudioTrackResult } from "./audio";
import type { ProjectDoc } from "./document";
import { TICKS_PER_SECOND, ticksPerFrame } from "./document";
import { FootageLibrary } from "./footage";
import { planMix } from "./mixdown";
import { frameAt } from "./resolve";
import { paintFrame, type AssetTable, type PixelStage } from "./render";
import type { EffectTable } from "./effects";
import { EffectPipeline } from "./shaders/pipeline";
import { WebMWriter } from "./webm";

/** Codecs tried in order. VP9 is smaller at the same quality; VP8 is universal. */
const CODECS = ["vp09.00.10.08", "vp8"];

/** A keyframe every two seconds, matching the muxer's cluster length. */
const KEYFRAME_SECONDS = 2;

export interface ExportProgress {
  frame: number;
  frames: number;
  stage: "loading" | "mixing" | "encoding" | "flushing" | "muxing" | "uploading" | "done";
}

export interface ExportOptions {
  project: ProjectDoc;
  assets: AssetTable;
  /** Bits per second. 8 Mbps is generous for vertical social video. */
  bitrate?: number;
  /** Bits per second for the audio track. */
  audioBitrate?: number;
  /**
   * Where to fetch an imported file's bytes from. Used for both halves of a
   * piece of footage — its sound, which `decodeAudioData` reads out, and its
   * picture, which `footage.ts` demuxes and decodes. Without it the export is
   * silent and its footage draws as a hole, which is what it did before either
   * existed, so leaving it out degrades rather than fails.
   */
  mediaUrlFor?: (assetId: string) => string;
  /**
   * Each clip's effect chain, resolved by the server, from the manifest.
   *
   * Left out, the export draws unfiltered — which is exactly what it did before
   * effects existed, so an old caller degrades rather than breaks.
   */
  effects?: EffectTable;
  onProgress?: (progress: ExportProgress) => void;
  signal?: AbortSignal;
}

export interface ExportResult {
  blob: Blob;
  renderer: string;
  frames: number;
  codec: string;
  durationMs: number;
  /** What happened to the sound, in words the export screen can show. */
  audio: {
    /** Whether the file has an audio track at all. */
    present: boolean;
    /** Why not, when it does not. Empty when it does. */
    reason: string;
    /** How far the mix was turned down to stay under clipping, or 1. */
    limitedBy: number;
    /** Assets that would not decode; their clips are missing from the mix. */
    missing: string[];
  };
  /** What happened to the footage. */
  footage: {
    /** How many video clips drew real frames. */
    drawn: number;
    /** Files that would not demux or decode; their clips drew as holes. */
    problems: Array<{ assetId: string; reason: string }>;
  };
  /** What happened to the filters. */
  effects: {
    /** Whether the GPU stage ran at all. False on a machine with no WebGL2. */
    accelerated: boolean;
    /** Full-screen draws the last frame cost. Zero when nothing is filtered. */
    passes: number;
    /** `[clipId, whatWasLost]` for clips the fallback could not draw fully. */
    losses: Array<[string, string[]]>;
    /** Primitives whose shader would not compile here. */
    problems: Array<{ primitive: string; reason: string }>;
  };
}

export class ExportUnsupported extends Error {}

interface VideoEncoderLike {
  encode(frame: unknown, options?: { keyFrame?: boolean }): void;
  flush(): Promise<void>;
  close(): void;
  configure(config: Record<string, unknown>): void;
  readonly encodeQueueSize: number;
}

interface WebCodecsWindow {
  VideoEncoder?: {
    new (init: {
      output: (chunk: never, metadata?: unknown) => void;
      error: (error: Error) => void;
    }): VideoEncoderLike;
    isConfigSupported(config: Record<string, unknown>): Promise<{ supported?: boolean }>;
  };
  VideoFrame?: new (source: CanvasImageSource, init: { timestamp: number; duration?: number }) => {
    close(): void;
  };
}

/** Whether this browser can export at all, and what to say when it cannot. */
export function exportSupport(): { supported: boolean; reason: string } {
  const scope = globalThis as unknown as WebCodecsWindow;
  if (!scope.VideoEncoder || !scope.VideoFrame) {
    return {
      supported: false,
      reason:
        "This browser has no WebCodecs, so it cannot encode video. Chrome, Edge " +
        "and Safari 16.4 or newer can. Everything else in the editor works — " +
        "only the export needs it."
    };
  }
  return { supported: true, reason: "" };
}

async function pickCodec(width: number, height: number, bitrate: number): Promise<string> {
  const scope = globalThis as unknown as WebCodecsWindow;
  const encoder = scope.VideoEncoder;
  if (!encoder) throw new ExportUnsupported(exportSupport().reason);
  for (const codec of CODECS) {
    try {
      const answer = await encoder.isConfigSupported({ codec, width, height, bitrate });
      if (answer?.supported) return codec;
    } catch {
      // An encoder that throws on a config is an encoder that does not have it.
    }
  }
  throw new ExportUnsupported(
    "This browser encodes neither VP9 nor VP8, which are the two codecs a WebM " +
      "file can carry."
  );
}

/**
 * Render every frame of the project and return the finished file.
 *
 * Frame times come from the tick clock, not from an accumulating float: frame
 * *n* is at `round(n * ticksPerFrame)` and nothing is ever added to a running
 * total. At 29.97fps an accumulator drifts by a frame every few minutes, and
 * the drift lands in the timestamps, where it turns into audio sync error.
 */
export async function exportProject(options: ExportOptions): Promise<ExportResult> {
  const support = exportSupport();
  if (!support.supported) throw new ExportUnsupported(support.reason);

  const { project, assets, effects, onProgress, signal } = options;
  const bitrate = options.bitrate ?? 8_000_000;
  const duration = project.duration;
  if (duration <= 0) {
    throw new Error("This timeline is empty. There is nothing to export.");
  }

  const perFrame = ticksPerFrame(project.fps);
  const frames = Math.max(1, Math.floor(duration / perFrame));
  const fps = TICKS_PER_SECOND / perFrame;
  const keyEvery = Math.max(1, Math.round(fps * KEYFRAME_SECONDS));
  const codec = await pickCodec(project.width, project.height, bitrate);

  const canvas =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(project.width, project.height)
      : Object.assign(document.createElement("canvas"), {
          width: project.width,
          height: project.height
        });
  const context = (canvas as HTMLCanvasElement).getContext("2d", {
    alpha: false
  }) as CanvasRenderingContext2D | null;
  if (!context) throw new Error("This browser would not give the exporter a 2D canvas.");

  // Footage first: demuxing a file that turns out to be unreadable is better
  // found now than a thousand frames into an encode.
  const needs = FootageLibrary.needs(project);
  let footage: FootageLibrary | null = null;
  const footageReport = { drawn: 0, problems: [] as Array<{ assetId: string; reason: string }> };
  if (needs.length && options.mediaUrlFor) {
    onProgress?.({ frame: 0, frames, stage: "loading" });
    footage = await FootageLibrary.load(needs, options.mediaUrlFor);
    // Read now rather than at the end: the library is closed in the `finally`
    // below, and a closed one has no clips to count.
    footageReport.drawn = needs.filter((item) => footage!.has(item.clipId)).length;
    footageReport.problems = footage.problems;
  }

  // Then the sound, because the muxer declares its tracks up front and has to
  // know whether there is one.
  onProgress?.({ frame: 0, frames, stage: "mixing" });
  const sound = await buildSound(project, options);
  if (signal?.aborted) throw new DOMException("Export cancelled", "AbortError");

  const writer = new WebMWriter({
    width: project.width,
    height: project.height,
    videoCodec: codec,
    durationMs: (duration / TICKS_PER_SECOND) * 1000,
    audio: sound.track
      ? {
          codec: sound.track.codec,
          sampleRate: sound.track.sampleRate,
          channels: sound.track.channels,
          description: sound.track.description
        }
      : undefined
  });
  for (const chunk of sound.track?.chunks ?? []) writer.addAudio(chunk);

  const scope = globalThis as unknown as WebCodecsWindow;
  let failure: Error | null = null;
  const encoder = new scope.VideoEncoder!({
    output: (chunk) => writer.addVideo(chunk as never),
    error: (error) => {
      failure = error;
    }
  });
  encoder.configure({
    codec,
    width: project.width,
    height: project.height,
    bitrate,
    framerate: fps,
    latencyMode: "quality"
  });

  const frameDurationUs = Math.round(1_000_000 / fps);
  // One pipeline for the whole export. Building one per frame would recompile
  // every shader six hundred times for a twenty-second video.
  const pipeline = EffectPipeline.create();
  const stage: PixelStage = { pipeline, effects, seed: 0, losses: [] };
  const losses = new Map<string, string[]>();
  try {
    for (let index = 0; index < frames; index += 1) {
      if (signal?.aborted) throw new DOMException("Export cancelled", "AbortError");
      if (failure) throw failure;

      const tick = Math.round(index * perFrame);
      const resolved = frameAt(project, tick);
      // Ticks only ever go up here, so every footage decoder runs forwards and
      // decodes each frame exactly once — the same work the file already is.
      // Resolved again half an output frame later, because this frame covers
      // the interval up to the next one and the middle of that interval is what
      // represents it. A second resolution rather than an offset added to a
      // source time: a reversed clip runs backwards and a curved one runs at a
      // rate that changes. See `FootageLibrary.apply`.
      if (footage) {
        await footage.apply(resolved, assets, frameAt(project, tick + Math.floor(perFrame / 2)));
      }
      // The seed is the frame index, never the clock. Grain that changed
      // between a preview and an export would be two different videos, and a
      // re-export has to produce the file it produced yesterday.
      stage.seed = index;
      stage.losses = [];
      paintFrame(context, project, resolved, assets, undefined, stage);
      if (stage.losses.length) {
        for (const entry of stage.losses) losses.set(entry[0], entry[1]);
      }

      const videoFrame = new scope.VideoFrame!(canvas as CanvasImageSource, {
        timestamp: Math.round((tick / TICKS_PER_SECOND) * 1_000_000),
        duration: frameDurationUs
      });
      encoder.encode(videoFrame, { keyFrame: index % keyEvery === 0 });
      videoFrame.close();

      // Encoding is asynchronous and painting is not, so without this the loop
      // fills the encoder's queue with a whole video's worth of frames and the
      // tab runs out of memory on anything long.
      while (encoder.encodeQueueSize > 8) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      onProgress?.({ frame: index + 1, frames, stage: "encoding" });
    }

    onProgress?.({ frame: frames, frames, stage: "flushing" });
    await encoder.flush();
    if (failure) throw failure;
  } finally {
    try {
      encoder.close();
    } catch {
      // Closing an encoder that already errored is not itself a problem.
    }
    // Every decoded frame is a GPU buffer, and a render that threw halfway
    // still has to give them back.
    footage?.close();
  }

  const effectPasses = Object.values(effects ?? {}).reduce(
    (total: number, chain) => total + chain.reduce((sum, item) => sum + (item.passes || 1), 0),
    0
  );
  // The GPU context and every compiled program go back now rather than when the
  // garbage collector gets round to it. A browser gives a tab a small number of
  // WebGL contexts, and an editor that exports twenty times in a session runs
  // out of them long before it runs out of memory.
  pipeline?.dispose();
  onProgress?.({ frame: frames, frames, stage: "muxing" });
  const blob = writer.blob();
  onProgress?.({ frame: frames, frames, stage: "done" });
  return {
    blob,
    renderer: `webcodecs/${codec}${sound.track ? "+opus" : ""}`,
    frames: writer.frameCount,
    codec,
    durationMs: (duration / TICKS_PER_SECOND) * 1000,
    audio: {
      present: Boolean(sound.track),
      reason: sound.reason,
      limitedBy: sound.track?.limitedBy ?? 1,
      missing: sound.track?.missing ?? []
    },
    footage: footageReport,
    effects: {
      accelerated: Boolean(pipeline),
      passes: effectPasses,
      losses: [...losses.entries()],
      problems: pipeline ? [...pipeline.problems] : []
    }
  };
}

/**
 * The audio track, or an explanation of why there isn't one.
 *
 * Everything here degrades rather than throws. A browser too old to encode
 * Opus, a music file that will not decode, a caller that gave no way to fetch
 * assets — none of those should cost someone their whole render. What they must
 * not do is happen silently, so each one comes back as a sentence the export
 * screen can put on the page.
 */
async function buildSound(
  project: ProjectDoc,
  options: ExportOptions
): Promise<{ track: AudioTrackResult | null; reason: string }> {
  const plan = planMix(project);
  if (plan.silent) {
    return { track: null, reason: "Nothing on this timeline makes a sound." };
  }
  if (!options.mediaUrlFor) {
    return {
      track: null,
      reason: "The exporter was given no way to fetch audio, so this file is silent."
    };
  }
  try {
    const track = await buildAudioTrack(plan, options.mediaUrlFor, {
      bitrate: options.audioBitrate
    });
    if (!track) {
      return { track: null, reason: "None of this project's audio could be decoded." };
    }
    return { track, reason: "" };
  } catch (error) {
    if (error instanceof AudioUnsupported) return { track: null, reason: error.message };
    throw error;
  }
}

/**
 * Fetch and decode every asset a project needs.
 *
 * Decoded once and held, because a five-second still at 30fps is a hundred and
 * fifty draws of the same picture and decoding it each time is the difference
 * between an export that takes seconds and one that takes minutes.
 */
export async function loadAssets(
  assetIds: string[],
  urlFor: (id: string) => string
): Promise<AssetTable> {
  const table: AssetTable = new Map();
  await Promise.all(
    assetIds.map(async (id) => {
      const response = await fetch(urlFor(id), { credentials: "same-origin" });
      if (!response.ok) return;
      const blob = await response.blob();
      const bitmap = await createImageBitmap(blob);
      table.set(id, { source: bitmap, width: bitmap.width, height: bitmap.height });
    })
  );
  return table;
}
