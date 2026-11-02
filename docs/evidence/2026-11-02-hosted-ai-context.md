# S-06.03.06 — Hosted AI task context and template stats

Date: 2026-11-02 IST. Branch: `develop`. Development is a partial slice of F-06.03, not story DONE.

## Why this was changed

`ContextLayer` held task decisions, steps, summaries, template text and send/reply counts in `ai_context.db`. With hosted CRM on the Render free plan, that context file still lived on an ephemeral disk. Losing it erases progress and performance history.

## Implementation

- Source `ce82d334cd96e66b81489071161063f56e7d4d4a`: `ContextLayer` takes an explicit `database_target`. For hosted mode it uses the existing `open_database` PostgreSQL/SQLite backend and `ensure_schema` versioned migrations. Local mode preserves existing standalone SQLite file behaviour.
- Real FastAPI application passes the actual configured hosted database to `ContextLayer` and refuses to ignore an existing `ai_context.db` file. Existing installations need a separate approved migration procedure before cutover; no silent data loss.
- The generated inventory table and runtime readiness classifier now state that template results have a hosted database home. The `SentMailIndex` and other stores are still local.

## TDD evidence observed so far

- RED source `daa57cf180dbaa15f0ebb5f3230a08b6e8ba7373` in isolated Render `dep-dbk615oae00c73fue270`: **5 failed, 1 skipped, 1 warning**; a PG-only case skipped because no PG service runs in the SQLite stage.
- Implementation `ce82d334cd96e66b81489071161063f56e7d4d4a` in isolated Render `dep-dbk623cs728c73c78no0`: **5 passed, 1 skipped, 1 warning** in the early hosted context regression. Existing hosted timer and migration gates passed. Full SQLite, real PostgreSQL, real Chromium, and final review deployment status need separate verification before marking green.
- New tests cover restart after destroying the temporary folder, separate workspaces' template history, failure without local fallback, actual application wiring, legacy-file refusal and PostgreSQL recreation.

## Unresolved acceptance

An operator-reviewed import/skip tool for existing local `ai_context.db`, real database restore to a new host, full-history board verification, independent penetration, full F-06.03 storage coverage, and external backup Q-29 are still open. No customer service, credential or `main` branch was changed.

## Full SQLite regression failure and correction (2026-11-02)

The first implementation `ce82d33` passed the five focused context checks but **failed** the full isolated SQLite review `dep-dbk623cs728c73c78no0`: **3 failed, 2,870 passed, 47 skipped, 44 warnings**. The three regressions were `tests/test_crm_hosted.py::test_a_campaign_made_in_the_app_outlives_the_disk[sqlite]`, `test_a_local_crm_holding_only_what_every_start_writes_does_not_stop_the_start[sqlite]`, and `tests/test_hosted_storage.py::test_readiness_checks_the_hosted_database[sqlite]`. All returned HTTP 503 for `/health/ready` with component `ai_context:OSError`. **Root cause:** `runtime_health` used the old `ContextLayer.path` to probe a local SQLite file even when the context connection had moved to `database_target`.

**Correction:** `7fdc4f2104a86ea7580f4cdbb6e335742d567195` checks the configured database target first and adds explicit `/health/ready` assertions in the hosted context application test. The isolated review now runs all three previously failing tests *before* the full regression suite. Review `dep-dbk66k0473hc73fo5bd0` is in progress at this evidence checkpoint. No success claim before the fresh logs confirm it.
