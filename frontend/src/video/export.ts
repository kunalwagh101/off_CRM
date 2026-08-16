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
import { planMix } from "./mixdown";
import { frameAt } from "./resolve";
import { paintFrame, type AssetTable } from "./render";
import { WebMWriter } from "./webm";

/** Codecs tried in order. VP9 is smaller at the same quality; VP8 is universal. */
const CODECS = ["vp09.00.10.08", "vp8"];

/** A keyframe every two seconds, matching the muxer's cluster length. */
const KEYFRAME_SECONDS = 2;

export interface ExportProgress {
  frame: number;
  frames: number;
  stage: "mixing" | "encoding" | "flushing" | "muxing" | "uploading" | "done";
}

export interface ExportOptions {
  project: ProjectDoc;
  assets: AssetTable;
  /** Bits per second. 8 Mbps is generous for vertical social video. */
  bitrate?: number;
  /** Bits per second for the audio track. */
  audioBitrate?: number;
  /**
   * Where to fetch an asset's bytes from, for the audio mix. Without it the
   * export is silent — which is what it was before there was an audio track at
   * all, so leaving it out degrades rather than fails.
   */
  audioUrlFor?: (assetId: string) => string;
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

  const { project, assets, onProgress, signal } = options;
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

  // The sound is built first, because the muxer declares its tracks up front and
  // has to know whether there is one. It also fails fast: an unreadable music
  // file is better found before a thousand frames have been encoded.
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
  try {
    for (let index = 0; index < frames; index += 1) {
      if (signal?.aborted) throw new DOMException("Export cancelled", "AbortError");
      if (failure) throw failure;

      const tick = Math.round(index * perFrame);
      paintFrame(context, project, frameAt(project, tick), assets);

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
  }

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
  if (!options.audioUrlFor) {
    return {
      track: null,
      reason: "The exporter was given no way to fetch audio, so this file is silent."
    };
  }
  try {
    const track = await buildAudioTrack(plan, options.audioUrlFor, {
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
