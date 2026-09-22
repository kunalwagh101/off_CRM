# Where everything stands

**Current implementation snapshot: 2026-09-22.**

This is a readable summary. `BOARD.md` is the source of truth and
`uv run python scripts/verify_board.py` is the independent delivery check.
Implementation in IN_REVIEW is not DONE evidence.

## Current flow

| State | Count | Meaning |
|---|---:|---|
| IN_PROGRESS | 0 | no story is being changed now |
| IN_REVIEW | 13 | code/tests/docs exist; executable and/or owner proof is pending |
| READY | 1 | `S-07.01.04 — Reports and artifacts` |
| BLOCKED | 3 | external platform access/review is missing |
| DEFERRED | 0 | nothing intentionally parked |

The owner explicitly authorised build-ahead under DD-22. That allows complete
implementation batches to accumulate in IN_REVIEW, but it does not allow the
repository to call them DONE ahead of their evidence/dependency chain.

## Build-ahead stories currently in review

### Public discovery and privacy

- S-05.01.01 — durable crawler frontier with shared host pacing;
- S-05.01.02 — declarative extraction packs;
- S-05.01.03 — structure-only competitor teardown;
- S-06.02.04 — inventory-driven subject access/deletion.

The privacy inventory now has **12 named stores**, including companions,
routines, workspace identities and derived meeting transcripts.

### Agent identity, steering and automation

- S-03.02.05 — one browser platform declaration drives identity/policy/budget;
- S-02.02.02 — one editable PLAN.md per run, read before every decision;
- S-04.01.01 — persisted companions with exact memory/tool grants;
- S-06.01.01 — workspace-bound logins, encrypted keys/sessions and immutable
  request-bound AI credentials;
- S-06.01.04 — durable interval/event routines with unattended-policy checks,
  dedupe, workspace browser leases and verified-finding-only notifications;
- S-06.02.01 — every model-visible text channel is secret-scanned before
  provider I/O.

### Security, accessibility and meetings

- S-06.02.02 — the API is private by default; runtime route enumeration proves
  protected routes refuse anonymous requests and validation does not echo
  sensitive bodies;
- S-06.02.05 — shared keyboard/focus/live-region/modal semantics plus recursive
  frontend accessibility contracts;
- S-07.01.03 — localhost browser captures microphone + shared system/tab audio
  without a bot, keeps raw chunks transient, freezes one declared
  transcription provider/model, and persists only derived transcript metadata.

## What is deliberately not claimed

The newest build-ahead stories have focused tests and demo commands, but this
session has not yet produced executable CI/local pass evidence for them.
Meeting transcription additionally needs a real localhost browser capture in the
owner verification pass. Accessibility needs the owner keyboard/screen-reader
pass.

Therefore their correct state is **IN_REVIEW**.

## Next READY work

Only one story is currently READY:

**S-07.01.04 — Reports and artifacts.**

It turns source-backed run findings into a deck, sheet or PDF while requiring
every claim to resolve back to a trace step. Do not pull it until the owner asks
for the next batch.

## Externally blocked

- S-01.05.01 — Google Cloud project + YouTube Data API v3/channel OAuth;
- S-01.05.02 — Meta/TikTok/LinkedIn platform review/partner access;
- S-01.05.03 — engagement readback, downstream of the YouTube connection.

Engineering must not replace these official-platform requirements with browser
automation while calling the result a real publishing integration.

## Dedicated verification pass

```bash
uv sync --extra dev --extra email --locked
npm ci --prefix frontend

# Run the focused commands listed in DEMO.md.
uv run pytest tests/ -q
npm test --prefix frontend
npm run build --prefix frontend
uv run python scripts/verify_board.py
```

The commands and their exit codes are the authority, not historical prose.
