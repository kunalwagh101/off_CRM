# F-06.15 — Daily Action Command Center

**Status: IN_REVIEW. Branch: develop only.**

## Complete user path
The selected campaign's Today's Priorities screen shows three source-backed queues: overdue human tasks, incoming replies still requiring triage, and linked nonterminal Sales Tracker opportunities with no recorded sales touch or a last touch older than seven days. The operator can filter these types, see truthful full-campaign counters, navigate to the relevant existing screen, or inspect Contact 360. No automatic emails, task completions, reminders, scoring models or paid API calls are introduced.

The authenticated endpoint composes a bounded database UNION from the saved task, message, review and sales-link tables. Exact campaign membership and Sales Tracker workspace are checked. One sales lead linked to multiple campaign members appears only once per campaign. Filtering occurs before LIMIT/OFFSET and order is deterministic: overdue task, then unreviewed reply, then sales attention. No private message content or customer notes are returned.

## Acceptance
1. Only genuinely overdue open tasks, unreviewed received replies and qualifying active opportunities appear.
2. Future or completed tasks, triaged replies and won/lost/recently-touched opportunities are excluded.
3. Server-side filtering/paging preserves truthful counts.
4. No foreign campaign's tasks/replies/linked leads appear.
5. Invalid filters, limits and offsets are rejected.

Tests authored in tests/test_relationship_intelligence.py and frontend/src/pages/RelationshipIntelligence.test.tsx. Not run. 10k+ member performance, PostgreSQL plan, browser and Q-27 isolation review remain outstanding.
