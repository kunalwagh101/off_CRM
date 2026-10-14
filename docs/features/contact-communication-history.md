# F-06.11 — Contact Communication History

**Status:** IN_REVIEW · **Branch:** develop.

## User journey
From a campaign contact or a reply, open a chronological correspondence view for **that campaign membership**, showing direction, subject, bounded body preview and received/sent time. The view also works before any message exists; no new message is generated or sent.

## Data contract
`GET /api/v1/campaigns/{campaign_id}/contacts/{campaign_contact_id}/messages?limit=25&offset=0`, bound 1–100. Validate the contact belongs to the requested campaign before accessing any messages. Query only `id, direction, stage, subject, SUBSTR(body,1,2000), truncated, timestamps`, newest-first with stable ID tie-break. Never expose `raw_json`, provider metadata, idempotency keys or other campaign contacts' messages. This is deliberate **authorised in-app access to message previews**, not redaction or public export.

## Acceptance
Given 52 messages, paging retrieves distinct first and second sets and accurate total. Given a message body longer than 2,000 chars, show truncated text with a notice. Given foreign campaign membership, return not found. No automatic external requests. Browser can open from Contacts, Reply Inbox and linked Follow-up Task.

## Required verification
Backend `tests/test_relationship_workflows.py` (pagination, foreign scope, raw-JSON exclusion); frontend `frontend/src/pages/RelationshipWorkflows.test.tsx` (render). Real auth, cross-user workspace boundary Q-27, SQLite/PostgreSQL, browser keyboard/focus/mobile, sensitive-data retention and independent security review remain unverified. No extra schema for this feature.
