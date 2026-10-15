# F-06.21 — Follow-up Performance Centre

**Mode:** TASK · **Branch:** develop · **Status:** IN_REVIEW; implementation and tests authored, verification pending.

## Outcome and end-to-end flow

From **Follow-up performance**, operators select all campaigns or one saved campaign. The screen shows total human tasks, open, overdue, completed and completed on time, followed by a paginated workload breakdown by the existing free-text assigned_to label. Empty labels group as **Unassigned**; case and outer whitespace differences group together. This is **not a user-identity or permissions system**.

GET /api/v1/crm/followup-performance?campaign_id=&limit=25&offset=0 derives all figures from existing durable campaign_followup_tasks, with an explicit saved due/completed time comparison. An on-time task requires status=done, saved completed_at, and completed_at <= due_at; a currently overdue task requires open status and due before the report instant. Overall counts are computed independently of the paginated owner list. The page guides the operator to current campaign follow-ups or Campaigns to select one, without silently adding automation or notifications.

## Criteria

1. Saved open/done/on-time/overdue tasks count correctly, including unassigned labels, different casing, no tasks and page 2 retaining the same overall counts.
2. Campaign parameter rejects nonexistent IDs, pagination is bounded and read-only; owner labels do not imply workspace access or task permission.
3. UI provides campaign selection, truthful metrics, owner worklists, loading/error/empty states, accessible navigation and paging.

**Dependencies:** F-06.12 durable human task manager and campaigns. **Schema:** unchanged. **Tests written:** tests/test_crm_operations.py and frontend/src/pages/CRMOperations.test.tsx. **Still open:** full test suite, PostgreSQL query plan, real browser/keyboard, cross-workspace decision Q-27 and independent review. Reminder/sending automation is explicitly out of scope.