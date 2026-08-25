# Product backlog

**Methodology: Kanban with vertical-slice increments.** Justified from the work,
not from fashion:

- **Not Scrum.** Scrum's engine is a team committing to a fixed scope for a
  fixed window, and measuring velocity across many such windows. There is one
  implementer here and no throughput history, so a sprint commitment is a
  promise from a party who cannot be held to it and a velocity figure would be
  invented precision. The delivery prompt says as much and excludes both.
- **Kanban, because work arrives as a conversation.** "Do the effect engine
  next" is a pull, not a sprint plan. Flow with a hard WIP limit is the honest
  model of that, and it is what stops three half-built things existing at once.
- **Vertical-slice increments, because layers are how a project looks finished
  and does nothing.** Every increment is one capability that a person can use
  end to end — document, API, UI, test — never "the backend for X".

WIP limit is **2**. `scripts/verify_board.py` enforces it.

---

## 0. How to read an ID

```
E-01           epic      · a business outcome with a value hypothesis
F-01.02        feature   · a capability, belonging to exactly one epic
S-01.02.03     story     · a user-visible slice, independently shippable
T-01.02.03.a   task      · an engineering step, <= 1 day
```

IDs are stable. An ID is never reused, renumbered or recycled. Scope that is cut
moves to `DEFERRED` on the board with a reason and a trigger — it is never
deleted, because a deleted ID is scope that silently vanished.

---

## 1. Epics

### E-01 — The content engine produces publishable work without supervision
**Owner:** the product. **Value hypothesis:** the cost of a piece of content
falls far enough that volume stops being the constraint, and the owner's time
moves from *making* to *judging*.
**Leading indicator:** pieces reaching the review queue per week.

### E-02 — The agent can reach any platform, safely
**Value hypothesis:** coverage stops being limited to platforms with an API.
Anything a person can do in a browser becomes automatable, which is most of the
work in a CRM.
**Leading indicator:** share of tasks completed without a human touching a browser.

### E-03 — Accounts, secrets and the machine cannot be compromised
**Value hypothesis:** an agent that holds real logins is only adoptable if
losing it costs nothing. This epic is what makes the rest installable by anyone
other than its author.
**Leading indicator:** zero credentials reachable from a model prompt; zero
agent-reachable paths to the host filesystem.

### E-04 — Several agents work one goal together
**Value hypothesis:** a single agent's context fills with irrelevant material and
its judgement degrades. Specialised agents with isolated context hold quality at
larger tasks.
**Leading indicator:** task size (in steps) completed without a human correction.

### E-05 — The system knows what is working, out in the world
**Value hypothesis:** content decisions made from measured audience response beat
decisions made from taste, and the gap widens with volume.
**Leading indicator:** share of published pieces whose shape was chosen from
measured data rather than a default.

### E-06 — A team can run it in production
**Value hypothesis:** the product is worth nothing to an organisation if it only
runs on its author's laptop under its author's supervision.
**Leading indicator:** distinct workspaces in active weekly use.

---

## 2. Features and stories

### F-01.01 — The timeline and its invariants  *(E-01)*

#### S-01.01.01 — A timeline that cannot represent an invalid edit
**As a** content owner, **I want** an editor whose document cannot hold
overlapping clips or a clip reading past its own material, **so that** an export
never fails for a reason nobody could see on screen.
- **Given** a track with a clip at 0–3s, **when** a second clip is added at
  2–5s, **then** the edit is refused naming both clips and the document is
  unchanged.
- **Given** any edit that raises, **when** it is applied, **then** the project
  version number does not advance.
- **Dependencies:** none. **Size:** L. **Indicator:** exports failing gates.

#### S-01.01.02 — Two resolvers held to one answer by a fixture
**As a** developer, **I want** the Python and TypeScript resolvers pinned to a
shared conformance fixture, **so that** the preview cannot lie about what the
export will contain.
- **Given** the conformance document, **when** both resolvers sample the same
  ticks, **then** every field of every draw item is byte-identical.
- **Dependencies:** S-01.01.01. **Size:** M. **Indicator:** preview/export drift reports.

### F-01.02 — The export  *(E-01)*

#### S-01.02.01 — Video, audio and footage in one exported file
**As a** content owner, **I want** the exported file to contain the pictures,
the imported footage and the mix, **so that** what I publish is what I edited.
- **Given** a timeline with a music bed, **when** it is exported, **then** the
  file carries an Opus track and the server's gates confirm it.
- **Given** a timeline that makes no sound, **when** it is exported, **then** the
  file is not required to carry audio.
- **Dependencies:** S-01.01.02. **Size:** L. **Indicator:** silent-export incidents.

#### S-01.02.02 — Time remapping as one integral
**As a** content owner, **I want** speed curves, freeze and reverse, **so that**
a cut has rhythm without hand-keyframing every clip.
- **Given** a clip with a `hero` curve, **when** the server predicts a source
  tick for each output frame, **then** the browser resolves the same tick for
  all of them.
- **Dependencies:** S-01.02.01. **Size:** L. **Indicator:** manual keyframe edits per project.

#### S-01.02.03 — 48 pixel primitives and a catalogue of looks
**As a** content owner, **I want** filters and effects as named looks with a
strength slider, **so that** a piece can be graded in one click and an
orchestrator has something to choose between.
- **Given** any of the declared looks, **when** applied at strength 0, **then**
  the picture is bit-identical to the source.
- **Given** a look nobody declared, **when** it is applied, **then** the edit is
  refused by name.
- **Dependencies:** S-01.02.01. **Size:** L. **Indicator:** looks used per published piece.

### F-01.03 — Assembly and direction  *(E-01)*

#### S-01.03.01 — Material in, finished timeline out
**As a** content owner, **I want** a recipe and a length to produce a complete
cut, **so that** I judge a video instead of building one.
- **Given** a recipe and a target length, **when** assembly runs, **then** the
  project duration equals the target exactly and the manifest is renderable.
- **Given** material that cannot cover the length, **when** assembly runs,
  **then** it says what it settled for rather than silently producing something else.
- **Dependencies:** S-01.02.03. **Size:** L. **Indicator:** manual timeline edits after assembly.

#### S-01.03.02 — A topic in, a finished project out
**As a** content owner, **I want** a model to choose the shape and write the
words, **so that** a trend becomes a video without me designing it.
- **Given** a topic, **when** direction runs, **then** the reply is validated
  against the recipe registry before any clip is laid.
- **Given** a reply naming a shape nobody declared, **when** it is parsed,
  **then** it is refused by name and nothing is stored.
- **Dependencies:** S-01.03.01. **Size:** L. **Indicator:** topics reaching a renderable project.

### F-01.04 — The human gate  *(E-01)*

#### S-01.04.01 — Push, ignore, edit
**As a** content owner, **I want** every machine-made piece to wait for my
verdict, **so that** nothing reaches an audience I have not seen.
- **Given** an assembled project, **when** it is created, **then** it is in the
  review queue with no action from me.
- **Given** a project edited since its last export, **when** push is attempted,
  **then** it is refused with the sentence saying why.
- **Given** any verdict, **when** it is recorded, **then** the diff against what
  the machine produced is stored with it.
- **Dependencies:** S-01.03.02. **Size:** M. **Indicator:** kept-share of assembled pieces.

#### S-01.04.02 — The owner's posting cap, and advice about the rate
**As a** content owner, **I want** to set a hard daily ceiling per handle and be
*advised* about the rate, **so that** the engine never speaks more loudly in
public than I chose.
- **Given** a handle capped at N, **when** the N+1th post for a day is
  scheduled, **then** it is refused naming the handle and the cap.
- **Given** a goal that needs more than the cap, **when** the pacer runs, **then**
  it recommends the cap and says whose cap it was.
- **Given** the default mode, **when** a cycle runs, **then** the rate is
  computed and **not** applied.
- **Dependencies:** S-01.04.01. **Size:** M. **Indicator:** account restrictions (target: zero).

### F-02.01 — Driving a real browser  *(E-02)*

#### S-02.01.01 — A hand-written DevTools client
**As a** developer, **I want** a CDP client with no browser-automation
dependency, **so that** off_CRM attaches to the browser the owner already uses
rather than shipping one.
- **Given** a running browser, **when** a command is sent, **then** exactly one
  reply resolves it and an event arriving meanwhile does not.
- **Given** a command the browser rejects, **when** it is sent, **then** the
  caller raises and the connection remains usable.
- **Dependencies:** none. **Size:** M. **Indicator:** browser-layer defect rate.

#### S-02.01.02 — The page as an accessibility outline with stable handles
**As an** agent, **I want** the page as roles and names with integer handles,
**so that** I act on meaning rather than on class names that change every deploy.
- **Given** a page, **when** it is perceived, **then** nodes are ordered as a
  person reads them, not as CDP returns them.
- **Given** a handle no snapshot issued, **when** it is acted on, **then** the
  action is refused naming the handles that exist.
- **Dependencies:** S-02.01.01. **Size:** M. **Indicator:** wrong-element actions.

#### S-02.01.03 — Ten verbs, real input, no arbitrary code
**As a** security owner, **I want** the action vocabulary closed, **so that** a
prompt injection on any page cannot become arbitrary action in a logged-in session.
- **Given** the vocabulary, **when** it is inspected, **then** no verb accepts
  code, a selector, or a URL the policy has not cleared.
- **Given** a click, **when** it fires, **then** it is a real pointer event and
  not a scripted one.
- **Dependencies:** S-02.01.02. **Size:** M. **Indicator:** injection findings.

#### S-02.01.04 — Per-domain policy, enforced in code
**As an** account owner, **I want** pace and autonomy limits enforced rather than
requested, **so that** the rules do not depend on a model choosing to obey.
- **Given** a session-gated platform, **when** an unattended run targets it,
  **then** it is refused.
- **Given** localhost, a `.internal` host or the cloud metadata address, **when**
  navigation is attempted, **then** it is refused.
- **Dependencies:** S-02.01.03. **Size:** M. **Indicator:** platform warnings received.

#### S-02.01.05 — An append-only work trace
**As an** owner, **I want** an unalterable record of every action, **so that**
"what did it actually do" always has a complete answer.
- **Given** a trace, **when** its interface is inspected, **then** it offers no
  delete, edit or truncate.
- **Given** a process killed mid-write, **when** the trace is reopened, **then**
  every complete step is readable.
- **Dependencies:** S-02.01.01. **Size:** S. **Indicator:** unexplained agent actions.

### F-02.02 — The run loop  *(E-02)*

#### S-02.02.01 — A goal becomes a bounded sequence of actions
**As an** owner, **I want** to give a goal and have the agent work toward it,
**so that** I state outcomes rather than steps.
- **Given** a goal and a step budget, **when** the run exceeds the budget,
  **then** it stops and reports where it got to.
- **Given** every decision, **when** it is made, **then** it goes through the
  egress broker and appears in the trace with its cost.
- **Dependencies:** S-02.01.05, S-03.02.01. **Size:** L. **Indicator:** goals completed unattended.

#### S-02.02.02 — PLAN.md as the single source of truth
**As an** owner, **I want** the plan to be a markdown file, **so that** the model
reads it as memory, the UI renders it as a checklist and I can edit it to steer.
- **Given** a run, **when** it starts, **then** exactly one PLAN.md exists for it.
- **Given** an owner edit to PLAN.md mid-run, **when** the next step is chosen,
  **then** the edit is what the model sees.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** runs steered rather than restarted.

#### S-02.02.03 — Interrupt, steer, resume
**As an** owner, **I want** to cut in mid-run and to resume after a stop,
**so that** a long task is not all-or-nothing.
- **Given** a stopped run, **when** it is resumed, **then** the trace is replayed
  into context and work continues from the last completed step.
- **Dependencies:** S-02.02.02. **Size:** M. **Indicator:** runs abandoned vs resumed.

#### S-02.02.04 — Safety countdowns before consequential actions
**As an** owner, **I want** a visible, cancellable delay before anything that
sends, deletes, spends or publishes, **so that** I am not trained to click through a dialog.
- **Given** a sensitive action, **when** it is reached, **then** it does not fire
  until the countdown elapses and it can be cancelled during it.
- **Dependencies:** S-02.02.01. **Size:** S. **Indicator:** actions cancelled during countdown.

### F-03.01 — Isolation  *(E-03)*

#### S-03.01.01 — A browser box: network yes, host filesystem never
**As an** owner, **I want** the browser to run in a container with no path to my
files, **so that** an agent holding real logins cannot reach anything else.
- **Given** the browser box, **when** it is inspected, **then** no host path is
  mounted and the CRM database is not mounted at all.
- **Given** a domain not on the allow-list, **when** it is requested, **then**
  the request does not leave the box.
- **Dependencies:** S-02.01.04. **Size:** L. **Indicator:** host paths reachable (target: zero).

#### S-03.01.02 — The existing code box keeps its no-network guarantee
**As a** security owner, **I want** the two sandbox profiles kept distinct,
**so that** adding a browser does not weaken the box that runs model-written code.
- **Given** the code sandbox, **when** its flags are inspected, **then**
  `--network=none` is still present.
- **Dependencies:** S-03.01.01. **Size:** S. **Indicator:** sandbox escape findings.

### F-03.02 — Identity and secrets  *(E-03)*

#### S-03.02.01 — Sign in to a platform once, inside the box
**As an** owner, **I want** to log into Instagram, Facebook, YouTube, X, LinkedIn
and TikTok inside the browser box, **so that** the agent can act as me without
ever touching my real browser profile.
- **Given** a platform, **when** I complete its login inside the box, **then**
  the session persists across restarts of the box.
- **Given** my password, **when** login completes, **then** it is present nowhere
  in off_CRM's storage.
- **Dependencies:** S-03.01.01. **Size:** L. **Indicator:** platforms connected per workspace.

#### S-03.02.02 — A vault the model cannot read
**As a** security owner, **I want** session material encrypted per account and
unreachable from any prompt, **so that** one compromise is not all of them.
- **Given** any prompt assembled for any provider, **when** it is inspected,
  **then** it contains no cookie, token or password.
- **Given** two connected platforms, **when** their stored material is inspected,
  **then** they are encrypted under different keys.
- **Given** the master key, **when** its source is inspected, **then** it derives
  from a passphrase or OS keychain and is not a file beside the data.
- **Dependencies:** S-03.02.01. **Size:** L. **Indicator:** secrets in prompts (target: zero).

#### S-03.02.03 — Revoke and forget
**As an** owner, **I want** to disconnect a platform and have its material
destroyed, **so that** leaving is as easy as joining.
- **Given** a connected platform, **when** I disconnect it, **then** its stored
  session is unrecoverable and the trace records the act.
- **Dependencies:** S-03.02.02. **Size:** S. **Indicator:** disconnect requests unfulfilled.

### F-04.01 — The agent team  *(E-04)*

#### S-04.01.01 — Companions: persisted agent profiles
**As an** owner, **I want** named agents with their own instructions, memory
scope and granted tools, **so that** "the one that posts" is a thing that exists
rather than a prompt I retype.
- **Given** a companion, **when** a run starts under it, **then** only its
  granted tools and its memory scope are in play.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** runs started from a companion.

#### S-04.01.02 — Skills: procedures fetched on demand
**As an** owner, **I want** playbooks stored separately from facts, **so that**
a long procedure does not bloat every prompt.
- **Given** a skill, **when** it is not relevant to the run, **then** it is
  absent from the prompt.
- **Dependencies:** S-04.01.01. **Size:** M. **Indicator:** prompt size per run.

#### S-04.01.03 — Sub-agents for context isolation
**As an** owner, **I want** a companion to spawn focused children, **so that**
reading forty profiles does not fill the parent's context with thirty-nine
irrelevant ones.
- **Given** a spawn, **when** depth or fan-out would exceed its bound, **then**
  it is refused.
- **Given** a child, **when** it finishes, **then** the parent receives its
  result and not its transcript.
- **Dependencies:** S-04.01.01. **Size:** L. **Indicator:** parent context size at task end.

#### S-04.01.04 — The five roles, wired to what already exists
**As an** owner, **I want** Scout, Maker, Poster, Analyst and Director to be
companions over the code already built, **so that** the engine gains judgement
without being rewritten.
- **Given** Maker, **when** it runs, **then** it calls the existing assembler and
  director rather than a reimplementation.
- **Given** Director, **when** it allocates work, **then** every downstream act
  still passes the review queue.
- **Dependencies:** S-04.01.03. **Size:** L. **Indicator:** end-to-end runs needing no human step.

### F-05.01 — Intelligence  *(E-05)*

#### S-05.01.01 — A crawler with a frontier, not a loop
**As an** owner, **I want** a politeness-aware frontier with revisit scheduling,
**so that** a fixed crawl budget goes where the change is.
- **Given** a host, **when** it is crawled, **then** its robots.txt and crawl
  delay are honoured.
- **Given** a page that has not changed in months, **when** the scheduler runs,
  **then** it is visited less often than one that changed yesterday.
- **Given** the frontier, **when** it is inspected, **then** it contains no
  session-gated platform.
- **Dependencies:** S-02.01.04. **Size:** L. **Indicator:** useful pages per crawl-hour.

#### S-05.01.02 — Extraction packs as declared data
**As an** owner, **I want** site-shaped extraction to be rows rather than
parsers, **so that** adding a source is configuration.
- **Given** a new source, **when** a pack is added, **then** no code changes.
- **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** sources added per code change.

#### S-05.01.03 — Take a competitor post apart and rebuild the shape
**As an** owner, **I want** a high-performing post reduced to its structure —
shape, pacing, hook, look — **so that** the engine reproduces what works without
reproducing the content.
- **Given** a public post, **when** it is analysed, **then** the output is a
  recipe reference and parameters, never copied media.
- **Given** an analysis, **when** it produces a project, **then** that project
  enters the review queue like any other.
- **Dependencies:** S-05.01.02, S-01.03.02. **Size:** L. **Indicator:** performance of derived pieces.

### F-06.01 — Team and production  *(E-06)*

#### S-06.01.01 — Workspaces with their own keys and their own logins
**As a** team member, **I want** my own provider keys and my own platform
sessions, **so that** my work and my credentials are mine.
- **Given** two workspaces, **when** either reads keys or sessions, **then**
  neither can reach the other's.
- **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** distinct workspaces in weekly use.

#### S-06.01.02 — Three-level permissions
**As an** owner, **I want** a global mode, a per-tool rule and a chat-scoped
override, **so that** trust is granted at the size of the decision.
- **Given** a tool set to `ask`, **when** an agent calls it, **then** the run
  pauses for a decision.
- **Given** a chat-scoped grant, **when** the conversation ends, **then** the
  grant expires.
- **Dependencies:** S-04.01.01. **Size:** M. **Indicator:** blanket-allow rate.

#### S-06.01.03 — Cost estimated before a run and ledgered after
**As an** owner, **I want** to know what a run will cost before it starts,
**so that** an autonomous system does not surprise me.
- **Given** a plan, **when** a run is proposed, **then** an estimate is shown
  before the first action.
- **Given** a finished run, **when** its trace is summed, **then** the total
  matches the provider ledger.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** estimate-to-actual error.

#### S-06.01.04 — Routines that fire agent runs on a schedule or an event
**As an** owner, **I want** scheduled and event-triggered runs, **so that** the
engine works when I am not there.
- **Given** an attended-only domain, **when** a routine targets it, **then** the
  routine is refused at creation, not at fire time.
- **Given** a run that found nothing, **when** it ends, **then** it does not notify.
- **Dependencies:** S-02.02.01, S-02.01.04. **Size:** M. **Indicator:** useful notifications per week.

#### S-06.01.05 — Deployment, monitoring and rollback
**As an** operator, **I want** a deployment path with health, logs and a way
back, **so that** a bad release is a five-minute problem.
- **Given** a release, **when** it fails health checks, **then** the previous
  version is restorable without data loss.
- **Given** any schema change, **when** it ships, **then** a rollback path is
  documented and tested.
- **Dependencies:** S-06.01.01. **Size:** L. **Indicator:** mean time to restore.

### F-06.02 — Non-functional work, with its own IDs  *(E-06)*

#### S-06.02.01 — No secret may enter a model prompt
- **Given** the payload builder, **when** any request is assembled, **then** a
  scan for credential-shaped material passes.
- **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** scanner findings.

#### S-06.02.02 — Every endpoint authorises and validates
- **Given** any endpoint, **when** called without a session, **then** it refuses.
- **Given** any body, **when** it is malformed, **then** the response is a 4xx
  with a message and never a stack trace.
- **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated reachability.

#### S-06.02.03 — Cost and latency budgets per run
- **Given** a run, **when** it exceeds its budget, **then** it stops and says so.
- **Dependencies:** S-06.01.03. **Size:** S. **Indicator:** budget overruns.

#### S-06.02.04 — Data deletion and subject access
- **Given** a request to delete a person's data, **when** it is executed, **then**
  it is removed from every store including traces and crawl caches.
- **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** deletion requests unfulfilled.

#### S-06.02.05 — The UI is usable by keyboard and screen reader
- **Given** any interactive screen, **when** navigated by keyboard alone, **then**
  every action is reachable and focus is visible.
- **Dependencies:** none. **Size:** M. **Indicator:** accessibility audit findings.

#### S-06.02.06 — The delivery process is verifiable by the owner
**As an** owner, **I want** a script that independently checks the board against
the repository, **so that** "this is done" is a claim I can test rather than
trust.
- **Given** a DONE item whose named test does not exist, **when** the verifier
  runs, **then** it exits non-zero.
- **Given** an orphan requirement, **when** the verifier runs, **then** it exits
  non-zero.
- **Dependencies:** none. **Size:** M. **Indicator:** unverifiable DONE claims.

---

## 3. Requirements → backlog coverage

Every requirement extracted from the conversation. **Orphans must be zero.**

| Req | Requirement | Backlog IDs |
|---|---|---|
| R-01 | A timeline whose document cannot hold an invalid edit | S-01.01.01 |
| R-02 | Preview and export resolve identically | S-01.01.02 |
| R-03 | Audio inside the exported file | S-01.02.01 |
| R-04 | Imported footage drawn on the canvas | S-01.02.01 |
| R-05 | Speed curves, freeze and reverse | S-01.02.02 |
| R-06 | Filters and effects as data with a strength slider | S-01.02.03 |
| R-07 | Material plus a recipe becomes a finished timeline | S-01.03.01 |
| R-08 | A topic becomes a finished project | S-01.03.02 |
| R-09 | Push / ignore / edit before anything is published | S-01.04.01 |
| R-10 | The owner's daily posting cap is never crossed | S-01.04.02 |
| R-11 | The engine recommends a rate and waits | S-01.04.02 |
| R-12 | Drive the owner's real logged-in browser, no Chromium fork | S-02.01.01 |
| R-13 | Perceive pages by meaning, with stable handles | S-02.01.02 |
| R-14 | A closed action vocabulary with no arbitrary code | S-02.01.03 |
| R-15 | Per-domain pace, attended-only and refusal rules | S-02.01.04 |
| R-16 | An append-only work trace | S-02.01.05 |
| R-17 | An agent run loop: perceive, decide, act, record | S-02.02.01 |
| R-18 | PLAN.md as the single source of truth | S-02.02.02 |
| R-19 | Interrupt, steer and resume a run | S-02.02.03 |
| R-20 | Safety countdowns before consequential actions | S-02.02.04 |
| R-21 | Everything the agents do runs in a sandbox | S-03.01.01, S-03.01.02 |
| R-22 | Agents can never reach local files | S-03.01.01 |
| R-23 | The browser box has network, restricted to an allow-list | S-03.01.01 |
| R-24 | The code sandbox keeps `--network=none` | S-03.01.02 |
| R-25 | Log into Instagram, Facebook, YouTube, X, LinkedIn, TikTok | S-03.02.01 |
| R-26 | Passwords are never stored anywhere | S-03.02.01 |
| R-27 | Session material encrypted, one key per account | S-03.02.02 |
| R-28 | The master key derives from a passphrase or keychain | S-03.02.02 |
| R-29 | No model ever sees a credential | S-03.02.02, S-06.02.01 |
| R-30 | Disconnecting a platform destroys its session | S-03.02.03 |
| R-31 | Companions: persisted agent profiles | S-04.01.01 |
| R-32 | Skills: procedures separate from memory facts | S-04.01.02 |
| R-33 | Sub-agents for context isolation | S-04.01.03 |
| R-34 | Scout, Maker, Poster, Analyst, Director | S-04.01.04 |
| R-35 | Agents share one memory, tool set and browser | S-04.01.01, S-04.01.04 |
| R-36 | A crawler with a politeness-aware frontier | S-05.01.01 |
| R-37 | Revisit scheduling driven by observed change | S-05.01.01 |
| R-38 | Extraction as declared packs, not parsers | S-05.01.02 |
| R-39 | Competitor posts reduced to structure and rebuilt | S-05.01.03 |
| R-40 | The crawler never targets session-gated platforms | S-05.01.01, S-02.01.04 |
| R-41 | Multi-user workspaces with their own provider keys | S-06.01.01 |
| R-42 | Each user has their own platform logins | S-06.01.01, S-03.02.01 |
| R-43 | Three-level permissions with a chat-scoped override | S-06.01.02 |
| R-44 | Cost estimated before a run and ledgered after | S-06.01.03 |
| R-45 | Routines fire agent runs on a schedule or an event | S-06.01.04 |
| R-46 | Quiet runs do not notify | S-06.01.04 |
| R-47 | Deployment, monitoring and a tested rollback | S-06.01.05 |
| R-48 | Every endpoint authorises and validates its input | S-06.02.02 |
| R-49 | Cost and latency budgets enforced per run | S-06.02.03 |
| R-50 | Data deletion reaches every store | S-06.02.04 |
| R-51 | The UI is keyboard and screen-reader usable | S-06.02.05 |
| R-52 | The board is verifiable independently of the builder | S-06.02.06 |
| R-53 | MCP client, to inherit third-party tools | S-07.01.01 |
| R-54 | Native OAuth integrations for the few worth doing | S-07.01.02 |
| R-55 | Meeting transcription without a bot in the call | S-07.01.03 |
| R-56 | Reports and artifacts: decks, sheets, PDF | S-07.01.04 |

### F-07.01 — Integrations and artifacts  *(E-04)*

#### S-07.01.01 — An MCP client
**As an** owner, **I want** off_CRM to speak MCP over HTTP/SSE and stdio,
**so that** it inherits tools other people have already built.
- **Given** a declared MCP server, **when** it is connected, **then** its tools
  appear in the same registry and obey the same permission rules.
- **Given** a tool the owner has not granted, **when** an agent names it, **then**
  the call is refused.
- **Dependencies:** S-06.01.02. **Size:** L. **Indicator:** tools available per workspace.

#### S-07.01.02 — Native OAuth integrations
**As an** owner, **I want** typed tools for Gmail, Sheets, Slack and the CRMs,
**so that** the common paths are fast and structured rather than driven by clicking.
- **Given** an OAuth grant, **when** it is stored, **then** it is held under the
  same vault rules as a platform session.
- **Dependencies:** S-03.02.02, S-07.01.01. **Size:** L. **Indicator:** browser fallbacks avoided.

#### S-07.01.03 — Meeting transcription with no bot in the call
**As an** owner, **I want** microphone and system audio captured locally,
**so that** meetings become notes without a third party joining.
- **Given** a capture, **when** it completes, **then** audio never leaves the
  machine except through the declared transcription provider.
- **Dependencies:** S-03.01.01. **Size:** L. **Indicator:** meetings captured per week.

#### S-07.01.04 — Reports and artifacts
**As an** owner, **I want** gathered data to become a deck, a sheet or a PDF,
**so that** research ends in something I can send.
- **Given** a run's findings, **when** a report is generated, **then** every
  claim in it links to a trace step.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** reports produced per research run.

---

## 4. Out of scope — decided, not forgotten

Silence must never be mistakable for scope.

| Not building | Why |
|---|---|
| A Chromium fork | A C++ patch set against upstream forever, ~100GB checkouts, code signing, an update channel, and responsibility for a browser people type passwords into. CDP attach buys the session, which is what the fork was for. |
| Mass automated scraping of LinkedIn / Instagram | Breaches their terms explicitly; the penalty falls on the owner's account, not on us; and for EU/UK subjects it is personal data with no lawful basis. Attended, human-paced access to the owner's own session is built instead. |
| Stealth, CAPTCHA solving, anti-bot evasion | The entire category exists to defeat a site's stated wishes. It also breaks weekly. |
| Storing platform passwords | Not encrypted, not hashed, not at all. The owner types them into the browser inside the box. |
| Velocity forecasting and story points | No throughput history exists, so any figure would be invented precision. The evidence ledger replaces the estimate. |
| Buying followers, engagement pods, sock puppets | Fraud against the platform and against the owner's own metrics. |
| A mobile app | The browser box and the editor both assume a desktop. |
| Multi-tenant SaaS hosting | The product is local-first by design; hosting other people's session cookies is a different business with a different threat model. |

---

## 5. Definition of the increment

One increment = one vertical slice a person can use end to end. Not "the backend
for X". The next increment is chosen by the owner from `READY`, and only when
`IN_PROGRESS` is empty.
