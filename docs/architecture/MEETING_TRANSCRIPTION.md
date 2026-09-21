# S-07.01.03 — Local meeting transcription with no bot

## Goal

Capture a meeting without inviting a recording bot or persisting raw audio.

## Data flow

```text
microphone ─┐
            ├─ browser AudioContext mix ─ MediaRecorder ─ transient Blob chunks
system/tab ─┘                                      │
                                                  ▼
                                      localhost off_CRM API
                                                  │
                                      governed EgressBroker
                                                  │
                                 declared transcription provider
                                                  │
                                                  ▼
                                transcript + timing/provenance only
                                          meeting_transcripts.db
```

## Custody boundary

Capture mutation endpoints require both:

1. a backend bound to loopback; and
2. a browser Origin whose hostname is localhost / 127.0.0.1 / ::1.

A hosted deployment cannot receive meeting audio.

The browser gets microphone and screen/tab-system-audio permission directly.
It mixes the two locally with Web Audio and records bounded chunks with
`MediaRecorder`. off_CRM never writes the raw bytes to disk or IndexedDB.

If capture setup fails, tracks are owned and stopped immediately. If a final
chunk fails transcription, the page keeps that raw Blob only in memory and
offers Retry & finish or Discard unfinished.

## Provider boundary

The owner chooses the transcription provider/model before capture. The API stores
that pair on the meeting and the transcriber refuses a later chunk that tries to
change either value. Audio therefore cannot be redirected by a later request.

All provider I/O still goes through `EgressBroker.call_transcript`; the meeting
package owns no provider transport.

## Persistence

`meeting_transcripts.db` stores:

- meeting/workspace id;
- derived transcript;
- word timing metadata;
- provider/model/language and egress log id;
- chunk digest/status/byte count.

It does not store raw audio.

The database participates in encrypted backup/restore and the privacy inventory.
A strong subject match deletes the whole matching meeting + chunk transcript
history.

## Verification

```bash
uv run pytest tests/test_meeting_transcription.py tests/test_privacy.py -q
npm test --prefix frontend
npm run build --prefix frontend
```

Owner verification additionally requires a real localhost browser:
share system/tab audio, permit microphone, speak/play audio, stop, and compare
the transcript while confirming no raw recording file was created.

## Migration / rollback

The meeting SQLite schema is additive. Older code ignores
`meeting_transcripts.db`. Rollback can leave the DB in place safely.

Raw-audio archival, speaker diarisation and cloud-hosted capture are out of
scope for this slice.
