/**
 * The timeline document, as the browser sees it.
 *
 * A mirror of `offsetx_apollo_builder/video/timeline.py`. The server owns the
 * document and validates every edit; this file exists because the browser has
 * to *draw* it sixty times a second, and asking the server what is on screen
 * once per frame would be a request every sixteen milliseconds.
 *
 * Nothing here edits anything. Every change goes to the server as a named
 * operation and comes back as a new document, so there is exactly one place
 * that decides whether an edit is legal.
 */

/** Ticks in one second. The MPEG timebase — see the Python module for why. */
export const TICKS_PER_SECOND = 90_000;

export const FRAME_RATES: Record<string, number> = {
  "23.976": 24000 / 1001,
  "24": 24,
  "25": 25,
  "29.97": 30000 / 1001,
  "30": 30,
  "50": 50,
  "59.94": 60000 / 1001,
  "60": 60
};

/** Every animatable property, its default, and the range it is clamped to. */
export const PROPERTY_SPEC: Record<string, [number, number, number]> = {
  x: [0, -20000, 20000],
  y: [0, -20000, 20000],
  scale: [1, 0.01, 50],
  rotation: [0, -3600, 3600],
  opacity: [1, 0, 1],
  anchor_x: [0.5, 0, 1],
  anchor_y: [0.5, 0, 1],
  crop_left: [0, 0, 0.99],
  crop_top: [0, 0, 0.99],
  crop_right: [0, 0, 0.99],
  crop_bottom: [0, 0, 0.99],
  volume: [1, 0, 4],
  brightness: [0, -1, 1],
  contrast: [0, -1, 1],
  saturation: [0, -1, 1],
  blur: [0, 0, 100]
};

export type Easing = "linear" | "hold" | "ease_in" | "ease_out" | "ease_in_out";
export type ClipKind = "video" | "image" | "audio" | "text" | "solid";
export type TrackKind = "video" | "audio";

export interface Keyframe {
  at: number;
  value: number;
  easing: Easing;
}

export interface Clip {
  id: string;
  kind: ClipKind;
  start: number;
  duration: number;
  in_point: number;
  source_duration: number;
  asset_id: string;
  text: string;
  speed: number;
  fade_in: number;
  fade_out: number;
  label: string;
  properties: Record<string, number>;
  keyframes: Record<string, Keyframe[]>;
  style: Record<string, unknown>;
}

export interface Track {
  id: string;
  kind: TrackKind;
  name: string;
  locked: boolean;
  muted: boolean;
  hidden: boolean;
  clips: Clip[];
}

export interface Marker {
  id: string;
  at: number;
  label: string;
  colour: string;
}

export interface ProjectDoc {
  version: number;
  id: string;
  name: string;
  width: number;
  height: number;
  fps: string;
  background: string;
  duration: number;
  tracks: Track[];
  markers: Marker[];
}

/** One clip, resolved at one instant. The unit the renderer draws. */
export interface DrawItem {
  clip_id: string;
  track_id: string;
  kind: ClipKind;
  z: number;
  asset_id: string;
  text: string;
  source_time: number;
  clip_time: number;
  speed: number;
  opacity: number;
  gain: number;
  properties: Record<string, number>;
  style: Record<string, unknown>;
}

export interface Frame {
  tick: number;
  items: DrawItem[];
}

/** What the server needs to hand over before anything can be drawn. */
export interface RenderManifest {
  project_id: string;
  version: number;
  name: string;
  width: number;
  height: number;
  fps: string;
  ticks_per_frame: number;
  ticks_per_second: number;
  duration_ticks: number;
  duration_seconds: number;
  frames: number;
  background: string;
  assets: Array<{
    id: string;
    available: boolean;
    /** Which store it came from: a generated picture, or imported material. */
    source?: "image" | "media";
    media_type?: string;
    width?: number;
    height?: number;
    duration_ticks?: number;
    has_audio?: boolean;
    status?: string;
  }>;
  warnings: string[];
  renderable: boolean;
}

export interface ProjectState {
  id: string;
  campaign_id: string;
  name: string;
  version: number;
  document: ProjectDoc;
  can_undo: boolean;
  can_redo: boolean;
  updated_at?: string;
}

export function ticksPerFrame(fps: string): number {
  const rate = FRAME_RATES[fps];
  if (!rate) throw new Error(`Unsupported frame rate ${fps}`);
  return TICKS_PER_SECOND / rate;
}

export function ticksToSeconds(ticks: number): number {
  return ticks / TICKS_PER_SECOND;
}

export function secondsToTicks(seconds: number): number {
  return Math.round(seconds * TICKS_PER_SECOND);
}

/** `0:04.20`, which is what a timecode field should read like at this length. */
export function formatTimecode(ticks: number): string {
  const total = Math.max(0, ticks) / TICKS_PER_SECOND;
  const minutes = Math.floor(total / 60);
  const seconds = total - minutes * 60;
  return `${minutes}:${seconds.toFixed(2).padStart(5, "0")}`;
}
