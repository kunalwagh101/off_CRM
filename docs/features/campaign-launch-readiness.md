# F-06.08 — Campaign Launch Readiness Center

**Status:** IN_REVIEW, no live-provider certification.

## User outcome
See why an email campaign is not yet prepared for an outbound run, directly from saved CRM data and without clicking Send to find out.

## Source-backed checks
`GET /api/v1/campaigns/{id}/launch-readiness` is authenticated, read-only and uses the existing `OutreachStore.send_queue_view` to count all campaign members and approved/due/sendable candidates. It checks active status, nonempty audience, at least one approved and due/sendable draft, and remaining daily quota computed using the campaign's time zone and recorded outbound messages. Non-email campaign kinds receive an explicit unsupported-kind result instead of interpreting an image project as email.

The screen shows check-by-check feedback and navigation to Campaigns, Contacts, Draft review or Queue; Recheck fetches current state without mutating anything.

**Crucial distinction:** `eligible_for_local_review` means these *local operational checks* pass, not that a message is authorised or guaranteed deliverable. The response explicitly marks `external_delivery_verified=false`. Suppression, source verification, recipient validity, provider credentials, consent/permission, send-window enforcement and final live-provider preflight remain in the existing actual sender. No send action exists on this new screen.

## Acceptance
Given no contacts, readiness explains missing audience and drafts. Given an imported/manual contact but no approved draft, candidate count remains zero. Given a sendable approved due draft, all local checks can pass, while external verification remains false. Given a paused campaign, it cannot be ready even with a draft. Given an unknown ID, the API refuses with not found. No mail can be sent by GET.

## Tests/limits
Python API regression in `tests/test_audience_launch_activity.py` + frontend SSR in `frontend/src/pages/AudienceLaunchActivity.test.tsx`. Needs real SQLite/PostgreSQL/Chrome/timezone and provider-independent acceptance, full suites, security review and board verifier. No migration. Rollback removes new read-only route and screen only.
