# Auto-captions

The first AI feature in the video editor, and the most-used thing CapCut does.

```
voiceover ──→ transcribe ──→ words + timings ──→ cues ──→ text clips on a
   ▲              (model)      (deterministic)              captions track
   │                                                              │
imported, because nothing here                          editable like anything
generates speech                                        else, and read by a
                                                        person before it goes out
```

---

## The precondition nobody mentions

Auto-captions transcribe speech, and off_CRM had no speech. The image campaign
generates stills; nothing produced audio, and the timeline had no way to take
any in. So half of this feature is a media import path, and that is not padding
— without it the caption button has nothing to listen to.

`POST /campaigns/{id}/video-media` accepts a recording or a clip, reads its
header, and stores it the way a picture is stored: bytes on disk at 0600, a row
holding the path and the hash.

**The header is read before anything is kept.** A file that does not declare its
own length is refused, because a clip whose `source_duration` is a guess is a
clip the timeline cannot stop from reading past its own end. That is why WAV is
supported and MP3 is not: a WAV's length is `data size / byte rate`, exact and
in the header, while an MP3's can only be had by walking every frame in the
file. The refusal says so.

**Uploading the same file twice returns the row that already exists**, keyed on
a hash per campaign — otherwise the same recording gets transcribed twice.

**A picture cannot come in this way.** Pictures come from the image campaign and
its swipe, which is where their quality is judged; importing one here would
route around that.

---

## Sending audio is different, and the difference is not cosmetic

Every other path through the egress broker is protected by a pre-flight scan:
the payload is built from an allowlist, scanned for owner data, and **blocked**
if anything is found. That scan is the load-bearing part of the whole trust
model.

**Audio defeats it completely.** The bytes are a waveform. A recording of
somebody reading a customer list out loud scans perfectly clean, because there
is nothing there to read. This is not a gap that better regexes fix — it is a
category difference between text and audio.

So the protection that remains is structural:

| Rule | What it does |
|---|---|
| `TRANSCRIBE_FORBIDDEN_CLASSES` | `mailbox` and `internal` are refused **by class**, before a provider is even looked up. Their protection *is* the scan, and the scan cannot run. |
| The tier filter | Unchanged. A recording only reaches a provider already trusted with that class of material as text. |
| The text part | A language hint or vocabulary prompt is still built from the allowlist and still scanned — that part *is* scannable, so there is no reason to lower it. |
| The egress log | Records that a call happened, its size and the word count. **Never the audio and never the transcript** — a log holding the recordings would be a second copy of the most sensitive thing here. |

The API sends captions as `campaign` class: a voiceover recorded for a
marketing video is the owner's own material, not public, so the tier rules
narrow for it. There is a test asserting the refusal happens before any
provider lookup.

---

## Word timings, not sentence timings

The adapter asks for `verbose_json` with `timestamp_granularities[]=word`.

A caption timed to a *sentence* appears in full when the sentence starts and
sits there until it ends — a wall of text that arrives before it is spoken,
which is the opposite of what captions are for. Word timings mean each line
appears as it is said.

Hosts differ in how they return them: a flat `words` list, words nested inside
`segments`, or segments alone. All three are read, in that order. A
segment-only answer is **kept rather than refused** — sentence timings make
worse captions than word timings and much better ones than no captions.

---

## Where to break, and why it is not a model call

Asking a model where to break would be a second call, a second cost and a
second thing that has a bad day, to answer a question that has rules. The rules
are in `video/captions.py`, they are tested, and they run offline.

Four reasons to break, checked in this order:

1. **the sentence ended** — always right, and the only break a reader expects
2. **the speaker paused** (a gap over 0.6s) — a caption spanning silence looks stuck
3. **the line is as long as it can be** (42 characters, two lines of ~21, the broadcast convention)
4. **the caption has been up as long as one should be** (5 seconds)

A clause break — comma, dash, colon — is taken **only once the line is over
half full**. Breaking at every comma gives a stutter of two-word captions,
which is harder to read than the long line it was avoiding. There is a test
named for it.

A test also asserts that no word is lost between the transcript and the
captions: the joined caption text equals the joined transcript text.

---

## The timeline's invariant is the specification

Clips on a track cannot overlap by a single tick. Speech does not respect that:

- words run together, so consecutive cues can share a boundary
- a short cue stretched to be readable can reach into the next one
- two adjacent cues rounded to the same frame collide

So `lay_out` has to produce a **legal track** or the editor refuses the entire
batch — with a message about tick collisions rather than about captions, which
would be a confusing way to learn about a bug in the caption builder.

It snaps every cue to a frame, holds each one back to at least a frame before
the next starts, and stretches short cues towards the readable minimum **using
only the gap actually in front of them**. A cue that still cannot be given a
single frame is **merged into its neighbour rather than dropped**: losing a
word is worse than a short caption.

### Mapping media time onto the timeline

Three things have to be undone, and forgetting any of them puts the words in
the wrong place rather than raising:

- the clip starts somewhere on the timeline, not at zero
- the clip may be trimmed, so it reads from part-way into the media (`in_point`)
- the clip may not run at 1×, so a second of media is not a second of timeline

Words spoken outside what the clip actually shows are dropped — captioning a
trimmed clip should caption what is left, not what was cut. Both the trimmed
case and the slowed case have tests.

---

## Captions are ordinary clips

The result is not a special object. It is text clips on a track called
**Captions**, so every edit already in the editor works on them: retime one,
restyle it, fix a misheard word, delete a line, keyframe it.

That is also where the human decision sits. A transcript is a guess about what
was said and it goes out under the owner's name, so a person reads it before
anything is published — the same judgement the swipe and the post approval
already are.

Three consequences worth stating:

- **The whole set is one step of undo.** A minute of speech is forty captions,
  and forty undos to remove something asked for once is a chore, not a history.
- **Running it twice replaces rather than stacks.** The existing captions over
  the same span are removed in the same batch.
- **New pictures never land on the caption track**, or a placed still would
  appear in the middle of the subtitles.

Captions sit at 32% of the height above centre — clear of the subject, and
clear of the caption the *platform* draws over the bottom of the frame.

---

## The transcript is paid for once

Stored per media file and language, and reused unless `refresh` is asked for.

This is **not** the response cache. That one is keyed on a payload and refuses
anything whose output is a message, for a good reason: two prospects with the
same title can build a byte-identical payload, and a hit would send them the
same email. A transcript is a fact about a specific file that cannot change
unless the file does, which is exactly the case where storing an answer is safe.

---

## Using it

```
POST /campaigns/{id}/video-media          multipart: a voiceover or a clip
GET  /campaigns/{id}/video-media
GET  /video-media/{id}/file
POST /video-projects/{id}/place-media     {"media_id", "start"}
POST /video-media/{id}/transcribe         {"language", "refresh"}
POST /video-projects/{id}/captions        {"clip_id", "language", "style", "max_chars"}
```

Needs a connected provider hosting a speech model. **Groq hosts Whisper on the
same key as its chat models**, which is the cheapest route and is already in
`config/providers.yaml`; OpenAI's `whisper-1` is there too. A workspace with no
such provider gets a 409 naming what to connect, not an empty caption track.

In the UI: select the voiceover clip, press **Auto captions**.

---

## What is not built

- **Karaoke highlighting.** Word timings are stored on every cue, so the data
  is there; drawing a word-by-word highlight needs a text renderer that can
  colour part of a line.
- **Translation.** A second call on the transcript, which the broker can
  already make — it is simply not wired.
- **Speaker labels.** Whisper does not diarise; that is a different model.
- ~~**Imported footage is audible but not drawable.**~~ No longer true. The
  browser demuxes and decodes footage now, so a clip that was captioned shows
  its own picture in the preview and in the export, and the manifest no longer
  refuses to call the project renderable. See "The picture: demuxing in the
  browser" in `VIDEO_EDITOR.md`.
- **No recording in the browser.** The UI takes a file. `MediaRecorder` would
  do it and it is not wired.
- **Nothing chooses the language.** It is passed through if given, and detected
  by the model otherwise.
