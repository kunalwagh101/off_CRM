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

### E-12 — off_CRM plans the go-to-market itself, and learns from what happens
**Owner:** the product. **Value hypothesis:** the owner describes the product
once and sets a goal; the system chooses which campaigns to run, fits them inside
what is actually connected, and — once they have run — says in a fixed order
where the plan is going wrong and writes the next version from the measured
numbers. The owner's time moves from *designing* campaigns to *approving* them.
**Leading indicator:** plans applied, and plan versions whose assumptions were
replaced by measured rates. Design: `docs/architecture/GTM_ENGINE.md`.

*(ID block. E-12 artifacts use R-120–R-149, DD-40–DD-59, D-80–D-99, Q-20–Q-39
and S-06.02.20 onward. On 2026-09-22 the branch `feature/next-three-batch-4` was
using numbers up to R-102, DD-28, D-70, Q-07 and S-06.02.17 in parallel; a
separate block means neither side collides with the other when they merge.
It then went on to use D-80 and D-81 as well; at the consolidation into
`develop` those two became D-100 and D-101, and every other line's clashing
numbers moved above the E-12 block — see `docs/BRANCHING.md`. Since then there
is one line, so the blocks are closed: a new ID takes the next free number.)*

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

#### S-03.01.03 — Browser blocks internal network access
**As a** security owner, **I want** the browser container prevented from reaching internal network services, **so that** a web page cannot use it to access infrastructure outside the public internet.
- **Given** any browser request, **when** it targets a non-public destination, **then** the browser and container refuse the connection in both attended and unattended modes.
- **Given** navigation, redirects, subresources and new tabs, **when** destination addresses change, **then** the same network restriction continues to apply.
- **Given** a public test website, **when** the browser accesses it, **then** normal browsing still works. Test with a real browser and container.
- **Dependencies:** S-03.01.01 (DONE). **Size:** L. **Audit:** A07, D-266.

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
- **Blocking risk:** crawler state must survive process restarts without allowing
  two workers to claim the same URL or weakening the existing public-URL policy.
- **Business value:** E-05 — spend a fixed crawl budget on fresh evidence rather
  than repeatedly fetching pages that have stayed unchanged.
- **Tasks:** T-05.01.01.a persist and lease the frontier (<=1 day);
  T-05.01.01.b wire adaptive revisits into the existing guarded fetch path
  (<=1 day); T-05.01.01.c acceptance, concurrency and regression evidence
  (<=1 day); T-05.01.01.d docs, demo, traceability and verifier certification
  (<=1 day).
- **Out of scope:** authenticated/session-gated crawling (forbidden by R-40);
  extraction packs (S-05.01.02); competitor-post analysis (S-05.01.03);
  search-engine/source discovery beyond the supplied run allow-list.

#### S-05.01.02 — Extraction packs as declared data
**As an** owner, **I want** site-shaped extraction to be declared as validated
data rather than new parser code, **so that** a new public source can be added
without a code release.
- **Given** a valid extraction-pack row for an allowed public domain, **when** a
  matching page is parsed, **then** its declared record selector and field
  selectors produce normalized `DiscoveredPerson` values without changing
  Python code.
- **Given** a pack with an unknown field, invalid selector shape, duplicate id,
  duplicate domain match, or unsupported extraction mode, **when** the registry
  loads, **then** it fails closed with a precise validation error and installs
  none of that invalid registry.
- **Given** a page whose domain has no extraction pack, **when** it is parsed,
  **then** the existing generic JSON-LD extraction path still runs unchanged.
- **Given** an extraction pack, **when** it is inspected, **then** it contains
  data only: CSS selectors plus bounded text/attribute extraction rules, never
  Python, templates, JavaScript, arbitrary expressions, network calls, or
  executable hooks.
- **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** sources added per code change.
- **Blocking risk:** a configuration system can accidentally become a second
  executable parser language; pack loading must remain declarative, bounded and
  validated before any page is processed.
- **Business value:** E-05 — reduce the cost and lead time of onboarding public
  research sources while keeping one reviewed crawler/parser implementation.
- **Tasks:** T-05.01.02.a define and validate the pack schema/registry (<=1 day);
  T-05.01.02.b apply a matching pack inside the existing Scrapling parse path
  with JSON-LD fallback (<=1 day); T-05.01.02.c configuration, negative and
  regression tests proving a source is added by data only (<=1 day);
  T-05.01.02.d docs, demo, traceability and verifier evidence (<=1 day).
- **Out of scope:** remote pack download; arbitrary code/template execution;
  authenticated/session-gated scraping; replacing the existing crawler safety
  policy; AI/LLM extraction; competitor-post analysis (S-05.01.03).

#### S-05.01.03 — Take a competitor post apart and rebuild the shape
**As an** owner, **I want** a high-performing public post reduced to reusable
structure — shape, pacing, hook and look — **so that** the engine can learn from
what works without copying the competitor's content.
- **Given** a public competitor post that passes the existing public-source
  policy, **when** it is analysed, **then** the result contains a known recipe
  reference, bounded structural parameters, source/provenance metadata and
  performance signals, but no copied frame, audio asset, caption, transcript or
  other source media.
- **Given** the same normalized public-post facts, **when** analysis is repeated,
  **then** the structural recipe output is deterministic unless an explicitly
  versioned analysis rule changes.
- **Given** a teardown result, **when** it is turned into a project, **then** it
  reuses the existing assembly/recipe path and enters the existing human review
  queue; it cannot publish, schedule, or bypass approval.
- **Given** a session-gated, private, unsupported or insufficient-evidence
  source, **when** analysis is requested, **then** it is refused or returned as
  insufficient evidence rather than fabricating a recipe.
- **Dependencies:** S-05.01.02, S-01.03.02. **Size:** L. **Indicator:** performance of derived pieces.
- **Blocking risk:** competitive inspiration can silently become media copying
  or model guesswork; the stored contract must contain only structural facts,
  provenance and bounded recipe parameters.
- **Business value:** E-05 — turn observed public performance into repeatable
  creative hypotheses while preserving human review and avoiding copied media.
- **Tasks:** T-05.01.03.a define the structure-only teardown contract and
  deterministic mapping to existing recipes (<=1 day); T-05.01.03.b connect
  public performance/source facts to that analyser (<=1 day);
  T-05.01.03.c create projects through the existing assembly/review path and
  prove no media/copy crosses the boundary (<=1 day); T-05.01.03.d negative,
  provenance, review-gate, docs and verifier evidence (<=1 day).
- **Out of scope:** downloading/storing competitor media; cloning captions,
  transcripts, music, voices or frames; bypassing human review; automated
  publishing; authenticated/session-gated competitor collection.

#### S-05.01.04 — Public-page fetches connect only to checked destinations
**As a** security owner, **I want** crawler connections to use verified public destinations, **so that** a hostname change does not redirect the connection to an internal network.
- **Given** a DNS change between validation and connection, **when** a page is fetched, **then** the connection must not reach an unverified destination.
- **Given** redirects, address changes and reused connections, **when** fetching content, **then** every destination passes the public-network restriction.
- **Given** a permitted public website, **when** it is fetched, **then** TLS checks, redirects, size limits and crawl pacing still work.
- **Dependencies:** S-05.01.01 (IN_REVIEW). **Size:** L. **Audit:** A08, D-267.

### F-06.01 — Team and production  *(E-06)*

#### S-06.01.01 — Workspaces with their own keys and their own logins
**As a** team member, **I want** my own provider keys and my own platform
sessions, **so that** my work and my credentials are mine.
- **Given** two workspaces, **when** either reads keys or sessions, **then**
  neither can reach the other's.
- **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** distinct workspaces in weekly use.

#### S-06.01.02 — Three-level permissions
**2026-10-30 implementation note:** Workspace and per-tool policy, owner-only API, action-dispatch protection, unattended initial-navigation protection and expiring chat-grant object are implemented on `develop`. **IN_REVIEW** until final Render QA, an authenticated attended-chat grant/close path, and upstream S-04.01.01 are DONE. No production rollout.

**2026-10-31 backend update:** The owner-only AI chat permission grant, close and tenant isolation APIs exist, and a bounded read-oriented `POST /api/v1/ai/chats/{chat_id}/browser-runs` connects those grants to the existing AgentRun through an isolated workspace browser lease. This is deliberately **not** a full attended browser: there is no live watch/cancel control, so the API refuses attended-only social sites and disables click/type/press/select. Source `3150fbb`, real Render QA `dep-dbiskimc6qcc739ivrcg` targeted 40 passed, full SQLite 2824 and PostgreSQL 2844 passed, Chromium desktop/mobile passed, isolated QA LIVE on 3150fbb. **IN_REVIEW** pending complete QA, actual external browser smoke, D-330, live monitoring/cancel UI and production security acceptance. See `docs/evidence/2026-10-31-read-only-chat-browser-run.md`.

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

#### S-06.01.06 — Campaigns, contacts and drafts belong to a workspace
**As an** owner hosting more than one client on one install, **I want** each
workspace to see only its own campaigns, contacts, drafts and templates, **so
that** one client's customers and product text never reach another's login.
- **Given** two workspaces, **when** either lists, reads or changes a campaign,
  contact, draft or template, **then** it reaches only its own rows, and
  another workspace's row is "not found".
- **Given** the rows that exist before this ships, **when** it ships, **then**
  each is assigned to the install's own workspace, `local`, by a migration whose
  rollback has been run.
- **Dependencies:** `Q-27` — built only if the owner chooses option 2.
  **Size:** L. **Indicator:** CRM rows readable across workspaces — target zero.
- **Why:** `D-135`. Workspace isolation (`S-06.01.01`) covered credentials, AI
  settings and products; the CRM stayed install-wide, so a draft written from
  one workspace's private product can be read from every login.
- **Design:** `docs/architecture/CRM_TENANCY.md` — ready for the day `Q-27` is
  answered with option 2; nothing is built before then.

### F-06.02 — Non-functional work, with its own IDs  *(E-06)*

#### S-06.02.54 — Visitor demo includes the actual AI and orchestration
**As the** owner, **I want** the demo to show our existing AI layer, **so that** visitors can run instructions through real configured models instead of only browsing CRM tables.
- **Given** a public visitor login, **when** signed in, **then** the app opens AI and exposes Chat, Compare, Plan and Image, plus provider setup.
- **Given** two signed visitor sessions, **when** they connect keys, create chats or inspect AI logs, **then** each sees only its own AI workspace and cannot use the other's key.
- **Given** an instruction and a connected eligible model, **when** Plan is run, **then** the existing broker calls the planner and routes each returned step to workers; missing provider setup produces a clear setup response rather than fake success.
- **Given** logout, **when** the session is revoked, **then** its connected keys are removed and another visitor's keys remain.
- **Given** a foreign AI log ID, **when** inspected, **then** it is not found rather than exposing a payload.
- **Given** protected sample CRM records, **when** a visitor attempts owner, mailbox, send or CRM mutation operations, **then** those operations remain refused.
**Dependencies:** S-06.02.53 (corrective follow-up requested by owner; upstream release verification remains open). **Size:** S. **Tests:** tests/test_public_demo_ai.py, tests/test_public_demo.py, frontend login/connectors and real Chromium acceptance. **Status:** IN_REVIEW; real provider key and original-site backup access remain external blockers. This does not claim arbitrary CRM/browser automation from chat.

#### S-06.02.53 — Separate public visitor demo with visible login details
**As the** owner, **I want** visitors to use a dedicated demo account shown on the login screen, **so that** my credentials and QA data stay private.
- **Given** a separate sample-only installation, **when** a visitor opens sign-in, **then** its public username and password are displayed and prefilled; private installations never disclose credentials.
- **Given** the visitor credentials, **when** signed in, **then** the account is in `public-demo`, sees one paused sample campaign and three fictional contacts, and can log out without affecting another session.
- **Given** any anonymous or visitor request, **when** it attempts a mutation other than login/logout or a connected-service read, **then** the server refuses before validation or execution.
- **Given** private/QA storage, external database, escaped paths or private integration settings, **when** public demo mode starts, **then** startup refuses rather than publishing existing data.
- **Given** a restart, **when** the sample-only folder is reopened, **then** no duplicate sample records appear, no scheduler starts, and stale advertised credentials cause startup refusal.
**Dependencies:** none. **Size:** S. **Tests:** `tests/test_public_demo.py`, frontend login rendering, `scripts/live/review_public_demo_browser.py`. **Status:** IN_REVIEW until separate Render deployment and real browser acceptance.

#### S-06.02.52 — Owner can inspect operational scheduler health (A17)
- **Given** the install owner, **when** they call `GET /api/v1/operations/health`, **then** the report lists email automation, content automation and all-workspace agent-routine scheduler health with static codes, without secrets, customer content or raw exceptions.
- **Given** an enabled but stopped scheduler, **when** the report is requested, **then** the relevant component is degraded and `alert_required=true`, while optional automation does not turn `/health/ready` into an HTTP 503.
- **Given** disabled optional schedulers, **when** read, **then** they are explicitly disabled, not falsely failed.
- **Given** invalid config or inaccessible routine inventory, **when** inspected, **then** it reports unknown and a logged error reference, never healthy.
- **Given** no install-owner authorization, **when** requested, **then** the response is 401/403 without topology details.
- **Status:** IN_REVIEW. Real external email worker heartbeat, queue age, configured alerts and independent penetration/load testing still separate production gates. **Tests:** `tests/test_operational_health.py`.

#### S-06.02.51 — Video upload stream and resource guard (A15)
**As an** operator, **I want** uploads to be rejected before multipart parsing exhausts RAM or temporary storage, **so that** malformed, large or stalled media uploads cannot overwhelm a web worker.
- **Given** a video-media or render POST, **when** its request body exceeds the configured per-file limit plus 16 KiB multipart overhead, **then** the ASGI reader sends 413 without invoking the endpoint or reading the rest.
- **Given** two concurrent video upload requests on one worker, **when** a third arrives, **then** the third receives 429 and capacity is restored when an active request finishes.
- **Given** a stalled or disconnected sender, **when** it times out or disconnects, **then** temporary data and capacity are released without media rows.
- **Given** a small valid upload or a nonvideo request, **when** sent, **then** the previous API behaviour is preserved.
- **Tests:** `tests/test_video_upload_body_guard.py`; existing `tests/test_video_upload_security.py`. **No schema changes.** Deployment-wide multi-instance/global quotas and independent load testing remain separate production gates.



#### S-06.02.50 — Bounded video media and render uploads (A15 partial remediation)
**As an** authenticated video operator, **I want** the configured size budget enforced on video imports and renders, **so that** a malicious oversized file cannot be read unbounded into the handler heap.
- **Given** a bounded upload budget, **when** the file exceeds it, **then** the API returns 413 without creating media/render records; both endpoints use `read(limit+1)`.
- **Given** an empty or unauthenticated upload, **when** sent, **then** it is rejected before decoding/storage.
- **Given** a valid WebM below the budget, **when** sent, **then** it is accepted and recorded.
- **Open production gap:** multipart stream spooling and cumulative concurrent memory/disk are not yet bounded. Source audit A15 stays OPEN pending separate stream, concurrency and interruption acceptance. Tests: `tests/test_video_upload_security.py`.



#### S-06.02.01 — No secret may enter a model prompt
- **Given** the payload builder, **when** any request is assembled, **then** a
  scan for credential-shaped material passes.
- **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** scanner findings.

#### S-06.02.02 — Every endpoint authorises and validates
- **Given** any API endpoint outside the documented closed public bootstrap /
  signed-callback allowlist, **when** called without an authenticated session or
  install token, **then** it refuses before business logic runs.
- **Given** any body, **when** it is malformed, **then** the response is a 4xx
  with a bounded message, never a stack trace and never an echo of sensitive
  request-body content.
- **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated reachability.
- **Business value:** E-06 — one forgotten route cannot silently become a
  customer-data bypass.
- **Blocking risk:** login/session bootstrap and externally signed
  unsubscribe/provider callbacks cannot require an already-existing CRM
  session. DD-29 records the explicit default-deny exception rule rather than
  hiding that necessary boundary in middleware.

#### S-06.02.03 — Cost and latency budgets per run
**As an** owner running unattended work, **I want** each run to respect the
spend and measured-latency ceilings I supply, **so that** autonomous work cannot
silently keep consuming money or execution time beyond my chosen limits.
- **Given** a positive spend ceiling, **when** the next model decision would
  cross it, **then** no provider call starts and the run ends `over_budget` with
  the ceiling and projected next spend recorded.
- **Given** a positive latency ceiling, **when** a completed provider or browser
  operation makes cumulative recorded `took_ms` reach or exceed it, **then** no
  new unit of work starts and the run ends `over_latency` with ceiling, actual
  latency and any in-flight overrun recorded.
- **Given** a run that is resumed, **when** no new latency ceiling is supplied,
  **then** its original ceiling and all earlier measured latency still count;
  raising the ceiling requires an explicit argument.
- **Given** a zero ceiling, **when** the run executes, **then** that dimension is
  uncapped exactly as before; a negative, boolean or non-integer latency ceiling
  is refused before the run starts.
- **Dependencies:** S-06.01.03, S-11.01.04. **Size:** S. **Indicator:** new work
  started after a recorded run ceiling — target zero. **Business value:** E-06,
  bounded production operation owners can trust.
- **Blocking risk:** none after the dependencies above. Exact millisecond
  cancellation of an operation already in flight is unsafe for side-effectful
  browser/provider operations; DD-20 records the operation-boundary rule.
- **Tasks:** T-06.02.03.a integrate latency with the existing trace/run/resume
  path (<=1 day); T-06.02.03.b acceptance and regression tests (<=1 day);
  T-06.02.03.c demo, traceability, evidence and verifier certification (<=1 day).

#### S-06.02.04 — Data deletion and subject access
**As an** operator handling a person's privacy request, **I want** one
transactional inventory-driven deletion/export path, **so that** personal data
is not left behind in a forgotten store.
- **Given** an identified person, **when** a subject-access request is executed,
  **then** every registered store reports the matching records/artifacts it
  holds with store name, record class and provenance, without exposing another
  subject's data.
- **Given** a confirmed deletion request, **when** it succeeds, **then** the
  person's data is removed from every registered mutable store including CRM
  research/discovery records, crawler URL/cache state that identifies the
  subject, trace captures/screenshots and generated subject-specific artifacts,
  and a non-personal deletion receipt records what store classes were cleared.
- **Given** any registered store fails deletion, **when** the operation runs,
  **then** the request is not reported complete: the receipt names the failed
  store, retry is safe/idempotent, and no false success is returned.
- **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** deletion requests unfulfilled.
- **Blocking risk:** personal data is spread across SQL rows plus filesystem
  trace/capture artifacts; a hard-coded deletion list will drift as new stores
  are added.
- **Business value:** E-06 — make privacy operations auditable and reliable
  enough for real customer use instead of relying on manual database/file
  cleanup.
- **Tasks:** T-06.02.04.a define one store inventory/subject-match contract and
  enumerate current personal-data stores (<=1 day); T-06.02.04.b implement
  subject access plus idempotent deletion adapters using existing transactions
  and filesystem primitives (<=1 day); T-06.02.04.c cross-store failure,
  isolation and retry tests (<=1 day); T-06.02.04.d docs, rollback/receipt,
  demo, traceability and verifier evidence (<=1 day).
- **Out of scope:** choosing automatic retention duration (Q-07 remains a
  separate owner decision); deleting legally required non-personal audit
  receipts; weakening append-only traces before an explicit confirmed privacy
  operation; cloud-provider deletion APIs not yet connected to off_CRM.

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
| R-99 | A test addresses a trace step by finding it, not by counting | S-06.02.14 |
| R-100 | CI gives the verifier full history and evidence dependencies before it runs | S-06.02.15 |
| R-101 | Frontend production dependencies stay audit-clean and development dependencies carry no unresolved high-severity finding | S-06.02.16 |
| R-102 | A DONE story cannot depend on unfinished work | S-06.02.17 |
| R-103 | Repository evidence workflows acquire a runner and execute | S-06.02.18 |
| R-104 | Every line of built work lives on one working branch whose full suite, frontend build and board verifier pass | S-06.02.19 |
| R-105 | Durable customer state, complete backups, safe recovery and truthful readiness (audit WP1) | S-06.02.21 |
| R-106 | Creating or switching campaigns preserves the intended target through refresh, failure and reload | S-06.02.22 |
| R-107 | Every finding of the 7 September production audit is re-checked on the one working branch, each closed by a test or kept open with a story | S-06.02.23 |
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
| R-120 | The owner records what the product is, who it is for, the problem, the proof, the offer and the forbidden claims, once | S-12.01.01 |
| R-121 | Product input is validated with a readable refusal; an address or a bad URL cannot be saved | S-12.01.01 |
| R-122 | A product change raises its version, and a plan records the version it was written against | S-12.01.01, S-12.02.01 |
| R-123 | A campaign links to one product, and its email templates and post captions use that product | S-12.01.02 |
| R-124 | Nothing the brain writes may contain one of the product's forbidden claims | S-12.01.01, S-12.02.01, S-12.02.03 |
| R-125 | A goal becomes a plan chosen only from declared channels, sources and shapes | S-12.02.01 |
| R-126 | A plan never proposes more volume than the connected identities and accounts carry | S-12.02.01 |
| R-127 | Plans send email only on the targeted-outreach stream | S-12.02.01 |
| R-128 | With no permitted model the brain still plans and reviews, by rules, and says so | S-12.02.01, S-12.02.03 |
| R-129 | Product details never travel in a system prompt, and never below the provider's data policy | S-12.02.01 |
| R-130 | Applying a plan creates paused campaigns and sends nothing by itself | S-12.02.02 |
| R-131 | A review reads real numbers and diagnoses in a fixed order, the pipe before the copy | S-12.02.03 |
| R-132 | No volume increase while delivery is unhealthy, and no copy verdict without enough data | S-12.02.03 |
| R-133 | A review becomes the next plan version, and applying it updates the same campaigns | S-12.02.04 |
| R-134 | The brain learns where it went wrong: measured rates replace assumed ones | S-12.02.04 |
| R-135 | The video director uses the product without widening the system-prompt gap | S-12.01.03 |
| R-136 | The brain drafts against the world's best practice and the owner's own winners | S-12.02.05 |
| R-137 | A demo video travels in the email, stored encrypted on the owner's Google Drive for now | F-12.03 |
| R-138 | off_CRM drives external GTM tools — Apollo, Hunter, Clay, Mailchimp — as their GTM engineer | F-12.04 |
| R-139 | A plan's audience compiles into an Apollo search with its credit cost shown first | F-12.05 |
| R-140 | The verifier distinguishes a shallow clone from a missing commit | S-06.02.20 |
| R-141 | A plan's posting channel runs from the screens: paired, switched on and approved there | S-12.02.06 |
| R-150 | A workspace's campaigns, contacts, drafts and templates are its own, if the owner chooses that (`Q-27`) | S-06.01.06 |
| R-151 | Every process that writes the workspace holds the lease a restore waits for | S-06.02.24 |
| R-152 | Every screen opens at its top, with its warnings in view | S-06.02.25 |
| R-153 | Every Python version the package supports, and the image's, runs the suite in CI | S-06.02.26 |
| R-154 | The audit's live harness runs against the branch that deploys | S-06.02.27 |
| R-155 | A command-line tool locks the workspace whose files it actually opens | S-06.02.28 |
| R-156 | Every model in the provider catalogue is called with options its provider accepts | S-06.02.29 |
| R-157 | A provider connects from the Connectors screen with the form's own values, and a refused value is named | S-06.02.30 |
| R-158 | Provider keys come only from the app; the server's environment never supplies one | S-06.02.31 |
| R-159 | Call and spend caps are chosen from presets or typed, with 0 meaning the provider's limit or no cap | S-06.02.32 |
| R-160 | Trust is the owner's to raise or lower, per provider and per model, with a recorded reason to raise | S-06.02.33 |
| R-161 | Connectors show what is left: our own count for every provider, the provider's figure where it reports one | S-06.02.34 |
| R-163 | A draft personalised with a model reaches it through a path the owner can set up from the screens, with the trust rules applied | S-06.02.35 |
| R-164 | A login that will act as the install owner is made so on purpose, never by picking a workspace name | S-06.02.36 |
| R-165 | Skip navigation focuses the current screen without changing its route | S-06.02.37 |
| R-166 | Any failure leaves one secret-free log line with an error id the user is also shown | S-06.02.38 |
| R-162 | Keys, settings, logins and CRM data survive a deploy on the free plan, in a hosted PostgreSQL | S-06.03.01, S-06.03.02, S-06.03.03, S-06.03.04, S-06.03.05, S-06.03.06, S-06.03.07 |
| R-167 | Browser network isolation denies non-public destinations before connection | S-03.01.03 |
| R-168 | Public fetcher connections use verified public destination addresses | S-05.01.04 |
| R-171 | The visitor demo preserves real AI orchestration with isolated visitor keys and chats | S-06.02.54 |
| R-170 | Third-party visitors use a separate sample-only read-only installation with a visible public login | S-06.02.53 |
| R-169 | A real low-bitrate WebM with encoded frames must not fail a byte-length-only export gate | S-06.02.39 |
| R-186 | The AI response cache cannot reuse a factual answer when numeric evidence, units, entities or meaning changes | S-06.02.58 |
| R-187 | A cached AI answer cannot be attributed to a different model, system prompt or generation setting | S-06.02.59 |

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
  machine except through the transcription provider/model declared when that
  meeting began, raw audio is not persisted by off_CRM, and the derived
  transcript remains workspace-scoped.
- **Dependencies:** S-03.01.01. **Size:** L. **Indicator:** meetings captured per week.
- **Business value:** E-04 — turn real conversations into usable notes without
  adding a meeting bot or creating a raw-recording store.
- **Blocking risk:** browser system-audio capture varies by browser/OS and
  requires the user to explicitly share audio.
- **Out of scope:** raw-audio archival, cloud-hosted capture, speaker
  diarisation, automatic meeting-bot attendance and bypassing browser capture
  permission prompts.

#### S-07.01.04 — Reports and artifacts
**As an** owner, **I want** gathered data to become a deck, a sheet or a PDF,
**so that** research ends in something I can send.
- **Given** a run's findings, **when** a report is generated, **then** every
  claim in it links to a trace step.
- **Given** the same verified findings, **when** XLSX, PPTX or PDF is requested,
  **then** the chosen artifact is produced locally without another model call.
- **Given** page-controlled text beginning with spreadsheet formula characters,
  **when** an XLSX is opened, **then** it remains literal text rather than an
  executable formula.
- **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** reports produced per research run.
- **Blocking risk:** PDF rendering depends on an installed Chrome/Chromium-family
  browser; generation must fail with an actionable message if none is present.
- **Business value:** E-04 — specialised agents end in a portable deliverable
  rather than leaving the owner to reconstruct findings from trace files.
- **Tasks:** T-07.01.04.a shared provenance-bound artifact model (<=1 day);
  T-07.01.04.b XLSX/PPTX/PDF writers and local CLI (<=1 day);
  T-07.01.04.c security/format/negative tests (<=1 day);
  T-07.01.04.d demo, traceability, docs, retro and verifier evidence (<=1 day).
- **Out of scope:** AI rewriting or summarising of verified findings; cloud
  document publishing; collaborative editing; slide design templates; changing
  the underlying run or provenance model.

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
- **Stated during the build:** the check runs *before* the decision is asked
  for, so the ceiling is never crossed rather than reported once it already has
  been. That also makes stopping free, which is what makes it safe to resume
  from — raise the ceiling and the run carries on from the same step.
- **Stated during the build:** the ceiling is recorded on `run_started` and
  re-applied by `resume()`. A ceiling that disappears when a run is resumed is
  not a ceiling; it is a speed bump. Raising it is `resume(spend_ceiling_usd=…)`
  and has to be done on purpose.
- **Stated during the build:** the next decision is predicted from the most
  expensive one so far, not the average. A ceiling is a promise, and the average
  lags a trend — a run whose pages keep growing would walk past the line while
  the average still said it was fine. Stopping early is recoverable; exceeding a
  limit the owner set is not.
- **Known limit, deliberate and tested:** a model with no price list cannot have
  its *first* decision predicted, because the pre-run estimate is zero. That one
  decision goes through whatever the ceiling says; from the second on, the run's
  own observed costs take over. Refusing every run on an unpriced model would
  make free and local models unusable, so the exposure is capped at one decision
  and `test_an_unpriced_model_costs_one_decision_of_headroom_and_no_more` is
  what keeps it at one.
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

#### S-06.02.14 — A test should not hardcode a trace step id
**As a** builder, **I want** tests to address a trace step by finding it rather
than by counting, **so that** adding a step to a run does not break tests that
have nothing to do with it.
- **Given** a test that needs a particular step's id, **when** it runs, **then**
  it locates the step by kind or content, not by a literal like `step-000002`.
- **Given** a new step added anywhere in a run, **when** the suite runs, **then**
  no test fails because the numbering moved.
- **Dependencies:** none. **Size:** S. **Indicator:** tests broken by an
  unrelated step being added — target zero.
- **Why:** `D-37`. Five test files hardcode `step-000002` as "the read action".
  It has broken twice: once in `S-11.01.03` when a `finding` step was added, and
  again in `S-06.01.03`. Both times the fix was to bump a number, which buys one
  story of quiet. The scripted-decision doubles make it awkward — the record
  citing a step is written before the run exists — so the fix is a placeholder
  the broker double substitutes at call time, not a search-and-replace.

#### S-06.02.15 — CI gives the verifier the repository it claims to verify
**As an** owner, **I want** CI to give the board verifier complete Git history
and every dependency its evidence commands require, **so that** a red or green
verifier result measures the repository rather than an incomplete CI checkout.
- **Given** a DONE evidence commit older than `HEAD`, **when** CI runs the
  verifier, **then** full ancestry is available and a reachable commit passes.
- **Given** DONE frontend evidence, **when** CI runs the verifier, **then**
  `npm ci` has already completed and the named frontend test can execute.
- **Given** the CI workflow itself, **when** its regression test runs, **then**
  both ordering constraints above are pinned in code.
- **Dependencies:** S-06.02.08, S-06.02.12. **Size:** S. **Indicator:** verifier
  failures caused by CI environment rather than repository state — target zero.
  **Business value:** E-06, trustworthy release evidence.
- **Blocking risk:** none. GitHub Actions run 393 proved the repaired workflow
  end to end on a clean runner.
- **Tasks:** T-06.02.15.a repair checkout/dependency ordering (<=1 day);
  T-06.02.15.b pin the workflow contract with regression tests (<=1 day);
  T-06.02.15.c record the defect and evidence (<=1 day).

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

#### S-06.02.16 — Resolve frontend development dependency audit findings
**As an** operator, **I want** the frontend development dependency tree free of
known high-severity audit findings, **so that** test and build tooling does not
knowingly carry a vulnerable package while the production tree remains clean.
- **Given** a clean `npm ci`, **when** `npm audit --omit=dev` runs, **then** the
  production dependency tree reports zero known vulnerabilities.
- **Given** the full development dependency tree, **when** `npm audit` runs,
  **then** no high-severity finding remains unresolved or silently ignored.
- **Given** a remediation that requires a breaking upgrade, **when** it is
  applied, **then** frontend tests and the production build prove the upgrade
  rather than relying on `npm audit fix --force`.
- **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit
  findings in the frontend development tree — target zero.

#### S-06.02.17 — DONE may not depend on unfinished work
**As an** owner, **I want** the verifier to reject a DONE story whose declared
upstream dependency is not DONE, **so that** a green board cannot contain an
impossible delivery history.
- **Given** a DONE story that depends on a READY, BACKLOG or BLOCKED story,
  **when** the verifier runs, **then** it fails and names both stories.
- **Given** a DONE story whose declared dependencies are all DONE, **when** the
  verifier runs, **then** the dependency check passes.
- **Dependencies:** S-06.02.11. **Size:** S. **Indicator:** DONE stories whose
  dependencies are not DONE — target zero.


#### S-06.02.18 — Restore executable CI runner capacity
**As an** owner, **I want** the repository evidence workflow to receive an
actual runner, **so that** focused tests, the full regression suite and the board
verifier can execute before any story is certified DONE.
- **Given** the current private repository and `.github/workflows/ci.yml`,
  **when** a push or pull-request run starts, **then** the `quality` job reaches
  at least runner setup/checkout and exposes workflow steps and logs.
- **Given** the hosted job cannot acquire a runner because of an account,
  repository or GitHub Actions service restriction, **when** the failure is
  inspected, **then** the blocker is recorded explicitly and no application
  story uses that run as passing evidence.
- **Given** GitHub-hosted execution is unavailable but an approved self-hosted
  runner is intentionally configured, **when** the same locked commands run,
  **then** the evidence contract remains unchanged; runner choice may not weaken
  tests or the verifier.
- **Dependencies:** none. **Size:** S. **Indicator:** CI jobs with zero workflow
  steps — target zero.
- **Blocking risk:** this is account/service infrastructure, not application
  code. The repository connector cannot inspect the owner's Actions billing,
  budgets or repository Actions policy.
- **Tasks:** verify owner Billing & licensing → Actions usage/budgets/payment
  state; verify repository Settings → Actions → General; if both are clean,
  provide GitHub Support the failing run/job IDs and timestamps; re-run the
  unchanged locked workflow only after runner capacity is restored.
- **Out of scope:** weakening/removing tests, changing DONE evidence rules,
  making the private production repository public to obtain free hosted
  minutes, or silently switching to an untrusted runner.

#### S-06.02.19 — One working branch holds everything built, and it is green
**As an** owner, **I want** one branch that carries every piece of work that was
built — and nothing that was not — with its whole suite passing, **so that**
what runs on Render is the product, not whichever branch was deployed last.
- **Given** the thirty-odd branches of 2026-09-23, **when** they are consolidated,
  **then** every branch is either merged, ported, or shown by a line-coverage
  and status comparison to be contained or superseded, and archived under
  `archive/<branch>` before it is deleted.
- **Given** two lines that used the same story, requirement, defect or decision
  IDs for different things, **when** they meet, **then** the later ones are
  renumbered and each renumbered entry says what it was called before.
- **Given** the consolidated branch, **when** the full Python suite, ruff gate,
  frontend tests and build, and the board verifier run, **then** all pass; a
  test that passed only because it checked nothing is repaired and shown to fail
  when the code is broken on purpose.
- **Dependencies:** none. **Size:** L. **Indicator:** branches carrying unmerged
  work — target one (`develop`).
- **Why:** `D-115`. The newest line had never run its own suite. Its failures
  and the merge's are `D-103`–`D-113`.
- **Out of scope:** moving IN_REVIEW stories to DONE — they wait for their own
  review; this story only removes the errors that stood in the way of one.
  Merging `develop` into `main` — the owner does that after checking it.

#### S-06.02.21 — Durable customer state and safe recovery (audit WP1)
**As an** owner, **I want** a restart, a redeploy or a restore never to lose or
corrupt the workspace, **so that** customer records survive the operations that
are supposed to protect them.
- **Given** production configuration, **when** the durable root is ephemeral,
  **then** the app refuses to start rather than silently losing state.
- **Given** a backup, **when** it is made, **then** every durable file under the
  data directory is in it — new stores included without editing a list — with a
  versioned, hashed manifest; only named rebuildable caches are left out.
- **Given** a restore, **when** it succeeds or is rejected, **then** writers are
  drained first, the whole workspace is swapped under a journal, every service
  is reopened and health-checked, and a failure rolls back to the previous
  generation; an interrupted swap rolls back at the next start.
- **Given** readiness, **when** a required store or durable path cannot be
  opened or written, or recovery is in progress, **then** `/health/ready` is red.
- **Dependencies:** none. **Size:** L. **Indicator:** restores that lose a
  record — target zero.
- **Why:** built on `integration/main-consolidation` as its `S-06.02.15` / `R-100`
  (findings A01–A04 and A17 of `docs/audits/2026-09-07-production-audit.md`).
  That branch shared no history with the newest line, which kept its own weaker
  restore — and that restore lost data (`D-114`). Ported here under a free ID.

#### S-06.02.22 — A created or selected campaign stays the active workspace
**As an** owner, **I want** the campaign I just created or picked to stay
selected through a refresh, a failed request or a reload, **so that** an import
never lands in an older campaign.
- **Given** a new campaign, **when** it is created, **then** it becomes the
  selected campaign and stays so after the campaign list refreshes.
- **Given** a selected campaign outside the bounded list, **when** the list
  refreshes, **then** the selection is kept by reading its detail; only a 404
  for that campaign lets the selection fall back.
- **Dependencies:** none. **Size:** S. **Indicator:** imports into a campaign the
  owner did not pick — target zero.
- **Why:** audit finding A33, reproduced in real Chrome. Built on
  `integration/main-consolidation` as its `S-06.02.16` / `R-101`; ported here
  under a free ID because this line's `S-06.02.16` is a different story.

#### S-06.02.23 — Re-check the 7 September production audit on `develop`
**As an** owner, **I want** each of the audit's 35 findings to say whether it is
still true of the branch I deploy, **so that** a finding fixed twice is not
worked on again and a finding still open is not assumed fixed.
- **Given** a finding the consolidation did not re-check, **when** its
  reproduction from `docs/audits/2026-09-07-production-audit.md` is run against
  `develop`, **then** it becomes a test that fails while the finding holds — or
  the finding is closed with the test that shows it no longer does.
- **Dependencies:** none. **Size:** L. **Indicator:** audit findings with
  unknown status on `develop` — target zero.
- **Split 2026-09-23:** the live-harness criterion moved to `S-06.02.27`, so the
  per-finding checks, which need nothing, are not held behind CI runners. A
  finding that still holds is not left as a failing test in the suite: it gets a
  `D-nnn` row and a story whose fix starts from that test. Work order:
  `docs/work-orders/S-06.02.23-audit-recheck.md`.
- **Why:** the audit ran on `main` at `9f71f3c`. The consolidation closed A01–A04
  and A17 (`S-06.02.21`), A26 (the image now installs the lock with its extras)
  and A35 (`D-120`); A33 is `S-06.02.22`; A31 is `S-06.02.16`. A32 and A34 were
  re-read in the code and are still open (`D-121`, `D-122`). The other 24 were
  found on a branch that `develop` has since changed a great deal — several
  (A05 identity, A06 logout, A09 Enter, A10 spend cap, A18 claim numbers, A19
  formulas, A24 deletion) are what later stories set out to fix — but none was
  re-run here, and "probably fixed" is not a status.
- **Out of scope:** fixing a finding that turns out to be open — each gets its
  own story, as A32 and A34 will.

#### S-06.02.24 — Every process that writes the workspace holds its lease
**As an** owner, **I want** the command-line tools to respect a restore as the
web app and the email worker do, **so that** nothing written during a restore
is lost with the generation it swaps out.
- **Given** a restore in progress, **when** the outreach, notebook or eval CLI
  starts, **then** it refuses with a sentence saying to retry once readiness
  returns, and writes nothing.
- **Given** a CLI command running, **when** a restore starts, **then** the
  restore waits for it within its bound, or is refused — as for the worker.
- **Given** a restore nobody has rolled back yet, **when** a CLI starts,
  **then** it refuses, as the email worker does (`D-129`).
- **Dependencies:** none. **Size:** S. **Indicator:** processes that write the
  workspace without its lease — target zero.
- **Why:** `D-134` and `D-138`, found while fixing the cold review's findings on
  `develop`. Work order: `docs/work-orders/S-06.02.24-workspace-lease-for-clis.md`.

#### S-06.02.25 — Every screen opens at its top, its warnings in view
**As an** owner, **I want** a screen to open at its top, with any warning above
it in view, **so that** I see why work is blocked instead of a page scrolled
past its own error.
- **Given** any screen opened from the navigation, **when** it has rendered,
  **then** its title and first panel are fully visible below the top bar, at
  desktop and phone widths.
- **Given** the campaign list failing, **when** a screen opens, **then** the
  "Could not refresh campaigns" panel is visible without scrolling.
- **Given** keyboard or screen-reader use, **when** the screen changes,
  **then** focus still moves to the main content, as `S-06.02.05` requires.
- **Dependencies:** none. **Size:** S. **Indicator:** screens whose top is
  hidden on arrival — target zero.
- **Why:** `D-137`. Work order: `docs/work-orders/S-06.02.25-screen-opens-at-top.md`.

#### S-06.02.37 — Skip navigation keeps the current screen
**As an** owner using the keyboard, **I want** Skip to main content to focus
the screen I am reading, **so that** skipping navigation does not send me to
Dashboard.
- **Given** Settings or another screen, **when** Skip to main content is
  activated with Enter, **then** the route and screen stay unchanged and main
  receives focus.
- **Given** a pointer activation of the same link, **when** it is used,
  **then** the same screen stays open and its top is visible.
- **Dependencies:** none. **Size:** S. **Indicator:** skip activations changing
  screens — target zero.
- **Why:** `D-239`, found in the independent review of `S-06.02.25` and
  reproduced in real Chromium; filed separately under change control.

#### S-06.02.26 — CI runs the suite on every Python the package supports
**As an** owner, **I want** the suite run on every Python version
`pyproject.toml` declares and the one the image runs, **so that** a failure on
one version only is caught on the push, not in someone's install.
- **Given** a push, **when** CI runs, **then** the whole suite runs on 3.10,
  3.11 and 3.12, each installed from the lock, and a failure on any fails the
  check.
- **Given** a version added to `pyproject.toml`, or the image's version
  changed, **when** the suite runs, **then** a test fails until CI names it.
- **Dependencies:** `S-06.02.18` (CI runners). **Size:** S. **Indicator:**
  supported versions without a CI job — target zero.
- **Why:** `D-128`: every backup failed on 3.10 and the suite could not even
  load there, and nothing ran it. Work order:
  `docs/work-orders/S-06.02.26-python-matrix.md`.

#### S-06.02.27 — The audit's live harness runs against `develop`
**As an** owner, **I want** the 7 September audit's live harness run against the
branch I deploy, **so that** the checks only real Chrome, PostgreSQL and Docker
can make are not taken on trust.
- **Given** the audit's live harness (`verification/` on the archived
  `integration/main-consolidation`), **when** it can run — CI runners
  (`S-06.02.18`) or a trusted machine with Docker, Chrome and PostgreSQL —
  **then** it runs against `develop` and its results are recorded, skips counted
  as failures.
- **Dependencies:** `S-06.02.18`. **Size:** M. **Indicator:** harness checks
  never run against `develop` — target zero.
- **Why:** split from `S-06.02.23` on 2026-09-23; `DD-37` is why the harness was
  not ported with the rest.
- **Where the harness is:** after the owner's branch clean-up, the tag
  `archive/integration/main-consolidation` (fetch tags with
  `git fetch origin 'refs/tags/archive/*:refs/tags/archive/*'`); before it, the
  branch itself, or pull request #14's ref (`git fetch origin pull/14/head`).

#### S-06.02.31 — Provider keys come only from the app
**As an** owner, **I want** every provider key to be one I typed into the app,
**so that** no user ever has to reach the server's environment, and no login
ever uses a key it was not given.
- **Given** `OFFSETX_AI_<PROVIDER>_KEY` set on the server, **when** any workspace
  lists or uses providers, **then** that variable supplies nothing.
- **Given** any web request — a draft, a provider profile — **when** it names
  a server environment variable or brings its own provider, **then** it is
  refused; and a login sees and uses only its own workspace's profiles
  (`D-154`, `D-155`, found by the story's fresh-context review).
- **Given** no stored key, **when** the owner connects a provider that needs one,
  **then** it is refused with a sentence saying to paste the key first; a local
  server that needs no key still connects.
- **Dependencies:** none. **Size:** S. **Indicator:** workspaces able to use a
  key they did not store — target zero.
- **Why:** `D-151` — the variable served every workspace login, other clients
  included. Owner, 2026-09-25: users add keys in the app, not the environment.

#### S-06.02.32 — The connect form offers limit presets
**As an** owner, **I want** to pick a daily call cap and spend cap from sensible
choices, **so that** I do not have to guess a number.
- **Given** the Connect form, **when** the owner sets the call cap, **then** the
  choices are the provider's own limit (0), 50, 200, 1,000 or a typed number;
  the spend cap offers no cap (0), $1, $5, $20 or a typed amount.
- **Given** a saved cap, **when** the form opens again, **then** it shows that
  cap, as its preset or as a typed number.
- **Dependencies:** `S-06.02.30`. **Size:** S. **Indicator:** caps set by typing
  a number the owner had to guess — no target; the presets are the default.
- **Why:** owner request, 2026-09-25.

#### S-06.02.33 — Trust is the owner's to change, per provider and per model
**As an** owner, **I want** to raise or lower how far any provider or model is
trusted, **so that** the defaults are a starting point and not a verdict.
- **Given** any provider, **when** the owner lowers its trust, **then** it
  applies at once to every model under it, with no reason asked.
- **Given** any model under a provider, **when** the owner sets its own trust,
  **then** it applies at or below the provider's tier, never above it — the
  provider sees everything sent to it (`DD-65`, amended after review).
- **Given** a raise above a default, **when** the owner saves it, **then** a
  typed reason is required and recorded with who and when; without one nothing
  changes.
- **Given** a provider raised above its default, **when** one of its models is
  capped because of who built it, **then** the provider's raise does not lift
  that model — only the model's own setting can.
- **Given** any trust setting, **when** the owner has not typed the separate
  mailbox unlock phrase, **then** received mail reaches no model — no trust
  setting opens the mailbox (`AGENTS.md` rule 5).
- **Given** a changed trust, **when** the owner saves the connection again,
  **then** the data ceiling follows the changed trust, not the default.
- **Dependencies:** none. **Size:** M. **Indicator:** trust changes made without
  a recorded reason for a raise — target zero.
- **Why:** owner request, 2026-09-25; decisions `DD-64`, `DD-65`.

#### S-06.02.39 — Valid low-bitrate WebM exports pass verification
**As a** video editor user, **I want** a completed low-bitrate Colour export to pass the file checks, **so that** the default short video is not refused merely because it compresses unusually well.
- **Given** a genuine encoded WebM with a video track, encoded video samples, correct dimensions and duration, **when** its byte length is under 4096, **then** the export passes the non-empty gate and all the other applicable existing gates.
- **Given** a short metadata-only, zero-sample or malformed WebM, **when** it is checked, **then** it remains rejected as incomplete; a larger valid export retains its old behaviour.
- **Given** a declared duration, dimensions or audio requirement, **when** the media disagrees, **then** those gates still refuse the export regardless of file size.
- **Dependencies:** S-01.02.01 (DONE). **Size:** S. **Audit:** A34, D-122. **Scope:** small WebM only; do not weaken other codecs or remove the existing threshold for unproved data.
- **Why:** owner-selected narrow fix after the production audit identified an actual 60-frame video refused under the size-only check.

#### S-06.02.38 — Any error can be traced back the next day
**As an** install owner, **I want** every failure to leave one log line with
an error id that the screen also shows, **so that** "it broke yesterday" can be
found and explained, on Render as well as on a laptop.
- **Given** any request that fails with a 5xx, **then** the response carries a
  readable sentence and an error id, and standard output carries one JSON line
  with that id, the time, the route, the workspace and the traceback.
- **Given** a failed worker cycle, command or background job, **then** the same:
  one line, an id, and the id printed with the sentence.
- **Given** a local install, **then** the lines also go to a size-capped
  rotating file under `OFFSETX_DATA_DIR/logs/`; on Render, standard output only.
- **Given** a failure whose message holds a password, key, token, cookie or a
  database URL with credentials, **then** none of it reaches a log line.
- **Given** a successful request, **then** nothing is logged beyond a one-line
  access record (method, route, status, time taken) — no bodies.
- **Dependencies:** none. **Size:** M. **Indicator:** failures with no log
  line and id — target zero.
- **Why:** owner's instruction, 2026-10-04 (`AGENTS.md`, "Logging"); `D-242`.

#### S-06.02.36 — A second owner login is made on purpose
**As an** install owner, **I want** a login in workspace `local` to be created
only when I say it should act as the owner, **so that** naming a workspace
never hands a colleague or client the owner's powers.
- **Given** the workspace form or API, **when** the id `local` is chosen,
  **then** the login is created only with an explicit owner choice, and the
  answer says what an owner login can do.
- **Given** existing logins in `local`, **then** they keep working.
- **Dependencies:** none. **Size:** S. **Indicator:** owner logins created
  without an owner choice — target zero.
- **Why:** `D-196`, from the sixth check, 2026-09-28. `DD-59` accepted it as a
  cost; the owner decides whether it stays one.

#### S-06.02.35 — Drafts reach a model the owner set up on a screen
**As an** owner, **I want** the Drafts screen's model option to use a provider
I can set up from the screens, **so that** "personalise with a model" is not a
pointer to a form that no longer exists.
- **Given** the owner's answer to `Q-28`, **when** a model is connected the way
  it names, **then** the Drafts screen offers it and drafts through it, and the
  trust tiers, scanner and egress log apply as they do to every other model call
  (answer 1), or the profile form is back in Settings and lists each profile
  with whose it is (answer 2).
- **Given** no model set up for the workspace, **when** Drafts opens, **then**
  its empty state names the screen that sets one up — a screen that exists.
- **Given** profiles saved before `DD-68`, **then** the owner can see and
  confirm or remove each one there, not only through the API.
- **Dependencies:** `Q-28`. **Size:** M. **Indicator:** empty states pointing
  at a screen that cannot do what they say — target zero.
- **Why:** `D-173`, found 2026-09-25 while fixing the second review's findings.

#### S-06.02.34 — Connectors show how much is left
**As an** owner, **I want** each connected provider to show what I have used
and what is left, **so that** I am not surprised when a key stops.
- **Given** every connected provider, **when** Connectors opens, **then** it
  shows today's calls counted by off_CRM against the owner's cap.
- **Given** a provider that reports what is left — a key or balance endpoint,
  or rate-limit headers on its replies — **when** it has been checked or called,
  **then** the screen shows the provider's own figure and when it was read.
- **Given** a provider that reports nothing (NVIDIA, checked 2026-09-25),
  **then** the screen says the provider does not report it, never a guess.
- **Dependencies:** `S-06.02.32`. **Size:** M. **Indicator:** providers whose
  reporting is unknown — target zero after the work order's first step.
- **Why:** owner request, 2026-09-25. A model cannot know an account's balance;
  only the provider's API can say, and many do not.

#### S-06.02.30 — A provider connects from the Connectors screen as shown
**As an** owner, **I want** the Connect button to work with the values the form
shows me, **so that** connecting a model is one click after pasting a key.
- **Given** the Connectors form's defaults — call cap 0, spend cap 0 — **when**
  the owner connects a provider, **then** it connects, and 0 means no cap of
  ours.
- **Given** a value the server refuses, **when** the screen shows the error,
  **then** the message names the field and what was wrong.
- **Dependencies:** none. **Size:** XS. **Indicator:** connect attempts refused
  for a value the form itself offered — target zero.
- **Why:** `D-149` and `D-150`, reported by the owner from the live app on
  2026-09-25.

#### S-06.02.29 — The NVIDIA reasoning model answers in chat
**As an** owner, **I want** a model I connected to answer, **so that** the AI
screen is not a wall of "every permitted provider failed".
- **Given** `nvidia/nemotron-3-ultra-550b-a55b` connected with a key, **when**
  the owner chats, **then** the request carries only options NVIDIA accepts:
  `max_tokens`, `temperature`, `top_p`, `chat_template_kwargs` — not
  `reasoning_budget`.
- **Dependencies:** none. **Size:** XS. **Indicator:** provider 400s caused by
  our own request options — target zero.
- **Why:** `D-147`, reported by the owner from the live app on 2026-09-25.

#### S-06.02.28 — A command-line tool locks the workspace it actually opens
**As an** owner, **I want** a command-line tool to hold the lease of the
workspace whose files it opens, **so that** no path spelling lets a write land
in a workspace a restore is swapping.
- **Given** an explicit `--db`, `--context` or `--token`, or an absolute
  `OFFSETX_OUTREACH_DB` or `OFFSETX_GMAIL_TOKEN`, naming the web app's files, run
  from any folder, **when** a restore holds the web app's workspace, **then**
  the tool refuses — it does not lock a `local_data` beside the current folder.
- **Given** `OFFSETX_DATA_DIR` set only in `.env`, **when** any of the six tools
  runs, **then** it resolves the same data directory as `offsetx-web`; today only
  `offsetx-web` and `offsetx-outreach` read `.env`.
- **Given** `offsetx-artifacts --run-dir .` from inside a run the app recorded,
  **when** a restore runs, **then** it refuses.
- **Dependencies:** `S-06.02.24`. **Size:** M. **Indicator:** writes made
  during a restore by a tool pointed at the workspace — target zero.
- **Why:** `D-146`, from the fresh-context review of `S-06.02.24`: the lease
  is keyed on the data directory worked out from the current folder, not on
  the files the command opens. The design call — how a tool learns which
  workspace a path belongs to — is the first step of its work order.

#### S-06.02.20 — The verifier tells a shallow clone apart from a missing commit
**As an** owner, **I want** the verifier to say "this clone is shallow" when that
is the reason a recorded commit cannot be found, **so that** an environment gap
never looks like thirty falsified DONE claims.
- **Given** a shallow clone that lacks a recorded commit, **when** the verifier
  runs, **then** it fails with a message naming the shallow clone and
  `git fetch --unshallow`, not one saying the commit does not exist.
- **Given** the CI workflow, **when** it checks out the repository, **then** it
  fetches full history so the ancestry rule can run there.
- **Dependencies:** S-06.02.12. **Size:** S. **Indicator:** verifier failures
  caused by the environment rather than the board — target zero.
- **Why:** `D-80`. A cloud session started shallow on 2026-09-22 and 32 DONE
  stories appeared to cite commits that do not exist. They all exist upstream.

---

### F-12.01 — One source of truth about the product  *(E-12)*

The product described once, versioned, and read by everything that writes for a
campaign linked to it.

#### S-12.01.01 — The owner records the product once
**As an** owner, **I want** to write down what my product is, who it is for, the
problem, the proof, the offer and what must never be claimed, once, **so that**
everything the system writes starts from the same truth.
- **Given** the required fields, **when** a product is created, **then** it is
  stored at version 1 and reads back identically.
- **Given** a missing or out-of-bounds required field, a website that is not
  `http(s)`, or more list items than the bound, **when** it is saved, **then**
  it is refused with a sentence naming the field.
- **Given** an email address anywhere in the product, **when** it is saved,
  **then** it is refused before it can reach a model.
- **Given** an existing product, **when** it is edited, **then** its version
  rises by exactly one.
- **Given** a forbidden claim, **when** text is checked, **then** the phrase is
  found case-insensitively as a whole phrase — including one ending in `%` —
  and not inside a longer word.
- **Given** a product in one workspace, **when** another workspace reads, edits
  or deletes it, **then** the answer is not found.
- **Given** the Product screen, **when** it renders, **then** the required
  fields and the forbidden-claims box are present.
- **Dependencies:** none. **Size:** M. **Indicator:** products with every
  required field filled.

#### S-12.01.02 — Everything that writes for a campaign uses its product
**As an** owner, **I want** each campaign linked to a product, and its emails
and post captions to use that product, **so that** my channels stop telling
three different stories.
- **Given** a product and campaigns, **when** the owner sets the product's
  campaigns, **then** each campaign is linked to exactly one product and the new
  set replaces the old one.
- **Given** an email template using `{product_offer}` and a campaign linked to a
  product, **when** a draft is created, **then** the placeholder is filled from
  the product.
- **Given** a campaign with no product, **when** a draft is created from a
  template using a product placeholder, **then** it renders empty rather than
  failing, and templates without product placeholders render exactly as before.
- **Given** a rendered draft containing one of the linked product's forbidden
  claims, **when** it is audited, **then** the audit flags the claim.
- **Given** a distribution campaign linked to a product and no angle, **when**
  the trend pipeline runs over HTTP or from the automation timer, **then** the
  product one-liner is the angle **and** the writer's data class is `campaign`.
- **Given** an explicit angle, **when** the pipeline runs, **then** the explicit
  angle wins over the product.
- **Dependencies:** S-12.01.01. **Size:** M. **Indicator:** campaigns linked to
  a product.

#### S-12.01.03 — The video director uses the product
**As an** owner, **I want** directed videos to speak in my product's voice,
**so that** video tells the same story as email.
- **Given** a video campaign linked to a product, **when** the director runs,
  **then** the product text travels in classified request fields, the request
  is `campaign` class, and nothing owner-typed is in the system prompt.
- **Given** any director call, **when** the egress log is read, **then** it
  shows everything that left, the system prompt included.
- **Dependencies:** S-12.01.02. **Size:** M. **Indicator:** model calls carrying
  owner text outside the payload — target zero.
- **Why:** `D-81`. Wiring the product into today's `style` argument would carry
  campaign material to tier C, unlogged. Work order:
  `docs/work-orders/S-12.01.03-video-director-uses-the-product.md`.

### F-12.02 — The strategy brain  *(E-12)*

A goal in; a plan chosen from declared options and fitted to real capacity;
paused campaigns; a review in a fixed order; the next version from measured
numbers.

#### S-12.02.01 — A goal becomes a checked plan that fits what is connected
**As an** owner, **I want** to set a goal for a product and get a plan back,
**so that** I approve a strategy instead of designing campaigns by hand.
- **Given** a model reply naming a channel kind or an audience source outside
  the vocabulary, **when** it is parsed, **then** the plan is refused by name
  with the known values.
- **Given** a reply proposing more email volume than the connected identities
  carry, or more posts than the accounts allow, **when** it is parsed, **then**
  the volume is clamped and a note says so.
- **Given** a reply whose angle contains one of the product's forbidden claims,
  **when** it is parsed, **then** the angle is removed, a note names the claim,
  and no stored plan contains the phrase.
- **Given** any plan with an email channel, **when** it is parsed or built,
  **then** the email stream is `targeted_outreach`.
- **Given** the system prompt the brain sends, **when** it is built, **then** it
  contains no text from the product.
- **Given** the request the brain sends, **when** it is built, **then** its data
  class is `campaign`, the one-liner is the positioning line and the rest of the
  product is in campaign notes.
- **Given** no permitted model, **when** a plan is drafted, **then** a
  rules-based plan is returned with a note saying why.
- **Given** a `replies` goal, **when** a plan is drafted, **then** its
  feasibility is arithmetic the owner can reproduce by hand.
- **Given** an unknown goal kind, a target or horizon out of bounds, or an
  unknown product, **when** it is submitted, **then** it is refused with a
  sentence.
- **Given** the Strategy screen, **when** it renders, **then** the goal form and
  the capacity panel are present.
- **Dependencies:** S-12.01.01. **Size:** L. **Indicator:** plans drafted per
  product.

#### S-12.02.02 — An approved plan becomes paused campaigns, and nothing sends by itself
**As an** owner, **I want** Apply to turn a plan into real campaigns that wait
for me, **so that** a strategy becomes work without anything going out behind
my back.
- **Given** a draft plan, **when** it is applied, **then** one campaign per
  channel exists, each paused, each linked to the product and the plan.
- **Given** an email channel, **when** it is applied, **then** its campaign
  carries the plan's daily volume, window, weekdays, timezone, hypothesis and
  per-message approval.
- **Given** a `views` goal with a distribution channel, **when** it is applied,
  **then** the distribution campaign has a views goal with the plan's deadline.
- **Given** a plan that is not a draft, **when** apply is called, **then** it is
  refused and nothing is created.
- **Given** an apply, **when** it returns, **then** it lists next steps, each
  naming an existing screen, and no contact is imported and nothing is spent.
- **Dependencies:** S-12.02.01. **Size:** M. **Indicator:** plans applied.

#### S-12.02.03 — The brain says where it is going wrong, in a fixed order
**As an** owner, **I want** the plan reviewed against real numbers, **so that**
I fix what is actually broken instead of rewriting emails that never arrived.
- **Given** an email channel whose delivery health is breached, **when** it is
  reviewed, **then** the finding is `delivery_unhealthy` whatever the reply
  rate, and raising volume is not permitted.
- **Given** each earlier condition in the order — paused, no contacts, drafts
  waiting, under volume — **when** it is reviewed, **then** that finding wins
  over every later one.
- **Given** fewer than 20 contacted, **when** it is reviewed, **then** the
  finding is `insufficient_data` and no copy remedy is offered.
- **Given** enough contacted, **when** the 90% interval sits wholly below,
  wholly above or across the assumed rate, **then** the finding is
  `behind_target`, `ahead_of_target` or `inconclusive`, and `inconclusive`
  states how many more sends would decide it.
- **Given** a distribution channel, **when** it is reviewed, **then** the
  finding follows `pacing.decide()`'s action.
- **Given** a model reply proposing a remedy the finding does not permit, a
  channel not in the plan, or a proposal containing a forbidden claim, **when**
  it is parsed, **then** that remedy is dropped with a note.
- **Given** no permitted model, **when** it is reviewed, **then** each finding
  gets its first permitted remedy and a note says why.
- **Given** a review, **when** it is stored, **then** the measurements it read
  are stored with it.
- **Dependencies:** S-12.02.02. **Size:** L. **Indicator:** reviews whose first
  finding is not about copy.

#### S-12.02.04 — A review becomes the next version of the plan
**As an** owner, **I want** the next plan written from what the last one
measured, **so that** the system learns from where it went wrong.
- **Given** an applied plan with a review and at least 20 contacted, **when** it
  is revised, **then** a draft at the next version exists whose parent is the
  plan and whose assumed reply rate is the measured one.
- **Given** fewer than 20 contacted, **when** it is revised, **then** the
  assumption is carried forward and a note says why.
- **Given** a revision that is applied, **when** it runs, **then** the same
  campaigns are updated rather than new ones created, a channel it dropped is
  paused, and the previous version is superseded.
- **Given** a plan with no review, **when** revise is called, **then** it is
  refused.
- **Dependencies:** S-12.02.03. **Size:** M. **Indicator:** plan versions whose
  assumption is a measured rate.

#### S-12.02.05 — The brain drafts against the expert corpus and the owner's winners
**As an** owner, **I want** plans written with the world's best practice and my
own winning templates in view, **so that** the brain starts from what works.
- **Given** an imported expert library and a judged winning template, **when** a
  plan is drafted, **then** both travel as reference material in classified
  fields, and the `gtm_plan` eval suite scores the brain with and without them.
- **Given** fewer than 30 cases in `gtm_plan`, **when** the comparison runs,
  **then** it reports that no verdict is trustworthy yet.
- **Dependencies:** S-12.02.04. **Size:** L. **Indicator:** plan-suite score
  with the corpus against without it.
- **Work order:** `docs/work-orders/S-12.02.05-plans-with-expert-references.md`.

#### S-12.02.06 — A plan's posting channel runs from the screens
**As an** owner, **I want** a plan's posting channel to start posting from the
screens, **so that** a views goal is something the product can actually reach.
Filed 2026-09-22 for `D-82`: today Apply creates the posting and picture
campaigns, and nothing on a screen pairs them, switches content automation on or
approves a post.
- **Given** an applied plan with posting and picture channels, **when** the
  owner resumes them, **then** content automation runs that pair without the
  owner writing its ids into an API call.
- **Given** a drafted post, **when** the owner opens Posting, **then** they can
  approve or skip it there.
- **Given** a paused campaign in a declared pair, **when** content automation
  runs, **then** it makes nothing for that pair — pairing at Apply must not
  spend image credits on a plan nobody has started. *(Done early for `D-87`.)*
- **Given** a plan's posts a day, **when** its posting runs, **then** that is
  the rate the pacer starts from, so the number the plan shows is the number
  that posts (`D-97`).
- **Dependencies:** S-12.02.02. **Size:** M. **Indicator:** plans with a views
  goal that publish a first post.
- **Work order:** `docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md`.

### F-12.03 — Video in the email  *(E-12, next milestone)*

A plan's email carries a demo video, stored encrypted on the owner's Google
Drive for now (`Q-20`), played through a per-recipient page off_CRM serves, with
watch time flowing back into the review beside replies. No stories until this
milestone opens — detail written earlier is fiction.

### F-12.04 — off_CRM drives the GTM tools the owner already pays for  *(E-12, later milestone)*

Apollo, Hunter, Clay, Mailchimp and their kind become tools the brain can plan
with and operate through their official APIs: the GTM engineer Clay needs, run
by off_CRM. No stories until opened.

### F-12.05 — A plan's audience becomes a search  *(E-12, later milestone)*

The audience a plan names compiles into an Apollo search payload and a
discovery objective, with the credit cost shown before anything is spent. No
stories until opened.

---

#### S-06.02.40 — A durable email worker runs beside the deployed web app
**As an** operator, **I want** queued approved email to be processed by one supervised, restartable worker, **so that** an unattended send does not depend on a free web request or a user keeping a tab open.
- **Given** a deployed workspace with durable CRM and queue state, **when** an approved due email is queued, **then** the independently deployed worker opens the same hosted database and processes it within an operating bound; no duplicate send after restart or lease contention.
- **Given** the worker crashes or loses the database/provider, **when** it restarts, **then** uncertain sends remain quarantined for reconciliation, a safe error reference is logged, and no operation is silently retried.
- **Given** the production service configuration, **when** it is reviewed or deployed, **then** a supervised worker process, health/restart policy, ownership, secrets delivery and rollback steps are present and proven on the actual hosting tier; two web services alone do not meet this acceptance.
- **Dependencies:** S-06.03.06 (durable homes for remaining state), S-06.02.38 (traceable worker failures). **Size:** M. **Audit:** A25 / D-270. **Indicator:** due jobs processed without a manual web session.
- **Constraint:** deployment runtime and any paid background-worker cost require operator approval; do not invent free worker capacity or claim a worker running from a CLI binary alone. Work order: `docs/work-orders/S-06.02.40-durable-deployment-worker.md`.

#### S-06.02.41 — Contacts beyond row 500 are reachable
**As a** campaign owner, **I want** accessible server-backed contact pages, **so that** no contact becomes invisible in larger campaigns.
- **Given** more than 500 contacts, **when** the owner moves between pages, **then** each row is reachable through the existing authenticated offset API and the total/range remain correct.
- **Given** search/status change, campaign change or records removed, **when** the list reloads, **then** the page index returns to a valid slice without mixing another campaign's data.
- **Dependencies:** none. **Size:** S. **Audit:** A23 / D-271. **Work order:** `docs/work-orders/S-06.02.41-contacts-pagination.md`.

#### S-06.02.42 — Enrichment exports cannot run spreadsheet formulas
**As a** CRM operator, **I want** CSV/XLSX reports to be safe when opened in a spreadsheet, **so that** untrusted Apollo/input text cannot execute formulas.
- **Given** a leading formula/control sequence in a report cell, **when** CSV/XLSX is generated, **then** it is literal text in the actual saved document; numeric cells retain their numeric type.
- **Given** the same text in persisted CRM or credit/exclusion/rejection ledger rows, **when** reports are generated, **then** original state and dedupe keys remain unchanged; readable snapshots are safely escaped.
- **Dependencies:** none. **Size:** S. **Audit:** A19 / D-272. **Work order:** `docs/work-orders/S-06.02.42-spreadsheet-formulas.md`.

#### S-06.02.43 — Logout revokes the copied browser session
**As a** workspace user, **I want** logout to invalidate my current cookie at the server, **so that** a copied cookie cannot still open private CRM data after logout.
- **Given** a signed session, **when** logout succeeds, **then** replay of that exact token is denied across process restarts and PostgreSQL/SQLite backends; other valid devices remain signed in.
- **Given** a storage outage during revocation, **when** logout is attempted, **then** the app does not claim the token was revoked.
- **Dependencies:** none. **Size:** M. **Audit:** A06 / D-273. **Work order:** `docs/work-orders/S-06.02.43-logout-revocation.md`.

#### S-06.02.44 — Download the entire filtered Contacts result
**As a** campaign owner, **I want** a CSV of all contacts matching the filters on screen, **so that** I can share a specific review list without losing rows beyond the current page.
- **Given** filters and 500+ contacts, **when** I download, **then** the attachment contains every matching contact, with stable named columns and spreadsheet-safe text; no private mail bodies or internal notes.
- **Given** an oversized or changing result, **when** I export, **then** no believable incomplete file is returned. The prior full-campaign report remains unchanged.
- **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** M. **Work order:** `docs/work-orders/S-06.02.44-filtered-contact-download.md`.

#### S-06.02.45 — Category and variant filters for contacts
**As a** campaign owner, **I want** to filter by values present in my current campaign, **so that** I can review a particular audience or A/B cohort.
- **Given** the active campaign, **when** its filters load, **then** only campaign categories and variants appear; combining them with text/status searches uses the existing server query.
- **Given** a filter change, **when** the list refreshes, **then** it restarts at page one with the right count.
- **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.45-contact-facet-filters.md`.

#### S-06.02.46 — Marked-only contacts remain reachable
**As a** campaign owner, **I want** to see only the contacts I marked with the existing checkbox, **so that** I can review the selected pool across all pages.
- **Given** marked contacts, **when** I filter and export, **then** the SQL query counts/returns only them; no client-side 100-row approximation or implicit send occurs.
- **Given** an uncheck or campaign switch, **when** records reload, **then** persistent selection remains associated with the correct campaign and empty/stale pages recover.
- **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.46-marked-only-contacts.md`.

#### S-06.02.47 — Large send queues are paginated
**As a** campaign owner, **I want** to navigate 100-row pages, **so that** I can inspect every queued contact without transferring every recipient's details at once.
- **Given** 211 contacts, **when** the Queue opens, **then** its default result has at most 100 items and the total and next-page controls make every contact reachable.
- **Given** an invalid page limit or offset, **when** queried, **then** the API rejects it; the actual sender is unchanged.
- **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.47-queue-pagination.md`.

#### S-06.02.48 — Campaign-wide queue counters do not mislead
**As a** campaign owner, **I want** accurate ready/approval/replied totals across the campaign, **so that** I know what genuinely needs review independent of the page I opened.
- **Given** a filtered or later page, **when** loaded, **then** counts cover every campaign membership using the sender's due-time logic.
- **Given** a future-scheduled approved draft or terminal contact, **when** counting, **then** it does not appear as ready; totals do not override final live-send preflight.
- **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.48-global-queue-totals.md`.

#### S-06.02.49 — Queue views focus on an actionable cohort
**As a** campaign owner, **I want** All, Approved and due, Needs approval and Replied views, **so that** I can review the right queue rows without scrolling past unrelated contacts.
- **Given** a view change, **when** applied, **then** filtering happens before paging and starts at page one with a view-specific total.
- **Given** an empty view, **when** opened, **then** the screen explains that this view has no members; switching views never approves or sends mail.
- **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.49-actionable-queue-views.md`.

#### S-06.02.58 — Factual AI cache never answers from similar-but-changed evidence
**As a** CRM operator, **I want** extracted facts and summaries to be reused only for the identical input, **so that** changed source values never silently receive an old answer.
- **Given** a long factual document cached with 42 million or an approval statement, **when** the number or negation changes, **then** the broker must miss the old entry before any answer is returned.
- **Given** the exact same canonical payload and same generation contract, **when** requested again, **then** the exact cached answer is returned without an additional provider call.
- **Given** a private workspace or denied policy, **when** another workspace/policy or mailbox source requests the entry, **then** no cached data crosses that boundary or bypasses the scanner.
- **Dependencies:** none. **Size:** M. **Audit:** A12 / D-360. **Work order:** `docs/work-orders/S-06.02.58-exact-factual-cache.md`.

#### S-06.02.59 — Cached AI answers belong to the model that generated them
**As a** model operator, **I want** each cached result linked to its original selected model, instructions and output options, **so that** comparing models never labels an older answer as a fresh result from another model.
- **Given** identical content but a changed selected model on the same provider key, **when** the broker runs, **then** the new model is called instead of reusing another model's output.
- **Given** changed system instructions or generation options, **when** the same model is selected, **then** the cache misses even when payload and provider stay the same.
- **Given** an identical canonical payload and generation contract, **when** the result is cached, **then** the log identifies a cache hit, not a billable send, and the actual model is reported without any raw prompt in the index.
- **Dependencies:** none. **Size:** M. **Audit:** A13 / D-361. **Work order:** `docs/work-orders/S-06.02.59-cache-model-provenance.md`.

#### S-06.02.60 — Atomic provider quota and USD budget enforcement (A11)
**As a** workspace owner, **I want** simultaneous AI calls to reserve their request and dollar budgets before transport, **so that** no worker can exceed the limits by racing another worker.
- **Given** one remaining request and two independent workers, **when** they race, **then** no more than one provider call begins.
- **Given** a daily USD cap, **when** priced concurrent requests, retries, crashes or uncertain outcomes occur, **then** reservations and reconciled totals prevent unaccounted spend.
- **Given** a corrupt/unavailable quota ledger or a different workspace account, **when** a request starts, **then** the system fails closed as needed and never leaks or resets another workspace's count.
- **Dependencies:** production egress, storage and traceable errors; Definition of Ready and current audit WIP gate still apply. **Size:** L. **Audit:** A11 / D-362. **Work order:** \`docs/work-orders/S-06.02.60-atomic-ai-quota.md\`.

#### S-06.02.61 — Email provider setup failure is recorded before any send (A16)
**As an** operator, **I want** provider-initialisation errors to fail or retry a claimed email job safely, **so that** the worker never leaves it stuck in sending.
- **Given** a permanent factory error before transport, **when** a job is claimed, **then** it reaches a truthful terminal state with a traceable reason and no send.
- **Given** temporary or unknown setup errors, **when** the worker continues, **then** it performs only bounded safe pre-send retry or an explicit failure and continues unrelated due jobs.
- **Given** an actual ambiguous post-send outcome, **when** retries are considered, **then** existing do-not-resend quarantine is unchanged.
- **Dependencies:** real durable email worker and traceable-errors contract before customer deployment; normal board readiness/WIP rules apply. **Size:** M. **Audit:** A16 / D-363. **Work order:** \`docs/work-orders/S-06.02.61-email-provider-setup.md\`.

### F-06.03 — Data that survives a deploy on the free plan  *(E-06)*

#### S-06.03.08 — Owner storage readiness and data-loss risk
- **Given** local or hosted configuration, **when** the owner requests `GET /api/v1/storage/readiness`, **then** the API lists each inventoried store's durability and safe next steps without private paths or credentials.
- **Given** a hosted CRM but remaining local media, routines and outboxes, **when** viewing the report, **then** it still blocks production readiness.
- **Given** a normal team workspace, invalid token or no authentication, **when** requesting the report, **then** it returns 403/401 with no store details.
- **Given** the operating-system mount `/` or temporary storage, **when** checking durability, **then** that is not certified as a persistent customer disk.
- **Status:** IN_REVIEW; tests: `tests/test_hosted_storage_readiness.py`; external backup Q-29 and S-06.03.06 remain open.

The owner's answer to `Q-26` (2026-09-25): stay on Render's free plan and keep
the data in a free hosted PostgreSQL. Design: `docs/architecture/HOSTED_STORAGE.md`.

#### S-06.03.01 — Every store's backend is known
- **Given** the running app, **when** the inventory test runs, **then** it lists
  every store opened at start-up, its backend today and its size on a real
  install, and the design's table is generated from it.
- **Dependencies:** none. **Size:** S.

#### S-06.03.02 — Keys, settings and logins live in the hosted database
- **Given** `OFFSETX_DATABASE_URL` and `OFFSETX_SECRETS_KEY` set once, **when** a
  key is typed in Connectors and the container is destroyed and recreated,
  **then** the key, the AI settings, trust changes, workspace logins and the
  egress log are all still there.
- **Given** a wrong or missing `OFFSETX_SECRETS_KEY`, **when** the app starts,
  **then** it refuses with a sentence, never starts with keys it cannot read.
- **Dependencies:** `S-06.03.01`, `S-06.02.31`. **Size:** L.

#### S-06.03.03 — The CRM lives in the hosted database
- **Given** the CRM suite, **when** it runs, **then** it passes against SQLite
  and PostgreSQL alike.
- **Given** an existing SQLite CRM, **when** the copy tool runs, **then** every
  table's count reconciles, and the inverse copy has been run once.
- **Dependencies:** `S-06.03.02`. **Size:** XL.

#### S-06.03.04 — The hosted database is backed up outside itself
- **Given** the hosted topology, **when** a night passes, **then** an encrypted
  export exists outside the database; restoring it into an empty one gives the
  same counts, and the owner can download it.
- **Dependencies:** `S-06.03.03`. **Size:** M. **Why:** Neon's free restore
  window is 6 hours.

#### S-06.03.05 — Production refuses a half-hosted install
- **Given** `OFFSETX_PRODUCTION=1`, **when** some stores are hosted and others
  are on a wiped disk, **then** the app refuses to start and names them.
- **Dependencies:** `S-06.03.04`, `S-06.03.06`. **Size:** S.

#### S-06.03.06 — Every other store has a decided home
*(Filed 2026-10-02 from the inventory, `S-06.03.01`: these stores had no phase.)*
- **Given** the inventory's stores marked "not decided" — template results,
  sent-mail recall, tools and companions, routines, meetings, imagery, posts,
  trends, the Notion link, the timers, privacy requests, the crawler — **when**
  each is decided, **then** it is either in the hosted database with the same
  proof as `S-06.03.02`, or marked disposable with the screen that holds it
  saying so.
- **Dependencies:** `S-06.03.03`. **Size:** L.

#### S-06.03.07 — A local install's decision belongs to that install
*(Filed 2026-10-03 from the fresh-context review of `S-06.03.03`, finding 10.)*
- **Given** two installs with their own disks sharing one hosted database,
  **when** the first has imported or skipped its local CRM file — or its keys
  and logins (`D-210`) — **then** the second is still asked about its own
  files, and neither install's data is hidden without a word.
- **Open first:** whether two installs may share one database at all is the
  owner's call; if not, the start refuses the second instead.
- **Dependencies:** `S-06.03.03`. **Size:** S.

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
| Hard-cancelling an already-running provider/browser operation to hit an exact millisecond latency wall | The current interfaces cannot prove rollback of a side effect. S-06.02.03 stops *new* work at the operation boundary and reports any one-operation overrun. Revisit only when every effectful operation has a cancellation/idempotency contract. |

---

## 5. Definition of the increment

One increment = one vertical slice a person can use end to end. Not "the backend
for X". The next increment is chosen by the owner from `READY`, and only when
`IN_PROGRESS` is empty.


### F-06.04 — Campaign Management  *(E-06, product feature)*

Manage a campaign's configuration and lifecycle from the Campaigns screen. This is a complete product feature, not a single field-level story.

- **Given** an existing email campaign, **when** the owner opens Edit settings, **then** they can update name, daily cap, IANA timezone, send window/weekdays, working-day follow-ups, approval mode and experiment settings; the values survive restart.
- **Given** an invalid timezone, control variant or cap, **when** saved, **then** the backend refuses without altering prior settings.
- **Given** an active or paused campaign, **when** the owner types ARCHIVE and confirms, **then** it becomes archived without deleting evidence; restoring it resumes in a *paused* state, requiring a later explicit Resume.

**Dependencies:** existing campaign create/PATCH backend (DONE). **Size:** L. **Feature specification:** `docs/features/campaign-management.md`.

### F-06.05 — Campaign Blueprint Reuse  *(E-06, product feature)*

Safely replicate configuration without replicating people, credentials or outbound effects.

- **Given** a configured campaign with real members, drafts and sends, **when** the owner duplicates its settings, **then** the new independent campaign inherits only validated campaign configuration and is inserted paused, with zero recipients, drafts or messages.
- **Given** a repeated duplicate request with the same idempotency key, **when** retried, **then** it returns the same campaign instead of creating an extra one.
- **Given** a missing source, invalid clone name, or forbidden copy-of-contacts fields, **when** sent, **then** the protected API refuses without side effects.

**Dependencies:** campaign create/PATCH backend (DONE). **Size:** L. **Feature specification:** `docs/features/campaign-blueprints.md`.

### F-06.06 — Campaign Performance Intelligence  *(E-06, product feature)*

An actual CRM-data performance panel, independent from the experimental A/B statistical report.

- **Given** a campaign, **when** the owner opens Performance, **then** the server reports unique contacted recipients, outbound messages, replies, uncontacted members, completed/stopped counts and draft state, with a refresh button and no model inference.
- **Given** a contact manually marked replied without being sent email, **when** the reply rate is shown, **then** the unsent record is excluded from its numerator and denominator; the denominator is unique contacts with outbound messages.
- **Given** a non-email campaign, **when** metrics are opened, **then** the email-specific reply rate is shown as N/A, rather than mislabelling the campaign.

**Dependencies:** existing campaign/CRM send/draft storage (DONE). **Size:** L. **Feature specification:** `docs/features/campaign-performance.md`.


### F-06.07 — Audience Management Workspace  *(E-06, product feature)*

**As a** campaign operator, **I want** to add, recognise and manage exact recipient records without needing a file import, **so that** outreach data is accurate and selected recipients can be stopped without contacting anyone unintentionally.
- **Given** a valid name and email, **when** added manually, **then** one campaign membership is created, never a draft or send; repeated or shared emails are linked without overwriting an existing global contact profile.
- **Given** up to 100 explicitly selected campaign membership IDs, **when** the owner marks/unmarks/stops, **then** all IDs are checked to belong to this campaign before an atomic transaction; foreign or missing IDs cause no mutation.
- **Given** an operator stops selected contacts, **when** the queue is subsequently evaluated, **then** those contacts are excluded by the existing sender; replied/completed contacts are not revived.
- **Dependencies:** existing CRM memberships, selection, authenticated API (DONE). **Size:** L. **Feature design:** `docs/features/audience-workspace.md`.

### F-06.08 — Campaign Launch Readiness Center  *(E-06, product feature)*

**As a** campaign operator, **I want** to see what is missing before starting email operations, **so that** I can correct drafts, settings and daily limits without failed runs or unsafe sends.
- **Given** an email campaign, **when** the readiness screen opens, **then** its active status, audience size, approved/due draft candidates and remaining daily cap are checked using saved CRM state; failures link to the appropriate screens.
- **Given** an empty, paused or unapproved campaign, **when** evaluated, **then** its local readiness is false with an actionable reason.
- **Given** a locally passing campaign, **when** readiness is green, **then** it still states that provider availability, suppression, permission, recipient validity and final send rules have **not** been cleared. No send or approval occurs.
- **Dependencies:** existing queue store, source of truth, auth and send gates (DONE). **Size:** L. **Feature design:** `docs/features/campaign-launch-readiness.md`.

### F-06.09 — Campaign Activity & Audit Timeline  *(E-06, product feature)*

**As a** campaign operator, **I want** to inspect what changed and when in this campaign, **so that** activity is explainable without raw database access or private message disclosure.
- **Given** many recorded events, **when** the timeline opens or changes page, **then** it returns stable, authenticated 50-event slices and an accurate total.
- **Given** an event-type filter, **when** selected, **then** the server counts and returns only events of that exact type; event choices are derived from current campaign records.
- **Given** potentially sensitive historical payloads, **when** events are displayed, **then** only whitelisted operation/count metadata is shown, never raw message/customer content. Historical events are unchanged.
- **Dependencies:** existing campaign event writer and auth (DONE). **Size:** L. **Feature design:** `docs/features/campaign-activity-timeline.md`.


### F-06.10 — Reply Inbox & Human Triage  *(E-06, product feature)*

**As a** campaign operator, **I want** a central review inbox of received responses, **so that** I can prioritise real conversations and plan human next steps.
- **Given** a received campaign reply, **when** it is saved by the existing sync engine, **then** the newest message appears in a bounded, paginated conversation list, initially unreviewed.
- **Given** an authorised review decision, **when** I assign a valid outcome and note, **then** that campaign membership's triage state updates without changing shared global contact outcome, canceling reply-stop protection or sending mail.
- **Given** another campaign's membership ID, **when** read or updated, **then** it is not leaked or modified.
- **Dependencies:** existing CRM inbound messages and protected campaign routes (DONE). **Size:** L. **Feature spec:** `docs/features/reply-inbox-triage.md`.

### F-06.11 — Contact Communication History  *(E-06, product feature)*

**As a** campaign operator, **I want** a chronology of messages for one campaign contact, **so that** I can understand what was sent and received before following up.
- **Given** a campaign member with sent and received mail, **when** History opens from Contacts or Reply Inbox, **then** the server returns only this member's timestamped correspondence, newest-first, in bounded pages.
- **Given** message bodies longer than 2,000 characters, **when** presented, **then** a truncated preview notice appears; raw provider JSON/keys are never returned.
- **Given** a foreign campaign member, **when** requesting history, **then** the API rejects it without revealing content.
- **Dependencies:** existing outbound/inbound `messages` table and campaign membership (DONE). **Size:** L. **Feature spec:** `docs/features/contact-communication-history.md`.

### F-06.12 — Human Follow-up Task Manager  *(E-06, product feature)*

**As a** sales or outreach operator, **I want** durable human-action tasks with due times, owners and completion status, **so that** leads do not get forgotten after a reply or meeting.
- **Given** a campaign or its contact, **when** I create a task with an explicit timezone-aware due date, **then** it is saved, optionally linked to that campaign member, and survives process restarts and database moves.
- **Given** two edits based on the same revision, **when** one saves first, **then** the stale edit receives HTTP 409; no colleague's work is overwritten.
- **Given** a task, **when** I edit, complete, reopen or filter due/overdue work, **then** saved state and completed timestamp are consistent, without any automatic external contact.
- **Dependencies:** versioned CRM schema, storage backup and campaign membership (DONE for code path; hosted restore gate open). **Size:** L. **Feature spec:** `docs/features/human-followup-tasks.md`.


### F-06.13 — Qualified Reply-to-Sales Conversion (E-06, product feature)

**As a campaign owner**, I want to turn reviewed positive incoming replies into deduplicated sales opportunities, so that commercial work follows evidence instead of duplicate manual entry.

- Given an actual received reply triaged Positive/Meeting, when I explicitly confirm Convert in Contact 360, then create or link one Sales Tracker lead in the same workspace, without sending mail, resuming automation or copying reply bodies.
- Given a previously promoted membership, when conversion repeats, then return its existing link. Given the same email in another campaign, reuse the existing lead without changing its fields.
- Given zero or multiple matching sales leads, missing qualified review, or foreign membership, when conversion is attempted, then use a safe deterministic create/deny path and preserve sender status.
- **Dependency:** F-06.10 Reply Inbox, SalesTracker, versioned CRM schema. **Size:** L. **Specification:** docs/features/reply-to-sales-conversion.md.

### F-06.14 — Contact 360 Workspace (E-06, product feature)

**As a campaign owner**, I want one reliable campaign contact view for identity, reply context, tasks and opportunity, so that I can act without navigating five separate modules.

- Given a campaign membership, when Contact 360 opens, then show only allowlisted identity, status, message counts, latest reply metadata, triage, next task and linked opportunity.
- Given a foreign membership, when requested, then deny without disclosing details; never include raw provider payloads, full email bodies or private contact notes.
- Given reviewed positive reply, when no opportunity is linked, then offer explicit promotion; support opening message history and follow-ups.
- **Dependency:** F-06.11, F-06.12, F-06.13. **Size:** L. **Specification:** docs/features/contact-360-workspace.md.

### F-06.15 — Daily Action Command Center (E-06, product feature)

**As a campaign operator**, I want source-backed human priorities in one campaign queue, so that overdue work, unreviewed replies and neglected commercial opportunities do not get lost.

- Given saved CRM records, when priorities loads, then show actual overdue open tasks, most recent unreviewed replies and linked open sales leads with missing/stale touch information, not a generated estimate.
- Given filtering, when paging a large campaign, then apply type filters before page limits and preserve truthful full-campaign counts.
- Given a cross-campaign record, when reading this queue, then exclude it; never mutate a task, approve a draft or send a message from the report.
- **Dependency:** F-06.10–F-06.14. **Size:** L. **Specification:** docs/features/daily-action-command-center.md.


### F-06.16 — Unified CRM Search  *(E-06, product feature)*

**As a CRM operator**, I want to find a person across all campaigns and the existing Sales Tracker from one search box, **so that** I can use the correct existing record rather than duplicate it.

- **Given** a 2–100 character name, email or company query, **when** searching Contacts or Sales, **then** I see accurately counted, bounded, server-filtered pages of only relevant identity/pipeline metadata.
- **Given** a person in multiple campaigns, **when** opening them, **then** the result contains one global contact, its membership count, and a correct paired campaign/member ID for Contact 360.
- **Given** a literal `%` or `_`, **when** searching, **then** it is escaped rather than becoming a wildcard; raw message bodies/notes and unauthorised workspaces are not searched.
- **Dependencies:** existing Contacts/SalesTracker and authenticated API. **Size:** L. **Feature specification:** `docs/features/unified-crm-search.md`.

### F-06.17 — Account Intelligence Workspace  *(E-06, product feature)*

**As a CRM operator**, I want to view company-level relationship coverage from saved contacts, campaigns and sales opportunities, **so that** I can identify account engagement and outstanding work.

- **Given** company names with only case/outer whitespace differences, **when** viewing Accounts, **then** records group under one normalized company key, without guessing legal entities or merging uncertain subsidiaries.
- **Given** an account, **when** opening its profile, **then** I see its people, sales opportunities, distinct campaign coverage, actual message counts and open contact-linked tasks, with links to campaign Contact 360.
- **Given** high-volume accounts, **when** paging, **then** filtering happens in SQL and aggregate counts do not inflate from many-to-many joins.
- **Dependencies:** existing global contacts, campaign memberships, tasks and SalesTracker. **Size:** L. **Feature specification:** `docs/features/account-intelligence-workspace.md`.

### F-06.18 — Campaign-to-Revenue Attribution  *(E-06, product feature)*

**As a campaign owner**, I want defensible reporting from recorded campaign links to actual sales outcomes, **so that** I can understand commercial progress without double-counting revenue.

- **Given** a sales lead linked to multiple campaigns, **when** attribution is calculated, **then** exactly one campaign receives its lead/won/cash credit by earliest persisted link; others retain their link counts without revenue duplication.
- **Given** campaign activity, **when** viewing the report, **then** I see recorded contacts, replied/qualified statuses, linked memberships, allocated leads, won/lost deals, booked value and recorded cash with full-campaign totals unaffected by paging.
- **Given** no linked sale or different currencies, **when** reporting, **then** zero or clear warnings appear; no misleading causal claim or invented FX conversions.
- **Dependencies:** F-06.13 campaign-sales links and existing SalesTracker. **Size:** L. **Feature specification:** `docs/features/campaign-revenue-attribution.md`.


### F-06.19 — CRM Data Quality Centre *(E-06, product feature)*

**As a CRM operator**, I want a safe data-quality workbench with accurate filters, **so that** I can prioritise corrections and review potential contact-to-sales overlaps without destructive automated merges.

- **Given** incomplete contacts, **when** choosing a specific issue or all issues, **then** I get only matching records with all applicable missing-email/company/title, no-campaign or exact-email-sales-overlap flags and stable pagination.
- **Given** a possible sales overlap, **when** inspecting the result, **then** it is explicitly only a review candidate, cannot trigger an automatic merge, and reveals no message bodies or sensitive notes.
- **Given** a filtered result, **when** navigating to a related campaign or Sales Tracker, **then** a real operator path is available; all filters and page bounds are validated.
- **Dependencies:** contacts, campaign membership and SalesTracker. **Size:** L. **Specification:** docs/features/crm-data-quality.md. **Status:** IN_REVIEW pending executed tests/security checks.

### F-06.20 — Campaign Comparison Dashboard *(E-06, product feature)*

**As a campaign manager**, I want to compare saved contact, outbound, inbound, qualification and sales-link outcomes across campaigns, **so that** I can see actual patterns without false lift or duplicated messages.

- **Given** repeated messages, **when** comparing campaigns, **then** contacted and replied counts are unique per campaign membership, not inflated by multiple messages.
- **Given** no outbound contacts, **when** computing descriptive reply rate, **then** it shows N/A rather than an invented percentage; the denominator and measurement limitations are visible.
- **Given** many campaigns, **when** searching and paging, **then** counts and results remain correct and operators can open Campaign activity.
- **Dependencies:** existing campaign membership, persisted message events, triage and sales links. **Size:** L. **Specification:** docs/features/campaign-comparison.md. **Status:** IN_REVIEW.

### F-06.21 — Follow-up Performance Centre *(E-06, product feature)*

**As a sales operations lead**, I want human follow-up workload and timeliness reports across campaigns, **so that** I can spot overdue queues and redistribute work through existing forms.

- **Given** open/done saved tasks, **when** viewing the report, **then** overdue, completed and on-time counts reflect saved due/completed times, never inferred activity.
- **Given** variations in assignee labels and unassigned tasks, **when** grouping, **then** whitespace/case-normalised display groups appear without implying real login ownership or permissions.
- **Given** a campaign filter and many labels, **when** paging, **then** overall counts remain unchanged and the UI links to follow-up work.
- **Dependencies:** F-06.12 human follow-up tasks, existing campaigns. **Size:** L. **Specification:** docs/features/followup-performance.md. **Status:** IN_REVIEW.


## F-06.22 — Duplicate Contact Review

Backend-first, owner-requested next independent CRM feature. Three sub-stories (discovery, bounded inspection, API security) and acceptance are specified in `docs/features/crm-duplicate-review.md`. No automatic merge and no schema changes. Q-27 prevents production DONE until customer-data scope is resolved.


#### S-06.02.55 — Numeric evidence preserves sign, precision, magnitude (A18 / D-354)
**As an** operator verifying research, **I want** a numeric claim to match the exact number and unit supported by a captured quote, **so that** an incorrect figure is not presented as proven.
- **Given** `value='42'`, **when** the host-captured quote says `-42`, `42.7`, `42,000` or `42%` as a different figure, **then** the claimed `42` must not be marked supported by the observed-finding verification path.
- **Given** a matching signed, decimal or grouped figure, **when** a quote belongs to the captured page, **then** it may be supported with correct sign/unit/locale handling; conflicting or ambiguous representations fail closed.
- **Given** a derived number, **when** its inputs exist, **then** unverified arithmetic cannot be reported as an observed fact merely because the model claims a total.
- **Dependencies:** S-11.02.03 (existing verifier). **Size:** M. **Open audit:** A18 / D-354. **Work order:** docs/work-orders/S-06.02.55-numeric-claim-integrity.md. Not READY; test-first fix requires normal verification gates.

#### S-06.02.57 — A09: Enter handlers cannot bypass human approval
**As an** operator, **I want** Enter-key browser actions to stop before any page-defined side effect, **so that** a website cannot execute send, publish, submit or delete without my approval.
- **Given** a focused textarea, rich-text editor, ordinary input without a form, non-English button or an event handler attached to the document, **when** the agent requests Enter without human approval, **then** no Enter key event is dispatched and the run needs confirmation.
- **Given** a failed or ambiguous focused-element inspection, **when** Enter is requested, **then** it fails closed without sending the key; failure to identify a safe target is not permission.
- **Given** an actual safe navigation key or an explicit trusted confirmation, **when** the action is invoked, **then** the original key behaviour is retained; the model cannot supply confirmed=true.
- **Given** a controlled real Chromium form with JavaScript Enter handlers, **when** the agent tries unconfirmed Enter, **then** the page does not change to SUBMITTED; the same action with trusted owner confirmation is observable.
- **Dependencies:** S-11.03.03 (previously implemented). **Size:** S. **Work order:** docs/work-orders/S-06.02.57-enter-approval.md. **Audit:** A09, partial remediation pending independent confirmation/DOM-change tests.

#### S-06.02.56 — Full generated-image decoding fails safely (A21 / D-355)
**As an** image reviewer, **I want** corrupt generator output rejected before entering approval, **so that** bad pixels and truncated payloads cannot pass or crash the whole batch.
- **Given** a well-shaped PNG header but no image data, **when** the image-gate entry point processes it, **then** the candidate fails the decodes gate, even above the byte threshold.
- **Given** truncated GIF/JPEG/WebP/PNG or hostile dimensions, **when** the gate checks it, **then** it returns a failed `GateReport`, not an uncaught parsing exception or an unsafe memory allocation.
- **Given** a real valid image, **when** checked with supported format, dimensions and aspect ratio, **then** the result succeeds; rejecting bad images must not reject ordinary good ones.
- **Dependencies:** existing image gate and image runner; bounded decoder choice and limits must be decided before READY. **Size:** M. **Open audit:** A21 / D-355. **Work order:** docs/work-orders/S-06.02.56-complete-image-decoding.md.
