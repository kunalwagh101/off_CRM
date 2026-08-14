# CapCut, feature by feature

Research for the AI video editor. Before designing anything, this is what the
thing we are being compared to actually does — CapCut mobile, desktop and web
combined, because the user does not care which app a feature lives in.

This is the inventory, the honest read on what is reachable inside off_CRM, and
**the running scoreboard**. The status column is kept current as the editor is
built, so this file answers "how much of CapCut do we have" without anyone
having to trust a summary written somewhere else.

## Where it stands

| | Rows | Share |
|---|---|---|
| ● Built | **29** | 18% |
| ◐ Partly built | **17** | 11% |
| ○ Not built | **112** | 71% |
| | **158** | |

Nine of those 112 are **out of scope on purpose** — a phone camera, a licensed
music library, a template marketplace. Against the 149 rows that are actually
reachable, 46 are touched: **31%**.

The 29 are not the easy 29. They are the timeline, its invariants, keyframes,
undo, the export and its gates, and auto-captions — the floor everything else
stands on. Transitions, masks and the AI rows are each a feature on top of a
timeline that now exists.

---

## How to read the columns

| Mark | Meaning |
|---|---|
| **B** | Browser can do it — canvas, WebAudio, WebCodecs. No backend. |
| **R** | Needs a real render backend (frame decode/encode). The one big decision. |
| **M** | Needs a model call. Goes through the egress broker like every other one. |
| **X** | Out of scope for off_CRM — a phone app, a licensed library, a marketplace. |
| ● ◐ ○ | Built · partly built · not built, as of the last commit that touched this file. |

---

## 1. Import and media

| Feature | | Status |
|---|---|---|
| Import video, image, audio from disk | B | ● audio and video import; pictures come from the image campaign |
| Camera roll / phone gallery | X | ○ |
| Record voiceover in-app | B | ○ |
| Screen recording (desktop) | X | ○ |
| Camera capture with live effects | X | ○ |
| Stock video / image library | X (licensing) | ○ |
| Cloud media, project sync | B | ● the document lives on the server, not the tab |
| Media panel: folders, favourites, search | B | ○ |
| Proxy / optimise media for smooth scrub | R | ○ |
| Replace a clip, keeping its edits | B | ○ |

## 2. Timeline and core editing

| Feature | | Status |
|---|---|---|
| Multi-track timeline (video, audio, text, effect, sticker) | B | ● video and audio tracks; text and colour live on video tracks |
| Main track vs overlay tracks (PiP) | B | ● |
| Split / cut at playhead | B | ● |
| Trim by dragging clip edges | B | ● |
| Ripple delete, close gap | B | ● |
| Snapping to playhead, clip edges, markers | B | ○ frame-snapping exists for captions, not for dragging |
| Timeline zoom in/out | B | ● |
| Markers on the timeline | B | ● |
| Lock, mute, hide a track | B | ● |
| Group / ungroup clips | B | ○ |
| Copy–paste attributes between clips | B | ○ |
| Undo / redo, full history | B | ● |
| Keyboard shortcuts, editable map | B | ● shortcuts yes, remapping no |
| Frame-by-frame stepping | R | ● arrows step a frame, shift steps ten |
| Freeze frame | R | ○ |
| Reverse clip | R | ○ |
| Split-screen layouts | B | ○ |
| **Keyframes on any property** | B | ● 16 properties, 5 easings |
| Motion blur between keyframes | R | ○ |
| Autosave, project versions | B | ● |

## 3. Transform and canvas

| Feature | | Status |
|---|---|---|
| Position, scale, rotate, flip | B | ◐ no flip |
| Crop | B | ● |
| Aspect presets 9:16, 1:1, 4:5, 16:9, 4:3, 21:9, custom | B | ● 6 presets plus custom, 8 frame rates |
| Background fill: blur, colour, image | B | ◐ colour only |
| Ken Burns / zoom-pan | B | ● keyframed scale and position is exactly this |
| Opacity | B | ● |
| Blend modes (screen, multiply, overlay…) | B | ○ |
| Corner radius, borders, shadow | B | ○ |

## 4. Speed and time

| Feature | | Status |
|---|---|---|
| Uniform speed 0.1×–100× | R | ● 0.1x-100x, and a keep-the-length variant |
| Speed curves — montage, hero, bullet, jump cut, custom | R | ○ |
| Smooth slow motion (frame interpolation) | M | ○ |
| Pitch preservation on speed change | R | ○ |
| Time remapping with keyframes | R | ○ |
| Freeze frame, reverse | R | ○ |

## 5. Transitions and animations

| Feature | | Status |
|---|---|---|
| Transitions: dissolve, wipe, glitch, zoom, whip, prism, page turn, light leak | B | ○ |
| Transition duration slider | B | ○ |
| Apply transition to all cuts | B | ○ |
| Clip animations: in, out, combo/loop | B | ○ |
| Text and sticker animations | B | ○ |

## 6. Effects and filters

| Feature | | Status |
|---|---|---|
| Video effects: glitch, VHS, retro, film grain, shake, flash, particles, weather | B (shaders) | ○ |
| Face / body / AR effects | M | ○ |
| Effect track spanning several clips | B | ○ |
| Filter presets by category | B (LUT) | ○ |
| Filter intensity slider | B | ○ |
| LUT import | B | ○ |

## 7. Colour

| Feature | | Status |
|---|---|---|
| Brightness, contrast, saturation, exposure | B | ◐ brightness, contrast, saturation; no exposure |
| Highlights, shadows, temperature, tint | B | ○ |
| Sharpen, vignette, fade, grain | B | ○ |
| HSL per channel, curves | B | ○ |
| Auto-adjust | B | ○ |
| Colour match across clips | M | ○ |

## 8. Masks, keying, compositing

| Feature | | Status |
|---|---|---|
| Masks: linear, mirror, circle, rectangle, heart, star | B | ○ |
| Mask invert, feather, keyframe | B | ○ |
| Chroma key / green screen | B (shader) | ○ |
| **Auto cutout — remove background, no green screen** | M | ○ |
| Brush cutout, refine edges | M | ○ |
| Motion tracking — pin text/sticker to a moving thing | M | ○ |
| Mosaic / blur that follows a face | M | ○ |
| Video stabilisation | R | ○ |

## 9. Text

| Feature | | Status |
|---|---|---|
| Text box, multi-language fonts | B | ● |
| Size, colour, gradient, stroke, shadow, glow, background box | B | ◐ no gradient or glow |
| Letter spacing, line spacing, alignment, opacity | B | ◐ no letter spacing |
| Text style presets | B | ◐ one caption style, overridable; no library |
| Animated text templates | B | ○ |
| Text animations in / out / loop | B | ◐ fades and keyframes, no named presets |
| Text tracked to a moving object | M | ○ |
| Text behind subject | M | ○ |
| Text to speech from the text layer | M | ○ |

## 10. Captions and subtitles

| Feature | | Status |
|---|---|---|
| **Auto captions from speech** | M | ● Whisper through the broker |
| Caption editing, split, merge, re-sync | B | ● captions are ordinary clips, so every edit works on them |
| Caption style templates | B | ◐ one default, overridable per call |
| Word-by-word karaoke highlight | B + M | ○ |
| Translate captions | M | ○ |
| Import / export SRT | B | ○ |
| Multi-speaker labels | M | ○ |
| Lyric sync to music | M | ○ |
| Burn captions in, or keep them separate | R | ◐ burned in; no separate subtitle output |

## 11. Stickers, overlays, graphics

| Feature | | Status |
|---|---|---|
| Sticker and GIF library | X (licensing) | ○ |
| Emoji, shapes, arrows, callouts | B | ◐ emoji in text clips; no shapes |
| Custom sticker from an uploaded image | B | ● a kept picture on an overlay track |
| Sticker animation and tracking | B / M | ◐ keyframe animation yes, tracking no |
| Frames, borders, overlays | B | ◐ overlay tracks; no frame presets |
| Logo / watermark layer | B | ● a picture on a top track |

## 12. Audio

| Feature | | Status |
|---|---|---|
| Music library, commercial-use filter | X (licensing) | ○ |
| Sound effects library | X | ○ |
| Extract audio from a video | R | ○ |
| Record voiceover | B | ○ |
| Volume, fade in/out, audio keyframes | B | ◐ in the document and the preview; the export writes no audio yet |
| Waveform display | B | ○ |
| **Beat detection, auto beat markers** | B | ○ |
| Audio speed, split, trim | B | ◐ split, trim and speed work on audio clips |
| Noise reduction / denoise | M | ○ |
| Voice enhance | M | ○ |
| Voice changer / pitch effects | B | ○ |
| **Vocal isolation — split voice from music** | M | ○ |
| Auto ducking under speech | B | ○ |
| Equaliser, reverb, echo | B | ○ |
| Text to speech, many voices | M | ○ |
| **AI voice cloning** | M | ○ |

## 13. The AI layer — the reason this feature exists

| Feature | | Status |
|---|---|---|
| Script → video, auto-assembled | M | ○ |
| AI script / hook writer | M | ○ |
| **Text to image** | M — already built in `imagery/` | ● the image campaign, which predates the editor |
| **Text to video** | M | ○ |
| Image to video (animate a still) | M | ○ |
| AI avatars / talking digital humans | M | ○ |
| Lip sync to new audio | M | ○ |
| **Auto reframe — resize and keep the subject centred** | M | ○ |
| Auto background removal | M | ○ |
| AI background generation / replacement | M | ○ |
| Retouch: skin, teeth, eyes, reshape | M | ○ |
| Outpaint / expand an image | M | ○ |
| **Upscale, enhance to HD/4K** | M | ○ |
| Frame interpolation for slow motion | M | ○ |
| Old photo restore, B&W colourise | M | ○ |
| **Object removal / magic eraser** | M | ○ |
| **Long video → shorts, auto highlights** | M | ○ |
| **Silence and filler-word removal** | M + R | ○ |
| **Text-based editing — cut the video by editing the transcript** | M + B | ○ |
| Smart trim / smart cut | M | ○ |
| AI music generation | M | ○ |
| Style transfer, anime, AI portrait | M | ○ |
| Auto dubbing with a cloned voice | M | ○ |
| Relight | M | ○ |
| Auto beat-synced slideshow | B | ○ |
| Product / commerce video generation | M | ○ |

## 14. Templates and auto-edit

| Feature | | Status |
|---|---|---|
| Template feed, trending by platform | X (marketplace) | ○ |
| Apply a template, auto-fill your clips into its slots | B | ○ |
| Build and save your own template | B | ○ |
| One-tap auto montage from a folder of clips | M | ○ |

## 15. Projects, brand, collaboration

| Feature | | Status |
|---|---|---|
| Cloud projects, backup, restore | B | ● every version is stored; undo survives a reload |
| Project folders | B | ○ |
| Team / shared workspace | B | ◐ workspace ids run through everything; no UI |
| **Brand kit — logo, fonts, colours** | B | ○ |
| Shared asset library | B | ◐ the campaign's kept pictures |
| Review link, comments on a cut | B | ○ |
| Mobile ↔ desktop project handoff | X | ○ |

## 16. Export and publishing

| Feature | | Status |
|---|---|---|
| Resolution 480p → 4K | R | ● the canvas is any size and the export matches it |
| Frame rate 24 / 25 / 30 / 50 / 60 | R | ● 8 rates, all exact at 90kHz |
| Bitrate and quality control | R | ◐ a bitrate parameter, not exposed in the UI |
| MP4 / MOV, H.264 / HEVC | R | ○ WebM with VP9 or VP8 only |
| Watermark on/off | R | ○ |
| Export GIF | R | ○ |
| Export audio only | R | ○ |
| Export current frame as an image | B | ○ |
| **Batch export several aspect ratios at once** | R | ○ |
| Export SRT separately | B | ○ |
| **Publish straight to TikTok / YouTube / Instagram / Facebook** | already built — `distribution/` | ○ the distribution campaign exists; only the local outbox publishes |
| Share link | B | ○ |

---

## What this means here

**The one decision that shapes everything: where frames get rendered.**

off_CRM has no ffmpeg and no Pillow. That was deliberate — `imagery/gates.py`
parses PNG, JPEG, GIF and three WebP variants by hand rather than adding a
dependency. A video editor cannot dodge the question the same way, because
somewhere a pixel has to be composited.

Three honest answers:

| Option | Cost | What it buys |
|---|---|---|
| Browser render — WebCodecs + canvas + WebAudio | one JS muxer dependency | everything marked **B**, real export, no server load |
| Server ffmpeg | one binary, a job queue | everything, including **R** |
| Neither — timeline as data only | nothing | a document nobody can play |

The third is not a real option and should not be dressed up as one.

**The shape that fits this codebase** is the same one used everywhere else: a
deterministic, dependency-free, fully tested core — the timeline document, the
edit operations, the gates — with the renderer as a swappable backend behind a
narrow interface. That way the part with the rules is testable offline, and the
part that needs a codec can be browser today and ffmpeg later without the core
knowing.

**What already exists and should not be rebuilt:**

| Existing | Reused for |
|---|---|
| `imagery/engine.py` | generation, the swipe, generator scoring |
| `imagery/gates.py` | the same idea, extended to MP4 and WebM headers |
| `imagery/store.py` | files at 0600, rows hold path + sha256 |
| `distribution/` | publishing the finished cut |
| `ai/broker.py` | every **M** row above, with its own task type |
| `ImageReview.tsx` | the swipe, which is already the quality signal |

**The gates need video.** `image` kind records its own gap: *"video (the gates
read image headers)"*. MP4 duration and dimensions live in `moov/mvhd` and
`tkhd`; WebM's are in EBML. Both are walkable by hand, the same way the JPEG
SOF walk already is. No dependency needed for the gate — only for the render.
