# The video editor

A timeline editor for the pictures this project generates. CapCut's shape —
tracks, clips, keyframes, a scrubbable preview, an export — built on the assets
the image campaign already produces and feeding the distribution campaign that
already publishes.

`docs/architecture/CAPCUT_FEATURE_MAP.md` is the inventory this was cut from.
This document is what exists.

```
approved picture ─┐
text / colour     ├─→ timeline ──→ edits ──→ manifest ──→ browser renders ──→ gates ──→ render
audio             ─┘       ▲                                                              │
                           └────────── undo / redo ──────────┘                            ▼
                                                                          an asset the distribution
                                                                          campaign can publish
```

---

## Where the work happens

**The server owns the document. The browser draws it.**

Every edit is a named operation sent to the server, validated there, and
returned as a new document that the screen redraws from. That costs one round
trip per edit and buys the property the whole feature rests on: there is one
place that decides whether an edit is legal, and it is the same place that
checks the exported file.

The browser does the part that needs a compositor and a GPU — painting frames
and encoding them. Every machine running off_CRM has both.

| Layer | Where | Why there |
|---|---|---|
| Document, edits, invariants | Python | Rules belong where they can be tested offline |
| Frame resolution | **Both** | A preview cannot make a request per frame |
| Painting, encoding, muxing | Browser | A canvas is already a compositor |
| Gates on the result | Python | A renderer checking its own output cannot fail |

---

## Time is an integer, and the unit is 1/90000 of a second

Seconds as floats are how an editor rots. Split a clip, trim it, split again,
and the boundaries drift until a cut lands half a frame early with no way to say
which operation did it. Frames are exact but tie the document to one frame rate,
so changing a project from 30fps to 24fps would move every edit ever made in it.

90kHz is the MPEG timebase, chosen for one arithmetic reason:

| Rate | Ticks per frame | Exact |
|---|---|---|
| 24 | 3750 | yes |
| 25 | 3600 | yes |
| 29.97 | 3003 | yes |
| 30 | 3000 | yes |
| 50 | 1800 | yes |
| 60 | 1500 | yes |

A split at frame 100 is *the same integer* however many times the project is
saved, reloaded and re-split. An unlisted frame rate is refused rather than
rounded, because rounding it would move every cut in the project.

---

## The invariants, which are most of the code

**Clips on a track never overlap.** Not "should not" — cannot. Every operation
that moves or resizes a clip re-checks the whole track and raises. An overlap
has no defined answer: two clips both claiming tick 500 means the renderer picks
one, and which one it picks is an implementation detail that can differ between
the preview and the export. That is the worst class of bug a video editor can
have, so it is made unrepresentable rather than handled.

**An edit either applies completely or leaves the document untouched.** Every
operation copies the project through `to_dict` → `from_dict` before changing
anything. That is slower than mutating in place and it means a refused edit
cannot half-apply, and a document that would not serialise fails at the edit
rather than at save time. A refused edit also does not consume a step of undo.

**A cut is not a one-frame overlap.** A clip is live when
`start <= tick < end`. A clip ending exactly where the next begins is the
ordinary result of a split, and treating both as live at the shared tick would
double every cut in every project.

**Keyframes are relative to the clip.** A fade starting 200ms into a clip has to
still start 200ms in after the clip is dragged elsewhere. Absolute keyframe
times are the version of this that looks correct until someone moves something.

**A split is transparent.** Cutting a clip in the middle of a zoom changes
nothing about what is on screen at any instant — both halves carry a synthesised
keyframe at the cut so the animation continues through it. A naive shift leaves
the second half restarting from its first keyframe's value, which shows up as a
jump on exactly the frame the viewer is looking at. There is a test that
resolves every tick either side of a split and asserts the two lists are equal.

**Trimming the head moves the animation with the material**, for the same
reason — keyframes are anchored to the footage, not to the timeline.

---

## The conformance fixture

The browser resolves keyframes itself, so there are **two implementations of one
rule** — `video/timeline.py` and `frontend/src/video/resolve.ts`. Two
implementations drift, and the way that drift shows up is the worst kind: the
preview looks right, the export does not match it, and nothing failed.

`tests/fixtures/timeline_conformance.json` holds one deliberately awkward
document — overlapping tracks, a hidden one, a muted one, a clip at 0.5× whose
source time is not its timeline time, every easing, fades meeting in the middle
— and the frame Python resolves at fifteen chosen ticks. The ticks are chosen,
not evenly spaced: the interesting instants are the boundaries, and an even
spread walks past every one of them (`0`, `1`, the tick before a cut, the cut,
the tick after, the last tick, one past the end).

Both suites assert against that file. Whichever side moves, a test goes red.

```
python scripts/build_timeline_fixture.py     # regenerate, deliberately
```

It also forced one piece of care: Python's `round()` breaks ties to even and
JavaScript's `Math.round` breaks them upward, so `resolve.ts` implements
`roundHalfToEven`. One tick is invisible on screen and is still a difference,
and a conformance check that tolerates "close enough" stops being able to tell
drift from noise.

---

## Export: WebCodecs, and no fallback

Frames are painted by the same function the preview uses, handed to a
`VideoEncoder`, and muxed into WebM by a hand-written EBML muxer.

**The obvious fallback — `MediaRecorder` on a captured canvas stream — was left
out on purpose.** It records in real time, so a two-minute video takes two
minutes; it drops frames silently when the tab is busy; and it writes a WebM
with no Duration field, because a streaming muxer does not know the length in
advance. That last one means the export gate could never do the check it exists
to do. A fallback whose output cannot be verified is not a fallback, it is a
quieter failure, so a browser without WebCodecs is told plainly what it needs.

Writing the muxer is the same call `imagery/gates.py` made about Pillow: two
hundred lines of exact format work against a dependency. It buys an exact
Duration written from the timeline that produced it, which is what makes the
gate meaningful.

Frame times come from the tick clock — frame *n* is at `round(n * ticksPerFrame)`
— never from an accumulating float. At 29.97fps an accumulator drifts by a frame
every few minutes, and the drift lands in the timestamps, where it becomes audio
sync error.

---

## Reading a video's shape without a decoder

`video/gates.py` parses MP4 and WebM headers by hand, the way `imagery/gates.py`
parses PNG, JPEG, GIF and WebP. MP4 is a tree of length-prefixed boxes; WebM is
EBML, the same idea with variable-length integers. Width, height, duration and
the track list are all header fields. Decoding a frame would need a codec;
reading the shape of the file does not.

Two details that are not obvious and are both tested:

- **The MP4 display matrix.** A phone records landscape and rotates on playback.
  A 90° rotation puts a zero in the top-left of the matrix, and the header
  dimensions are pre-rotation — reporting those would call a portrait video
  landscape and fail the aspect gate for no reason.
- **Version 1 boxes.** Files over 4GB widen three fields to 64 bits, which moves
  the matrix twelve bytes later. Getting that wrong reads the volume field as a
  rotation. A test caught exactly this during the build.

### The gates

| Gate | Catches |
|---|---|
| `decodes` | not a file |
| `not_empty` | a container with a header and no frames — the encoder ran, nothing was painted |
| `readable_header` | truncated, or a moov that was never written |
| `has_video_track` | an audio file with a video extension |
| `aspect_ratio` | an export of the wrong shape, within 5% for macroblock rounding |
| `duration_matches` | an export that stopped somewhere other than the end of the edit |
| `not_duplicate` | the same bytes stored twice |

A failing render is **stored anyway**, with its report. A gate result nobody can
check the file against is an assertion, not evidence.

---

## How this was verified

Not only by unit tests. The container and the pixels were checked against things
outside this project:

1. **`tests/fixtures/muxed_sample.webm` is written by the TypeScript muxer**
   (`cd frontend && npm run fixtures`) and parsed by the Python gates in CI. One
   language writes the format, the other reads it, and neither can drift alone.
2. **ffmpeg reads that file** as `matroska,webm 1080x1920, 3.00s, vp9, 30fps`.
3. **A real Chromium export**, driven headless: a document with a scale ramp and
   a text clip, encoded through WebCodecs and muxed by `webm.ts`. The gates
   passed it, and ffmpeg decoded its frames.
4. **The pixels were measured, not eyeballed.** Frame 0 of that export decodes
   to a blue rectangle of exactly 432×768 at (324, 576) — precisely scale 0.4 of
   a 1080×1920 canvas, which is what the keyframe at tick 0 says it should be.

---

## Storage

Its own database, like the image and distribution runners.

| Table | Holds |
|---|---|
| `video_projects` | the current document and a version number |
| `video_history` | every version there has ever been |
| `video_renders` | the exported file: path, hash, gates, which version it came from |

**Undo is a pointer move, not an inverse operation.** There is no "unsplit" that
has to reconstruct what a split destroyed, because the document from before the
split is still there. It survives a reload, so closing the tab does not throw
away an hour of work the way an in-memory stack does. Editing after an undo
drops the abandoned branch — otherwise redo could restore something from a
history that no longer follows from the current document.

History is capped at 300 versions. Every keystroke on a text clip is an edit,
and an uncapped history grows without bound for a document nobody is finished
with.

Renders are **files at 0600** with a row holding the path and the hash, exactly
as pictures are.

---

## Which campaign owns a timeline

The **image** campaign, whose registry entry has said from the day it was
written that video was what it was missing. A video project consumes that
campaign's kept pictures and produces another asset for it. Every entry point
checks the kind, the same way the image and distribution runners check each
other — and a project cannot be opened through a campaign of a different kind
even if its id is known.

---

## Using it

```
GET    /video/presets                              canvas shapes, frame rates, edit names
POST   /campaigns/{id}/video-projects              {"name","preset","fps"}
GET    /campaigns/{id}/video-projects
GET    /campaigns/{id}/image-assets?status=approved  what can go on the timeline
GET    /video-projects/{id}                        the document
POST   /video-projects/{id}/edit                   {"op","params"} or {"operations":[…]}
POST   /video-projects/{id}/undo | /redo
GET    /video-projects/{id}/history
GET    /video-projects/{id}/manifest               what to draw, and what is wrong
GET    /video-projects/{id}/frame?tick=            the server's answer for one instant
POST   /video-projects/{id}/place-asset            a kept picture onto the timeline
POST   /video-projects/{id}/renders                multipart: the exported file
GET    /video-renders/{id}/file
```

The batch form of `/edit` exists because a drag produces a stream of moves and
undo should return to where the drag began, not to the middle of it.

`/manifest` reports warnings, and they are the point: a timeline can reference a
picture that was swiped away after it was placed, and the honest thing is to say
so **before** an export runs rather than render a black hole and hand back a
file that looks finished.

### The screen

**Video editor**, under a Video group in the sidebar. Canvas preview, transport,
a timeline with tracks and draggable clips, trim handles, and an inspector.
Space plays, S splits, Delete removes, Shift+Delete closes the gap, Ctrl+Z and
Ctrl+Shift+Z walk the history, arrows step a frame and Shift+arrows step ten.

---

## What is not built

Stated in the same detail as what is, because the gap here is large and the
feature map makes it look larger.

- **Nothing AI does anything yet.** Captions, auto-cutout, auto-reframe, object
  removal, text-to-video — every row marked **M** in the feature map — is a
  model call through the broker, and none is wired. The timeline is the thing
  they will all edit; this is the floor they stand on.
- **Video clips are modelled but there is no video material.** The document,
  the gates, speed, in-points and source duration all handle video. The image
  campaign generates stills, so nothing produces a video asset to place yet.
- **Audio is modelled and not exported.** Tracks, gain, fades and volume
  keyframes all resolve, and the muxer has an audio track ready. Nothing
  generates audio to put on it, so the exporter writes video only.
- **No transitions.** A dissolve is two clips overlapping in time, which the
  no-overlap invariant currently forbids on one track. It needs a real transition
  object between adjacent clips rather than a relaxed invariant.
- **No transcript, so no text-based editing.** That needs speech-to-text, which
  is a model call.
- **No auto-reframe.** Changing the canvas deliberately does not move anything:
  reframing every clip for a new aspect ratio is a model call, and a crude
  version would slice subjects down the middle and call it done.
- **The export holds the whole file in memory.** Fine for a sixty-second
  vertical video; not fine for ten minutes at 4K.
- **One fade per clip, governing picture and sound together.** Separate video
  and audio fades are real; a clip whose picture fades while its audio stays at
  full is worse than either, so one fade drives both until there are two.
