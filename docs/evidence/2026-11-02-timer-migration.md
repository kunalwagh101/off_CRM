# S-06.03.06 — Legacy timer cutover QA evidence

Recorded 2026-11-02 (IST). Branch `develop`; source of truth: live GitHub + actual isolated Render review logs.

## TDD run
- RED `095c1a624d717ec5f8437b12afd0a2ebe9a4ff45` on Render `dep-dbjrc2h42hec73ds2qr0`: early `uv run pytest -q tests/test_timer_migration.py` failed **during collection**, because `db/timer_import.py` did not exist. No test cases executed. This is not a fabricated 9-test RED result.
- Implementation `3e9b87cf363fbd9dcbffdca4700391f83231bf9b` on Render `dep-dbjrd3p42hec73ds5j40`: **9 migration tests passed**, **6 hosted timer persistence tests passed**, **7 readiness tests passed**, plus the early authentication/security and agent permission gates. Other full-suite results must be recorded separately when verified.
- Additional security patch `fe93aad867f83fab86ee0ff76e070657a18a23fd` changes migration to an exclusive workspace lease and adds 3 regressions. Render full source verification pending at this checkpoint; earlier 3e9b87c green is not evidence for fe93aad.

## What is checked
Manual import or skip with protected archive; no silent overwrites; defaults disable unsupervised email/content/Gmail permission; malformed JSON rejection; symbolic link and path traversal refusal; rollback of a partial database write; repeatability after interruption; and an actual CLI entrypoint (last three tested only after fe93aad is reviewed).

## Remaining limits
This tool does not automatically migrate customer data. A chosen archive path must actually be durable, and operators must stop all application and worker instances. No customer database or third-party service was accessed. Full independent security/penetration, external encrypted backup/restore, workflow-level multi-install controls, and media/outbox durability remain open. A successful timer import alone does not certify the hosted application.

## Verified final isolated Render QA (2026-11-02 IST)

- **Exact reviewed source:** `0232cf5e2d15493dd7538b10fcbc69e404609c47`. **Service:** `off-crm-review-runner-20261015` (`srv-db86p4u89jmc73cehns0`), not a customer-facing application. **Deploy:** `dep-dbjri0utlv9c73e36570`, **LIVE** at `2026-11-01T22:28:58.000609Z` (2026-11-02 03:58:58 IST).
- **Migration TDD gate:** `tests/test_timer_migration.py`, 14 passed and one PostgreSQL-only case skipped at the SQLite stage. This includes exclusive-lock refusal, real CLI import, interrupted cleanup retry and two malformed-pipeline rejection cases.
- **Existing timer regression:** 6 passed. **Storage readiness:** 7 passed. **Authentication:** 34 passed. **Verifier unit:** 67 passed. Twelve repeated concurrency checks passed. Focused operational and permissions checks completed in the QA image.
- **Full Python SQLite:** 2,868 passed, 46 skipped, 44 warnings.
- **Focused disposable PostgreSQL:** 215 passed, 1 warning. **Full disposable PostgreSQL:** 2,889 passed, 94 skipped, 44 warnings. The additional PostgreSQL-only migration case ran with `OFF_CRM_TEST_POSTGRES_URL` set in the PostgreSQL stage and is included in that green full suite.
- **Real Chromium browser:** Contacts at 1280px and 390px PASS; visitor demo at 1440px and 390px PASS. Frontend npm tests/build and configured audit, critical Ruff checks and Docker QA final image stages completed successfully.
- **Final deployment:** the review marker became LIVE after the Docker QA image was built; it does not mean that the feature was released to the actual customer service.

**Limits and QA debt:** Full-history `uv run python scripts/verify_board.py` was not independently executed; 67 verifier-unit tests passed. Independent penetration testing, external durable-backup restore, key rotation, existing customer-file migration, real mail/SES sends and cross-instance supervised worker acceptance were not executed. This evidence does not certify these untested paths. The entire S-06.03.06 story and F-06.03 stay open.
