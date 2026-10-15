# off_CRM / develop — CRM Intelligence three-feature batch

Date 2026-10-15 · Requested: three **product features**, not three story-sized fixes. **Release state: IN_REVIEW**, no test/deployment pass claimed.

Selected after inspecting current Contacts, CRM identity, per-campaign replies/tasks, SalesTracker and new campaign_sales_links. The next meaningful missing capabilities are:
1. F-06.16 Unified CRM Search — cross-campaign contacts plus existing sales leads without private-message search.
2. F-06.17 Account Intelligence Workspace — company-grouped contacts, campaigns, sales opportunities, message counts and open tasks, based on exact normalized company name.
3. F-06.18 Campaign-to-Revenue Attribution — truthful recorded sales value attribution, first-linked per unique lead to prevent duplicate revenue sums.

## Code
Backend `offsetx_apollo_builder/outreach/crm_insights.py`, four authenticated GETs in `offsetx_apollo_builder/api/app.py`: `/crm/search`, `/crm/accounts`, `/crm/account?company_key=...`, `/crm/attribution`. Three navigation-enabled React screens `frontend/src/pages/CRMSearch.tsx`, `AccountIntelligence.tsx`, `RevenueAttribution.tsx` and `frontend/src/App.tsx`. Existing CRM schema, sender, provider gateway, credentials and task workflows unchanged. No schema migration, no external API, no inference. Source docs in `docs/features/unified-crm-search.md`, `account-intelligence-workspace.md`, `campaign-revenue-attribution.md`.

## Regression tests authored; no results fabricated
- `tests/test_crm_insights.py`: 2 campaigns, deduplicated global contact and aligned membership pair, literal-safe LIKE pattern and paging; case-insensitive company grouping without join fanout; linked lead first campaign cash/value attribution, stable all-campaign totals, auth and invalid-parameter denial.
- `frontend/src/pages/CRMIntelligence.test.tsx`: safe route encoding, the three operator screens and explicit non-causal revenue label.
- Previously developed tests and the full suite remain required.

Run on real checkout:
```bash
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest tests/test_crm_insights.py tests/test_relationship_intelligence.py tests/test_relationship_workflows.py tests/test_crm_hosted.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

Missing acceptance: disposable PostgreSQL, 10k+ query plan and indexes, UI Chromium keyboard/mobile/modals, tenancy boundary Q-27, financial metric semantics and data privacy review. GitHub Actions jobs repeatedly failed with zero run steps on prior commits; do not call these DONE/deployed until verified. No new data table means rollback simply removes read-only API and screens.

## Decisions
DD-115 — Global search uses only purpose-allowed fields and explicit small queries; no raw private content search.
DD-116 — Company grouping uses case-insensitive trimmed names only, not false certainty about subsidiaries or entity mergers.
DD-117 — First linked campaign wins attribution for a sales lead, with a clear noncausal disclaimer and no double-counting; monetary units not converted.
