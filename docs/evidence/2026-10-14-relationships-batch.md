# off_CRM develop — Relationship management features

Mode TASK · Senior full-stack engineering · Date 2026-10-14 · Three *features*: **F-06.10 Reply Inbox & Triage**, **F-06.11 Contact Communication History**, **F-06.12 Human Follow-up Task Manager**. Code and tests **authored; not executed or production certified**.

## Reuse before building
The existing CRM had real incoming/outgoing `messages` and stops pending follow-ups upon a reply, but no campaign-scoped review queue or single-contact conversation UI. Its global `contacts.outcome_label` cannot represent different reviews in two campaigns. The sales tracker has sales leads but no general campaign-contact human task queue. Reused `OutreachStore`, `CampaignRelationships` with SQL projections, protected FastAPI router, `useResource`, and the standard CRM transactional schema upgrader.

## Implemented
- `offsetx_apollo_builder/outreach/schema.py`: add `campaign_reply_triage` and `campaign_followup_tasks`, indexes and SQLite `SCHEMA_VERSION=10`; `store.py` PostgreSQL step 2 creates these on existing databases; fresh baseline includes them. Both enter `CRM_TABLES` backup inventory.
- `offsetx_apollo_builder/outreach/relationships.py`: paged, campaign-scoped, latest-message reply inbox; metadata-only triage; per-membership message previews; durable tasks with date, label, due and revision CAS.
- `offsetx_apollo_builder/api/schemas.py` + `api/app.py`: validated create/update and GET endpoints; idempotent task creation and HTTP 409 stale revisions; no auth bypass.
- `frontend/src/pages/ReplyInbox.tsx`, `ContactConversation.tsx`, `Followups.tsx`, `Contacts.tsx`, `App.tsx`: end-to-end interface and navigation for reply → history → task, with loading/empty/errors, bounded pagination, keyboard-friendly form controls and no send button.

## Authored (not run) checks
`tests/test_relationship_workflows.py`: campaign isolation and no cross-campaign reply review, preserves reply stop and global outcome label, 52-message bounded paging and no raw provider JSON, task creation/update/complete/reopen/restart and stale conflict, protected APIs and create idempotency. `frontend/src/pages/RelationshipWorkflows.test.tsx`: paths and bounded pagination, reply review UI, contact history, task owner/due/completion.

Commands required in real checkout:
```bash
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest tests/test_relationship_workflows.py tests/test_outreach_api.py tests/test_outreach_engine.py tests/test_db_backend.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```
Also must test SQLite 9→10 + Postgres CRM 1→2 on a disposable clone of actual schemas, backed-up real hosted data, reader/writer concurrency, actual reply provider sync, cross-workspace auth Q-27, Chromium keyboard/mobile, security review and rollback/restore. A real backup is mandatory before applying the schema migration in hosted environments. No live sends or provider calls were made.

## Known blockers
No usable runnable private repository checkout in this tool session; prior GitHub Actions `quality` and `postgres` jobs failed with **zero executed steps**. Actual results cannot be claimed from source-only commits. Current Q-27 tenancy decision and hosted backup/key-custody rules unresolved. All F-06.10–F-06.12 remain IN_REVIEW; not DONE/deployed. No background task scheduling or customer engagement automation was secretly enabled.

## Decisions
DD-109: campaign-scoped review separate from global contact outcome.
DD-110: conversation projections exclude raw metadata, truncate previews, validate membership.
DD-111: persistent manual tasks, optimistic revision, explicit schema upgrade, no auto-action.
