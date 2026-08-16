/**
 * What is on screen at one tick — the browser's copy of the server's answer.
 *
 * This is the one file in the editor that is deliberately a duplicate. The
 * server resolves keyframes in `timeline.py` and the browser resolves them here,
 * because a preview cannot make a network round trip per frame. Two
 * implementations of one rule will drift, and the way that drift shows up is
 * the worst kind there is: the preview looks right, the exported file does not
 * match it, and nothing failed anywhere.
 *
 * So it is pinned. `tests/fixtures/timeline_conformance.json` holds one
 * document and the frames Python resolves from it, and `resolve.test.ts`
 * asserts this file produces the same numbers. Change either side without the
 * other and a test goes red.
 *
 * That is also why the arithmetic below is written the long way round in two
 * places — see `roundHalfToEven`. Matching Python exactly is the whole job.
 */

import type { Clip, DrawItem, Frame, Keyframe, ProjectDoc, Track, Transition } from "./document";
import { PROPERTY_SPEC } from "./document";

/**
 * Python's `round()` breaks ties to the nearest even number; JavaScript's
 * `Math.round` breaks them upward. One tick of difference is invisible on
 * screen and is still a difference, and a conformance check that tolerates
 * "close enough" stops being able to tell drift from noise.
 */
export function roundHalfToEven(value: number): number {
  const floor = Math.floor(value);
  const remainder = value - floor;
  if (remainder > 0.5) return floor + 1;
  if (remainder < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Six decimal places, matching what the server writes into the fixture. */
export function roundTo(value: number, places: number): number {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

export function clampProperty(name: string, value: number): number {
  const spec = PROPERTY_SPEC[name];
  if (!spec) return value;
  const [fallback, low, high] = spec;
  if (Number.isNaN(value)) return fallback;
  return Math.max(low, Math.min(high, value));
}

function ease(easing: string, ratio: number): number {
  if (easing === "hold") return 0;
  if (easing === "ease_in") return ratio * ratio;
  if (easing === "ease_out") return 1 - (1 - ratio) * (1 - ratio);
  if (easing === "ease_in_out") {
    if (ratio < 0.5) return 2 * ratio * ratio;
    return 1 - 2 * (1 - ratio) * (1 - ratio);
  }
  return ratio;
}

/**
 * The value of an animated property at `offset` ticks into its clip.
 * Holds before the first keyframe and after the last, rather than
 * extrapolating past either end.
 */
export function interpolate(frames: Keyframe[], offset: number): number {
  if (!frames.length) return 0;
  const ordered = [...frames].sort((a, b) => a.at - b.at);
  if (offset <= ordered[0].at) return ordered[0].value;
  if (offset >= ordered[ordered.length - 1].at) return ordered[ordered.length - 1].value;
  for (let index = 0; index < ordered.length - 1; index += 1) {
    const left = ordered[index];
    const right = ordered[index + 1];
    if (left.at <= offset && offset <= right.at) {
      const span = right.at - left.at;
      if (span <= 0) return right.value;
      const ratio = ease(left.easing, (offset - left.at) / span);
      return left.value + (right.value - left.value) * ratio;
    }
  }
  return ordered[ordered.length - 1].value;
}

/**
 * The area under a speed curve from 0 to `offset` — how much material a clip
 * has read by then. Matches `_consumed` in `timeline.py`.
 *
 * The curve is straight between its points, so each piece is a trapezoid:
 * exact, and computable identically in two languages, which a bezier is not.
 * Before the first point the first speed holds and after the last the last one
 * does, for the same reason `interpolate` holds rather than extrapolating —
 * running a *speed* past its last keyframe can send a clip off the end of its
 * own material.
 */
export function consumed(clip: Clip, offset: number): number {
  const at = Math.max(0, Math.min(offset, clip.duration));
  const curve = clip.speed_curve ?? [];
  if (!curve.length) return at * clip.speed;
  const points = [...curve].sort((a, b) => a.at - b.at);
  let total = 0;
  const head = Math.min(at, points[0].at);
  if (head > 0) total += head * points[0].value;
  for (let index = 0; index < points.length - 1; index += 1) {
    const left = points[index];
    const right = points[index + 1];
    if (at <= left.at) break;
    const span = right.at - left.at;
    if (span <= 0) continue;
    if (at >= right.at) {
      total += ((left.value + right.value) / 2) * span;
      continue;
    }
    const ratio = (at - left.at) / span;
    const here = left.value + (right.value - left.value) * ratio;
    total += ((left.value + here) / 2) * (at - left.at);
    break;
  }
  const last = points[points.length - 1];
  if (at > last.at) total += (at - last.at) * last.value;
  return total;
}

/**
 * Where in its material a clip is reading, `offset` ticks in.
 *
 * A reversed clip walks the same span from the far end: at offset 0 it is at
 * the last instant it will ever read, and at the end of the clip it is back at
 * the in-point.
 */
export function sourceAt(clip: Clip, offset: number): number {
  if (clip.reversed) {
    const span = consumed(clip, clip.duration);
    return clip.in_point + roundHalfToEven(span - consumed(clip, offset));
  }
  return clip.in_point + roundHalfToEven(consumed(clip, offset));
}

/** Every property of one clip, resolved at `offset` ticks into it. */
export function propertyAt(clip: Clip, offset: number): Record<string, number> {
  const values: Record<string, number> = {};
  for (const [name, spec] of Object.entries(PROPERTY_SPEC)) values[name] = spec[0];
  for (const [name, value] of Object.entries(clip.properties ?? {})) {
    values[name] = clampProperty(name, value);
  }
  for (const [name, frames] of Object.entries(clip.keyframes ?? {})) {
    if (frames && frames.length) values[name] = clampProperty(name, interpolate(frames, offset));
  }
  return values;
}

/**
 * How far into a fade this instant is. One fade governs both picture and
 * sound, the same as on the server.
 */
export function fadeFactor(clip: Clip, offset: number): number {
  let factor = 1;
  if (clip.fade_in > 0 && offset < clip.fade_in) {
    factor *= Math.max(0, offset / clip.fade_in);
  }
  const tail = clip.duration - clip.fade_out;
  if (clip.fade_out > 0 && offset > tail) {
    factor *= Math.max(0, (clip.duration - offset) / clip.fade_out);
  }
  return Math.max(0, Math.min(1, factor));
}

/**
 * How loud a clip is, `offset` ticks into itself.
 *
 * The only place this rule lives on this side, matching `clip_gain` in
 * `timeline.py`. The preview reads it through `frameAt` and the exporter's
 * mixer reads it directly, and those two disagreeing would be a preview that
 * lies about the file it is previewing.
 *
 * `volume` is an escape hatch for a caller that has already resolved this
 * clip's properties, so `frameAt` does not do that work twice.
 */
export function clipGain(track: Track, clip: Clip, offset: number, volume?: number): number {
  if (track.muted) return 0;
  // A still or a caption on a video track makes no sound. Footage does, even on
  // a video track, because its audio travels inside the same file.
  if (track.kind !== "audio" && clip.kind !== "video") return 0;
  const level = volume === undefined ? propertyAt(clip, offset).volume : volume;
  return Math.max(0, level * fadeFactor(clip, offset));
}

/**
 * The span both clips of a transition are drawn for, centred on their cut.
 *
 * Returns null when the two clips are not adjacent any more — a transition left
 * behind by an edit that moved one of them. Drawing it near the old cut would
 * put a dissolve in the middle of a clip.
 */
export function transitionWindow(track: Track, item: Transition): [number, number] | null {
  const left = track.clips.find((clip) => clip.id === item.from_clip_id);
  const right = track.clips.find((clip) => clip.id === item.to_clip_id);
  if (!left || !right) return null;
  if (left.start + left.duration !== right.start) return null;
  const half = Math.max(1, Math.trunc(item.duration / 2));
  return [Math.max(0, left.start + left.duration - half), left.start + left.duration + half];
}

/**
 * What the viewer sees and hears at `tick`.
 *
 * A clip is live when `start <= tick < end`. The half-open interval is what
 * stops every cut in every project being a one-frame overlap.
 */
export function frameAt(project: ProjectDoc, tick: number): Frame {
  const moment = Math.max(0, Math.trunc(tick));
  const items: DrawItem[] = [];
  project.tracks.forEach((track: Track, index: number) => {
    // Which clips this instant asks for beyond their own bounds, and how far
    // through the blend it is. Once per track: a transition belongs to a
    // boundary, not to either side of it.
    const extended = new Map<string, DrawItem["transition"]>();
    for (const item of track.transitions ?? []) {
      const window = transitionWindow(track, item);
      if (!window) continue;
      const [start, end] = window;
      if (!(start <= moment && moment < end)) continue;
      const span = Math.max(1, end - start);
      const progress = Math.min(1, Math.max(0, (moment - start) / span));
      extended.set(item.from_clip_id, {
        id: item.id,
        preset: item.preset,
        progress: roundTo(progress, 6),
        role: "from",
        partner: item.to_clip_id
      });
      extended.set(item.to_clip_id, {
        id: item.id,
        preset: item.preset,
        progress: roundTo(progress, 6),
        role: "to",
        partner: item.from_clip_id
      });
    }

    for (const clip of track.clips) {
      const crossing = extended.get(clip.id);
      const live = clip.start <= moment && moment < clip.start + clip.duration;
      if (!live && !crossing) continue;
      // A clip drawn outside its own bounds is held at its nearest frame — the
      // alternative is reading past the end of its own material.
      const offset = Math.min(Math.max(0, moment - clip.start), Math.max(0, clip.duration - 1));
      const resolved = propertyAt(clip, offset);
      const fade = fadeFactor(clip, offset);
      const hasSource = clip.kind === "video" || clip.kind === "audio";
      const sourceTime = hasSource ? sourceAt(clip, offset) : -1;
      const gain = clipGain(track, clip, offset, resolved.volume);
      const visible = track.hidden && track.kind === "video" ? 0 : 1;
      items.push({
        clip_id: clip.id,
        track_id: track.id,
        kind: clip.kind,
        z: index,
        asset_id: clip.asset_id,
        text: clip.text,
        source_time: sourceTime,
        clip_time: offset,
        speed: clip.speed,
        opacity: resolved.opacity * (track.kind === "video" ? fade : 1) * visible,
        gain,
        properties: resolved,
        style: { ...(clip.style ?? {}) },
        transition: crossing ? { ...crossing } : {}
      });
    }
  });
  items.sort((a, b) => (a.z !== b.z ? a.z - b.z : a.clip_id < b.clip_id ? -1 : a.clip_id > b.clip_id ? 1 : 0));
  return { tick: moment, items };
}

/** Total length of the document, which is the last tick any clip reaches. */
export function projectDuration(project: ProjectDoc): number {
  let longest = 0;
  for (const track of project.tracks) {
    for (const clip of track.clips) longest = Math.max(longest, clip.start + clip.duration);
  }
  return longest;
}

/** Every asset the document references, once each, in timeline order. */
export function assetIds(project: ProjectDoc): string[] {
  const clips = project.tracks.flatMap((track) => track.clips).sort((a, b) => a.start - b.start);
  const seen: string[] = [];
  for (const clip of clips) {
    if (clip.asset_id && !seen.includes(clip.asset_id)) seen.push(clip.asset_id);
  }
  return seen;
}

/** The clip a click at `tick` lands on, for a given track. */
export function clipAt(track: Track, tick: number): Clip | null {
  return track.clips.find((clip) => clip.start <= tick && tick < clip.start + clip.duration) ?? null;
}
