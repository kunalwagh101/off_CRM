# The content engine — blueprint

What we are building, why, in what order, and what has to be true for it to
work. Written to be argued with.

The brief: a campaign is given a goal — *one million views* — and the system
watches competitors, finds what is rising, writes the angle, builds the picture
or the video, posts it at the right time to the right platform, tracks what
happened, and gets better. The owner sees each piece and can **push**,
**ignore**, or **edit** it. The editor they edit in is a CapCut-class tool that
the machine also drives itself.

---

# 0. The three claims that decide whether this works

Everything else is execution. These three are where the project is won or lost,
and two of them are not engineering problems.

### Claim 1 — "The orchestration layer knows what will trend"

**It does not, and it cannot today.** There is no dataset. Nothing has been
published, so there are zero outcomes to learn from. Any system claiming to know
what grabs attention before it has posted anything is asserting, not knowing.

What is buildable, and is genuinely valuable:

> A **declared registry of attention hypotheses**, each one a testable rule, run
> as bandit arms against real engagement, so the system learns which are true
> **for this brand, on this platform, with this audience**.

The neon-thumbnail example in the brief is a hypothesis: *"a palette that breaks
the surrounding feed's colour norm increases stop-rate."* That is falsifiable.
Encode it, apply it to half the variants, measure stop-rate, and in ninety days
you have evidence instead of folklore — and the evidence is yours, not a blog's.

This is the same shape the project already uses twice: the provider registry
(declared, default-deny) and the image generator bandit (learn from the swipe).
**Section 5** specifies it.

The honest framing to hold onto: **we are not building a model that knows. We
are building an apparatus that finds out, quickly and cheaply, and remembers.**

### Claim 2 — "It posts to LinkedIn, Instagram, YouTube and X"

This is gated on **platform authorisation, not on our code**. Current reality,
already documented in `distribution/platforms.py`:

| Platform | Publish | Read competitors | Follower count | Blocker |
|---|---|---|---|---|
| YouTube | API, workable | **Yes, at scale** | Yes | OAuth + quota |
| Instagram | API, business accounts | Thin (Business Discovery) | Yes, business only | Meta app review |
| Facebook | API, pages | Almost nothing | Yes, pages | Meta app review |
| TikTok | **Posts private-only** until app review | Research API, separate application | No | TikTok app review |
| LinkedIn | Partner access required | No | Org pages only | LinkedIn partner programme |
| X | Paid API tier | Paid | Paid tier | Cost |

**Every one of those blockers is your paperwork, not our sprint.** The engine
should be built so that the day an approval lands, one adapter is written and
nothing else changes. It already is: `publishers.py` is an interface, and the
local outbox implements it.

**This is the largest schedule risk in the project and it is entirely external.**
Start the Meta and TikTok applications now; they take weeks.

### Claim 3 — "It replaces CapCut"

The editor needs ~345 tools. **71 are built.** They decompose into ~75
primitives, which is why this is finite — see `CAPCUT_TOOL_INVENTORY.md`. But
the honest sequencing point is this:

> The editor is **not** on the critical path to the first million views. The
> machine posting good content automatically is. The editor is what makes the
> owner able to *fix* what the machine produced, and later what makes the
> product sellable on its own.

Building all 345 before publishing anything would be building a video editor and
calling it a CRM. **Sections 8–9** interleave them deliberately.

---

# 1. What success means, precisely

A goal of "one million views" is a lagging indicator that arrives too late to
steer by. It needs leading indicators that move in days.

| Level | Metric | Why this one | Target to set |
|---|---|---|---|
| **North star** | Views per campaign | The stated goal | 1,000,000 |
| Lagging | Follower growth rate (%/week) | The brief is right that this beats likes — followers compound, likes do not | to define |
| Leading | **Stop-rate** — 3s views ÷ impressions | The only metric that measures attention itself | ≥ platform median |
| Leading | Watch-through at 50% | Whether the content earns the scroll | ≥ platform median |
| Leading | Posts published per week | Throughput; nothing works without volume | to define |
| Leading | **Owner approval rate** at the swipe | Whether the machine's taste matches yours | ≥ 60% |
| Leading | Time from topic detected → posted | The Amul point: value decays fast | < 6 hours |
| Efficiency | Cost per 1,000 views | Whether it is a business | to define |
| Quality | Gate pass rate | Whether the machine ships broken files | ≥ 95% |

**Two of these need numbers from you** (follower growth target, cost ceiling)
and they change what the system optimises. Marked in section 10.

The **swipe is the cheapest signal in the system** — it arrives in seconds,
before anything is published, and it already trains the generator bandit. Real
engagement is the truth, but it arrives days later. Use both: the swipe filters,
engagement decides.

---

# 2. The value chain

```
   ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────┐
   │  1. INTELLIGENCE │──▶│  2. CREATION     │──▶│  3. DISTRIBUTION    │
   │                  │   │                  │   │     & LEARNING      │
   │ competitors      │   │ angle + script   │   │ schedule            │
   │ trends           │   │ image / video    │   │ publish             │
   │ topics           │   │ edit             │   │ measure             │
   │ analytics        │   │ captions         │   │ attribute           │
   └─────────────────┘   └──────────────────┘   └─────────────────────┘
            ▲                      │                        │
            │                      ▼                        │
            │             ┌──────────────────┐              │
            │             │   THE OWNER      │              │
            │             │ push · ignore ·  │              │
            │             │      edit        │              │
            │             └──────────────────┘              │
            └──────────────── learning ────────────────────┘
```

**The owner is inside the loop, not beside it.** Every push/ignore is a labelled
example. Every edit is a correction that says *what the machine got wrong*, and
a diff between what it made and what you shipped is the highest-quality training
signal in the whole system — better than any engagement number, because it is
specific.

**Nothing publishes without a push.** That is not a limitation to remove later.
It is the same rule as the email campaign's approval and the image swipe, and it
is what makes an autonomous content engine something you can actually run under
your own name.

---

# 3. Subsystem 1 — Intelligence

## 3.1 What exists

| Piece | Status |
|---|---|
| YouTube competitor watch list | ● `distribution/trends.py` |
| Uploads-playlist sweep, quota-costed | ● 1 unit/50 videos vs 100 for search |
| Velocity + outlier multiple vs channel's own median | ● |
| Cross-channel topic clustering with lift | ● `distribution/topics.py` |
| Topic → brief → candidates pipeline | ● `distribution/pipeline.py` |
| Scheduled sweeps | ○ **nothing calls it on a timer** |
| Own-account analytics read-back | ◐ schema exists, no adapter |
| Comment mining | ○ |
| Audio/format trend detection | ○ |
| Semantic clustering | ○ deliberate — lexical only, documented |

## 3.2 What to add, and why

**A timer.** `AutomationService` exists and nothing schedules a sweep. This is
the smallest change with the largest effect in the whole document: without it
the engine is a set of buttons.

**Own-account analytics.** You cannot learn from what you posted if you never
read the result back. YouTube Analytics API gives views, watch time, impressions
and **click-through rate** per video. Instagram Insights gives reach, saves,
shares. This closes the loop.

**Follower tracking** is a snapshot job, not an event stream: read follower
count per account per day, store the series, report growth rate and its
acceleration. The brief is right that this matters more than likes. It is also
*easy* — a daily counter — and it is not built.

**Comment mining** is where the language of the audience lives, and it is the
cheapest source of hooks that already resonate.

## 3.3 What we will not do

Scraping platforms whose terms forbid it, and browser automation. Already
refused package-wide and it stays refused: an account ban costs the audience,
which is the asset.

---

# 4. Subsystem 2 — Creation

## 4.1 The pipeline as it stands

```
topic → brief → N candidates → gates → [SWIPE] → caption → draft post → [APPROVE] → schedule
```

Built end to end for **images**. The two human gates are deliberate.

## 4.2 What creation needs next

| Need | Why | Stage |
|---|---|---|
| Angle derived, not typed | Today the owner supplies the angle string. It should come from positioning + what performed | 3 |
| Script writer | Video needs a script before it needs a timeline | 3 |
| Hook variants | The first 3 seconds decide the stop-rate. Generate 5, test them | 3 |
| Video generation | Text→video, image→video | 5 |
| Voiceover | TTS, then cloned voice | 4 |
| **Auto-assembly** | Script + assets + music → a timeline, automatically | 5 |
| Editor tools | So the owner can fix what the machine made | 2, 4, 6 |

**Auto-assembly is the heart of the brief** — *"imagine CapCut but it does it
automatically"*. It is the orchestrator that picks a combination of tools. It
cannot exist before the tools are declared as data, which is why the primitive
registry in `CAPCUT_TOOL_INVENTORY.md` comes first.

## 4.3 How the orchestrator picks a combination

Not a black box. A search over a declared space, scored by a declared objective:

```
recipe = argmax over (template × palette × pacing × hook × effect-set)
         of  predicted_stop_rate(recipe, topic, platform, brand)
         subject to  brand constraints, platform constraints, gate rules
```

- **The space** is the preset registry — data, not code.
- **The score** starts as a prior from the attention registry (§5) and becomes a
  learned posterior as engagement arrives.
- **The constraints** are hard: brand palette, platform aspect and length,
  gates. A recipe that violates one is never scored, not scored-and-rejected.

Early on the search is a bandit over a few dozen recipes. It does not need to be
a neural network, and calling it one before there is data would be theatre.

---

# 5. The attention layer, specified honestly

The part of the brief that matters most and is easiest to fake.

## 5.1 Shape

A **registry of hypotheses**, in YAML, exactly like `providers.yaml`:

```yaml
- id: palette_break
  claim: >-
    A palette that breaks the surrounding feed's colour norm raises stop-rate.
  applies_to: [image, video]
  mechanism: pattern_interrupt
  implementation:
    kind: palette_constraint
    params: { saturation_min: 0.8, hue_away_from: feed_median }
  evidence: none_yet          # none_yet | internal | external
  source: ""                  # a citation when the evidence is external
  measured_lift: null         # filled by the learning loop
  sample_size: 0
```

Rules, non-negotiable:

1. **`evidence: none_yet` is the honest default.** A hypothesis with no evidence
   still runs — it just cannot claim anything.
2. **Every hypothesis is falsifiable and measured.** `measured_lift` is written
   by the loop, never by hand.
3. **A hypothesis that loses is retired**, in the registry, visibly. Negative
   results are the valuable ones — they are what nobody else has.
4. **Default-deny for claims:** the UI may only display a lift that has a sample
   size behind it, exactly as the generator bandit refuses to steer below 12
   decisions.

## 5.2 Starting hypotheses

Roughly 60 to seed across five mechanisms. Not "thousands" — a thousand
untested hypotheses is a thousand ways to be wrong slowly, and the measurement
budget is the constraint, not the idea budget.

| Mechanism | Examples |
|---|---|
| **Pattern interrupt** | palette break, unexpected motion in frame 1, silence before speech, off-centre subject, hand-held tilt in a feed of tripods |
| **Curiosity gap** | question hook, withheld payoff, number that does not add up, mid-sentence open |
| **Cognitive ease** | one idea per post, caption ≤ 42 chars, high contrast, face in the first frame |
| **Social proof / stake** | named competitor, a real number, a dated claim, a stated cost |
| **Rhythm** | cut on beat, pace change at 3s, silence at the hook, tempo matched to topic |

## 5.3 How a hypothesis becomes a measurement

```
brief ──▶ apply hypothesis to half the variants (holdout)
      ──▶ swipe (fast, weak signal)
      ──▶ publish
      ──▶ stop-rate at 24h and 7d (slow, true signal)
      ──▶ lift vs holdout, with a confidence interval
      ──▶ registry updated; bandit reweighted
```

**The holdout is what makes it science.** Applying an idea to everything and
watching the number go up measures the weather.

**Statistical honesty:** with a handful of posts a week, most single hypotheses
will take months to reach significance. Two consequences, both stated now rather
than discovered later: pool evidence across brands where the mechanism is
plausibly universal, and **report confidence intervals, never a bare lift.**

---

# 6. Subsystem 3 — Distribution and learning

## 6.1 The decision surface

What the owner sees, per piece of content:

| Action | Effect | Signal recorded |
|---|---|---|
| **Push** | Schedules to the platforms the campaign targets | Positive label; credits the generator, recipe and hypotheses |
| **Ignore** | Discards; the file is deleted | Negative label; same attribution |
| **Edit** | Opens the video editor on it | **The most valuable signal**: the diff between produced and shipped |
| *(implicit)* | Publishing outcome | Engagement, attributed back to the recipe |

**Push is not publish-immediately.** It enters the schedule; the scheduler picks
the slot by the timing model (§6.3). The distinction matters — "post this" and
"post this now" are different intents and conflating them wastes the timing
model entirely.

## 6.2 Scheduling and pacing

Already in `distribution/`: per-account daily caps, a send window, due-post
polling. What is missing is *which* slot, which needs own-account analytics
(§3.2) — until there is data, use published best-time defaults per platform and
say plainly in the UI that they are defaults, not learned.

## 6.4 Pacing: the goal sets the rate

Posting volume is not a number set once and forgotten. `distribution/pacing.py`
computes it:

```
posts per day  =  (target − measured views) ÷ views per post ÷ days left
```

Every term is something the owner can check, which is deliberate. A model could
produce this number and nobody could argue with it — the wrong property for a
control that decides how loudly you speak in public.

Four rules, and they are the whole design:

| Rule | Why |
|---|---|
| **No data, no steering** | Before ~5 measured posts there is no views-per-post figure. It holds the declared rate and says so. A controller with nothing to measure is a random number generator. |
| **Raise slowly, lower at once** | A missed goal is recoverable next week; a banned account is not. Rises are capped at +25% per cycle. An engine that spots it is behind and posts 10× more *is* a spam bot at that moment. |
| **Deadband of 10%** | Without it the rate moves every cycle on noise, and a schedule that changes hourly is unplannable. |
| **Platform caps are hard** | Instagram's 25/day is a ceiling the arithmetic approaches and never crosses. The goal does not get a vote on the platform's terms. |

The new rate is **stored**, so the ramp compounds across cycles rather than
restarting from the declared number every hour and never arriving. `auto_pace`
is off by default.

## 6.3 Learning

Three loops, three speeds:

| Loop | Latency | Teaches |
|---|---|---|
| Swipe | seconds | Generator quality, brand taste |
| **Edit diff** | minutes | What the machine got *specifically* wrong |
| Engagement | 1–7 days | What the audience actually rewards |

The edit-diff loop is the one nobody builds and it is nearly free here: the
timeline is a document with full version history, so *what the owner changed* is
literally a diff between version N and N+k. Feed the changed properties back —
"the owner always increases text size", "the owner always cuts the first 2
seconds" — and the machine stops making that mistake.

---

# 7. Architecture

```
offsetx_apollo_builder/
├── ai/              broker · registry · bandit · payload · scanner · quota    ●
├── imagery/         generate → gate → swipe → generator scores                ●
├── video/           timeline · edits · gates · captions · store · engine      ●
│   ├── primitives/  render + audio + time primitives (~75)                    ○ NEW
│   ├── presets/     transitions, effects, filters, animations, text (YAML)    ○ NEW
│   └── assembly/    script → timeline; the orchestrator's output              ○ NEW
├── distribution/    platforms · trends · topics · pipeline · publishers       ●
│   ├── analytics/   own-account read-back, follower series                    ○ NEW
│   └── scheduler/   slot choice, pacing                                       ◐
├── attention/       hypothesis registry · holdout assignment · lift maths     ○ NEW
└── orchestrator/    goal → plan → recipe search → produce → measure           ○ NEW
```

**Rules that carry over unchanged:** models never pull, off_CRM pushes. One
egress gate. Payloads built from an allowlist. Default-deny everywhere. The
scanner blocks and never redacts — and for bytes it cannot read, the class is
refused instead (`AUTO_CAPTIONS.md`).

**Data flow for one post**

```
sweep → topics → [cooldown check] → brief (+ hypotheses, holdout assigned)
      → N candidates → gates → SWIPE → [edit?] → caption → recipe recorded
      → draft post → PUSH → schedule → publish → metrics at 1h/24h/7d
      → lift computed → registry + bandit updated
```

---

# 8. Build stages

Each stage lists what it unlocks and how we know it worked. **No stage is
"done" without its acceptance evidence.**

### Stage 1 — Make it run by itself *(the highest value per line in this document)*
- Timer in `AutomationService`: sweep → plan → draft → publish-due
- Own-account analytics adapter (YouTube first — the only one usable today)
- Follower snapshot job + growth series
- **Unlocks:** the engine stops being a set of buttons.
- **Acceptance:** a 7-day unattended run producing drafts daily with no manual call; follower series populated; a report of what it did.

### Stage 2 — Editor: the CapCut feel *(~25 tools)*
- Transitions (real transition object), animation presets, text presets +
  gradient/glow/spacing, blend modes, flip, borders/shadow, full colour set,
  snapping, copy-paste attributes, frame export, SRT export
- **Unlocks:** the owner can actually fix a piece instead of rejecting it.
- **Acceptance:** all rows marked ● in the map; conformance fixture regenerated; export byte-verified in a real browser as before.

### Stage 3 — The attention registry
- `attention/` package, ~60 seeded hypotheses, holdout assignment, lift with
  confidence intervals, registry surfaced in the UI
- Angle derived from positioning + past performance; hook variants
- **Unlocks:** every post becomes an experiment.
- **Acceptance:** a hypothesis measured end to end on real posts, with an interval — and one hypothesis retired for losing.

### Stage 4 — Audio for real *(~20 tools)* — **the mix is built; the rest is not**
- ✅ `OfflineAudioContext` mixing + Opus in the muxer → **audio in the export**
- ✅ Gain envelopes from volume keyframes and fades, planned in Python and
  applied in the browser, pinned by the same conformance fixture as the frames
- ✅ Clipping reported before the render, and the whole mix scaled to fit
- ✅ An export gate that fails a silent file from a timeline that makes a sound
- ⬜ Waveforms, beat detection, ducking, EQ; TTS voiceover
- **Unlocks:** video with sound. Most platforms punish silent video.
- **Acceptance:** ✅ the muxer's own Opus-bearing output is parsed back by the
  Python gates at 48000Hz / 2 channels, and the two mix planners agree point for
  point on the conformance document. ⬜ beat markers within 50ms of ground truth
  on a test track — that is the beat-detection half, which is not built.

### Stage 5 — Video and auto-assembly *(the brief's centre)*
- ✅ Draw footage on the canvas: a hand-written MP4 and WebM demuxer feeding
  `VideoDecoder`, forward-only with a cursor, in the preview and the export
- ✅ Freeze frame, reverse, speed curves — one integral, three menu items; 12
  curve presets over 4 families, verified frame for frame against the server
- ✅ **The assembly orchestrator**: assets + recipe → a finished timeline. 8
  recipes over 5 families, deterministic and seeded; a model picks the recipe
  and writes the words, never the document
- ✅ The edit-diff, so what the owner changes afterwards is measurable
- ⬜ Text→video and image→video generators
- ✅ **The director**: a topic picks the shape and writes the words, through the
  broker. Its reply is validated against the recipe registry before a clip is
  laid, which is what makes a scraped topic safe to pass in
- **Unlocks:** *"CapCut, but it does it automatically."*
- **Acceptance:** ✅ 30 of 30 exported frames matched their own source frame in a
  real browser, measured by reading the canvas. ✅ a recipe and a length went to
  a finished video with zero manual timeline edits — manifest `renderable: true`
  with no warnings, exported in Chromium, **all eight server gates passed**, and
  `difference()` measures what an owner changes against it.

### Stage 6 — The effect engine *(~40 primitives, ~800 presets)*
- Shader primitives, then transitions/effects/filters as declared data
- **Unlocks:** the search space the orchestrator needs to be interesting.
- **Acceptance:** a preset added in YAML with no code change; orchestrator picks a recipe from ≥ 200 candidates.

### Stage 7 — Platform adapters
- YouTube first (only one usable now), then Instagram/Facebook on approval
- **Gated on your app reviews, not on us.**
- **Acceptance:** a real post published through the official API and its metrics read back.

### Stage 8 — Standalone
- Extract `video/` + `attention/` as an installable product
- **Acceptance:** the extraction test already used for `ai/` passes for `video/`.

---

# 9. Sequencing, and the argument for it

**Stage 1 before everything.** An engine nobody has to press is worth more than
more tools nobody has time to use. It also starts the data collection that
Stages 3, 5 and 6 all depend on — every week it is delayed is a week of evidence
not gathered.

**Stage 2 before Stage 5.** The owner has to be able to fix things before the
machine is trusted to make more of them.

**Stage 4 before Stage 5.** Auto-assembling silent video is auto-assembling
something the platforms will bury.

**Stage 6 last of the editor work.** It is the largest and the least useful
until there is a search worth running over it.

**Stage 7 whenever your approvals land** — it is parallel, and it is the one
thing that cannot be hurried from this side.

---

# 10. Assumptions that need your answer

Wrong answers here change the build, so they are questions rather than guesses.

| # | Question | Why it changes the build |
|---|---|---|
| 1 | Which brands/accounts, and do they exist yet? | Whether Stage 1 has anything to watch or post as |
| 2 | Are Meta / TikTok / LinkedIn applications started? | Stage 7's date; weeks of lead time |
| 3 | Target follower growth rate, and cost ceiling per 1,000 views? | Two of the success metrics are undefined without them |
| 4 | ~~Posting volume per week per platform?~~ | **Answered: adjustable, and the goal moves it.** Built — see §6.4. What is still open is the *ceiling* you are comfortable with per platform. |
| 5 | Is the editor a product you will sell, or an internal tool? | Changes Stage 8 from optional to required, and changes Stage 2's polish bar |
| 6 | ~~Do you have any historical post performance?~~ | **Answered: no.** The attention registry starts with `evidence: none_yet` on every hypothesis and earns its numbers from scratch. |
| 7 | Budget per month for model calls? | Decides local vs hosted, and whether video generation is in reach |

---

# 11. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Platform approvals never arrive | **High** | Build adapter-shaped; YouTube first; local outbox always works |
| Not enough volume to prove any hypothesis | **High** | Pool across brands; report intervals; prefer few strong hypotheses |
| Model cost per video exceeds value | Medium | Free tiers first; deterministic paths everywhere they suffice |
| Account ban from over-automation | **High** | Official APIs only; per-account caps; human push required |
| The editor becomes the project | Medium | Stage gates; the editor is never on the critical path to Stage 1 |
| Generated content is off-brand | Medium | Swipe + push, both mandatory; brand constraints hard in the recipe |
| Attention hypotheses are folklore | **High** | Holdouts, intervals, visible retirement of losers |

---

# 12. What is true today

| | |
|---|---|
| Campaign kinds | email ●, image ●, distribution ● |
| Competitor intelligence | YouTube ●, everything else ○ |
| Image creation + swipe | ● |
| Video editor | 71 of 345 tools |
| Auto-captions | ● |
| Publishing | local outbox only |
| Learning loops | swipe ●, edit-diff ○, engagement ◐ schema only |
| Runs unattended | **○ — nothing is on a timer** |
| Tests | 957 Python, 20 frontend |

The last two lines are the summary of this whole document: the parts work, and
**nothing runs them.** Stage 1 is the answer to that, and it is where the build
goes next.
