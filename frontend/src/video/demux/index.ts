/**
 * Pulling the encoded frames out of a container, in the browser.
 *
 * `paintFrame` has always been able to draw a video frame — its `AssetSource`
 * is a `CanvasImageSource` and a `VideoFrame` is one. What was missing was
 * anything that could produce *the frame at a given instant*, and that needs
 * two things the platform does not hand over: a demuxer, and a decoder.
 *
 * The decoder is `VideoDecoder`, which is free. The demuxer is this.
 *
 * ---
 *
 * **Why not a `<video>` element.** The obvious approach is to set
 * `video.currentTime` and `drawImage`. It reads as simpler and it is worse in
 * three ways that all matter here. A seek costs tens of milliseconds, and an
 * export asks for every frame in order, so a sixty-second render pays about a
 * minute in seeks alone. It cannot be done in a worker or against an
 * `OffscreenCanvas`, because a `<video>` needs a document. And it gives no way
 * to hold a decoded frame, which is what freeze-frame and reverse are made of.
 *
 * A decoder fed in order does the same work once, forwards, at decode speed.
 *
 * **What this is not.** It is not a general demuxer. It finds *one* video track
 * and the byte ranges of its frames, which is exactly what `VideoDecoder` wants
 * and nothing else. No subtitles, no chapters, no editing of what it reads —
 * audio still goes through `decodeAudioData`, which handles containers itself.
 *
 * The two parsers mirror `video/gates.py`, which already walks both of these
 * formats on the server to read a file's shape. Same boxes, same elements, one
 * level deeper.
 */

import { demuxIsoBmff } from "./isobmff";
import { demuxMatroska } from "./matroska";

/** One encoded frame, as a range inside the file rather than a copy of it. */
export interface FrameRef {
  /** Byte offset into the file. */
  offset: number;
  length: number;
  /** Presentation time, microseconds. What `EncodedVideoChunk` wants. */
  timestampUs: number;
  durationUs: number;
  /** Whether decoding can start here. */
  key: boolean;
}

export interface VideoTrack {
  /** A WebCodecs codec string, e.g. `vp09.00.10.08` or `avc1.640028`. */
  codec: string;
  /** `avcC` / `hvcC` / `av1C` bytes, for the codecs that need one. */
  description?: Uint8Array;
  width: number;
  height: number;
  /** Frames in presentation order. */
  frames: FrameRef[];
  container: "webm" | "mp4";
}

export class DemuxError extends Error {}

/**
 * Read a file's video track.
 *
 * Dispatches on the container's own magic rather than on a declared MIME type,
 * because the type comes from an upload form and the magic comes from the file.
 */
export function demuxVideo(bytes: Uint8Array): VideoTrack {
  if (bytes.length >= 4 && bytes[0] === 0x1a && bytes[1] === 0x45 && bytes[2] === 0xdf && bytes[3] === 0xa3) {
    return demuxMatroska(bytes);
  }
  // ISO BMFF has no magic at byte 0 — the first box's *type* is the marker, and
  // `ftyp` is required to be first in any file that claims to be one.
  if (bytes.length >= 12) {
    const tag = String.fromCharCode(bytes[4], bytes[5], bytes[6], bytes[7]);
    if (tag === "ftyp" || tag === "moov" || tag === "styp") return demuxIsoBmff(bytes);
  }
  throw new DemuxError(
    "This file is neither WebM nor MP4, so its frames cannot be read. Those " +
      "are the two containers the importer accepts."
  );
}

/** Whether the browser can decode this track, asked before anything is decoded. */
export async function canDecode(track: VideoTrack): Promise<{ ok: boolean; reason: string }> {
  const scope = globalThis as unknown as {
    VideoDecoder?: { isConfigSupported(config: Record<string, unknown>): Promise<{ supported?: boolean }> };
  };
  if (typeof scope.VideoDecoder === "undefined") {
    return { ok: false, reason: "This browser has no WebCodecs VideoDecoder, so footage cannot be drawn." };
  }
  try {
    const answer = await scope.VideoDecoder.isConfigSupported({
      codec: track.codec,
      codedWidth: track.width,
      codedHeight: track.height,
      ...(track.description ? { description: track.description } : {})
    });
    if (answer.supported) return { ok: true, reason: "" };
    return {
      ok: false,
      reason: `This browser cannot decode ${track.codec}. The clip's sound still works; its picture does not.`
    };
  } catch (error) {
    return {
      ok: false,
      reason: `This browser refused ${track.codec}: ${error instanceof Error ? error.message : String(error)}`
    };
  }
}
