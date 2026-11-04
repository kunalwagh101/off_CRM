# A11 / D-362 — atomic AI quota spending and request reservations

## Provenance and TDD

**Date:** 2026-11-04 UTC. **Repo:** `kunalwagh101/off_CRM`. **Branch:** `develop`. **Story:** S-06.02.60 (BACKLOG while audit S-06.02.23 is active).

- **RED 1**, test-only source b57c971b15a754009c3db29998134eb8f3268b7e, Render dep-dblf71ugekts7388c3g0, build_failed: **8 failed in 13.78 s**. Failed cases included four actual two-process broker-to-stub-provider races (daily/minute cap, local/hosted SQLite), corrupt local/hosted counter resets, and absence of durable reservation and crash reconciliation.
- First repaired code 97191af/59f29dc and iterative scope/test updates 4abe3d9/1cc7dac passed **14 focused cases** in isolated QA (one PG case skipped when no database was supplied).
- **RED 2**, test-only source e488c303bbcd8fa2064ffd5918e3fe29cfb4fb78, Render dep-dblfdv8u01pc73a2of90, build_failed: **1 failed, 13 passed, 1 skipped**. A new key for the same workspace bypassed its one-call budget.
- **Exact corrected code/test source:** `8957a27b9d1d7d646757bf86d51f8059b21a0781`. Isolated Render review dep-dblffhijnfac73fs3770: **14 A11 PASS, 1 PG-only skipped at the early gate**. Full PG mode will activate the latter; final result pending at this checkpoint.

## Implementation

- `EgressBroker` stays the only AI egress gate. Per attempt for chat, images or transcription, it passes the policy scanner, attempts cache lookup if applicable, then **reserves quota before transport** and reconciles after. Plan-stage checking is only advisory.
- `QuotaTracker` books one UUID ticket transactionally in *two* counters: the workspace that initiated the call and the physical provider account (identified by a SHA-256 credential digest, never stored raw). Each independent worker and app instance uses the same hosted lock. A workspace changing its API key cannot reset its workspace allowance; two workspaces using one provider key share that key's allowance.
- Local JSON uses cross-process OS file locks plus a separate atomically replaced ledger file, strict corrupt-ledger refusal and flushed writes. Hosted JSON uses the existing PostgreSQL advisory transaction. A failed write before transport denies the call with a safe reference. A crash retains its reserved call and conservative USD allowance; a receipt reconciles actual usage idempotently once.
- When the pricing catalogue does not support an enforceable USD estimate, calls with a hard dollar cap refuse rather than count an unknown paid call as free. Reserve uses configured context size and higher of input/output USD/token prices. This bound is **not** a provider-side invoice guarantee.

## Test and security gates

- Early local/hosted multi-process, crash/restart, malformed ledger, failure-reference redaction, spend reconciliation, account isolation, key rotation, legacy counters and conservative price tests: 14 PASS at code 8957a27.
- The real PostgreSQL two-process test is enabled only when `OFF_CRM_TEST_POSTGRES_URL` points at a **disposable** PG server, in the PG Docker stage.
- Full SQLite regression, real PostgreSQL, frontend/npm audits, Chromium and full-history Git evidence verifier: **not yet claimed** at this checkpoint.
- No independent paid-provider acceptance, provider-enforced billing cap, third-party penetration testing, actual customer usage or customer/main deployment. Persistent pending tickets after a crash require operator recovery, not automatic re-send. Retention/pruning of reservation IDs remains a release consideration.

## Rollback

Stop all old AI egress workers, preserve both the database and pending-ticket ledger, identify outstanding provider actions from the egress log, and reconcile unknown results manually before re-enabling AI. Rolling back to the old check-then-record code reopens A11 and is unsafe without an explicit controlled incident decision. Never clear the ledger as a workaround.

## Full exact-source isolated QA results — 2026-11-04

Render isolated QA `dep-dblffhijnfac73fs3770` ran on pinned source `8957a27b9d1d7d646757bf86d51f8059b21a0781`.

| Gate | Observed |
|---|---|
| RED first reproduction | 8 FAILED intentionally at `b57c971` |
| RED credential-rotation regression | 1 FAILED intentionally at `e488c30` |
| A11 focused GREEN | 14 passed, 1 skipped (PG test only) |
| Full SQLite Pytest | **2,984 passed**, 55 skipped, 44 warnings |
| Real disposable PostgreSQL Pytest | **3,008 passed**, 100 skipped, 44 warnings; PG A11 independent-worker race test activated |
| Focused real PostgreSQL regression | 215 passed |
| Structural board verifier | PASS using `--skip-tests`, evidence commands replayed 0 |
| Chromium contacts | PASS at 1280px and 390px |
| Chromium public demo | PASS at 1440px and 390px |
| Frontend, static/security and review Docker gates | All configured build stages passed; image exported |

**Final deployment observation:** isolated Render review runner `dep-dblffhijnfac73fs3770` became **LIVE** at 2026-11-04T09:35:47.896966Z on exactly `8957a27b9d1d7d646757bf86d51f8059b21a0781`; Render logs confirmed the URL service live at 09:35:48 UTC. This is isolated QA, not production acceptance. **Remaining:** independent penetration testing, actual paid-provider receipt/billing verification, full-history board verifier with real Git work tree, operator review of pending crashed reservations, actual customer rollout and production storage/backup. None is claimed complete.
