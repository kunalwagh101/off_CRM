import { describe, expect, it } from "vitest";
import conformance from "../../../tests/fixtures/timeline_conformance.json";
import type { ProjectDoc } from "./document";
import { envelopeFor, gainAt, headroom, planMix, type MixPlan } from "./mixdown";
import { clipGain } from "./resolve";

/**
 * The mix conformance check.
 *
 * `scripts/build_timeline_fixture.py` writes what the server plans for the
 * fixture document; `tests/test_video_mixdown.py` asserts Python still plans it,
 * and this asserts the browser plans the same thing. A file exported here whose
 * gains differ from the ones the preview showed would be the failure nobody
 * notices until the video is already posted.
 */
const fixture = conformance as unknown as {
  document: ProjectDoc;
  mix: MixPlan;
};

describe("mix conformance with the server planner", () => {
  it("plans the same clips, in the same order, from the same assets", () => {
    const plan = planMix(fixture.document);
    expect(plan.clips.map((item) => item.clip_id)).toEqual(
      fixture.mix.clips.map((item) => item.clip_id)
    );
    expect(plan.asset_ids).toEqual(fixture.mix.asset_ids);
    expect(plan.duration_ticks).toBe(fixture.mix.duration_ticks);
    expect(plan.sample_rate).toBe(fixture.mix.sample_rate);
    expect(plan.channels).toBe(fixture.mix.channels);
    expect(plan.silent).toBe(fixture.mix.silent);
    expect(plan.headroom).toBeCloseTo(fixture.mix.headroom, 6);
  });

  it("agrees on every point of every envelope", () => {
    const plan = planMix(fixture.document);
    for (let index = 0; index < fixture.mix.clips.length; index += 1) {
      const want = fixture.mix.clips[index];
      const got = plan.clips[index];
      const where = `clip ${want.clip_id}`;
      expect(got.kind, where).toBe(want.kind);
      expect(got.start, where).toBe(want.start);
      expect(got.duration, where).toBe(want.duration);
      expect(got.in_point, where).toBe(want.in_point);
      expect(got.speed, where).toBeCloseTo(want.speed, 6);
      // The point count matters as much as the values: the same curve described
      // in a different number of points means one simplifier moved.
      expect(got.envelope.length, where).toBe(want.envelope.length);
      for (let point = 0; point < want.envelope.length; point += 1) {
        expect(got.envelope[point][0], `${where} point ${point} at`).toBe(
          want.envelope[point][0]
        );
        expect(got.envelope[point][1], `${where} point ${point} gain`).toBeCloseTo(
          want.envelope[point][1],
          6
        );
      }
    }
  });

  it("carries footage into the mix, not just the music track", () => {
    const kinds = new Set(planMix(fixture.document).clips.map((item) => item.kind));
    expect(kinds).toEqual(new Set(["audio", "video"]));
  });
});

describe("the envelope describes the curve the preview plays", () => {
  it("reads back to the resolver's own gain all the way along", () => {
    const track = fixture.document.tracks.find((item) => item.id === "track_audio")!;
    const clip = track.clips[0];
    const envelope = envelopeFor(track, clip);
    for (let at = 0; at <= clip.duration; at += 900) {
      expect(gainAt(envelope, at), `at ${at}`).toBeCloseTo(clipGain(track, clip, at), 2);
    }
  });

  it("starts at zero and ends at the clip's own length", () => {
    for (const item of planMix(fixture.document).clips) {
      expect(item.envelope[0][0]).toBe(0);
      expect(item.envelope[item.envelope.length - 1][0]).toBe(item.duration);
    }
  });

  it("keeps a flat clip down to its two ends", () => {
    const track = fixture.document.tracks.find((item) => item.id === "track_base")!;
    const footage = track.clips.find((item) => item.id === "clip_slow")!;
    expect(envelopeFor(track, footage)).toEqual([
      [0, 1],
      [footage.duration, 1]
    ]);
  });
});

describe("what the plan leaves out", () => {
  it("leaves out a muted track", () => {
    const document: ProjectDoc = {
      ...fixture.document,
      tracks: fixture.document.tracks.map((track) => ({ ...track, muted: true }))
    };
    const plan = planMix(document);
    expect(plan.silent).toBe(true);
    expect(plan.asset_ids).toEqual([]);
  });

  it("leaves out stills and captions however loud they are set", () => {
    const plan = planMix(fixture.document);
    expect(plan.clips.some((item) => item.clip_id === "clip_still")).toBe(false);
    expect(plan.clips.some((item) => item.clip_id === "clip_text")).toBe(false);
  });

  it("reports no headroom for nothing rather than throwing", () => {
    expect(headroom([])).toBe(0);
  });
});
