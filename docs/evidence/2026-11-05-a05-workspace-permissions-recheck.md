# S-06.02.23 / A05 — workspace identity and administration, partial audit recheck

## Scope and source

Repo: `kunalwagh101/off_CRM`, branch `develop`. Runtime application code unchanged. Test-only commit `ee14710e3b1cf7deb74c64e44d9cf9a06bcf5ff1` and Docker review integration commit `94fa650586ea0ca40178d47b473354dabb1abc67`.

The three checks call the application's actual FastAPI entry points with two independently authenticated disposable workspaces and an install administrator.

## Observed isolated Render QA

Deployment: `dep-dblr106i0phs7385jao0`, service `off-crm-review-runner-20261015` (`srv-db86p4u89jmc73cehns0`). Deployed source: `94fa650586ea0ca40178d47b473354dabb1abc67`.

Command: `uv run pytest -q tests/test_audit_a05_workspace_identity.py`

Result from Render build logs, step #27: **3 passed, 1 deprecation warning in 4.65s**. The tests cover cross-workspace permission read refusal even with spoofed headers, non-admin denial for account listing/create/disable, and immediate cookie rejection after disabling only one account. This is a passing regression recheck of existing code, not a red-first defect fix.

The review Dockerfile also runs broader application tests, disposable SQLite/PostgreSQL, Chromium, static checks and frontend gates. Those are not counted as passed unless their corresponding output and full review status are observed separately.

## Open audit scope and release status

A05 is **partial**, not closed. The three cases do not prove a complete per-user role policy, isolation of all CRM rows (Q-27), independent penetration, production tenant acceptance, or access controls for every endpoint. S-06.02.23 and the broader F-06.02 audit remain **IN_PROGRESS**. Structural board checks with `--skip-tests` do not replay historical DONE evidence commands.

No main/customer deployment, external action, schema migration or database change. Rollback for the change is to revert the test file and its Dockerfile.review line, which reduces future coverage but does not affect customer data.
## Final isolated review, source-bound (2026-11-05 IST)

- Exact executable/test source: `94fa650586ea0ca40178d47b473354dabb1abc67`; Render isolated review `dep-dblr106i0phs7385jao0` confirmed **LIVE** at **2026-11-04 22:44:20 UTC**. This URL is a QA result marker, not the customer application.
- A05 targeted real API integration: **3 passed, 1 deprecation warning** (`uv run pytest -q tests/test_audit_a05_workspace_identity.py`).
- Full SQLite Python regression: **3,015 passed, 56 skipped, 44 warnings** (`uv run pytest -q`); full disposable real-PostgreSQL regression: **3,039 passed, 101 skipped, 44 warnings** (`OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`). Focused PostgreSQL suite: **215 passed**; PostgreSQL reconnect and session-revocation probes also passed.
- Other configured review gates passed: frontend tests/build/npm audits, Ruff, browser approval A09 (4 real Chromium cases), numeric-claim A18 (2 real Chromium cases), Chromium Contacts workflow at 1280px and 390px, Public Demo at 1440px and 390px, 12 repeated SQLite-concurrency probes and structural board verifier.
- **Limits:** the structural board verifier ran with `--skip-tests` (no full Git-history replay); the full suites have environment-dependent skips; no independent penetration engagement, live customer workspace or provider-backed acceptance, comprehensive A05 RBAC/CRM ownership (Q-27) verification, `main` promotion, or customer release. A05 remains **partial** and S-06.02.23 remains **IN_PROGRESS**. All new commits after `94fa650` are audit documentation only.
