# Where everything stands

*Plain English. Every segment of off_CRM, what state it is in, and who has to do
what next.*

Verified from the repository board on 2026-08-27. Recompute the numbers with
`python scripts/verify_board.py`; this summary records that output rather than
claiming to update itself.

---

## The seven states, and what each one honestly means

| | State | What it means | Board column |
|---|---|---|---|
| ✅ | **DELIVERED** | Built, tested, and a script re-ran the test to prove it | `DONE` |
| 🔬 | **RESEARCHED** | We know exactly how. The decision is made. No code yet | `READY` |
| 📋 | **PLANNED** | Written down properly — who it is for, how we'd know it works | `BACKLOG` |
| 🚧 | **BUILDING** | Being worked on right now. Never more than 2 at once | `IN_PROGRESS` |
| 🧪 | **PROVING** | Code exists, but the complete evidence command has not passed here | `IN_REVIEW` |
| 🔒 | **WAITING ON YOU** | The engineering is fine. Something outside the code is missing | `BLOCKED` |
| ⏸️ | **PARKED** | Deliberately cut, with a written reason and what brings it back | `DEFERRED` |

**Why seven and not three.** "Not done" hides several completely different
situations: *we haven't decided how*, *we've decided and haven't built it*, and
*we built it but have not proved it here*, and *we can't build it until you do
something*. Those need different actions from different people, so they get
different words.

---

## The scoreboard

```
✅ DELIVERED        23 stories   ███████████████████████
🔬 RESEARCHED        1 story     █
🔒 WAITING ON YOU    3 stories   ███
📋 PLANNED          26 stories   ██████████████████████████
🚧 BUILDING          0 stories
🧪 PROVING           1 story     █
⏸️ PARKED            0 stories

71 requirements tracked · 0 orphans · 49% of acceptance criteria behind a test
```

---

# Part 1 — What is DELIVERED ✅

**These work today. You can run them.** Each one has a test that a script
re-runs, so "it works" is checkable rather than something I said.

## The video engine — the biggest finished piece

| What it does | Story | Proof |
|---|---|---|
| A timeline that **cannot** hold a broken edit | S-01.01.01 | 49 tests |
| Preview and export always agree | S-01.01.02 | 29 tests |
| Real video, real sound, real footage in the file | S-01.02.01 | 46 tests |
| Slow-mo, freeze, reverse — smooth and exact | S-01.02.02 | 34 tests |
| **48 visual effects, 124 named looks**, each with a strength slider | S-01.02.03 | 49 tests |
| **Give it clips + a style → it cuts the whole video** | S-01.03.01 | 94 tests |
| **Give it a topic → it writes the script and makes the video** | S-01.03.02 | 31 tests |

> **What that means:** type *"why nobody reads changelogs"* and you get back a
> finished, graded, captioned, vertical video. Nobody touches a timeline.

## The safety gate

| What it does | Story | Proof |
|---|---|---|
| **Push / Ignore / Edit** — nothing publishes without you | S-01.04.01 | 37 tests |
| Your daily posting cap. Nothing crosses it, ever | S-01.04.02 | 19 tests |

> The engine can also work out the *ideal* posting rate from your goal — and
> then it **waits for you to agree**. That was your call and it's built that way.

## The browser hands

| What it does | Story | Proof |
|---|---|---|
| Talks to a real Chrome, no extra software | S-02.01.01 | 32 tests |
| Reads a page by **meaning**, not code | S-02.01.02 | 32 tests |
| **Ten actions, and no way to run code** | S-02.01.03 | 32 tests |
| Speed limits and no-go zones, enforced | S-02.01.04 | 32 tests |
| Writes down every action, un-editably | S-02.01.05 | 32 tests |

## The box, and getting logged in

| What it does | Story | Proof |
|---|---|---|
| A container with internet and **no path to your files. Not one** | S-03.01.01 | 30 tests |
| The old code box still cannot have the network at all | S-03.01.02 | 72 tests |
| **Sign in once, inside the box** — and your password is stored nowhere | S-03.02.01 | 21 tests |

> **What "stored nowhere" means, exactly:** not encrypted, not hashed, not held
> for a second. No function in the sign-in code will even *accept* a password —
> a test reads every signature and fails the build if one ever does. You type it
> into the browser yourself, and the only thing that comes back is *yes, that
> worked*. Two of those tests are the promise itself: one types a password into
> a test login page and then searches **every byte off_CRM wrote** for it; the
> other kills the browser and restarts it to prove the login survives.

## The honesty machinery

| What it does | Story | Proof |
|---|---|---|
| A script that re-runs every "done" claim and catches lies | S-06.02.06 | 29 tests |
| A decision you record unblocks work; deleting it doesn't | S-06.02.07 | 29 tests |

## Protected bulk email — the safe core

| What it does | Story | Proof |
|---|---|---|
| Permission, relationship and global suppression fail closed | S-08.01.01 | 3 focused tests |
| Durable immutable jobs survive restarts without blind duplicate retries | S-08.01.02 | 6 focused tests |
| Fresh domain authentication and an isolated SES lane | S-08.01.03 | 2 focused tests |
| Signed feedback suppresses bad recipients and pauses unhealthy campaigns | S-08.01.04 | 3 focused tests |

> This improves deliverability; it does not guarantee inbox placement. Real AWS,
> DNS and mailbox-cohort testing are still required before removing the beta label.

---

# Part 1B — What is PROVING 🧪

### 🧪 S-08.01.05 — Operators control delivery without hidden live sends
The API, signed public unsubscribe and exact live-send confirmation pass their
two Python tests. The Deliverability screen and its frontend test exist, but
this clean environment cannot install one uncached npm dependency under the
current network policy. It stays `IN_REVIEW` until that test is re-run.

---

# Part 2 — RESEARCHED 🔬 (decided, not built)

**One thing left. You approved all three decisions on 2026-08-25** — the other
two are now built and have moved up to Part 1.

### 🔬 S-03.02.02 — The vault
Session keys encrypted, **one key per account**, so one leak isn't all of them.
And the AI **never sees a key** — it says "click button 7", the browser holds
the secret.
**Decided (Q-01):** your computer's keychain, with a passphrase as backup.

---

# Part 3 — WAITING ON YOU 🔒

**The code is not the problem here.** These need something only you can get.

### 🔒 S-01.05.01 — Actually posting to YouTube
**What's missing:** a Google Cloud project with *YouTube Data API v3* turned on.
**Effort:** free, about 10 minutes, no human review.
**This is the fastest path to a real post.**

### 🔒 S-01.05.02 — Instagram, Facebook, TikTok, LinkedIn, X
**What's missing:** their app reviews. Meta review, TikTok audit, LinkedIn
partner programme.
**Effort:** weeks of calendar time. None of it is engineering.

### 🔒 S-01.05.03 — Reading real view counts back
Waits on the first one.

---

# Part 4 — PLANNED 📋 (26 stories)

Written down properly. Nothing here is a mystery — each has a description, a
test plan, and what it depends on.

### Making the agent actually think and act *(the next big unlock)*
| Story | In one line |
|---|---|
| S-02.02.01 | Give it a goal → it works out the steps itself |
| S-02.02.02 | Its to-do list is a file **you can edit mid-job** to steer it |
| S-02.02.03 | Stop it halfway, resume later from where it was |
| S-02.02.04 | 5 seconds to hit cancel before anything sends or deletes |

### The team of agents
| Story | In one line |
|---|---|
| S-04.01.01 | Named agents with their own instructions and memory |
| S-04.01.02 | Playbooks loaded only when relevant |
| S-04.01.03 | An agent sends helpers off, so its own head stays clear |
| S-04.01.04 | **Scout · Maker · Poster · Analyst · Director** wired to what exists |

### Finding what's working out there
| Story | In one line |
|---|---|
| S-05.01.01 | A proper crawler that remembers politeness and revisits what changes |
| S-05.01.02 | Adding a new website to watch = one row, not new code |
| S-05.01.03 | Take a competitor's hit post apart → rebuild the *shape*, not the content |

### Making it usable by a team
| Story | In one line |
|---|---|
| S-03.02.03 | Disconnect a platform and its login is gone for good |
| S-06.01.01 | Each person: own AI keys, own logins |
| S-06.01.02 | Permissions: everywhere → per-tool → just-this-chat |
| S-06.01.03 | See what a job will cost **before** it runs |
| S-06.01.04 | Jobs that run on a timer or when an email arrives |
| S-06.01.05 | Deploy it properly, and a way back when a release is bad |

### The unglamorous things that decide whether it's real
| Story | In one line |
|---|---|
| S-06.02.01 | A scan proving no secret ever entered a prompt |
| S-06.02.02 | Every endpoint checks who you are and what you sent |
| S-06.02.03 | A job that costs too much stops itself |
| S-06.02.04 | Delete someone's data and it's gone from **everywhere** |
| S-06.02.05 | The whole app usable by keyboard and screen reader |

### Borrowing other people's work
| Story | In one line |
|---|---|
| S-07.01.01 | **MCP** — inherit tools other people already built |
| S-07.01.02 | Proper Gmail / Sheets / Slack / HubSpot connections |
| S-07.01.03 | Meeting notes with no bot joining the call |
| S-07.01.04 | Turn findings into a deck, a spreadsheet or a PDF |

---

# Part 5 — PARKED ⏸️

### ⏸️ S-03.01.02 — Keeping the code-box locked down
**Why parked:** it's already locked down, and nothing right now touches it.
**Comes back when:** someone starts building the browser box next to it.

---

# Part 6 — Who does what

| Job | Who | How it happens |
|---|---|---|
| Decide **what** gets built next | **You** | Pick from `READY` on `BOARD.md` |
| Decide **how** it gets built | The engineer/AI | Ponytail rules: reuse first, smallest correct thing |
| Answer a question that blocks work | **You** | Add a decision to `OPEN_QUESTIONS.md` |
| Decide something is **cut** | **You** | Nothing gets dropped by the builder |
| Prove something is done | The verifier | `python scripts/verify_board.py` |
| Get a Google Cloud project / app review | **You** | Nobody else can |

---

# Part 7 — How to check any of this yourself

```bash
python scripts/verify_board.py
```

It re-runs every test behind every "delivered" claim. If I said something was
done and it isn't, **this goes red**. It caught me twice while I was writing it.

```bash
python scripts/verify_board.py --skip-tests   # just the counts, 2 seconds
```

---

# The short version

**The hard engineering is largely done.** A real video editor, a real effects
engine, a protected bulk-email core, a real safety layer between you and every
AI provider, and real browser hands. That is the part that takes months.

**What's left is mostly wiring** — the loop that makes the parts act on their
own, and the vault that makes it safe to let them.

**Three things need you and only you:** a Google Cloud project, the platform app
reviews, and picking what gets built next.
