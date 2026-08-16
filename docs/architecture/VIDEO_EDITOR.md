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
| The audio mix, as a plan | **Both** | Deciding the gain shape is arithmetic; applying it needs a decoder |
| Demuxing and decoding footage | Browser | The codec is already there and the frames are needed per frame |
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

**Re-basing keyframes shifts them; it does not rebuild them.** An earlier
version synthesised a keyframe at each boundary from the interpolated value,
which is exact for a linear segment and wrong for every other kind — a sub-range
of an ease-out curve is not itself an ease-out curve, so re-easing the halves
changed the shape between the samples. Splitting mid-ease visibly altered the
animation, and the test that should have caught it happened to use a linear
segment. Shifting reproduces the curve exactly because it is the same control
points from a new origin; everything outside the range is dropped except the
nearest keyframe on each side, which are the two that anchor the boundaries.
Exact, and bounded.

---

## Transitions, without relaxing the invariant

A dissolve needs both clips on screen at once. Clips on a track cannot overlap
by a tick. Those two facts look like a contradiction and the tempting fix —
allowing transitions to overlap — would reopen the exact bug the invariant
exists to prevent: two clips claiming one tick, with the preview and the export
free to disagree about which wins.

So the clips stay adjacent and untouched, and a **`Transition` object on the
track** declares how far either side of their shared cut both are drawn. The
overlap becomes a bounded, declared property of the boundary rather than an
accident of two clips' positions.

| Rule | Why |
|---|---|
| Both sides get **one shared `progress`**, 0 → 1 across the window | Two clocks are how the halves end up disagreeing about where the middle is |
| A clip drawn past its end is **held at its last frame** | Otherwise it reads past the end of its own material — the thing the validator exists to prevent |
| One transition per cut | Two blends over the same frames has no defined answer |
| Halves at both ends of a clip must **fit inside it** | If they overlap each other, a frame belongs to two blends |
| An edit that destroys the cut **removes the transition** | Otherwise it lingers as a ghost that reappears if the clips ever line up again |

**46 presets over 9 families.** The families are code in
`frontend/src/video/transitions.ts`; the presets are rows in
`video/presets.py`. A new transition is a row and nothing else — which is what
makes the space searchable by something choosing a look, per
`CAPCUT_TOOL_INVENTORY.md`.

Animations work the same way, except they are not even a new concept: applying
one **writes ordinary keyframes**, so it survives a split, travels with a trim
and resolves identically in both languages, because all of that already worked.

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

## The sound: a plan, not samples

Until Stage 4 every file off_CRM produced was silent. The timeline had resolved
gain per clip per instant since the day it was written and the exporter threw
all of it away. Platforms bury silent video, so this was the difference between
an export that can be posted and one that cannot.

The obvious fix is to ask the resolver what the gain is and write a sample. At
48kHz that is forty-eight thousand resolver calls a second, to produce a number
that changes a few times across a whole clip — and it would mean a second mixing
implementation in Python that nothing ever runs, since the audio is assembled in
the browser where the decoder is.

So `video/mixdown.py` produces an **envelope**: the points at which each clip's
gain changes, in the clip's own time. WebAudio applies exactly that shape with
`setValueAtTime` and `linearRampToValueAtTime`, which is what a `GainNode` is
for. The arithmetic that decides the shape stays in Python, testable and
offline; the sample-pushing stays where the samples are.

**Where the envelope is dense and where it is not.** Between two keyframes the
gain is a straight line, and a straight line needs its two ends. Two things bend
it: an eased keyframe segment, and a fade — which is linear on its own but
*multiplies* the volume curve, so a fade over a ramp is a product of two lines
and therefore a parabola. Those stretches, and only those, are sampled at 100Hz,
and whatever turns out straight anyway is collapsed back to its endpoints. A
constant clip is two points; a one-second linear fade is three; a two-second
eased ramp is about eighty.

| Piece | Does |
|---|---|
| `video/mixdown.py` | plans the mix: which clips, read from where, at what gain shape |
| `frontend/src/video/mixdown.ts` | the same plan in the browser, pinned to the same fixture |
| `frontend/src/video/audio.ts` | `OfflineAudioContext` renders it, `AudioEncoder` makes it Opus |
| `frontend/src/video/webm.ts` | muxes the Opus track alongside the video one |

Three decisions worth naming:

- **A video clip is in the mix.** Its sound travels inside the same container as
  its picture, and `decodeAudioData` reads it out. The picture cannot be drawn
  yet, but leaving footage out of the mix because its picture is unfinished
  would be keeping the wrong half.
- **The gain rule lives in one function.** `clip_gain()` in `timeline.py`,
  `clipGain()` in `resolve.ts`. The preview reads it through the frame resolver
  and the mixer reads it directly, and those two disagreeing would be a preview
  that lies about the file it is previewing.
- **Clipping is scaled, not clamped.** Two clips at full volume sum to 2.0 and
  the samples wrap into a rasp. `headroom()` reports the worst-case sum and the
  whole mix is scaled by its reciprocal — uniform, so the balance between clips
  is untouched — and the export says it happened rather than quietly changing
  how loud someone's video is. The manifest says it *before* the render, so it
  can be fixed properly instead.

**Deliberately not built:** ducking, compression, EQ, normalisation. Each is a
real feature and each changes what the mix *sounds* like rather than what it
*is*; building them before the plain mix works would mean debugging two things
at once. `headroom()` is the number auto-ducking will act on when it arrives.

The plan is in the conformance fixture's `mix` block, so the two planners are
pinned to one file exactly the way the two resolvers are — including the number
of points in each envelope, because the same curve described in a different
number of points means one simplifier moved.

And the gate closes the loop: the server plans the mix itself, so if the
timeline makes a sound and the file that comes back has no audio track, the
render fails. A browser that could not encode Opus hands back a perfectly good
picture, and a silent video nobody noticed was silent is the exact failure this
stage exists to prevent.

---

## The picture: demuxing in the browser

`paintFrame` could always draw a video frame — its `AssetSource` is a
`CanvasImageSource` and a `VideoFrame` is one, so the painter needed no change
at all. What was missing was anything that could produce *the frame at a given
instant*, and that needs two things the platform does not hand over: a demuxer
and a decoder. The decoder is `VideoDecoder`, which is free. The demuxer is
`video/demux/`.

**Why not a `<video>` element.** Setting `video.currentTime` and calling
`drawImage` reads as much simpler and is worse in three ways that all matter
here. A seek costs tens of milliseconds and an export asks for every frame in
order, so a sixty-second render pays about a minute in seeks alone. It cannot be
done in a worker or against an `OffscreenCanvas`, because a `<video>` needs a
document. And it gives no way to *hold* a decoded frame, which is what freeze
frame and reverse are made of. A decoder fed in order does the same work once,
forwards, at decode speed.

| Piece | Does |
|---|---|
| `demux/matroska.ts` | walks EBML into Clusters and reads the SimpleBlocks |
| `demux/isobmff.ts` | expands MP4's five parallel sample tables into one frame list |
| `demux/index.ts` | dispatches on the container's own magic; asks `isConfigSupported` |
| `footage.ts` | a cursor, a decoder and a small frame cache per clip |

The two parsers are one level deeper than `video/gates.py`, which already walks
both formats on the server to read a file's shape. Same boxes, same elements.

**Forward-only, and that is the design.** A decoder cannot start anywhere: it
needs a keyframe and then every frame between that keyframe and the one you
want. So `Footage` keeps a cursor, feeds chunks in decode order and holds the
last dozen decoded frames. An export asks in increasing order, so the cursor
never goes backwards and each frame is decoded exactly once. Scrubbing jumps
around, and a jump backwards or into a different group of pictures restarts from
that group's keyframe — which is what a seek costs in any editor.

Four things that are not obvious and are each a test:

- **Decode order is not presentation order.** Anything with B-frames stores
  frames in the order they must be *decoded* and displays them in another. The
  frame list stays in decode order, because that is what a decoder has to be
  fed, and a separate index sorted by presentation time answers "which frame is
  showing at T". MP4 spells the difference out in its `ctts` table; the fixture
  carries one.
- **A flushed decoder will not take a delta frame.** Flushing is how you make a
  reordering decoder give up what it is holding, and afterwards it has forgotten
  everything a delta frame refers back to. Flushing on a hunch — `decodeQueueSize`
  hits zero when a chunk is *accepted*, long before its frame comes out — meant
  flushing on the first frame of every file and then refusing the second. Real
  Chromium found that one.
- **One clip, one cursor.** Two clips of the same recording at different points
  each get their own reader over shared bytes. Sharing one would make each seek
  the other backwards on every frame. The asset table is keyed by clip for
  footage and by asset for stills, which is the whole difference between them.
- **An output frame is an interval, not an instant.** A container stores times
  in its own units, so 30fps footage has frames at 33ms and 67ms while a 30fps
  timeline asks at 33.333ms and 66.667ms. Sampled at the leading edge that asks
  for frame 1 twice and never asks for frame 2 — a third of the footage silently
  replaced by duplicates. The exporter samples half an output frame ahead, at
  the middle of the interval the frame actually covers, and every source frame
  is then asked for exactly once. A preview passes nothing: the playhead is a
  real instant.

**What the server cannot check.** There is a gate for a missing audio track,
because a header says whether one exists. There is no equivalent for footage: a
clip that drew as a red hole produces a file whose header is perfect. So the
browser reports per-file failures instead — a container it cannot parse, a codec
this browser will not take — and one unreadable import costs its own clip rather
than the whole render.

---

## Time remapping: one integral, three features

Freeze frame, reverse and speed curves look like three items in a menu. In the
document they are one thing — how a clip's own offset maps to a position in its
material — and building them as three would have meant three answers to that
question that have to agree.

At a constant rate the map is a multiplication: `source = in_point + offset ×
speed`. A **speed curve** makes it the integral of a rate that varies, a
**freeze** is that same integral with the rate at zero, and **reverse** walks
the same span from the far end. So there is one function, `Clip.source_at`, and
`speed × offset` is simply what it computes when there is no curve — which is
why the conformance frames came out unchanged when it landed.

```
consumed(t) = ∫₀ᵗ speed(u) du        the area under the speed curve
source_at(t) = in_point + consumed(t)                    forwards
             = in_point + consumed(duration) − consumed(t)   reversed
```

**The curve is straight between its points, and that is a decision.** CapCut's
speed curves are beziers. A bezier's integral is fine on paper and a problem
here: the resolver exists twice, in Python and in TypeScript, and the two have
to agree *to the tick* or the preview stops describing the export. Straight
segments make each piece a trapezoid — `(v₀+v₁)/2 × Δt` — which is the same
arithmetic in both languages on the same doubles. An eased speed point is
refused, and the error says to use more points instead.

**A speed of zero is a freeze, not a missing value.** That is what lets a frozen
stretch live *inside* a curve, which is what every "bullet time" preset is:
`bullet` runs in at 3×, holds at 0 for a fifth of the clip, and runs out at 3×.
Two places had to learn not to write `float(speed or 1.0)` — the same
falsy-zero shape that once restarted a paused campaign.

**Presets are rows, families are code**, the same as transitions and animations.
Twelve curves over four families — `ramp`, `hero`, `impact`, `loop` — each a
list of `(fraction, speed)` points, so one preset fits a clip of any length.
Each carries its `average`, which is the number that decides whether a clip
still fits inside its own source: a `hero` ramp averages 1.10×, so a ten-second
clip on one needs eleven seconds of material. `apply_speed_curve` with
`keep_duration=False` divides by that average to find the length at which the
curve consumes exactly what the clip consumed before.

**Retimed sound is left out, and the manifest says which clips and why.**
Resampling audio is not playing it faster — it is deciding what to do about the
pitch, and that is a feature of its own. Playing a clip's audio at one rate
underneath a picture doing something else would drift further apart the longer
the clip ran, so `mixdown.retimed_reason` names the clip and the reason and the
mix goes on without it. The picture is unaffected.

**One bug here only a real browser could find.** The exporter samples the middle
of an output frame rather than its leading edge (see the footage section), and
it originally did that by adding `half a frame × clip.speed` to the resolved
source time. That is wrong twice over once time is remapped: a reversed clip
moves *backwards* through its material, and a curved clip's local rate is not
its `speed` field at all. It now resolves a second frame half a step later and
takes each clip's source time from that — while still drawing the cast of the
first, because at a cut the two hold different clips.

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
| `has_audio_track` | a silent file from a timeline that makes a sound — only asked for when the mix plan says so |
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
   `muxed_sample_audio.webm` is the same file with an Opus track, carrying the
   real `opusHead()` bytes `audio.ts` writes — the Python parser reads 48000Hz
   and 2 channels back out of it.
2. **ffmpeg reads that file** as `matroska,webm 1080x1920, 3.00s, vp9, 30fps`.
3. **A real Chromium export**, driven headless: a document with a scale ramp and
   a text clip, encoded through WebCodecs and muxed by `webm.ts`. The gates
   passed it, and ffmpeg decoded its frames.
4. **The pixels were measured, not eyeballed.** Frame 0 of that export decodes
   to a blue rectangle of exactly 432×768 at (324, 576) — precisely scale 0.4 of
   a 1080×1920 canvas, which is what the keyframe at tick 0 says it should be.
5. **The samples were measured too.** A real 3-second WAV — 440Hz left, 660Hz
   right — placed on an audio track with a one-second fade at each end, exported
   through headless Chromium, then decoded back by Chromium's own demuxer and
   Opus decoder. ffmpeg reads the result as
   `matroska,webm … vp9 1080x1920 30fps / opus 48000 Hz stereo, 3.00s`, and the
   gates pass it. The RMS of the decoded left channel per quarter-second:

   | Window | Measured | Predicted from the envelope |
   |---|---|---|
   | 0.00–0.25s | 0.0623 | 0.0623 |
   | 0.25–0.50s | 0.1648 | 0.1648 |
   | 0.50–0.75s | 0.2716 | 0.2715 |
   | 0.75–1.00s | 0.3794 | 0.3789 |
   | the flat middle | 0.4310–0.4320 | 0.4316 |

   The prediction is arithmetic, not a previous run: for a sine of amplitude *A*
   ramped linearly, the RMS over `[a, b]` is `A/√2 · √((b³−a³)/3(b−a))`. The
   fade came out of the file as the shape the planner described, and the peak
   frequencies came back 440Hz left and 660Hz right — so the channels did not
   swap on the way through either.
6. **The footage was measured the same way.** Headless Chromium encoded a real
   60-frame VP9 file in which frame *n* is a flat colour spelling *n* out as a
   three-digit base-4 number, one digit per channel. The levels are 85 apart on
   purpose: a flat fill through VP9 becomes limited-range YUV 4:2:0 and comes
   back a dozen levels off, and at that spacing no amount of that drift can
   round a channel to the wrong level, so "which frame is this" has an exact
   answer. That file was demuxed by `demux/matroska.ts`, decoded, placed on a
   timeline, and painted by `paintFrame`; the centre pixel of the canvas was
   read for the first thirty output frames.

   **All thirty matched their own source frame, in order, with nothing
   duplicated and nothing dropped.** The same measurement before the half-frame
   sampling fix read `0,1,1,3,4,4,6,7,7,…` — which is how that bug was found.

   `scripts/build_mp4_fixture.py` covers the other container from the other
   direction: Python writes an MP4 from the spec — three different chunk sizes,
   sparse sync samples, a signed `ctts` and a version-1 `mdhd` — and
   `demux/isobmff.ts` reads every frame's offset, length, keyframe flag and
   presentation time back out exactly.
7. **Time remapping was checked against the server's own prediction.** Python
   resolved three documents — a `hero` curve, a `bullet` freeze and a reverse —
   and wrote down, for each of thirty output frames, the source tick it says
   should be on screen. Chromium then ran the same documents through the
   browser's resolver, decoder and painter over the same 60-frame test video.

   **All ninety source ticks were identical, and every drawn frame matched.**
   The sequences are the features, legible on their own:

   ```
   hero    1,3,5,7,9,10,11,12,13,13,14,14,15,15,16,16,17,17,18,18,…,24,25,27,29,31
   bullet  1,4,6,8,10,12,13,14,15,15,15,15,15,15,15,15,15,15,16,16,…,26,29,31,34
   reverse 29,28,27,26,25,24,23,22,21,20,19,18,17,16,15,14,13,12,11,…,3,2,1,0
   ```

   Fast in and out with a slow middle; a hard stop on frame 15 for eight output
   frames; and a countdown with nothing repeated or skipped. The first run of
   this found the off-by-one described above — every reverse frame was exactly
   one too far along.

---

## Storage

Its own database, like the image and distribution runners.

| Table | Holds |
|---|---|
| `video_projects` | the current document and a version number |
| `video_history` | every version there has ever been |
| `video_renders` | the exported file: path, hash, gates, which version it came from |

**Timelines can live in Postgres.** The store goes through the same seam the
egress log uses — an explicit target wins, then `OFFSETX_DATABASE_URL`, then the
local file — so a deployment sets one variable and nothing else changes. That
matters on a host whose filesystem does not survive a restart: Render's free
plan writes to `/tmp`, and an instance that sleeps comes back empty. An hour of
editing is not a storage detail.

What this deliberately does **not** fix: renders, uploaded recordings and
generated pictures are bytes on a disk. A database does not hold them, and
pretending otherwise would be worse than the gap. The document — the timeline,
its history, its transcripts — is the part that took the work, and it is the
part that moves. Files still need a real disk or object storage.

`tests/test_video_postgres.py` runs the whole edit session, undo, media and
transcripts against **both backends**, and asserts structurally that the API
never hands the store a bare path.

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
- **Retimed audio.** A clip on a speed curve, frozen, or reversed exports
  without its sound. Doing it properly means resampling, and resampling means
  deciding about pitch — a feature in its own right. The manifest names every
  clip this affects rather than leaving it to be noticed in the file.
- **Speed curves are straight between their points**, not bezier. Two resolvers
  have to agree to the tick, and a trapezoid does that where a cubic does not.
- **The mix is plain.** No ducking, no compression, no EQ, no normalisation, no
  waveform to look at and no beat detection to cut to. Gain, fades and volume
  keyframes reach the file exactly as the preview plays them, and that is all.
- **No text-based editing.** There is a transcript — auto-captions produce one —
  but editing the video by editing its transcript is not wired.
- **No auto-reframe.** Changing the canvas deliberately does not move anything:
  reframing every clip for a new aspect ratio is a model call, and a crude
  version would slice subjects down the middle and call it done.
- **The export holds the whole file in memory.** Fine for a sixty-second
  vertical video; not fine for ten minutes at 4K.
- **One fade per clip, governing picture and sound together.** Separate video
  and audio fades are real; a clip whose picture fades while its audio stays at
  full is worse than either, so one fade drives both until there are two.
