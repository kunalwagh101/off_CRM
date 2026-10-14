# F-06.10 — Reply Inbox & Human Triage

**Status:** IN_REVIEW · **Branch:** develop · **Leading role:** senior full-stack engineer.

## Product journey
A campaign operator sees actual incoming messages as one thread entry per campaign contact, sorted by the most recent stored reply. A received message is available as a bounded 500-character preview; the operator can open the full conversation, classify the outcome, enter an internal review note and create a linked human task. This does **not** send a reply, revoke or grant contact permission, or restart follow-up automation.

## Data ownership
The current global `contacts.outcome_label` is intentionally not used for campaign-specific review: one person may be approached by two campaigns with different results. New `campaign_reply_triage` table keys on `campaign_contact_id` (unique membership) with `review_status=unreviewed|triaged`, outcome enum (positive, neutral, negative, meeting, not_interested, wrong_person), note bounded 1,000 and timestamp. Existing `messages` remains the truth for inbound presence. Retains previous reply-stop behavior.

## API / UI
- Authenticated `GET /api/v1/campaigns/{id}/replies/inbox?limit=50&offset=0&review_status=unreviewed&outcome=`: SQL-level filtering before paging, at most 100 rows. No raw provider JSON or token, only bounded reply preview and contact identity.
- Authenticated `PATCH /api/v1/campaigns/{id}/replies/{membership_id}/triage`: strict enum, verifies membership and an actual received message; updates per-campaign review only and emits a metadata-only event.
- `#replies` screen: filter review/outcome, list previews, review modal, open communication history and create a human follow-up.

## Acceptance
Given a stored reply, new inbox shows it unreviewed. Given triage, it moves to Reviewed only in the correct campaign while status remains replied. Given an unrelated campaign/recipient, the API denies instead of leaking or changing data. Given 51+ responses, both pages remain accessible; no external mail is triggered by any read or triage.

## Evidence / limits
`tests/test_relationship_workflows.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx`; suite not run in this GitHub-only session. Needs production auth and workspace tenant isolation Q-27 decisions, PostgreSQL migration, live browser, actual Gmail sync and reply-stop concurrency acceptance. No model dependency or cache. Rollback requires compatible restored database; do not downgrade a schema-versioned database by simply deploying old binaries.
