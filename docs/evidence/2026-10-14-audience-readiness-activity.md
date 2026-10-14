# Develop continuation — three product features (2026-10-14)

**User direction:** three next *features*, not three micro-stories. **Mode:** TASK; product/engineering owner. **Branch:** `develop` only. **Release state:** IN_REVIEW.

Feature IDs and product specs:
- **F-06.07 Audience Management Workspace** — `docs/features/audience-workspace.md`
- **F-06.08 Campaign Launch Readiness Center** — `docs/features/campaign-launch-readiness.md`
- **F-06.09 Campaign Activity & Audit Timeline** — `docs/features/campaign-activity-timeline.md`

These were selected after source inspection confirmed import-only contact creation, no read-only campaign launch checker and an event endpoint without a user-facing timeline. Existing send_queue, protected contact/CRM storage, events and security middleware are reused. No new paid service or persistence schema was introduced; live sending and approvals are not automated.

## Changed code
`offsetx_apollo_builder/api/schemas.py`, `offsetx_apollo_builder/api/app.py`, `offsetx_apollo_builder/outreach/store.py`, new `offsetx_apollo_builder/outreach/launch.py`, `frontend/src/pages/Contacts.tsx`, new `frontend/src/pages/AudienceOperations.tsx`, `frontend/src/pages/LaunchReadiness.tsx`, `frontend/src/pages/CampaignActivity.tsx`, `frontend/src/App.tsx`.

## Test source written, no execution evidence
- `tests/test_audience_launch_activity.py`: strict auth/validation, duplicate and cross-campaign contact linking, atomic foreign-ID refusal, terminal stop, manual stop/mark and restart, read-only launch checks with actual local draft approval, 57-event timeline with facet, filter and paging.
- `frontend/src/pages/AudienceLaunchActivity.test.tsx`: manual form, typed STOP, launch status and next actions, URL encoding, metadata allowlist and no raw sensitive event payload render.
- Existing API/outreach regression tests remain required.

Commands to execute from a real checkout:
```bash
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest tests/test_audience_launch_activity.py tests/test_outreach_api.py tests/test_outreach_engine.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```
Manual: Chromium desktop/mobile, after-restart SQLite/PostgreSQL, concurrent local worker vs bulk STOP, event pagination during concurrent writes, authenticated unauthorised access, screen-reader keyboard focus.

## Verification limits
The GitHub connector provides source read/commits but no runnable private working checkout here; earlier Actions `quality` and `postgres` failed before executing any steps. These tests have not been run or red/green observed. No independent reviewer, PostgreSQL/Chrome/live send or deployed release is claimed. The current app's documented tenant ownership decision Q-27 and durable worker/backup blockers are unaffected. Do not mark DONE until verification and relevant risk review pass.

## Decisions and rollback
- DD-105: manual contact entry conservatively links existing email, no implicit send.
- DD-106: batch selection explicit IDs capped at 100; stop fail-closed for new sends but cannot recall an in-flight external send.
- DD-107: local readiness is an explanatory preflight, not live provider assurance.
- DD-108: event feed displays only approved metadata, preserves existing API contract.
Rollback: revert these new screens/endpoints/store helpers and optional events facet/query; keep durable contacts, stops and event history. No migration or secret change.
