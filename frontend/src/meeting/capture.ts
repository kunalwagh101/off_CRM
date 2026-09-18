export class MeetingCaptureError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MeetingCaptureError";
  }
}

export type MeetingCapture = {
  mimeType: string;
  startedAt: number;
  stop(): Promise<Blob>;
  cancel(): void;
};

const MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4"
];

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop();
}

function supportedMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? "";
}

export function meetingCaptureSupport(): { supported: boolean; reason: string } {
  if (typeof window === "undefined" || !window.isSecureContext) {
    return {
      supported: false,
      reason: "Meeting capture needs a secure browser context. Open off_CRM on localhost on this device."
    };
  }
  if (!navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices?.getDisplayMedia) {
    return {
      supported: false,
      reason: "This browser cannot capture both microphone and shared system audio."
    };
  }
  if (typeof MediaRecorder === "undefined" || typeof AudioContext === "undefined") {
    return {
      supported: false,
      reason: "This browser cannot mix and record meeting audio locally."
    };
  }
  return { supported: true, reason: "" };
}

export async function startMeetingCapture(options: {
  onSystemAudioEnded?: () => void;
} = {}): Promise<MeetingCapture> {
  const support = meetingCaptureSupport();
  if (!support.supported) throw new MeetingCaptureError(support.reason);

  let microphone: MediaStream | null = null;
  let display: MediaStream | null = null;
  let context: AudioContext | null = null;
  let recorder: MediaRecorder | null = null;
  let cancelled = false;
  let finished: Blob | null = null;
  const chunks: BlobPart[] = [];

  try {
    microphone = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      video: false
    });
    display = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true
    });

    const systemTracks = display.getAudioTracks();
    if (!systemTracks.length) {
      throw new MeetingCaptureError(
        "No system audio was shared. Choose a browser tab or screen option with “Share audio” enabled, then try again."
      );
    }

    context = new AudioContext();
    const destination = context.createMediaStreamDestination();
    context.createMediaStreamSource(microphone).connect(destination);
    context.createMediaStreamSource(new MediaStream(systemTracks)).connect(destination);

    const preferred = supportedMimeType();
    recorder = preferred
      ? new MediaRecorder(destination.stream, { mimeType: preferred })
      : new MediaRecorder(destination.stream);

    recorder.addEventListener("dataavailable", (event: BlobEvent) => {
      if (!cancelled && event.data.size) chunks.push(event.data);
    });

    const systemEnded = () => options.onSystemAudioEnded?.();
    for (const track of systemTracks) track.addEventListener("ended", systemEnded, { once: true });

    recorder.start();

    const cleanup = () => {
      if (microphone) stopTracks(microphone);
      if (display) stopTracks(display);
      if (context && context.state !== "closed") void context.close();
    };

    return {
      mimeType: recorder.mimeType || preferred || "audio/webm",
      startedAt: Date.now(),
      stop(): Promise<Blob> {
        if (finished) return Promise.resolve(finished);
        if (!recorder || recorder.state === "inactive") {
          cleanup();
          return Promise.reject(new MeetingCaptureError("Meeting recording is no longer active."));
        }
        return new Promise<Blob>((resolve, reject) => {
          recorder!.addEventListener(
            "stop",
            () => {
              cleanup();
              if (cancelled) {
                reject(new MeetingCaptureError("Meeting recording was cancelled."));
                return;
              }
              const blob = new Blob(chunks, {
                type: recorder!.mimeType || preferred || "audio/webm"
              });
              if (!blob.size) {
                reject(new MeetingCaptureError("The meeting recording contains no audio."));
                return;
              }
              finished = blob;
              resolve(blob);
            },
            { once: true }
          );
          recorder!.stop();
        });
      },
      cancel(): void {
        if (cancelled) return;
        cancelled = true;
        chunks.length = 0;
        if (recorder && recorder.state !== "inactive") recorder.stop();
        cleanup();
      }
    };
  } catch (error) {
    if (microphone) stopTracks(microphone);
    if (display) stopTracks(display);
    if (context && context.state !== "closed") void context.close();
    if (error instanceof MeetingCaptureError) throw error;
    if (error instanceof DOMException && error.name === "NotAllowedError") {
      throw new MeetingCaptureError(
        "Microphone or screen-audio permission was not granted. Allow both permissions and try again."
      );
    }
    throw new MeetingCaptureError(
      error instanceof Error ? error.message : "Meeting capture could not start."
    );
  }
}
