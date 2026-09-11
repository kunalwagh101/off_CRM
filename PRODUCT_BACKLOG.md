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

### E-07 — Permitted email reaches recipients without losing operational control
**Value hypothesis:** a company can send permission-based email at useful volume
without one crash, complaint or bad list damaging every future message.
**Leading indicator:** accepted mail with low permanent-bounce and complaint rates,
with zero sends to suppressed recipients.

### E-11 — The agent browses the open web alone and comes back with facts you can trust
**Owner:** the product. **Value hypothesis:** every other capability in off_CRM
is limited by what somebody typed into it. An agent that can go and *find out*
removes that ceiling — and the thing that makes it worth having is not that it
browses, it is that what it returns can be **checked**. An autonomous agent
whose output cannot be audited is a rumour generator.
**Leading indicator:** facts returned per run that survive their own provenance
check, and runs completed without a human touching the browser.

**Why this is a new epic rather than more of E-02.** E-02 delivered the hands
and the loop, and both are shipped and tested. What is missing is everything
between "it can click" and "you can leave it running": recovery, stall
detection, a money ceiling, structured answers, provenance, and knowing when to
stop and ask. Those are not refinements of the loop — they are the difference
between a demo and a system, and they carry their own risk, so they carry their
own IDs.

*(Note on numbering: E-08, E-09 and E-10 were proposed in `FEATURE_TREE.md` to
govern the pre-process CRM code and have **not been approved by the owner**.
They are deliberately skipped here so the numbers cannot collide whichever way
that decision goes.)*

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

### F-01.05 — Publishing to a real platform  *(E-01)*

> **Found during review on 2026-08-25.** The product exists to put content in
> front of an audience, and nothing in this backlog covered the adapter that
> actually does it — the engine publishes to a local outbox only. Decomposing
> from the conversation rather than from the product's purpose is how that
> slipped through. New IDs rather than a silent addition.

#### S-01.05.01 — Publish to YouTube through the official API
**As a** content owner, **I want** an approved render uploaded to YouTube,
**so that** the engine's output reaches an audience instead of a folder.
- **Given** a pushed render, **when** a scheduled post comes due, **then** it is
  uploaded via `videos.insert` and the returned video id is stored on the post.
- **Given** an upload that fails, **when** the round completes, **then** the post
  is marked failed with the API's own reason and nothing is silently retried.
- **Given** the daily quota, **when** it would be exceeded, **then** the upload
  is deferred rather than attempted and rejected.
- **Dependencies:** S-01.04.02. **Size:** L. **Indicator:** posts published through an official API.

#### S-01.05.02 — One adapter contract for the remaining platforms
**As a** content owner, **I want** Instagram, Facebook, TikTok, LinkedIn and X
behind the same interface as YouTube, **so that** a platform becoming available
is a configuration change rather than a rewrite.
- **Given** a platform whose app review has not passed, **when** a post targets
  it, **then** it is refused at scheduling with what is still needed.
- **Given** a platform that becomes available, **when** its adapter is enabled,
  **then** no code outside that adapter changes.
- **Dependencies:** S-01.05.01. **Size:** L. **Indicator:** platforms reachable per workspace.

#### S-01.05.03 — Read real engagement back from the platform
**As a** content owner, **I want** views and likes fetched from the platform
itself, **so that** the pacing controller steers on measured reality rather than
on numbers somebody typed.
- **Given** a published post, **when** metrics are refreshed, **then** the
  reading is stored as a snapshot and totals use the newest per post.
- **Given** a platform with no metrics API, **when** a refresh runs, **then** it
  reports that rather than reporting zero.
- **Dependencies:** S-01.05.01. **Size:** M. **Indicator:** share of posts with measured engagement.

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

#### S-03.02.04 — Several accounts per platform, each with its own budget
**As an** owner, **I want** to connect more than one account on a platform and
have off_CRM know each one's limits, **so that** running ten accounts does not
get ten accounts banned.
- **Given** two accounts on one platform, **when** both are connected, **then**
  each has its own record and its own action budget, and spending one does not
  spend the other.
- **Given** an account that has reached its daily budget, **when** the agent
  attempts an action that touches the platform, **then** the action is refused
  and the refusal says when the budget resets.
- **Given** an action that only observes (`read`, `screenshot`, `wait_for`),
  **when** it runs, **then** it costs no budget — looking is not acting.
- **Dependencies:** S-03.02.01. **Size:** M. **Indicator:** accounts connected
  per workspace without a suspension.

#### S-03.02.05 — A platform is a row, not a code change
**As an** owner, **I want** to add Reddit, or any of a hundred other sites, by
declaring it, **so that** coverage is not limited to the six platforms somebody
hardcoded.
- **Given** a declared platform with its sign-in signals and pace, **when** it is
  added to the registry, **then** sign-in, connection state and budget all work
  with no code change.
- **Given** a declared platform missing a required field, **when** it is loaded,
  **then** it is refused by name at load time rather than failing mid-run.
- **Dependencies:** S-03.02.04. **Size:** M. **Indicator:** platforms in use
  beyond the built-in six.

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

#### S-06.02.07 — An answered question stops blocking
**As an** owner, **I want** a question I have decided to stop holding work back,
**so that** recording a decision is what unblocks the board rather than deleting
the question and losing why it was asked.
- **Given** a question marked answered, **when** an item citing it enters READY,
  **then** the verifier passes.
- **Given** a question with no answer, **when** an item citing it enters READY,
  **then** the verifier still fails.
- **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** decisions recorded vs questions deleted.

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
| R-72 | Several accounts on one platform, each independently recorded | S-03.02.04 |
| R-73 | Each account has its own action budget, enforced before the action | S-03.02.04 |
| R-74 | Observing costs no budget; only touching the platform does | S-03.02.04 |
| R-75 | A new platform is a declared row, not a code change | S-03.02.05 |
| R-76 | A failed action is recovered from, and repeated failure stops the run | S-11.01.01 |
| R-77 | A looping or stalled run is detected and stopped | S-11.01.02 |
| R-78 | A run resumes after the process dies, with its facts intact | S-11.01.03 |
| R-79 | A run has a spend ceiling and a pre-run estimate | S-11.01.04 |
| R-80 | A run returns records against a declared schema, not prose | S-11.02.01 |
| R-81 | Every returned fact carries URL, time, step and screenshot | S-11.02.02 |
| R-82 | A claim the cited page does not support is dropped, not returned | S-11.02.03 |
| R-83 | A page is never fetched twice in one run | S-11.02.04 |
| R-84 | A CAPTCHA, login wall or 2FA pauses the run and asks the owner | S-11.03.01 |
| R-85 | Prompt injection in page text is detected and recorded | S-11.03.02 |
| R-86 | Every run produces an auditable claim-to-evidence report | S-11.04.01 |
| R-87 | A run's progress is visible while it runs | S-11.04.02 |
| R-88 | Concurrent runs share pace and account budget, not multiply them | S-11.05.01 |
| R-89 | A resumed run never repeats a consequential action | S-11.05.02 |
| R-95 | Enter goes through the same consequential gate as a click | S-11.03.03 |
| R-96 | The verifier checks READY, not only DONE | S-06.02.11 |
| R-97 | Every commit the board names is on the branch | S-06.02.12 |
| R-98 | Every defect and design call is written down in one place | S-06.02.13 |
| R-90 | Every evidence command uses one runner | S-06.02.08 |
| R-91 | Every shared-connection write is serialised by one guard | S-06.02.09 |
| R-92 | Authentication is required on every host, loopback included | S-06.02.10 |
| R-93 | A local install provisions its own token rather than failing | S-06.02.10 |
| R-94 | Requests for a host this server does not answer to are refused | S-06.02.10 |
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
| R-57 | A recorded decision unblocks the board; a deleted question does not | S-06.02.07 |
| R-58 | Approved renders are published to YouTube through its official API | S-01.05.01 |
| R-59 | Instagram, Facebook, TikTok, LinkedIn and X behind one adapter contract | S-01.05.02 |
| R-60 | Engagement is read back from the platform, not typed in | S-01.05.03 |
| R-61 | Permission marketing and transactional mail require the correct recorded basis | S-08.01.01 |
| R-62 | Global suppression blocks every send path and cancels queued work | S-08.01.01 |
| R-63 | Non-transactional mail has a signed one-click unsubscribe path | S-08.01.05 |
| R-64 | Bulk mail is an immutable durable job claimed by only one worker | S-08.01.02 |
| R-65 | Ambiguous delivery is quarantined and never retried automatically | S-08.01.02 |
| R-66 | Replies, send windows, daily caps and rate state stop or defer before a provider call | S-08.01.02 |
| R-67 | A bulk sending identity has fresh SPF, DKIM, DMARC, alignment and SES evidence | S-08.01.03 |
| R-68 | SES receives raw MIME with the required stream, feedback and unsubscribe metadata | S-08.01.03 |
| R-69 | Signed, idempotent provider feedback turns complaints and hard bounces into suppression | S-08.01.04 |
| R-70 | Delivery health thresholds pause unsafe campaigns and require an explicit resume | S-08.01.04 |
| R-71 | Operators can inspect preflight and health, and live SES queueing requires exact confirmation | S-08.01.05 |

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

### F-08.01 — Protected bulk email delivery  *(E-07)*

*Retrospective change-control entry, 2026-08-27.* The implementation first
arrived in `d96ea9d` without backlog IDs. These stories certify the current
repository state; they do not pretend the original implementation followed the
pull-before-code process.

#### S-08.01.01 — Permission and suppression fail closed
**As an** operator, **I want** permission and suppression decided before any
provider call, **so that** scale cannot turn one bad record into unauthorised mail.
- **Given** permission marketing without an active recorded grant, **when**
  preflight runs, **then** the recipient is blocked before queueing.
- **Given** an address that denied permission or is globally suppressed, **when**
  either the direct or durable path tries to send, **then** it refuses and queued
  work is cancelled.
- **Given** a transactional lane, **when** its permission is checked, **then**
  only a recorded customer, contract or service-request relationship passes.
- **Dependencies:** none. **Size:** M. **Indicator:** provider calls to ineligible recipients.

#### S-08.01.02 — Durable jobs survive crashes without duplicate sends
**As an** operator, **I want** each bulk email to be durable and claimed once,
**so that** a restart or second worker cannot silently send it twice.
- **Given** an approved due draft, **when** it is queued, **then** an immutable
  payload snapshot is stored and only one worker can claim it.
- **Given** an ambiguous provider result or an expired claim without a recorded
  message, **when** recovery runs, **then** the job becomes `delivery_unknown`
  and is never retried automatically.
- **Given** a reply, cancellation, closed send window, daily cap or lane delay,
  **when** a worker reaches the job, **then** it is cancelled or deferred before
  the provider call and no false provider attempt is consumed.
- **Dependencies:** S-08.01.01. **Size:** L. **Indicator:** duplicate-send incidents.

#### S-08.01.03 — Authenticated SES lanes carry bulk mail
**As an** operator, **I want** each bulk stream tied to an authenticated SES
identity, **so that** high volume uses evidence-backed infrastructure rather
than a personal mailbox.
- **Given** a sending identity, **when** it is assigned to a campaign, **then**
  its provider and stream must match and bulk lanes use isolated subdomains.
- **Given** a permission-marketing send, **when** authentication evidence is
  missing, failing or older than seven days, **then** SPF, DKIM, DMARC,
  alignment or SES verification blocks it.
- **Given** an allowed SES job, **when** it is submitted, **then** raw MIME
  carries the correct stream tags, feedback configuration and unsubscribe
  headers where required.
- **Dependencies:** S-08.01.01. **Size:** L. **Indicator:** authenticated accepted sends.

#### S-08.01.04 — Provider feedback stops unhealthy sending
**As an** operator, **I want** delivery feedback to change future eligibility,
**so that** complaints and permanent bounces cannot be ignored.
- **Given** an SNS envelope, **when** it reaches the public feedback endpoint,
  **then** its certificate source, signature and expected topic are verified
  before any database mutation.
- **Given** a duplicate hard-bounce or complaint event, **when** it is processed,
  **then** the event is idempotent and the recipient is globally suppressed once.
- **Given** health metrics beyond configured thresholds, **when** feedback is
  aggregated, **then** the campaign pauses automatically and only an explicit
  resume clears the pause.
- **Dependencies:** S-08.01.02, S-08.01.03. **Size:** L. **Indicator:** sends after a complaint.

#### S-08.01.05 — Operators control delivery without hidden live sends
**As an** operator, **I want** one visible control surface for preflight, health
and queueing, **so that** a live bulk send cannot happen by accident.
- **Given** an authenticated operator, **when** the delivery API or dashboard is
  opened, **then** identities, settings, preflight, permissions, suppressions,
  jobs and health are visible and editable through guarded actions.
- **Given** a recipient using the public unsubscribe route, **when** the signed
  token is valid, **then** the action works without login; an invalid token is refused.
- **Given** a live SES queue request, **when** the exact confirmation phrase is
  absent, **then** no job is created and the dashboard keeps the safety controls visible.
- **Dependencies:** S-08.01.01, S-08.01.02, S-08.01.03, S-08.01.04. **Size:** M.
  **Indicator:** live queue requests without explicit confirmation.

---

### F-11.01 — The run survives contact with the real web  *(E-11)*

Real pages 500, rate-limit, redirect to a consent wall and move the button. A
loop that stops at the first of those is a demo.

#### S-11.01.01 — A failed action is recovered from, not repeated
**As an** owner, **I want** the agent to try a different approach when an action
fails, **so that** one stale handle does not end a twenty-minute run.
- **Given** an action that raises `ActionRefused`, **when** it fails, **then**
  the agent re-perceives and is told what failed and why, and the same
  action with the same arguments is never retried more than once.
- **Given** three consecutive failed actions, **when** the third fails, **then**
  the run stops with `status=stuck` rather than continuing to burn budget.
- **Given** a transient failure, **when** it happens, **then** it is retried
  with backoff and the retry is recorded in the trace as a retry, not as a fresh
  attempt. **(done)**
- **Scope corrected during the build:** the original wording said "navigation
  timeout, 5xx". **HTTP status is not observable through the ten verbs** — a
  server returning 500 still sends a page and the browser renders it, so `goto`
  succeeds. Retrying on 5xx would have been a comment describing something the
  code cannot see. Transient therefore means timeout-shaped, and a status-aware
  retry needs its own ID if it is ever wanted.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** runs ending `stuck`
  vs `done`.

#### S-11.01.02 — A run that stops making progress is stopped
**As an** owner, **I want** a run that is going in circles to be caught,
**so that** a step budget is not spent on the same two pages forty times.
- **Given** the agent returns to a URL it has already acted on twice with no new
  facts recorded, **when** the third visit is decided, **then** the run stops
  with `status=looping` and the trace names the cycle.
- **Given** ten consecutive steps that produce nothing new, **when** the tenth
  completes, **then** the run stops with `status=stalled`. **(done)**
- **Given** a run that is progressing, **when** these checks run, **then** they
  never stop it — a false positive here is worse than a wasted step. **(done)**
- **Scope clarified during the build:** "no new fact and no new URL" was widened
  to "no new fact, no new **unvisited** page, and no action this run had not
  already performed". Two corrections, both forced by the third criterion.
  *Unvisited* rather than *different*, because bouncing between two pages is a
  different URL every step and is the exact cycle this story exists to catch.
  And the action clause, because filling a form is a dozen successful steps on
  one page with no fact and no navigation — stopping that is the false positive
  the third criterion forbids.
- **Dependencies:** S-11.01.01. **Size:** M. **Indicator:** steps per fact returned.

#### S-11.01.03 — A run survives the process dying
**As an** owner, **I want** a killed run to resume where it stopped,
**so that** a deploy or a crash does not throw away forty steps of work.
- **Given** a run interrupted at step N, **when** it is resumed, **then** it
  continues from step N+1 with the facts already gathered intact. **(done)**
- **Given** a resumed run, **when** it finishes, **then** the trace is one
  continuous record, not two, and the resume point is marked in it. **(done)**
- **Given** a run that already ended, **when** a resume is attempted, **then** it
  is refused — a second ending would make the trace say two contradictory things
  about how the run turned out. **(added during the build)**
- **Given** a fact whose evidence artefact is gone, **when** the trace is
  replayed, **then** the fact is dropped rather than rebuilt unsourced. Losing
  one is recoverable; inventing one is what `S-11.02.02` exists to prevent.
  **(added during the build)**
- **Dependencies:** S-02.02.01, S-02.01.05. **Size:** M. **Indicator:** runs
  resumed vs restarted.

#### S-11.01.04 — A run has a money ceiling, not only a step ceiling
**As an** owner, **I want** to cap what a run may spend before it starts,
**so that** an agent left running overnight cannot cost more than I agreed.
- **Given** a run with a spend ceiling, **when** the next decision would cross
  it, **then** the decision is not made and the run stops with `status=over_budget`.
- **Given** a run, **when** it is planned, **then** an estimate is produced
  before the first step and the owner sees it.
- **Given** a finished run, **when** it is inspected, **then** actual spend per
  step is in the trace, not a total nobody can decompose.
- **Dependencies:** S-02.02.01, S-06.01.03. **Size:** M. **Indicator:** runs
  stopped by ceiling; estimate vs actual error.

### F-11.02 — What it brings back is data, not prose  *(E-11)*

**This is the centre of the epic.** `S-02.02.01` returns `result: str` — a
sentence. A sentence cannot be put in a CRM, checked, or diffed against the next
run. Everything here exists to replace that string with something a machine and
a person can both audit.

#### S-11.02.01 — A run declares the shape of its answer and is held to it
**As an** owner, **I want** to say what fields I want back, **so that** a run
returns records rather than a paragraph I have to re-read.
- **Given** a goal with a declared field schema, **when** the run finishes,
  **then** the result validates against that schema or the run reports
  `status=incomplete` naming the fields it could not fill.
- **Given** a model that returns a field not in the schema, **when** the result
  is assembled, **then** the extra field is dropped and the drop is recorded.
- **Given** no schema, **when** a run finishes, **then** it still returns the
  free-text result `S-02.02.01` returns today — the old behaviour is not removed.
- **Dependencies:** S-02.02.01. **Size:** L. **Indicator:** runs returning a
  valid record vs prose.

#### S-11.02.02 — Every fact carries where it came from
**As an** owner, **I want** each returned field to name its source,
**so that** I can check a claim without re-running anything.
- **Given** a returned field, **when** it is inspected, **then** it carries the
  URL, the UTC timestamp, the trace step id and the screenshot filename of the
  page it was read from.
- **Given** a field with no source, **when** the result is assembled, **then**
  it is refused rather than returned unsourced.
- **Dependencies:** S-11.02.01, S-02.01.05. **Size:** M. **Indicator:** share of
  returned fields with resolvable provenance — target 100%.

#### S-11.02.03 — A claim the page does not support is refused
**As an** owner, **I want** a fact checked against the page it allegedly came
from, **so that** a confident model cannot invent a phone number.
- **Given** a returned field, **when** it is verified, **then** its value must
  appear in the captured text of the cited page, normalised for whitespace and
  case, or the field is dropped and the drop is reported.
- **Given** a field that is a legitimate derivation (a count, a summary),
  **when** it is returned, **then** it is labelled `derived` and its inputs are
  each individually sourced.
- **Given** a page whose text was truncated by `MAX_READ_CHARS`, **when** a
  claim cannot be found in it, **then** the failure says the text was truncated
  rather than asserting the claim was invented.
- **Dependencies:** S-11.02.02. **Size:** L. **Indicator:** claims dropped by
  verification per hundred returned. **This is the story that makes the epic's
  value hypothesis true or false.**

#### S-11.02.04 — The same page is never read twice in one run
**As an** owner, **I want** the agent to remember what it has read,
**so that** the budget goes on new pages.
- **Given** a URL already read in this run, **when** the agent decides to read
  it again, **then** the stored capture is returned and the page is not asked
  again. **(done)**
- **Given** two URLs that differ only by tracking parameters, **when** they are
  compared, **then** they are treated as the same page. **(done)**
- **Given** a page that changed under an unchanged URL, **when** it is read
  again, **then** the memo is not used — added during the build, because a
  stale capture is worse than a second read. **(done)**
- **Dependencies:** S-02.02.01. **Size:** S. **Indicator:** duplicate fetches
  per run — target zero.

### F-11.03 — It knows when to stop and ask  *(E-11)*

#### S-11.03.01 — A wall the agent must not climb pauses the run and asks
**As an** owner, **I want** a CAPTCHA, a login wall or a 2FA prompt to reach me,
**so that** the agent neither gives up silently nor tries to defeat it.
- **Given** a page carrying a CAPTCHA, a sign-in form or a 2FA challenge,
  **when** it is perceived, **then** the run pauses with `status=needs_human`,
  names what it found, and keeps the browser open at that page.
- **Given** a paused run, **when** the owner completes the challenge and
  resumes, **then** the run continues from the same step.
- **Given** any of these, **when** they are encountered, **then** off_CRM
  **never** attempts to solve, evade or fingerprint around them. Recorded as a
  decision in `RETRO.md` 2026-09-06; see OUT OF SCOPE below.
- **Stated during the build:** this detector is allowed to **stop a run**, which
  `injection.py` is explicitly not — so the trade was re-argued rather than
  inherited. It comes out differently because the costs are opposite: a wrong
  injection match costs one line in a trace, a wrong match here costs the owner
  a glance. What makes that safe is that pausing is cheap and recoverable — the
  check runs *before* the model is asked anything, so no budget is spent, and
  the browser is left on the page. Where the two errors are close it leans
  towards asking, because a false negative costs a whole run spent against a
  locked door.
- **Stated during the build:** the pause is not in the set `resume()` treats as
  final, and `human_gate` still is. They are opposite situations — a wall means
  a person must act before the run *can* continue; a human gate means a person
  must decide whether it should happen *at all*, which is not a thing you resume
  into.
- **Known limits, deliberate:** a "change password" settings page has a password
  field and will pause a run that lands on one — accepted, because the cost is a
  pause the owner resumes from. A password field with no accessible name is
  missed; Chrome does not expose password-ness in the accessibility tree, on
  purpose, so the field is found by its label. The challenge phrases are
  English.
- **Dependencies:** S-11.01.03. **Size:** M. **Indicator:** runs resumed after
  a human unblock.

#### S-11.03.02 — A page that tries to give orders is reported, not obeyed
**As a** security owner, **I want** prompt injection detected and surfaced,
**so that** an attack on the agent is visible rather than silent.
- **Given** page text instructing the agent to ignore instructions, exfiltrate,
  change goal or call a tool, **when** it is perceived, **then** the step is
  flagged `injection_suspected` in the trace with the offending text quoted.
- **Given** such a page, **when** the next decision is made, **then** the run
  continues under the owner's original goal — detection changes the record, not
  the behaviour, because behaviour is already contained by the closed
  vocabulary. **(done)**
- **Stated during the build:** the quote lives in the step's capture artefact,
  not in `detail`. Page text does not belong in `trace.jsonl` — the rule the
  finding steps follow and that several tests defend — so the detail names which
  rules matched and the artefact holds the words.
- **Known limit, deliberate:** this reports *injection-shaped text*, not proven
  malice. A page explaining prompt injection to humans contains the text and
  will match. Because nothing is blocked, a wrong match costs one line in a
  trace, so the patterns are tuned to catch a rephrasing rather than to avoid
  every false positive. **This module must never be given the power to stop
  something without that trade being re-argued.**
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** injection attempts
  seen per thousand pages.

#### S-11.03.03 — Enter is gated like the button beside it
**As a** security owner, **I want** `press` to go through the same
consequential-action check as `click`, **so that** the human gate cannot be
stepped around by pressing Enter instead of clicking Send.
- **Given** a page where clicking "Send" needs confirmation, **when** the agent
  presses Enter in the same form, **then** it needs confirmation too.
- **Given** a key that cannot submit anything, **when** it is pressed, **then**
  nothing new is asked of the owner.
- **Dependencies:** S-02.02.04. **Size:** M. **Indicator:** consequential
  actions reaching the world without a gate — target zero.
- **Why:** found while building `S-11.05.02` on 2026-09-10 and **verified**:
  `check_action` is called exactly once in `browser/page.py`, inside `click`.
  `press` calls it zero times. Enter in a form is a submit, so the gate that
  stops the agent clicking Send does not stop it sending. Filed rather than
  fixed in flight because the fix belongs with the human-gate story, and
  because a gate that asks about every keystroke would be worse than none.

### F-11.04 — You can watch it, steer it, and prove what it did  *(E-11)*

#### S-11.04.01 — A run report a person can audit
**As an** owner, **I want** one page per run showing every claim beside its
evidence, **so that** trusting the output is a decision I make from evidence.
- **Given** a finished run, **when** its report is opened, **then** every
  returned field appears with its source URL, timestamp and screenshot, and
  every step appears in order with its cost.
- **Given** a run that failed, **when** its report is opened, **then** it shows
  where and why, not a blank page. **(done)**
- **Added during the build:** the report renders text an attacker wrote — every
  quote came off a web page — so nothing page-derived may become live markup,
  and a screenshot filename that is not local to the run directory is dropped
  rather than followed. **(done)**
- **Added during the build:** a report that cannot be written never costs the
  owner the run's result; the failure is recorded and the outcome returned.
  **(done)**
- **Dependencies:** S-11.02.02. **Size:** M. **Indicator:** reports opened per run.

#### S-11.04.02 — Progress is visible while it happens
**As an** owner, **I want** to watch a run without tailing a log,
**so that** I can stop something going wrong at step 4 instead of step 40.
- **Given** a running agent, **when** the owner watches, **then** each step
  appears as it completes with its action, URL and running cost.
- **Dependencies:** S-11.04.01. **Size:** M. **Indicator:** runs stopped early
  by a watching owner.

### F-11.05 — Many runs at once, without hurting anything  *(E-11)*

#### S-11.05.01 — Concurrent runs share one browser safely
**As an** owner, **I want** several runs at once, **so that** throughput is not
one page at a time.
- **Given** two runs on the same browser, **when** both act, **then** each has
  its own tab, its own trace and its own snapshot, and neither can resolve a
  handle from the other's page.
- **Given** N concurrent runs, **when** they act on one host, **then** the
  per-host pace floor is respected **across** them, not per run.
- **Given** N concurrent runs on one account, **when** they act, **then** they
  draw on one budget, not N.
- **Dependencies:** S-03.02.04. **Size:** L. **Indicator:** concurrent runs
  without a pace violation.

#### S-11.05.02 — Re-running does not duplicate what it already did
**As an** owner, **I want** a resumed or repeated run to be safe,
**so that** a retry cannot send the same message twice.
- **Given** a consequential action already recorded in the trace, **when** a
  resumed run reaches the same step, **then** it is not performed again.
  **(done)**
- **Scope stated during the build:** the guard covers `click` and `press` — the
  two verbs that can send without the URL changing — and **deliberately not
  `goto`**, because navigating is how a resumed run gets back to where it was
  working and blocking a repeat would make resuming useless. The cost is that a
  URL whose GET has a side effect is not protected here.
- **Dependencies:** S-11.01.03. **Size:** M. **Indicator:** duplicate side
  effects — target zero.

### F-11.06 — Process corrections  *(E-06)*

#### S-06.02.10 — The local API is not open to whatever can reach the port
**As an** owner, **I want** authentication and a host allowlist on every host
including loopback, **so that** another process on my machine, or a web page
that can rebind a name to 127.0.0.1, cannot read my CRM.
- **Given** no token and no demo login, **when** the app is constructed, **then**
  it refuses to start and says how to fix it. **(done)**
- **Given** a local install that has never been configured, **when** it starts
  through `run_offsetx_web.py`, **then** a token is generated at `0600`, printed
  once, and stable across restarts. **(done)**
- **Given** a request whose `Host` is not one this server answers to, **when** it
  arrives, **then** it is refused with 421 before any other check, including the
  public-path exemption. **(done)**
- **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated 200s on
  `/api/` — target zero.

#### S-06.02.09 — Every database write goes through one guard
**As an** owner, **I want** all shared-connection access serialised, **so that**
two requests cannot corrupt each other's writes.
- **Given** concurrent transactions on `OutreachStore`, **when** they run,
  **then** no write is lost and no transaction error is raised. **(fixed
  2026-09-08)**
- **Given** a bare `store.connection.execute(...)` outside a transaction,
  **when** another thread holds an open transaction, **then** it does not read
  uncommitted rows or get committed by that transaction. **(fixed 2026-09-09)**
- **Given** a long-lived connection assigned anywhere in `outreach/`, **when**
  the package is parsed, **then** it is wrapped by `GuardedConnection`.
  **(fixed 2026-09-09)**
- **Dependencies:** none. **Size:** M. **Indicator:** unguarded `.execute(` call
  sites outside `transaction()` — target zero.
- **Why:** the audit fixed the transaction race with a lock, which removes the
  proven data loss. It does not stop a bare `.execute` landing inside another
  thread's open transaction. `db/connection.py` already routes every method
  through its lock; this module has ~300 call sites that do not.

#### S-06.02.11 — The verifier catches a stale READY column
**As an** owner, **I want** `scripts/verify_board.py` to check readiness the way
it already checks DONE, **so that** work is not sitting in BACKLOG because a
manual step nobody does was never done.
- **Given** a story in `BACKLOG` whose declared dependencies are all `DONE` and
  which has no open question against it, **when** the verifier runs, **then** it
  names the story as ready to move.
- **Given** a story in `READY` whose dependencies are not all `DONE`, **when**
  the verifier runs, **then** it fails — the Definition of Ready is not advisory.
- **Given** a story whose dependency line names an id that does not exist,
  **when** the verifier runs, **then** it fails rather than treating the
  dependency as satisfied.
- **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** stories found stale
  by an audit rather than by the verifier — target zero.
- **Why:** on 2026-09-10, asked whether one story was really blocked, an audit
  found **fourteen** in BACKLOG that could have been pulled — twelve whose
  dependencies had all finished and two with no dependencies at all. The verifier
  re-runs every DONE claim's test but never asks whether READY is true. A board
  that is only accurate about the past is half a board.

  The audit script that found them is in this story's commit and is what the
  check should be built from. Note the bug in the first version of it: a
  dependency regex of `[^.]*` stopped at the first period, and **story ids
  contain periods**, so `S-03.02.04` parsed as `S-03` and every dependency
  looked unmet. A checker that reads ids has to be tested against a real one.

#### S-06.02.13 — A defect log and a decision log the next session can read
**As an** owner, **I want** every bug, security hole and design call written
down in one place in plain English, **so that** the next session can see what
this codebase keeps getting wrong without reading a year of commit messages.
- **Given** `DEFECT_LOG.md`, **when** it is read, **then** every defect found
  carries an id, the date it was found, its kind, one plain-English line saying
  what went wrong, and whether it is fixed or filed.
- **Given** a defect recorded as `open`, **when** the verifier runs, **then** it
  fails unless that row names a backlog id that exists — an unfixed defect with
  nowhere to go is a defect nobody will fix.
- **Given** two rows sharing an id, **when** the verifier runs, **then** it
  fails. An id that points at two things points at neither.
- **Given** `DECISIONS.md`, **when** it is read, **then** every entry says what
  was given up, because a decision with no cost was not a decision.
- **Dependencies:** none. **Size:** S. **Indicator:** defects found twice —
  target zero.
- **Why:** asked for by the owner on 2026-09-11. The reasons things broke were
  spread across commit messages, `RETRO.md` and `CHANGELOG.md` — fine for
  reading one story, useless for *has this happened before?* Writing the
  existing 34 defects into one table made five repeating patterns visible that
  no individual retro had shown, including one that had already been fixed
  twice under different names (`D-14`, `D-24`, `D-32`: two lists that must match
  drifting apart). `RETRO.md` keeps its job — three lines of process lesson per
  increment — and is not replaced by this.

#### S-06.02.12 — A recorded commit must be on the branch
**As an** owner, **I want** `scripts/verify_board.py` to check that every
`commit:` on the board is an ancestor of `HEAD`, **so that** the board's link
from a claim to the code that satisfies it cannot quietly rot.
- **Given** a DONE entry whose `commit:` is reachable from `HEAD`, **when** the
  verifier runs, **then** it passes.
- **Given** a DONE entry whose `commit:` names an object that exists but is not
  on the branch — the usual cause is `git commit --amend` after the sha was
  written down — **when** the verifier runs, **then** it fails and names the
  entry.
- **Given** a DONE entry whose `commit:` names no object at all, **when** the
  verifier runs, **then** it fails.
- **Dependencies:** none. **Size:** S. **Indicator:** board shas not on the
  branch — target zero.
- **Why:** found on 2026-09-11 while recording the sha for `S-11.04.02`. Writing
  the sha onto the board and then amending the commit to include that edit
  changes the sha, so the line points at the commit that *was* replaced. Two
  older entries, `S-03.01.01` and `S-03.01.02`, had been carrying an orphaned
  `0be650d` since 2026-08-29 for exactly this reason, and nothing noticed —
  `git cat-file -e` still finds a dangling object, so a naive existence check
  passes. The test is ancestry, not existence.

#### S-06.02.08 — One runner for every evidence command
**As an** owner, **I want** every evidence command to use the same test runner,
**so that** a red board means broken code and never a stale environment.
- **Given** the board, **when** every DONE evidence command is read, **then**
  they all invoke the same runner.
- **Given** a clean checkout, **when** the documented setup is run and the
  verifier follows, **then** it passes without a second, undocumented step.
- **Dependencies:** none. **Size:** S. **Indicator:** verifier failures caused
  by environment rather than code — target zero.
- **Why:** on 2026-09-06 the board went red because some evidence used
  `uv run pytest` against an unsynced venv while the rest used `python -m
  pytest`. It looked exactly like a code defect for several minutes. A lie
  detector that can cry wolf gets ignored.

---

## 3b. Amendments to shipped definitions

Nothing below is edited in place. A shipped story is a record of what was
built and verified, and rewriting it would make the evidence block describe
something that never happened. These are **superseding notes**, and each names
the story that carries the new work.

| Shipped | Still true | Superseded by | What changed and why |
|---|---|---|---|
| `S-02.02.01` — a goal becomes a bounded sequence of actions | yes, as built | `S-11.02.01` | Its `result` is a free-text string. That was correct for a first bounded loop and is wrong for a system whose output feeds a CRM. The string is **kept** as the no-schema fallback; the record is added beside it. |
| `S-02.02.01` | yes | `S-11.01.01`, `S-11.01.02`, `S-11.01.04` | The loop stops on a step budget and on nothing else. Production needs it to stop on failure, on looping, on stalling and on money. |
| `S-02.01.05` — an append-only work trace | yes | `S-11.02.02` | The trace already holds URL, timestamp and screenshot per step. Nothing yet **binds a returned fact to a step**, so provenance is available and unclaimed. |
| `S-02.01.03` — ten verbs, real input, no arbitrary code | yes, unchanged | — | Explicitly **not** superseded. The closed vocabulary is what makes an autonomous loop safe, and E-11 adds nothing to it. |
| `S-05.01.01` — a crawler with a frontier | unchanged | — | Retargeted in framing only: it is the always-on half that *feeds* E-11, not a competing path to the web. No criteria change. |
| `S-03.02.04` — accounts and budgets | yes | `S-11.05.01` | Budgets are per account and correct for one run at a time. Concurrency makes N runs draw N budgets unless the ledger is shared, which is what `S-11.05.01` fixes. |

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
