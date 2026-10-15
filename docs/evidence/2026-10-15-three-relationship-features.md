# off_CRM develop — Three relationship product features

Date: 2026-10-15. Status: IN_REVIEW, NOT DONE or deployed. The user explicitly requested three full features rather than individual stories.

## Scope
- F-06.13 Qualified Reply-to-Sales Conversion: user-confirmed promotion after positive/meeting triage, reuse same-email lead, provenance link, duplicate fail-closed.
- F-06.14 Contact 360 Workspace: campaign-scoped safe overview and integrated entry from existing Contacts/Reply Inbox/Follow-ups/Priorities.
- F-06.15 Daily Action Command Center: source-backed overdue tasks, replies awaiting review and untouched linked opportunities, with filter, stable pagination and navigation.

New campaign_sales_links table + index, SQLite schema 11 and PostgreSQL CRM migration step 3; new table in the CRM_TABLES backup/copy inventory. Existing sender and provider integrations unchanged. Authenticated endpoints in api/app.py, business logic in outreach/relationship_ops.py and new React components Contact360.tsx / ActionCenter.tsx.

## Test and release gates
Test source authored in tests/test_relationship_intelligence.py and frontend/src/pages/RelationshipIntelligence.test.tsx. Updated tests/test_crm_hosted.py and tests/test_relationship_workflows.py to expect 34 CRM tables and schema 11. No executable checkout or CI runner was available in the prior sessions, so do not claim that these tests passed.

Required commands from an actual checkout:
- uv run ruff check --select E9,F63,F7,F82 .
- uv run pytest tests/test_relationship_intelligence.py tests/test_relationship_workflows.py tests/test_crm_hosted.py -q
- uv run pytest -q
- uv run python scripts/verify_board.py
- cd frontend && npm ci && npm test && npm run build

Release also requires verified current database backup, PostgreSQL migration v2-to-v3 and fresh bootstrap, copy/restore parity, two concurrent promotion requests, cross-workspace security Q-27, no regressions to reply-stop/send approval, real browser and large campaign performance test. Existing hosted Actions have repeatedly failed before executing any steps. Rollback must not downgrade schema by reverting code alone.

Decisions: DD-112 sale conversion depends on recorded review and fail-closed duplicate detection; DD-113 overview is strict field-allowlisted; DD-114 action queue is source-backed and read-only. Main untouched; no live external outreach.
