# 2026-10-30 — S-06.02.52 TDD and operational readiness evidence

Red `3cf2c69d9d7628873ed7bdcb66e27a3191b1e0e7`, Render `dep-dbhsga67bikc73fr5nrg`: `uv run pytest -q tests/test_operational_health.py` **7 failed, 1 warning**, all 404 missing endpoint. Previous gates `tests/test_hosted_storage_readiness.py` 7 passed, `tests/test_agent_permissions.py tests/test_agent_run.py` 22 passed, typed-body 1 passed.

Initial green `b7d9bbd0a05326f04578e993b4c9a8992f7a5436`, Render `dep-dbhsh9ks728c73cqtkl0`: **7 passed, 1 warning** targeted. Final source `3e5058c1ac6dcd574534c78529a7c7e7e72bf3a8` adds an observability error reference to unknown failures; Render `dep-dbhsifajnfac73c7bu4g` QA in progress. Do not apply initial-green results to later code until rerun is observed.

Supported scope: existing in-process optional schedulers only. `GET /api/v1/operations/health` is owner-only and returns static component states, `alert_required` and a documented explicit `external_worker_monitoring=not_instrumented`. It does not monitor the separate CLI worker, measure queue age, or send alerts; it does not affect public readiness. No live provider or production data used. Full PostgreSQL/SQLite, browser and real worker failure acceptance still to report. No `main` or customer production change.

## Final hardened-source QA: full test suites and review LIVE

**Exact application source:** `3e5058c1ac6dcd574534c78529a7c7e7e72bf3a8`. **Isolated Render service:** `srv-db86p4u89jmc73cehns0` / deploy `dep-dbhsifajnfac73c7bu4g`. Connected Render confirmed **status=live** at **2026-10-29T22:46:47.765324Z**. This is a disposable test-only review marker, not customer production.

| Test command or gate | Actual observed result |
|---|---|
| `uv run pytest -q tests/test_operational_health.py` | **7 passed, 1 warning** |
| `uv run pytest -q tests/test_hosted_storage_readiness.py` | **7 passed, 1 warning** |
| `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py` | **22 passed, 1 warning** |
| Strict API typed-body regression | **1 passed** |
| `uv run ruff check --select E9,F63,F7,F82 .` | **All checks passed** |
| Existing contacts/export regressions | **19 passed** |
| Existing workspace isolation regressions | **3 passed** |
| Existing 40-worker concurrency + restart | **12 / 12 independent repeats passed** |
| Verifier unit tests | **67 passed** (NOT the full Git-history board verification command) |
| `uv run pytest -q` SQLite mode | **2,806 passed, 45 skipped, 44 warnings** |
| `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` | **2,826 passed, 94 skipped, 44 warnings** against disposable PostgreSQL |
| Focused PostgreSQL suite | **215 passed, 1 warning** |
| Existing Chromium Contacts 1280px / 390px | **PASS / PASS** |
| Frontend npm tests, build and audit | Review Docker stage satisfied from prior valid cache; frontend source did not change |

The tests cover disabled optional components, stopped enabled automation and content schedulers, stopped enabled agent routines, workspace owner access, inspection failures, and private-data non-disclosure. The review service exposes a QA pass marker, not the production FastAPI application. No independent live email-worker failure test, real alert delivery, fresh network penetration test or actual backup/restore certification was performed. **S-06.02.52 stays IN_REVIEW; A17 remains OPEN**, including missing external worker heartbeat and queue-age signals, and real configured paging. No customer app/production or `main` deployment.
