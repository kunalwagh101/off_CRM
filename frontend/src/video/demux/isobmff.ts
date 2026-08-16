/**
 * MP4 / MOV, read for its video frames.
 *
 * `video/gates.py` already walks this tree on the server to read a file's
 * shape — `moov > trak > tkhd` for the dimensions and the display matrix. This
 * goes further down the same tree, into `stbl`, where MP4 keeps the thing that
 * makes it seekable: not the frames, but five parallel tables describing where
 * every frame is and when it plays.
 *
 * ```
 * moov
 *  └ trak                 one per stream; the one whose hdlr is "vide"
 *     └ mdia
 *        ├ mdhd           timescale — how many units are in a second
 *        └ minf > stbl
 *           ├ stsd        the codec, and its setup bytes (avcC / hvcC / …)
 *           ├ stts        how long each sample lasts, run-length encoded
 *           ├ ctts        how far presentation moves from decode (B-frames)
 *           ├ stss        which samples can be decoded from cold
 *           ├ stsz        how big each sample is
 *           ├ stsc        how samples are grouped into chunks
 *           └ stco/co64   where each chunk starts in the file
 * ```
 *
 * None of it is difficult and all of it is fiddly, which is why the tables are
 * expanded into one flat list of frames here and never consulted again.
 */

import { DemuxError, type FrameRef, type VideoTrack } from "./index";
import { fillDurations } from "./matroska";

interface Box {
  type: string;
  /** Payload, not including the header. */
  start: number;
  end: number;
}

/** Walk one level of the box tree. */
function* boxes(view: DataView, from: number, to: number): Generator<Box> {
  let at = from;
  while (at + 8 <= to) {
    let size = view.getUint32(at, false);
    const type = String.fromCharCode(
      view.getUint8(at + 4),
      view.getUint8(at + 5),
      view.getUint8(at + 6),
      view.getUint8(at + 7)
    );
    let body = at + 8;
    if (size === 1) {
      // A 64-bit size, which is how files over 4GB are written.
      if (body + 8 > to) return;
      const high = view.getUint32(body, false);
      const low = view.getUint32(body + 4, false);
      size = high * 2 ** 32 + low;
      body += 8;
    } else if (size === 0) {
      size = to - at;
    }
    if (size < 8 || at + size > to) return;
    yield { type, start: body, end: at + size };
    at += size;
  }
}

function find(view: DataView, from: number, to: number, type: string): Box | null {
  for (const box of boxes(view, from, to)) if (box.type === type) return box;
  return null;
}

function hex(view: DataView, at: number, count: number): string {
  let out = "";
  for (let index = 0; index < count; index += 1) out += view.getUint8(at + index).toString(16).padStart(2, "0");
  return out;
}

/**
 * The codec string and setup bytes, from a sample description entry.
 *
 * H.264's is built from the first bytes of its own `avcC`: profile,
 * compatibility flags and level, which is exactly what `avc1.640028` spells
 * out. Guessing it would mean handing the decoder a configuration the file
 * does not have.
 */
function codecFrom(
  view: DataView,
  bytes: Uint8Array,
  entry: Box
): { codec: string; description?: Uint8Array; width: number; height: number } {
  // A visual sample entry is 8 bytes reserved + 70 bytes of fixed fields before
  // its child boxes, with width and height 24 bytes in.
  const width = view.getUint16(entry.start + 24, false);
  const height = view.getUint16(entry.start + 26, false);
  const children = entry.start + 78;

  const avcC = find(view, children, entry.end, "avcC");
  if (avcC) {
    return {
      codec: `avc1.${hex(view, avcC.start + 1, 3)}`,
      description: bytes.slice(avcC.start, avcC.end),
      width,
      height
    };
  }
  const hvcC = find(view, children, entry.end, "hvcC");
  if (hvcC) {
    return {
      codec: "hev1.1.6.L93.B0",
      description: bytes.slice(hvcC.start, hvcC.end),
      width,
      height
    };
  }
  const av1C = find(view, children, entry.end, "av1C");
  if (av1C) {
    return {
      codec: "av01.0.04M.08",
      description: bytes.slice(av1C.start, av1C.end),
      width,
      height
    };
  }
  const vpcC = find(view, children, entry.end, "vpcC");
  if (vpcC) {
    // vpcC is a full box: version and flags, then profile, level, bit depth.
    const profile = view.getUint8(vpcC.start + 4);
    const level = view.getUint8(vpcC.start + 5);
    const depth = view.getUint8(vpcC.start + 6) >> 4;
    const pad = (value: number) => String(value).padStart(2, "0");
    return { codec: `vp09.${pad(profile)}.${pad(level)}.${pad(depth)}`, width, height };
  }
  throw new DemuxError(
    `This MP4's video track is ${entry.type}, which this build cannot decode. ` +
      "H.264, HEVC, VP9 and AV1 are understood."
  );
}

/** `(count, value)` runs, as `stts` and `ctts` both store them. */
function runs(view: DataView, box: Box): Array<[number, number]> {
  const count = view.getUint32(box.start + 4, false);
  const out: Array<[number, number]> = [];
  for (let index = 0; index < count; index += 1) {
    const at = box.start + 8 + index * 8;
    if (at + 8 > box.end) break;
    out.push([view.getUint32(at, false), view.getInt32(at + 4, false)]);
  }
  return out;
}

function sampleSizes(view: DataView, stsz: Box): number[] {
  const uniform = view.getUint32(stsz.start + 4, false);
  const count = view.getUint32(stsz.start + 8, false);
  if (uniform) return new Array(count).fill(uniform);
  const out: number[] = [];
  for (let index = 0; index < count; index += 1) {
    const at = stsz.start + 12 + index * 4;
    if (at + 4 > stsz.end) break;
    out.push(view.getUint32(at, false));
  }
  return out;
}

/** Where every sample starts, from the chunk tables. */
function sampleOffsets(view: DataView, stsc: Box, offsets: number[], sizes: number[]): number[] {
  const entries: Array<{ firstChunk: number; perChunk: number }> = [];
  const count = view.getUint32(stsc.start + 4, false);
  for (let index = 0; index < count; index += 1) {
    const at = stsc.start + 8 + index * 12;
    if (at + 12 > stsc.end) break;
    entries.push({
      firstChunk: view.getUint32(at, false),
      perChunk: view.getUint32(at + 4, false)
    });
  }
  if (!entries.length) throw new DemuxError("This MP4's sample-to-chunk table is empty.");

  const out: number[] = [];
  let sample = 0;
  for (let chunk = 0; chunk < offsets.length && sample < sizes.length; chunk += 1) {
    // The last entry whose firstChunk is at or before this one governs it —
    // the table is run-length encoded over chunks, not a row per chunk.
    let perChunk = entries[0].perChunk;
    for (const item of entries) {
      if (item.firstChunk - 1 <= chunk) perChunk = item.perChunk;
      else break;
    }
    let at = offsets[chunk];
    for (let index = 0; index < perChunk && sample < sizes.length; index += 1) {
      out.push(at);
      at += sizes[sample];
      sample += 1;
    }
  }
  if (out.length < sizes.length) {
    throw new DemuxError(
      `This MP4 describes ${sizes.length} frames but its chunk table only places ${out.length}.`
    );
  }
  return out;
}

function chunkOffsets(view: DataView, stbl: Box): number[] {
  const stco = find(view, stbl.start, stbl.end, "stco");
  const out: number[] = [];
  if (stco) {
    const count = view.getUint32(stco.start + 4, false);
    for (let index = 0; index < count; index += 1) out.push(view.getUint32(stco.start + 8 + index * 4, false));
    return out;
  }
  const co64 = find(view, stbl.start, stbl.end, "co64");
  if (!co64) throw new DemuxError("This MP4 has no chunk offset table, so its frames cannot be located.");
  const count = view.getUint32(co64.start + 4, false);
  for (let index = 0; index < count; index += 1) {
    const at = co64.start + 8 + index * 8;
    out.push(view.getUint32(at, false) * 2 ** 32 + view.getUint32(at + 4, false));
  }
  return out;
}

export function demuxIsoBmff(bytes: Uint8Array): VideoTrack {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const moov = find(view, 0, bytes.length, "moov");
  if (!moov) {
    throw new DemuxError(
      "This MP4 has no moov box. A recording that was interrupted does this — " +
        "the frames are there and the index that finds them was never written."
    );
  }

  for (const trak of boxes(view, moov.start, moov.end)) {
    if (trak.type !== "trak") continue;
    const mdia = find(view, trak.start, trak.end, "mdia");
    if (!mdia) continue;
    const hdlr = find(view, mdia.start, mdia.end, "hdlr");
    if (!hdlr) continue;
    const handler = String.fromCharCode(
      view.getUint8(hdlr.start + 8),
      view.getUint8(hdlr.start + 9),
      view.getUint8(hdlr.start + 10),
      view.getUint8(hdlr.start + 11)
    );
    if (handler !== "vide") continue;

    const mdhd = find(view, mdia.start, mdia.end, "mdhd");
    if (!mdhd) continue;
    const version = view.getUint8(mdhd.start);
    // Version 1 widens creation and modification time to 64 bits, which moves
    // the timescale twelve bytes later. Reading the wrong one turns a
    // thirty-second video into a nine-hour one.
    const timescale = version === 1 ? view.getUint32(mdhd.start + 20, false) : view.getUint32(mdhd.start + 12, false);
    if (!timescale) continue;

    const minf = find(view, mdia.start, mdia.end, "minf");
    const stbl = minf && find(view, minf.start, minf.end, "stbl");
    if (!stbl) continue;

    const stsd = find(view, stbl.start, stbl.end, "stsd");
    const stts = find(view, stbl.start, stbl.end, "stts");
    const stsz = find(view, stbl.start, stbl.end, "stsz");
    const stsc = find(view, stbl.start, stbl.end, "stsc");
    if (!stsd || !stts || !stsz || !stsc) {
      throw new DemuxError("This MP4's sample tables are incomplete, so its frames cannot be located.");
    }

    const entry = [...boxes(view, stsd.start + 8, stsd.end)][0];
    if (!entry) throw new DemuxError("This MP4's video track describes no codec.");
    const { codec, description, width, height } = codecFrom(view, bytes, entry);

    const sizes = sampleSizes(view, stsz);
    const offsets = sampleOffsets(view, stsc, chunkOffsets(view, stbl), sizes);

    // Decode times, from the run-length table.
    const decodeTimes: number[] = [];
    let clock = 0;
    for (const [count, delta] of runs(view, stts)) {
      for (let index = 0; index < count && decodeTimes.length < sizes.length; index += 1) {
        decodeTimes.push(clock);
        clock += delta;
      }
    }
    while (decodeTimes.length < sizes.length) decodeTimes.push(clock);

    // Composition offsets, when there are B-frames. Without ctts, presentation
    // order is decode order.
    const ctts = find(view, stbl.start, stbl.end, "ctts");
    const shifts: number[] = [];
    if (ctts) {
      for (const [count, offset] of runs(view, ctts)) {
        for (let index = 0; index < count && shifts.length < sizes.length; index += 1) shifts.push(offset);
      }
    }
    while (shifts.length < sizes.length) shifts.push(0);

    // Sync samples. No stss at all means every sample is one, which is what a
    // file of all-keyframes says by omission.
    const stss = find(view, stbl.start, stbl.end, "stss");
    const syncs = new Set<number>();
    if (stss) {
      const count = view.getUint32(stss.start + 4, false);
      for (let index = 0; index < count; index += 1) {
        syncs.add(view.getUint32(stss.start + 8 + index * 4, false) - 1);
      }
    }

    const toUs = (units: number) => Math.round((units * 1_000_000) / timescale);
    const frames: FrameRef[] = sizes.map((length, index) => ({
      offset: offsets[index],
      length,
      timestampUs: toUs(decodeTimes[index] + shifts[index]),
      durationUs: 0,
      key: stss ? syncs.has(index) : true
    }));
    if (!frames.length) throw new DemuxError("This MP4 declares a video track and carries no frames.");
    if (!frames[0].key) {
      throw new DemuxError("This MP4's first frame is not a keyframe, so decoding cannot start.");
    }
    fillDurations(frames);
    return { codec, description, width, height, frames, container: "mp4" };
  }

  throw new DemuxError("This MP4 has no video track to draw.");
}
