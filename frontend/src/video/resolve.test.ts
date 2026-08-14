import { describe, expect, it } from "vitest";
import conformance from "../../../tests/fixtures/timeline_conformance.json";
import type { Frame, ProjectDoc } from "./document";
import { formatTimecode, ticksPerFrame } from "./document";
import { assetIds, frameAt, interpolate, projectDuration, roundHalfToEven } from "./resolve";

/**
 * The conformance check.
 *
 * The fixture is written by `scripts/build_timeline_fixture.py` from the
 * server's resolver. `tests/test_video_timeline.py` asserts Python still
 * produces it; this asserts the browser produces the same thing. Neither side
 * can move without the other noticing, which is the only defence against a
 * preview that quietly stops matching its own export.
 */
const fixture = conformance as unknown as {
  ticks_per_second: number;
  document: ProjectDoc;
  frames: Frame[];
};

describe("timeline conformance with the server resolver", () => {
  it("agrees on every sampled frame", () => {
    expect(fixture.frames.length).toBeGreaterThan(10);
    for (const expected of fixture.frames) {
      const actual = frameAt(fixture.document, expected.tick);
      expect(actual.items.map((item) => item.clip_id)).toEqual(
        expected.items.map((item) => item.clip_id)
      );
      for (let index = 0; index < expected.items.length; index += 1) {
        const want = expected.items[index];
        const got = actual.items[index];
        const where = `tick ${expected.tick} clip ${want.clip_id}`;
        expect(got.kind, where).toBe(want.kind);
        expect(got.z, where).toBe(want.z);
        expect(got.asset_id, where).toBe(want.asset_id);
        expect(got.text, where).toBe(want.text);
        expect(got.source_time, where).toBe(want.source_time);
        expect(got.clip_time, where).toBe(want.clip_time);
        expect(got.opacity, where).toBeCloseTo(want.opacity, 6);
        expect(got.gain, where).toBeCloseTo(want.gain, 6);
        expect(got.style, where).toEqual(want.style);
        for (const [name, value] of Object.entries(want.properties)) {
          expect(got.properties[name], `${where} ${name}`).toBeCloseTo(value, 6);
        }
      }
    }
  });

  it("resolves the document the fixture was built from", () => {
    expect(projectDuration(fixture.document)).toBe(fixture.document.duration);
    expect(fixture.ticks_per_second).toBe(90_000);
    expect(assetIds(fixture.document)).toEqual(["asset_still", "asset_music", "asset_clip"]);
  });

  it("keeps a hidden track's sound and takes away only its picture", () => {
    const frame = frameAt(fixture.document, 45_000);
    const hidden = frame.items.find((item) => item.clip_id === "clip_hidden");
    expect(hidden).toBeDefined();
    expect(hidden?.opacity).toBe(0);
  });

  it("ends the timeline exactly, with nothing live one tick past the end", () => {
    expect(frameAt(fixture.document, fixture.document.duration - 1).items.length).toBeGreaterThan(0);
    expect(frameAt(fixture.document, fixture.document.duration).items).toEqual([]);
  });
});

describe("interpolation", () => {
  it("holds before the first keyframe and after the last", () => {
    const frames = [
      { at: 1000, value: 2, easing: "linear" as const },
      { at: 3000, value: 6, easing: "linear" as const }
    ];
    expect(interpolate(frames, 0)).toBe(2);
    expect(interpolate(frames, 2000)).toBe(4);
    expect(interpolate(frames, 9999)).toBe(6);
  });

  it("treats hold as a step, not a ramp", () => {
    const frames = [
      { at: 0, value: 0, easing: "hold" as const },
      { at: 100, value: 1, easing: "linear" as const }
    ];
    expect(interpolate(frames, 99)).toBe(0);
    expect(interpolate(frames, 100)).toBe(1);
  });

  it("returns zero for a property with no keyframes at all", () => {
    expect(interpolate([], 500)).toBe(0);
  });
});

describe("matching Python's arithmetic", () => {
  it("breaks rounding ties to even, the way Python does", () => {
    expect(roundHalfToEven(0.5)).toBe(0);
    expect(roundHalfToEven(1.5)).toBe(2);
    expect(roundHalfToEven(2.5)).toBe(2);
    expect(roundHalfToEven(-1.5)).toBe(-2);
    expect(roundHalfToEven(2.4)).toBe(2);
    expect(roundHalfToEven(2.6)).toBe(3);
  });

  it("knows the tick length of every frame rate it offers", () => {
    expect(ticksPerFrame("30")).toBe(3000);
    expect(ticksPerFrame("24")).toBe(3750);
    expect(ticksPerFrame("25")).toBe(3600);
    expect(ticksPerFrame("29.97")).toBeCloseTo(3003, 6);
    expect(() => ticksPerFrame("48")).toThrow();
  });

  it("formats a timecode a person can read", () => {
    expect(formatTimecode(0)).toBe("0:00.00");
    expect(formatTimecode(90_000)).toBe("0:01.00");
    expect(formatTimecode(5_490_000)).toBe("1:01.00");
  });
});
