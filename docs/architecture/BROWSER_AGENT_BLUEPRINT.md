# The browser agent

*How off_CRM gets hands.*

Every capability in this project so far has been a **producer**: it makes
timelines, pictures, captions, posts. This is the first one that is a
**consumer** — something that goes out and reads the web the way a person does,
and can therefore reach the places an API cannot.

The target is Strawberry's feature set, which is written down at the bottom of
this file, feature by feature, with how each one lands here.

---

## Read this first: what a Chromium fork buys, and what it costs

Strawberry is **a fork of Chromium**. Not an extension, not automation on top —
a rebuilt browser. That is a real engineering decision and it deserves a real
answer rather than an imitation.

**What the fork buys them:** the agent runs inside *your* browser session. Your
cookies, your SSO, your passkeys, your extensions. So it can open LinkedIn as
you, read a dashboard behind Okta as you, use a CRM you are already signed into.
No API keys, no OAuth dance, no scraping infrastructure.

**What the fork costs:** a C++ patch set maintained against upstream Chromium
forever, a ~100GB checkout, hours of compile per build, code signing for macOS
and Windows, an auto-update channel, and a security team's worth of
responsibility for shipping a browser people put their passwords into.

**off_CRM does not fork Chromium.** It gets the same property a different way:

```
      Strawberry                          off_CRM
┌──────────────────────┐        ┌──────────────────────────┐
│  forked Chromium     │        │  YOUR Chrome / Chromium  │
│  agent compiled in   │        │  launched with           │
│  ────────────────    │        │  --remote-debugging-port │
│  your profile        │        │  --user-data-dir=<yours> │
└──────────────────────┘        └───────────┬──────────────┘
                                            │ CDP over a WebSocket
                                ┌───────────▼──────────────┐
                                │  off_CRM browser agent   │
                                └──────────────────────────┘
```

**The Chrome DevTools Protocol** is how every debugger, every recorder and every
automation tool talks to Chromium. It is JSON over a WebSocket, it is
documented, and it is stable. Pointed at your *real profile directory*, it gives
the agent the same session a fork would: the same cookies, the same logins, the
same passkeys, because it **is** the same browser.

**What is genuinely different, stated plainly:**

| | Fork | CDP attach |
|---|---|---|
| Your real session | yes | yes |
| Branded as one app | yes | no — it is a Chrome window |
| Works with your extensions | yes | yes |
| Chrome must be started by off_CRM | no | **yes** — see below |
| Ships a browser you must trust | yes | no |
| Buildable by one person | no | yes |

**The one real wrinkle.** Chrome refuses `--remote-debugging-port` when the
profile is the *default* one, unless `--user-data-dir` names a path explicitly
— a deliberate 2024 change that stopped malware reading cookies out of a running
browser. And Chrome allows one process per profile directory. So off_CRM has to
be the thing that starts the browser, and a Chrome already open on that profile
has to be closed first. That is a sentence in the setup screen, not a design
problem, and it is the honest cost of not shipping our own browser.

### Why not Playwright

Playwright would be one line instead of a CDP client. It is not used here for
three reasons, and the third is the one that decides it:

1. Its value is *launching and managing* browsers. We are attaching to one that
   already exists, so most of it is unused.
2. It pulls ~300MB of browser binaries we would never run — the whole point is
   your browser, not a downloaded one.
3. **The house style is a hand-written client.** This project wrote its own
   EBML demuxer, its own ISO-BMFF parser and its own WebM muxer rather than take
   ffmpeg, for reasons written down in `VIDEO_EDITOR.md`. CDP is far simpler
   than any of those: `Target`, `Page`, `Runtime`, `Input`, `DOM`, `Network`. A
   few hundred lines, fully understood, no supply chain.

---

## Where this sits against what already exists

A great deal of the Strawberry feature list is **already built here** under
different names. Naming that honestly is what stops this becoming a rewrite.

| Strawberry feature | off_CRM today | What is left |
|---|---|---|
| Model routing, failover | `ai/registry.py` + `ai/broker.py` — providers as config, per-model trust tiers, quota-aware failover | nothing |
| Memory | `ai/context.py` — durable facts with owner approval | scope to a companion |
| Credits | `ai/quota.py` — local per-provider counting | pre-run estimate, per-run ledger |
| Local-first data | the entire product | nothing |
| 3-level permissions | `ai/broker.py` data classes + `ai/tools.py` owner-pinned tools | a per-tool rule layer and a chat-scoped override |
| Routines | `distribution/automation.py` — interval service with steps | cron, event triggers, per-routine agents |
| Reports/artifacts | `notebook.py`, video renders, image assets | decks and spreadsheets |
| Skills | — | new |
| Companions | — | new |
| Agent runs, sub-agents, PLAN.md, work trace | `ai/modes.py` orchestrated mode is the seed | new |
| MCP servers | — | new |
| Browser as fallback | — | **new, and it is the centre** |
| Meeting transcription | `video/engine.py` has a transcriber seam | OS audio capture |
| Safety countdowns | — | new |

**The rule that governs all of it** is already written and already enforced by a
test: `ai/broker.py` is the only thing in this codebase that may talk to a model
provider, and `tests/test_ai_egress_wall.py` fails the build if a second one
appears. The browser agent is a *tool user*, not a model caller. It asks the
broker, like everything else.

---

## The eight stages

Each is shippable on its own and each is useful before the next exists.

### Stage 1 — The browser  ·  `browser/`

The hands. Nothing above it works without this.

- `cdp.py` — a WebSocket client for the DevTools Protocol. Sessions, targets,
  request/response correlation, events.
- `session.py` — find the browser, launch it against the owner's profile, attach,
  survive it being closed.
- `page.py` — the action vocabulary, and it is deliberately **small and closed**:
  `goto`, `click`, `type`, `press`, `scroll`, `select`, `wait_for`, `read`,
  `screenshot`, `download`. A model names one of these. It cannot describe a new
  one — the same rule `ai/tools.py` already applies to Docker.
- `perceive.py` — turning a page into something a model can act on. **Not raw
  HTML**: an accessibility-tree snapshot with stable element handles, which is
  a tenth the tokens and does not break when a class name changes.
- `policy.py` — per-domain rules. Which sites may be driven at all, which
  actions need a countdown, which are refused outright.
- `trace.py` — every action, appended, with a screenshot reference.

**Verification:** drive a real Chromium here, in this repo's tests, and assert
on the pixels and the DOM afterwards — the same standard the video work was held
to.

### Stage 2 — Runs, plans and the trace  ·  `agent/`

The loop. A goal in, a sequence of tool calls out, with a person able to watch,
steer and stop it.

- `run.py` — the agent loop: perceive → decide → act → record, until done or
  stopped. Every decision goes through `ai/broker.py`.
- `plan.py` — **PLAN.md as the single source of truth.** One markdown file per
  run. The model reads it as memory; the UI parses it into a live checklist; the
  owner edits it to steer. It is a *file*, not a database row, because the model
  is good at markdown and because the owner can open it.
- `trace.py` — append-only. Every search, click, tool call and sub-agent step,
  with timing and cost. Auditable, resumable, and it is also the "watch it
  think" view — one record serving both.
- `steer.py` — interrupt, queue a follow-up mid-run, resume from a trace.

**The design decision that matters:** a run is resumable because the trace is
complete. Not "we save progress" — the trace *is* the progress, so resuming is
replaying it into the context and continuing.

### Stage 3 — Companions and skills  ·  `agent/companions.py`, `agent/skills.py`

- **Companions** — persisted agent profiles. A name, instructions, its own
  memory scope, its own files, its own granted integrations, its own permission
  rules. "Sales Sally" is a row, not a prompt someone retypes.
- **Skills** — reusable procedures, fetched on demand.

**Memory and skills are deliberately separate**, and Strawberry is right about
why: facts and processes have opposite retrieval needs. A fact ("our ICP is
Series-A fintech in the EU") is small and belongs in *every* prompt. A procedure
("how we qualify an inbound lead") is long and belongs in the prompt *only when
that job is running*. Putting them in one store means either bloating every
prompt or losing the facts.

### Stage 4 — Sub-agents  ·  `agent/subagent.py`

A companion spawns focused children, each with its own scoped task, its own
PLAN.md and its own trace.

**They exist for context isolation, not speed.** A run that reads forty LinkedIn
profiles fills its context with thirty-nine irrelevant ones. A child that reads
one profile and returns four fields keeps the parent's context clean. Parallelism
is a bonus.

Bounded: a depth limit and a fan-out limit, because a spawner that can spawn
spawners is an unbounded cost.

### Stage 5 — The crawler  ·  `crawl/`

The always-on half. What you asked for as *"a crawler that stays on the internet
and scrapes things for us."*

- **A frontier, not a script.** A priority queue of URLs with politeness state
  per host — crawl delay, last-hit time, robots.txt with its own cache. This is
  the difference between a crawler and a for-loop.
- **Revisit scheduling.** A page that changed yesterday is worth checking
  tomorrow; one that has not changed in a year is not. Adaptive intervals per
  URL, so a fixed crawl budget goes where the change is.
- **Content addressing.** Store by hash; a page that came back identical costs
  one row, not one document.
- **Three fetchers behind one seam**, which `discovery.py` already has the shape
  of: `requests`+Scrapling for static HTML, Crawl4AI for JavaScript, and — new
  — **the browser agent for anything that needs a session**.
- **Extraction as declared data**, the same pattern `video/effects.py` uses: a
  selector pack per site kind, so adding a source is a row and not a parser.

### Stage 6 — MCP and integrations  ·  `integrations/`

- **An MCP client** — HTTP/SSE and local stdio. This is the highest-leverage
  item in the entire blueprint: it is how off_CRM inherits every tool anyone
  else has already built, without building any of them.
- **Native OAuth apps** — Gmail, Sheets, Slack, HubSpot, Salesforce, GitHub.
  Typed tools, fast and structured, for the handful worth doing properly.
- **The browser as the fallback** — and this is why coverage is not limited to
  what is integrated. No API? Drive the UI.

Every one of them registers into the same tool registry `ai/tools.py` already
defines, so the permission model is written once.

### Stage 7 — Trust  ·  `agent/permissions.py`

- **Three levels**: a global mode, then a per-integration per-tool rule
  (ask / allow / disable), then a chat-scoped override that expires with the
  conversation.
- **Safety countdowns.** A visible delay before anything that sends, deletes,
  spends or publishes. Not a confirm dialog — a countdown you can watch and
  cancel, because a dialog trains people to click through and a countdown
  does not.
- **Credits.** `ai/quota.py` counts provider calls already. This adds a per-run
  ledger and, more importantly, an **estimate before the run** — plain browsing
  free, every agent action metered.

### Stage 8 — Meetings and artifacts

- **Meeting transcription with no bot in the call**: microphone plus
  system-audio loopback, captured locally. ScreenCaptureKit on macOS, WASAPI on
  Windows, PulseAudio monitor on Linux. Works on Meet, Zoom, Teams and in a
  room, because it is capturing the *machine*, not joining the *meeting*.
  Transcription goes through the seam `video/engine.py` already has.
- **Reports and artifacts** — decks, dashboards, spreadsheets, PDFs from
  gathered data. `notebook.py` and the video renderer are the precedent.

**This stage is honest about its platform cost.** System-audio loopback is
OS-specific native code. On Linux it is a PulseAudio monitor source and is
straightforward; on macOS it needs ScreenCaptureKit and a signed helper; on
Windows, WASAPI loopback. That is real work and it is the last stage for that
reason.

---

## The part that is about you, not about the code

You asked for this so off_CRM can find leads on LinkedIn, Instagram and YouTube.
Three different things are being asked for there and they have three different
answers.

**YouTube — build freely.** An official Data API, public data, already partly
wired in `distribution/trends.py`. No agent needed.

**Instagram and LinkedIn via their APIs — narrow but legitimate.** Instagram's
Business Discovery returns limited data about *business* accounts. LinkedIn's
posting and profile APIs need partner approval. Both are declared in
`distribution/platforms.py` with what they actually allow.

**Driving your own logged-in session — legitimate, and it is what this is for.**
You opening LinkedIn and reading a profile you can already see is not scraping;
it is you, using a computer. The agent doing it at your speed, on your machine,
in your session, is the same act automated.

**Where it stops being that** is volume. A crawler running unattended against
LinkedIn at machine speed is a different thing from you reading profiles: it
breaches their terms explicitly, it gets the account permanently restricted, and
where the people are in the EU or UK it is a GDPR problem — scraped personal
data with no lawful basis and no notice to the person.

So the policy layer in Stage 1 is not decoration:

- **Per-domain rate limits that mirror human pace**, not machine pace, on any
  site being driven through a session.
- **Session-driven sites are excluded from the unattended crawler.** The agent
  may visit LinkedIn when you ask it to. The Stage 5 frontier may not have
  LinkedIn in it.
- **The existing `BLOCKED_SOCIAL_DOMAINS` list stays** for the headless engines.
  It was right for what it governs — anonymous scraping — and the browser agent
  is a separate path with its own rules, not a way around it.

That is stated here rather than buried, because it is the difference between a
tool that makes your CRM better and one that loses you an account.

---

## Feature-by-feature: every item on your list

Nothing below is omitted or merged.

### Agent core

| Feature | Where it lands | How |
|---|---|---|
| **Companions** | Stage 3 | A stored profile: name, instructions, memory scope, files, granted skills, integration grants, permission rules. Selected per run. |
| **Agent runs** | Stage 2 | A run is a goal plus a loop. Distinct from chat: a run has a PLAN.md, a trace, a budget and a stop button. |
| **Sub-agents** | Stage 4 | A parent spawns children with scoped tasks. Each gets its own PLAN.md and trace. Depth and fan-out bounded. |
| **PLAN.md** | Stage 2 | One markdown file per run. Model memory, UI checklist and owner steering surface — one artefact serving three readers. |
| **Work trace** | Stage 2 | Append-only, every step, with cost and timing. Auditable, resumable, and the "watch it think" view. |
| **Model routing** | **built** | `ai/registry.py` + `ai/broker.py`. Provider-agnostic, trust-tiered, quota-aware, auto-failover. |
| **Interrupt / steer / resume** | Stage 2 | Queue follow-ups mid-run; cut in and redirect; resume from the trace after a stop. |

### Knowledge layer

| Feature | Where | How |
|---|---|---|
| **Memory** | **built**, extended in Stage 3 | `ai/context.py` already stores durable facts with owner approval. Gains a companion scope. |
| **Skills** | Stage 3 | Procedures, global or companion-scoped, fetched on demand. Separate store from memory, for the retrieval reason above. |
| **Meeting transcription** | Stage 8 | Mic + system-audio loopback captured locally; no bot joins the call. Transcription through the existing broker seam. |
| **Reports / artifacts** | Stage 8 | Decks, dashboards, spreadsheets, PDFs. `notebook.py` and the video renderer are the precedent. |

### Automation

| Feature | Where | How |
|---|---|---|
| **Routines** | Stage 7, on `distribution/automation.py` | Cron and interval exist. Gains event triggers (incoming mail, webhook) and the ability to fire an agent run rather than a fixed pipeline. |
| **Notification rules** | Stage 7 | A run that found nothing deletes itself. Only a finding notifies. This is a *policy on the trace*, which is why it comes after the trace exists. |

### Integrations

| Feature | Where | How |
|---|---|---|
| **Native OAuth apps** | Stage 6 | Gmail, Sheets, Slack, HubSpot, Salesforce, GitHub. Typed tools into `ai/tools.py`. |
| **MCP servers** | Stage 6 | HTTP/SSE and stdio client. The highest-leverage item here: it inherits other people's tools instead of building them. |
| **Browser as fallback** | Stage 1 | Any site with no API gets driven by clicking. This is why coverage is not limited to what is integrated. |

### Trust and control

| Feature | Where | How |
|---|---|---|
| **3-level permissions** | Stage 7 | Global mode → per-integration per-tool rule → chat-scoped override. |
| **Safety countdowns** | Stage 7 | A visible, cancellable delay before send / delete / purchase / publish. A countdown rather than a dialog, because dialogs train people to click through. |
| **Local-first data** | **built** | Cookies, history and passwords never leave the machine. The egress broker already makes "what left" answerable, and `Egress.tsx` already shows it. |
| **Credits** | Stage 7 | `ai/quota.py` counts already. Adds a per-run ledger and a pre-run estimate. Plain browsing free; agent actions metered. |

---

## Stage 1, as built

`offsetx_apollo_builder/browser/` — six modules, 32 tests, three of them driving
a real Chromium.

| File | What it is |
|---|---|
| `cdp.py` | The DevTools Protocol over a WebSocket. One read loop routing by shape: an `id` resolves a waiter, a `method` fans out to listeners. Every command bounded by a timeout. |
| `session.py` | Finds a browser, launches it against the owner's profile, attaches. Attach-before-launch, because a browser the owner is working in should be joined and not replaced. |
| `perceive.py` | The accessibility tree as an indented outline with integer handles. Walked depth-first, because CDP's flat list is **not** document order. |
| `policy.py` | Per-domain rules: pace, attended-only, refused actions, countdown actions. |
| `page.py` | Ten verbs. Real mouse and key events, not JavaScript shortcuts. |
| `trace.py` | Append-only JSONL with screenshots beside it. No delete, no edit, no truncate. |

### Verified against a real browser, not a mock

1. **The whole stack, end to end.** Chromium 141 launched, a page opened,
   the accessibility tree read, an email typed with real key events, the field
   re-read *from the browser* to prove the value took, a Send button refused
   without confirmation and accepted with it, and the page's own output —
   `sent to hello@acme.test` — read back. Then a screenshot with a real PNG
   header, and handle `9999` refused by name.
2. **A dropdown chosen by its visible label**, with the `change` event firing —
   which is the half a value assignment silently skips.
3. **The policy against the live browser**: `file:///etc/passwd` refused,
   `linkedin.com` refused in unattended mode.
4. **A bad command raises rather than hangs**, and the connection is still
   usable afterwards — the point of failing one waiter instead of the socket.

### Three real bugs, all found by running it

- **`select` was advertised and never implemented.** The vocabulary listed ten
  verbs and `Page` had nine. There is a test now asserting both directions:
  every verb implemented, and nothing implemented that is not advertised.
- **CDP's node list is not document order.** The first snapshot put a footer
  link above the paragraph it follows. Fixed by walking `childIds` depth-first.
  A snapshot is prose to a model, and prose whose sentences are shuffled is
  prose that gets misread.
- **Thirteen leaked Chromium processes.** `start_new_session=True` — used so the
  browser survives off_CRM being interrupted — makes the browser its own
  process-group leader, so `terminate()` reached the parent and none of the
  renderers. Found by counting `chrome` processes after a test run. It presented
  as *flaky tests*, which is what a resource leak usually presents as.

---

## What this blueprint will not pretend

- **A Chromium fork is not being built.** The CDP path gets the session, which is
  what the fork was for. It does not get a browser with your name on the icon.
- **Meeting audio needs native code per platform.** Linux is easy, macOS needs a
  signed helper, Windows needs WASAPI. That is why it is Stage 8 and not Stage 2.
- **Stages are not a weekend.** Stage 1 alone is a CDP client, a perception
  layer, a policy layer and a trace, verified against a real browser.
- **The crawler will not be pointed at LinkedIn.** The agent will, when you ask
  it to. Those are different systems on purpose, and the reason is in the
  section above.
