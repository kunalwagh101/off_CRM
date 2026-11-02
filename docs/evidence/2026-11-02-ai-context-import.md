# S-06.03.06 — Explicit AI context history migration

Date: 2026-11-02 IST. Branch: develop. Scope: one part of F-06.03, not DONE.

## The data being protected

The existing `ai_context.db` holds task steps, user decisions, structured facts,
and template send/reply counters in `ai_task_state` and `ai_template_stats`.
The hosted context path is already implemented; older local history requires
the install owner's explicit decision before the hosted app may start.

## Implementation

- `offsetx-db import-context --source OLD --archive PRIVATE --yes` imports only
  into an empty hosted context, or permits an identical prior import when
  cleaning up after interruption. Existing unrelated hosted rows are never
  merged or overwritten.
- `--skip` archives the old history unchanged and keeps existing hosted
  records untouched; the owner makes this choice deliberately.
- The archive is a SQLite online backup, preserving changes not yet merged out
  of the source WAL. It is created privately before any destination write or
  source removal. No archive path within the ephemeral data directory is allowed.
- Hosted records use the existing `ContextLayer` schema. Tasks, decisions,
  counters and workspace IDs remain unchanged. The importer has no model/API
  egress and does not perform email sends or background work.
- Both hosted tables are imported in one transaction. An incomplete database
  write rolls back. The original source remains available on failure.
  Interrupted cleanup may be retried only if all existing rows match.
- The command requires the application's configured hosted credentials. Stop
  the app and worker before migration. The operator must select a genuinely
  persistent, secure archive volume, not a Render ephemeral folder.

## Test-first evidence

- RED source `ffd81e03886399518a3c4fccc7e0e552304085bf`,
  Render `dep-dbk8kfijnfac739tqm40`: test collection stopped with
  `ModuleNotFoundError` because the importer did not exist. No cases ran.
- First GREEN source `2adfdcc837e62427b9c033af9690fa40c28f4653`,
  Render `dep-dbk8lnu7bikc739gfoq0`: six migration tests PASS in the early
  focused gate. Full QA on this source is not proof for later changes.
- Added security/rollback cases and explicit connection closing, source
  integrity diagnostics and archive symlink checks through code/test commit
  `12361049103a8913753899b34eba5ef2f18698e6`. Isolated Render review
  `dep-dbk8on7f3r2c7391pn50` runs this exact source; its results must be
  filled in only after observed completion.

## Remaining blockers

Customer data has **not** been migrated, and this is not a verified customer
deployment. The owner must confirm archive durability and authorise any real
import/skip action. External encrypted backups, independent penetration,
other unhosted stores, full-history board verification and production restore
remain open. S-06.03.06 stays BACKLOG under the existing WIP policy.

## Final pinned isolated Render QA — PASS

**Reviewed source:** `12361049103a8913753899b34eba5ef2f18698e6`.
**Review service:** `srv-db86p4u89jmc73cehns0` (not the customer's web app).
**Deployment:** `dep-dbk8on7f3r2c7391pn50` — **LIVE** at
`2026-11-02T13:30:28.135455Z` after the configured Docker test stages.

Observed tests and gates from Render build logs:

- AI history importer first gate: **12 passed, 1 skipped**. The skipped
  case requires PostgreSQL and was run separately in the disposable
  PostgreSQL stage: **1 passed** for
  `test_postgresql_context_import_survives_reconnect`.
- Existing hosted context regression gate: **5 passed, 1 skipped** in the
  SQLite stage (PostgreSQL case tested in its dedicated PostgreSQL stage).
- Existing timer migration: **14 passed, 1 skipped**; hosted timer settings
  **6 passed**. Readiness and API security gates succeeded.
- Verifier unit tests: **67 passed**; repeated WP1 concurrency tests **12/12**.
- Full SQLite: **2,885 passed, 48 skipped, 44 warnings**.
- Focused PostgreSQL: **215 passed, 1 warning**.
- Full disposable PostgreSQL: **2,908 passed, 94 skipped, 44 warnings**.
- Real Chromium: contact pagination at 1280px and 390px PASS, and public-demo
  workflow at 1440px and 390px PASS.
- Critical Ruff, frontend npm test/build and configured npm security audit
  gates passed as required before the final QA image was published.

**Scope limits:** The review service's LIVE status means its QA-marker image
is deployed, not that a customer service or main branch was deployed. No real
user's local AI history was migrated or skipped. Full-history
`uv run python scripts/verify_board.py` was not observed (verifier unit tests
were), and an independent penetration test, external encrypted backup/restore,
production migration rehearsal and durable handling of the other local
stores have not been completed. These remain blockers for S-06.03.06 DONE.
