/**
 * The audio mix, as a plan — the browser's copy of `mixdown.py`.
 *
 * The second deliberate duplicate in this editor, for the same reason as
 * `resolve.ts`: the export runs here, where the decoder is, and it cannot ask
 * the server what the gain is forty-eight thousand times a second. So the shape
 * of every clip's gain is worked out as an **envelope** — the handful of points
 * where it actually changes — and `audio.ts` hands that straight to a
 * `GainNode`, which is what `setValueAtTime` and `linearRampToValueAtTime` are
 * for.
 *
 * Pinned to the server the same way the resolver is: the `mix` block of
 * `tests/fixtures/timeline_conformance.json` is what Python plans for the
 * fixture document, and `mixdown.test.ts` asserts this file plans the same
 * thing. Neither side can move quietly.
 */

import type { Clip, ProjectDoc, Track } from "./document";
import { TICKS_PER_SECOND } from "./document";
import { clipGain, roundTo } from "./resolve";

/** How finely a curved stretch is sampled. 10ms, well under audible. */
export const ENVELOPE_HZ = 100;
export const ENVELOPE_STEP = Math.trunc(TICKS_PER_SECOND / ENVELOPE_HZ);

/** Two gains this close are the same gain to a listener. */
const ENVELOPE_TOLERANCE = 1e-4;

/** Below this a clip is inaudible, and including it costs a fetch and a decode. */
export const SILENCE = 0.001;

export const SAMPLE_RATE = 48_000;
export const CHANNELS = 2;

const AUDIBLE_KINDS = ["audio", "video"];

/** `[at, gain]` in the clip's own time. */
export type EnvelopePoint = [number, number];

export interface MixClip {
  clip_id: string;
  asset_id: string;
  kind: string;
  start: number;
  duration: number;
  in_point: number;
  speed: number;
  envelope: EnvelopePoint[];
}

export interface MixPlan {
  duration_ticks: number;
  sample_rate: number;
  channels: number;
  silent: boolean;
  headroom: number;
  clips: MixClip[];
  asset_ids: string[];
}

function volumeKeyframes(clip: Clip) {
  return [...(clip.keyframes?.volume ?? [])].sort((a, b) => a.at - b.at);
}

/**
 * The stretches of a clip whose gain is not a straight line.
 *
 * Two things bend it. A fade, because it multiplies whatever the volume curve
 * is doing — flat times a ramp is still a ramp, but a ramp times a ramp is a
 * parabola, and this cannot tell which without looking. And an eased keyframe,
 * whose whole purpose is to not be a straight line.
 */
function denseSpans(clip: Clip): Array<[number, number]> {
  const spans: Array<[number, number]> = [];
  if (clip.fade_in > 0) spans.push([0, Math.min(clip.fade_in, clip.duration)]);
  if (clip.fade_out > 0) {
    spans.push([Math.max(0, clip.duration - clip.fade_out), clip.duration]);
  }
  const frames = volumeKeyframes(clip);
  for (let index = 0; index < frames.length - 1; index += 1) {
    const left = frames[index];
    const right = frames[index + 1];
    if (left.easing !== "linear" && left.value !== right.value) {
      spans.push([Math.max(0, left.at), Math.min(clip.duration, right.at)]);
    }
  }
  return spans.filter(([start, end]) => end > start);
}

/** Every offset at which a clip's gain is worth asking about. */
function samplePoints(clip: Clip): number[] {
  const points = new Set<number>([0, clip.duration]);
  if (clip.fade_in > 0) points.add(Math.min(clip.fade_in, clip.duration));
  if (clip.fade_out > 0) points.add(Math.max(0, clip.duration - clip.fade_out));
  for (const frame of clip.keyframes?.volume ?? []) {
    if (frame.at > 0 && frame.at < clip.duration) points.add(frame.at);
  }
  for (const [start, end] of denseSpans(clip)) {
    for (let at = start; at < end; at += ENVELOPE_STEP) points.add(at);
    points.add(end);
  }
  return [...points].filter((at) => at >= 0 && at <= clip.duration).sort((a, b) => a - b);
}

function onLine(left: EnvelopePoint, right: EnvelopePoint, point: EnvelopePoint): boolean {
  const span = right[0] - left[0];
  if (span <= 0) return Math.abs(point[1] - left[1]) <= ENVELOPE_TOLERANCE;
  const expected = left[1] + (right[1] - left[1]) * ((point[0] - left[0]) / span);
  return Math.abs(point[1] - expected) <= ENVELOPE_TOLERANCE;
}

/**
 * Drop every point a straight line would have passed through anyway.
 *
 * Each dropped point is checked against the line from the last *kept* point
 * rather than from its neighbour, so a shallow curve cannot be walked away from
 * one tolerance at a time.
 */
function simplify(points: EnvelopePoint[]): EnvelopePoint[] {
  if (points.length <= 2) return [...points];
  const kept: EnvelopePoint[] = [points[0]];
  let pending: EnvelopePoint[] = [];
  for (const point of points.slice(1)) {
    if (pending.every((item) => onLine(kept[kept.length - 1], point, item))) {
      pending.push(point);
      continue;
    }
    kept.push(pending[pending.length - 1]);
    pending = [point];
  }
  if (pending.length) kept.push(pending[pending.length - 1]);
  return kept;
}

/**
 * The points at which a clip's gain changes.
 *
 * Always begins at 0 and ends at `duration`, so the renderer never has to guess
 * what happens at the edges. The end is read at `duration` itself and not one
 * tick earlier, which is how a fade-out arrives at exactly zero on the cut
 * rather than at a hundredth of full volume.
 */
export function envelopeFor(track: Track, clip: Clip): EnvelopePoint[] {
  if (clip.duration <= 0) return [];
  const sampled: EnvelopePoint[] = samplePoints(clip).map((at) => [at, clipGain(track, clip, at)]);
  return simplify(sampled);
}

/**
 * Every clip that could make a sound.
 *
 * A **video** clip counts: its audio travels inside the same file as its
 * picture, and `decodeAudioData` reads it out quite happily.
 */
export function audibleClips(project: ProjectDoc): Array<[Track, Clip]> {
  const found: Array<[Track, Clip]> = [];
  for (const track of project.tracks) {
    if (track.muted) continue;
    for (const clip of track.clips) {
      if (!AUDIBLE_KINDS.includes(clip.kind) || !clip.asset_id) continue;
      found.push([track, clip]);
    }
  }
  return found;
}

/** The envelope's own reading at `offset`, the way WebAudio will read it. */
export function gainAt(envelope: EnvelopePoint[], offset: number): number {
  if (!envelope.length) return 0;
  if (offset <= envelope[0][0]) return envelope[0][1];
  const last = envelope[envelope.length - 1];
  if (offset >= last[0]) return last[1];
  for (let index = 0; index < envelope.length - 1; index += 1) {
    const [leftAt, leftGain] = envelope[index];
    const [rightAt, rightGain] = envelope[index + 1];
    if (leftAt <= offset && offset <= rightAt) {
      const span = rightAt - leftAt;
      if (span <= 0) return rightGain;
      return leftGain + (rightGain - leftGain) * ((offset - leftAt) / span);
    }
  }
  return last[1];
}

/**
 * The worst-case sum of gains at any instant.
 *
 * Two clips at full volume sum to 2.0 and the output clips. Measured at every
 * envelope point rather than at clip boundaries, because two clips fading
 * through each other are loudest where neither starts nor ends.
 */
export function headroom(clips: MixClip[]): number {
  if (!clips.length) return 0;
  const moments = new Set<number>();
  for (const item of clips) {
    moments.add(item.start);
    moments.add(item.start + item.duration);
    for (const [at] of item.envelope) moments.add(item.start + at);
  }
  let worst = 0;
  for (const moment of [...moments].sort((a, b) => a - b)) {
    let total = 0;
    for (const item of clips) {
      if (item.start <= moment && moment < item.start + item.duration) {
        total += gainAt(item.envelope, moment - item.start);
      }
    }
    worst = Math.max(worst, total);
  }
  return worst;
}

/**
 * The whole mix.
 *
 * Clips whose gain never rises above silence are dropped rather than rendered
 * at zero — each one costs a fetch and a decode to contribute nothing.
 */
export function planMix(project: ProjectDoc): MixPlan {
  const clips: MixClip[] = [];
  for (const [track, clip] of audibleClips(project)) {
    const envelope = envelopeFor(track, clip);
    if (!envelope.length) continue;
    const peak = envelope.reduce((high, [, gain]) => Math.max(high, gain), 0);
    if (peak <= SILENCE) continue;
    clips.push({
      clip_id: clip.id,
      asset_id: clip.asset_id,
      kind: clip.kind,
      start: clip.start,
      duration: clip.duration,
      in_point: clip.in_point,
      speed: clip.speed,
      envelope
    });
  }
  clips.sort((a, b) =>
    a.start !== b.start ? a.start - b.start : a.clip_id < b.clip_id ? -1 : a.clip_id > b.clip_id ? 1 : 0
  );

  const assetIds: string[] = [];
  for (const item of clips) {
    if (!assetIds.includes(item.asset_id)) assetIds.push(item.asset_id);
  }

  let duration = 0;
  for (const track of project.tracks) {
    for (const clip of track.clips) duration = Math.max(duration, clip.start + clip.duration);
  }

  return {
    duration_ticks: duration,
    sample_rate: SAMPLE_RATE,
    channels: CHANNELS,
    silent: clips.length === 0,
    headroom: roundTo(headroom(clips), 6),
    clips,
    asset_ids: assetIds
  };
}
