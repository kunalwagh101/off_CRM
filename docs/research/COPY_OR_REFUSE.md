# What to copy, what to refuse

**Status: point-in-time analysis, not a working record.** Written 2026-09-14
against the working tree at `aa38057`. Story IDs and "already built" claims were
read from the code and from `BOARD.md`, not from `BUILD_STATE.md`. Re-check
against `BOARD.md` before acting — this file is not maintained.

Live page: <https://claude.ai/artifact/CHt5b9abvUsjmErHtdZBcy>
Companion doc: [`COMPETITORS_STRAWBERRY_CRUX.md`](COMPETITORS_STRAWBERRY_CRUX.md)
— who these companies are.

---

## 0. A correction that comes before everything

The 2026-09-12 brief said this repo's run loop does not exist. **Wrong.**

`agent/run.py` is 2,091 lines and holds a real run loop: `AgentRun`, a `Decision`
type, a step budget, a money ceiling, cost estimated before and ledgered after,
page content treated as untrusted data, every step appended to a trace. Safety
countdowns are built too (`browser/countdown.py`, `S-02.02.04`).

The cause: `BUILD_STATE.md` was last updated 2026-08-28 and roughly fifteen
commits landed after it. **`BOARD.md` is the current truth; `BUILD_STATE.md`
lags.** Fix that drift before it misleads another session — a stale second source
of truth is worse than no second source.

What is genuinely still open is smaller and sharper: `S-02.02.02` PLAN.md
(READY) and `S-02.02.03` interrupt/steer/resume (BACKLOG). Not a missing run
loop — a missing plan file and a missing steer channel.

---

## 1. Glossary

Written for someone who has not met these terms before. The last column says
what this repo has today.

| Term | Plain meaning | off_CRM |
|---|---|---|
| **Chromium fork** | Chromium is the open-source engine behind Chrome and Edge. A fork copies that whole source and ships your own browser from it. | No — deliberately |
| **In-process** | "In the same running program." Strawberry's agent code sits inside the browser and can touch page memory directly. This repo's sits outside and talks over a socket. | Out of process, on purpose |
| **DOM** | Document Object Model — the tree of every element on a page as the browser holds it. Thousands of nodes, most of them meaningless wrappers. | Reads the a11y tree instead |
| **Accessibility (a11y) tree** | A second, much smaller tree the browser builds for screen readers. Says "button named Send", not "div class css-1x4kf9". ~50× fewer tokens, survives a redesign. | Yes — `browser/perceive.py` |
| **Vision fallback** | When page text cannot describe something (a canvas, an image-only button), screenshot it and let the model look. A backup sense, not the main one. | Screenshots yes, vision loop no |
| **Full browser driving** | The agent can do anything a person can: click, type, scroll, tab, upload. No API needed — the site's UI is the API. | Ten verbs, not "anything" |
| **Ten verbs** | The agent may only choose from ten named actions. A fixed menu; it cannot invent an eleventh. | Yes — `browser/page.py` `ACTIONS` |
| **`evaluate`** | A CDP command that runs any JavaScript inside the page. If a model can write JS in a logged-in session, one poisoned page can make it read your Gmail. | Banned by design |
| **Real input events** | Send actual mouse and key events instead of setting a field's value in code. Sites listen for hover, focus and keypress; a code-set value looks filled and behaves empty. | Yes — `dispatchMouseEvent` |
| **Context window** | How much text a model holds at once. Read 100 profiles into one conversation and the useful part drowns. This limit is the whole reason sub-agents exist. | Bounded at 50 steps/run |
| **Sub-agents / isolated context** | Split a big job into small ones. Each child gets a fresh conversation, a small task, and returns a short summary. The parent never sees raw pages. A memory trick; speed is the side effect. | No — `S-04.01.03` |
| **Own plan each** | Every sub-agent writes its own to-do file and step log, so it pauses, resumes and audits independently. | No plan file yet |
| **Personas / Companions** | A saved agent profile with a name and a job. Underneath: a row with a name, an instruction block, which memories it sees, which tools it may use. The persona is marketing; the scoping is the engineering. | No — `S-04.01.01`, READY |
| **Skills** | A saved procedure in plain text — "how to build a competitor battlecard", step by step. Pulled in only when needed. A recipe card, not a feature. | No — `S-04.01.02` |
| **Facts injected / procedures on demand** | Two stores, split on purpose. Facts are short and always relevant, so paste them into every prompt. Procedures are long and rarely relevant, so fetch on request. | Facts yes, procedures no |
| **PLAN.md** | One markdown file per run holding plan and to-dos. Three readers, one file: model memory, UI checklist, owner steering. State in a file means a run survives a crash. | No — `S-02.02.02`, READY |
| **Work trace** | Append-only log of every step — no edit, no delete. Audit record, resume point and "watch it think" view from one artefact. | Yes — `browser/trace.py` |
| **Steer / resume** | Steer = correct a run while it is running. Resume = pick a stopped run back up from its last good step. | `replay()` exists, steering no |
| **Three-level permissions** | A global setting, then a rule per tool per app, then a temporary override lasting only this chat. Three dials, so "allow once" never becomes "allow forever". | One axis — `S-06.01.02` |
| **Safety countdown** | A visible, cancellable timer before something irreversible. Beats a dialog, because people click through dialogs. | Yes — `browser/countdown.py` |
| **Failover switch vs governance** | Failover: "if Anthropic is down, call Google." Governance: "this data class may only reach this trust tier, and here is the logged proof of what left." | Governance, fully built |
| **Muxer** | Multiplexer. Video and audio arrive as two compressed streams; the muxer interleaves them into one playable file with correct headers and timestamps. Normally a library. | Yes — hand-written WebM |
| **Ad variants from winning patterns** | Break performing ads into parts (hook, first 3 seconds, music, pacing, CTA), find which parts recur in winners, build new ads reusing them. Learning, not guessing. | Same idea, on email |
| **Brand kit** | Brand rules as machine-readable data: logos, colour codes, fonts, tone, banned words, legal lines. Without it, generated creative is off-brand and unusable. | No — nothing in `imagery/` or `video/` |
| **Creative pipeline** | Performance data → what wins → brief → variants → quality gates → approval → publish → measure → feed back. A loop, not a line. | Every piece exists, unjoined |
| **Credits / metering** | Charge per unit of AI work, not per seat. Matches price to cost, so a heavy user cannot lose you money. | Counting yes, pricing no |

---

## 2. Should this repo build a Chromium fork?

**Verdict: refuse, and it is not close.**

The reason is already written in `docs/architecture/BROWSER_AGENT_BLUEPRINT.md`:
a fork buys exactly one thing, that the agent runs in your real logged-in
session, and that same property comes from launching your own Chrome against your
own profile with a debugging port and driving it over CDP.

What the fork costs:

| Cost | Detail | Who pays |
|---|---|---|
| Build infrastructure | Tens of GB of source, hours of compile per platform. macOS, Windows and Linux runners, every time. | You, weekly, forever |
| Upstream treadmill | Chromium ships stable roughly every four weeks plus security patches. Fall behind and you ship known-exploitable software as someone's main browser. | A dedicated person |
| Code signing | Apple Developer ID plus notarisation; Windows Authenticode with an EV certificate. Otherwise both flag your installer as malware. | Money + identity paperwork |
| Auto-update channel | Update server, signed manifests, rollback. If it breaks you cannot patch machines you already shipped to. | An ongoing service you run |
| Switching cost | Changing someone's default browser is one of the hardest asks in consumer software. Strawberry ships history/password import purely to fight this. | Every user |
| Extension compatibility | Chrome Web Store support against a *curated* list. Curation is permanent. | Support load forever |

What it would gain, honestly — three things and only three: an app with your name
on the icon (distribution and brand, which matters to a consumer company and not
to this project); the ability to change browser behaviour itself (custom sidebar,
pages rendered inside a chat pane, split view without reload); and immunity to a
Chrome policy change. None is worth an engineer-year at one person.

### The one real risk of not forking

This approach depends on Chrome continuing to allow `--remote-debugging-port`
against a normal user profile. Google has tightened this path before.

**Mitigation, not a fork:** support a dedicated off_CRM browser profile (a copied
profile directory, not the live one), keep `browser/session.py` able to find
Chromium, Brave and Edge, and write the fallback down now so the day it breaks is
an afternoon rather than a rewrite. `find_browser()` and `profile_hints()`
already exist — the seam is there.

### The rest of the list

| Their feature | Verdict | Why |
|---|---|---|
| DOM + vision fallback | **Build the vision half** | Keep the a11y tree as the primary sense — better and cheaper. Add vision as a fallback verb when a snapshot returns fewer than N actionable nodes. ~a day; PNGs are already captured. |
| Full browser driving | **Refuse** | "Anything a person can do" includes running arbitrary JavaScript. Ten verbs plus a vision fallback covers real tasks. The closed vocabulary is the safety story. |
| Ten verbs, no `evaluate`, real input | **Already built** | Verified against Chromium 141. Do not touch it. |
| Sub-agents, own plan each | **Build** — section 4 | Highest quality-per-line item on the list. |
| Personas + 40 skills | **Build the scoping, skip the personas** | Cute names add nothing at one user. The scoping underneath — memories, tools, permissions — is real. `S-04.01.01`. |
| Ad variants from winning patterns | **Build** — section 4 | The hard half is already owned. |
| Hand-written muxer | **Already built, and rare** | The line that makes a founding-engineer interviewer sit up. Lead with it. |

---

## 3. Three head-to-heads

### A. Their PLAN.md + live trace + steer/resume, against this run loop

**Split.** This run loop is stronger where it matters for trust: a real step
budget, a money ceiling, cost estimated before and ledgered after, findings that
survive only when deterministic code finds the value *and* its supporting quote
in a captured page. Strawberry publishes no equivalent discipline. **They are
better at the human surface** — the plan is a file you can open and edit, and you
can talk to a run while it runs.

Three changes, in order:

1. **Write the plan to a file — `S-02.02.02`, already READY.** Add
   `agent/plan.py`. One `PLAN.md` per run, beside the trace in the run directory.
   Free prose at the top (goal, decisions, sources); a machine-readable to-do
   block underneath, each item with id, title and status `pending`/`doing`/`done`.
   The rule that makes it work: **the file is the state, not a copy of it.**
   Re-parse after every successful write and stream the parsed version to the
   watcher — `agent/watch.py` already has the `Progress` observer for this.

2. **Add a steer channel — `S-02.02.03`.** Give `AgentRun` an `asyncio.Queue`
   for incoming owner messages. At the top of each loop iteration, drain the
   queue and fold anything found into the next `Decision` input as a section
   marked *owner instruction* — never mixed with page text, which stays untrusted
   data. Steering that arrives mid-step waits for the next step; do not interrupt
   an in-flight CDP call or you leak a page state you cannot reason about.

3. **Make resume a first-class command.** `ResumeState` and `replay(trace)`
   already exist in `run.py`. What is missing is the door: a CLI verb and an API
   endpoint taking a run id, rebuilding state and continuing. Ninety percent is
   already paid for.

### B. Their three-level permissions + countdowns, against this policy layer

**Countdowns are already built** — `browser/countdown.py`, `S-02.02.04`, DONE.

The real difference is the *axis*. Strawberry asks "which tool, in which app, for
which chat". This repo asks "how much of this, and is a human watching" —
`browser/policy.py` draws the line at **volume and autonomy**, so LinkedIn is
allowed at reading pace when asked and never on a schedule. **This axis is the
better one.** Per-tool allow lists train people to click "always allow", after
which the control is gone.

But one axis is not enough, which is what `S-06.01.02` is for. Do not replace.
**Stack:**

- **Level 1, global mode:** normal, or ask-before-everything. One switch.
- **Level 2, per integration per action:** `ask` / `allow` / `never`, per
  workspace. `browser/identity.py` already has a `ConnectionStore` keyed by
  platform and account; the rule table hangs off the same key.
- **Level 3, run-scoped override:** "allow for this run only", held in memory,
  gone when the run ends. Never written to disk — that is the point.
- **Then keep the existing axis on top as a hard floor:** no level-2 rule may
  grant unattended access to a session-gated platform. A permission dialog must
  never unlock something the policy layer refuses.

### C. Their model routing, against this broker

**This wins outright — do not change the design.** Strawberry routes for uptime
and cost. This repo routes for *permission*: `ai/tiers.py` classifies the data,
`config/providers.yaml` places a provider in a tier, `ai/payload.py` builds the
outbound object from an allowlist starting empty, `ai/broker.py` is the only code
that may call a provider, `ai/log.py` records what left.

**One thing to take from them: failover.** A governance system can still fail
*closed* when a provider is down — correct behaviour, bad experience. Add a
narrow rule inside the broker: if a call fails for a transport reason (timeout,
5xx, rate limit) rather than a policy reason, retry on the next provider **at the
same trust tier or lower**, and write the substitution into the egress log.

Say the constraint in the code comment, because it is the whole safety property:
*failover may go down a tier, never up.* A retry that quietly promotes data to a
looser provider is exactly the bug this module exists to prevent.

---

## 4. The five additions, with exact steps

### Add 1 — Learn from your own performance data

**Build it, but point it at data that actually exists here.**

Most of this is already owned. `ai/bandit.py` runs Thompson allocation across
approved variants. `ai/context.py` stores a `TemplateScore` with sends, replies,
a reply rate and a `judged` flag that refuses to call a winner too early.
`distribution/store.py` has a `dist_metrics` table with `record_metrics()` and
`latest_metrics()`.

The machinery exists and is wired to *email replies*. Crux wired the same shape
to *ad spend*. The work is a new score source and one join table.

Files: `ai/bandit.py`, `ai/context.py`, `distribution/store.py`, plus new
`creative/features.py` and `creative/scores.py`.

**Step 1 — give every creative a feature vector.** This is what Crux calls "100+
parameters" and it is not magic: a fixed list of labels per asset, stored as
declared data the way `video/presets.py` already stores transitions.

```
creative_features
  asset_id      TEXT  -- FK to image_assets.id or video_renders.id
  kind          TEXT  -- 'image' | 'video'
  hook_type     TEXT  -- question | stat | problem | demo | testimonial
  first_frame   TEXT  -- face | product | text | motion
  pacing        TEXT  -- slow | medium | fast   (cuts per 10s, bucketed)
  duration_s    REAL
  caption_style TEXT  -- from video/presets.py, already a registry
  cta_text      TEXT
  palette       TEXT  -- dominant hue bucket from imagery/gates.py
  music         TEXT  -- none | ambient | beat
  source        TEXT  -- 'declared' | 'derived' | 'model'
  PRIMARY KEY (asset_id, kind)
```

The `source` column matters. A feature set in the recipe is `declared` and is
ground truth. One computed from the file (duration, cut rate, palette) is
`derived`. One a model guessed from watching the video is `model` — useful, and
never allowed to outvote the other two. Without that column you eventually train
on your own hallucinations.

**Step 2 — join features to outcomes.** `creative/scores.py`, one function: given
a campaign, read `dist_metrics` for every published post, attach each post's
asset features, return per-feature-value aggregates — n, mean engagement, and a
confidence interval. Reuse the `judged` / `MIN_SENDS_TO_JUDGE` idea from
`TemplateScore` verbatim: **below threshold, report "we do not know yet" and
refuse to rank.** Do not build a model. Counting with an honest interval beats a
regression you cannot explain, and it matches the data volume available.

**Step 3 — feed winners into the brief, through the fence.** `video/director.py`
takes a topic and returns a shape plus words. Add an optional `evidence`
argument: top feature values with n and rate. The model receives them as *data in
the payload*, through `ai/payload.py`'s allowlist, like everything else. It does
not query the metrics table. Models never pull.

**Step 4 — let the bandit allocate, not decide.** `bandit.arms_from_scores()`
already turns scores into arms; point it at creative variants. Keep the existing
rule: the bandit decides *how much traffic* an approved variant gets, never
*whether* a new variant goes live.

> **The hard truth.** Crux's own launch post states the requirement: **$500K
> minimum annual ad spend, six months of history, 20–25 creatives tested per
> month.** That is a statistical floor, not sales gating. off_CRM publishes to a
> local outbox and has no ad spend. Build the mechanism — it is cheap because the
> parts exist — but be honest that it will have nothing to learn from for a long
> time, and point it at the only real signal available: email reply rates, which
> already work, and post engagement once something actually publishes.

### Add 2 — Sub-agents with isolated context (`S-04.01.03`)

**Build it. Best quality-per-line on this list.**

Plainly: instead of one agent reading 100 pages into one conversation, a parent
splits the job into 20 chunks of 5. Each child starts with an empty conversation,
reads its 5 pages, hands back a small structured answer. The parent only ever
sees answers.

There is an advantage here Strawberry does not talk about: `agent/result.py`
already defines `ResultSchema`, `Finding` and `Provenance`, and `agent/verify.py`
already checks that a claimed value appears in a captured page. **That is exactly
the contract a child should return.** The typed hand-back is the hard part of
sub-agents and it was built for another reason.

Files: new `agent/subagent.py`, plus `agent/run.py`, `agent/result.py`,
`browser/trace.py`, `browser/budget.py`.

1. **Define the child contract first.** A child takes a goal string, a
   `ResultSchema`, a step budget, a money budget and a starting URL list. It
   returns verified `Finding` objects and its own trace id. Nothing else crosses
   the boundary — no raw page text, no free-form notes. If it cannot fill the
   schema it returns empty with a reason.
2. **Budgets divide, never multiply.** The parent's step budget and money ceiling
   are split among children, not handed to each. 50 steps across 5 children is 10
   each. `browser/budget.py`'s `BudgetLedger` is the natural home: a child
   allocation is a child row against the parent's ledger. Get this wrong and one
   plain-English request quietly becomes a hundred model calls — the most
   expensive bug available in this feature.
3. **Bound fan-out and depth.** Hard constants beside `MAX_RUN_STEPS`:
   `MAX_CHILDREN = 8`, `MAX_DEPTH = 1`. Depth 1 means no grandchildren. Ship it
   that way; recursive agents are a research project and a runaway bill.
4. **Each child gets its own trace, linked.** The child writes its own
   append-only trace; the parent records one step: "spawned child, id X, goal Y".
   `Trace` already refuses edits and deletes, so the audit story holds
   automatically. `agent/report.py` then renders a parent with collapsible
   children.
5. **Cap concurrency.** `asyncio.Semaphore(3)` or so. `S-11.05.01` — concurrent
   runs share one browser safely — is DONE, so the browser side is paid for. Each
   child gets a tab, not a browser.

### Add 3 — Facts always injected, procedures on demand (`S-04.01.02`)

**Worth adding. Here is the precise gap.** `ai/context.py` is the facts store and
it works. There is no *procedures* store: long, step-by-step playbooks relevant
only occasionally. Today a repeatable method would have to live in code or in the
prompt. Both are wrong — code is too rigid to edit, and the prompt is paid for on
every call whether relevant or not.

Facts and procedures have **opposite retrieval profiles**. A fact is ~20 tokens
and relevant to almost every run, so always-inject is cheap and correct. A
procedure is ~800 tokens and relevant to maybe one run in twenty. Inject all of
them every time and you pay 16,000 tokens for 800 tokens of value, and push the
actual task further from the model's attention. That is not a small
inefficiency — it makes answers measurably worse.

Files: new `agent/skills.py`, plus `ai/context.py`, `ai/payload.py`.

1. **Store a skill as a file, not a row.** A directory per skill with a markdown
   file and small front matter: name, one-line description, optional companion
   scope. Files mean you edit a procedure in your editor, diff it in git and
   review it in a PR. A row means you need a UI before you can fix a typo.
2. **Inject only descriptions; fetch bodies on demand.** Every run's prompt
   carries a menu of name plus one-line description, ~15 tokens each. The model
   asks for one by name, which triggers a plain file read — **not a
   model-initiated query against a store**, which would break the governing rule.
   The body then enters the next payload through `ai/payload.py` like any other
   allowlisted field.
3. **Write skills from runs that worked.** After a successful run, offer "save
   this as a skill". The trace and report already exist; turning a trace into a
   numbered procedure is a deterministic transform plus one model pass to tidy
   wording, with the owner approving the result.

### Add 4 — Brand kit, and a queue brands can add to

**Genuinely new. No story exists yet.** Nothing in `imagery/` or `video/` holds
brand rules — the schemas are `image_briefs`, `image_assets`,
`image_generator_stats`, `video_projects`, `video_history`, `video_renders`,
`video_media`, `video_transcripts`, `video_reviews`. No brand table anywhere.

Two things hide in this request. **The kit** is the brand's rules. **The queue**
is the brand's request line. Build the kit first; the queue is worthless without
it.

Files: new `brand/store.py`, new `brand/gates.py`, plus `imagery/gates.py`,
`video/director.py`, `video/presets.py`.

```
brand_kits
  id, workspace_id, name, updated_at

brand_rules            -- one row per rule, so each can be checked alone
  kit_id, kind, value, hard
     kind ∈ palette | font | logo | tone | banned_word
              | required_line | aspect | safe_area
     hard  = 1 means a violation blocks; 0 means it warns

brand_assets           -- the actual files
  kit_id, role, path, sha256
     role ∈ logo_primary | logo_mono | font_file | product_shot

brand_requests         -- the queue
  id, kit_id, requested_by, brief_text, refs_json,
  status, due_at, created_at
     status ∈ queued | briefed | generating | in_review
              | approved | rejected | published
```

1. **Make rules machine-checkable or do not store them.** This is the difference
   between a brand kit and a PDF nobody reads. "Use our blue" is useless.
   `palette = #1B4FA8, tolerance ΔE 5` is checkable. `imagery/gates.py` already
   parses image headers and computes size without an image library — extend that
   same deterministic style: dominant-colour distance, minimum logo clear space,
   aspect ratio, safe-area text bounds. A rule you cannot check automatically is
   a note for a human and belongs in the brief text, not the rules table.
2. **Run brand gates where quality gates run.** `imagery/engine.py` already does
   generate → gate → review queue → swipe → score. Brand gates slot in as a
   second gate stage, after quality gates and before anything reaches a human. A
   hard rule fails the asset and the reason is stored. Never silently fix an
   asset — a generator that keeps drifting off-palette is information you want.
3. **Inject the kit into the brief; never let the model read the store.** When
   `video/director.py` or the image brief builder runs, relevant kit rules go in
   as allowlisted payload fields — hex values, banned words, the required legal
   line. off_CRM pushes; the model does not pull.
4. **Then build the queue, thinly.** `brand_requests` plus five endpoints:
   create, list, claim, approve, reject. The status column is the whole product.
   No notifications, SLAs or assignment rules until one real brand has filed ten
   real requests — every one of those is a guess until then.

### Add 5 — The creative pipeline

**Assemble, do not build.** One new file joining six things that already exist.

| Stage | Where it lives | State |
|---|---|---|
| 1 · Request | `brand_requests` | New (Add 4) |
| 2 · Evidence | `creative/scores.py` | New (Add 1) |
| 3 · Brief | `video/director.py` | Built |
| 4 · Generate | `video/assembly.py`, `imagery/engine.py` | Built |
| 5 · Gates | quality gates + brand gates | Built / new half |
| 6 · Approve | review queue, swipe | Built |
| 7 · Publish | `distribution/engine.py` | Built — **local outbox only** |
| 8 · Measure | `dist_metrics` | Built |

Stage 8 feeds stage 2, and that is where the loop closes.

> **Say the blocker out loud.** Stage 7 writes to a local outbox. `S-01.05.01` —
> publish to YouTube through the official API — is **BLOCKED** on the board.
> Until something really publishes, stage 8 measures nothing and the loop is
> drawn rather than running. Build stages 1 and 2 anyway; they are cheap and work
> on email data today. But do not call the loop closed until a post goes out and
> a number comes back.

---

## 5. Build order, if only four things get done

1. **Fix the drift between `BUILD_STATE.md` and `BOARD.md`.** An hour. A stale
   second source of truth already produced wrong advice in a published brief and
   will do it again. Regenerate it from the board, or demote it to history and
   say so at the top.
2. **`S-07.01.01` — the MCP client.** Strawberry hand-wrote 1,254 operations. One
   MCP client inherits other people's instead. No other unbuilt story changes
   capability-per-hour this much.
3. **`S-02.02.02` PLAN.md, then `S-04.01.03` sub-agents.** PLAN.md first because
   sub-agents need a per-child plan to be worth anything, and because it is
   already READY. Sub-agents second because they are the biggest quality win and
   the typed hand-back contract already exists in `agent/result.py`.
4. **The brand kit — the checkable half only.** `brand_kits`, `brand_rules`,
   `brand_assets`, and brand gates inside `imagery/engine.py`. Skip the request
   queue until a real brand files real requests.

### The pushback

The question that prompted this document was "should we build a Chromium fork as
well — it might be a great add". That instinct is the pattern across three briefs
now: every capability that appears is genuinely buildable here, so the list grows
and nothing gets a buyer.

**The constraint is not capability. It is that six bands at one-person depth
beats nobody.** Build the four above, then stop adding and find one user.

---

## Confidence

High on everything about this repo — it was read directly from the working tree
at `aa38057` on 2026-09-14: module line counts, class and function names, SQL
schemas, and `BOARD.md` story states. High on Strawberry's integration counts,
pricing and funding, all vendor-published. High on the Crux $500K / 6-month /
20–25 creative floor — it is their own stated requirement. Low on Crux revenue
and team size. Every customer outcome quoted from either company is
vendor-reported and unverified. GAIA ~78% is self-reported.
