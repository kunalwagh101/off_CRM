import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MeetingCaptureError,
  meetingCaptureSupport,
  startMeetingCapture
} from "./capture";

class FakeTrack {
  kind: string;
  stopped = false;
  listeners: Record<string, Array<() => void>> = {};

  constructor(kind: string) {
    this.kind = kind;
  }

  stop() {
    this.stopped = true;
  }

  addEventListener(name: string, handler: () => void) {
    (this.listeners[name] ??= []).push(handler);
  }

  end() {
    for (const handler of this.listeners.ended ?? []) handler();
  }
}

class FakeStream {
  tracks: FakeTrack[];

  constructor(tracks: FakeTrack[] = []) {
    this.tracks = tracks;
  }

  getTracks() {
    return this.tracks;
  }

  getAudioTracks() {
    return this.tracks.filter((track) => track.kind === "audio");
  }
}

class FakeAudioContext {
  state = "running";
  closed = false;

  createMediaStreamDestination() {
    return { stream: new FakeStream([new FakeTrack("audio")]) };
  }

  createMediaStreamSource() {
    return { connect: vi.fn() };
  }

  async close() {
    this.closed = true;
    this.state = "closed";
  }
}

class FakeRecorder {
  static isTypeSupported = vi.fn(() => true);
  state = "inactive";
  mimeType: string;
  listeners: Record<string, Array<(event: any) => void>> = {};

  constructor(_stream: FakeStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? "audio/webm";
  }

  addEventListener(name: string, handler: (event: any) => void) {
    (this.listeners[name] ??= []).push(handler);
  }

  start() {
    this.state = "recording";
  }

  stop() {
    if (this.state === "inactive") return;
    this.state = "inactive";
    const blob = new Blob(["captured-audio"], { type: this.mimeType });
    for (const handler of this.listeners.dataavailable ?? []) {
      handler({ data: blob });
    }
    for (const handler of this.listeners.stop ?? []) handler({});
  }
}

describe("local meeting capture", () => {
  let microphone: FakeStream;
  let display: FakeStream;
  let micTrack: FakeTrack;
  let systemTrack: FakeTrack;
  let videoTrack: FakeTrack;

  beforeEach(() => {
    micTrack = new FakeTrack("audio");
    systemTrack = new FakeTrack("audio");
    videoTrack = new FakeTrack("video");
    microphone = new FakeStream([micTrack]);
    display = new FakeStream([systemTrack, videoTrack]);

    Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn(async () => microphone),
        getDisplayMedia: vi.fn(async () => display)
      }
    });
    vi.stubGlobal("MediaStream", FakeStream);
    vi.stubGlobal("AudioContext", FakeAudioContext);
    vi.stubGlobal("MediaRecorder", FakeRecorder);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("refuses a screen share with no system-audio track and cleans up both permissions", async () => {
    display = new FakeStream([videoTrack]);

    await expect(startMeetingCapture()).rejects.toThrow("No system audio was shared");
    expect(micTrack.stopped).toBe(true);
    expect(videoTrack.stopped).toBe(true);
  });

  it("records locally without making any network request", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const capture = await startMeetingCapture();
    const result = await capture.stop();

    expect(result.size).toBeGreaterThan(0);
    expect(result.type).toContain("audio/webm");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(micTrack.stopped).toBe(true);
    expect(systemTrack.stopped).toBe(true);
    expect(videoTrack.stopped).toBe(true);
  });

  it("notifies the caller if system-audio sharing ends during the recording", async () => {
    const ended = vi.fn();
    const capture = await startMeetingCapture({ onSystemAudioEnded: ended });

    systemTrack.end();

    expect(ended).toHaveBeenCalledOnce();
    capture.cancel();
  });

  it("turns a browser permission denial into an actionable capture error", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn(async () => {
          throw new DOMException("denied", "NotAllowedError");
        }),
        getDisplayMedia: vi.fn()
      }
    });

    await expect(startMeetingCapture()).rejects.toEqual(
      expect.objectContaining({
        name: "MeetingCaptureError",
        message: expect.stringContaining("permission was not granted")
      })
    );
  });

  it("refuses an insecure browser context before asking for any media", () => {
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: false });
    const support = meetingCaptureSupport();

    expect(support.supported).toBe(false);
    expect(support.reason).toContain("localhost");
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
  });

  it("exports a specific error type for callers that need to distinguish capture failures", () => {
    expect(new MeetingCaptureError("x")).toBeInstanceOf(Error);
  });
});
