# A14 — Atomic HTTP idempotency: source, RED/GREEN, and release boundaries

**Date:** 2026-11-04 UTC. **Repo:** `kunalwagh101/off_CRM`. **Branch:** `develop`. **Work:** S-06.02.62 / D-364 / R-190.

The September A14 finding said read->effect->upsert was unsafe under concurrent API workers. The current `_idempotent` matched that structure.

## Test-first reproduction
- **RED source:** `ac10fa0c324ec02a4cbc9ad8a2923b402114ff14`.
- **Isolated Render deploy:** `dep-dblfslqjnfac73ft665g` build_failed.
- **Test command:** `uv run pytest -q tests/test_api_idempotency_a14.py`.
- **Observed:** **5 FAILED** (two independent TestClients sharing the CRM created duplicate campaigns, changed payload replayed an old campaign, failure after mutation left a campaign, uncertain send repeated, and invalid key was accepted). The controlled fake send made no customer email request.

## Initial repaired source
- **GREEN executable source:** `19682d5e0eb8d7827f604dd297020768410d5ef4`.
- **Isolated Render:** `dep-dblfu1ugekts738a7780`, early A14 gate **5 PASSED**.
- `offsetx_apollo_builder/api/app.py` uses a versioned response envelope with hashed request/principal identity in existing `idempotency_records`; SQLite/PG transaction serializes pure CRM operation and saved result. Provider/email operations first persist `in_progress`, so ambiguous or crashed sends cannot be repeated blindly. Saved completion replays; same key with changed caller/payload is 409. Unbounded/malformed headers 422.

## Extended coverage and final review
- Updated historical replay test in `tests/test_outreach_api.py`: exact same request replays, changed request returns 409. Extended A14 tests include real disposable PG two-app race, authenticated caller boundary, completed external replay and legacy-row refusal. Latest test-only commit `7c47b34`.
- **Pending at this checkpoint:** isolated Render full SQLite and PostgreSQL suite for the extended tests, actual provider integration, independent penetration, full-history board verifier, and customer release.
- A failed external operation leaves an in-progress claim for manual reconciliation. This is safer than repeating a possibly delivered message, but may require operator action to recover.

## Security boundaries
No original request bodies or provider keys are stored in the idempotency metadata; it keeps a SHA-256 fingerprint. No production credentials, customer database, live SES sends or main changes were made. Synthetic tests do not certify real provider exactly-once delivery.

## Rollback
Stop API workers before any downgrade to old non-atomic code. Preserve the CRM and its idempotency ledger together. Do not delete an unresolved key without checking the last send/receipt in the provider and audit logs. Reverting the fix reopens A14.

## Completed-send provider setup regression (added after first GREEN)

- Test first `0b66f15914a295d0cf002f8479a739e7c4e9a183` added a replay case where the provider factory becomes unavailable after a successful send. First repaired source `19682d5` still built the provider before looking up the cached result.
- Code fix `c6d11927449e151a7c11cb7cfb402fbf81c428c8` defers mail-provider construction until the guarded operation actually runs. Completed replays avoid provider setup, while first execution still stores the in-progress claim before setup/transport.
- **No final exact-source GREEN assertion for this added case until the next isolated Render run.**

## Final-source adversarial and crash coverage, pending exact-source QA

- Additional tests `6dd36182ac05b2c1dc9a9670267c7d26887b28f7`: concurrently altered payload must return 409 rather than steal another caller's key, and SQL metacharacters must never be executed from the key.
- Added actual independent OS process crash test `2e709a59479d374397d66abf242f9e4148d6c879`: a worker performs an insert, dies with exit code 47 before idempotency transaction commit, and a fresh app checks the database is clean and the same key may safely retry once.
- Code `c6d1192` moves send-provider construction after idempotency replay check, covered by `0b66f15`; a completed replay must succeed without another provider connection.
- **The last executable source is 2e709a5; only its own isolated Render QA results count as final acceptance.** Prior Render `dep-dblg1uc9v7es739u8t10` used older 38371c and does not cover these subsequent tests/changes.

## Completed exact-source full automated QA — 2026-11-04

**GitHub reviewed source:** `1c1d3a2b1e0acf1262776b5c082adacce691d776`. **Last code/test modification:** `2e709a59479d374397d66abf242f9e4148d6c879`. **Isolated Render review deploy:** `dep-dblg7k8u01pc73a4m7lg`.

| Gate | Observed result |
|---|---|
| Initial TDD RED | 5 failed as expected on `ac10fa0` |
| Focused final A14 (SQLite-stage) | **12 passed, 1 skipped** (real PG test requires URL) |
| Full SQLite | **2,996 passed**, 56 skipped, 44 warnings |
| Focused PostgreSQL integrations | **215 passed** |
| Full disposable PostgreSQL | **3,020 passed**, 101 skipped, 44 warnings; PG-specific A14 cross-instance race included |
| Real Chromium Contacts and public demo | PASS at desktop/mobile breakpoints |
| Frontend, npm audit, Ruff, security, verifier unit tests | Passed the configured review Docker gates |
| Structural board verifier | PASS with `--skip-tests`; **0** historical evidence commands replayed |

All review Docker test stages were built and the QA image exported. Render subsequently confirmed this isolated QA service **LIVE** at **2026-11-04T10:27:18.435081Z** on source `1c1d3a2`. The automated suite uses synthetic identities, a disposable database and fake external sends. It **does not** constitute independent penetration certification, customer deployment, a real email-provider acceptance test or actual exactly-once delivery assurance beyond the modelled HTTP idempotency and stored claims. The last audit story remains in progress and this A14 story remains BACKLOG.

**Rollback:** Stop competing application workers. Preserve idempotency and campaign data in one consistent database backup. Never delete `in_progress` records after an uncertain email send to force an automatic replay. The previous unguarded helper is unsafe for customer traffic.
