# Where everything stands

**Current implementation snapshot: 2026-09-20.**

This file is a readable summary. `BOARD.md` remains the source of truth and
`uv run python scripts/verify_board.py` is the mechanism that proves DONE
claims. Do not promote a story because this prose sounds confident.

## Current flow

| State | Count | Meaning |
|---|---:|---|
| IN_PROGRESS | 0 | nothing is being built right now |
| IN_REVIEW | 7 | implementation exists; complete executable/owner proof is pending |
| READY | 7 | dependency/decision gate passed; available to pull |
| BLOCKED | 3 | external platform access/review is missing |
| DEFERRED | 0 | nothing is intentionally parked |

The seven IN_REVIEW stories are:

- S-05.01.01 — durable crawler frontier;
- S-05.01.02 — declarative extraction packs;
- S-05.01.03 — structure-only competitor teardown;
- S-06.02.04 — subject access and deletion;
- S-03.02.05 — browser platform registry;
- S-02.02.02 — one editable PLAN.md per agent run;
- S-04.01.01 — persisted companions.

They are not DONE. The owner explicitly asked to build ahead and run a dedicated
verification pass later; DD-22 records that rule.

## What the product can already do

The mature/delivered base includes:

- the video timeline/editor, effects, retiming, automated assembly/director and
  human review queue;
- posting-rate caps and content-distribution planning;
- AI egress containment, provider tiers, prompt scanning, cost/quota controls,
  evals and broker-only provider calls;
- a real bounded browser run loop with ten closed verbs, accessibility
  perception, provenance, recovery, resume, structured results, progress/loop
  detection, cost/latency ceilings and concurrent-run safety;
- attended browser login, encrypted session vault, revoke/forget and per-account
  action budgets;
- protected bulk email permission/suppression, durable jobs, SES/domain
  authentication and feedback-driven pausing;
- the CRM, sales tracker, discovery/research graph, AI chat/memory and content
  production/distribution stores;
- a verifier that replays DONE evidence and rejects impossible dependency
  histories.

For exact delivered story evidence, read the DONE column of `BOARD.md`. This
file intentionally does not duplicate all historical pass counts.

## What the two build-ahead batches added

### Public discovery and privacy

**Crawler frontier (S-05.01.01).** Public discovery has durable due URLs,
leases, shared per-host pacing, adaptive revisit intervals and failure backoff,
while reusing the existing robots/SSRF/redirect/size safety boundary.

**Extraction packs (S-05.01.02).** A public source can be declared through
validated JSON selectors over the existing Scrapling parser. Packs are data,
not executable plugins. Generic JSON-LD remains the fallback.

**Competitor teardown (S-05.01.03).** Public structural/performance facts map
deterministically to an existing video recipe. Copied caption/transcript/audio/
media fields are refused. Derived projects use our own material and enter the
existing human review queue.

**Privacy (S-06.02.04).** Authenticated workspace-bound subject access and
confirmed deletion use one nine-adapter inventory covering CRM/research/
delivery data, sent-mail recall, AI context/egress, generated artifacts, CSV
queues/exports, companion profiles, crawler state and browser trace runs.
Partial failures remain partial and retry safely.

### Agent identity, steering and reusable profiles

**Platform registry (S-03.02.05).** Browser identity signals, host policy and
default account budgets now come from one packaged validated declaration.
Reddit is the acceptance example: one data row, no Reddit-specific code path.

**PLAN.md (S-02.02.02).** Every agent run owns exactly one current PLAN.md.
The model reads it fresh before every decision, so an owner edit affects the
next decision. The append-only trace captures the exact plan version each
decision actually saw.

**Companions (S-04.01.01).** Named profiles persist transactionally beside the
existing ToolRegistry. Each has owner instructions, one exact memory scope and
granted tool IDs. Runtime exposes only approved memory from that scope and tools
that are both granted and currently enabled; execution checks the grant again.
Authenticated CRUD/context/memory routes are wired.

## Available next work

The current READY column, in board order:

- S-06.01.01 — workspaces with their own keys and logins;
- S-06.01.04 — scheduled/event routines;
- S-06.02.01 — adversarial proof that no secret enters a model prompt;
- S-06.02.02 — every endpoint authorises and validates;
- S-06.02.05 — keyboard/screen-reader usability;
- S-07.01.03 — meeting transcription without a bot;
- S-07.01.04 — reports and artifacts.

Nothing should be pulled merely because it is listed here; the owner chooses the
next batch.

## Externally blocked

Three publishing stories remain blocked by things only the owner/platforms can
provide:

- S-01.05.01 — Google Cloud project, YouTube Data API v3 and channel OAuth;
- S-01.05.02 — Meta review, TikTok content-posting audit and LinkedIn partner
  programme;
- S-01.05.03 — real engagement readback, dependent on the YouTube connection.

Engineering must not fake these with browser automation or local outboxes while
calling them real publishing.

## Verification debt

The current IN_REVIEW stories already have focused tests and runnable commands
recorded in `DEMO.md` and `TRACEABILITY.md`. The dedicated verification pass
must run:

```bash
uv sync --extra dev --extra email --locked
npm ci --prefix frontend

# Focused commands are listed per story in DEMO.md.
uv run pytest tests/ -q
cd frontend && npm test && npm run build
cd ..
uv run python scripts/verify_board.py
```

Owner/manual acceptance happens after those engineering checks, as requested.

Until that pass exists, the honest state is **implemented, IN_REVIEW** — not
DONE.
