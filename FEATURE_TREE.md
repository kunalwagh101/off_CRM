# The Feature Tree

**What off_CRM is made of, all the way down, and what is wired to what.**

Read this if you are about to build something, review something, or decide what
gets built next. It is written to be read twice: once by someone who has never
seen the code, and once by an engineer who has to change it. Both readings are
in here on purpose, marked **`Plain:`** and **`Precise:`**.

There are five other documents and they do different jobs. This one exists
because none of them answered the question *"show me the whole machine, in
parts, with the wires drawn."*

| Document | Answers |
|---|---|
| `README.md` | What is this product? |
| `SYSTEM_MAP.md` | What are the big pieces, roughly? |
| `PRODUCT_BACKLOG.md` | What did we **decide to build** in this workstream? |
| `BOARD.md` | What is the status of that work **right now**? |
| `BUILD_STATE.md` | What happened, session by session? |
| **`FEATURE_TREE.md`** ← this | **What exists in the repo, in a tree, wired, with the truth about each part** |

There is a visual version of this document — the same content with the schematic
and the coverage chart drawn rather than described:
**https://claude.ai/code/artifact/36a7be48-e0a9-4fa6-80e2-7e5fd3227955**
This file is the source of truth; the page is rebuilt from it.

The distinction that matters most is between this file and `PRODUCT_BACKLOG.md`.
The backlog was decomposed **from a conversation**. This tree is decomposed
**from the repository**. Section 8 is what happens when you put them side by
side, and it is not a comfortable read.

---

## 1. What do we call the levels?

You asked whether these are features, segments or sections. Here is the answer,
and the reason.

Four levels. Not three (too coarse to test), not five (nobody maintains five).

```
Pillar        P-3            A part you could sell on its own
  Module      P-3.2            A working part inside a pillar
    Capability  P-3.2.4          ONE thing a person can do
      Behaviour   P-3.2.4.b        ONE rule that must hold — this is what a test checks
```

**Plain:** A pillar is a *shop*. A module is a *counter* in the shop. A
capability is a *thing you can buy at that counter*. A behaviour is a *promise
about how it works* — "it never charges you twice" — and every promise gets a
test.

**Precise:**

| Level | ID | Definition | Sizing rule |
|---|---|---|---|
| Pillar | `P-n` | A bounded context with its own vocabulary. If two pillars share a data model, one of them is wrong. | Never "done". It has a maturity level. |
| Module | `P-n.m` | A cohesive unit inside the pillar — usually one Python package or one directory. Owns its storage. | Weeks. |
| Capability | `P-n.m.k` | A vertical slice a user can name. Cuts through storage, logic and interface. **Independently shippable.** | 1–5 days. |
| Behaviour | `P-n.m.k.a` | One Given/When/Then. Machine-testable. | One test. |

### The join to the board

**A Capability and a Story are the same object seen from two sides.** A Story is
a Capability *while it is being built*. That is the join key, and it means we do
not run two competing plans:

```
FEATURE_TREE.md              PRODUCT_BACKLOG.md / BOARD.md
   Capability  P-5.1.3   ←→   Story  S-01.02.03
   Behaviour   P-5.1.3.a ←→   Acceptance criterion (Given/When/Then)
```

Anything in this tree that has **no** `S-` number is work that exists in the
repository but has never passed through the delivery process. Section 8 counts
them.

> **Why not just extend the backlog?** Because the backlog answers "what are we
> doing next" and this answers "what have we got". Merging them produces a
> document that is wrong for both questions. They are joined at the Capability,
> which is enough.

---

## 2. The whole product on one page

Ten pillars. The number in brackets is lines of shipped code.

```
off_CRM
│
├─ P-1  THE WALL ...................... AI containment           [ 4,900 ]  ✅
│        Nothing a model can say gets it more data than it was handed.
│
├─ P-2  THE BRAIN ..................... model orchestration      [ 6,300 ]  ✅
│        Which model, how many times, was the answer any good.
│
├─ P-3  THE BOOK ...................... people & records         [ 5,900 ]  ◐
│        Who exists, why we think so, and where they are in the pipeline.
│
├─ P-4  THE FINDER .................... discovery & enrichment   [ 2,700 ]  ◐
│        Going out and coming back with people who were not in the book.
│
├─ P-5  THE VOICE ..................... outreach & email         [ 8,800 ]  ◐
│        Writing to them, and the machinery that makes mail actually arrive.
│
├─ P-6  THE STUDIO .................... video & image production [ 25,400 ]  ✅
│        A topic goes in. A finished, graded, captioned video comes out.
│
├─ P-7  THE MEGAPHONE ................. distribution & measure   [ 3,600 ]  ◐
│        Posting it, at a rate you set, and reading back what happened.
│
├─ P-8  THE HANDS ..................... browser agent            [ 3,200 ]  ◐
│        Doing anything a person can do in a browser, inside a box.
│
├─ P-9  THE COCKPIT ................... API & screens            [ 12,300 ]  ◐
│        The surfaces a human actually touches.
│
└─ P-10 THE FLOOR ..................... storage, jobs, honesty   [ 3,700 ]  ✅

         ✅ mature   ◐ partial   ⬜ not built
```

**Plain:** Read it top to bottom and it is a story. The Wall and the Brain are
the safe AI engine. The Book and the Finder are the CRM. The Voice, the Studio
and the Megaphone are the three ways off_CRM reaches the world — email, content,
posts. The Hands are for everything with no API. The Cockpit is what you look
at. The Floor is what it all stands on.

---

## 3. How the pillars wire together

This is the part no other document draws. Arrows are **data flow**, and every
arrow is a real function call you can find in the repository.

```
                            ┌──────────────────────────────┐
                            │   P-9  THE COCKPIT           │
                            │   api/app.py · 178 routes    │
                            │   frontend · 22 screens      │
                            └───┬────────────────────┬─────┘
                                │ commands           │ reads
             ┌──────────────────┘                    └──────────────┐
             ▼                                                      ▼
   ┌───────────────────┐                                 ┌────────────────────┐
   │  P-4 THE FINDER   │   people + evidence             │  P-10 THE FLOOR    │
   │  discovery.py     │────────────────┐                │  db/ · file_queue  │
   │  apollo_client.py │                │                │  verify_board.py   │
   └─────────┬─────────┘                ▼                └──────────△─────────┘
             │                ┌───────────────────┐                 │
             │ dedupe/score   │  P-3 THE BOOK     │  every pillar ──┘
             └───────────────▶│  outreach/store   │  persists here
                              │  sales · campaigns│
                              └───┬────────┬──────┘
                                  │        │  (contacts NEVER cross the wall)
              ┌───────────────────┘        └─────────────┐
              ▼                                          ▼
   ┌─────────────────────┐                    ┌──────────────────────┐
   │  P-5 THE VOICE      │                    │  P-6 THE STUDIO      │
   │  outreach/engine    │                    │  video/ · imagery/   │
   │  deliverability/    │                    │  frontend/src/video  │
   └──────────┬──────────┘                    └───────────┬──────────┘
              │                                            │
              │  ┌─────────────────────────────────────────┘
              │  │
              ▼  ▼
   ╔══════════════════════════════════════════════════════════╗
   ║  P-1 THE WALL   —  the ONLY door to any model            ║
   ║                                                          ║
   ║  EgressRequest → tier filter → quota → build from EMPTY  ║
   ║                → scan (block, never redact) → call → log ║
   ╚═══════════════════════════╤══════════════════════════════╝
                               ▼
                    ┌────────────────────┐
                    │  P-2 THE BRAIN     │
                    │  modes · verify    │
                    │  cache · bandit    │
                    │  evals · recall    │
                    └─────────┬──────────┘
                              ▼
                     external AI providers


   ┌──────────────────────┐          ┌────────────────────────┐
   │  P-7 THE MEGAPHONE   │          │  P-8 THE HANDS         │
   │  distribution/       │◀────────▶│  browser/  (in a box)  │
   │  outbox · adapters   │  will    │  CDP · perceive · page │
   └──────────────────────┘  use     └────────────────────────┘
              ▲                                   │
              │ engagement                        │ everything runs
              └───────────────────────────────────┘ --network=none by default
```

### The three rules the wiring encodes

**1. Everything to a model goes through one door.**
`P-1` is not a library the other pillars *may* use. It is the only code in the
repository that calls a provider. `broker.py` is that door.

> **Plain:** imagine an office where only one person is allowed to walk out of
> the building, and they get searched on the way. Nobody else has a key.
> **Precise:** `payload.py` builds the outbound object from an **allowlist,
> starting empty**. The default is not "send everything minus secrets" — the
> default is *nothing*, and fields are added by policy. That inversion is the
> whole security model: a field nobody thought about is absent, not leaked.

**2. Models never pull. off_CRM pushes.**
There is no tool a model can call that reads the CRM. It receives a constructed
payload and replies. A model that can *ask* for data has access; one that can
only *receive* does not.

**3. Human approval sits between generation and every outward action.**
`P-5`, `P-6` and `P-7` all stop at a review queue. Nothing reaches a real inbox,
a real timeline or a real feed without a person saying yes.

---

## 4. The four mature pillars

These have deep tests and can be built on with confidence.

### P-1 · THE WALL — AI containment

**Plain:** The AI is kept in a room. Things are handed *to* it. It cannot reach
out and take anything. Even if someone tricks it into asking, there is nothing
to ask with.

**Precise:** `offsetx_apollo_builder/ai/` (the containment half) plus
`browser/box.py` and `browser/guard.py`. 42 egress-wall tests, 43 sandbox tests,
30 box tests.

| ID | Module | What it does | Tests | Story |
|---|---|---|---|---|
| P-1.1 | `tiers.py` | Trust tiers A–D from **two** axes: jurisdiction *and* retention terms. Passing one is not enough | in wall suite | — |
| P-1.2 | `payload.py` | Builds the outbound object from an allowlist, **starting empty** | 42 | — |
| P-1.3 | `scanner.py` | Pre-flight scan. A hit **blocks and raises** — it never redacts and continues | 42 | — |
| P-1.4 | `broker.py` | The single egress gate. 1,119 lines, and the only code that calls a provider | 42 | — |
| P-1.5 | `quota.py` | RPM / RPD / spend accounting, file-backed, checked before the call | 13 | — |
| P-1.6 | `log.py` | Egress log: provider, tier, **exact payload**, timestamp. Own table | 28 | — |
| P-1.7 | `workspace.py` | Per-workspace settings; provider keys Fernet-encrypted at rest | — | S-06.01.01 ◐ |
| P-1.8 | `sandbox.py` | Container isolation for AI-written code. `--network=none`, refuses `host` | 43 | S-03.01.02 ✅ |
| P-1.9 | `browser/box.py` | The browser's container: network **yes**, host filesystem **never** | 30 | S-03.01.01 ✅ |
| P-1.10 | `browser/guard.py` | Per-request domain allow-list via the DevTools `Fetch` domain. Deny-by-default unattended | 30 | S-03.01.01 ✅ |

**Capabilities worth naming:**

- `P-1.4.1` A caller asks for a completion and gets one, or a **structured refusal** that says which rule stopped it. → the refusal is a first-class return value, not an exception string.
- `P-1.3.1` A payload containing a credential, a mailbox header or an internal field name is **blocked at every policy level, including `full`**.
- `P-1.9.1` A container is composed with `--read-only --cap-drop=ALL --security-opt=no-new-privileges --user=65534:65534`, the store is never mounted, and the profile lives in a **named volume, not a bind mount** — so there is no host path in the command at all.

**Wired to:** everything. Nothing else may call a provider.
**Known gap:** `S-06.02.01` ("no secret may enter a model prompt") is still in
BACKLOG as a *test suite* — the control exists, the adversarial proof does not.

---

### P-2 · THE BRAIN — model orchestration

**Plain:** Choosing which AI to use, asking it more than once when it matters,
checking whether the answer was any good, and not paying twice for the same
question.

**Precise:** the capability half of `ai/`. 48 cache tests, 45 eval tests, 34
bandit, 34 failure-classification, 33 abstraction, 31 tools, 30 recall.

| ID | Module | What it does | Tests |
|---|---|---|---|
| P-2.1 | `registry.py` | `config/providers.yaml` → resolved provider. **Adding a provider is a config edit, never a code change** | 10 |
| P-2.2 | `modes.py` | Four run modes: simple, verified, compare, orchestrated | 17 |
| P-2.3 | `verify.py` | write → check → repair → review | 19 |
| P-2.4 | `cache.py` | Exact **and lexical near-match** response cache, keyed on the payload | 48 |
| P-2.5 | `bandit.py` | Thompson allocation between **approved** template variants | 34 |
| P-2.6 | `evals.py` + `eval_cli.py` | Eval datasets and automated scoring | 45 |
| P-2.7 | `abstraction.py` | Widens the *shape* of a request: bands, stages, margins | 33 |
| P-2.8 | `recall.py` | RAG over **sent** mail only. Received mailbox content is inaccessible by default | 30 |
| P-2.9 | `tools.py` + `tool_cli.py` | Owner-pinned tools. A catalogue, not a constructor | 31 |
| P-2.10 | `failures.py` + `errors.py` | What kind of failure this was, and what to do about it | 34 |
| P-2.11 | `context.py` | Context assembly under a budget | 20 |
| P-2.12 | `discovery.py` | Asks a provider which models its key actually reaches | — |

**The design decision worth understanding:** `P-2.5` only ever allocates between
variants a **human approved**. The bandit optimises *within* a fence, it does not
choose the fence. That is the difference between "AI improves your templates" and
"AI writes whatever wins", and only one of those is safe to run unattended.

**Wired to:** called by `P-5` (email), `P-6` (director, captions), `P-7`
(pipeline). Always through `P-1`.

---

### P-6 · THE STUDIO — video & image production

**Plain:** Type *"why nobody reads changelogs"* and get back a finished,
graded, captioned, vertical video. Nobody touches a timeline.

**Precise:** 25,400 lines across `video/`, `imagery/` and `frontend/src/video/`.
**This is the most heavily tested pillar in the repository** — 400+ Python tests
plus 8 browser test files.

| ID | Module | What it does | Tests | Story |
|---|---|---|---|---|
| P-6.1 | `video/timeline.py` | The document and its invariants. **Clips on a track cannot overlap — that state is unrepresentable, not handled** | 49 | S-01.01.01 ✅ |
| P-6.2 | `resolve.ts` ↔ `timeline.py` | Two resolvers, one answer, pinned by `tests/fixtures/timeline_conformance.json` | 29 | S-01.01.02 ✅ |
| P-6.3 | `video/edits.py` | Every edit a pure function; a **default-deny** registry | in engine suite | — |
| P-6.4 | `video/engine.py` | create → edit → undo → caption → render → gate | 46 | S-01.02.01 ✅ |
| P-6.5 | `video/effects.py` | **48 GLSL primitives × 124 named looks.** Every parameter declares a `neutral`, so `amount=0` is bit-exact identity | 49 | S-01.02.03 ✅ |
| P-6.6 | `video/presets.py` | Transitions, animations, text styles, speed curves — as data | 36 | — |
| P-6.7 | retime path | Speed curves, freeze, reverse, as one integral | 34 | S-01.02.02 ✅ |
| P-6.8 | `video/assembly.py` | Material + recipe → a finished project, plus the edit-diff | 94 | S-01.03.01 ✅ |
| P-6.9 | `video/director.py` | A topic → a shape and the words. The model's reply is **checked**, not trusted | 31 | S-01.03.02 ✅ |
| P-6.10 | `video/mixdown.py` | The audio mix as a gain-envelope plan the browser executes | 29 | — |
| P-6.11 | `video/captions.py` | Transcript → readable cues → text clips, deterministically | 42 | — |
| P-6.12 | `video/gates.py` | MP4 + WebM + WAV header parsing. Gates on the **exported file**, not on intent | 33 | — |
| P-6.13 | review queue | Push / ignore / edit | 37 | S-01.04.01 ✅ |
| P-6.14 | `imagery/` | generate → gate → review → swipe → learn generator preference | 22 | — |
| P-6.15 | `frontend/src/video/` | demux, footage cache, render, WebM mux, export | 8 files | — |

**The architectural inversion worth knowing:** for **transitions**, the browser
gets a preset id and resolves it. For **effects**, the *server* resolves and the
browser only executes — because 124 looks is too large a catalogue to ship per
clip. Same system, opposite decision, and the reason is size, not taste.

**Wired to:** `P-2` for the director and captions (through `P-1`). `P-7` for
publishing. `P-10` for storage. `P-9` for the editor screen.

---

### P-10 · THE FLOOR — storage, jobs, honesty

**Plain:** Where everything is kept, how work survives a crash, and the script
that catches us lying about what is finished.

| ID | Module | What it does | Tests | Story |
|---|---|---|---|---|
| P-10.1 | `db/` | One interface, SQLite locally or Postgres. `copy.py` migrates between them | 28 | — |
| P-10.2 | `file_queue.py` | Durable file-backed queue | 2 | — |
| P-10.3 | `attempt_ledger.py` | Attempts recorded so a retry is never blind | 1 | — |
| P-10.4 | `notebook.py` | Research-notebook export; **the destination is a trust tier** | 34 | — |
| P-10.5 | `codegraph.py` | Graphify wrapper with the semantic path switched **off** | 33 | — |
| P-10.6 | `scripts/verify_board.py` | **The lie detector.** Re-runs every DONE claim's test and fails on any failure | 29 | S-06.02.06 ✅ |
| P-10.7 | question lifecycle | An answered question unblocks; a deleted one does not | 29 | S-06.02.07 ✅ |

**`P-10.6` is the most important 300 lines in the repository** and it deserves a
plain explanation: anybody can write the word DONE. This script reads `BOARD.md`,
finds the test each DONE item names, **runs it**, checks the files it names
exist, and exits non-zero if any of that is false. It has already caught its own
author twice.

**Its blind spot is real and is the subject of section 8.**

---

## 5. The partial pillars — where the work is

### P-3 · THE BOOK — people & records  ◐

**Plain:** The filing cabinet. Every person, every company, every campaign, every
deal and where it sits on the board.

**Precise:** 5,900 lines. **And this is where the risk is concentrated.**

| ID | Module | Lines | Tests | State |
|---|---|---|---|---|
| P-3.1 | `outreach/store.py` | **2,297** | **no dedicated suite** | ⚠️ |
| P-3.2 | `outreach/sales.py` — kanban, commissions, leak flags, projections | **1,312** | **6** | ⚠️ |
| P-3.3 | `outreach/models.py` + `schema.py` | 850 | indirect | ◐ |
| P-3.4 | `campaigns.py` — the registry of campaign kinds; email is only one | 300 | 21 | ✅ |
| P-3.5 | `intake.py` — two-mode intake; **a contact list never meets a model** | 470 | 28 | ✅ |
| P-3.6 | `categories.py` / `locked_categories.py` | 200 | 3 | ◐ |
| P-3.7 | `outreach/notion.py` — mirror to Notion | 300 | 8 | ◐ |
| P-3.8 | `outreach/backup.py` | 200 | — | ◐ |

**Capabilities not yet named as stories** (this is the gap, stated plainly):

- `P-3.1.1` A contact survives a crash mid-import without a partial row.
- `P-3.1.2` Two writers cannot corrupt the same campaign.
- `P-3.2.1` A commission figure is reproducible from the event log.
- `P-3.2.2` A revenue projection is labelled with the **evidence class** it came from.

None of those has a test. `outreach/store.py` is the single largest module in the
product and the only thing exercising it is other tests using it incidentally.

---

### P-4 · THE FINDER — discovery & enrichment  ◐

**Plain:** Going out to the public web, coming back with real people and the
evidence for why they matter, and not adding the same company twice.

| ID | Module | Lines | Tests | State |
|---|---|---|---|---|
| P-4.1 | `discovery.py` — Scrapling + Crawl4AI, robots.txt, allowlists, rate limits, redirect checks, response limits, **SSRF controls** | **1,420** | **6** | ⚠️ |
| P-4.2 | `apollo_client.py` + `existing_poi_enrichment.py` — enrichment with a hard credit cap | 500 | 13 | ◐ |
| P-4.3 | `dedupe.py` — same company, two names | 217 | 3 | ⚠️ |
| P-4.4 | `scoring.py` | 60 | 2 | ◐ |
| P-4.5 | `research.py` | 209 | — | ◐ |
| P-4.6 | **A real crawler** — frontier, politeness, change-driven revisit | — | — | ⬜ S-05.01.01 |
| P-4.7 | **Extraction packs** — a new source is one row, not a new parser | — | — | ⬜ S-05.01.02 |
| P-4.8 | **Competitor teardown** — take a hit post apart, rebuild the shape | — | — | ⬜ S-05.01.03 |

`P-4.1` carries the SSRF controls, the robots.txt honouring and the domain
allowlist — **security-critical code, 1,420 lines, six tests.**

To be fair to what exists: those six tests aim at the right things
(`test_public_url_policy_blocks_social_and_private_targets`,
`test_crawl4ai_adapter_hard_disables_evasive_browser_features`,
`test_discovery_api_requires_robots_and_uses_injected_public_fetcher`). They are
not decoration. But six tests is one assertion per 236 lines on the only module
in the product that issues outbound requests to **arbitrary user-supplied
URLs**, and the failure mode of a gap there is a request from your machine to
somewhere it should never reach.

---

### P-5 · THE VOICE — outreach & email  ◐

**Plain:** Writing to people, and the machinery that decides whether the mail
actually arrives instead of landing in spam.

| ID | Module | Lines | Tests | Story |
|---|---|---|---|---|
| P-5.1 | `outreach/engine.py` — three-stage sequences, stop-on-reply | **951** | **2** | ⚠️ |
| P-5.2 | `outreach/gmail.py` | 491 | — | ⚠️ |
| P-5.3 | `outreach/providers.py` + `provider_profiles.py` | 1,000 | 5 | ◐ |
| P-5.4 | `outreach/email_expert.py` | 506 | 2 | ◐ |
| P-5.5 | `outreach/memory.py` — learns from approved human edits | 300 | 7 | ◐ |
| P-5.6 | `deliverability/preflight.py` — SPF, DKIM, DMARC, alignment, SES evidence | 400 | 16 | S-08.01.03 ✅ |
| P-5.7 | `deliverability/store.py` — durable immutable jobs, single-claim | **1,031** | 16 | S-08.01.02 ✅ |
| P-5.8 | `deliverability/ses.py` — raw MIME with stream + feedback + unsubscribe metadata | 400 | 16 | S-08.01.03 ✅ |
| P-5.9 | `deliverability/events.py` — signed idempotent feedback → suppression | 350 | 16 | S-08.01.04 ✅ |
| P-5.10 | `deliverability/unsubscribe.py` — signed one-click | 250 | 16 | S-08.01.05 ◐ |
| P-5.11 | permission + suppression | — | 16 | S-08.01.01 ✅ |

**The split is stark and worth naming:** the *new* deliverability sub-package
(`P-5.6`–`P-5.11`) went through the delivery process and has story IDs, evidence
and tests. The *original* engine (`P-5.1`–`P-5.5`) — which is what actually sends
your mail today — has 3,250 lines and 16 tests between all five modules.

---

### P-7 · THE MEGAPHONE — distribution & measurement  ◐

**Plain:** Posting the finished thing, at a rate you decide, and reading back
what actually happened to it.

| ID | Module | Tests | Story |
|---|---|---|---|
| P-7.1 | `platforms.py` — what each platform permits, and what off_CRM refuses | 21 | — |
| P-7.2 | `trends.py` — competitor watch list, what is actually rising | 19 | — |
| P-7.3 | `topics.py` — what several channels cover at once | 14 | — |
| P-7.4 | `pipeline.py` — trend → brief → swipe → caption → draft | 21 | — |
| P-7.5 | `pacing.py` — **the owner's cap, and the engine's advice.** Your number wins | 19+26 | S-01.04.02 ✅ |
| P-7.6 | `automation.py` | 39 | — |
| P-7.7 | `youtube.py` — Data API v3 **read** client | 19 | — |
| P-7.8 | `publishers.py` — adapter interface + **local outbox** | 21 | — |
| P-7.9 | **Real YouTube upload** | — | 🔒 S-01.05.01 |
| P-7.10 | **IG / FB / TikTok / LinkedIn / X adapters** | — | 🔒 S-01.05.02 |
| P-7.11 | **Read engagement back from the platform** | — | 🔒 S-01.05.03 |

🔒 = blocked on **you**, not on engineering. `P-7.9` needs a Google Cloud project
with YouTube Data API v3 enabled — free, about ten minutes. `P-7.10` needs Meta
app review, TikTok's content-posting audit and the LinkedIn partner programme:
weeks of calendar time and no code.

**Today every "publish" lands in a local outbox.** That is honest and it is also
the product's largest single gap: it can make content and cannot yet post it.

---

### P-8 · THE HANDS — browser agent  ◐

**Plain:** off_CRM can use a web browser like a person — look at the page, click,
type, scroll — inside a locked box, and it writes down everything it does.

| ID | Module | Tests | Story |
|---|---|---|---|
| P-8.1 | `cdp.py` — hand-written DevTools client, no Playwright | 36 | S-02.01.01 ✅ |
| P-8.2 | `perceive.py` — the page as an **accessibility outline**, not HTML | 36 | S-02.01.02 ✅ |
| P-8.3 | `page.py` — **ten verbs, real input events, no `evaluate`** | 36 | S-02.01.03 ✅ |
| P-8.4 | `policy.py` — per-domain pace, attended-only, refusal | 36 | S-02.01.04 ✅ |
| P-8.5 | `trace.py` — append-only, no way to remove a step | 36 | S-02.01.05 ✅ |
| P-8.6 | `session.py` — attach to a real browser; stale-lock recovery | 36 | — |
| P-8.7 | `identity.py` + `signin.py` — six platforms; **no function accepts a password** | 21 | S-03.02.01 ✅ |
| P-8.8 | **The vault** — per-account key, OS keychain / passphrase fallback | 15 focused | S-03.02.02 ✅ |
| P-8.9 | **Revoke and forget** — clear vaulted cookies, destroy account envelope, trace the act | 6 focused incl. live Chromium | S-03.02.03 ✅ |
| P-8.10 | **The run loop** — goal → bounded sequence of actions | — | ⬜ S-02.02.01 |
| P-8.11 | **PLAN.md as memory** | — | ⬜ S-02.02.02 |
| P-8.12 | **Interrupt, steer, resume** | — | ⬜ S-02.02.03 |
| P-8.13 | **Safety countdowns** | — | ⬜ S-02.02.04 |

**The honest summary:** off_CRM now has safe browser hands and a complete managed session lifecycle: attended login → protected per-account vault → destructive revoke/forget. It still has no will. Every individual motion works, but nothing yet decides which motion to make from a goal. `P-8.10` is now the next dependency-contiguous autonomy feature and remains the highest-leverage unbuilt thing in this pillar.

---

### P-9 · THE COCKPIT — API & screens  ◐

**Plain:** The website you actually click on, and the ~190 doors behind it.

| ID | Module | Size | Tests | State |
|---|---|---|---|---|
| P-9.1 | `api/app.py` — **178 routes in one 3,248-line file** | 3,248 | ~47 total | ⚠️ |
| P-9.2 | `api/auth.py` | 116 | **4** | ⚠️ |
| P-9.3 | `api/email_delivery.py` — 12 routes | 500 | 16 | ✅ |
| P-9.4 | `api/schemas.py` + `config.py` | 300 | — | ◐ |
| P-9.5 | 22 React screens | 15,876 | 1 suite + 7 video suites | ◐ |
| P-9.6 | **Every endpoint authorises and validates** | — | — | ⬜ S-06.02.02 |
| P-9.7 | **Keyboard and screen-reader usable** | — | — | ⬜ S-06.02.05 |

Routes by area — `campaigns` 44, `ai` 39, `video-projects` 16, `sales` 14,
`notion` 6, `trends` 5, `distribution` 5, and 39 others across smaller groups.

**`P-9.1` is a structural problem, not a style complaint.** 178 routes in one
module means no route group can be tested, deployed, rate-limited or authorised
independently, and `S-06.02.02` cannot be honestly closed until it is split.

---

## 6. The truth about test coverage

Here is the finding that should drive the shipping order. Counting tests per
thousand lines of the module they cover:

Each row is one module measured against the test file that covers it. Nothing
here is estimated — the commands are at the end of this section.

```
                module                          lines   tests   per 1,000 lines
  ──────────────────────────────────────────────────────────────────────────────
  P-6  video/effects.py       ← test_video_effects   1,044    49   ███████████ 47
  P-6  video/timeline.py      ← test_video_timeline  1,114    49   ███████████ 44
  P-1  ai/sandbox.py          ← test_ai_sandbox        438    43   ███████████ 98
  P-1  ai/broker.py           ← test_ai_egress_wall  1,119    42   █████████   38
  P-8  browser/               ← 3 browser suites     3,239    87   ██████      27
  ──────────────────────────────────────────────────────────────────────────────
  P-5  deliverability/        ← test_email_delivery  2,713    16   █            6
  P-3  outreach/sales.py      ← test_sales_tracker   1,312     6   ·            5
  P-4  discovery.py           ← test_discovery       1,420     6   ·            4
  P-9  api/app.py             ← auth + outreach_api  3,248    12   ·            4
  P-5  outreach/engine.py     ← test_outreach_engine   951     2   ·            2
  P-3  outreach/store.py      ← (no direct suite)    2,297     0   ·            0
```

**The coverage is inverted.** The newest code — the video editor and the AI wall,
built in the last few weeks — is the best tested in the repository. The oldest
code — the code that touches **real people's personal data, real money and real
sends** — is the least tested.

Two rows deserve a caveat rather than a red mark:

- **`deliverability/` at 6/kloc is not the same kind of thin.** Its 16 tests were
  written *against acceptance criteria* and are named in evidence blocks, so they
  cover the rules that matter rather than the lines. Ratio is a proxy, and here it
  understates. Everything below it in the table has no such defence.
- **`api/app.py` at 4/kloc undercounts**, because many suites exercise routes
  incidentally through `TestClient`. But `S-06.02.02` — "every endpoint authorises
  and validates" — is still in BACKLOG, which is the real statement: nobody has
  checked all ~190 doors on purpose.

Reproduce the whole table:

```bash
python -m pytest --collect-only -q 2>/dev/null | grep "::" | sed 's/::.*//' \
  | sort | uniq -c | sort -rn
find offsetx_apollo_builder -name '*.py' | xargs wc -l | sort -rn | head -30
```

**Plain:** we have spent our care on the fun part. The parts that could actually
hurt someone are the parts nobody has checked.

That is not a criticism of any past decision; it is what happens when a process
is introduced partway through a project and only governs work done *after* it.
Which is exactly section 8.

---

## 7. Maturity legend

| Mark | Meaning | Bar |
|---|---|---|
| ✅ | **Mature** | Story ID, tests, evidence block, verifier re-runs it |
| ◐ | **Works, unproven** | Code runs; no story ID, or tests do not cover the criteria |
| ⬜ | **Not built** | Named, decomposed, not started |
| 🔒 | **Blocked externally** | Waiting on an approval only the owner can obtain |
| ⚠️ | **Load-bearing and thin** | Large, business-critical, and under-tested |

---

## 8. Reconciliation: what the board knows vs what the repo contains

This section is why the tree was worth building.

`PRODUCT_BACKLOG.md` was decomposed from a conversation. It contains **71
requirements and 54 stories, with zero orphans** — and that is true. The
verifier confirms it every run.

But it is true *about the conversation*. Checked against the repository:

```
Backlog mentions of the shipped CRM core
─────────────────────────────────────────────────────
  apollo .............. 0     notion ............. 0
  discovery ........... 0     sales .............. 0
  scoring ............. 0     dedupe ............. 0
  intake .............. 0     bandit ............. 0
  recall .............. 0     tiers .............. 0
  imagery ............. 0     enrichment ......... 0
  notebook ............ 0     codegraph .......... 0
```

**Roughly half the shipped code has no backlog ID.** `P-3`, `P-4`, most of `P-5`,
all of `P-2`'s quality machinery and all of `P-9` were built before the delivery
process existed and were never brought into it.

**The verifier cannot catch this, and it is important to understand why.**
`verify_board.py` checks that every requirement in the coverage table has a
story, and that every story on the board has evidence. Both of those are true.
What it cannot check is whether the coverage table *describes the product* — it
validates the map against itself. A module nobody ever wrote a requirement for is
invisible to it. That is not a bug in the script; it is the boundary of what a
script can know.

**This tree is the fix.** It is decomposed from the repository, so a module can
no longer be invisible by never having been mentioned.

### The proposed correction

Three new epics, so the existing product is governed by the same rules as new
work — and so `⚠️` items get a home:

| New | Covers | Existing code |
|---|---|---|
| **E-08 — The record survives everything** | `P-3` The Book | `outreach/store.py`, `sales.py`, `campaigns.py` |
| **E-09 — Finding people, safely and legally** | `P-4` The Finder | `discovery.py`, `apollo_client.py`, `dedupe.py` |
| **E-10 — Every door is locked and checked** | `P-9` The Cockpit | `api/app.py`, `api/auth.py` |

This is a **change-control decision, and it is yours to make** — descoping and
re-scoping are the owner's call, not the builder's. Section 11 asks it directly.

---

## 9. How we ship from here — the two-gate protocol

You asked for two tests before a feature counts. Here it is as a rule, extending
`DEFINITION_OF_DONE.md` rather than replacing it.

```
  Capability pulled  ─▶  built  ─▶  GATE 1  ─▶  GATE 2  ─▶  DONE
                                   code       live
```

### Gate 1 — the code test

Unchanged from the current Definition of Done. Named tests, run this session,
output pasted into the evidence block, verifier re-runs them.

### Gate 2 — the live check  *(new)*

**Plain:** the test proving it works in the *lab* is not the test proving it
works in the *product*. Gate 2 is starting the real application and using the
feature the way you would.

**Precise:** every DONE capability gains a second evidence field:

```
- P-4.1.3 · Discovery refuses an internal address
  tests:   tests/test_discovery.py::test_ssrf_target_is_refused
  command: python -m pytest tests/test_discovery.py -q
  result:  7 passed (2026-09-03)
  live:    scripts/live/P-4.1.3.sh          ← NEW: runs against a booted app
  live-result: refused 169.254.169.254 with 403; egress log empty (2026-09-03)
  code:    offsetx_apollo_builder/discovery.py
  commit:  <sha>
```

A live check must:

1. **Boot the real thing** — `uvicorn` for API work, a real Chromium for browser
   work, a real `docker run` for box work.
2. **Exercise it the way a person would** — through the API or the UI, not by
   importing the module.
3. **Assert on an observable outcome** — a row in the database, a file in the
   outbox, a rejected request, a rendered pixel.
4. **Be re-runnable by you**, from a clean checkout, with one command.

This is not new machinery. It is already how the strongest work in the repo was
proven — the video export was checked against a real Chromium encoding a real
file, the pacing cap against a live uvicorn comparing bytes in the outbox, the
browser guard against a real page calling `fetch()`. **Gate 2 makes the best
existing practice mandatory instead of optional.**

### The verifier change that enforces it

`scripts/verify_board.py` gains one rule: a DONE item with a `live:` script that
does not exist, or that exits non-zero, fails the board. Until that lands, Gate 2
is a checklist item and I will say so rather than implying it is enforced.

### What a capability looks like when it is genuinely finished

```
  [x] Behaviours written as Given/When/Then before any code
  [x] Code implemented — no TODO, no stub, no fixture standing in for real data
  [x] GATE 1  a named test, run this session, output in the evidence block
  [x] GATE 2  a live check against the booted application, output recorded
  [x] Failure paths covered, not only the happy one
  [x] CHANGELOG + this tree updated (status mark changed)
  [x] BOARD.md updated, verifier green
```

---

## 10. The recommended shipping order

Ordered by **risk removed per day of work**, not by what is pleasant to build.

### Wave 1 — close the exposure  *(the ⚠️ rows)*

| # | Capability | Why first |
|---|---|---|
| 1 | `P-4.1` — a real test suite for `discovery.py` | 1,420 lines of SSRF, robots and allowlist controls with six tests. The only part of the product that makes outbound requests to **arbitrary user-supplied URLs**. Boundary cases first: redirect chains that end somewhere private, DNS names resolving to link-local, IPv6 loopback forms, and response-size limits. |
| 2 | `P-9.2` + `P-9.6` — authorise and validate every endpoint | ~190 routes, 4 auth tests. `S-06.02.02` exists; it has just never been pulled. |
| 3 | `P-3.1` — durability and concurrency tests for `outreach/store.py` | The largest module in the product, holding every contact, with no direct suite. |
| 4 | `P-5.1` — cover the sending engine's stop-on-reply and sequence rules | 951 lines, 2 tests, and it sends real mail. |

**None of these is new functionality.** All four are proving that code which
already runs does what we believe. That is the cheapest risk reduction available
and it is what a senior reviewer would insist on before anything else ships.

### Wave 2 — make the agent act

| # | Capability | Why |
|---|---|---|
| 5 | `P-8.8` — the vault (`S-03.02.02`) — **DONE 2026-09-04** | The login now has protected per-account session custody, an OS-backed/passphrase master boundary, and fail-closed prompt/connection gates. |
| 6 | `P-8.9` — revoke and forget (`S-03.02.03`) — **DONE 2026-09-04** | The managed session lifecycle is now closed: real Chromium loses the vaulted session cookie before the account envelope and public connection record are destroyed. |
| 7 | `P-8.10` — the run loop (`S-02.02.01`) | **Next autonomy slice.** Hands and a safe credential lifecycle exist; will does not. |
| 8 | `P-8.11`–`P-8.13` — PLAN.md, interrupt/resume, countdowns | These make the loop *safe* to leave alone. Shipping the run loop without them is not defensible. |

### Wave 3 — reach the world

| # | Capability | Why |
|---|---|---|
| 9 | `P-7.9` — real YouTube upload | **Ten minutes of your time unblocks it.** It is the fastest path from "makes content" to "posted content". |
| 10 | `P-4.6`–`P-4.8` — crawler, extraction packs, teardown | Feeds `P-7` with what is actually working out there. |
| 11 | `P-7.10` — the remaining platform adapters | Blocked on app reviews. Start the paperwork in parallel with wave 1. |

### Wave 4 — a team can use it

`P-9.1` split, `S-06.01.01` workspaces surfaced, `S-06.01.02` permissions,
`S-06.01.03` cost estimates, `S-06.01.05` deploy and rollback, `S-06.02.05`
accessibility.

---

## 11. What I need from you

Four decisions. Three are yours by the change-control rule; one is a ten-minute
task that unblocks the most visible gap in the product.

1. **Do the three new epics (E-08, E-09, E-10) get created?** They bring the
   existing CRM under the same process as new work. Saying no is a legitimate
   answer — it means we accept that half the product stays ungoverned — but it
   should be said out loud rather than by default.

2. **Wave 1 before Wave 2?** My recommendation is yes and I would argue for it,
   but it is four capabilities of *proving old code* before any new feature, and
   that is a real cost. If you would rather see the agent act first, say so and
   I will sequence Wave 2 first with the risk stated on the board.

3. **Is Gate 2 mandatory for every capability, or only for those that touch the
   outside world?** Mandatory-everywhere is cleaner to enforce. Outside-world-only
   is faster and covers the cases that actually matter. I lean to the second, with
   "touches the outside world" defined as: sends a request, writes a file a person
   will open, renders pixels, or stores a credential.

4. **The Google Cloud project for YouTube.** Free, about ten minutes, no human
   review. It converts `P-7.9` from 🔒 to buildable and turns the product from one
   that makes content into one that posts it.

---

## 12. Keeping this file honest

This tree is a claim about the repository, so it decays the moment the repository
moves. Two rules:

1. **Changing a status mark is part of the Definition of Done.** A capability
   that reaches DONE flips `◐` to `✅` in the same commit as its evidence block.
2. **A new module with no `P-` number is a process violation**, exactly as a
   feature with no story ID is. If the tree cannot see it, it is invisible again,
   and section 8 is what that costs.

Line counts and test counts in this document were measured on 2026-09-03 against
commit `7a1d584`. They will drift. The commands that produced them are in
`DEMO.md §1`; re-run them rather than trusting these numbers a month from now.
