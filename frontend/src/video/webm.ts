/**
 * A WebM muxer, written by hand.
 *
 * WebCodecs gives encoded frames; it does not give a file. Something has to
 * wrap those frames in a container, and the options were a dependency or two
 * hundred lines of EBML. This project already made that call once, in
 * `imagery/gates.py`, where reading a PNG's width was worth writing rather than
 * worth adding Pillow for. The same answer applies here, and this time there is
 * a second reason.
 *
 * **MediaRecorder cannot say how long its own output is.** It streams, so it
 * writes a WebM whose Duration field is absent — which is why a recording
 * scrubs badly in some players and reports no length until fully buffered. The
 * export gate in `video/gates.py` checks the file's duration against the
 * timeline's, and against a MediaRecorder file that check can only ever say
 * "unknown". Muxing here means the Duration is written exactly, from the
 * timeline that produced it, so the gate has something real to compare.
 *
 * The parser on the other side of this is `_probe_webm` in
 * `offsetx_apollo_builder/video/gates.py`. They are two halves of one format
 * and `tests/test_video_gates.py` reads what this writes.
 */

/** Element ids, written as the raw bytes EBML stores — marker bits included. */
const ID = {
  EBML: [0x1a, 0x45, 0xdf, 0xa3],
  EBMLVersion: [0x42, 0x86],
  EBMLReadVersion: [0x42, 0xf7],
  EBMLMaxIDLength: [0x42, 0xf2],
  EBMLMaxSizeLength: [0x42, 0xf3],
  DocType: [0x42, 0x82],
  DocTypeVersion: [0x42, 0x87],
  DocTypeReadVersion: [0x42, 0x85],
  Segment: [0x18, 0x53, 0x80, 0x67],
  Info: [0x15, 0x49, 0xa9, 0x66],
  TimecodeScale: [0x2a, 0xd7, 0xb1],
  MuxingApp: [0x4d, 0x80],
  WritingApp: [0x57, 0x41],
  Duration: [0x44, 0x89],
  Tracks: [0x16, 0x54, 0xae, 0x6b],
  TrackEntry: [0xae],
  TrackNumber: [0xd7],
  TrackUID: [0x73, 0xc5],
  TrackType: [0x83],
  FlagLacing: [0x9c],
  CodecID: [0x86],
  CodecPrivate: [0x63, 0xa2],
  Video: [0xe0],
  PixelWidth: [0xb0],
  PixelHeight: [0xba],
  Audio: [0xe1],
  SamplingFrequency: [0xb5],
  Channels: [0x9f],
  Cluster: [0x1f, 0x43, 0xb6, 0x75],
  Timecode: [0xe7],
  SimpleBlock: [0xa3]
} as const;

const VIDEO_TRACK = 1;
const AUDIO_TRACK = 2;

/**
 * How long a cluster may run. A SimpleBlock's timecode is a signed 16-bit
 * offset from its cluster, so anything past ~32 seconds cannot be addressed;
 * two is the conventional length and keeps seeking responsive.
 */
const CLUSTER_MS = 2000;

/**
 * The point at which a cluster is cut whether or not a keyframe has arrived.
 *
 * A cluster normally ends at the next video keyframe, which is fine while there
 * is video. An audio-heavy or keyframe-sparse stretch would otherwise run past
 * the 32,767ms a signed 16-bit offset can express, and the blocks after that
 * would be written with wrapped timecodes — a file that parses and plays its
 * sound in the wrong order.
 */
const MAX_CLUSTER_MS = 30_000;

/** Write a variable-length integer: the value, prefixed by its own width. */
function vint(value: number): Uint8Array {
  let width = 1;
  while (width < 8 && value >= 2 ** (7 * width) - 1) width += 1;
  const bytes = new Uint8Array(width);
  let remaining = value;
  for (let index = width - 1; index >= 0; index -= 1) {
    bytes[index] = remaining & 0xff;
    remaining = Math.floor(remaining / 256);
  }
  bytes[0] |= 0x80 >> (width - 1);
  return bytes;
}

function uintBytes(value: number): Uint8Array {
  if (value === 0) return new Uint8Array([0]);
  const bytes: number[] = [];
  let remaining = value;
  while (remaining > 0) {
    bytes.unshift(remaining & 0xff);
    remaining = Math.floor(remaining / 256);
  }
  return new Uint8Array(bytes);
}

function floatBytes(value: number): Uint8Array {
  const buffer = new ArrayBuffer(8);
  new DataView(buffer).setFloat64(0, value, false);
  return new Uint8Array(buffer);
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function element(id: readonly number[], payload: Uint8Array): Uint8Array {
  return concat([new Uint8Array(id), vint(payload.length), payload]);
}

const uintElement = (id: readonly number[], value: number) => element(id, uintBytes(value));
const floatElement = (id: readonly number[], value: number) => element(id, floatBytes(value));
const stringElement = (id: readonly number[], value: string) =>
  element(id, new TextEncoder().encode(value));

/** WebCodecs names a codec in its own vocabulary; Matroska has another. */
export function codecId(codec: string, kind: "video" | "audio"): string {
  const name = (codec || "").toLowerCase();
  if (kind === "video") {
    if (name.startsWith("vp8")) return "V_VP8";
    if (name.startsWith("vp09") || name.startsWith("vp9")) return "V_VP9";
    if (name.startsWith("av01")) return "V_AV1";
    throw new Error(
      `${codec} cannot go in a WebM file. WebM carries VP8, VP9 and AV1; ` +
        "H.264 needs an MP4 container, which this muxer does not write."
    );
  }
  if (name.startsWith("opus")) return "A_OPUS";
  if (name.startsWith("vorbis")) return "A_VORBIS";
  throw new Error(`${codec} cannot go in a WebM file. WebM carries Opus and Vorbis.`);
}

interface PendingBlock {
  track: number;
  timestampMs: number;
  keyframe: boolean;
  data: Uint8Array;
}

export interface WebMOptions {
  width: number;
  height: number;
  videoCodec: string;
  /** Milliseconds. Written into Info so the file states its own length. */
  durationMs: number;
  audio?: {
    codec: string;
    sampleRate: number;
    channels: number;
    /** Opus needs its OpusHead; WebCodecs hands it over as decoderConfig.description. */
    description?: Uint8Array;
  };
}

/**
 * Collects encoded chunks and writes one WebM file.
 *
 * Everything is buffered until `finish()`. That is a deliberate limit — it
 * means an export is bounded by memory rather than streaming — and it buys the
 * thing that matters: a Segment with a known size and a Duration that is
 * correct, which a streaming muxer cannot write because it does not yet know
 * either number.
 */
export class WebMWriter {
  private blocks: PendingBlock[] = [];

  constructor(private readonly options: WebMOptions) {}

  addVideo(chunk: { timestamp: number; type: string; byteLength: number; copyTo(target: Uint8Array): void }): void {
    const data = new Uint8Array(chunk.byteLength);
    chunk.copyTo(data);
    this.blocks.push({
      track: VIDEO_TRACK,
      timestampMs: chunk.timestamp / 1000,
      keyframe: chunk.type === "key",
      data
    });
  }

  addAudio(chunk: { timestamp: number; byteLength: number; copyTo(target: Uint8Array): void }): void {
    const data = new Uint8Array(chunk.byteLength);
    chunk.copyTo(data);
    this.blocks.push({
      track: AUDIO_TRACK,
      timestampMs: chunk.timestamp / 1000,
      keyframe: true,
      data
    });
  }

  get frameCount(): number {
    return this.blocks.filter((block) => block.track === VIDEO_TRACK).length;
  }

  private header(): Uint8Array {
    return element(
      ID.EBML,
      concat([
        uintElement(ID.EBMLVersion, 1),
        uintElement(ID.EBMLReadVersion, 1),
        uintElement(ID.EBMLMaxIDLength, 4),
        uintElement(ID.EBMLMaxSizeLength, 8),
        stringElement(ID.DocType, "webm"),
        uintElement(ID.DocTypeVersion, 2),
        uintElement(ID.DocTypeReadVersion, 2)
      ])
    );
  }

  private info(): Uint8Array {
    return element(
      ID.Info,
      concat([
        // One millisecond per timecode unit, which is what every browser writes
        // and what keeps a SimpleBlock's 16-bit offset covering a whole cluster.
        uintElement(ID.TimecodeScale, 1_000_000),
        stringElement(ID.MuxingApp, "off_CRM"),
        stringElement(ID.WritingApp, "off_CRM video editor"),
        floatElement(ID.Duration, Math.max(0, this.options.durationMs))
      ])
    );
  }

  private tracks(): Uint8Array {
    const entries: Uint8Array[] = [
      element(
        ID.TrackEntry,
        concat([
          uintElement(ID.TrackNumber, VIDEO_TRACK),
          uintElement(ID.TrackUID, VIDEO_TRACK),
          uintElement(ID.TrackType, 1),
          uintElement(ID.FlagLacing, 0),
          stringElement(ID.CodecID, codecId(this.options.videoCodec, "video")),
          element(
            ID.Video,
            concat([
              uintElement(ID.PixelWidth, this.options.width),
              uintElement(ID.PixelHeight, this.options.height)
            ])
          )
        ])
      )
    ];
    const audio = this.options.audio;
    if (audio) {
      entries.push(
        element(
          ID.TrackEntry,
          concat([
            uintElement(ID.TrackNumber, AUDIO_TRACK),
            uintElement(ID.TrackUID, AUDIO_TRACK),
            uintElement(ID.TrackType, 2),
            uintElement(ID.FlagLacing, 0),
            stringElement(ID.CodecID, codecId(audio.codec, "audio")),
            ...(audio.description ? [element(ID.CodecPrivate, audio.description)] : []),
            element(
              ID.Audio,
              concat([
                floatElement(ID.SamplingFrequency, audio.sampleRate),
                uintElement(ID.Channels, audio.channels)
              ])
            )
          ])
        )
      );
    }
    return element(ID.Tracks, concat(entries));
  }

  private simpleBlock(block: PendingBlock, clusterMs: number): Uint8Array {
    const relative = Math.round(block.timestampMs - clusterMs);
    const head = new Uint8Array(3);
    new DataView(head.buffer).setInt16(0, relative, false);
    head[2] = block.keyframe ? 0x80 : 0x00;
    return element(ID.SimpleBlock, concat([vint(block.track), head, block.data]));
  }

  private clusters(): Uint8Array[] {
    const ordered = [...this.blocks].sort((a, b) => a.timestampMs - b.timestampMs);
    const out: Uint8Array[] = [];
    let current: PendingBlock[] = [];
    let clusterMs = 0;
    const flush = () => {
      if (!current.length) return;
      out.push(
        element(
          ID.Cluster,
          concat([
            uintElement(ID.Timecode, clusterMs),
            ...current.map((block) => this.simpleBlock(block, clusterMs))
          ])
        )
      );
      current = [];
    };
    for (const block of ordered) {
      const since = block.timestampMs - clusterMs;
      const startsCluster =
        !current.length ||
        (block.track === VIDEO_TRACK && block.keyframe && since >= CLUSTER_MS) ||
        since >= MAX_CLUSTER_MS;
      if (startsCluster && current.length) flush();
      // Rounded on the way in rather than on the way out: the Timecode element
      // holds a whole millisecond, and computing a block's offset against the
      // unrounded value would put every block in the cluster up to half a
      // millisecond away from where it says it is.
      if (!current.length) clusterMs = Math.round(block.timestampMs);
      current.push(block);
    }
    flush();
    return out;
  }

  /** The finished file. */
  finish(): Uint8Array {
    if (!this.blocks.length) {
      throw new Error(
        "Nothing was encoded, so there is no file to write. An export that " +
          "produced no frames is a failure worth reporting, not an empty video."
      );
    }
    const segment = element(ID.Segment, concat([this.info(), this.tracks(), ...this.clusters()]));
    return concat([this.header(), segment]);
  }

  blob(): Blob {
    const bytes = this.finish();
    return new Blob([bytes as unknown as BlobPart], { type: "video/webm" });
  }
}
