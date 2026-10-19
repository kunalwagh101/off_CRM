# off_CRM CRM Operations review checkpoint — 2026-10-19

Repository `kunalwagh101/off_CRM`, branch `develop`. Three existing product features are the selected review cohort: F-06.19 CRM Data Quality Centre, F-06.20 Campaign Comparison Dashboard and F-06.21 Follow-up Performance Centre. These were already implemented on 2026-10-15; do not rebuild or present them as new features. All remain IN_REVIEW.

## New code and review

- F-06.19: added a regression for workspace-scoped Sales Tracker email-overlap hints. The CRM records themselves remain install-wide pending Q-27. The test prevents accidentally treating another workspace's Sales Tracker data as a duplicate.
- F-06.20: corrected an inaccurate metric. The earlier SQL classified an inbound message as `replied_after_outreach` even when saved before every outbound message. An isolated SQLite reproduction on 2026-10-19 gave an incorrect count of 1 for inbound 2026-10-10 / outbound 2026-10-11; the chronological comparison gave 0. The production read-only query now requires an inbound at or after a saved outbound, preserving the response keys and non-causal warning. Added the reverse-order and later-reply regression and updated UI wording.
- F-06.21: added a regression confirming that reopening a completed follow-up clears the completion timestamp and removes it from done/on-time reporting.

No new tables, secrets, provider calls, outbound actions or data migrations are introduced. The user-visible route structure and JSON field names stay compatible. Rollback is a normal code revert; there is no database rollback.

## Evidence and limitations

The isolated Python/sqlite3 reproduction was **executed**, but it is not a run of the repository application. The new repository pytest, Vitest, full Python/PostgreSQL, browser accessibility checks and board verifier have **not been executed** in this code-editing environment because the private repository is only available through the connected GitHub API, not as an executable local checkout (network DNS to GitHub is unavailable). No new PASS claim is made for these three features. Earlier QA evidence remains historical only.

Run on the current full checkout:

```bash
uv sync --extra dev --extra email --extra postgres --locked
uv run pytest tests/test_crm_operations.py tests/test_crm_read_lock.py tests/test_wp1_recovery_edges.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

Then validate against disposable PostgreSQL, chromium keyboard/screen-reader paths, large-data query plans and restart/recovery. Obtain independent security/data review. Q-27 unresolved CRM tenancy blocks multi-customer release. D-314 concurrency and D-315/D-316 browser acceptance remain IN_REVIEW until the last exact-source Render run is independently inspected; Render deploy LIVE is not sufficient to assert test pass.

**Status:** implementation changes committed to develop once the linked Git commit exists. All three feature IDs stay IN_REVIEW; no production release claim.

## 2026-10-19 verified Render follow-up

Full QA results on the source revision `54864b0`: **2760 passed/45 skipped SQLite**, **2780 passed/94 skipped PostgreSQL**, **212 frontend passed**, **215 focused PostgreSQL passed**, **12/12 concurrency stress**, and **desktop/mobile Chromium Contacts passed**. See `docs/evidence/2026-10-19-render-qa-54864b0.md` for actual commands and limits. All three product features remain IN_REVIEW pending independent acceptance. Previous 'not executed' language documents the earlier pre-Render checkpoint and is not the latest test state.
