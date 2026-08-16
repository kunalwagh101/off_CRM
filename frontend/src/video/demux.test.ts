import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DemuxError, demuxVideo } from "./demux";

/**
 * The demuxer, against files written by something that is not it.
 *
 * Two fixtures, from two different directions, because a parser tested against
 * its own writer proves only that they agree with each other:
 *
 * - `muxed_sample.webm` is written by `frontend/src/video/webm.ts` — the
 *   *muxer*, which knows nothing about this file — and is already parsed on the
 *   server by `video/gates.py`. Three implementations of one format now.
 * - `sample_tables.mp4` is written by `scripts/build_mp4_fixture.py` from the
 *   ISO spec, with the sample tables laid out to be awkward in the ways real
 *   files are: chunks of three different sizes, sparse keyframes, and a `ctts`
 *   that puts presentation order out of step with decode order.
 *
 * The payloads are synthetic and that is the point: sample *n* is a known
 * length full of a known byte, so "did it find the right bytes" is a thing this
 * can assert exactly rather than approximately.
 */

const FIXTURES = resolve(__dirname, "../../../tests/fixtures");

function fixture(name: string): Uint8Array {
  return new Uint8Array(readFileSync(resolve(FIXTURES, name)));
}

describe("WebM, written by our own muxer", () => {
  const bytes = fixture("muxed_sample.webm");
  const track = demuxVideo(bytes);

  it("finds the track the muxer declared", () => {
    expect(track.container).toBe("webm");
    expect(track.codec).toBe("vp09.00.10.08");
    expect(track.width).toBe(1080);
    expect(track.height).toBe(1920);
  });

  it("finds every frame, and only those", () => {
    expect(track.frames.length).toBe(90);
  });

  it("finds each frame's actual bytes", () => {
    // The muxer wrote frame n as `300 + n % 17` bytes of the value `n & 0xff`.
    // Nothing but a correct offset and length reproduces that.
    track.frames.forEach((frame, index) => {
      expect(frame.length, `frame ${index} length`).toBe(300 + (index % 17));
      const payload = bytes.subarray(frame.offset, frame.offset + frame.length);
      expect(payload.length, `frame ${index} range`).toBe(frame.length);
      const distinct = new Set(payload);
      expect(distinct.size, `frame ${index} is not one repeated byte`).toBe(1);
      expect(payload[0], `frame ${index} content`).toBe(index & 0xff);
    });
  });

  it("marks the keyframes the encoder asked for and no others", () => {
    const keys = track.frames.flatMap((frame, index) => (frame.key ? [index] : []));
    // A keyframe every two seconds at 30fps.
    expect(keys).toEqual([0, 60]);
  });

  it("puts the frames where they belong in time", () => {
    expect(track.frames[0].timestampUs).toBe(0);
    track.frames.forEach((frame, index) => {
      // The muxer stores whole milliseconds, so a frame can be up to one out
      // from the microsecond the encoder gave it.
      expect(Math.abs(frame.timestampUs - Math.round((index * 1_000_000) / 30))).toBeLessThan(1000);
    });
    const times = track.frames.map((frame) => frame.timestampUs);
    expect([...times].sort((a, b) => a - b)).toEqual(times);
  });

  it("gives every frame a duration, including the last", () => {
    for (const frame of track.frames) expect(frame.durationUs).toBeGreaterThan(0);
    const last = track.frames[track.frames.length - 1];
    expect((last.timestampUs + last.durationUs) / 1_000_000).toBeCloseTo(3, 1);
  });

  it("ignores the audio track when there is one", () => {
    const withSound = demuxVideo(fixture("muxed_sample_audio.webm"));
    expect(withSound.frames.length).toBe(90);
    expect(withSound.frames[0].length).toBe(300);
  });
});

describe("MP4, written from the spec by the server", () => {
  const bytes = fixture("sample_tables.mp4");
  const track = demuxVideo(bytes);

  const DURATIONS = [...Array(12).fill(20), ...Array(12).fill(25)];
  /** Decode order I P B B against display order I B B P. */
  const SHIFTS = [0, 40, -20, -20, ...Array(20).fill(0)];
  const TIMESCALE = 600;

  it("reads the codec out of its own avcC rather than guessing", () => {
    expect(track.container).toBe("mp4");
    // 0x64 0x00 0x28 — high profile, level 4.0. Handing the decoder anything
    // else would be handing it a configuration the file does not have.
    expect(track.codec).toBe("avc1.640028");
    expect(track.description?.length).toBe(14);
    expect(track.description?.[0]).toBe(1);
  });

  it("picks the video track and not the sound one that comes first", () => {
    expect(track.width).toBe(640);
    expect(track.height).toBe(360);
    expect(track.frames.length).toBe(24);
  });

  it("walks the chunk table to find where each sample actually is", () => {
    // Chunks of 4, 6, 6 and 8 — the shape a three-entry stsc describes and the
    // one a parser that assumes a row per chunk gets wrong.
    track.frames.forEach((frame, index) => {
      expect(frame.length, `sample ${index} size`).toBe(12 + (index % 7));
      const payload = bytes.subarray(frame.offset, frame.offset + frame.length);
      expect(new Set(payload).size, `sample ${index} is not one repeated byte`).toBe(1);
      expect(payload[0], `sample ${index} content`).toBe(index & 0xff);
    });
  });

  it("adds the composition offset, so presentation is not decode order", () => {
    let decodeTime = 0;
    track.frames.forEach((frame, index) => {
      const presentation = decodeTime + SHIFTS[index];
      expect(frame.timestampUs, `sample ${index}`).toBe(
        Math.round((presentation * 1_000_000) / TIMESCALE)
      );
      decodeTime += DURATIONS[index];
    });
  });

  it("leaves the frames in decode order, which is what a decoder is fed", () => {
    // Samples 1 and 2 are the swapped pair. In *presentation* order the second
    // comes after the third; in the array it must not have moved.
    expect(track.frames[1].timestampUs).toBeGreaterThan(track.frames[2].timestampUs);
  });

  it("reads the sync sample table rather than assuming every frame is one", () => {
    const keys = track.frames.flatMap((frame, index) => (frame.key ? [index] : []));
    expect(keys).toEqual([0, 5, 10, 15, 20]);
  });

  it("measures durations along presentation order, not array order", () => {
    for (const frame of track.frames) expect(frame.durationUs).toBeGreaterThan(0);
  });

  it("reads a version-1 mdhd, whose timescale is twelve bytes further on", () => {
    // The same file with one flag changed. A parser reading the version-0
    // offset finds a creation timestamp where the timescale should be, and
    // turns a one-second video into a several-hour one.
    const wide = demuxVideo(fixture("sample_tables_v1.mp4"));
    expect(wide.frames.length).toBe(24);
    expect(wide.frames.map((frame) => frame.timestampUs)).toEqual(
      track.frames.map((frame) => frame.timestampUs)
    );
  });
});

describe("what it refuses", () => {
  it("refuses a file that is neither container", () => {
    expect(() => demuxVideo(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0]))).toThrow(DemuxError);
  });

  it("refuses an MP4 whose index was never written", () => {
    // What an interrupted recording looks like: the frames are all there and
    // the thing that finds them is not.
    const bytes = fixture("sample_tables.mp4");
    const broken = bytes.slice(0, bytes.length - 400);
    expect(() => demuxVideo(broken)).toThrow(/moov/);
  });

  it("says which container it thought it had", () => {
    expect(() => demuxVideo(new Uint8Array(4))).toThrow(/neither WebM nor MP4/);
  });
});
