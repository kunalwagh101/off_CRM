# F-06.16 — Unified CRM Search

**Branch:** develop. **State:** IN_REVIEW; not deployed or tested in runnable checkout.

## User value
Find a contact regardless of the campaign where they were added; or search the existing Sales Tracker opportunities without opening each campaign or manually copying an email. The user can inspect an exact campaign membership in Contact 360 or navigate to Sales Tracker.

## API and UX
Authenticated `GET /api/v1/crm/search?query=&kind=contacts|leads&limit=25&offset=0`. Require a literal 2–100-character query; no match-all endpoint or empty-query bulk dump. Use the existing escape-aware `OutreachStore._like` to prevent user input `%` and `_` becoming SQL wildcards. Filter by name, email and company only—not message bodies, raw emails, notes or other sensitive metadata. Each kind is paged and counted in SQL, capped at 100 items per page. Contacts are globally deduplicated through their existing CRM identity and return membership count plus one **consistent** membership/campaign pair selected using the identical ordering. Sales records are filtered by the existing SalesTracker workspace id. Contact 360 can open that campaign-scoped membership; sales results navigate to the single existing Sales Tracker.

The frontend exposes a search form, two explicit record-type tabs, pagination, errors/empty states and no send controls.

## Acceptance tests
- Person with memberships in multiple campaigns returns one global contact and correct campaign count; chosen campaign/member pair refers to the same record.
- Search terms containing literal `%` or `_` do not become wildcards. Queries shorter than two characters, invalid type/limit/offset are refused.
- Sales results are restricted to existing workspace; contacts and sales display no private notes/provider JSON.
- Unauthenticated calls refused; paged results have accurate total and non-overlapping slices.
- Browser keyboard and responsive tests pass before DONE.

**Sources:** `outreach/crm_insights.py`, `api/app.py`, `frontend/src/pages/CRMSearch.tsx`. **Tests authored:** `tests/test_crm_insights.py`, `frontend/src/pages/CRMIntelligence.test.tsx`; no actual execution in the GitHub connector session. No migration. Rollback removes route/UI only; all CRM data remains unchanged. Existing workspace ownership Q-27 remains an explicit production security gate.
