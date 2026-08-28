# CONTINUE — the handoff prompt

**What this is.** Paste the block below into a fresh Claude Code session — or
any capable coding AI — and it will pick up exactly where the last one stopped,
without you re-explaining anything.

It works because the state lives in the repository, not in a conversation. The
prompt just tells the AI where to look and what the rules are.

**How to use it:** copy everything between the two `-----` lines. Optionally add
one line at the end saying which story to pull. If you don't, it will tell you
what's available and wait.

---

```
-----------------------------------------------------------------------------
You are joining an in-flight project. State lives in the repository, never in
chat. Read these five files before doing anything else:

  BOARD.md                 the only source of truth for status
  PRODUCT_BACKLOG.md       every epic, feature, story, acceptance criteria
  OPEN_QUESTIONS.md        decisions made, and questions still open
  DEFINITION_OF_DONE.md    the two gates: Ready, and Done
  STATE_OF_THE_PRODUCT.md  plain-English summary of where everything stands

Repository: https://github.com/kunalwagh101/off_CRM   (branch: main)
Deep context, only if you need it:
  docs/architecture/BROWSER_AGENT_BLUEPRINT.md   the agent plan, 8 stages
  docs/architecture/VIDEO_EDITOR.md              the editor, and why it is built that way
  SYSTEM_MAP.md                                  every component and its state
  ~/.claude/rules/ponytail.md                    how code gets written here

=== METHODOLOGY ===

Kanban with vertical-slice increments. WIP limit 2. Not Scrum, and the reason
matters: there is one implementer and no throughput history, so a sprint
commitment is a promise from someone who cannot be held to it, and a velocity
number would be invented precision. Flow with a hard WIP limit is the honest
model. Every increment is one capability usable end to end — never "the backend
for X".

=== STEP 1 — STANDUP (do this first, every session) ===

Run:  python scripts/verify_board.py

Then report, before anything else:
  - counts per column, straight from that output
  - any drift between the board and the repository
  - anything DONE whose test no longer passes

If the verifier is red, fixing that is the whole job until it is green. A red
verifier means the board is lying, and everything built on top of a lying board
is guesswork.

=== STEP 2 — PULL ONE ITEM ===

  - IN_PROGRESS must have room (limit 2). If it is full, finish or escalate.
  - Pull only from READY. Never from BACKLOG directly — an item in BACKLOG has
    not passed the Definition of Ready.
  - Never pull something BLOCKED. Blocked means someone else owes something.
  - Move it to IN_PROGRESS in BOARD.md and commit that move before writing code.

If READY is empty, say so and stop. Do not invent work. Report what is blocked
and what it is blocked on.

=== STEP 3 — BUILD IT (Ponytail rules) ===

Before writing any code:
  1. Read the existing code path first. This codebase is large and most things
     already exist somewhere.
  2. Ask whether the new code is necessary at all.
  3. Reuse what is here. Prefer the standard library. Prefer native platform
     features. Prefer dependencies already installed.
  4. Avoid wrappers, factories, service layers and abstractions nobody asked for.
  5. Write the smallest solution that fully and correctly solves it.

Before any large architectural addition, explain why the existing architecture
cannot solve it more simply.

NEVER simplify away: security controls · authentication and authorization ·
input validation · error handling · data integrity · transactions where needed ·
concurrency protection · observability · tests for important behaviour ·
accessibility · production reliability.

Architectural rules this codebase already enforces, which you must not break:
  - ai/broker.py is the ONLY thing that may call a model provider. A test fails
    the build if a second one appears.
  - A model names an existing tool. It can never describe a new one.
  - The browser agent has ten verbs and no way to run code. Do not add an
    "evaluate" verb, ever.
  - Nothing publishes without a human verdict.
  - Secrets never enter a prompt.

=== STEP 4 — PROVE IT ===

Definition of Done, all of it, every time:
  [ ] no TODO, no stub, no mock, no hardcoded fixture inside the slice
  [ ] a test per acceptance criterion, named in the evidence block
  [ ] the test command actually run this session, output pasted
  [ ] error handling, validation, authz and data-integrity paths covered
  [ ] docs and CHANGELOG updated; migration and rollback noted if state changed
  [ ] board updated and the verifier passes

Then add the evidence block under the item in BOARD.md:

  - S-0X.0Y.0Z · Title
    tests: tests/test_thing.py::test_specific_behaviour
    command: python -m pytest tests/test_thing.py -q
    result: N passed (YYYY-MM-DD)
    code: offsetx_apollo_builder/module/file.py
    commit: <sha>

Code written but not verified is IN_REVIEW, not DONE. There is no third state
for "I am fairly sure it works".

=== STEP 5 — CLOSE ===

  1. python scripts/verify_board.py    (must be green)
  2. Update CHANGELOG.md
  3. Add a runnable block to DEMO.md — a command the owner pastes and watches
  4. Commit, then push to main
  5. Retro, three lines: what was cut, what the estimate got wrong, what to
     change next time. Append it to RETRO.md.

=== CHANGE CONTROL ===

New scope gets a NEW ID and is re-planned. It is never absorbed into an item
already in flight.

Scope that is cut moves to DEFERRED with a reason and a trigger to revisit.
Descoping is the owner's decision, never yours.

If you find a requirement with no backlog ID: stop, add the ID, and ask whether
it belongs in this increment at all.

=== THINGS ONLY THE OWNER CAN DO ===

Do not attempt these, and do not wait on them silently — say they are needed:
  - a Google Cloud project with YouTube Data API v3 enabled
  - Meta app review, TikTok content-posting audit, LinkedIn partner programme
  - answering an open question in OPEN_QUESTIONS.md
  - deciding that scope is cut

=== HONESTY ===

Do not claim anything works without evidence a script can re-run. If a piece is
unfinished, say so plainly and record the honest status on the board. Report
failures with their output. That is what finishing looks like when the work is
not done yet.

Start with STEP 1 now.
-----------------------------------------------------------------------------
```

---

## Optional: add one line to point it at a specific story

Paste the block above, then add one of these:

```
Pull S-03.02.02 — the vault. Q-01 is answered: OS keychain, passphrase fallback.
It is the only READY story, and S-03.02.01 just made it the obvious next one:
the login now works and nothing yet protects what it leaves behind.
```

```
Pull S-02.02.01 — the run loop. Everything in `browser/` is a hand the agent
does not yet know how to use on its own.
```

```
Don't pull anything. Just run the standup and tell me where we are.
```

---

## Why this file exists rather than a longer conversation

A conversation is not state. It gets summarised, truncated, and eventually lost —
and the next session then rebuilds a worse version of it from guesses.

Every fact this prompt needs is in a file the AI can read: what is done is in
`BOARD.md`, why it is done that way is in `docs/architecture/`, what is decided
is in `OPEN_QUESTIONS.md`, and whether any of it is true is answered by
`scripts/verify_board.py`.

That is the whole point of the process. **The prompt is short because the
repository is honest.**
