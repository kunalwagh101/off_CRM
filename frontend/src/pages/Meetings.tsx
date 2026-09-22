import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";

type TranscriptionChoice = {
  provider_id: string;
  provider_name: string;
  flag: string;
  model_id: string;
  tier: string;
};

type MeetingCapabilities = {
  local_server: boolean;
  requires_local_browser: boolean;
  max_chunk_bytes: number;
  chunk_seconds: number;
  providers: TranscriptionChoice[];
};

type Meeting = {
  id: string;
  title: string;
  status: "recording" | "completed" | "failed";
  provider_id: string;
  model_id: string;
  language: string;
  transcript: string;
  chunk_count: number;
  audio_bytes: number;
  started_at: string;
  ended_at?: string | null;
  chunks?: Array<{
    sequence: number;
    status: string;
    transcript: string;
    error: string;
  }>;
};

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg"
];

function preferredMimeType(): string {
  return MIME_CANDIDATES.find((value) => MediaRecorder.isTypeSupported(value)) ?? "";
}

function localBrowser(): boolean {
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function splitChoice(value: string): { providerId: string; modelId: string } {
  const separator = value.indexOf(":");
  return separator < 0
    ? { providerId: value, modelId: "" }
    : { providerId: value.slice(0, separator), modelId: value.slice(separator + 1) };
}

export default function Meetings() {
  const { notify } = useApp();
  const capabilities = useResource(() => api.get<MeetingCapabilities>("/meetings/capabilities"), []);
  const meetings = useResource(() => api.get<{ items: Meeting[] }>("/meetings?limit=100"), []);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("");
  const [choice, setChoice] = useState("");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState("");
  const [captureError, setCaptureError] = useState("");
  const [needsFinalize, setNeedsFinalize] = useState(false);
  const [selected, setSelected] = useState<Meeting | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const microphoneRef = useRef<MediaStream | null>(null);
  const displayRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const meetingIdRef = useRef("");
  const sequenceRef = useRef(0);
  const pendingRef = useRef<Map<number, Blob>>(new Map());
  const uploadChainRef = useRef<Promise<void>>(Promise.resolve());
  const stoppingRef = useRef(false);

  useEffect(() => {
    if (!choice && capabilities.data?.providers.length) {
      const first = capabilities.data.providers[0];
      setChoice(`${first.provider_id}:${first.model_id}`);
    }
  }, [choice, capabilities.data]);

  useEffect(() => {
    return () => {
      recorderRef.current?.state !== "inactive" && recorderRef.current?.stop();
      microphoneRef.current?.getTracks().forEach((track) => track.stop());
      displayRef.current?.getTracks().forEach((track) => track.stop());
      void audioContextRef.current?.close();
    };
  }, []);

  function releaseCapture() {
    microphoneRef.current?.getTracks().forEach((track) => track.stop());
    displayRef.current?.getTracks().forEach((track) => track.stop());
    microphoneRef.current = null;
    displayRef.current = null;
    const context = audioContextRef.current;
    audioContextRef.current = null;
    if (context && context.state !== "closed") void context.close();
    recorderRef.current = null;
  }

  async function uploadChunk(sequence: number, blob: Blob): Promise<void> {
    const caps = capabilities.data;
    const meetingId = meetingIdRef.current;
    if (!caps || !meetingId) return;
    if (blob.size > caps.max_chunk_bytes) {
      throw new Error(
        `Audio chunk is ${Math.ceil(blob.size / 1024 / 1024)} MB; the local API limit is ${Math.floor(caps.max_chunk_bytes / 1024 / 1024)} MB.`
      );
    }
    const { providerId, modelId } = splitChoice(choice);
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const form = new FormData();
      const extension = blob.type.startsWith("audio/ogg") ? "ogg" : "webm";
      form.append("file", blob, `meeting-${meetingId}-chunk-${sequence}.${extension}`);
      form.append("sequence", String(sequence));
      form.append("provider_id", providerId);
      form.append("model_id", modelId);
      form.append("language", language.trim());
      try {
        await api.upload(`/meetings/${meetingId}/chunks`, form);
        pendingRef.current.delete(sequence);
        return;
      } catch (error) {
        lastError = error;
        if (attempt < 2) {
          await new Promise((resolve) => window.setTimeout(resolve, 750 * (attempt + 1)));
        }
      }
    }
    throw lastError instanceof Error ? lastError : new Error("Meeting chunk transcription failed");
  }

  function queueChunk(blob: Blob) {
    if (!blob.size) return;
    const sequence = sequenceRef.current;
    sequenceRef.current += 1;
    pendingRef.current.set(sequence, blob);
    uploadChainRef.current = uploadChainRef.current
      .then(() => uploadChunk(sequence, blob))
      .catch((error: unknown) => {
        setCaptureError(error instanceof Error ? error.message : "Meeting transcription failed");
      });
  }

  async function startCapture() {
    const caps = capabilities.data;
    if (needsFinalize) {
      setCaptureError("Finish or discard the previous meeting before starting another.");
      return;
    }
    if (!caps) return;
    if (!localBrowser() || !caps.local_server) {
      setCaptureError("Meeting capture is local-only. Open off_CRM from localhost.");
      return;
    }
    if (!navigator.mediaDevices?.getDisplayMedia || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setCaptureError("This browser does not support local microphone + system-audio capture.");
      return;
    }
    if (!caps.providers.length || !choice) {
      setCaptureError("Connect and enable a transcription provider first.");
      return;
    }

    setBusy("starting");
    setCaptureError("");
    stoppingRef.current = false;
    try {
      // Browser permission prompts happen before any meeting record is created.
      // Raw tracks remain in this browser process and are never written to disk.
      const display = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true
      });
      displayRef.current = display;
      const systemTrack = display.getAudioTracks()[0];
      if (!systemTrack) {
        display.getTracks().forEach((track) => track.stop());
        throw new Error("No system audio was shared. Choose a tab/screen and enable Share audio.");
      }
      const microphone = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });
      microphoneRef.current = microphone;

      const context = new AudioContext();
      audioContextRef.current = context;
      await context.resume();
      const destination = context.createMediaStreamDestination();

      const systemSource = context.createMediaStreamSource(new MediaStream([systemTrack]));
      const microphoneSource = context.createMediaStreamSource(microphone);
      const systemGain = context.createGain();
      const microphoneGain = context.createGain();
      systemGain.gain.value = 0.8;
      microphoneGain.gain.value = 0.8;
      systemSource.connect(systemGain).connect(destination);
      microphoneSource.connect(microphoneGain).connect(destination);

      const { providerId, modelId } = splitChoice(choice);
      const created = await api.post<Meeting>("/meetings", {
        title: title.trim() || `Meeting ${new Date().toLocaleString()}`,
        provider_id: providerId,
        model_id: modelId,
        language: language.trim()
      });

      meetingIdRef.current = created.id;
      sequenceRef.current = 0;
      pendingRef.current.clear();
      uploadChainRef.current = Promise.resolve();

      const mimeType = preferredMimeType();
      const recorder = new MediaRecorder(
        destination.stream,
        mimeType ? { mimeType, audioBitsPerSecond: 96_000 } : { audioBitsPerSecond: 96_000 }
      );
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => queueChunk(event.data);
      recorder.onerror = () => setCaptureError("The browser stopped recording audio unexpectedly.");
      display.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (!stoppingRef.current) void stopCapture();
      }, { once: true });
      recorder.start(caps.chunk_seconds * 1000);
      setRecording(true);
      setSelected(created);
      meetings.reload();
      notify("Meeting capture started. Mic + shared system audio stay local until each chunk is sent to your selected transcription provider.", "success");
    } catch (error) {
      releaseCapture();
      setCaptureError(error instanceof Error ? error.message : "Could not start meeting capture");
    } finally {
      setBusy("");
    }
  }

  async function retryPending(): Promise<boolean> {
    const pending = [...pendingRef.current.entries()].sort(([left], [right]) => left - right);
    for (const [sequence, blob] of pending) {
      try {
        await uploadChunk(sequence, blob);
      } catch (error) {
        setCaptureError(error instanceof Error ? error.message : "Could not retry a meeting chunk");
        return false;
      }
    }
    return true;
  }

  async function stopCapture() {
    if (stoppingRef.current) return;
    stoppingRef.current = true;
    setBusy("stopping");
    setCaptureError("");
    try {
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        await new Promise<void>((resolve) => {
          recorder.addEventListener("stop", () => resolve(), { once: true });
          recorder.stop();
        });
      }
      await uploadChainRef.current;
      const recovered = await retryPending();
      if (!recovered) {
        setRecording(false);
        setNeedsFinalize(true);
        releaseCapture();
        return;
      }
      const meetingId = meetingIdRef.current;
      if (meetingId) {
        const completed = await api.post<Meeting>(`/meetings/${meetingId}/complete`, {});
        setSelected(completed);
      }
      pendingRef.current.clear();
      meetingIdRef.current = "";
      setNeedsFinalize(false);
      setRecording(false);
      releaseCapture();
      meetings.reload();
      notify("Meeting stopped. Raw audio was not stored by off_CRM.", "success");
    } catch (error) {
      setCaptureError(error instanceof Error ? error.message : "Could not finish meeting");
      setRecording(false);
      releaseCapture();
    } finally {
      stoppingRef.current = false;
      setBusy("");
    }
  }

  async function finalizePendingMeeting() {
    if (!meetingIdRef.current || !needsFinalize) return;
    setBusy("finalizing");
    setCaptureError("");
    try {
      const recovered = await retryPending();
      if (!recovered) return;
      const completed = await api.post<Meeting>(
        `/meetings/${meetingIdRef.current}/complete`,
        {}
      );
      setSelected(completed);
      pendingRef.current.clear();
      meetingIdRef.current = "";
      setNeedsFinalize(false);
      meetings.reload();
      notify("Meeting transcription finished.", "success");
    } catch (error) {
      setCaptureError(error instanceof Error ? error.message : "Could not finish meeting");
    } finally {
      setBusy("");
    }
  }

  async function discardPendingMeeting() {
    const meetingId = meetingIdRef.current;
    if (!meetingId) return;
    setBusy("discarding");
    try {
      await api.delete(`/meetings/${meetingId}`);
      pendingRef.current.clear();
      meetingIdRef.current = "";
      setNeedsFinalize(false);
      setCaptureError("");
      setSelected(null);
      meetings.reload();
      notify("Unfinished meeting discarded. No raw audio was stored.", "success");
    } catch (error) {
      setCaptureError(error instanceof Error ? error.message : "Could not discard meeting");
    } finally {
      setBusy("");
    }
  }

  async function openMeeting(id: string) {
    setBusy(`open-${id}`);
    try {
      setSelected(await api.get<Meeting>(`/meetings/${id}`));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not load meeting", "error");
    } finally {
      setBusy("");
    }
  }

  async function deleteMeeting(id: string) {
    if (!window.confirm("Delete this transcript and its chunk metadata? Raw audio is not stored.")) return;
    try {
      await api.delete(`/meetings/${id}`);
      if (selected?.id === id) setSelected(null);
      meetings.reload();
      notify("Meeting transcript deleted", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not delete meeting", "error");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local capture"
        title="Meeting notes"
        description="Capture your microphone and shared system/tab audio locally. No bot joins the call, and off_CRM never stores the raw audio."
      />

      {captureError ? <div className="state-panel state-error" role="alert"><strong>Capture needs attention</strong><p>{captureError}</p></div> : null}

      <Panel
        title={recording ? "Recording locally" : "Start a meeting"}
        subtitle="Your browser mixes microphone + shared system audio. Only short audio chunks leave this machine, through the transcription provider you select."
        action={
          recording ? (
            <Button tone="danger" busy={busy === "stopping"} onClick={() => void stopCapture()}>Stop meeting</Button>
          ) : needsFinalize ? (
            <div className="page-actions">
              <Button tone="ghost" busy={busy === "discarding"} onClick={() => void discardPendingMeeting()}>Discard unfinished</Button>
              <Button busy={busy === "finalizing"} onClick={() => void finalizePendingMeeting()}>Retry & finish</Button>
            </div>
          ) : (
            <Button busy={busy === "starting"} onClick={() => void startCapture()}>Start local capture</Button>
          )
        }
      >
        {capabilities.loading ? <StatePanel title="Checking capture support" description="Reading local-browser and transcription-provider capabilities." tone="loading" /> : null}
        {capabilities.error ? <StatePanel title="Capture unavailable" description={capabilities.error} tone="error" /> : null}
        {capabilities.data ? (
          <div className="form-grid">
            <Field label="Meeting title">
              <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder="Weekly customer call" disabled={recording} />
            </Field>
            <Field label="Transcription model" hint={capabilities.data.providers.length ? "Only models permitted for meeting audio are listed." : "Connect a transcription provider in Connectors."}>
              <select value={choice} onChange={(event) => setChoice(event.target.value)} disabled={recording || !capabilities.data.providers.length}>
                {!capabilities.data.providers.length ? <option value="">No transcription model available</option> : null}
                {capabilities.data.providers.map((provider) => (
                  <option key={`${provider.provider_id}:${provider.model_id}`} value={`${provider.provider_id}:${provider.model_id}`}>
                    {provider.flag} {provider.provider_name} · {provider.model_id}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Language (optional)" hint="Leave blank for provider detection.">
              <input value={language} onChange={(event) => setLanguage(event.target.value)} maxLength={32} placeholder="en" disabled={recording} />
            </Field>
            <div className="field">
              <span>Capture boundary</span>
              <p className="meeting-boundary">
                <Badge tone={capabilities.data.local_server && localBrowser() ? "success" : "danger"}>
                  {capabilities.data.local_server && localBrowser() ? "Local only" : "Not local"}
                </Badge>
                <span>30-second chunks · max {Math.floor(capabilities.data.max_chunk_bytes / 1024 / 1024)} MB each</span>
              </p>
            </div>
          </div>
        ) : null}
        {recording ? (
          <p className="meeting-recording-status" role="status" aria-live="polite">
            <span className="recording-dot" aria-hidden="true" /> Recording microphone and shared system audio. Keep this page open until you stop.
          </p>
        ) : null}
      </Panel>

      <div className="two-column">
        <Panel title="Past meetings" subtitle="Transcript text and provider provenance only; no raw audio files are kept.">
          {meetings.loading ? <StatePanel title="Loading meetings" description="Reading transcript history." tone="loading" /> : null}
          {meetings.error ? <StatePanel title="Could not load meetings" description={meetings.error} tone="error" /> : null}
          {!meetings.loading && !(meetings.data?.items.length) ? <StatePanel title="No meetings yet" description="Start a local capture above when your next call begins." /> : null}
          <div className="meeting-list">
            {(meetings.data?.items ?? []).map((item) => (
              <article className="meeting-row" key={item.id}>
                <button type="button" className="meeting-open" onClick={() => void openMeeting(item.id)} disabled={busy === `open-${item.id}`}>
                  <strong>{item.title}</strong>
                  <span>{formatDate(item.started_at)} · {item.chunk_count} chunk{item.chunk_count === 1 ? "" : "s"}</span>
                </button>
                <Badge tone={item.status === "completed" ? "success" : item.status === "failed" ? "danger" : "warning"}>{item.status}</Badge>
                <button type="button" className="link-button" onClick={() => void deleteMeeting(item.id)} aria-label={`Delete ${item.title}`}>Delete</button>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title={selected?.title ?? "Transcript"} subtitle={selected ? `${selected.provider_id || "Provider pending"} · ${selected.model_id || "model pending"}` : "Select a meeting to inspect its transcript."}>
          {selected ? (
            <>
              <div className="meeting-meta">
                <Badge tone={selected.status === "completed" ? "success" : "warning"}>{selected.status}</Badge>
                <span>{selected.audio_bytes ? `${Math.round(selected.audio_bytes / 1024)} KB transcribed` : "No audio transcribed yet"}</span>
              </div>
              <pre className="meeting-transcript" aria-label="Meeting transcript">{selected.transcript || "Transcript will appear as chunks complete."}</pre>
              {selected.transcript ? (
                <Button
                  tone="secondary"
                  onClick={() => {
                    void navigator.clipboard.writeText(selected.transcript);
                    notify("Transcript copied", "success");
                  }}
                >
                  Copy transcript
                </Button>
              ) : null}
            </>
          ) : <StatePanel title="Nothing selected" description="Choose a past meeting to read the transcript." />}
        </Panel>
      </div>
    </div>
  );
}
