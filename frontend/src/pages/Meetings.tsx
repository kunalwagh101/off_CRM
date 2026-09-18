import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { AIProvidersPayload } from "../types";
import { meetingCaptureSupport, startMeetingCapture, type MeetingCapture } from "../meeting/capture";

type MeetingSummary = {
  id: string;
  title: string;
  created_at: string;
  language: string;
  provider_id: string;
  provider_name: string;
  model_id: string;
  duration_ms: number;
  audio_bytes: number;
  word_count: number;
  log_id: string;
};

type Meeting = MeetingSummary & {
  transcript: string;
  words: Array<{ word: string; start: number; end: number }>;
};

function isLoopbackBrowser(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname.toLowerCase();
  return host === "localhost" || host === "127.0.0.1" || host === "::1" || host === "[::1]";
}

function filenameFor(type: string): string {
  if (type.includes("ogg")) return "meeting.ogg";
  if (type.includes("mp4")) return "meeting.m4a";
  if (type.includes("wav")) return "meeting.wav";
  return "meeting.webm";
}

export default function Meetings() {
  const { notify } = useApp();
  const meetings = useResource(() => api.get<{ items: MeetingSummary[] }>("/meetings?limit=100"), []);
  const providers = useResource(() => api.get<AIProvidersPayload>("/ai/providers"), []);
  const captureRef = useRef<MeetingCapture | null>(null);
  const endingRef = useRef(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState("");
  const [title, setTitle] = useState("");
  const [active, setActive] = useState<Meeting | null>(null);
  const [startedAt, setStartedAt] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const localOrigin = isLoopbackBrowser();
  const support = meetingCaptureSupport();
  const mistral = providers.data?.providers.find((provider) => provider.id === "mistral");
  const transcriberReady = Boolean(
    mistral?.connected &&
      mistral.enabled &&
      mistral.effective_tier === "A" &&
      mistral.model_ids.includes("voxtral-mini-latest")
  );
  const canStart = localOrigin && support.supported && transcriberReady && !busy && !recording;

  useEffect(() => {
    if (!recording || !startedAt) return;
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [recording, startedAt]);

  useEffect(
    () => () => {
      captureRef.current?.cancel();
      captureRef.current = null;
    },
    []
  );

  async function finish() {
    const capture = captureRef.current;
    if (!capture || endingRef.current) return;
    endingRef.current = true;
    captureRef.current = null;
    setRecording(false);
    setBusy("transcribing");
    try {
      const blob = await capture.stop();
      const form = new FormData();
      form.append("file", blob, filenameFor(blob.type || capture.mimeType));
      form.append("title", title.trim());
      const result = await api.upload<Meeting>("/meetings/transcribe", form);
      setActive(result);
      setTitle("");
      await meetings.reload();
      notify("Meeting transcript saved locally.", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Meeting transcription failed.", "error");
    } finally {
      endingRef.current = false;
      setBusy("");
    }
  }

  async function begin() {
    if (!localOrigin) {
      notify("Meeting capture only works from localhost on this device.", "error");
      return;
    }
    setBusy("starting");
    try {
      const capture = await startMeetingCapture({
        onSystemAudioEnded: () => {
          if (!endingRef.current) {
            notify("System-audio sharing stopped, so the meeting recording is ending.", "warning");
            void finish();
          }
        }
      });
      captureRef.current = capture;
      setStartedAt(capture.startedAt);
      setElapsed(0);
      setRecording(true);
      notify("Recording locally. Nothing is uploaded until you press Stop.", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Meeting capture could not start.", "error");
    } finally {
      setBusy("");
    }
  }

  function cancel() {
    const capture = captureRef.current;
    if (!capture) return;
    endingRef.current = true;
    captureRef.current = null;
    capture.cancel();
    setRecording(false);
    setStartedAt(0);
    setElapsed(0);
    endingRef.current = false;
    notify("Recording cancelled. No meeting audio was uploaded.", "info");
  }

  async function openMeeting(id: string) {
    setBusy("open-" + id);
    try {
      setActive(await api.get<Meeting>("/meetings/" + id));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not open meeting transcript.", "error");
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Local meeting capture"
        title="Meeting notes"
        description="Record your microphone and the system audio you explicitly share. No bot joins the call, and raw audio is not stored by off_CRM."
        actions={
          recording ? (
            <>
              <Badge tone="danger">Recording {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</Badge>
              <Button onClick={() => void finish()} busy={busy === "transcribing"}>Stop &amp; transcribe</Button>
              <Button tone="ghost" onClick={cancel}>Cancel</Button>
            </>
          ) : (
            <Button onClick={() => void begin()} busy={busy === "starting"} disabled={!canStart}>Start recording</Button>
          )
        }
      />

      {localOrigin && support.supported && !providers.loading && !transcriberReady ? (
        <div className="danger-note" role="alert">
          <strong>Tier A transcription is not configured</strong>
          <p>
            Open <a href="#connectors">Connectors</a>, connect Mistral, then enable the
            <code> voxtral-mini-latest </code> model. Meeting audio is not allowed to fall back to OpenAI, Groq or another lower-trust provider.
          </p>
        </div>
      ) : null}

      {!localOrigin ? (
        <div className="danger-note" role="alert">
          <strong>Local device required</strong>
          <p>Open off_CRM through localhost or 127.0.0.1 on the computer where the meeting is playing. A hosted off_CRM server is not allowed to receive raw meeting audio.</p>
        </div>
      ) : !support.supported ? (
        <div className="danger-note" role="alert">
          <strong>Capture is not supported in this browser</strong>
          <p>{support.reason}</p>
        </div>
      ) : (
        <div className="form-note">
          <strong>What you will share</strong>
          <span>Choose a tab or screen with “Share audio” enabled, then grant microphone access. Recording stays in the browser until you press Stop.</span>
        </div>
      )}

      <div className="meeting-layout">
        <Panel title="Capture" subtitle="The recording itself is never added to the meeting library.">
          <div className="form-stack">
            <label className="field">
              <span>Meeting title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder="Weekly sales call" disabled={recording} />
            </label>
            <p className="muted-copy">
              Transcription is allowed only through a highest-trust Tier A provider configured in off_CRM. If none is available, the recording is refused rather than sent somewhere less trusted.
            </p>
          </div>
        </Panel>

        <Panel title="Saved meetings" subtitle="Private transcript records on this device.">
          {meetings.loading ? (
            <StatePanel title="Loading meetings" description="Reading local transcript records." tone="loading" />
          ) : meetings.error ? (
            <StatePanel title="Could not read meetings" description={meetings.error.message} tone="error" />
          ) : !(meetings.data?.items.length) ? (
            <StatePanel title="No meeting transcripts yet" description="Start a recording, stop it, and the transcript will appear here." />
          ) : (
            <div className="meeting-list">
              {meetings.data.items.map((meeting) => (
                <button
                  type="button"
                  className={active?.id === meeting.id ? "meeting-row meeting-row-active" : "meeting-row"}
                  key={meeting.id}
                  onClick={() => void openMeeting(meeting.id)}
                  disabled={busy === "open-" + meeting.id}
                >
                  <span>
                    <strong>{meeting.title}</strong>
                    <small>{new Date(meeting.created_at).toLocaleString()} · {meeting.word_count} words</small>
                  </span>
                  <small>{meeting.provider_name || meeting.provider_id} · {meeting.model_id}</small>
                </button>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title={active ? active.title : "Transcript"}
        subtitle={active ? (active.provider_name || active.provider_id) + " · " + active.model_id + " · " + active.word_count + " timed words" : "Open a saved meeting to review what was said."}
        className="meeting-transcript-panel"
      >
        {active ? (
          <div className="meeting-transcript">
            <p>{active.transcript}</p>
            <details>
              <summary>Transcription audit details</summary>
              <dl className="definition-list">
                <div><dt>Created</dt><dd>{new Date(active.created_at).toLocaleString()}</dd></div>
                <div><dt>Provider</dt><dd>{active.provider_name || active.provider_id}</dd></div>
                <div><dt>Model</dt><dd>{active.model_id}</dd></div>
                <div><dt>Audio sent</dt><dd>{Math.round(active.audio_bytes / 1024)} KiB</dd></div>
                <div><dt>Egress log</dt><dd>{active.log_id || "Not recorded"}</dd></div>
              </dl>
            </details>
          </div>
        ) : (
          <StatePanel title="Nothing selected" description="Choose a meeting transcript from the saved list." />
        )}
      </Panel>
      <p className="sr-status" role="status" aria-live="polite">
        {recording ? "Meeting recording in progress, " + elapsed + " seconds." : busy === "transcribing" ? "Meeting transcription in progress." : ""}
      </p>
    </>
  );
}
