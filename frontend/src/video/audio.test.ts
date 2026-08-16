import { describe, expect, it } from "vitest";
import { opusHead, placements, renderMix, type SourcePlacement } from "./audio";
import { TICKS_PER_SECOND } from "./document";
import type { MixPlan } from "./mixdown";

/**
 * The audio side of the export, minus the browser.
 *
 * Two things are worth testing here and the rest is WebAudio's job. First, the
 * conversion from timeline time to source time — a clip's `speed` means "source
 * consumed per tick", so a half-speed clip plays half as much material over the
 * same stretch, and getting that backwards produces something that sounds
 * plausible for about a second. Second, the graph is wired the way it says it
 * is: the right ramps on the right node, and the master gain actually turned
 * down when the mix would clip.
 */

const SECOND = TICKS_PER_SECOND;

function plan(overrides: Partial<MixPlan> = {}): MixPlan {
  return {
    duration_ticks: 5 * SECOND,
    sample_rate: 48_000,
    channels: 2,
    silent: false,
    headroom: 1,
    clips: [],
    asset_ids: [],
    ...overrides
  };
}

function clip(overrides: Partial<MixPlan["clips"][number]> = {}) {
  return {
    clip_id: "clip-1",
    asset_id: "asset-1",
    kind: "audio",
    start: 0,
    duration: 4 * SECOND,
    in_point: 0,
    speed: 1,
    envelope: [
      [0, 1],
      [4 * SECOND, 1]
    ] as Array<[number, number]>,
    ...overrides
  };
}

describe("where each clip plays", () => {
  it("puts a plain clip at its own start, for its own length", () => {
    const [item] = placements(plan({ clips: [clip()] }));
    expect(item.when).toBe(0);
    expect(item.offset).toBe(0);
    expect(item.duration).toBe(4);
    expect(item.playbackRate).toBe(1);
  });

  it("reads twice as much material for a clip played at double speed", () => {
    const [item] = placements(plan({ clips: [clip({ speed: 2 })] }));
    expect(item.playbackRate).toBe(2);
    // Four seconds of timeline at double speed consumes eight of source, and
    // WebAudio measures `start`'s duration argument in the buffer's own time.
    expect(item.duration).toBe(8);
  });

  it("reads half as much for a clip slowed down", () => {
    const [item] = placements(plan({ clips: [clip({ speed: 0.5 })] }));
    expect(item.duration).toBe(2);
  });

  it("starts reading at the trim point, in source seconds", () => {
    const [item] = placements(plan({ clips: [clip({ in_point: 3 * SECOND })] }));
    expect(item.offset).toBe(3);
  });

  it("refuses to divide by a speed of zero", () => {
    const [item] = placements(plan({ clips: [clip({ speed: 0 })] }));
    expect(item.playbackRate).toBe(1);
    expect(Number.isFinite(item.duration)).toBe(true);
  });

  it("puts every ramp on the output timeline, not the clip's own", () => {
    const [item] = placements(
      plan({
        clips: [
          clip({
            start: 2 * SECOND,
            envelope: [
              [0, 0],
              [SECOND, 1],
              [4 * SECOND, 0]
            ]
          })
        ]
      })
    );
    expect(item.ramps).toEqual([
      { at: 2, gain: 0 },
      { at: 3, gain: 1 },
      { at: 6, gain: 0 }
    ]);
  });
});

// ── the graph ───────────────────────────────────────────────────────────────

interface RecordedParam {
  sets: Array<[number, number]>;
  ramps: Array<[number, number]>;
  value: number;
}

class FakeParam implements RecordedParam {
  sets: Array<[number, number]> = [];
  ramps: Array<[number, number]> = [];
  value = 1;
  setValueAtTime(value: number, at: number) {
    this.sets.push([value, at]);
  }
  linearRampToValueAtTime(value: number, at: number) {
    this.ramps.push([value, at]);
  }
}

class FakeGain {
  gain = new FakeParam();
  connectedTo: unknown = null;
  connect(target: unknown) {
    this.connectedTo = target;
  }
}

class FakeSource {
  buffer: unknown = null;
  playbackRate = new FakeParam();
  started: Array<[number, number, number]> = [];
  connectedTo: unknown = null;
  connect(target: unknown) {
    this.connectedTo = target;
  }
  start(when: number, offset: number, duration: number) {
    this.started.push([when, offset, duration]);
  }
}

class FakeContext {
  destination = { name: "destination" };
  gains: FakeGain[] = [];
  sources: FakeSource[] = [];
  constructor(
    readonly channels: number,
    readonly length: number,
    readonly sampleRate: number
  ) {}
  createGain() {
    const node = new FakeGain();
    this.gains.push(node);
    return node;
  }
  createBufferSource() {
    const node = new FakeSource();
    this.sources.push(node);
    return node;
  }
  async startRendering() {
    return { rendered: true } as unknown as AudioBuffer;
  }
}

function withFakeAudio<T>(run: (contexts: FakeContext[]) => T): T {
  const scope = globalThis as Record<string, unknown>;
  const original = scope.OfflineAudioContext;
  const contexts: FakeContext[] = [];
  scope.OfflineAudioContext = class extends FakeContext {
    constructor(channels: number, length: number, sampleRate: number) {
      super(channels, length, sampleRate);
      contexts.push(this);
    }
  };
  try {
    return run(contexts);
  } finally {
    scope.OfflineAudioContext = original;
  }
}

const buffers = new Map<string, AudioBuffer>([["asset-1", {} as AudioBuffer]]);

describe("wiring the offline graph", () => {
  it("makes a context long enough to hold the whole timeline", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(plan({ clips: [clip()] }), buffers);
      expect(contexts[0].length).toBe(5 * 48_000);
      expect(contexts[0].sampleRate).toBe(48_000);
      expect(contexts[0].channels).toBe(2);
    });
  });

  it("sets the first envelope point outright and ramps to the rest", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(
        plan({
          clips: [
            clip({
              envelope: [
                [0, 0],
                [SECOND, 1],
                [4 * SECOND, 0.25]
              ]
            })
          ]
        }),
        buffers
      );
      // The first gain node is the master; the clip's is the second.
      const node = contexts[0].gains[1];
      expect(node.gain.sets).toEqual([[0, 0]]);
      expect(node.gain.ramps).toEqual([
        [1, 1],
        [0.25, 4]
      ]);
    });
  });

  it("turns the whole mix down by exactly the amount it would have clipped", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(plan({ clips: [clip()], headroom: 2 }), buffers, 2);
      expect(contexts[0].gains[0].gain.value).toBe(0.5);
    });
  });

  it("leaves a mix that does not clip at full level", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(plan({ clips: [clip()] }), buffers, 1);
      expect(contexts[0].gains[0].gain.value).toBe(1);
    });
  });

  it("skips a clip whose asset would not decode rather than failing the render", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(
        plan({ clips: [clip(), clip({ clip_id: "clip-2", asset_id: "missing" })] }),
        buffers
      );
      expect(contexts[0].sources.length).toBe(1);
    });
  });

  it("routes every clip through its own gain into the master", async () => {
    await withFakeAudio(async (contexts) => {
      await renderMix(plan({ clips: [clip()] }), buffers);
      const [master, clipGainNode] = contexts[0].gains;
      expect(master.connectedTo).toBe(contexts[0].destination);
      expect(clipGainNode.connectedTo).toBe(master);
      expect(contexts[0].sources[0].connectedTo).toBe(clipGainNode);
      expect(contexts[0].sources[0].started).toEqual([[0, 0, 4]]);
    });
  });
});

// ── the container's idea of Opus ────────────────────────────────────────────

describe("the OpusHead written when the encoder supplies none", () => {
  const head = opusHead(2, 48_000);

  it("is the nineteen bytes Matroska expects", () => {
    expect(head.length).toBe(19);
    expect(new TextDecoder().decode(head.subarray(0, 8))).toBe("OpusHead");
    expect(head[8]).toBe(1);
  });

  it("states the channel count and rate a demuxer reads back", () => {
    const view = new DataView(head.buffer, head.byteOffset, head.byteLength);
    expect(view.getUint8(9)).toBe(2);
    expect(view.getUint32(12, true)).toBe(48_000);
    expect(view.getInt16(16, true)).toBe(0);
    expect(view.getUint8(18)).toBe(0);
  });

  it("follows the channel count it was given", () => {
    expect(opusHead(1, 48_000)[9]).toBe(1);
  });
});

// ── type-level guard ────────────────────────────────────────────────────────

describe("the placement contract", () => {
  it("names its units, because seconds and ticks look identical in a number", () => {
    const item: SourcePlacement = placements(plan({ clips: [clip({ start: SECOND })] }))[0];
    expect(item.when).toBe(1);
    expect(item.clipId).toBe("clip-1");
    expect(item.assetId).toBe("asset-1");
  });
});
