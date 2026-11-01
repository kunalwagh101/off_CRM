# S-06.03.06 — Hosted timer-settings slice: TDD evidence

Date: 2026-11-02 IST. Repository: kunalwagh101/off_CRM, branch develop.

## Requirement and solution

One identified risk in F-06.03: owner-defined automation settings lived in `automation.json` and `content_automation.json`, which disappear on a free Render restart. The implementation uses two named documents through the same hosted storage used for provider settings and AI quota. Owner-configured local installations retain their existing files. No storage migration is attempted without explicit approval and no new send is triggered.

## Observed test-first sequence

- RED source `9a30a43f32bcbe34410d289def374818094826ee`, isolated Render `dep-dbjqsn3bc2fs73dkcag0`: **6 failed**, no false PASS, review build stopped at the early test gate.
- Implementation source `ff40ea84843ea119be48b7d1eedbebac23f9e838`, Render `dep-dbjqtnjbc2fs73dkedjg`: **5 passed, 1 failed**. The one failure was the new test fixture omitting `AppSettings.secrets_key`. Validation correctly refused a half-configured hosted install. No app validation was changed to hide this.
- Corrected test source `6166be72a618736e6bb0a60afcd6235bb45cee22`, isolated Render `dep-dbjqubh42hec73dr2bu0`: **6 passed, 1 warning** for the new test file; **7 passed, 1 warning** for `tests/test_hosted_storage_readiness.py`. Remaining broad review stages are recorded only when observed.

## Security and limits

The test cases cover application restart, lost disposable folder, failed hosted write, local-file ambiguity and backward compatibility. The hosted store uses the existing transaction and secret-protected configuration. Real external cloud database backup and restore, cross-instance actual task execution, external SMTP/SES success, complete old-configuration migration, unsupervised sending and full project penetration remain unverified. No customer data was modified and no customer-facing service deployed.

## Final pinned isolated Render QA — PASS

**Reviewed source:** `6166be72a618736e6bb0a60afcd6235bb45cee22`, app changes `ff40ea84843ea119be48b7d1eedbebac23f9e838`. **Service:** `off-crm-review-runner-20261015` (`srv-db86p4u89jmc73cehns0`), review deployment `dep-dbjqubh42hec73dr2bu0`. The Render connector returned **LIVE** at **2026-11-01T21:45:53.536628Z** (02 November, 03:15:53 IST), after the image finished its configured Docker QA stages.

Actual build log results:

- New hosted timer tests: `uv run pytest -q tests/test_hosted_timer_settings.py` — **6 passed, 1 warning**.
- Storage readiness: `uv run pytest -q tests/test_hosted_storage_readiness.py` — **7 passed, 1 warning**.
- Authentication/public demo focused gate — **34 passed**.
- Verifier unit tests — **67 passed**; 12 repeated concurrent API writer checks passed.
- Full SQLite suite: `uv run pytest -q` — **2,854 passed, 45 skipped, 44 warnings**.
- PostgreSQL focused suite: **215 passed, 1 warning** against disposable PostgreSQL 17.
- Full PostgreSQL suite with `OFF_CRM_TEST_CRM_ON_POSTGRES=1`: **2,874 passed, 94 skipped, 44 warnings**.
- Chromium contacts at 1280px and 390px **PASS**; public visitor-demo workflow at 1440px and 390px **PASS**.
- Configured frontend test/build/audit and Ruff stages succeeded as preconditions for the final QA image. All stages in `Dockerfile.review` completed.

**Caveats:** 45 SQLite and 94 PostgreSQL tests were skipped within their respective runs; Chromium and focused PostgreSQL gates separately executed specified real-service cases. This is not independent penetration testing, an end-to-end external-provider send, a real production database restore, a live customer deployment or proof of all S-06.03.06 stores. Full-history `uv run python scripts/verify_board.py` is not confirmed; only verifier-unit tests are evidenced. Documentation-only commits after reviewed source were not re-run through the full image. S-06.03.06 stays BACKLOG under the project's existing WIP rule; S-06.02.23 remains IN_PROGRESS. No `main` promotion.
