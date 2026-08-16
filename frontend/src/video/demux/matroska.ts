/**
 * Matroska / WebM, read for its video frames.
 *
 * The mirror image of `webm.ts`, which writes this format, and of
 * `_probe_webm` in `video/gates.py`, which reads its header on the server. Same
 * elements; this one goes one level further and walks the Clusters.
 *
 * EBML is a tree of `(id, size, payload)` where both the id and the size are
 * variable-length integers. An id keeps its leading marker bit so it compares
 * directly against a constant; a size drops it, because the marker only says
 * how many bytes the number occupies.
 */

import { DemuxError, type FrameRef, type VideoTrack } from "./index";

const EBML_HEADER = 0x1a45dfa3;
const SEGMENT = 0x18538067;
const INFO = 0x1549a966;
const TIMECODE_SCALE = 0x2ad7b1;
const TRACKS = 0x1654ae6b;
const TRACK_ENTRY = 0xae;
const TRACK_NUMBER = 0xd7;
const TRACK_TYPE = 0x83;
const CODEC_ID = 0x86;
const CODEC_PRIVATE = 0x63a2;
const DEFAULT_DURATION = 0x23e383;
const VIDEO = 0xe0;
const PIXEL_WIDTH = 0xb0;
const PIXEL_HEIGHT = 0xba;
const CLUSTER = 0x1f43b675;
const TIMECODE = 0xe7;
const SIMPLE_BLOCK = 0xa3;
const BLOCK_GROUP = 0xa0;
const BLOCK = 0xa1;
const REFERENCE_BLOCK = 0xfb;

/** Nanoseconds per Matroska tick when Info does not say otherwise. */
const DEFAULT_TIMECODE_SCALE = 1_000_000;

/** Containers this walks into. Everything else is skipped whole. */
const CONTAINERS = new Set([SEGMENT, INFO, TRACKS, TRACK_ENTRY, VIDEO, CLUSTER, BLOCK_GROUP]);

interface Reader {
  bytes: Uint8Array;
  view: DataView;
  at: number;
}

/** An EBML variable-length integer. `keepMarker` is the difference between an
 * element id and a size. */
function vint(reader: Reader, keepMarker: boolean): number {
  const first = reader.bytes[reader.at];
  if (first === undefined) throw new DemuxError("This WebM ends in the middle of an element.");
  let width = 1;
  let mask = 0x80;
  while (width <= 8 && !(first & mask)) {
    width += 1;
    mask >>= 1;
  }
  if (width > 8) throw new DemuxError("This WebM has an element length it cannot express.");
  let value = keepMarker ? first : first & (mask - 1);
  for (let index = 1; index < width; index += 1) {
    const next = reader.bytes[reader.at + index];
    if (next === undefined) throw new DemuxError("This WebM ends in the middle of an element.");
    value = value * 256 + next;
  }
  reader.at += width;
  // An all-ones size means "unknown", which a live muxer writes because it
  // cannot know the length in advance. -1 means "to the end of the parent".
  if (!keepMarker && value === 2 ** (7 * width) - 1) return -1;
  return value;
}

function uint(bytes: Uint8Array, from: number, to: number): number {
  let value = 0;
  for (let index = from; index < to; index += 1) value = value * 256 + bytes[index];
  return value;
}

function ascii(bytes: Uint8Array, from: number, to: number): string {
  let out = "";
  for (let index = from; index < to && bytes[index]; index += 1) out += String.fromCharCode(bytes[index]);
  return out;
}

/**
 * A Matroska CodecID as WebCodecs wants it.
 *
 * VP8 and VP9 carry no per-file decoder configuration, so the codec string is
 * the whole configuration — and WebCodecs requires the full four-part form for
 * VP9. `vp09.00.10.08` is profile 0, level 3.1, 8-bit, which is what every
 * browser encoder produces and what an imported WebM will almost always be. A
 * file outside that gets refused by `isConfigSupported` with its own message
 * rather than mis-decoded here.
 */
function codecFor(id: string, priv?: Uint8Array): { codec: string; description?: Uint8Array } {
  if (id === "V_VP8") return { codec: "vp8" };
  if (id === "V_VP9") return { codec: "vp09.00.10.08" };
  if (id === "V_AV1") return { codec: "av01.0.04M.08", description: priv };
  if (id === "V_MPEG4/ISO/AVC") {
    // H.264 in Matroska carries the same avcC the MP4 sample entry does.
    const profile = priv && priv.length >= 4 ? [priv[1], priv[2], priv[3]] : null;
    const suffix = profile
      ? profile.map((byte) => byte.toString(16).padStart(2, "0")).join("")
      : "42e01e";
    return { codec: `avc1.${suffix}`, description: priv };
  }
  if (id === "V_MPEGH/ISO/HEVC") return { codec: "hev1.1.6.L93.B0", description: priv };
  throw new DemuxError(
    `This WebM's video track is ${id}, which this build cannot decode. VP8, VP9, ` +
      "AV1 and H.264 are understood."
  );
}

export function demuxMatroska(bytes: Uint8Array): VideoTrack {
  const reader: Reader = { bytes, view: new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), at: 0 };

  let timecodeScale = DEFAULT_TIMECODE_SCALE;
  let frameDurationNs = 0;
  let trackNumber = -1;
  let codecId = "";
  let codecPrivate: Uint8Array | undefined;
  let width = 0;
  let height = 0;
  const frames: FrameRef[] = [];

  // Track fields arrive per TrackEntry and only the video one is kept, so they
  // are gathered into a scratch record and committed when the entry closes.
  let entry: {
    number: number;
    type: number;
    codec: string;
    priv?: Uint8Array;
    w: number;
    h: number;
    durationNs: number;
  } | null = null;
  let clusterTicks = 0;

  const scaleToUs = (ticks: number) => Math.round((ticks * timecodeScale) / 1000);

  function block(from: number, to: number, simple: boolean, key: boolean): void {
    const local: Reader = { ...reader, at: from };
    const track = vint(local, false);
    if (track !== trackNumber) return;
    if (local.at + 3 > to) throw new DemuxError("This WebM has a block with no header.");
    const relative = reader.view.getInt16(local.at, false);
    const flags = bytes[local.at + 2];
    local.at += 3;
    if (flags & 0x06) {
      throw new DemuxError(
        "This WebM laces several frames into one block. Video is not normally " +
          "laced and this build does not unpack it."
      );
    }
    frames.push({
      offset: local.at,
      length: to - local.at,
      timestampUs: scaleToUs(clusterTicks + relative),
      durationUs: frameDurationNs ? Math.round(frameDurationNs / 1000) : 0,
      key: simple ? Boolean(flags & 0x80) : key
    });
  }

  function walk(start: number, end: number): void {
    reader.at = start;
    while (reader.at < end) {
      const elementStart = reader.at;
      let element: number;
      let size: number;
      try {
        element = vint(reader, true);
        size = vint(reader, false);
      } catch {
        return;
      }
      const body = reader.at;
      const stop = size < 0 ? end : Math.min(end, body + size);
      if (stop <= elementStart) return;

      if (element === CLUSTER) {
        clusterTicks = 0;
        walk(body, stop);
      } else if (element === BLOCK_GROUP) {
        // A BlockGroup's frame is a keyframe exactly when it references
        // nothing. The flag byte inside a plain Block is always zero, so the
        // answer has to come from its siblings rather than from itself.
        let referenced = false;
        let blockRange: [number, number] | null = null;
        const scan: Reader = { ...reader, at: body };
        while (scan.at < stop) {
          const child = vint(scan, true);
          const childSize = vint(scan, false);
          const childStop = childSize < 0 ? stop : Math.min(stop, scan.at + childSize);
          if (child === BLOCK) blockRange = [scan.at, childStop];
          if (child === REFERENCE_BLOCK) referenced = true;
          scan.at = childStop;
        }
        if (blockRange) block(blockRange[0], blockRange[1], false, !referenced);
      } else if (element === TRACK_ENTRY) {
        entry = { number: -1, type: 0, codec: "", w: 0, h: 0, durationNs: 0 };
        walk(body, stop);
        if (entry && entry.type === 1 && trackNumber < 0) {
          trackNumber = entry.number;
          codecId = entry.codec;
          codecPrivate = entry.priv;
          width = entry.w;
          height = entry.h;
          // Read from the *video* entry, not from whichever track declared one
          // last — an audio track's frame length is not this one's.
          frameDurationNs = entry.durationNs;
        }
        entry = null;
      } else if (CONTAINERS.has(element)) {
        walk(body, stop);
      } else if (element === TIMECODE_SCALE) {
        timecodeScale = uint(bytes, body, stop) || DEFAULT_TIMECODE_SCALE;
      } else if (element === TIMECODE) {
        clusterTicks = uint(bytes, body, stop);
      } else if (element === SIMPLE_BLOCK) {
        block(body, stop, true, false);
      } else if (entry) {
        if (element === TRACK_NUMBER) entry.number = uint(bytes, body, stop);
        else if (element === TRACK_TYPE) entry.type = uint(bytes, body, stop);
        else if (element === CODEC_ID) entry.codec = ascii(bytes, body, stop);
        else if (element === CODEC_PRIVATE) entry.priv = bytes.slice(body, stop);
        else if (element === DEFAULT_DURATION) entry.durationNs = uint(bytes, body, stop);
        else if (element === PIXEL_WIDTH) entry.w = uint(bytes, body, stop);
        else if (element === PIXEL_HEIGHT) entry.h = uint(bytes, body, stop);
      }
      reader.at = stop;
    }
  }

  // Skip the EBML header and walk the Segment, which holds everything.
  let cursor = 0;
  while (cursor < bytes.length) {
    reader.at = cursor;
    const element = vint(reader, true);
    const size = vint(reader, false);
    const body = reader.at;
    const stop = size < 0 ? bytes.length : Math.min(bytes.length, body + size);
    if (element === SEGMENT) {
      walk(body, stop);
      break;
    }
    if (element !== EBML_HEADER) throw new DemuxError("This WebM does not begin with an EBML header.");
    cursor = stop;
  }

  if (trackNumber < 0) throw new DemuxError("This WebM has no video track to draw.");
  if (!frames.length) throw new DemuxError("This WebM declares a video track and carries no frames.");

  const { codec, description } = codecFor(codecId, codecPrivate);
  fillDurations(frames);
  return { codec, description, width, height, frames, container: "webm" };
}

/**
 * Give every frame a duration.
 *
 * Matroska usually does not store one per frame — the gap to the *next frame in
 * presentation order* is the duration, and the last frame inherits the one
 * before it. A frame with no duration decodes fine but cannot answer "is this
 * the frame at tick T", which is the only question this demuxer exists to
 * serve.
 *
 * The array itself is left in **decode order**, which is the order a
 * `VideoDecoder` has to be fed. They are the same order for VP8 and VP9, and
 * not the same for anything with B-frames — so the gap is measured on a sorted
 * copy and written back through the objects rather than by reordering them.
 */
export function fillDurations(frames: FrameRef[]): void {
  const ordered = [...frames].sort((left, right) => left.timestampUs - right.timestampUs);
  // Two frames can land on the same instant — a file with a bad composition
  // table, or one where two frames genuinely round to the same microsecond —
  // and the gap to the *next distinct* time is the honest answer for both. A
  // duration of zero would be worse than wrong: it is a frame that covers no
  // moment at all, so no lookup ever returns it.
  for (let index = 0; index < ordered.length; index += 1) {
    if (ordered[index].durationUs > 0) continue;
    let ahead = index + 1;
    while (ahead < ordered.length && ordered[ahead].timestampUs <= ordered[index].timestampUs) {
      ahead += 1;
    }
    ordered[index].durationUs =
      ahead < ordered.length
        ? ordered[ahead].timestampUs - ordered[index].timestampUs
        : ordered[index - 1]?.durationUs ?? 0;
  }
  // The last frame has nothing after it, so it inherits — and if the file is
  // one frame long there is nothing to inherit from either.
  const last = ordered[ordered.length - 1];
  if (last && last.durationUs <= 0) last.durationUs = ordered[ordered.length - 2]?.durationUs ?? 1;
}
