# F-06.03 storage-readiness: TDD and QA evidence (2026-10-30)

## Intended user capability
A normal user cannot read global data-store topology. The install owner can call `GET /api/v1/storage/readiness` and receive a storage inventory without credentials, URL strings or raw filesystem paths. Hosted CRM, provider keys and AI workspace settings are distinguished from media, outboxes, routines, caches and privacy files that have no verified durable filesystem. The report does not enable production or create backup data.

## Exact source revisions and observed QA

- **RED** `0b96e38f9c5712745872d16295715d24e97898e6`, Render `dep-dbhr4i2jnfac73an8ee0`: the new `uv run pytest -q tests/test_hosted_storage_readiness.py` gate **failed all 5 tests** on absent HTTP route/404. This was the intended test-first baseline. Build failed at the targeted gate and did not run broader regressions.
- **Initial GREEN** `fc0a4cfa768ad24666477739dbae8c74e6e5df3d`, Render `dep-dbhr63ff3r2c73c62te0`: **5 passed, 1 warning** targeted, **2,782 passed / 45 skipped / 44 warnings** in the complete SQLite suite, **215 passed / 1 warning** in targeted real disposable PostgreSQL suite, existing Chromium Contacts **1280px and 390px PASS**, Ruff and cached frontend gates passed. Full PostgreSQL regression and final deploy status should be checked before extending these claims.
- **Later security change** `d89bebb1ef151a6d92ac38e950bc443d6ae600f3`: two additional tests for a logged-in non-owner workspace (403 without details) and false OS-root `/` durable-mount claims; helper rejects OS root and temp folders. Those two changes have **not yet been executed on Render**. A final redeploy attempt was restricted by the execution interface. **Never apply the initial GREEN results to these changes without a new test run.**
- **Docs/handoff follow-up** `333de2eee16f8a70ba77fa1ae6bdbde7aa221170`: board S-06.03.08 IN_REVIEW, D-323 and DD-123 recorded. These are documentation changes and not a newly tested application source.

## Required remaining verification and release gates

Run latest `develop` on the isolated review runner, not the live customer service; at minimum `uv run pytest -q tests/test_hosted_storage_readiness.py` (seven cases), the full SQLite and real disposable PostgreSQL suites, frontend lint/build/security audit and desktop/mobile Chromium. Run `uv run python scripts/verify_board.py` in a full Git-history checkout. Test a real owner login/tenant cookie and a persistent disk across an actual container restart before claiming production durability. No independent external penetration test has been executed.

**Critical product blockers:** Q-29 owner-approved off-database encrypted backup destination/key policy, S-06.03.04 backup and restore, and S-06.03.06 placement of non-hosted customer files. The existing `OFFSETX_PRODUCTION` guard continues to reject unsupported hosted/half-hosted production; this report does not override it. D-321 moderate Vitest dev advisories remain open. No main branch or customer data/service changed.
