# F-06.09 — Campaign Activity & Audit Timeline

**Status:** IN_REVIEW.

## User outcome
Investigate the history of a campaign without querying the database manually or navigating away from off_CRM.

## Source-backed workflow
The existing campaign event writer is unchanged. Extend the authenticated `GET /api/v1/campaigns/{id}/events` with an optional exact `event_type` predicate applied **before** COUNT and LIMIT/OFFSET, retaining the previous default unfiltered response. Stable ordering uses `created_at DESC, id DESC`. A new read-only `GET /api/v1/campaigns/{id}/events/types` returns distinct types and counts for the selected campaign. UI page `#activity` adds a type facet, 50-event pagination, refresh, a labelled timeline and basic human-readable operation types.

The UI permits only a small allowlist of non-content event payload metadata (action enum, numeric counters, safe field names). It **does not display** raw payloads, customer emails, private message bodies, secrets or arbitrary user-provided source strings. Existing API payload contract remains unchanged for existing clients; this is a conservative *presentation policy*, not a redesign of internal event retention or a blanket claim that all payloads are safe. No deletion/mutation.

## Acceptance
Given 57 events, UI and API expose first 50 and remaining seven without duplicate IDs. Given a filter, both total and page contain only that type. Given no match, show a helpful empty state. Given unauthenticated request, both event endpoints are denied. Raw payload secret-like strings must not appear in displayed event descriptions.

## Tests and release
Python `tests/test_audience_launch_activity.py`, frontend `frontend/src/pages/AudienceLaunchActivity.test.tsx`; pending full suites, actual keyboard/mobile browser, multi-tenant/Postgres verification, independent review. No migration. Rollback UI route and optional type filtering; preserve original read contract and historical event records.
