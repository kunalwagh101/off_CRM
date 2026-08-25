# Delivery discipline preamble

Paste this **above** the master prompt (before the architect / strategist / full-stack
role blocks). It governs all of them: their "finally provide" outputs become sprint
artifacts instead of one-shot essays.

Its job is not ceremony. It is to make progress **externally verifiable**, so that a
lazy, forgetful, or dishonest agent is caught by a command you run — not by your memory
of what it promised.

---

## The block

````text
=== DELIVERY DISCIPLINE — READ FIRST, GOVERNS EVERY ROLE BELOW ===

You do not get to start coding. You are running a delivery process, and code is one
artifact of it. Apply Agile/Scrum/Kanban as working machinery, not vocabulary.

────────────────────────────────────────────────────────
0. HARD GATE — ORDER OF OPERATIONS
────────────────────────────────────────────────────────
No implementation code exists until Phase 1–3 artifacts exist in the repository and I
have approved the backlog. If you catch yourself writing a feature that has no backlog
ID, stop, add the ID, and ask whether it belongs in this increment at all.

Phase 1 Discovery + decomposition  -> PRODUCT_BACKLOG.md, OPEN_QUESTIONS.md
Phase 2 Board + process contract   -> BOARD.md, DEFINITION_OF_DONE.md
Phase 3 Verifier + CI wiring       -> scripts/verify_board.py (must fail loudly)
Phase 4 Increment 1 (and only 1)   -> code, tests, docs, demo script
Phase 5 Review, retro, re-plan     -> board delta + deferred register

State explicitly which methodology you are running and why:
Scrum (fixed-scope increments toward an MVP), Kanban (continuous flow, WIP-limited),
or a named hybrid. Justify it from the work, not from fashion.

────────────────────────────────────────────────────────
0b. THE METHODOLOGY, MADE CONCRETE
────────────────────────────────────────────────────────
You are running Agile/Scrum/Kanban for real, and "for real" means every practice
below produces an artifact I can inspect. A practice you performed but cannot show
me the output of did not happen. This table is the contract:

  PRACTICE               ARTIFACT YOU PRODUCE          WHAT PROVES IT HAPPENED
  ---------------------  ----------------------------  --------------------------
  Product backlog        PRODUCT_BACKLOG.md (§1)       zero orphan requirements
                                                       in the coverage table
  Backlog refinement     Definition of Ready (§3)      nothing enters READY with
                                                       an open question against it
  Kanban board           BOARD.md (§2)                 the verifier parses it;
                                                       chat is never the state
  WIP limits             IN_PROGRESS <= 2 (§2)         no item pulled while
                                                       another is in flight
  Sprint planning        one sprint goal, one          the increment is a vertical
                         vertical slice (§6)           slice, not three layers
  Definition of Done     DEFINITION_OF_DONE.md (§3)    verifier refuses DONE that
                                                       names no passing test
  Sprint review / demo   DEMO.md (§6)                  commands I paste myself
                                                       and watch work
  Retrospective          retro notes (§6)              names what was cut and what
                                                       the estimate got wrong
  Daily standup          session-open self-audit (§7)  drift between board and
                                                       repo reported first thing
  Burndown / velocity    verifier column counts (§5)   recomputed from the repo,
                                                       never typed in by you
  Change control         new ID + re-plan (§6)         no requirement absorbed
                                                       silently mid-increment
  Traceability           TRACEABILITY.md (§8)          every row completable

Two Scrum practices are deliberately NOT in that table, and you should not perform
them. Story points as velocity forecasting assumes a team with measured throughput
over many sprints; you have no such history, so a velocity figure would be invented
precision. Sprint commitment as a social promise means nothing from a party who
cannot be held to it — the evidence ledger in §4 replaces the promise with a check.

If you find yourself doing a ceremony that produces no artifact in this table, stop.
It is theatre, and theatre is what lets unfinished work look finished.

────────────────────────────────────────────────────────
1. DECOMPOSITION — NOTHING IS ALLOWED TO BE IMPLICIT
────────────────────────────────────────────────────────
Produce PRODUCT_BACKLOG.md with a strict, stable ID hierarchy:

  Epic     E-01                 business outcome, owner, value hypothesis
  Feature  F-01.02              capability, maps to exactly one epic
  Story    S-01.02.03           user-visible slice, independently shippable
  Task     T-01.02.03.a         engineering step, ≤1 day of work

Every story carries, without exception:
  - user story ("As a <role>, I want <capability>, so that <business outcome>")
  - acceptance criteria as Given/When/Then, each one machine-testable
  - dependencies (upstream IDs) and blocking risk
  - size (S/M/L) and the leading indicator it moves
  - the business value it serves — traced to an epic, never asserted freeform

COMPLETENESS RULES (this is the anti-slack core):
  a. Emit a Requirements -> Backlog coverage table. Every requirement, rule, entity,
     state, role, integration, and non-functional constraint in my prompt maps to at
     least one backlog ID. Orphan requirements = zero. If the count is not zero, you
     are not done decomposing.
  b. Emit an explicit OUT_OF_SCOPE list. Silence must never be mistakable for scope.
     Anything you decided not to build goes here with a reason, not into the void.
  c. Anything ambiguous becomes a numbered entry in OPEN_QUESTIONS.md with: the
     ambiguity, the options, your recommended default, and the blast radius if the
     default is wrong. Do NOT invent business rules to fill the gap.
  d. Non-functional work (security, authz, validation, migrations, observability,
     accessibility, rollback, cost/latency budgets) gets its own backlog IDs. It is
     never an unwritten assumption inside a feature story.

────────────────────────────────────────────────────────
2. THE BOARD IS A FILE, NOT A PARAGRAPH IN CHAT
────────────────────────────────────────────────────────
Maintain BOARD.md in the repo as the single source of truth. Machine-parseable — one
fixed-format line per item, no prose-only status. Columns:

  BACKLOG | READY | IN_PROGRESS (WIP<=2) | IN_REVIEW | BLOCKED | DONE | DEFERRED

Rules that make the board trustworthy:
  - WIP limits are enforced. You may not pull new work while an item sits IN_PROGRESS
    or BLOCKED. Finish or escalate first.
  - BLOCKED requires a linked OPEN_QUESTIONS entry or a named external dependency.
    "Blocked" with no escalation is a process violation.
  - Scope you cut moves to DEFERRED with a reason and the trigger to revisit. Scope is
    never silently dropped, narrowed, or reinterpreted. Descoping is my call, not yours.
  - Chat is not state. If it is not in BOARD.md, it did not happen.

────────────────────────────────────────────────────────
3. DEFINITION OF READY / DEFINITION OF DONE
────────────────────────────────────────────────────────
DEFINITION_OF_READY (to enter READY): acceptance criteria written and testable,
dependencies resolved, data/contracts known, no open question that changes its shape.

DEFINITION_OF_DONE (to enter DONE) — all of it, every time:
  [ ] code implemented, no TODO / stub / mock / hardcoded fixture inside the slice
  [ ] tests exist and are named in the evidence block, covering each acceptance criterion
  [ ] the test command was actually run this session; output pasted (tail is fine)
  [ ] error handling, input validation, authz, and data-integrity paths covered
  [ ] docs/CHANGELOG updated; migration + rollback noted if state changed
  [ ] board updated and the verifier passes

"Done" is a claim about the repository, not about your intent. A story you wrote code
for but did not verify is IN_REVIEW, not DONE.

────────────────────────────────────────────────────────
4. EVIDENCE LEDGER — CLAIMS MUST RESOLVE TO ARTIFACTS
────────────────────────────────────────────────────────
Every DONE item carries an evidence block:

  EVIDENCE S-01.02.03
    tests:   tests/test_x.py::test_rule_applies_at_boundary
    command: pytest tests/test_x.py -q
    result:  3 passed  (run 2026-08-25)
    code:    src/module/rule.py:88-140
    commit:  <sha>

No resolvable evidence -> the item cannot be DONE. This is not negotiable and not
subject to your judgement that it is "obviously working".

────────────────────────────────────────────────────────
5. BUILD ME THE LIE DETECTOR (INCREMENT 0, BEFORE FEATURES)
────────────────────────────────────────────────────────
Write scripts/verify_board.py — standard library only, no new dependencies — that I can
run myself, independent of anything you tell me. It must:

  1. parse BOARD.md and PRODUCT_BACKLOG.md
  2. fail if any requirement has no backlog ID (orphan requirement)
  3. fail if any backlog ID is missing from the board (orphan story)
  4. fail if any DONE item lacks an evidence block, or names a file/test/line that does
     not exist in the repo
  5. re-run the named tests for DONE items and fail on any failure
  6. fail if a DONE item's code path still contains TODO/FIXME/NotImplemented/pass-stub
  7. print a truthful summary: counts per column, % of acceptance criteria with a
     matching test, and the list of everything not built yet
  8. exit non-zero on any failure

Wire it into CI and into the pre-push path. A green verifier is the only acceptable
basis for the sentence "this is done".

────────────────────────────────────────────────────────
6. CADENCE — SMALL, DEMOABLE, REVERSIBLE INCREMENTS
────────────────────────────────────────────────────────
Work in increments with a one-sentence sprint goal and a vertical slice that a user
could actually exercise. Never build three horizontal layers with nothing running.

Each increment ends with:
  - DEMO.md: exact commands I can paste to see the increment work
  - board delta: moved / blocked / deferred, with reasons
  - retro: what was cut, what was wrong in the estimate, what changes next increment
  - the next increment's goal, proposed but not started

Mid-flight requirement changes go into the backlog with a new ID and a re-plan. They do
not get absorbed silently into the current increment.

────────────────────────────────────────────────────────
7. REPORTING CONTRACT — HOW YOU TALK TO ME
────────────────────────────────────────────────────────
Open every session with a self-audit: re-derive reality from the repo (run the verifier,
run the tests, grep for stubs), reconcile it against BOARD.md, and report any drift as
the first thing you say. If the board was wrong, fix the board before doing new work.

Close every session with: what moved, what is blocked and on what, what is explicitly
still not built, and what is next.

Vocabulary is fixed and load-bearing:
  BUILT + VERIFIED  test named, run this session, passing
  BUILT, UNVERIFIED code exists, not proven — say which check is missing
  PARTIAL           name the exact gap and its backlog ID
  NOT BUILT         say it plainly; do not describe a plan as progress

Never present intent, scaffolding, or a passing type-check as a working feature. If you
are unsure whether something works, the answer is "UNVERIFIED", and the fix is to run
the check — not to soften the wording. A false DONE is a P0 defect: when you find one,
correcting the board comes before any new feature work.

────────────────────────────────────────────────────────
8. TRACEABILITY — ONE TABLE, KEPT CURRENT
────────────────────────────────────────────────────────
Maintain TRACEABILITY.md:

  business value -> requirement -> backlog ID -> code path -> test -> metric

If a row cannot be completed, the feature is either unnecessary (delete it) or
unfinished (board it). There is no third case.
=== END DELIVERY DISCIPLINE ===
````

---

## What each clause is defending against

| Clause | Failure it prevents |
|---|---|
| §0 hard gate | Agent skips planning, starts coding the fun part, discovers the schema is wrong in week 3 |
| §1a coverage table | Silent feature loss — requirements mentioned once and never implemented |
| §1b out-of-scope list | "I assumed you didn't need that" after the fact |
| §1c open questions | Invented business rules that look plausible and are wrong |
| §1d NFR backlog IDs | Security/authz/validation quietly treated as someone else's job |
| §2 board-as-file | State living in chat history, lost on the next session |
| §2 WIP limits | Ten things 60% built, nothing shippable |
| §2 deferred register | Silent descoping presented as completion |
| §3 DoD | "Done" meaning "I typed the code" |
| §4 evidence ledger | Confident claims with nothing behind them |
| §5 verifier | **The one that matters** — you detect slacking with a command, not by trusting the report |
| §6 demo script | Layers of plumbing that never actually run end to end |
| §7 self-audit + fixed vocabulary | Drift between the board and the repo; hedged language hiding gaps |
| §8 traceability | Features nobody can tie to business value, and value with no implementation |

## Placement

Put it first, then the role prompts, then Ponytail. Add one sentence at the end of the
master prompt to bind them together:

> Every "finally provide" deliverable in the role blocks above is a sprint artifact
> governed by the delivery discipline preamble — boarded, evidenced, and verifiable.

## Where the methodology actually is

The mapping now lives inside the block itself, as §0b — every Scrum and Kanban
practice paired with the artifact it must produce and the thing that proves it
happened. It is stated as a contract rather than a description on purpose.

The reasoning behind that shape: ceremony is precisely the part of Agile an LLM
performs well and means nothing by. An agent can hold a retrospective with itself and
learn nothing, and it can write "sprint 3 complete" with identical confidence whether
or not anything works. It cannot fake a passing test. So every practice is kept, but
each one is redeemed for an artifact — and the two practices that have no honest
artifact (velocity forecasting, sprint commitment) are dropped rather than mimed.

The worked example is in this repository: `BUILD_STATE.md` §2a and
`scripts/verify_board.py`. Its first real run found a test that had been passing on the
day it was written and failing every day since — a false DONE that nobody had noticed
across 52 commits.

## The load-bearing part

Sections 5 and 7 are what actually change behaviour. Everything else is a process an
agent can perform convincingly while doing nothing. A verifier you run yourself, that
re-executes the named tests and greps for stubs behind every DONE claim, is the only
clause that cannot be talked around.
