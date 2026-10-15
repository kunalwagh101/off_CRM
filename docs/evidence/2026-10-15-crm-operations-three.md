# off_CRM — 2026-10-15 CRM operations three-feature batch

**Repo:** `kunalwagh101/off_CRM` · **Branch:** `develop` only · **Mode:** TASK. **Release state: IN_REVIEW; no tests passed or deployment claimed.**

## Source baseline

Verified `develop` at `882915552951807f244bb2b44092d48a65a1c831` before selecting next work. Existing F-06.16–18 already delivered in source, not reproduced. Read agent instructions, working state, board, product backlog, decisions, defects, traceability, current API/frontend and associated acceptance.

## New feature-level implementation

1. **F-06.19 CRM Data Quality Centre.** Safe, authenticated, read-only filtered contact quality index: missing email/company/title, no campaign membership, same-workspace exact-email Sales Tracker collision hint. Per-record flags and navigation to existing review paths. No automatic merge/dedupe, private notes, messages, source data or sending.
2. **F-06.20 Campaign Comparison Dashboard.** Saved cross-campaign membership, uniquely outbound-contacted, independently inbound-contacted, both-direction contact, manually qualified reply and sales-link counts; descriptive reply rate with real outbound denominator and N/A for zero. Pageable, searchable frontend and navigation to activity. Counts cannot fan out on repeated messages.
3. **F-06.21 Follow-up Performance Centre.** Existing durable human tasks grouped by normalised free-text assignee label, with separate all-campaign totals for open/done/overdue/completed-on-time, campaign filter, pageable owner breakdown and navigation to follow-up work. No job automation or login/permission inference.

Implementation: `outreach/crm_operations.py`; three authenticated GETs in `api/app.py`; `frontend/src/pages/CRMOperations.tsx` with three route entries in `App.tsx`. No schema change, migrations, new secrets or external/provider calls. Existing send/gateway boundaries untouched.

Tests authored: `tests/test_crm_operations.py` covering real seeded SQLite, escaping, unique contact counts, grouping, paging, API authentication/parameter limits; `frontend/src/pages/CRMOperations.test.tsx` covering path escaping and screen contract. All author-time checks are source inspection, **not** execution evidence.

## Release gates not met

The preceding GitHub Actions run `38674480652` had `quality` and `postgres` fail before executing any steps, so it supplies neither passing tests nor verified source defects. The agent's local sandbox does not have a network path to clone this private repository into an executable checkout. No Python pytest, Ruff, full board verification, Vitest, frontend build, PostgreSQL migrations/real query plans, Chromium accessibility or hosted instance have been executed in this change set.

Execute on trusted checkout:

```bash
uv sync --extra dev --extra email --extra postgres --locked
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest tests/test_crm_operations.py tests/test_crm_insights.py tests/test_relationship_workflows.py tests/test_relationship_intelligence.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

Further check on disposable PostgreSQL and browser, performance with large CRM datasets, rollback (read-only API/UI removal; no migration), cross-workspace and permission review, real hosted persistence/backups. **Q-27 remains unresolved:** campaigns/contacts currently shared across install workspaces and must not be labelled separate-customer safe. F-06.19–21 stay **IN_REVIEW**. Existing `S-06.02.23` stays the sole `IN_PROGRESS` board entry; WIP ≤2. Neither `main` nor sending routines were touched.
