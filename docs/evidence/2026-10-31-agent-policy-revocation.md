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
- Wider full SQLite/PostgreSQL/Chromium build stages are **still being checked**; a triggered build does not establish they passed.

## Open verification and release gates

- F-06.01 / S-06.01.02 stays **IN_REVIEW**, not DONE, because upstream `S-04.01.01` is IN_REVIEW and the authenticated attended-chat grant/close path is still not available.
- No independent external penetration test or live user approval sequence is claimed.
- Revocation for other adapters beyond scheduled browser agents is not yet proven.
- Full-history `uv run python scripts/verify_board.py` with a real Git-history checkout is not yet demonstrated in this change.
- This is **isolated Render QA**, not a customer production deploy; `main` has not changed.
- No migration to roll back. Revert the code only with explicit risk acceptance: the prior snapshot/read fallback reopened D-327.
