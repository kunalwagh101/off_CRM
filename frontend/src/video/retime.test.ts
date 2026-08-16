import { describe, expect, it } from "vitest";
import conformance from "../../../tests/fixtures/timeline_conformance.json";
import type { Clip, ProjectDoc } from "./document";
import { TICKS_PER_SECOND } from "./document";
import { retimedReason, planMix, type MixPlan } from "./mixdown";
import { consumed, frameAt, sourceAt } from "./resolve";

/**
 * Time remapping, in the browser's copy of the resolver.
 *
 * `resolve.test.ts` already pins every frame of the conformance document, and
 * that document now carries a clip that is both on a `hero` curve and reversed
 * — so the exact agreement is already covered there. These are the properties
 * that make the arithmetic *readable*: that a ramp is the area under it, that
 * a held section consumes nothing, that reverse walks the same span backwards.
 *
 * They matter here rather than only in Python because this is the copy that
 * decides which frame the exporter draws.
 */

const SECOND = TICKS_PER_SECOND;
const fixture = conformance as unknown as { document: ProjectDoc; mix: MixPlan };

function clip(overrides: Partial<Clip> = {}): Clip {
  return {
    id: "clip-1",
    kind: "video",
    start: 0,
    duration: 10 * SECOND,
    in_point: 0,
    source_duration: 30 * SECOND,
    asset_id: "footage-1",
    text: "",
    speed: 1,
    fade_in: 0,
    fade_out: 0,
    label: "",
    properties: {},
    keyframes: {},
    style: {},
    ...overrides
  } as Clip;
}

describe("the integral under a speed curve", () => {
  it("is a plain multiplication at one rate", () => {
    const plain = clip();
    for (const at of [0, 1, SECOND, 5 * SECOND, 10 * SECOND]) {
      expect(consumed(plain, at)).toBe(at);
      expect(sourceAt(plain, at)).toBe(at);
    }
  });

  it("is the area under a ramp, not the average of its ends", () => {
    // 0.5 rising to 2.0 over ten seconds: (0.5 + 2.0) / 2 * 10s = 12.5s.
    const ramped = clip({
      speed_curve: [
        { at: 0, value: 0.5, easing: "linear" },
        { at: 10 * SECOND, value: 2.0, easing: "linear" }
      ]
    });
    expect(consumed(ramped, 10 * SECOND)).toBeCloseTo(12.5 * SECOND, 3);
    // Speed at 5s is 1.25, so the area to there is (0.5 + 1.25) / 2 * 5s.
    expect(consumed(ramped, 5 * SECOND)).toBeCloseTo(4.375 * SECOND, 3);
  });

  it("consumes nothing at all through a held section", () => {
    const held = clip({
      speed_curve: [
        { at: 0, value: 2, easing: "linear" },
        { at: 2 * SECOND, value: 0, easing: "linear" },
        { at: 6 * SECOND, value: 0, easing: "linear" },
        { at: 10 * SECOND, value: 2, easing: "linear" }
      ]
    });
    expect(consumed(held, 6 * SECOND) - consumed(held, 2 * SECOND)).toBe(0);
  });

  it("holds the first and last speeds rather than extrapolating them", () => {
    const inner = clip({
      speed_curve: [
        { at: 2 * SECOND, value: 2, easing: "linear" },
        { at: 4 * SECOND, value: 2, easing: "linear" }
      ]
    });
    expect(consumed(inner, 2 * SECOND)).toBeCloseTo(4 * SECOND, 3);
    expect(consumed(inner, 10 * SECOND)).toBeCloseTo(20 * SECOND, 3);
  });

  it("never reads outside the clip's own length", () => {
    const plain = clip();
    expect(consumed(plain, -5000)).toBe(0);
    expect(consumed(plain, 99 * SECOND)).toBe(consumed(plain, 10 * SECOND));
  });
});

describe("reverse", () => {
  it("starts at the far end and finishes at the in-point", () => {
    const backward = clip({ reversed: true });
    expect(sourceAt(backward, 0)).toBe(10 * SECOND);
    expect(sourceAt(backward, 10 * SECOND)).toBe(0);
  });

  it("keeps the in-point as the place it finishes", () => {
    const backward = clip({ reversed: true, in_point: 2 * SECOND });
    expect(sourceAt(backward, 10 * SECOND)).toBe(2 * SECOND);
    expect(sourceAt(backward, 0)).toBe(12 * SECOND);
  });

  it("moves one way the whole time, even on a curve", () => {
    const both = clip({
      reversed: true,
      speed_curve: [
        { at: 0, value: 2.5, easing: "linear" },
        { at: 3 * SECOND, value: 0.5, easing: "linear" },
        { at: 7 * SECOND, value: 0.5, easing: "linear" },
        { at: 10 * SECOND, value: 2.5, easing: "linear" }
      ]
    });
    const times: number[] = [];
    for (let at = 0; at <= 10 * SECOND; at += SECOND) times.push(sourceAt(both, at));
    expect([...times].sort((a, b) => b - a)).toEqual(times);
    expect(sourceAt(both, 10 * SECOND)).toBe(0);
  });
});

describe("agreement with the server, on the awkward clip", () => {
  it("resolves the fixture's retimed clip exactly where Python does", () => {
    // The frames are already compared byte for byte in `resolve.test.ts`; this
    // names the clip so a fixture rebuilt without it fails loudly rather than
    // quietly losing the only coverage time remapping has.
    const retimed = fixture.document.tracks
      .flatMap((track) => track.clips)
      .find((item) => item.id === "clip_retimed");
    expect(retimed, "the conformance document lost its retimed clip").toBeDefined();
    expect(retimed!.reversed).toBe(true);
    expect(retimed!.speed_curve?.length).toBeGreaterThan(2);

    const first = frameAt(fixture.document, retimed!.start).items.find(
      (item) => item.clip_id === "clip_retimed"
    );
    // Reversed, so its first drawn frame is the *last* instant it will read.
    expect(first!.source_time).toBe(Math.round(consumed(retimed!, retimed!.duration)));
  });
});

describe("what the mix leaves out", () => {
  it("says why a retimed clip is silent rather than playing it at one rate", () => {
    expect(retimedReason(clip())).toBe("");
    expect(retimedReason(clip({ reversed: true }))).toBe("it plays backwards");
    expect(retimedReason(clip({ speed: 0 }))).toBe("it is frozen on one instant");
    expect(
      retimedReason(
        clip({
          speed_curve: [
            { at: 0, value: 1, easing: "linear" },
            { at: SECOND, value: 2, easing: "linear" }
          ]
        })
      )
    ).toBe("its speed changes over its own length");
  });

  it("agrees with the server about which of the fixture's clips are excluded", () => {
    const plan = planMix(fixture.document);
    expect(plan.excluded).toEqual(fixture.mix.excluded);
    expect(plan.excluded.length).toBeGreaterThan(0);
    for (const [clipId] of plan.excluded) {
      expect(plan.clips.some((item) => item.clip_id === clipId)).toBe(false);
    }
  });
});
