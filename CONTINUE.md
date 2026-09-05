# CONTINUE — the handoff prompt

**What this is.** Paste the block below into a fresh Claude Code session — or
any capable coding AI — and it will pick up exactly where the last one stopped,
without you re-explaining anything.

It works because the state lives in the repository, not in a conversation. The
prompt just tells the AI where to look and what the rules are.

**How to use it:** copy everything between the two `-----` lines. Optionally add
one line at the end saying which story to refine or pull. If you don't, it will
tell you what's available and wait.

---

```
-----------------------------------------------------------------------------
You are joining an in-flight production project serving real users.
Every plan, design, prompt and implementation must follow the production
contract in AGENTS.md. Historical demo assumptions are superseded. The owner
must not need to repeat this requirement.

State lives in the repository, never in chat. Read these files before doing
anything else:

  AGENTS.md                standing production contract and security boundaries
  BOARD.md                 the only source of truth for status
  PRODUCT_BACKLOG.md       every epic, feature, story, acceptance criteria
  OPEN_QUESTIONS.md        decisions made, and questions still open
  DEFINITION_OF_DONE.md    the two gates: Ready, and Done
  TRACEABILITY.md          requirement -> story -> test -> code
  STATE_OF_THE_PRODUCT.md  plain-English summary, useful context but board wins

Repository: https://github.com/kunalwagh101/off_CRM   (branch: main)
Deep context, only if you need it:
  docs/architecture/BROWSER_AGENT_BLUEPRINT.md   the agent plan, 8 stages
  docs/VAULT.md                                  browser-session custody contract
  docs/architecture/VIDEO_EDITOR.md              the editor, and why it is built that way
  SYSTEM_MAP.md                                  every component and its state
  FEATURE_TREE.md                                repo-first product decomposition
  ~/.claude/rules/ponytail.md                    how code gets written here

=== METHODOLOGY ===

Kanban with vertical-slice increments. WIP limit 2. Not Scrum, and the reason
matters: there is one implementer and no throughput history, so a sprint
commitment is a promise from someone who cannot be held to it, and a velocity
number would be invented precision. Flow with a hard WIP limit is the honest
model. Every increment is one capability usable end to end — never "the backend
for X".

=== STEP 1 — STANDUP (do this first, every session) ===

Run:  uv run python scripts/verify_board.py

Then report, before anything else:
  - counts per column, straight from that output
  - any drift between the board and the repository
  - anything DONE whose test no longer passes

If the verifier is red, fixing that is the whole job until it is green. A red
verifier means the board is lying, and everything built on top of a lying board
is guesswork.

=== STEP 2 — REFINE OR PULL ONE ITEM ===

  - IN_PROGRESS must have room (limit 2). If it is full, finish or escalate.
  - Pull only from READY. Never from BACKLOG directly — an item in BACKLOG has
    not passed the Definition of Ready.
  - If READY is empty, refine the agreed next candidate against the Definition
    of Ready first; moving BACKLOG -> READY is its own inspectable state change.
  - Never pull something BLOCKED. Blocked means someone else owes something.
  - Move READY -> IN_PROGRESS in BOARD.md and commit that move before code.

If there is no agreed next candidate and READY is empty, say so and stop. Do not
invent work.

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
  - Browser-session vault capture/restore is trusted host orchestration and is
    never exposed as a model tool.
  - Nothing publishes without a human verdict.
  - Secrets never enter a prompt.

=== STEP 4 — PROVE IT ===

Definition of Done, all of it, every time:
  [ ] no runtime stub, fake success, mock integration or fixture replacing real data
  [ ] real user path, relevant persistence, failure and recovery checks verified
  [ ] remaining production blockers and unverified integrations recorded
  [ ] a test per acceptance criterion, named in the evidence block
  [ ] the test command actually run this session, output pasted
  [ ] error handling, validation, authz and data-integrity paths covered
  [ ] docs and CHANGELOG updated; migration and rollback noted if state changed
  [ ] board updated and the verifier passes

Then add the evidence block under the item in BOARD.md:

  - S-0X.0Y.0Z · Title
    tests: tests/test_thing.py::test_specific_behaviour
    command: uv run pytest tests/test_thing.py -q
    result: N passed (YYYY-MM-DD)
    code: offsetx_apollo_builder/module/file.py
    commit: <sha>

Code written but not verified is IN_REVIEW, not DONE. There is no third state
for "I am fairly sure it works".

=== STEP 5 — CLOSE ===

  1. uv run python scripts/verify_board.py    (must be green)
  2. Update CHANGELOG.md
  3. Record reproducible production acceptance checks in the story's evidence
     document; a walkthrough alone does not establish release readiness
  4. Update TRACEABILITY.md and any repo-first feature map affected by the slice
  5. Commit, then push to main
  6. Retro, three lines: what was cut, what the estimate got wrong, what to
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

## Optional: point it at the next candidate

Checked on 2026-09-05: `main` at `1e26a1f` closes `S-03.02.03` (Revoke
and forget). `agent/s-02-02-01-bounded-run-loop` at `6cd9d81` contains the
Run Loop implementation and focused tests, but its board still records
`S-02.02.01` as `IN_PROGRESS`. It has not been merged into `main`.

Re-check both refs before continuing. Finish the existing Run Loop against the
production contract and the Definition of Done, record actual evidence and
reconcile the board and feature map before taking another feature.
`S-08.01.05` also remains `IN_REVIEW` with frontend verification outstanding.

The next dependent feature is `S-02.02.02 — PLAN.md as the single source of
truth`: one saved plan per run, read again before each decision so owner edits
take effect. Refine it against the Definition of Ready after the Run Loop is
DONE; then move BACKLOG -> READY before pulling it. Interrupt/resume and
consequential-action countdowns remain separate required follow-on stories.

The current `render.yaml` stores CRM data under `/tmp`. Durable storage and
restart/restore evidence are required before that deployment can serve
production data. This documentation change does not fix the deployment.

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
