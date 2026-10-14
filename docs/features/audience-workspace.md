# F-06.07 — Audience Management Workspace

**Status:** IN_REVIEW (not production-verified). **Branch:** develop.

## User outcome
Campaign owners can manually add a contact without a spreadsheet, reuse a previously known email without corrupting its shared profile, build a transient explicit batch across pages and safely mark/unmark or stop outreach to those exact records.

## Complete vertical workflow
- UI `Contacts` opens `ManualContactModal`, collects name, valid email, company, role, approved category and optional documented public evidence. Backend `POST /api/v1/campaigns/{id}/contacts/manual` validates the strict payload and uses the existing global-contact identity, email dedupe and campaign membership store. An existing profile with the same email is **linked, not overwritten**. Same campaign/email is a no-op. No draft, approval, email or provider action is generated. The endpoint accepts an idempotency key for network retries.
- The UI has an independent batch checkbox (not the persisted `Marked` attribute); users may accumulate at most **100** explicit campaign-membership IDs across pages. Selection resets on campaign change. `POST /api/v1/campaigns/{id}/contacts/bulk` accepts explicit IDs and mark, unmark or stop; no all-campaign implicit action.
- The server rejects a duplicate, missing, foreign-campaign or over-100 ID set **before mutating any row**. Bulk updates run transactionally with the existing CRM locking. Repeated mark/stop is idempotent by state. Stop excludes replied/completed/stopped records, writes status stopped and clears next_action_at. Existing send logic already skips stopped records; the action never resumes or sends.
- The action log stores operation and counts; not a raw list of emails.
- There is no automatic bulk resume, destructive deletion, CRM merge or live send in this feature. The existing import, contact editor and selected-only filters are preserved.

## Acceptance
Given a new email, manual add creates one campaign record with status new. Given duplicate email in the same campaign, no duplicate appears. Given that email in another campaign, the original global profile remains unchanged. Given a mixed owned/foreign ID batch, no records change. Given selected contacts, stop blocks future queue sends and preserves terminal statuses. Given process restart, memberships and stops remain persistent.

## Tests and release gate
`tests/test_audience_launch_activity.py` (actual FastAPI+SQLite auth, duplicate, negative validation, foreign-transaction rollback, stop, persisted state), `frontend/src/pages/AudienceLaunchActivity.test.tsx` (form and confirmation). Run `uv run pytest tests/test_audience_launch_activity.py tests/test_outreach_api.py tests/test_outreach_engine.py -q`, `uv run pytest -q`, `cd frontend && npm test && npm run build`, board verifier and live Chrome/Postgres/concurrent-send acceptance. Not run in the GitHub-only source session.

**Rollback:** remove manual/bulk endpoints and the added UI; keep resulting contact/status data and archived events. No schema change. **Residual risk:** a send already claimed by a worker may be in flight; stop is not a guarantee of recall. Tenant-level ownership Q-27 remains open; don't overstate per-workspace row isolation.
