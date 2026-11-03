# 2026-11-03 — A12/A13 factual cache and model-provenance review

## Provenance
- Repository: `kunalwagh101/off_CRM`, branch `develop`.
- Exactly tested source: `6528060b4c61324948e16256d702f9e51bd073a7`.
- Isolated Render review service: `srv-db86p4u89jmc73cehns0`.
- Deployment: `dep-dbl0abqjnfac73a521g0`; **LIVE at 2026-11-03 16:19:15 UTC**.
- Later documentation-only commits `1bdac84` and `95a4c72` do not alter the executable code or test source. No new customer/main deployment.

## What was changed in this session
- Added `tests/test_ai_cache_integrity.py::test_A12_A13_restart_keeps_fact_and_model_provenance_isolated`.
- The test uses the real local SQLite ResponseCache, writes a result, closes the database, then reopens it. Identical factual evidence hits with the correct model. A changed numerical fact, model identity, system instruction, output-format option or workspace must miss. The test also checks that the original workspace's stats remain accurate and near-hits remain zero.
- The source fix (from earlier develop commits) disables fuzzy factual reuse and partitions cache keys by model identity, SHA-256 system-instruction digest and request generation contract in the existing EgressBroker boundary.
- No schema change, new dependency, real customer data or paid model calls were made.

## TDD history and directly observed QA
- **RED, previously run:** `3e06faa` on `dep-dbkrmik9v7es73f6gj1g`: 4 expected failing cases (changed factual numbers, changed negation, missing model and prompt partition).
- **Focused GREEN on exact current test source:** `uv run pytest -q tests/test_ai_cache_integrity.py`: **9 passed**.
- **Broker-model checks:** `uv run pytest -q tests/test_ai_cache.py -k A13`: **2 passed, 48 deselected**. Tests exercise EgressBroker.call switching models/prompts with a controlled provider, not a paid service.
- **Other focused QA/security:** image/video suite 113 passed; A18 numeric verification 48 passed/2 skipped; A09 Enter 4 passed and legacy keyboard 34 passed; auth 34 passed; contacts/spreadsheet export 19 passed; other per-gate tests passed.
- **Full SQLite** `uv run pytest -q`: **2,965 passed, 54 skipped, 44 warnings**.
- **Disposable real PostgreSQL** `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`: **2,988 passed, 100 skipped, 44 warnings**.
- **Focused real PostgreSQL**: **215 passed**.
- **Board verifier unit tests:** 67 passed; structural `scripts/verify_board.py --skip-tests` passed (explicit log says evidence commands run 0). Not a full evidence replay.
- **Frontend:** npm test, production build and configured audit gates completed as mandatory Docker build stages.
- **Real Chromium:** browser stages completed, including desktop 1440px and mobile 390px public-demo checks, contacts and authentication flows; PUBLIC DEMO CHROMIUM PASS observed in Render logs.
- **Ruff:** configured critical checks passed.
- Final review image built successfully and Render marked the deployment live on the exact tested source.

## Status, safety and rollback
- S-06.02.58 and S-06.02.59 stay **IN_REVIEW**; the 35-finding audit S-06.02.23 remains **IN_PROGRESS**.
- The original A12 and A13 defects are mitigated for named reproduced cases. This does **not** constitute independent penetration certification, real multi-provider acceptance, full-history board evidence replay or production customer acceptance.
- The higher cache-miss rate can increase model spend. Existing daily spend checks have a separate open atomic-reservation defect **D-362 / S-06.02.60**, so do not market cost controls as hardened by the cache repair.
- The accepted security behaviour cannot be rolled back to historical fuzzy factual reuse or unpartitioned model keys without reopening A12/A13. No database migration was required.
- Customer/main deployment, paid-provider credentials, mail sends and production data changes were not performed.
