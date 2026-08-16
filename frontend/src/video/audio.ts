/**
 * Turning a mix plan into an Opus track.
 *
 * Three steps, deliberately separate so only the middle one needs a browser:
 *
 * 1. `placements()` turns the plan into a list of "play this buffer, here, at
 *    this rate, with this gain shape". Pure arithmetic, and the place a bug
 *    would actually live — the conversion between *timeline* time and *source*
 *    time is not the identity as soon as a clip's speed is not 1.
 * 2. `renderMix()` wires those into an `OfflineAudioContext` and lets the
 *    browser do the resampling and summing, faster than real time.
 * 3. `encodeAudio()` hands the result to `AudioEncoder` in 20ms frames and
 *    collects Opus chunks for the muxer.
 *
 * **On clipping.** Two clips at full volume sum past 1.0 and the samples wrap
 * into a rasp that no amount of later mastering removes. `planMix` already
 * reports the worst-case sum, so the whole mix is scaled by its reciprocal when
 * it exceeds one. That is uniform, so the balance between clips is untouched;
 * it is reported back as `limitedBy` so the export can say the mix was turned
 * down rather than quietly changing how loud someone's video is.
 *
 * **On the OpusHead.** WebCodecs usually hands over a decoder description with
 * the first chunk, and a WebM with no CodecPrivate on its Opus track is a file
 * some demuxers refuse. One is written here when the encoder does not supply
 * one, because the structure is nineteen fixed bytes and guessing is not
 * involved.
 */

import { TICKS_PER_SECOND } from "./document";
import type { MixClip, MixPlan } from "./mixdown";

/** 20ms at 48kHz — Opus's natural frame, and what every encoder prefers. */
const FRAME_SAMPLES = 960;

/** Enough for speech and music at 48kHz stereo without thinking about it. */
export const AUDIO_BITRATE = 128_000;

/** Opus always reports 48kHz regardless of what went in. */
const OPUS_PRE_SKIP = 3840;

export interface GainRamp {
  /** Absolute seconds on the output timeline. */
  at: number;
  gain: number;
}

export interface SourcePlacement {
  clipId: string;
  assetId: string;
  /** When to start playing, in output seconds. */
  when: number;
  /** Where to start reading, in *source* seconds. */
  offset: number;
  /** How much source to read, in *source* seconds. */
  duration: number;
  playbackRate: number;
  /** First entry is set outright; the rest are ramped to. */
  ramps: GainRamp[];
}

export interface AudioTrackResult {
  chunks: EncodedAudioChunkLike[];
  description?: Uint8Array;
  sampleRate: number;
  channels: number;
  codec: string;
  /** How far the whole mix was turned down to stay under clipping, or 1. */
  limitedBy: number;
  /** Assets that would not decode. The export continues without them. */
  missing: string[];
}

export interface EncodedAudioChunkLike {
  timestamp: number;
  byteLength: number;
  copyTo(target: Uint8Array): void;
}

export class AudioUnsupported extends Error {}

/**
 * Where every clip plays and how loud, in the units WebAudio wants.
 *
 * A clip's `speed` is how much source it consumes per tick of timeline, which
 * is exactly what `playbackRate` means — so the rate is the speed, and the
 * amount of *source* to read is the clip's timeline length multiplied by it.
 * Getting that multiplication the wrong way round gives a clip that plays for
 * the right length at the wrong content, or the reverse, and either one sounds
 * plausible for the first second.
 */
export function placements(plan: MixPlan): SourcePlacement[] {
  return plan.clips.map((clip: MixClip) => {
    const rate = clip.speed > 0 ? clip.speed : 1;
    const outputSeconds = clip.duration / TICKS_PER_SECOND;
    return {
      clipId: clip.clip_id,
      assetId: clip.asset_id,
      when: clip.start / TICKS_PER_SECOND,
      offset: clip.in_point / TICKS_PER_SECOND,
      duration: outputSeconds * rate,
      playbackRate: rate,
      ramps: clip.envelope.map(([at, gain]) => ({
        at: (clip.start + at) / TICKS_PER_SECOND,
        gain
      }))
    };
  });
}

/** Whether this browser can render and encode audio at all. */
export function audioSupport(): { supported: boolean; reason: string } {
  const scope = globalThis as Record<string, unknown>;
  if (typeof scope.OfflineAudioContext !== "function") {
    return {
      supported: false,
      reason: "This browser has no OfflineAudioContext, so it cannot mix audio."
    };
  }
  if (typeof scope.AudioEncoder !== "function") {
    return {
      supported: false,
      reason:
        "This browser has no WebCodecs AudioEncoder, so it cannot encode Opus. " +
        "The video will export without sound."
    };
  }
  return { supported: true, reason: "" };
}

/**
 * Fetch and decode every asset the mix needs.
 *
 * An asset that will not decode is reported rather than thrown: one unreadable
 * file should cost its own clip, not the entire export. Video files go through
 * the same path — their audio lives in the same container and `decodeAudioData`
 * reads it out.
 */
export async function loadAudioAssets(
  assetIds: string[],
  urlFor: (id: string) => string,
  sampleRate: number
): Promise<{ buffers: Map<string, AudioBuffer>; missing: string[] }> {
  const scope = globalThis as unknown as {
    OfflineAudioContext: new (channels: number, length: number, rate: number) => OfflineAudioContext;
  };
  // A one-sample context, used only for its decoder. Decoding needs *a*
  // context and does not care which.
  const decoder = new scope.OfflineAudioContext(1, 1, sampleRate);
  const buffers = new Map<string, AudioBuffer>();
  const missing: string[] = [];
  await Promise.all(
    assetIds.map(async (id) => {
      try {
        const response = await fetch(urlFor(id), { credentials: "same-origin" });
        if (!response.ok) throw new Error(`${response.status}`);
        buffers.set(id, await decoder.decodeAudioData(await response.arrayBuffer()));
      } catch {
        missing.push(id);
      }
    })
  );
  return { buffers, missing };
}

/**
 * Sum the whole mix into one buffer, offline.
 *
 * Every clip gets its own `GainNode` carrying its envelope, and the envelope is
 * applied as automation rather than by touching samples — WebAudio interpolates
 * a linear ramp per sample, which is the same curve the planner described and
 * far smoother than anything stepping through an envelope by hand.
 */
export async function renderMix(
  plan: MixPlan,
  buffers: Map<string, AudioBuffer>,
  limitedBy = 1
): Promise<AudioBuffer> {
  const scope = globalThis as unknown as {
    OfflineAudioContext: new (channels: number, length: number, rate: number) => OfflineAudioContext;
  };
  const seconds = plan.duration_ticks / TICKS_PER_SECOND;
  const length = Math.max(1, Math.ceil(seconds * plan.sample_rate));
  const context = new scope.OfflineAudioContext(plan.channels, length, plan.sample_rate);

  const master = context.createGain();
  master.gain.value = limitedBy > 0 ? 1 / limitedBy : 1;
  master.connect(context.destination);

  for (const item of placements(plan)) {
    const buffer = buffers.get(item.assetId);
    if (!buffer) continue;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = item.playbackRate;

    const gain = context.createGain();
    item.ramps.forEach((ramp, index) => {
      if (index === 0) gain.gain.setValueAtTime(ramp.gain, ramp.at);
      else gain.gain.linearRampToValueAtTime(ramp.gain, ramp.at);
    });

    source.connect(gain);
    gain.connect(master);
    // Reading past the end of a buffer is silence, not an error, so a clip
    // longer than its material simply runs out — which is what the timeline
    // validator already refuses to let happen.
    source.start(item.when, item.offset, item.duration);
  }

  return context.startRendering();
}

/** The nineteen bytes a Matroska Opus track needs as CodecPrivate. */
export function opusHead(channels: number, sampleRate: number): Uint8Array {
  const bytes = new Uint8Array(19);
  bytes.set(new TextEncoder().encode("OpusHead"), 0);
  const view = new DataView(bytes.buffer);
  view.setUint8(8, 1); // version
  view.setUint8(9, channels);
  view.setUint16(10, OPUS_PRE_SKIP, true);
  view.setUint32(12, sampleRate, true);
  view.setInt16(16, 0, true); // output gain
  view.setUint8(18, 0); // channel mapping family: mono or plain stereo
  return bytes;
}

interface AudioEncoderLike {
  configure(config: Record<string, unknown>): void;
  encode(data: unknown): void;
  flush(): Promise<void>;
  close(): void;
}

/**
 * Encode a rendered buffer as Opus.
 *
 * Fed in 20ms frames because that is Opus's own frame length; handing an
 * encoder one enormous `AudioData` works in some browsers and stalls in others,
 * and 20ms is also what keeps a chunk's timestamp meaningful inside a cluster.
 */
export async function encodeAudio(
  buffer: AudioBuffer,
  options: { bitrate?: number } = {}
): Promise<{ chunks: EncodedAudioChunkLike[]; description?: Uint8Array }> {
  const scope = globalThis as unknown as {
    AudioEncoder: new (init: {
      output: (chunk: EncodedAudioChunkLike, metadata?: { decoderConfig?: { description?: ArrayBuffer | Uint8Array } }) => void;
      error: (error: Error) => void;
    }) => AudioEncoderLike;
    AudioData: new (init: Record<string, unknown>) => { close(): void };
  };
  const support = audioSupport();
  if (!support.supported) throw new AudioUnsupported(support.reason);

  const channels = buffer.numberOfChannels;
  const rate = buffer.sampleRate;
  const chunks: EncodedAudioChunkLike[] = [];
  let description: Uint8Array | undefined;
  let failure: Error | null = null;

  const encoder = new scope.AudioEncoder({
    output: (chunk, metadata) => {
      const supplied = metadata?.decoderConfig?.description;
      if (supplied && !description) {
        description = supplied instanceof Uint8Array ? supplied : new Uint8Array(supplied);
      }
      chunks.push(chunk);
    },
    error: (error) => {
      failure = error;
    }
  });
  encoder.configure({
    codec: "opus",
    sampleRate: rate,
    numberOfChannels: channels,
    bitrate: options.bitrate ?? AUDIO_BITRATE
  });

  // Planar float is what an AudioBuffer already holds, so this copies rather
  // than converts.
  const planes: Float32Array[] = [];
  for (let channel = 0; channel < channels; channel += 1) {
    planes.push(buffer.getChannelData(channel));
  }

  try {
    for (let start = 0; start < buffer.length; start += FRAME_SAMPLES) {
      if (failure) throw failure;
      const frames = Math.min(FRAME_SAMPLES, buffer.length - start);
      const block = new Float32Array(frames * channels);
      for (let channel = 0; channel < channels; channel += 1) {
        block.set(planes[channel].subarray(start, start + frames), channel * frames);
      }
      const data = new scope.AudioData({
        format: "f32-planar",
        sampleRate: rate,
        numberOfFrames: frames,
        numberOfChannels: channels,
        timestamp: Math.round((start / rate) * 1_000_000),
        data: block
      });
      encoder.encode(data);
      data.close();
    }
    await encoder.flush();
    if (failure) throw failure;
  } finally {
    try {
      encoder.close();
    } catch {
      // Closing an encoder that already errored is not itself a problem.
    }
  }

  return { chunks, description: description ?? opusHead(channels, rate) };
}

/**
 * The whole audio side of an export: fetch, mix, encode.
 *
 * Returns null for a plan with nothing in it. A slideshow with no music is a
 * real export, and the right answer there is a file with no audio track rather
 * than a file with a silent one.
 */
export async function buildAudioTrack(
  plan: MixPlan,
  urlFor: (id: string) => string,
  options: { bitrate?: number } = {}
): Promise<AudioTrackResult | null> {
  if (plan.silent || plan.duration_ticks <= 0) return null;
  const support = audioSupport();
  if (!support.supported) throw new AudioUnsupported(support.reason);

  const { buffers, missing } = await loadAudioAssets(plan.asset_ids, urlFor, plan.sample_rate);
  if (!buffers.size) return null;

  const limitedBy = plan.headroom > 1 ? plan.headroom : 1;
  const buffer = await renderMix(plan, buffers, limitedBy);
  const { chunks, description } = await encodeAudio(buffer, options);
  if (!chunks.length) return null;

  return {
    chunks,
    description,
    sampleRate: buffer.sampleRate,
    channels: buffer.numberOfChannels,
    codec: "opus",
    limitedBy,
    missing
  };
}
