# develop continuation — Contacts full-results workflow — 2026-10-13

**Stories:** S-06.02.44, S-06.02.45, S-06.02.46. **Status:** IN_REVIEW. No production deploy or full test execution.

## Why these three
The owner asked for the next three useful product changes. Source scan found that Contacts displayed 100-row pages, had only search/status selectors, and stored checkboxes that could not be queried as a group. The existing `/campaigns/{id}/export` remains a broad full-campaign report: it does not mean the current filtered contact list is downloadable. This batch builds a coherent, reversible contacts workflow and does **not** introduce a provider or a new database table.

## Implemented
1. **S-06.02.44**: Add an authenticated `GET /api/v1/campaigns/{id}/contacts/download` endpoint and matching button. CSV is produced from the existing store's filtered query in batches of up to 500; max 50,000 results with an explicit refusal rather than truncation; UTF-8 BOM, attachment, no-store and nosniff. Exports only an allowlist of contact/operational fields, not message contents or internal notes; spreadsheet formula cells are prefixed with an apostrophe. The server holds a CRM transaction across the export and asks PostgreSQL for a repeatable-read readonly snapshot, preventing page drift in a concurrent CRM writer; SQLite holds its read transaction. It also verifies unique ids and stable count.
2. **S-06.02.45**: Campaign-specific distinct category and variant facet API; search/status/variant/category filters combine with existing pagination and reset the page when changed. Values are server-derived and URL encoded. Facets require existing authenticated campaign access as far as the current CRM tenancy model permits; Q-27 remains blocked.
3. **S-06.02.46**: Optional `selected_only=true` predicate on the stored membership checkbox in the same SQL query *before* counting/pagination, with UI Marked only toggle and export parity. No bulk mutation or send behaviour.

## Coverage prepared, NOT executed here
- Python `tests/test_contacts_filters_export.py`: authenticated/unauthenticated list and export, real API import, facets, selected mark/unmark, selected export, 503 fake rows across page boundary, explicit oversized/incomplete refusal, CSV injection and no internal notes.
- Frontend `frontend/src/pages/Contacts.pagination.test.tsx`: aria labels, export control and combined encoded filters, without breaking original paging contract.
- Regression checks to run: `uv run ruff check --select E9,F63,F7,F82 .`, `uv run pytest tests/test_contacts_filters_export.py tests/test_outreach_api.py -q`, `uv run pytest -q`, `cd frontend && npm ci && npm test && npm run build`, then `uv run python scripts/verify_board.py`.
- Real-data acceptance: import a 503+ contact campaign, select across pages, compare exact CSV row sets, check category/variant counts on SQLite and PostgreSQL, test a simultaneous edit, verify browser download and spreadsheet nonexecution. Need an independent reviewer and live service.

## Known blocks and limitations
The GitHub connector can read/commit private source, but the local execution container does not have a runnable clone of this repo. The most recent GitHub Actions runs create `quality` and `postgres` jobs and both fail with **zero executed steps** (external S-06.02.18). Neither tests nor a hosted PostgreSQL/browser acceptance were run here. All stories are IN_REVIEW; release is not certified.

Export fails if more than 50,000 rows match. In-flight exports use a single database snapshot and may wait on writer locks; measure large campaigns before release. Existing authorization design for multi-workspace CRM ownership is still Q-27, not silently solved here.

## Defect tracking
New functional gaps recorded as **D-274** (no filtered list export), **D-275** (category/variant selectors unavailable), **D-276** (marked contacts cannot be viewed across pages). The central `DEFECT_LOG.md` had connector write failures in the previous batch; reconcile these references before any DONE claim.
