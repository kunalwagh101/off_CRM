# F-06.12 — Persistent Human Follow-up Task Manager

**Status:** IN_REVIEW · **Branch:** develop.

## User journey
The operator creates a task after a reply or from the worklist, selects a due time and priority, optionally associates the campaign contact, assigns a **display label** for the responsible colleague, writes a note, and later edits, completes or reopens it. Filters show open/done/all and overdue. This creates **no automatic message, email, phone call, background reminder or access-control grant**. Assignment labels do not implement authorisation; workspace role-based task assignment remains a separate explicit future rule.

## Persistence and concurrency
New `campaign_followup_tasks` table with campaign and optional contact foreign keys, title, notes, assigned label, timezone-normalized UTC due timestamp, priority, open/done, monotonically increasing revision, completed_at, created_at and updated_at. This is additive CRM `SCHEMA_VERSION=10` for SQLite, and PostgreSQL `_POSTGRES_STEPS` second migration. New table is added to the `CRM_TABLES` inventory for copy/backup handling. All mutations run inside the current database transaction. Update requires matching revision; stale edits return **409**, not silent overwrites. Create accepts the existing HTTP Idempotency-Key mechanism.

## API
- `GET /campaigns/{id}/followups?status=open|done|all&overdue_only=false&limit=50&offset=0` with count and stable page.
- `POST /campaigns/{id}/followups` with strict title, optional membership, valid timezone-aware datetime, note/owner label and normal/high.
- `PATCH /campaigns/{id}/followups/{task_id}` with required revision, safe field updates, complete or reopen; metadata-only campaign events.

## Acceptance
Create persists across restart; only the originating campaign sees it. Unknown contact or task cannot be linked from another campaign. A stale revision yields conflict. Complete sets timestamp, reopen clears it and increments revision. Overdue compares timezone-aware UTC. Repeating create with identical idempotency key cannot duplicate tasks. No code path invokes send.

## Release/rollback gates
Focused backend/API and frontend tests authored in `tests/test_relationship_workflows.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx`; not executed here. Required: legacy SQLite migration, new SQLite creation, real PostgreSQL migration from version 1→2, database restore/backups including both tables, concurrent stale revisions, full Python/TypeScript suite and live user browser. **Schema downgrades are unsupported:** restore a prior verified backup or deploy a compatible application release; never drop task data to roll back. Workspace tenancy Q-27 remains a release decision.
