# CapCut, feature by feature

Research for the AI video editor. Before designing anything, this is what the
thing we are being compared to actually does — CapCut mobile, desktop and web
combined, because the user does not care which app a feature lives in.

Nothing here is built. This document is the inventory and the honest read on
what is reachable inside off_CRM.

---

## How to read the verdict column

| Mark | Meaning |
|---|---|
| **B** | Browser can do it — canvas, WebAudio, WebCodecs. No backend. |
| **R** | Needs a real render backend (frame decode/encode). The one big decision. |
| **M** | Needs a model call. Goes through the egress broker like every other one. |
| **X** | Out of scope for off_CRM — a phone app, a licensed library, a marketplace. |

---

## 1. Import and media

| Feature | Verdict |
|---|---|
| Import video, image, audio from disk | B |
| Camera roll / phone gallery | X |
| Record voiceover in-app | B |
| Screen recording (desktop) | X |
| Camera capture with live effects | X |
| Stock video / image library | X (licensing) |
| Cloud media, project sync | B |
| Media panel: folders, favourites, search | B |
| Proxy / optimise media for smooth scrub | R |
| Replace a clip, keeping its edits | B |

## 2. Timeline and core editing

| Feature | Verdict |
|---|---|
| Multi-track timeline (video, audio, text, effect, sticker) | B |
| Main track vs overlay tracks (PiP) | B |
| Split / cut at playhead | B |
| Trim by dragging clip edges | B |
| Ripple delete, close gap | B |
| Snapping to playhead, clip edges, markers | B |
| Timeline zoom in/out | B |
| Markers on the timeline | B |
| Lock, mute, hide a track | B |
| Group / ungroup clips | B |
| Copy–paste attributes between clips | B |
| Undo / redo, full history | B |
| Keyboard shortcuts, editable map | B |
| Frame-by-frame stepping | R |
| Freeze frame | R |
| Reverse clip | R |
| Split-screen layouts | B |
| **Keyframes on any property** | B |
| Motion blur between keyframes | R |
| Autosave, project versions | B |

## 3. Transform and canvas

| Feature | Verdict |
|---|---|
| Position, scale, rotate, flip | B |
| Crop | B |
| Aspect presets 9:16, 1:1, 4:5, 16:9, 4:3, 21:9, custom | B |
| Background fill: blur, colour, image | B |
| Ken Burns / zoom-pan | B |
| Opacity | B |
| Blend modes (screen, multiply, overlay…) | B |
| Corner radius, borders, shadow | B |

## 4. Speed and time

| Feature | Verdict |
|---|---|
| Uniform speed 0.1×–100× | R |
| Speed curves — montage, hero, bullet, jump cut, custom | R |
| Smooth slow motion (frame interpolation) | M |
| Pitch preservation on speed change | R |
| Time remapping with keyframes | R |
| Freeze frame, reverse | R |

## 5. Transitions and animations

| Feature | Verdict |
|---|---|
| Transitions: dissolve, wipe, glitch, zoom, whip, prism, page turn, light leak | B |
| Transition duration slider | B |
| Apply transition to all cuts | B |
| Clip animations: in, out, combo/loop | B |
| Text and sticker animations | B |

## 6. Effects and filters

| Feature | Verdict |
|---|---|
| Video effects: glitch, VHS, retro, film grain, shake, flash, particles, weather | B (shaders) |
| Face / body / AR effects | M |
| Effect track spanning several clips | B |
| Filter presets by category | B (LUT) |
| Filter intensity slider | B |
| LUT import | B |

## 7. Colour

| Feature | Verdict |
|---|---|
| Brightness, contrast, saturation, exposure | B |
| Highlights, shadows, temperature, tint | B |
| Sharpen, vignette, fade, grain | B |
| HSL per channel, curves | B |
| Auto-adjust | B |
| Colour match across clips | M |

## 8. Masks, keying, compositing

| Feature | Verdict |
|---|---|
| Masks: linear, mirror, circle, rectangle, heart, star | B |
| Mask invert, feather, keyframe | B |
| Chroma key / green screen | B (shader) |
| **Auto cutout — remove background, no green screen** | M |
| Brush cutout, refine edges | M |
| Motion tracking — pin text/sticker to a moving thing | M |
| Mosaic / blur that follows a face | M |
| Video stabilisation | R |

## 9. Text

| Feature | Verdict |
|---|---|
| Text box, multi-language fonts | B |
| Size, colour, gradient, stroke, shadow, glow, background box | B |
| Letter spacing, line spacing, alignment, opacity | B |
| Text style presets | B |
| Animated text templates | B |
| Text animations in / out / loop | B |
| Text tracked to a moving object | M |
| Text behind subject | M |
| Text to speech from the text layer | M |

## 10. Captions and subtitles

| Feature | Verdict |
|---|---|
| **Auto captions from speech** | M |
| Caption editing, split, merge, re-sync | B |
| Caption style templates | B |
| Word-by-word karaoke highlight | B + M |
| Translate captions | M |
| Import / export SRT | B |
| Multi-speaker labels | M |
| Lyric sync to music | M |
| Burn captions in, or keep them separate | R |

## 11. Stickers, overlays, graphics

| Feature | Verdict |
|---|---|
| Sticker and GIF library | X (licensing) |
| Emoji, shapes, arrows, callouts | B |
| Custom sticker from an uploaded image | B |
| Sticker animation and tracking | B / M |
| Frames, borders, overlays | B |
| Logo / watermark layer | B |

## 12. Audio

| Feature | Verdict |
|---|---|
| Music library, commercial-use filter | X (licensing) |
| Sound effects library | X |
| Extract audio from a video | R |
| Record voiceover | B |
| Volume, fade in/out, audio keyframes | B |
| Waveform display | B |
| **Beat detection, auto beat markers** | B |
| Audio speed, split, trim | B |
| Noise reduction / denoise | M |
| Voice enhance | M |
| Voice changer / pitch effects | B |
| **Vocal isolation — split voice from music** | M |
| Auto ducking under speech | B |
| Equaliser, reverb, echo | B |
| Text to speech, many voices | M |
| **AI voice cloning** | M |

## 13. The AI layer — the reason this feature exists

| Feature | Verdict |
|---|---|
| Script → video, auto-assembled | M |
| AI script / hook writer | M |
| **Text to image** | M — already built in `imagery/` |
| **Text to video** | M |
| Image to video (animate a still) | M |
| AI avatars / talking digital humans | M |
| Lip sync to new audio | M |
| **Auto reframe — resize and keep the subject centred** | M |
| Auto background removal | M |
| AI background generation / replacement | M |
| Retouch: skin, teeth, eyes, reshape | M |
| Outpaint / expand an image | M |
| **Upscale, enhance to HD/4K** | M |
| Frame interpolation for slow motion | M |
| Old photo restore, B&W colourise | M |
| **Object removal / magic eraser** | M |
| **Long video → shorts, auto highlights** | M |
| **Silence and filler-word removal** | M + R |
| **Text-based editing — cut the video by editing the transcript** | M + B |
| Smart trim / smart cut | M |
| AI music generation | M |
| Style transfer, anime, AI portrait | M |
| Auto dubbing with a cloned voice | M |
| Relight | M |
| Auto beat-synced slideshow | B |
| Product / commerce video generation | M |

## 14. Templates and auto-edit

| Feature | Verdict |
|---|---|
| Template feed, trending by platform | X (marketplace) |
| Apply a template, auto-fill your clips into its slots | B |
| Build and save your own template | B |
| One-tap auto montage from a folder of clips | M |

## 15. Projects, brand, collaboration

| Feature | Verdict |
|---|---|
| Cloud projects, backup, restore | B |
| Project folders | B |
| Team / shared workspace | B |
| **Brand kit — logo, fonts, colours** | B |
| Shared asset library | B |
| Review link, comments on a cut | B |
| Mobile ↔ desktop project handoff | X |

## 16. Export and publishing

| Feature | Verdict |
|---|---|
| Resolution 480p → 4K | R |
| Frame rate 24 / 25 / 30 / 50 / 60 | R |
| Bitrate and quality control | R |
| MP4 / MOV, H.264 / HEVC | R |
| Watermark on/off | R |
| Export GIF | R |
| Export audio only | R |
| Export current frame as an image | B |
| **Batch export several aspect ratios at once** | R |
| Export SRT separately | B |
| **Publish straight to TikTok / YouTube / Instagram / Facebook** | already built — `distribution/` |
| Share link | B |

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
