# F-06.17 — Account Intelligence Workspace

**Branch:** develop. **State:** IN_REVIEW; not released.

## User value
See which companies are in the CRM and which people, campaigns and sales opportunities relate to them, with existing outreach activity and unfinished human tasks. The company overview is a relationship view—not a legally verified account entity or automatic company merger.

## Implementation
- Authenticated `GET /api/v1/crm/accounts?search=&limit=25&offset=0`. It unions nonempty company names from global CRM contacts and workspace-scoped Sales Tracker leads, grouped by `lower(trim(company))`, not fuzzy matching. The server supplies per-account distinct contacts, campaign coverage, lead count and won count using independent SQL subqueries to avoid many-to-many join multiplication. Filtering and pagination operate in SQL. Search is wildcard-escaped. Blank company labels are omitted.
- Authenticated `GET /api/v1/crm/account?company_key=...&limit=25&offset=0` first confirms the exact normalized key exists, then returns bounded lists of people and opportunities, complete totals, distinct campaign coverage, counts of received/outbound messages, replied campaign members and open **contact-linked** follow-up tasks. Never include message bodies, raw JSON, private notes, credentials or model prompts. Contact 360 is reached from the right campaign/member pair, with one modal open at a time.
- UI provides searchable company cards, a profile panel and links to Contact 360, campaign contacts and Sales Tracker.

## Caveats and acceptance
- Different capitalizations/outer whitespace for the same company are grouped; alternate spellings and subsidiary structures are **not** automatically merged.
- Counts are based on recorded CRM rows and campaign memberships, not external company knowledge or inferred verified identities. Records without company names remain in original CRM but do not appear in account grouping.
- Two contacts across two campaigns and two opportunities at the same normalized company produce correct distinct totals, not inflated joins.
- Unmatched company returns 404, invalid paging 422. All authenticated routes require workspace access; Q-27 tenancy audit remains open.
- Verify SQLite and PostgreSQL, 10k+ account performance, live browser, accessibility and privacy/security before DONE.

**Files:** `outreach/crm_insights.py`, `api/app.py`, `frontend/src/pages/AccountIntelligence.tsx`, tests as above. No schema change and no write operations or external lookups.
