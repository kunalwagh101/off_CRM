# S-07.01.03 — Meeting transcription without a bot

## What the story means

The owner can turn a meeting into a private transcript without inviting a
recording bot into the call.

The browser records two sources the owner explicitly grants:

1. microphone audio;
2. audio from the screen or browser tab the owner explicitly shares.

Those sources are mixed **in the browser**. Nothing is uploaded while recording.
When the owner presses **Stop & transcribe**, one audio blob is sent to the
off_CRM process running on the same machine. off_CRM then sends that audio
directly to the declared transcription provider.

Raw meeting audio is never written to an off_CRM file, database row, cache or
egress log. The stored object is the transcript plus word timings and audit
metadata.

## Data flow

```text
microphone ─┐
            ├─ Web Audio mixer ─ MediaRecorder ─ browser-memory Blob
shared tab ─┘                                  |
                                               | Stop & transcribe
                                               v
                                  loopback-only POST /meetings/transcribe
                                               |
                                      in-memory byte buffer
                                               |
                                               v
                                    EgressBroker.call_transcript
                                               |
                          DataClass.MEETING → Tier A only
                                               |
                                               v
                              Mistral / voxtral-mini-latest
                                               |
                                      text + word timings
                                               |
                         +---------------------+------------------+
                         |                                        |
                         v                                        v
                 private MeetingStore                       egress log
                 transcript JSON only                 size + word count only
                 mode 0600 / dir 0700              NO audio / NO transcript
```

## Why this uses AI

Speech-to-text is the one part where a model is genuinely needed. Recording,
mixing, permissions, routing, storage and the UI are deterministic host code.

There is deliberately **no second model call** for summarisation or action-item
generation in this story. A verified transcript is the deliverable. Turning it
into semantic notes is a separate product decision because it creates another
egress path for meeting content.

## The trust rule

A waveform defeats off_CRM's text scanner. A recording can contain a password,
customer list or internal strategy while its raw bytes look like harmless
binary data.

For that reason meeting audio is its own data class:

```text
DataClass.MEETING
```

Only Tier A providers may receive it.

OpenAI Whisper and Groq Whisper remain useful for lower-sensitivity caption work,
but they are Tier B in this registry and therefore cannot receive meeting audio.
There is no override from the Meeting Notes screen and no automatic downgrade.

### Tier A transcription provider

Verified against Mistral's official documentation on 2026-09-19:

- endpoint: `POST /v1/audio/transcriptions`;
- current recommended batch transcription alias: `voxtral-mini-latest`;
- word timestamp granularities are supported;
- the endpoint is OpenAI-SDK compatible for the fields used here.

The source and packaged provider registries both declare
`voxtral-mini-latest` as `kind: transcribe` under Mistral.

Official references:

- https://docs.mistral.ai/api/endpoint/audio/transcriptions
- https://docs.mistral.ai/capabilities/audio/transcription
- https://docs.mistral.ai/getting-started/models/models_overview

Mistral currently documents a conflict between manual `language` selection and
timestamp granularities. Meeting Notes therefore uses automatic language
detection instead of exposing a language hint that would make the requested word
timestamps invalid.

## Local-only boundary

The browser upload is allowed only when **both** are loopback:

- the HTTP `Host` header;
- the actual peer address seen by the ASGI request.

Accepted examples are literal `localhost`, `127.0.0.1` and `::1`.
No hostname is DNS-resolved into a loopback answer.

Why both checks matter:

- checking only Host can be spoofed by a remote peer;
- checking only peer can still make a reverse proxy turn a hosted server into an
  audio relay.

The local check executes before the upload body is read or a provider is called.
A hosted off_CRM deployment returns a structured 403 explaining that the owner
must open off_CRM on the machine where the meeting is playing.

This is stricter than ordinary authenticated API access on purpose. If a hosted
off_CRM server accepted the recording, raw meeting audio would already have left
the owner's machine before the declared transcription provider saw it, violating
the story.

## Browser capture

`frontend/src/meeting/capture.ts` uses browser-native APIs already available in
the supported product environment:

- `getUserMedia({audio: ...})` for microphone;
- `getDisplayMedia({video: true, audio: true})` for the owner's explicit tab or
  screen share;
- `AudioContext` to mix the two sources;
- `MediaRecorder` to record only the mixed audio stream.

The display video track is requested because browsers expose shared-system audio
through display capture. That video track is **never attached to the recorder**.

If the chosen share exposes no audio track, capture fails immediately with an
instruction to enable **Share audio**. The product does not silently fall back to
microphone-only notes because that would create a transcript that appears
complete while omitting every remote participant.

All microphone and display tracks are stopped on:

- successful Stop;
- Cancel;
- permission/capture failure;
- screen-audio sharing ending;
- component unmount.

The capture helper contains no `fetch` or API dependency. Tests spy on network
access and prove recording itself makes no request.

## Browser permission policy

The response `Permissions-Policy` is deliberately narrow:

```text
camera=(), microphone=(self), display-capture=(self), geolocation=()
```

Camera and geolocation remain disabled. Microphone and display capture are
available only to this same-origin application.

## API contract

### POST /api/v1/meetings/transcribe

Multipart fields:

- `file` — WebM, Ogg, WAV or MP4 audio;
- `title` — optional, max 200 after validation.

Controls:

- loopback Host + peer required before reading audio;
- declared Content-Length is an early rejection only;
- actual read is capped at 128 MiB and remains authoritative;
- empty audio rejected;
- unsupported MIME type rejected;
- filename reduced to its basename before it is handed to the provider;
- request uses `DataClass.MEETING`;
- lower-tier transcribers are filtered before a provider call;
- raw audio buffer is not accepted by the storage layer.

### GET /api/v1/meetings

Loopback-only. Returns transcript metadata, not transcript bodies, so the list is
small and accidental UI dumps do not copy every meeting's text.

### GET /api/v1/meetings/{id}

Loopback-only. Returns one transcript and word timings. Meeting ids are validated
against a closed pattern, so a URL cannot walk the local filesystem.

## Persistence

`MeetingStore` writes one JSON file per meeting under:

```text
<OFFSETX_DATA_DIR>/meetings/
```

Directory permissions are `0700` and file permissions are `0600` where the
host OS supports POSIX modes.

The write is atomic:

```text
create unique .tmp → write → flush → fsync → chmod → os.replace
```

Stored fields:

- meeting id and title;
- UTC creation time;
- transcript;
- word timings;
- detected language;
- provider and model;
- transcription duration;
- number of bytes that were sent;
- egress-log id.

There is **no raw_audio field** and the store's API does not accept audio bytes.

Word timings reject negative, reversed, NaN and infinite values before writing.

## Egress log

The existing transcription broker records:

- provider and model;
- trust tier;
- data class = `meeting`;
- request status and duration;
- number of audio bytes sent;
- number of returned timed words.

It does **not** record the raw audio or the returned transcript. A focused test
uses deliberately secret byte/text markers and verifies neither can be found in
the saved egress record.

## Configuration UX

Meeting capture remains disabled until all of these are true:

- the browser is on a loopback off_CRM origin;
- the browser supports secure media capture;
- Mistral is connected;
- the connection is still Tier A;
- `voxtral-mini-latest` is among the owner's enabled models.

The screen says exactly how to fix a missing transcriber. It does not silently
turn on a model the owner did not select.

## Security and privacy properties

The story specifically proves:

- no meeting bot joins a call;
- no network request occurs while recording;
- no system audio means no recording;
- remote Host or peer is refused before provider work;
- meeting audio cannot fall below Tier A;
- OpenAI/Groq transcription is rejected for `MEETING`;
- recording bytes are absent from local persistence;
- transcript text and recording bytes are absent from the egress log;
- transcript paths cannot traverse out of the meeting directory;
- output records are private on POSIX hosts;
- malformed/non-finite timings do not enter storage.

## Failure behaviour

A failure is explicit and leaves no fake transcript.

Examples:

- permission denied → explain that microphone/screen-audio permission is needed;
- system audio absent → explain **Share audio** must be enabled;
- share ends → stop the recording flow rather than keep recording a partial mic
  track;
- hosted origin → 403 local-only message;
- no configured Tier A transcriber → tell the owner to connect Mistral and enable
  `voxtral-mini-latest`;
- provider fails → existing broker failover stays inside the same trust tier;
- provider returns no useful transcript → no local meeting record is created.

## Rollback

There is no database migration.

Code rollback removes:

- Meeting Notes navigation/page/capture helper;
- three meeting API endpoints;
- the `MEETING` data class;
- the Mistral Voxtral registry entry;
- `MeetingStore`.

Existing transcript JSON files are derived local records and are not interpreted
by other product modules. They can remain on disk or be manually backed up
before rollback.

The response permission policy should return to its previous microphone/display
deny state if the feature is removed.

## Known limits

- No speaker diarisation.
- No semantic summary or action-item model.
- No calendar integration.
- No bot auto-join or auto-attendance.
- No cloud recording.
- No live captions during the call.
- Browser/system support for shared audio varies by OS and browser; the product
  refuses a share that does not actually expose an audio track.
- A live provider call is environment-gated because it requires an owner's
  Mistral API key and a real captured recording.
