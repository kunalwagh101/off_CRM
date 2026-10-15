# F-06.14 — Contact 360 Workspace

**Status: IN_REVIEW. Branch: develop only.**

## Complete user path
Open a Contact 360 modal from Contacts, Reply Inbox, Follow-up Tasks or Today's Priorities. It shows campaign-scoped identity, status, counts of actual outgoing and received messages, latest received reply subject/date, explicit review outcome, outstanding human task count and earliest due action, and linked Sales Tracker opportunity. Authorized users can open the separate Communication History view for message previews, navigate to Follow-ups or Sales Tracker, and explicitly promote a qualified reply.

The protected GET endpoint validates exact campaign membership before querying the related records. Its response has strict field allowlists: never include raw provider JSON, message bodies, private contact notes, credentials, model prompts or message idempotency keys. This is a local CRM view, not an AI summary.

## Acceptance
1. No replies/tasks/opportunity means accurate zero and empty states.
2. Another campaign membership cannot be read.
3. Actual reply/task and linked opportunity appear without leaking private content.
4. The conversion option is shown only for explicitly triaged Positive/Meeting incoming replies.
5. Keyboard/modal focus and mobile layout require real browser acceptance.

Tests authored in tests/test_relationship_intelligence.py and frontend/src/pages/RelationshipIntelligence.test.tsx. They remain unrun; PostgreSQL, privacy and Q-27 tenancy review are required.
