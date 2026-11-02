# F-06.22 — TDD and isolated QA evidence (2026-11-02)

## Provenance
- Repository `kunalwagh101/off_CRM`, **develop** only. Review service `srv-db86p4u89jmc73cehns0` in owner's confirmed Render workspace.
- RED source `e86ff75bbdbcb3ff08131d0786b0633196c6887e`, build `dep-dbk95sbbc2fs73epnd40`: **build_failed** as expected, `uv run pytest -q tests/test_crm_duplicate_review.py` **4 failed, 1 warning in 3.43s**. The three service calls did not exist and the authenticated API returned 404. This is a genuine before-implementation test failure.
- GREEN source `a0e9daf9e826cc7415964dd9dec42dd42daca119`, build `dep-dbk9797f3r2c73932q0g`: `uv run pytest -q tests/test_crm_duplicate_review.py` **4 passed, 1 warning in 3.42s**. Ruff syntax/critical checks passed. Auth tests **34 passed** and `tests/test_ci_verifier_environment.py tests/test_verify_board.py` **67 passed**. All facts from actual Render logs.
- Full image contains frontend test/build/audit, backend full SQLite, disposable PostgreSQL, Chromium acceptance and guarded concurrency suites. **Full build result was in progress when this first record was committed**; later verified results must be appended rather than guessed.

## Acceptance coverage
1. Unit/service: two collision groups after `lower(trim(email))`; exact group counts, repeatable ordering, independent page totals, unchanged contact table.
2. Integration: real `OutreachEngine`/SQLite `SalesTracker`, real FastAPI `TestClient`, authenticated endpoint and real saved contacts.
3. Adversarial API: unauthenticated 401, invalid inputs 422, quote/percent/underscore SQL-shaped search safely parameterised, private note/source fields excluded.
4. High-match group: six contacts with a three-record bounded preview and truthful `has_more`.

## Outstanding release evidence
- Review *not* DONE: no direct independent live penetration exercise, no PostgreSQL query-plan/large data benchmark of the new aggregation, no confirmed Q-27 workspace ownership model, no full-history `uv run python scripts/verify_board.py` invocation, no customer/browser screen acceptance. Synthetic test identities only.
- No provider sends and no production/live demo deployment. Restore is irrelevant because schema/data untouched; rollback is removal of the API route and service method via a normal revert on `develop`.
- The broader S-06.02.23 production audit is unrelated and remains IN_PROGRESS. Distinguish isolated QA image from production certification.
