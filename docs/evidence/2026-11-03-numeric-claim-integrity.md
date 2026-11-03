# S-06.02.55 — Numeric claim integrity QA (2026-11-03)

## Branch and exact source
Repo `kunalwagh101/off_CRM`, `develop` only. Exact tested code source `c1eefe2a3ea3ea867dd654d44dc6a600318eadff`. Isolated QA service `srv-db86p4u89jmc73cehns0`, Render workspace `tea-cspt7hggph6c739lq5j0`. Review deploy `dep-dbkni7fb9u1s73fubjl0` reached **LIVE** at 2026-11-03T06:22:32Z. No `main`, production/customer data, real model provider calls or mail sends were changed.

## Genuine test-first RED
Test-only `00b16572a2982bf03147f341fb19bfa01633e64f`, Render `dep-dbkn8p59fdbs73bquspg`: **15 failed, 13 passed, 8 deselected**. The mismatch tests cover a bare claimed numeric value incorrectly matched inside signed, decimal, grouped, percentage or currency evidence. `cad21abf` implemented numeric-specific matching; `c1eefe2` added Unicode and real browser checks.

## Final isolated QA, observed in Render logs
| Check | Result |
|---|---|
| `uv run pytest -q tests/test_agent_claim_verification.py -k A18` | **48 passed, 2 skipped, 8 deselected** |
| `uv run pytest -q tests/test_agent_claim_verification.py -k A18_real_chromium` | **2 passed, 56 deselected**; actual Chromium capture |
| Full SQLite `uv run pytest -q` | **2,940 passed, 50 skipped, 44 warnings** |
| Full disposable PostgreSQL `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` | **2,963 passed, 96 skipped, 44 warnings** |
| Focused real PostgreSQL CRM/hosted suite | **215 passed** |
| Board verifier unit tests | **67 passed** |
| Concurrent API write repeats | **12/12 passed** |
| Contacts and public visitor Chromium desktop/mobile | PASS |
| Frontend tests/build/audits and Ruff | PASS as required QA-image build stages |
| `uv run python scripts/verify_board.py --skip-tests` | PASS in Docker build; this is structural verification, not full-history evidence replay |

New behavior: fail closed when a cited quote's numeric sign, decimal separator, grouping, percentage/currency attachment or Unicode equivalent changes the claimed value. Do not invent cross-locale conversions or claim verified arithmetic without explicit validation. Ordinary correctly matched values remain accepted.

## Remaining before DONE/release
Independent live penetration exercise, full `uv run python scripts/verify_board.py` with historical Git checkout and recorded evidence commands, manual operator acceptance, and production deployment/recovery/security review are still **unverified**. An A18 unit/Chromium suite is not a security certification. The existing F-11.02 original sub-stories remain DONE; this targeted security repair is `IN_REVIEW`. Other open production findings and data isolation issues are unaffected.

Rollback: revert numeric matching in `offsetx_apollo_builder/agent/verify.py` using a normal `develop` code revert if required, but this reopens D-354. No migration, schema or durable state changed.
