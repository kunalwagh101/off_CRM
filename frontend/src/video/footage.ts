/**
 * The frame of a video clip at a given instant.
 *
 * `paintFrame` has always been able to draw one — its `AssetSource` is a
 * `CanvasImageSource` and a `VideoFrame` is one, so the painter needs no change
 * at all. This is the part that was missing: something that turns "the clip is
 * 1.4 seconds into its own material" into the actual decoded picture.
 *
 * ---
 *
 * **Decoding is forward-only, and that is the whole design.** A `VideoDecoder`
 * cannot start anywhere: it needs a keyframe and then every frame between that
 * keyframe and the one you want. So this keeps a cursor into the file, feeds
 * chunks in decode order, and holds the last few decoded frames.
 *
 * An export asks for frames in increasing order, which means the cursor never
 * goes backwards and every frame is decoded exactly once — the same work the
 * file already represents. Scrubbing the preview jumps around, and a jump
 * backwards or into a different group of pictures resets the decoder and
 * re-runs from that group's keyframe. That is what a seek costs in any editor.
 *
 * **Frames are owned here.** `frameAt` returns a frame that stays valid until
 * the next call, and closing it is this object's job. A `VideoFrame` holds a
 * GPU buffer and leaking them stops a decoder dead after a few dozen, so the
 * ownership has to sit in one place — and the caller paints immediately, which
 * is what makes one place enough.
 */

import { TICKS_PER_SECOND } from "./document";
import { canDecode, demuxVideo, type FrameRef, type VideoTrack } from "./demux";
import type { AssetTable, LoadedAsset } from "./render";
import type { Frame, ProjectDoc } from "./document";

/**
 * How many decoded frames to hold.
 *
 * Each is a full picture in GPU memory — about 3MB at 1080p — so this is a
 * memory ceiling, not a cache size to tune upward. It only has to be deep
 * enough that the decoder's own reordering delay never outruns it.
 */
const CACHE_FRAMES = 12;

/** How far ahead of the decoder to run. Deep enough to keep it busy, shallow
 * enough that a seek does not throw away much work. */
const FEED_AHEAD = 8;

/** How long to wait on a silent decoder before deciding it has nothing more. */
const IDLE_MS = 60;

interface VideoFrameLike {
  timestamp: number;
  displayWidth: number;
  displayHeight: number;
  close(): void;
}

interface VideoDecoderLike {
  decodeQueueSize: number;
  configure(config: Record<string, unknown>): void;
  decode(chunk: unknown): void;
  flush(): Promise<void>;
  reset(): void;
  close(): void;
}

export class FootageError extends Error {}

export class Footage {
  private decoder: VideoDecoderLike | null = null;
  /** Decode-order index of the next chunk to feed. */
  private cursor = 0;
  private ready: VideoFrameLike[] = [];
  private waiters: Array<() => void> = [];
  private failure: Error | null = null;
  private current: VideoFrameLike | null = null;
  /** How many frames this decoder has produced since it was configured. */
  private outCount = 0;
  /** Set after a flush: the decoder has to be given a keyframe again. */
  private needsKey = false;
  /**
   * One decode at a time.
   *
   * A cursor and a decoder queue are not re-entrant, and a scrubbing preview
   * will happily ask for a second frame before the first has arrived. Two
   * interleaved requests would each advance the other's cursor, and the symptom
   * is the worst kind — the wrong frame, sometimes.
   */
  private turn: Promise<unknown> = Promise.resolve();

  /** Decode-order indices, sorted by presentation time. */
  private readonly order: number[];
  /** Presentation start of each entry in `order`, for the binary search. */
  private readonly starts: number[];

  private constructor(
    readonly assetId: string,
    readonly track: VideoTrack,
    private readonly bytes: Uint8Array
  ) {
    // The presentation index. Decode order and presentation order are the same
    // for VP8 and VP9 and are not the same for anything with B-frames, and the
    // decoder has to be fed in one while the timeline asks in the other.
    this.order = track.frames.map((_, index) => index);
    this.order.sort((a, b) => track.frames[a].timestampUs - track.frames[b].timestampUs);
    this.starts = this.order.map((index) => track.frames[index].timestampUs);
  }

  get width(): number {
    return this.track.width;
  }

  get height(): number {
    return this.track.height;
  }

  /** Total length, in the project's own ticks. */
  get durationTicks(): number {
    const last = this.track.frames[this.order[this.order.length - 1]];
    if (!last) return 0;
    return Math.round(((last.timestampUs + last.durationUs) / 1_000_000) * TICKS_PER_SECOND);
  }

  static async open(assetId: string, bytes: Uint8Array): Promise<Footage> {
    const track = demuxVideo(bytes);
    const support = await canDecode(track);
    if (!support.ok) throw new FootageError(support.reason);
    return new Footage(assetId, track, bytes);
  }

  /**
   * Another reader over the same file.
   *
   * Two clips of one recording, at two different points, need two cursors —
   * sharing one would make each seek the other backwards on every frame. The
   * bytes and the index are shared; only the decoder is not.
   */
  fork(): Footage {
    return new Footage(this.assetId, this.track, this.bytes);
  }

  /**
   * Give up the decoder and the frames, keeping the index.
   *
   * What a clip that has left the screen should cost: nothing but its table of
   * where its frames are. Coming back is a seek, which it would have been
   * anyway.
   */
  release(): void {
    if (!this.decoder && !this.current) return;
    this.close();
    this.cursor = 0;
    this.failure = null;
  }

  /**
   * The frame covering `ticks` into this material.
   *
   * Returns null past the end rather than throwing: a clip trimmed to a length
   * its source cannot fill is a validation problem, and the honest thing at
   * paint time is to draw the hole the painter already draws for a missing
   * asset.
   */
  async frameAt(ticks: number): Promise<VideoFrameLike | null> {
    const mine = this.turn.then(() => this.resolveFrame(ticks));
    // Failures must not poison the queue for the next caller, so the chain is
    // kept on a settled version of it.
    this.turn = mine.catch(() => undefined);
    return mine;
  }

  private async resolveFrame(ticks: number): Promise<VideoFrameLike | null> {
    if (this.failure) throw this.failure;
    const wanted = Math.max(0, Math.round((ticks / TICKS_PER_SECOND) * 1_000_000));
    const slot = this.slotFor(wanted);
    if (slot < 0) return null;
    const decodeIndex = this.order[slot];
    const target = this.track.frames[decodeIndex];

    if (this.current && this.current.timestamp === target.timestampUs) return this.current;

    const hit = await this.decodeUpTo(decodeIndex, target);
    if (!hit) return null;
    this.adopt(hit);
    return hit;
  }

  /** Which presentation slot covers this instant. */
  private slotFor(us: number): number {
    if (!this.starts.length || us < this.starts[0]) return this.starts.length ? 0 : -1;
    let low = 0;
    let high = this.starts.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (this.starts[middle] <= us) low = middle;
      else high = middle - 1;
    }
    const frame = this.track.frames[this.order[low]];
    // Past the last frame's own end is past the end of the material.
    if (low === this.starts.length - 1 && us >= frame.timestampUs + Math.max(1, frame.durationUs)) {
      return -1;
    }
    return low;
  }

  /** The decode index of the keyframe this one has to be decoded from. */
  private groupStart(decodeIndex: number): number {
    for (let index = decodeIndex; index >= 0; index -= 1) {
      if (this.track.frames[index].key) return index;
    }
    return 0;
  }

  private async decodeUpTo(decodeIndex: number, target: FrameRef): Promise<VideoFrameLike | null> {
    const group = this.groupStart(decodeIndex);
    // Backwards, or into a group the cursor has already passed the start of and
    // is not inside: start again from this group's keyframe. `needsKey` forces
    // the same thing after a flush, because a flushed decoder will not take a
    // delta frame — it has forgotten everything a delta refers back to.
    if (!this.decoder || this.needsKey || this.cursor > decodeIndex || this.cursor < group) {
      this.restart(group);
    }

    while (true) {
      if (this.failure) throw this.failure;
      const found = this.ready.find((item) => item.timestamp === target.timestampUs);
      if (found) return found;

      const decoder = this.decoder!;
      while (this.cursor <= decodeIndex && decoder.decodeQueueSize < FEED_AHEAD) {
        this.feed(this.cursor);
        this.cursor += 1;
      }

      const before = this.outCount;
      await this.nextOutput();
      if (this.cursor <= decodeIndex || this.outCount !== before) continue;

      // Everything the target needs has been fed and nothing new has come out.
      // Either the decoder is holding frames back to reorder them, or it is
      // simply done — and a flush is the only thing that distinguishes the two.
      //
      // Deliberately not reached by feeding one chunk and immediately looking:
      // `decodeQueueSize` falls to zero as soon as a chunk is *accepted*, well
      // before its frame comes out, so treating that as "done" would flush on
      // the very first frame of every file — and then refuse the second one.
      await decoder.flush();
      this.needsKey = true;
      if (this.failure) throw this.failure;
      return this.ready.find((item) => item.timestamp === target.timestampUs) ?? null;
    }
  }

  private feed(index: number): void {
    const reference = this.track.frames[index];
    const scope = globalThis as unknown as {
      EncodedVideoChunk: new (init: Record<string, unknown>) => unknown;
    };
    this.decoder!.decode(
      new scope.EncodedVideoChunk({
        type: reference.key ? "key" : "delta",
        timestamp: reference.timestampUs,
        duration: reference.durationUs || undefined,
        data: this.bytes.subarray(reference.offset, reference.offset + reference.length)
      })
    );
  }

  private restart(fromDecodeIndex: number): void {
    this.dispose();
    const scope = globalThis as unknown as {
      VideoDecoder: new (init: {
        output: (frame: VideoFrameLike) => void;
        error: (error: Error) => void;
      }) => VideoDecoderLike;
    };
    const decoder = new scope.VideoDecoder({
      output: (frame) => this.receive(frame),
      error: (error) => {
        this.failure = error;
        this.wake();
      }
    });
    decoder.configure({
      codec: this.track.codec,
      codedWidth: this.track.width,
      codedHeight: this.track.height,
      ...(this.track.description ? { description: this.track.description } : {}),
      optimizeForLatency: true
    });
    this.decoder = decoder;
    this.cursor = fromDecodeIndex;
    this.outCount = 0;
    this.needsKey = false;
  }

  private receive(frame: VideoFrameLike): void {
    this.outCount += 1;
    this.ready.push(frame);
    while (this.ready.length > CACHE_FRAMES) {
      const dropped = this.ready.shift();
      // Never close the frame the caller is currently holding.
      if (dropped && dropped !== this.current) dropped.close();
    }
    this.wake();
  }

  /** Take ownership of the frame being handed out, and release the last one. */
  private adopt(frame: VideoFrameLike): void {
    if (this.current && this.current !== frame && !this.ready.includes(this.current)) {
      this.current.close();
    }
    this.current = frame;
  }

  /**
   * Wait for the decoder to produce something, or for it to go quiet.
   *
   * The timeout is not a guess at how long decoding takes — it is what stops a
   * decoder that has silently dropped a frame from hanging the caller forever.
   * The loop above treats "nothing new arrived" as a fact to act on rather than
   * as an error, so being woken early costs one more turn around it.
   */
  private nextOutput(): Promise<void> {
    return new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        resolve();
      };
      this.waiters.push(finish);
      setTimeout(finish, IDLE_MS);
    });
  }

  private wake(): void {
    const waiting = this.waiters;
    this.waiters = [];
    for (const resolve of waiting) resolve();
  }

  private dispose(): void {
    for (const frame of this.ready) if (frame !== this.current) frame.close();
    this.ready = [];
    if (this.decoder) {
      try {
        this.decoder.close();
      } catch {
        // Closing a decoder that already errored is not itself a problem.
      }
    }
    this.decoder = null;
  }

  close(): void {
    this.dispose();
    if (this.current) this.current.close();
    this.current = null;
  }
}

/**
 * Every piece of footage a project draws, and what went wrong with the rest.
 *
 * A file that will not demux or a codec the browser will not take costs its own
 * clip and nothing else. The alternative — failing the whole render — turns one
 * bad import into a person's evening.
 */
export class FootageLibrary {
  private constructor(
    /** Keyed by **clip**, not by asset: two clips of one file read from two
     * different points and each needs its own cursor. */
    private readonly readers: Map<string, Footage>,
    readonly problems: Array<{ assetId: string; reason: string }>
  ) {}

  /** Every video clip in the document, as the pairs `load` wants. */
  static needs(project: ProjectDoc): Array<{ clipId: string; assetId: string }> {
    const out: Array<{ clipId: string; assetId: string }> = [];
    for (const track of project.tracks) {
      for (const clip of track.clips) {
        if (clip.kind === "video" && clip.asset_id) out.push({ clipId: clip.id, assetId: clip.asset_id });
      }
    }
    return out;
  }

  static async load(
    needs: Array<{ clipId: string; assetId: string }>,
    urlFor: (id: string) => string
  ): Promise<FootageLibrary> {
    const readers = new Map<string, Footage>();
    const problems: Array<{ assetId: string; reason: string }> = [];
    // One fetch and one demux per file, however many clips use it.
    const opened = new Map<string, Promise<Footage>>();
    for (const { assetId } of needs) {
      if (opened.has(assetId)) continue;
      opened.set(
        assetId,
        (async () => {
          const response = await fetch(urlFor(assetId), { credentials: "same-origin" });
          if (!response.ok) throw new FootageError(`The server returned ${response.status}.`);
          return Footage.open(assetId, new Uint8Array(await response.arrayBuffer()));
        })()
      );
    }

    const claimed = new Set<string>();
    for (const { clipId, assetId } of needs) {
      try {
        const source = await opened.get(assetId)!;
        // The first clip takes the reader itself; the rest fork it.
        readers.set(clipId, claimed.has(assetId) ? source.fork() : source);
        claimed.add(assetId);
      } catch (error) {
        if (!problems.some((item) => item.assetId === assetId)) {
          problems.push({
            assetId,
            reason: error instanceof Error ? error.message : String(error)
          });
        }
      }
    }
    return new FootageLibrary(readers, problems);
  }

  get size(): number {
    return this.readers.size;
  }

  /** Record a file's failure once, however many clips of it there are. */
  private blame(assetId: string, error: unknown): void {
    if (this.problems.some((item) => item.assetId === assetId)) return;
    this.problems.push({
      assetId,
      reason: error instanceof Error ? error.message : String(error),
    });
  }

  has(clipId: string): boolean {
    return this.readers.has(clipId);
  }

  /**
   * Put the right frame of every piece of footage into the asset table, ready
   * for `paintFrame`.
   *
   * Entries are keyed by clip id, which the painter prefers over the asset id
   * exactly so that one file used twice can show two different moments of
   * itself at once.
   *
   * Clips that are not on screen are released — their decoder and their held
   * frames go, their index stays. Without that, a project with twenty pieces of
   * footage would sit on twenty decoders' worth of GPU memory to draw the one
   * that is visible.
   *
   * **`ahead`, and why an exporter passes a second frame.** An output frame is
   * not an instant, it is the interval until the next one, and the source frame
   * that best represents that interval is the one showing in the middle of it —
   * not the one showing at its leading edge. The difference is invisible until
   * the two frame rates are close but not identical, which is exactly the
   * ordinary case: a container stores its times in its own units, so 30fps
   * footage has frames at 33ms and 67ms while a 30fps timeline asks at 33.333ms
   * and 66.667ms. Sampled at the edge, that asks for frame 1 twice and never
   * asks for frame 2 — a third of the footage silently replaced by duplicates.
   *
   * So the exporter resolves a *second* frame half an output frame later and
   * passes it here, and each clip takes its source time from that. It has to be
   * a resolved frame rather than a number to add on: a reversed clip moves
   * backwards through its material, and a clip on a speed curve moves at a rate
   * that is different at every instant. Adding half a frame times the clip's
   * `speed` gets both of those wrong, in opposite directions.
   *
   * Which clips are *drawn* still comes from `frame`. At a cut the two
   * resolutions hold different clips, and taking the cast from the later one
   * would leave the outgoing clip with nothing to draw on the frame it is
   * still on screen for.
   *
   * A preview passes nothing: the playhead is a real instant, and the honest
   * answer there is the frame actually showing at it.
   */
  async apply(frame: Frame, into: AssetTable, ahead?: Frame): Promise<void> {
    const later = new Map<string, number>();
    for (const item of ahead?.items ?? []) later.set(item.clip_id, item.source_time);

    const live = new Set<string>();
    for (const item of frame.items) {
      if (item.kind !== "video") continue;
      const source = this.readers.get(item.clip_id);
      if (!source) continue;
      live.add(item.clip_id);
      const at = later.get(item.clip_id) ?? item.source_time;
      let picture: VideoFrameLike | null = null;
      try {
        picture = await source.frameAt(at);
      } catch (error) {
        // A file that demuxed cleanly and named a codec this browser supports
        // can still carry a bitstream the decoder rejects — a container whose
        // frames are not what its header says they are. That costs this clip,
        // which draws the hole the painter already draws for a missing asset,
        // and it is reported rather than taking the whole render down with it.
        this.blame(source.assetId, error);
        this.readers.delete(item.clip_id);
        into.delete(item.clip_id);
        source.close();
        continue;
      }
      if (!picture) {
        into.delete(item.clip_id);
        continue;
      }
      const asset: LoadedAsset = {
        source: picture as unknown as LoadedAsset["source"],
        width: picture.displayWidth,
        height: picture.displayHeight
      };
      into.set(item.clip_id, asset);
    }
    for (const [clipId, source] of this.readers) {
      if (!live.has(clipId)) {
        source.release();
        into.delete(clipId);
      }
    }
  }

  close(): void {
    for (const item of this.readers.values()) item.close();
    this.readers.clear();
  }
}
