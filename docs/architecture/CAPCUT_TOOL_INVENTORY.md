# CapCut, tool by tool — the complete inventory

The brief was "list all of the thousands of tools". Before the list, the number
needs fixing, because getting it wrong sets the whole build strategy wrong.

## The counting problem, and why it decides the architecture

CapCut does not have thousands of *tools*. It has **roughly 350 distinct
controls** and **several thousand library presets** sitting on top of them.

| | Count | What it is |
|---|---|---|
| **Tools** — a control with parameters | ~350 | "Set opacity", "apply a mask", "key out a colour" |
| **Presets** — one saved configuration of a tool | ~4,000+ | 150 transitions, 400 effects, 150 filters, 200 text templates, thousands of stickers |
| **Primitives** — what a tool is actually made of | **~75** | A blend mode. A colour matrix. A convolution. A keyframe curve. |

Counting the presets and calling them tools is the mistake that makes this look
like ten years of work. **Nobody hand-builds 400 effects.** A "VHS" effect is a
colour matrix + a noise generator + a horizontal displacement + a chromatic
offset — four primitives with saved parameters. "Glitch" is the same four with
different numbers.

So the build is:

```
~75 primitives  ─→  ~350 tools  ─→  thousands of presets  ─→  the orchestrator
   (code)            (code)            (data, in YAML)         (searches combinations)
```

That last arrow is the thing the brief actually wants: *"it uses all of them in
combination and finds the right combination for that video."* An orchestrator
can only search a space that is **declared as data**. Four hundred hand-written
effect functions are not searchable; four hundred rows in a registry are.

**This is the single most important decision in the document.** Everything below
is organised to serve it.

Status marks: ● built · ◐ partly · ○ not yet. Current totals are in
`CAPCUT_FEATURE_MAP.md`, which is the tracked scoreboard; this file is the
complete surface, including everything the map compressed into one line.

---

# Part 1 — Editing tools

## 1.1 Media and project (28 tools)

| Tool | Parameters | |
|---|---|---|
| Import media | file, url, camera roll | ● file |
| Import by format | mp4, mov, webm, m4a, wav, mp3, png, jpg, gif, webp | ◐ 5 of 10 |
| Record voiceover | device, gain, countdown | ○ |
| Record screen | region, audio source | ○ |
| Record camera | facing, resolution, effects | ○ |
| Stock library search | query, category, licence filter | ○ |
| Replace clip | keep edits, keep duration | ○ |
| Detach audio from video | — | ○ |
| Media folders | create, move, rename | ○ |
| Media favourites | toggle | ○ |
| Media search | filename, type, duration | ○ |
| Proxy generation | resolution, codec | ○ |
| Create project | name, preset, fps, size | ● |
| Duplicate project | — | ○ |
| Rename project | name | ● |
| Delete project | — | ● |
| Project autosave | interval | ● every edit |
| Project version history | list, restore | ● 300 deep |
| Project backup / restore | export, import | ○ |
| Cloud sync | — | ● server-owned |
| Project folders | — | ○ |
| Team workspace | members, roles | ◐ ids only |
| Shared asset library | — | ◐ campaign pictures |
| Review link | expiry, permissions | ○ |
| Comments on a cut | timestamp, thread, resolve | ○ |
| Brand kit — logo | asset, placement, opacity | ○ |
| Brand kit — fonts | family set | ○ |
| Brand kit — colours | palette | ○ |

## 1.2 Timeline (34 tools)

| Tool | Parameters | |
|---|---|---|
| Add track | kind, index | ● |
| Remove track | id | ● |
| Reorder track | index | ● |
| Rename track | name | ● |
| Lock track | bool | ● |
| Mute track | bool | ● |
| Hide track | bool | ● |
| Solo track | bool | ○ |
| Track height | px | ○ |
| Add clip | kind, start, duration, source | ● |
| Remove clip | — | ● |
| Ripple delete | — | ● |
| Insert gap | at, duration | ● |
| Close all gaps | track | ○ |
| Move clip | start, track | ● |
| Split at playhead | at | ● |
| Split all tracks at playhead | at | ○ |
| Trim head | delta | ● |
| Trim tail | delta | ● |
| Slip (move content, keep position) | delta | ○ |
| Slide (move position, keep neighbours) | delta | ○ |
| Roll (move a shared cut) | delta | ○ |
| Duplicate clip | at | ● |
| Copy / paste clip | — | ○ |
| Copy / paste attributes | which properties | ○ |
| Group clips | ids | ○ |
| Ungroup | id | ○ |
| Snapping | playhead, edges, markers, grid | ○ |
| Magnetic timeline | on/off | ○ |
| Zoom timeline | level, fit | ● |
| Markers | add, remove, label, colour, jump | ● |
| Playhead scrub | tick | ● |
| Frame step | ±1, ±10 | ● |
| Undo / redo | depth | ● |

## 1.3 Transform and canvas (22 tools)

| Tool | Parameters | |
|---|---|---|
| Position | x, y | ● |
| Scale | uniform | ● |
| Scale non-uniform | x, y | ○ |
| Rotate | degrees | ● |
| Flip horizontal | bool | ○ |
| Flip vertical | bool | ○ |
| Anchor point | x, y | ● |
| Crop rectangle | l, t, r, b | ● |
| Crop by ratio | preset | ○ |
| Crop freeform / rotate | angle | ○ |
| Opacity | 0–1 | ● |
| Blend mode | 16 modes | ○ |
| Corner radius | px | ○ |
| Border | width, colour | ○ |
| Drop shadow | x, y, blur, colour | ○ |
| Canvas preset | 7 ratios | ● 6 |
| Canvas custom size | w, h | ● |
| Canvas colour | colour | ● |
| Canvas blur background | radius | ○ |
| Canvas image background | asset | ○ |
| Frame rate | 8 rates | ● |
| Fit mode | cover, contain, stretch, none | ● |

## 1.4 Time (14 tools)

| Tool | Parameters | |
|---|---|---|
| Uniform speed | 0.1–100× | ● |
| Speed keeping duration | rate | ● |
| Speed curve | control points | ○ |
| Speed curve presets | 6 named | ○ |
| Time remap keyframes | curve | ○ |
| Freeze frame | at, duration | ○ |
| Reverse | — | ○ |
| Pitch preservation | bool | ○ |
| Frame interpolation | off / blend / optical | ○ |
| Motion blur | shutter angle | ○ |
| Beat grid | bpm, offset | ○ |
| Snap to beat | — | ○ |
| Auto beat-sync slideshow | clip set | ○ |
| Ripple edit across tracks | — | ○ |

## 1.5 Keyframes (9 tools)

| Tool | Parameters | |
|---|---|---|
| Add keyframe | property, at, value | ● |
| Remove keyframe | property, at | ● |
| Clear keyframes | property or all | ● |
| Easing per keyframe | 5 curves | ● |
| Custom bezier easing | 4 control points | ○ |
| Keyframe copy / paste | — | ○ |
| Keyframe graph editor | — | ○ |
| Animatable properties | **16 today, ~40 at full surface** | ◐ |
| Keyframe survives split / trim | — | ● |

---

# Part 2 — Look: the parts that make a picture

## 2.1 Colour (18 tools)

| Tool | | Tool | |
|---|---|---|---|
| Brightness | ● | Exposure | ○ |
| Contrast | ● | Highlights | ○ |
| Saturation | ● | Shadows | ○ |
| Temperature | ○ | Whites | ○ |
| Tint | ○ | Blacks | ○ |
| Vibrance | ○ | Sharpen | ○ |
| Vignette | ○ | Grain | ○ |
| Fade / lift | ○ | HSL per channel (8 bands) | ○ |
| Curves (RGB + per channel) | ○ | LUT import + intensity | ○ |

## 2.2 Filters — 1 tool, ~150 presets

One tool: *apply LUT with intensity*. The 150 filters are 150 `.cube` files
across categories: Food, Portrait, Landscape, Retro, Movie, Mono, Vibe, Season,
Film stock, Gaming. `○`

## 2.3 Effects — ~40 primitives, ~400 presets

The 400 named effects in CapCut decompose into these primitives. Build the
primitives, declare the presets.

| Primitive | Feeds effects like |
|---|---|
| Colour matrix | retro, mono, sepia, duotone, thermal |
| Channel offset | chromatic aberration, 3D, anaglyph |
| Displacement map | glitch, wave, water, heat haze |
| Noise generator | grain, static, snow, VHS |
| Scanline / stripe | VHS, CRT, hologram |
| Blur (gaussian, radial, directional, zoom) | dreamy, speed, focus pull |
| Sharpen / unsharp | crisp, detail |
| Edge detect | comic, sketch, outline |
| Posterise / quantise | comic, poster, retro-game |
| Halftone / dither | print, comic, retro-game |
| Pixelate | mosaic, censor, 8-bit |
| Kaleidoscope / mirror tile | prism, kaleidoscope |
| Bloom / glow threshold | bling, dreamy, neon |
| Light leak overlay | film, vintage |
| Lens flare | cinematic, sun |
| Vignette shaped | spotlight, tunnel |
| Gradient overlay | duotone, sunset, neon wash |
| Screen / multiply overlay texture | paper, grunge, dust |
| Shake transform | earthquake, impact, beat-pop |
| Zoom pulse | beat drop, heartbeat |
| Roll / RGB split jitter | glitch, error |
| Frame drop / strobe | stutter, flash |
| Trail / echo | ghost, motion trail |
| Particle emitter | snow, rain, confetti, sparkle, embers |
| Weather overlay | rain, snow, fog |
| Film burn / flash frame | transition-in, cut punch |
| Text-shaped mask | knockout titles |
| Alpha matte from luminance | light wrap, blend |
| Chroma key | green screen |
| Colour range key | any-colour key |
| Segmentation mask (model) | auto cutout, background swap |
| Face landmark mesh (model) | beauty, AR, face effects |
| Body pose mesh (model) | body effects |
| Optical flow (model) | slow-mo, motion blur |
| Depth map (model) | 3D photo, parallax, relight |
| Motion tracker (model) | pin, mosaic-follow, text track |
| Object mask (model) | object removal, isolate |
| Sky mask (model) | sky replace |
| Beat detector | beat sync, pulse |
| Loudness meter | ducking, auto-level |

**All `○` today.** Nine of these forty are model calls; thirty-one are shaders.

## 2.4 Masks and compositing (14 tools)

| Tool | | Tool | |
|---|---|---|---|
| Linear mask | ○ | Mask feather | ○ |
| Mirror mask | ○ | Mask invert | ○ |
| Circle mask | ○ | Mask keyframes | ○ |
| Rectangle mask | ○ | Freeform / pen mask | ○ |
| Heart / star mask | ○ | Brush mask | ○ |
| Chroma key | ○ | Key spill suppression | ○ |
| Auto cutout (model) | ○ | Refine edge | ○ |

## 2.5 Transitions — 1 mechanism, ~150 presets

One mechanism — *blend clip A into clip B over N frames using a progress
function* — plus a transition track object that the no-overlap invariant
permits. The 150 presets are progress functions: dissolve, 12 wipes, 20 slides,
zoom, whip, spin, glitch, prism, page turn, ripple, burn, light leak, morph,
mask-shape reveals. `○`

**This is why transitions are not built yet.** A dissolve is two clips visible
at once, and the timeline forbids that on one track. It needs a real transition
object between adjacent clips — not a relaxed invariant, which would reopen the
worst bug class in the editor.

## 2.6 Animations — 1 mechanism, ~120 presets

One mechanism: *keyframe a property set over the first or last N frames*. Built
already, without the preset library. The 120 presets are named combinations —
fade, slide 4 ways, zoom in/out, bounce, spin, flip, blur in, typewriter, wave,
shake, pop, elastic — in three families: **in**, **out**, **loop**. `◐`

---

# Part 3 — Text, captions, graphics

## 3.1 Text (32 tools)

| Tool | | Tool | |
|---|---|---|---|
| Text content | ● | Letter spacing | ○ |
| Font family | ● | Line spacing | ● |
| Font size | ● | Alignment | ● |
| Font weight | ● | Vertical text | ○ |
| Italic / underline / strike | ○ | Text direction (RTL) | ○ |
| Fill colour | ● | Gradient fill | ○ |
| Stroke width + colour | ● | Multiple strokes | ○ |
| Shadow | ○ | Glow | ○ |
| Background box | ● | Box radius + padding | ◐ |
| Opacity | ● | Blur | ● |
| Bend / arc text | ○ | 3D extrude | ○ |
| Text on a path | ○ | Auto-wrap to width | ● |
| Text presets (~200) | ○ | Save custom preset | ○ |
| Text animation in / out / loop | ◐ | Per-character animation | ○ |
| Text tracked to object (model) | ○ | Text behind subject (model) | ○ |
| Text to speech (model) | ○ | Font from image (model) | ○ |

## 3.2 Captions (16 tools)

| Tool | | Tool | |
|---|---|---|---|
| **Auto captions (model)** | ● | Caption style presets | ◐ |
| Language select | ● | Word-by-word karaoke | ○ |
| Edit caption text | ● | Highlight colour | ○ |
| Split caption | ● | Translate (model) | ○ |
| Merge caption | ● | Multi-speaker labels (model) | ○ |
| Re-time caption | ● | Lyric sync (model) | ○ |
| Batch restyle | ○ | Import SRT / VTT | ○ |
| Reading-speed warning | ● | Export SRT / VTT | ○ |

## 3.3 Stickers and graphics (14 tools)

| Tool | | Tool | |
|---|---|---|---|
| Sticker library (thousands) | ○ | Custom sticker from image | ● |
| GIF library | ○ | Sticker animation | ◐ |
| Emoji | ◐ | Sticker tracking (model) | ○ |
| Shapes (rect, circle, arrow, line, poly) | ○ | Shape fill / stroke | ○ |
| Callout / speech bubble | ○ | Frames and borders | ○ |
| Logo / watermark layer | ● | Overlay blend | ○ |
| Progress bar / timer | ○ | Countdown | ○ |

---

# Part 4 — Audio (38 tools)

| Tool | | Tool | |
|---|---|---|---|
| Music library | ○ | Sound effects library | ○ |
| Extract audio from video | ○ | Import audio | ● |
| Record voiceover | ○ | Volume | ● |
| Volume keyframes | ● | Fade in / out | ● |
| Mute | ● | Solo | ○ |
| Split / trim audio | ● | Audio speed | ● |
| Pitch preserve | ○ | Pitch shift | ○ |
| Waveform display | ○ | Peak / loudness meter | ○ |
| Normalise / auto-level | ○ | Limiter | ○ |
| Compressor | ○ | Gate | ○ |
| Equaliser | ○ | Reverb | ○ |
| Echo / delay | ○ | Chorus / flanger | ○ |
| Voice changer presets | ○ | Auto ducking | ○ |
| Beat detection | ○ | Beat markers | ○ |
| Snap cuts to beat | ○ | Noise reduction (model) | ○ |
| Voice enhance (model) | ○ | Vocal isolation (model) | ○ |
| De-reverb (model) | ○ | Text to speech (model) | ○ |
| Voice cloning (model) | ○ | Auto dubbing (model) | ○ |
| Audio in the export | ○ | Audio-only export | ○ |

**Audio is modelled in the document and absent from the export.** That is the
single largest honest gap in the editor today.

---

# Part 5 — The AI tools (42)

Every one is a model call through the egress broker. The trust rules in
`AUTO_CAPTIONS.md` — especially that **a scanner cannot read a waveform or a
picture** — apply to all of them.

| Tool | Input → output | |
|---|---|---|
| Transcribe | audio → words + timings | ● |
| Auto captions | transcript → text clips | ● |
| Translate captions | text → text | ○ |
| Auto dub | transcript + voice → audio | ○ |
| Text to speech | text → audio | ○ |
| Voice cloning | sample + text → audio | ○ |
| Noise reduction | audio → audio | ○ |
| Voice enhance | audio → audio | ○ |
| Vocal isolation | audio → 2 stems | ○ |
| Beat / structure detection | audio → markers | ○ |
| Text to image | prompt → image | ● in `imagery/` |
| Text to video | prompt → video | ○ |
| Image to video | image + motion → video | ○ |
| Video to video / restyle | video → video | ○ |
| Lip sync | video + audio → video | ○ |
| AI avatar | script → talking video | ○ |
| Auto cutout | image/video → alpha | ○ |
| Background replace | image + alpha + bg → image | ○ |
| Sky replace | image + sky mask → image | ○ |
| Object removal | image + mask → image | ○ |
| Outpaint / expand | image + target ratio → image | ○ |
| Upscale | image/video → larger | ○ |
| Restore / colourise | image → image | ○ |
| Relight | image + depth → image | ○ |
| Face retouch | image → image | ○ |
| Body reshape | image → image | ○ |
| Frame interpolation | video → higher fps | ○ |
| Stabilisation | video → video | ○ |
| Auto reframe | video + subject track → crop path | ○ |
| Motion tracking | video → track path | ○ |
| Object detection | frame → boxes + labels | ○ |
| Face detection | frame → landmarks | ○ |
| Depth estimation | frame → depth map | ○ |
| Scene / shot detection | video → cut points | ○ |
| Silence detection | audio → ranges | ○ |
| Filler-word detection | transcript → ranges | ○ |
| Highlight detection | video + transcript → best ranges | ○ |
| Text-based editing | transcript edit → timeline edit | ○ |
| Script writer | brief → script | ○ |
| Hook writer | topic → 5 openings | ○ |
| Music generation | prompt → audio | ○ |
| Auto montage | clips + music → timeline | ○ |

---

# Part 6 — Export and publishing (24 tools)

| Tool | | Tool | |
|---|---|---|---|
| Resolution | ● any canvas | Frame rate | ● 8 |
| Bitrate | ◐ not in UI | Quality preset | ○ |
| Codec H.264 | ○ | Codec HEVC | ○ |
| Codec VP9 | ● | Codec AV1 | ○ |
| Container MP4 | ○ | Container WebM | ● |
| Container MOV | ○ | Export GIF | ○ |
| Audio-only export | ○ | Export current frame | ○ |
| Watermark toggle | n/a none added | Burn captions | ● |
| Export SRT | ○ | Batch aspect ratios | ○ |
| Export gates | ● 7 gates | Render history | ● |
| Publish YouTube | ○ adapter | Publish Instagram | ○ adapter |
| Publish TikTok | ○ restricted | Publish LinkedIn / X / Facebook | ○ |

---

# The totals

| Part | Tools | ● | ◐ | ○ |
|---|---|---|---|---|
| 1 Editing | 107 | 34 | 4 | 69 |
| 2 Look | 72 | 3 | 1 | 68 |
| 3 Text, captions, graphics | 62 | 17 | 6 | 39 |
| 4 Audio | 38 | 7 | 0 | 31 |
| 5 AI | 42 | 3 | 0 | 39 |
| 6 Export | 24 | 7 | 1 | 16 |
| **Total** | **345** | **71** | **12** | **262** |

Plus **~4,000 presets** — 150 transitions, 400 effects, 150 filters, 200 text
styles, 120 animations, and the sticker/music libraries which are licensed
content and will never be cloned.

**The 262 remaining tools are not 262 units of work.** They are ~75 primitives,
and the primitives are shared: build *displacement map* once and eleven effects
become configuration. That is the entire reason this is a finite project.

See `CONTENT_ENGINE_BLUEPRINT.md` for the build order and what each stage
unlocks.
