# F-06.19 — CRM Data Quality Centre

**Mode:** TASK · **Branch:** develop · **Status:** IN_REVIEW; Render full SQLite/PostgreSQL and frontend tests passed for source `54864b0`; manual privacy/UX sign-off pending. See `docs/evidence/2026-10-19-render-qa-54864b0.md`.

## Outcome and end-to-end flow

Operators open **CRM data quality** in navigation, select an issue (any, missing email/company/title, not linked to a campaign, or exact-email Sales Tracker overlap), optionally filter by name/email/company, then review matching contact records in pages of 25. The frontend can navigate to the existing campaign Contact screen or Sales Tracker. A global contact without campaign membership links to Campaigns to choose a destination. A record may have multiple flags.

Backend CRMOperations.contact_quality handles GET /api/v1/crm/quality?issue=all&search=&limit=25&offset=0. The issue is allowlisted, search is escaped for literal LIKE, and requested pages are bounded to 100. Counts precede pagination, deterministic order is (lower(full_name), id). A sales overlap is scoped to the active Sales Tracker workspace and compares only nonempty normalised exact email. Overlaps are **review hints**, not verified duplicates; no merging, changing or linking records occurs automatically. Responses expose only contact identity fields, issue codes, campaign count and one consistent campaign/member pair. No notes, message bodies, provider data or credentials.

## Criteria

1. Each issue filter returns accurate records and total, including an email collision hint without mutating either record. Missing fields and zero-membership contacts are distinguishable.
2. Search escapes percent/underscore, parameters reject invalid issue/page, and results never return private notes/message bodies. First campaign/member pair is consistent.
3. A responsive, accessible page provides issue and text filters, empty/error/loading states, safe navigation and paging.

**Dependency:** Existing contacts, campaign membership and Sales Tracker. **Schema:** unchanged. **Tests written:** tests/test_crm_operations.py and frontend/src/pages/CRMOperations.test.tsx. **Pending before DONE:** Python/frontend/build, PostgreSQL query plan on large data, Chrome/accessibility, workspace Q-27 and independent privacy review. Existing editable CRM forms must be used for any correction; this feature is intentionally non-destructive.