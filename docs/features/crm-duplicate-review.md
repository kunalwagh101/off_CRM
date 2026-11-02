# F-06.22 — Duplicate Contact Review (backend)

**Status: IN_REVIEW.** Branch `develop`. Backend-first owner instruction. New feature with three connected sub-stories. This work does not authorise any automated merge or new source of contact identity.

## Operator outcome
An authenticated operator calls `GET /api/v1/crm/duplicates` and receives groups of contacts with the same nonempty email after case-folding and trimming outer whitespace. Each group has its full count and a capped sample of three contact IDs/names/company/title values. The operator reviews possible duplicates in existing contact screens. These are **hints**, never proof of a shared person.

## Complete sub-stories and acceptance
1. **F-06.22a discovery:** group existing records by `lower(trim(email))`; exclude empty values and unique emails; preserve accurate global group totals and stable ordering; do not modify CRM rows.
2. **F-06.22b safe inspection:** page groups with `limit=1..25`, `offset>=0`, literal email substring search at most 100 characters, bounded three-record previews and `has_more`; return only allowlisted identity fields.
3. **F-06.22c API security:** use the existing authenticated FastAPI boundary; anonymous requests refuse access; invalid paging and oversized queries get 422; quote, percent, underscore and injection-shaped searches cannot change SQL structure.

## Invariants and release gates
No database migration, sending, merge, dedupe rewrite or background job. Existing upsert still prevents identical case-folded emails; this detects legacy/whitespace variants. Cross-workspace contact ownership remains subject to **Q-27** (the global CRM tenancy decision), so do not mark this feature DONE or release to production before independent privacy review. Complete real SQLite and PostgreSQL integration and load/query-plan checks, API auth/security checks, full tests, board verifier, Render QA and operational rollback before DONE. Read-only code rollback: revert new route and method; no state migration needed. This spec defines all three backend sub-stories; a future dedicated UI is separate scope, not falsely claimed here.

## Given / When / Then regression mapping

- **F-06.22a:** Given stored email variants differing in case and outside whitespace, when a signed-in operator queries duplicates, then only true nonblank collision groups appear with stable total counts and no mutations. Test: `test_duplicate_groups_are_stable_bounded_and_never_merge`.
- **F-06.22b:** Given a collision with six contacts, when the operator searches for that address, then results have an accurate six-record count, at most three sample identities, `has_more=true`, stable group pagination and no raw private fields. Tests: `test_duplicate_group_previews_are_capped_even_when_many_match`, `test_duplicate_search_is_literal_and_validation_rejects_bad_pages`.
- **F-06.22c:** Given an anonymous request, malformed pagination or SQL-looking search, when the protected endpoint receives it, then it denies access or bounds and escapes inputs without disclosure or SQL injection. Test: `test_duplicate_api_requires_auth_and_has_strict_input_bounds`.

## Verified QA and release position (2026-11-02)

TDD RED: commit `e86ff75`, Render `dep-dbk95sbbc2fs73epnd40`, **4 expected failures** before API/method existed. TDD GREEN: commit `a0e9daf`, Render `dep-dbk9797f3r2c73932q0g`, **4 passed** in 3.42s. Existing targeted permission/API/inventory/CI-verifier tests passed to date; full isolated review still in progress at this checkpoint. Further evidence: `docs/evidence/2026-11-02-crm-duplicate-review.md`.

A reported duplicate is only a review candidate. No edit, merge, email, provider call or migration was performed. Read-only endpoint rollback is a version revert after checking no clients depend on it; no database rollback required. Full PostgreSQL result, large-scale grouping performance, cross-workspace isolation Q-27, full-history evidence rerun, manual release acceptance and independent penetration remain open and prevent DONE.
