# F-06.18 — Campaign-to-Revenue Attribution

**Branch:** develop. **State:** IN_REVIEW; real DB and UI tests not yet executed.

## User value
Follow the existing chain from campaign contacts and received replies to reviewed qualified replies, linked Sales Tracker opportunities, won deals and recorded money. Unlike inflated multi-touch dashboards, the same sales lead cannot contribute revenue twice when linked to more than one campaign.

## Attribution contract
Read-only authenticated `GET /api/v1/crm/attribution?limit=25&offset=0`. A SQL window function assigns each sales lead to the **earliest recorded campaign_sales_links link** by `(linked_at, campaign_contact_id)`, across the same Sales Tracker workspace. `ROW_NUMBER()=1` is the only row eligible for attributed lead, win/loss and monetary totals. Per-campaign metrics also independently include campaign membership count, saved replied count, manually triaged Positive/Meeting count, and *all* link memberships (so operators can distinguish multiple associations from uniquely attributed deals).

Fields:
- `attributed_leads`: unique, earliest-linked opportunities.
- `won_deals` and `lost_deals`: attributed leads with matching saved Sales Tracker status.
- `booked_value`: sum total_deal_value of attributed Won leads.
- `recorded_cash`: sum cash_collected of attributed Won leads.
- `cash_less_clawbacks`: sum cash_collected minus refund_clawback_amount of attributed Won leads; can be negative and is not an independently verified payment ledger.
- `overall`: full-campaign totals from the same one-lead-only assignment, **independent of paginated campaign results**.
- `value_units`: monetary units from Sales Tracker; no conversion, do not aggregate inconsistent currencies.

Every campaign appears including those with zero links; server paginates campaigns deterministically. No emails are sent, calls scheduled, AI revenue projected or money altered.

## Critical limitation
This is **CRM-first-link association**, not evidence that the linked campaign caused the sale, a multi-touch causal model or GAAP recognised revenue. Missing CRM links mean unattributed sales are omitted. The app labels this prominently instead of implying stronger evidence. Only records in the current Sales Tracker workspace contribute.

## Acceptance
- A single won lead linked to two campaigns contributes exactly one win and one monetary sum to the earliest linked campaign.
- Different campaigns may report two converted membership links but only one attributed lead; full overall metrics equal unique linked leads.
- Won/open/lost pipeline states count correctly, page 2 does not alter overall totals, negative clawback math preserved.
- No foreign workspace records; 0-link campaigns included; auth and query bounds enforced.
- Full Python/SQL/PostgreSQL/window-function, UI, backup and independent financial interpretation review before DONE.

**Source:** `outreach/crm_insights.py`, `api/app.py`, `frontend/src/pages/RevenueAttribution.tsx`. Tests authored in `tests/test_crm_insights.py` and `frontend/src/pages/CRMIntelligence.test.tsx`. No migration, writable API or external service.
