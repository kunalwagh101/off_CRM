# F-06.20 — Campaign Comparison Dashboard

**Mode:** TASK · **Branch:** develop · **Status:** IN_REVIEW; no passed executable checks claimed.

## Outcome and end-to-end flow

**Compare campaigns** shows all existing campaigns, with optional literal-safe name filter and server-side paging. Each campaign shows saved contact membership, uniquely contacted members (at least one outbound message), uniquely replied members with both outbound and inbound messages, all members with inbound messages, manually qualified Positive/Meeting replies and campaign-sales *link memberships*.

GET /api/v1/crm/compare?search=&limit=25&offset=0 uses correlated indexed membership/message existence checks. Messages are never duplicated into contact counts. Reply rate is (members with both outbound and inbound)/(members with outbound), or N/A when no member has outbound, and is a descriptive rate, not causal lift. Inbound-before-outbound timing is not inferred; the rate counts presence of both records, not causal chronology. Sales links are not won deals or unique revenue; the existing attribution screen remains authoritative for unique recorded financial association. The operator can open Campaign activity in the existing UI.

## Criteria

1. Repeated outgoing or incoming messages do not double-count members; campaigns with no sends show N/A, not a misleading zero percent.
2. Page/filter limits are enforced, names are searched literally, and stable pagination does not discard empty campaigns.
3. UI shows definitions, loading/error/empty states, six real metrics, navigation and accessible paging.

**Dependencies:** Existing campaigns, campaign contacts, messages, manual reply triage and conversion links. **Schema:** unchanged. **Tests written:** tests/test_crm_operations.py and frontend/src/pages/CRMOperations.test.tsx. **Required before DONE:** all Python/frontend gates, actual SQLite and PostgreSQL performance, real browser and accessible keyboard review. No sending path changes.