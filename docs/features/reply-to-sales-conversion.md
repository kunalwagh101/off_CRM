# F-06.13 — Qualified Reply-to-Sales Conversion

**Status: IN_REVIEW. Branch: develop only.**

## Complete user path
The user syncs an inbound reply, reviews it in the Reply Inbox, marks it Positive or Meeting, then explicitly confirms conversion in Contact 360. This action either links a matching existing Sales Tracker lead (same normalized email within the current Sales Tracker workspace) or creates a new lead at stage New. Nothing resumes email follow-ups, sends a message, books a meeting, or rewrites existing sales lead fields.

A durable campaign_sales_links table records one membership-to-lead relation per campaign contact. The conversion executes the campaign-member check, approved triage check, actual inbound existence, email reconciliation, lead creation or reuse and provenance link within one CRM write transaction. A repeated request returns the existing linked lead. Multiple existing leads with the same email cause a fail-closed error, rather than an arbitrary choice. An audit event records only the lead ID and whether it was created. No reply body is copied into Sales Tracker.

## Acceptance
1. A missing reply, unreviewed reply, non-positive reply, or foreign membership cannot create a lead.
2. Repeated promotion and the same email across different campaigns reuse the lead without overwriting its fields.
3. Ambiguous duplicate sales emails require manual reconciliation.
4. Campaign stop/replied state and send approvals are unchanged.
5. SQLite schema v10-to-v11 and PostgreSQL migration step 3 persist the link and include it in CRM backup inventory.

Tests authored: tests/test_relationship_intelligence.py and frontend/src/pages/RelationshipIntelligence.test.tsx. NOT RUN. Real PostgreSQL migration, concurrency and tenant boundary Q-27 checks are outstanding. Code rollback cannot safely downgrade a versioned database; use a verified backup or forward-compatible deployment.
