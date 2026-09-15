# Competitive brief — Strawberry and Crux

**Status: point-in-time research, not a working record.** Written 2026-09-12,
corrected 2026-09-14. Nothing here is maintained. Company facts decay fast;
re-check before acting on any number. `BOARD.md` is the truth about this repo,
never this file.

Live page: <https://claude.ai/artifact/T1vMugUFNw6yasiKmHbqwn>
Companion doc: [`COPY_OR_REFUSE.md`](COPY_OR_REFUSE.md) — the build answers.

Sources: public only. Companion brief on Floqer preceded this one (2026-09-05).

---

## Correction, 2026-09-14

Version 1 of this brief said the run loop and safety countdowns were unbuilt.
**Both are built** — `agent/run.py` (2,091 lines) and `browser/countdown.py`
(story `S-02.02.04`, DONE). The error came from trusting `BUILD_STATE.md`, last
updated 2026-08-28, when roughly fifteen later commits had landed.

The lesson is worth more than the correction: **a second source of truth that
lags is worse than no second source.** Either regenerate `BUILD_STATE.md` from
`BOARD.md`, or demote it to history and say so at the top of it.

---

## Why these two belong in one document

They compete with different halves of this codebase, and neither knows the other
exists.

**Strawberry** is a Chromium fork that puts AI agents inside the browser. It
competes with `browser/` and `agent/` — 8,429 lines of CDP client, perception and
run machinery.

**Crux** is an AI copilot for paid media that turns ad-performance data into new
ad creative. It competes with `video/`, `imagery/` and `distribution/` — roughly
18,000 lines across Python and TypeScript.

The uncomfortable part is what the pairing reveals, and it is not about either
company. Both are ~21 people covering one narrow band of the stack deeply.
off_CRM is one person covering six bands.

---

## Strawberry

`strawberrybrowser.com` · legal entity Dendrite Systems · Stockholm · macOS + Windows

| Fact | Value |
|---|---|
| Funding | $6M, October 2025, led by General Catalyst and EQT Ventures |
| Angels | Founders of Lovable, Hugging Face, Supabase |
| Founders | Charles Maddock, Sebastian Thunman, Arian Hanifi |
| Headcount | 21 (June 2026) |
| Open beta | February 2026, now public |
| GAIA | ~78%, self-reported, 466 tasks, exact match |
| Native integrations | 93, containing 1,254 hand-written operations |
| OAuth apps | 1,975 |
| Pricing | Free 2k credits · Intern $20/8k · Part-time $100/30k · Full-time $250/75k · top-up $10/1k |

### The moat is one decision, and it is expensive

Every scraper and cloud agent dies at the login wall. Strawberry starts behind
it. Because the agent runs in-process with the user's real Chrome profile —
cookies, SSO, passkeys — it reaches LinkedIn Sales Navigator, an ATS, a CRM and
internal dashboards with no API key and no OAuth app to approve. Traffic leaves
from a residential IP with a real browser fingerprint.

Two of the twelve tasks in their own benchmark suite are LinkedIn sourcing runs.
That is not a demo choice; it is the argument.

### The number that matters is 1,254

Ninety-three native integrations containing 1,254 hand-written operations, each
one written and maintained by a person. That is not an AI achievement, it is a
grind, and it is the clearest signal of where 21 people and $6M went.

It is also the argument for `S-07.01.01`, the MCP client: **MCP inherits other
people's tool definitions instead of hand-writing 1,254 of your own.** That is
the only way one developer competes with that number.

### Read this repo's own blueprint before reading them as a rival

`docs/architecture/BROWSER_AGENT_BLUEPRINT.md` is 486 lines mapping every
Strawberry feature onto eight stages of this build, stating which already exist
here under other names, and explaining why this repo does not fork Chromium.
Stage 1 is built and verified against Chromium 141. One slice of Stage 3 is built.

Strawberry is not a competitor that was discovered. It is the reference
implementation this repo has been building against since August 2026.

### Stage by stage

| Capability | Strawberry | off_CRM | Read |
|---|---|---|---|
| Browser control | Chromium fork, in-process | Stage 1 built — hand-written CDP client against the real profile | Same property, a fraction of the cost. The app icon was given up, not the capability. |
| Page perception | DOM + vision fallback | Accessibility tree, integer handles, a model cannot describe an element | **Better design here.** ~50× fewer tokens, stable across restyling. |
| Action surface | Full browser driving | Ten verbs, no `evaluate`, real input events | Refusing JS execution in a logged-in session is a deliberate, defensible narrowing. |
| Runs, plans, trace | PLAN.md + live trace + steer/resume | **Run loop built** — `agent/run.py`: step budget, money ceiling, cost ledgered, append-only trace. Missing: PLAN.md (`S-02.02.02`) and steering (`S-02.02.03`) | Corrected 2026-09-14. The gap is the plan file and the steer channel, not the loop. |
| Sub-agents | Parallel, isolated context, own plan each | Not built — `S-04.01.03` | Worth copying. A context-budget trick, not a speed trick. |
| Companions & skills | Personas + 40+ shipped skills | Stage 3, first slice only | The personas are the cheap half. The scoping is the engineering. |
| Memory | Facts always injected, procedures on demand | Facts built (`ai/context.py`). Procedures not — `S-04.01.02` | Their split is correct. Half of it is already here. |
| Permissions | Three levels + safety countdowns | Countdowns **built** (`browser/countdown.py`, `S-02.02.04`). Policy drawn at volume and autonomy; attended-only on session-gated sites. Three-level rules open (`S-06.01.02`) | Different axis, arguably stricter. Stack them rather than swap. |
| MCP & integrations | 93 native, 1,254 ops, plus MCP | Not built — `S-07.01.01` | Highest-leverage unbuilt story in the repo. |
| Model routing | Anthropic preferred, Google and xAI failover | Registry, trust tiers, broker, egress log | Theirs is a failover switch. This is a governance system. |

### What they have that engineering cannot buy

A downloadable app people run as their default browser, 21 people, General
Catalyst, and a credit meter that turned browsing into a business model — plan
names (*Intern*, *Part-time*, *Full-time*) that sell employment fractions rather
than software seats. That framing is free to copy and worth more than any
feature above.

### Where they are weak

Sharing a companion currently grants edit access to its settings and memories, a
sharp edge they document themselves. Meeting transcription needs OS-level audio
capture, fragile across macOS and Windows. And the architecture depends on the
agent sitting inside an authenticated session with broad reach — precisely the
blast radius `ai/broker.py` and the ten-verb rule exist to avoid. Their ceiling
is higher. Their floor, when a page misbehaves, is lower.

---

## Crux

`getcrux.ai` · San Francisco · Y Combinator W24 · Emergent Ventures

| Fact | Value |
|---|---|
| Funding | $2.6M seed, February 2024 |
| Founded | 2022 |
| Founders | Himank Jain (CEO, ex-J&J ML, ex-PwC), Atharva Padhye, Prabhat Singh (CTO) — all IIT Bombay |
| Headcount | 9 on the YC page, 21 on a tracker (May 2026) — conflicting |
| Named logos | Cloaked, Motion, ElevenLabs, Jerry |
| Agents | Copilot, Market Researcher, Creative Strategist, Creative Producer |
| Ad platforms | Meta, Google, TikTok, YouTube, Pinterest, Snapchat |
| First-party data | Snowflake, Tableau, Metabase, Looker |

### The three numbers that matter most

From Crux's own YC launch post, not from a critic:

- **$500K minimum annual ad spend**
- **6+ months of account history**
- **20–25 creatives tested per month**

That is not sales snobbery, it is a statistical floor. To claim "question hooks
beat stat hooks" you need enough creatives, enough spend behind each, and enough
time for seasonality to wash out. Below that line the difference between two
hooks is noise and a confident answer is a lie.

**This is the single most important fact in this document** for anyone
considering copying the "learn from your own performance data" loop.

### How it works, in three steps

1. **Deconstruct.** Every image and video in the ad account is broken into
   hundreds of labelled elements — hook type, storyline, music, pacing, CTA,
   format, who is on screen.
2. **Correlate.** Those labels join to real spend and performance to find which
   element values keep appearing in winners.
3. **Prescribe.** Output is a brand-specific playbook plus a **weekly creative
   brief** telling the team what to shoot next.

Note the core deliverable: a brief for humans, weekly. The Creative Producer
agent that generates the asset is the newer layer on top. The original, proven
business is telling a good creative team what to make. That ordering is a lesson.

### Claims, and how much weight to put on them

| Claim | What it says | Confidence |
|---|---|---|
| 4 weeks → 4 minutes per ad | Time to produce one concept. The core pitch. | Vendor-reported |
| Motion: 7,600+ assets in 4 months | Volume from a 3-person creative team. Most specific and most believable. | Vendor-reported |
| Cloaked: scaled 10x, raised $375M | Correlation presented as contribution. The raise is real; the attribution is marketing. | Treat as logo, not proof |
| Fintech: $1.1M saved on Google Search | Unnamed customer, unnamed baseline, one channel. | Unverifiable |
| ~$1.7M ARR, $5M valuation | Third-party *estimate* dated 2024 — two years stale, never confirmed. | Low |

### Their four agents, translated

| Agent | What it really is | Nearest thing in this repo |
|---|---|---|
| Copilot | Chat front door over everything else. A router. | `ai/modes.py` orchestrated mode |
| Market Researcher | Competitor ad monitoring + social listening on a schedule. | `distribution/trends.py`, `topics.py` |
| Creative Strategist | The correlation engine. The actual product, hardest to copy. | `ai/bandit.py` + `TemplateScore`, pointed at the wrong data |
| Creative Producer | Generation from the winning pattern. Newest, thinnest, most commoditised. | `video/` + `imagery/` — **deeper here** |

### Overlap with this repo

| Capability | Crux | off_CRM | Read |
|---|---|---|---|
| Video assembly | Generates ad variants from winning patterns | `video/` — timeline, edits, presets, recipes, assembly, mixdown, undo | **Deeper on mechanics here.** Nobody at a 21-person adtech startup hand-wrote a muxer. |
| Creative direction | Learned from the brand's own ad performance | `director.py` — topic → shape and words | **They win, decisively.** This guesses from a topic; theirs learns from spend. |
| Captions | Part of the pipeline | Deterministic transcript → cues → text clips | Parity. This is more auditable; theirs is used daily. |
| Image generation | On-brand creative from a brand kit | `imagery/` — generate → gate → review → score | Same loop. They have brand kits; this has gates and a swipe queue. |
| Performance feedback | Six ad platforms, creative fatigue detection | Engagement snapshots, local outbox only | **Their actual moat**, and it is not the video. |
| Distribution | Paid channels, live | `distribution/` — goals, caps, pacing, trends, local outbox | This plans and never publishes. Theirs is the point. |
| Data posture | "We strictly do not train on your data" | Allowlist payloads, single egress gate, trust tiers, logged | Theirs is a promise. This is an architecture. Nobody in adtech is asking for it yet. |
| Buyer | Performance marketing team, 7–8 figure spend | Undefined | The open question. |

### Do not misread where their defensibility lives

Video generation is becoming commodity — every model provider ships it. What is
not commodity is the closed loop: real spend data from six platforms, 100+
creative parameters tagged consistently, and enough accounts to know which hook
works in which vertical. That needs platform API access, customer trust and time.

If this repo ever aimed at that market, the honest gap to close is **the
measurement side, not the rendering side** — and that side needs ad accounts
this project does not have.

### Where they are weak

Cold start is brutal: a new brand gets nothing useful for months, which caps
their market to heavy spenders. They depend on six ad-platform APIs they do not
control; one Meta permissions change can break the product overnight. Their
published outcomes are all vendor-reported.

### The hiring signal

Crux is hiring a **Founding Engineer, Full Stack / AI Video — Bengaluru,
₹80L–₹1Cr, 0.5–1.0% equity** (as listed 2026-09-12; postings change). Their other
two founding roles are US-remote go-to-market. The one engineering seat they are
opening, in India, at founding equity, is for AI video.

This repo holds 8,554 lines of Python and 4,817 of TypeScript doing exactly
that: a timeline document with invariants, every edit a pure function behind a
default-deny registry, a frame resolver implemented twice and pinned by one
conformance fixture, a hand-written WebM muxer, deterministic auto-captions, and
61 of 162 CapCut feature rows built.

The 2026-09-05 Floqer brief called the content studio "unmatched and unpriced"
and said it had to become either the wedge or a distraction. This is the first
buyer found for it.

---

## Span versus depth

Three funded companies, three narrow bands, ~21 people each:

- **Clay / Floqer** — find, enrich, write. 150+ and 80+ data providers.
- **Strawberry** — act on the web. One band, fully owned.
- **Crux** — make creative, measure spend. Make it, measure it, make the next one.
- **off_CRM** — all six bands. 1,520 passing tests. No buyer in any of them.

The instinct is to read that span as range — proof the architecture generalises.
Read it the other way. Each funded band is narrow **because** narrow is what gets
a customer, and any of those teams could build the other five bands badly in a
quarter if a customer asked. Six-band span is not a moat, it is deferred choice.

---

## Verdict

1. **Stop reading Strawberry as a competitor.** They are the spec, by this
   repo's own written admission. Build `S-02.02.02` and `S-07.01.01`; treat the
   rest of the eight stages as optional.
2. **The gap is the plan file and the steer channel, not the run loop.**
   Revised 2026-09-14.
3. **Crux is the first real buyer the video engine has ever had.** Closest fit
   between what is built here and what somebody is paying for, across three briefs.
4. **But their moat is the measurement loop, not the rendering.** Pursue Crux as
   a role, not as a market enterable from a laptop. Be clear which one it is.
5. **Six bands at one-person depth is the actual risk.** Every funded competitor
   beats this repo in its own band and would lose in the other five — worth
   nothing, because customers buy one band at a time.
6. **The egress wall still has no buyer, and that is now a pattern.** Floqer's
   buyers do not ask for it. Strawberry's architecture is the opposite of it.
   Crux answers the question with one sentence on a website and customers accept
   it. Keep the wall — it costs nothing to keep and it is genuinely excellent —
   but stop expecting it to open a door.

---

## Method and ambiguity

Public sources only, fetched 2026-09-12. Strawberry detail from its own
canonical-facts and benchmarks pages plus funding coverage; Crux detail from its
YC company page, YC launch post and its own site. Repo figures counted from the
working tree at `aa38057`: `ai/` 11,356 lines, `browser/` 4,934, `agent/` 3,495,
`video/` 8,554 Python and 4,817 TypeScript, `imagery/` 1,020, `distribution/`
3,574, `outreach/` 8,950; 1,520 Python tests passing as of 2026-08-28.

**Ambiguity.** Strawberry's October 2025 round is labelled "seed" by most
coverage and "Series A" by one tracker — one round, two labels. Crux team size is
9 on YC and 21 on a tracker; treat both as unreliable. The $1.7M ARR and $5M
valuation figures are third-party estimates from 2024. Crux's founder list
differs between its YC profile and Crunchbase, which names a fourth co-founder.
Every customer outcome quoted from either company is vendor-published and
unverified. GAIA ~78% is self-reported. Salary and equity bands are as listed on
the day and change without notice.

**Sources.** ycombinator.com/companies/getcrux · getcrux.ai · emergent.vc ·
crunchbase.com · tracxn.com · getlatka.com · sifted.eu · siliconcanals.com ·
startupsmagazine.co.uk · hyperight.com · nyteknik.se · aiworld.eu ·
strawberrybrowser.com
