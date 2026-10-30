# F-06.01 / S-06.01.02 — per-action permission revocation (2026-10-31 IST)

## Scope and existing contract

Existing `AgentPermissionPolicy` was already installed for global/per-tool allow/ask/deny settings, with an in-memory `ChatPermissionGrants` helper. Scheduled `RoutineAgentExecutor` correctly checked its initial goto and passed a *fixed snapshot* to `AgentRun`, which checked each chosen action against the snapshot. That did not protect against a policy change while an agent was still running.

Change: give scheduled runs a fresh policy callback per action, fail closed when settings are corrupt/unavailable, preserve safe error references and avoid new storage or provider egress. API owner GET/PUT refuse invalid settings. Test synthetic inputs only.

## Executed TDD: RED

- Exact RED test source: `a45716a580dc9b533c86a9ccac49b7b694833ac8`.
- Isolated Render review runner: `srv-db86p4u89jmc73cehns0`, deployment `dep-dbifi0ui0phs739b7m80`: **build_failed**, intentionally.
- Actual command: `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`.
- Actual result: **2 failed, 22 passed, 1 warning**. New mid-run revoke test and store-failure test both failed because `AgentRun.__init__` did not accept `permission_policy_provider`. This is a test-first failure, not a release pass.

## Implemented change and GREEN evidence

Exact application-code candidate: `12b92516e02b1b73121ef31cbaf4672057c07114`.

- `agent/run.py`: accepts current-policy callback; reads current policy before each selected action or cached read; on storage error logs a secret-safe reference, appends a refusal trace, performs no browser action and returns `permission_denied`.
- `agent/routines.py`: binds this callback to the current workspace and retains initial `goto` permission gate.
- `ai/workspace.py`: introduces strict `raw_permissions` that does not hide broken settings documents or failed reads.
- `api/app.py`: GET/PUT of owner permissions fail with actionable 503 instead of returning or writing unsafe policy data.
- Tests `test_mid_run_permission_revocation_blocks_the_second_browser_action`, `test_permission_store_failure_fails_closed_without_leaking_error` and `test_corrupt_saved_settings_fail_closed_for_owner_reads_and_updates` cover revocation, no-action error, log-safe response and settings preservation.
- Render GREEN deployment `dep-dbifjnrbc2fs73fbd6c0` on code `12b9251`:
  - `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`: **25 passed, 1 warning** (verified Render build logs).
  - `uv run pytest -q tests/test_api_auth.py::test_no_api_route_accepts_an_untyped_raw_dict_body`: **1 passed, 1 warning**.
  - `uv run pytest -q tests/test_operational_health.py`: **7 passed, 1 warning**.
  - `uv run pytest -v --tb=short tests/test_contacts_filters_export.py tests/test_spreadsheet_exports.py tests/test_existing_poi_enrichment.py tests/test_apollo_rejection_ledger.py`: **19 passed, 1 warning**.
  - Existing workspace GTM isolation tests: **3 passed, 1 warning**.
- Full SQLite `uv run pytest -q`: **2809 passed, 45 skipped, 44 warnings**.
  - Full disposable PostgreSQL `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`: **2829 passed, 94 skipped, 44 warnings**.
  - Focused PostgreSQL integration: **215 passed, 1 warning**.
  - Chromium Contacts synthetic import at 1280px and 390px: **PASS**.
  - Board-verifier unit cases **67 passed**; Ruff fast severity check passed. Frontend build/audit stages passed as required by the review image.
  - Render QA deploy `dep-dbifjnrbc2fs73fbd6c0` reached **LIVE**. These complete QA results belong to code `12b9251`, **not** the later D-328 correction.


## D-328 follow-up: strict validation and write must be atomic

A source-code review found that the owner PUT route called a strict read and
then used the existing lenient save later. If the document became corrupt
between them, the new permission could overwrite damaged policy data.
This is a distinct defect, recorded as `D-328`.

**Actual RED:** test
`tests/test_agent_permissions.py::test_permission_update_refuses_corruption_between_validation_and_write`
was written first on commit `498ec0d` (later doc-only commits did not change
the test). Render deployment `dep-dbifr0afngtc73dig9l0` on
`7a648c5cc42c2173c4a2d8906fc18cac27ba7123` **build_failed**:
`uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`
reported **1 failed, 25 passed, 1 warning**, with precisely that new test
failing on the former lenient write path.

**Corrected source:** `09ded49a7c41c3b1402664e2fd83f3c64e53fd9c`.
`WorkspaceAISettingsStore.save(..., strict=True)` makes the document read
strict *inside* its existing exclusive write lock. The permission owner PUT
uses it. Other callers retain their original default (`strict=False`),
minimising unrelated migration risk. No new persistence or schema change.

**GREEN QA deployment:** `dep-dbifrl2jnfac738ptqhg` was triggered on
the corrected source. Capture its actual final targeted, full SQLite,
PostgreSQL, Chromium and deploy results before treating D-328 as verified.
The review-only runner never establishes an independent live penetration test.

## D-329 follow-up: preserve the legacy document-reader call

The new strict write did not alter permissions, but it unconditionally called
`_document(strict=False)` in ordinary settings writes. An existing concurrency
regression monkeypatches `_document()` with a no-keyword wrapper. That was an
unintended compatibility break.

**Actual Render full SQLite RED:** tested source
`09ded49a7c41c3b1402664e2fd83f3c64e53fd9c`, deployment
`dep-dbifrl2jnfac738ptqhg` **build_failed** after targeted permissions
**26 passed** and the full SQLite run **1 failed, 2809 passed, 45 skipped,
44 warnings**. Exact failure:
`tests/test_workspace_isolation.py::test_independent_workspace_stores_do_not_lose_concurrent_provider_updates`.
The traceback identifies the unexpected `strict` keyword in the old
no-keyword wrapper. **This was a real regression and was not waived.**

**Fix:** source `e8200718c786b8d1fe2e9118b249aa405e087950` uses
`_document()` unchanged for normal writes, and `_document(strict=True)`
only for permission writes. Final isolated Render review: `dep-dbifv8942hec73f36l50` for exact
source `e8200718c786b8d1fe2e9118b249aa405e087950` has passed:
- **26** agent/permission tests, **7** storage readiness cases, **1** API typed-body contract test, and **7** operational health cases.
- **19** contact/export/enrichment tests, **3** workspace isolation cases, **12** repeated concurrency checks, **67** board-verifier unit tests; Ruff check passed.
- Full SQLite **2810 passed, 45 skipped, 44 warnings**.
- Focused disposable PostgreSQL integration **215 passed**.
- Full disposable PostgreSQL **2830 passed, 94 skipped, 44 warnings**.
- Chromium Contacts synthetic acceptance at desktop **1280px PASS**, mobile **390px PASS**.
- Frontend build/npm high-severity audit gates passed within this Docker review image.
The final image was built successfully through the verification copy stages.
Render **LIVE deployment status must still be confirmed separately**; neither
these automated tests nor a LIVE QA marker prove independent penetration testing.

## D-330 static review: missing policy document is not yet fail closed

The strict reader rejects corrupt JSON and read errors, but `_document(strict=True)`
still returns an empty document for a *missing* settings file or hosted row.
That is needed by existing fresh installs, which default to global allow.
A deployed installation whose saved deny settings disappear could therefore
be mistaken for a fresh install. This was found by **static inspection**;
it was **not** reproduced as a destructive live test or corrected here.

A safe fix needs an explicit first-run marker or owner-approved fail-closed
migration, plus hosted persistence and restart acceptance. Tracked as
**D-330**, open under S-06.01.02/F-06.03. Do **not** claim full missing-store
fail-closed protection, loss-of-disk tolerance, independent pen clearance or
production release from the current test counts.

## Open verification and release gates

- F-06.01 / S-06.01.02 stays **IN_REVIEW**, not DONE, because upstream `S-04.01.01` is IN_REVIEW and the authenticated attended-chat grant/close path is still not available.
- No independent external penetration test or live user approval sequence is claimed.
- Revocation for other adapters beyond scheduled browser agents is not yet proven.
- Full-history `uv run python scripts/verify_board.py` with a real Git-history checkout is not yet demonstrated in this change.
- This is **isolated Render QA**, not a customer production deploy; `main` has not changed.
- No migration to roll back. Revert the code only with explicit risk acceptance: the prior snapshot/read fallback reopened D-327.
