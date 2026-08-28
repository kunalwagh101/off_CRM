# What off_CRM is made of

*Plain English. Every part of the system, what it does, and whether it exists.*

```
  ✅  built and tested        ◐  half there        ⬜  not built yet
```

Every ⬜ and ◐ has a backlog ID. If something here has no ID, it is not planned
— it is forgotten, and that is a bug in the plan rather than in the code.

---

## The one-paragraph version

off_CRM finds leads and ideas, makes content, asks you before publishing, and
runs guarded outreach. Today the making and review paths are finished; local
publishing works while real platform adapters wait on external access. The
protected bulk-email core is built, with its dashboard awaiting one frontend
proof run. What is still missing is the loop that ties the parts together: an
**agent** that can use a browser like a person, so the parts stop needing you to
press each one in turn.

---

## 1. The Brain — deciding which AI to use, and what it may see

**Where:** `offsetx_apollo_builder/ai/` · 25 files, ~11,000 lines

This is the part almost nobody builds and everybody needs. It sits between your
CRM and every AI provider, and it decides three things: *which model*, *may this
model see this data*, and *what actually left the machine*.

| Part | What it does | State |
|---|---|---|
| `broker.py` | **The only door to any AI provider.** A test fails the build if a second one appears | ✅ |
| `registry.py` | Providers as config, not code. Each model has a trust tier | ✅ |
| `tiers.py` | Which model may see which kind of data. A cheap model can never win a job it is not cleared for | ✅ |
| `quota.py` | Counts every call locally, so a provider that lies cannot hide it | ✅ |
| `context.py` | Memory — facts about you, injected into prompts, approved by you | ✅ |
| `modes.py` | One model, or several checking each other, or a head model planning | ✅ |
| `verify.py` | Checking is cheaper than writing, so output gets checked | ✅ |
| `sandbox.py` | A locked room for AI-written code. **No network, no files, no database** | ✅ |
| `tools.py` | The AI names a tool. It cannot invent one | ✅ |
| `log.py` | Every outbound call, recorded. This is what "local-first" is *proved* by | ✅ |
| **Skills** | Playbooks fetched only when relevant, so a long procedure doesn't bloat every prompt | ⬜ S-04.01.02 |
| **Companions** | Named agents with their own instructions and memory | ⬜ S-04.01.01 |
| **MCP client** | Borrow tools other people already built | ⬜ S-07.01.01 |

> **Why this matters:** everything else in this document is safe *because* this
> layer exists. It is the reason an agent holding your LinkedIn session is not a
> terrifying idea.

---

## 2. The Hands — using a browser like a person

**Where:** `offsetx_apollo_builder/browser/` · 10 files, ~3,000 lines

Built last week. This is what lets off_CRM reach anything that has no API —
which is most of the useful web.

| Part | What it does | State |
|---|---|---|
| `cdp.py` | Talks to a real Chrome over its debug wire. Hand-written, no Playwright | ✅ |
| `session.py` | Starts *your* browser with *your* profile, so it is already logged in | ✅ |
| `perceive.py` | Reads a page as **meaning**, not HTML. Every button gets a number | ✅ |
| `page.py` | **Ten verbs.** Click, type, scroll, read… and no way to run code | ✅ |
| `policy.py` | Per-site speed limits, and which sites a robot may never visit alone | ✅ |
| `trace.py` | Writes down every single action. Cannot be edited or deleted | ✅ |
| `box.py` | The container it all runs in. Network yes, your files never | ✅ |
| `guard.py` | Refuses a request to an undeclared domain before Chrome sends it | ✅ |
| `identity.py` | The six platforms, and where this workspace stands with each | ✅ |
| `signin.py` | Opens the login page, waits for **you**, reads back only whether it worked | ✅ |
| **The run loop** | Goal in → look, think, act, repeat → done | ⬜ S-02.02.01 |
| **PLAN.md** | The agent's to-do list, as a file you can edit mid-run to steer it | ⬜ S-02.02.02 |
| **Stop & resume** | Cut in halfway; carry on later from where it stopped | ⬜ S-02.02.03 |
| **Countdowns** | 5 seconds to hit cancel before anything sends or deletes | ⬜ S-02.02.04 |
| **Sub-agents** | One agent sends helpers off to do side-quests | ⬜ S-04.01.03 |

> **The key idea:** the AI never gets to write code that runs in your browser.
> It picks from ten verbs and says a number. That is the whole reason a nasty
> web page cannot hijack it.

---

## 3. The Makers — turning an idea into a video

**Where:** `offsetx_apollo_builder/video/` (13 files, ~8,500 lines) and
`imagery/` (4 files, ~1,000 lines)

This is the biggest finished piece. It is a real video editor.

| Part | What it does | State |
|---|---|---|
| `timeline.py` | The document. **Cannot hold an invalid edit** — clips physically cannot overlap | ✅ |
| `edits.py` | ~45 named operations. Undo survives closing the tab | ✅ |
| `effects.py` | 48 pixel operations, 124 named looks. Every one has a strength slider | ✅ |
| `presets.py` | Transitions, animations, speed curves — as data rows, not code | ✅ |
| `recipes.py` | 8 video shapes: hook, list, story, montage, demo | ✅ |
| `assembly.py` | **Material + a recipe → a finished cut.** Nobody touches a timeline | ✅ |
| `director.py` | A topic → a model picks the shape and writes the words | ✅ |
| `mixdown.py` | The sound, planned as an envelope | ✅ |
| `gates.py` | Checks the exported file is really the right size and length | ✅ |
| `captions.py` | Speech → subtitles | ✅ |
| `imagery/` | Pictures, and the swipe that keeps or bins each one | ✅ |
| Frontend `video/` | Browser-side: demuxers, WebGL shaders, the exporter | ✅ |

> **What it can already do, today:** you type *"why nobody reads changelogs"* and
> it produces a graded, captioned, scored, exported vertical video. That works
> now.

---

## 4. The Judge — you, saying yes or no

| Part | What it does | State |
|---|---|---|
| Video review queue | **Push / Ignore / Edit.** Nothing publishes without you | ✅ |
| Image swipe | Keep or bin each picture; every swipe scores the generator | ✅ |
| The edit-diff | Measures what *you* changed after the machine's attempt | ✅ |
| Learning from it | Nothing reweights the recipes yet — the data is only collecting | ⬜ *(needs a few hundred verdicts first)* |

> **The rule the whole product runs on:** a machine that makes things
> unattended must never also be the thing that decides they go out.

---

## 5. The Mouth — posting, and how much

**Where:** `offsetx_apollo_builder/distribution/` · 11 files, ~3,600 lines

| Part | What it does | State |
|---|---|---|
| `platforms.py` | What each platform actually allows, and what it refuses | ✅ |
| `engine.py` | Plan → approve → schedule → publish | ✅ |
| `pacing.py` | Works out the ideal rate from your goal and **waits for you** | ✅ |
| Your daily cap | Per account. Nothing crosses it — not the goal, not the AI | ✅ |
| `trends.py` | Watches YouTube channels for what is rising | ✅ |
| `publishers.py` | Local outbox — the whole pipeline, testable, no real account risked | ✅ |
| **YouTube adapter** | Real uploads via the official API | ◐ *needs your Google Cloud project* |
| **Instagram / TikTok / LinkedIn / X** | Real posting | ⬜ *needs their app review — weeks, and on you* |

---

## 6. The Courier — protected bulk email

**Where:** `offsetx_apollo_builder/outreach/deliverability/`,
`offsetx_apollo_builder/api/email_delivery.py`, and the Deliverability screen

| Part | What it does | State |
|---|---|---|
| Policy preflight | Permission, relationship, suppression and frequency rules fail closed | ✅ S-08.01.01 |
| Durable queue | Immutable jobs, one-worker claims, bounded retries and ambiguous-send quarantine | ✅ S-08.01.02 |
| Domain + SES lane | Fresh SPF, DKIM, DMARC and alignment evidence before bulk mail | ✅ S-08.01.03 |
| Feedback + health | Signed SNS events, bounce/complaint suppression and automatic pause | ✅ S-08.01.04 |
| Operator control centre | API and UI for preflight, health and exact-confirmed live queueing | ◐ S-08.01.05 *(frontend proof pending)* |

> It can manage high-volume sending safely. It cannot buy reputation or promise
> the inbox; the sender still needs a domain, DNS records and a provider such as SES.

---

## 7. The Finder — what is happening out there

**Where:** `discovery.py`, `research.py`, `dedupe.py`

| Part | What it does | State |
|---|---|---|
| Scrapling engine | Fetches and parses ordinary web pages | ✅ |
| Crawl4AI engine | Pages that need JavaScript | ◐ *installed by an optional extra* |
| Safety rails | robots.txt, no internal addresses, social sites blocked for headless | ✅ |
| `dedupe.py` | Stops the same company arriving twice under two names | ✅ |
| **A real crawler** | A queue that remembers politeness and revisits what changes | ⬜ S-05.01.01 |
| **Extraction packs** | Adding a new source = one row, not a new parser | ⬜ S-05.01.02 |
| **Competitor teardown** | Take a hit post apart → shape, pacing, hook → rebuild it | ⬜ S-05.01.03 |

---

## 8. The Vault — your logins  ⬜ **none of this exists yet**

This is the next thing to build, and the decisions are now made:

| Part | The decision you just approved | ID |
|---|---|---|
| Browser box | A container with internet but **no path to your files** | S-03.01.01 |
| Allow-list | Deny by default when unattended; allow-with-policy when you are watching | S-03.01.01 (Q-02) |
| Logging in | You sign into **LinkedIn first**, inside the box | S-03.02.01 (Q-03) |
| Passwords | **Never stored. Anywhere.** You type them yourself | S-03.02.01 |
| Session keys | Encrypted, one key per account | S-03.02.02 |
| Master key | OS keychain, passphrase as fallback | S-03.02.02 (Q-01) |
| The AI's view | It **never sees a cookie.** It says "click 7"; the browser has the secret | S-03.02.02 |
| Disconnecting | Removes the session for good | S-03.02.03 |

---

## 9. The Foundations — storage, API, screens

| Part | What it does | State |
|---|---|---|
| `db/` | SQLite locally, Postgres if you want. Same code | ✅ |
| `api/` | ~4,100 lines of endpoints | ✅ |
| Frontend | 17 screens: campaigns, contacts, drafts, images, video, posting, AI | ✅ |
| Workspaces | Every table already separates people. Your keys are yours | ◐ S-06.01.01 *(works; not surfaced in the UI)* |
| **Permissions** | Global → per-tool → this-chat-only | ⬜ S-06.01.02 |
| **Cost estimate** | What a run will cost, *before* it runs | ⬜ S-06.01.03 |
| **Deploy & rollback** | A way back when a release is bad | ⬜ S-06.01.05 |
| **Keyboard / screen reader** | The UI usable without a mouse | ⬜ S-06.02.05 |

---

## 10. The Rules — how we know any of this is true

| Part | What it does | State |
|---|---|---|
| `PRODUCT_BACKLOG.md` | 54 stories, 71 requirements, **zero orphans** | ✅ |
| `BOARD.md` | The only place status lives. Chat does not count | ✅ |
| `DEFINITION_OF_DONE.md` | Six boxes. All of them, every time | ✅ |
| `scripts/verify_board.py` | **Re-runs every "done" claim's test.** Catches lies, including mine | ✅ |
| `TRACEABILITY.md` | Requirement → story → test → code, unbroken | ✅ |

---

## The honest scoreboard

```
Built and tested        20 stories      44% of all acceptance criteria
Built, proof pending     1 story        deliverability dashboard
Ready to start           3 stories      the vault and the box
Waiting in the backlog  26 stories
Blocked externally       3 stories      platform access and reviews
Deferred                 1 story        with a reason and a trigger
```

**Roughly two-thirds of the *hard* engineering is done** — the timeline, the
effects, the export, the AI safety layer, the browser hands. What is left is
mostly *connecting* work: the loop that makes the parts act on their own, and
the vault that makes it safe to let them.

### The three things only you can unblock

1. **A Google Cloud project** with YouTube Data API v3 enabled → real uploads.
2. **Meta / TikTok / LinkedIn app review** → real posting there. Weeks, not days.
3. **Nothing else.** Everything in section 8 is now decided and buildable.
