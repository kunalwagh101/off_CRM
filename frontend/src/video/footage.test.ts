import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { demuxVideo } from "./demux";
import { TICKS_PER_SECOND } from "./document";
import { Footage, FootageLibrary } from "./footage";

/**
 * Which frame you get, and how much work it took to get it.
 *
 * The demuxer's tests prove the index is right. These prove the thing built on
 * top of it: that "the clip is 1.4 seconds into its material" lands on the
 * frame that actually covers 1.4 seconds, and that asking for frames in order —
 * which is what an export does — decodes each one exactly once instead of
 * seeking back to a keyframe for every single one.
 *
 * The decoder is a stand-in. A real `VideoDecoder` is a codec, and what is
 * under test here is not the codec: it is the cursor, the seek decision and the
 * frame cache around it. The real one is exercised end to end in a browser
 * instead — see `docs/architecture/VIDEO_EDITOR.md`.
 */

const FIXTURES = resolve(__dirname, "../../../tests/fixtures");
const SECOND = TICKS_PER_SECOND;

/** Every chunk the fake decoder was handed, in order. */
let fed: Array<{ type: string; timestamp: number }> = [];
/** How many times a decoder was created — one per seek that could not be
 *  served by running forwards. */
let starts = 0;
let closed = 0;

class FakeFrame {
  closedOnce = false;
  constructor(
    readonly timestamp: number,
    readonly displayWidth: number,
    readonly displayHeight: number
  ) {}
  close() {
    this.closedOnce = true;
    closed += 1;
  }
}

class FakeDecoder {
  decodeQueueSize = 0;
  private config: Record<string, unknown> = {};
  constructor(private readonly init: { output: (frame: FakeFrame) => void; error: (e: Error) => void }) {
    starts += 1;
  }
  configure(config: Record<string, unknown>) {
    this.config = config;
  }
  decode(chunk: { type: string; timestamp: number }) {
    fed.push({ type: chunk.type, timestamp: chunk.timestamp });
    // A real decoder is asynchronous; this one is too, so the pump's
    // wait-for-output path is the one being exercised.
    this.decodeQueueSize += 1;
    queueMicrotask(() => {
      this.decodeQueueSize -= 1;
      this.init.output(
        new FakeFrame(chunk.timestamp, Number(this.config.codedWidth), Number(this.config.codedHeight))
      );
    });
  }
  async flush() {
    await new Promise((done) => setTimeout(done, 0));
  }
  reset() {}
  close() {}
}

beforeEach(() => {
  fed = [];
  starts = 0;
  closed = 0;
  const scope = globalThis as Record<string, unknown>;
  scope.VideoDecoder = FakeDecoder;
  (scope.VideoDecoder as unknown as Record<string, unknown>).isConfigSupported = async () => ({
    supported: true
  });
  scope.EncodedVideoChunk = class {
    type: string;
    timestamp: number;
    constructor(init: { type: string; timestamp: number }) {
      this.type = init.type;
      this.timestamp = init.timestamp;
    }
  };
});

afterEach(() => {
  const scope = globalThis as Record<string, unknown>;
  delete scope.VideoDecoder;
  delete scope.EncodedVideoChunk;
});

function webm(): Uint8Array {
  return new Uint8Array(readFileSync(resolve(FIXTURES, "muxed_sample.webm")));
}

/**
 * The fixture is 90 frames at 30fps — 3 seconds, keyframes at 0 and 60.
 *
 * Frame times come from the file rather than from `n / 30`. Matroska stores
 * whole milliseconds, so frame *n* sits at `round(n * 1000 / 30)` ms and not at
 * `n / 30` seconds, and the two disagree by enough that a third of the evenly
 * spaced instants land on the previous frame. Asking the file where its frames
 * are is both correct and the thing actually worth asserting.
 */
const PRESENTATION = [...demuxVideo(webm()).frames].sort((a, b) => a.timestampUs - b.timestampUs);

/** The tick at which frame `n` begins. */
function tickOf(n: number): number {
  return Math.round((PRESENTATION[n].timestampUs / 1_000_000) * SECOND);
}

async function open(): Promise<Footage> {
  return Footage.open("asset-1", webm());
}

describe("finding the frame that covers an instant", () => {
  it("gives frame 0 at the very start", async () => {
    const source = await open();
    const frame = await source.frameAt(0);
    expect(frame?.timestamp).toBe(0);
    source.close();
  });

  it("holds a frame until the next one begins", async () => {
    const source = await open();
    // Anywhere inside frame 0's own span is still frame 0, right up to the
    // tick frame 1 starts on.
    for (const ticks of [0, 1, tickOf(1) - 1]) {
      expect((await source.frameAt(ticks))?.timestamp, `at ${ticks}`).toBe(0);
    }
    expect((await source.frameAt(tickOf(1)))?.timestamp).toBe(PRESENTATION[1].timestampUs);
    source.close();
  });

  it("lands on the right frame well into the file", async () => {
    const source = await open();
    const frame = await source.frameAt(tickOf(45));
    // 45 frames in at 30fps is 1.5 seconds, to within the muxer's millisecond.
    expect((frame!.timestamp ?? 0) / 1_000_000).toBeCloseTo(1.5, 2);
    source.close();
  });

  it("reports the source's own size, which the painter fits to the canvas", async () => {
    const source = await open();
    const frame = await source.frameAt(0);
    expect(frame?.displayWidth).toBe(1080);
    expect(frame?.displayHeight).toBe(1920);
    expect(source.width).toBe(1080);
    source.close();
  });

  it("returns nothing past the end rather than the last frame forever", async () => {
    const source = await open();
    expect(await source.frameAt(10 * SECOND)).toBeNull();
    source.close();
  });

  it("knows how long the material is", async () => {
    const source = await open();
    expect(source.durationTicks / SECOND).toBeCloseTo(3, 1);
    source.close();
  });
});

describe("how much work each answer costs", () => {
  it("decodes each frame exactly once when asked in order", async () => {
    // The export case, and the reason the whole thing is built around a cursor.
    const source = await open();
    for (let index = 0; index < 30; index += 1) await source.frameAt(tickOf(index));
    expect(fed.length).toBe(30);
    expect(starts).toBe(1);
    source.close();
  });

  it("does not re-decode a frame it is already holding", async () => {
    const source = await open();
    await source.frameAt(0);
    const before = fed.length;
    await source.frameAt(1);
    await source.frameAt(2);
    expect(fed.length).toBe(before);
    source.close();
  });

  it("runs forward from where it is rather than starting again", async () => {
    const source = await open();
    await source.frameAt(0);
    await source.frameAt(tickOf(20));
    // Frames 0..20 inclusive, and only one decoder for all of them.
    expect(fed.length).toBe(21);
    expect(starts).toBe(1);
    source.close();
  });

  it("starts again from a keyframe when asked to go backwards", async () => {
    const source = await open();
    await source.frameAt(tickOf(50));
    const forward = fed.length;
    fed = [];
    await source.frameAt(tickOf(10));
    expect(starts).toBe(2);
    // From frame 0, because that is the keyframe covering frame 10 — not from
    // frame 10, which cannot be decoded on its own.
    expect(fed[0].type).toBe("key");
    expect(fed[0].timestamp).toBe(0);
    expect(fed.length).toBe(11);
    expect(forward).toBe(51);
    source.close();
  });

  it("seeks into a later group from its own keyframe, not from the file's", async () => {
    const source = await open();
    await source.frameAt(tickOf(70));
    // Keyframes are at 0 and 60, so the second group costs 11 frames and not 71.
    expect(fed.length).toBe(11);
    expect(fed[0].type).toBe("key");
    source.close();
  });

  it("holds a bounded number of frames however far it runs", async () => {
    const source = await open();
    for (let index = 0; index < 60; index += 1) await source.frameAt(tickOf(index));
    // 60 decoded, and all but a dozen given back.
    expect(closed).toBeGreaterThan(40);
    source.close();
  });

  it("serialises overlapping requests instead of crossing its own cursor", async () => {
    // What a scrubbing preview does: ask again before the last answer arrives.
    const source = await open();
    const answers = await Promise.all([
      source.frameAt(tickOf(0)),
      source.frameAt(tickOf(5)),
      source.frameAt(tickOf(2))
    ]);
    expect(answers.map((frame) => frame!.timestamp)).toEqual([
      PRESENTATION[0].timestampUs,
      PRESENTATION[5].timestampUs,
      PRESENTATION[2].timestampUs
    ]);
    source.close();
  });
});

describe("two clips of one file", () => {
  it("each read from their own point without dragging the other about", async () => {
    const source = await open();
    const second = source.fork();
    const early = await source.frameAt(0);
    const late = await second.frameAt(tickOf(70));
    expect(early!.timestamp).toBe(0);
    expect(late!.timestamp).toBeGreaterThan(0);
    // The first reader still holds its own frame; the fork did not move it.
    expect((await source.frameAt(0))!.timestamp).toBe(0);
    source.close();
    second.close();
  });
});

describe("the library", () => {
  it("fetches a file once however many clips use it", async () => {
    let fetches = 0;
    const scope = globalThis as Record<string, unknown>;
    scope.fetch = async () => {
      fetches += 1;
      return { ok: true, arrayBuffer: async () => webm().buffer } as unknown as Response;
    };
    const library = await FootageLibrary.load(
      [
        { clipId: "clip-a", assetId: "asset-1" },
        { clipId: "clip-b", assetId: "asset-1" }
      ],
      (id) => `/media/${id}`
    );
    expect(fetches).toBe(1);
    expect(library.size).toBe(2);
    expect(library.has("clip-a") && library.has("clip-b")).toBe(true);
    library.close();
    delete scope.fetch;
  });

  it("reports a file it could not read instead of failing the whole render", async () => {
    const scope = globalThis as Record<string, unknown>;
    scope.fetch = async (url: string) =>
      (String(url).includes("bad")
        ? { ok: false, status: 404 }
        : { ok: true, arrayBuffer: async () => webm().buffer }) as unknown as Response;
    const library = await FootageLibrary.load(
      [
        { clipId: "clip-a", assetId: "good" },
        { clipId: "clip-b", assetId: "bad" }
      ],
      (id) => `/media/${id}`
    );
    expect(library.size).toBe(1);
    expect(library.has("clip-a")).toBe(true);
    expect(library.problems).toHaveLength(1);
    expect(library.problems[0].assetId).toBe("bad");
    expect(library.problems[0].reason).toContain("404");
    library.close();
    delete scope.fetch;
  });

  it("takes each clip's source time from the frame resolved half a step later", async () => {
    // The exporter samples the middle of an output frame rather than its
    // leading edge. It has to do that by resolving a second frame, not by
    // adding half a frame times the clip's speed: a reversed clip moves
    // backwards through its material and a curved one moves at a rate that is
    // different at every instant, so the arithmetic version is wrong in both
    // directions. A real browser found this; this keeps it found.
    const scope = globalThis as Record<string, unknown>;
    scope.fetch = async () =>
      ({ ok: true, arrayBuffer: async () => webm().buffer }) as unknown as Response;
    const library = await FootageLibrary.load(
      [{ clipId: "clip-a", assetId: "asset-1" }],
      (id) => `/media/${id}`
    );
    const table = new Map();
    const draw = (sourceTime: number) => ({
      tick: 0,
      items: [
        {
          clip_id: "clip-a",
          track_id: "t",
          kind: "video",
          z: 0,
          asset_id: "asset-1",
          text: "",
          source_time: sourceTime,
          clip_time: 0,
          speed: 1,
          opacity: 1,
          gain: 0,
          properties: {},
          style: {},
          transition: {}
        }
      ]
    });

    // Frame 0's leading edge, with the half-step landing on frame 4's time —
    // a jump no multiplication by `speed` would have produced.
    await library.apply(draw(0) as never, table, draw(tickOf(4)) as never);
    const asset = table.get("clip-a") as { source: { timestamp: number } };
    expect(asset.source.timestamp).toBe(PRESENTATION[4].timestampUs);

    // And with no second frame it falls back to the one it was given.
    await library.apply(draw(tickOf(2)) as never, table);
    const fallback = table.get("clip-a") as { source: { timestamp: number } };
    expect(fallback.source.timestamp).toBe(PRESENTATION[2].timestampUs);

    library.close();
    delete scope.fetch;
  });

  it("names every video clip a document needs footage for", () => {
    const project = {
      tracks: [
        {
          clips: [
            { id: "c1", kind: "video", asset_id: "a1" },
            { id: "c2", kind: "image", asset_id: "a2" },
            { id: "c3", kind: "video", asset_id: "" }
          ]
        },
        { clips: [{ id: "c4", kind: "video", asset_id: "a1" }] }
      ]
    };
    expect(FootageLibrary.needs(project as never)).toEqual([
      { clipId: "c1", assetId: "a1" },
      { clipId: "c4", assetId: "a1" }
    ]);
  });
});

describe("the index the demuxer hands over", () => {
  it("covers the whole file with no gaps between frames", async () => {
    const track = demuxVideo(webm());
    const ordered = [...track.frames].sort((a, b) => a.timestampUs - b.timestampUs);
    for (let index = 0; index < ordered.length - 1; index += 1) {
      const end = ordered[index].timestampUs + ordered[index].durationUs;
      expect(end, `frame ${index} leaves a gap`).toBe(ordered[index + 1].timestampUs);
    }
  });
});
