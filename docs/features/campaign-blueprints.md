# Product feature — Campaign Blueprint Reuse

**Module:** Campaigns; branch develop; state **IN_REVIEW**.

The user can duplicate a successful campaign's operating settings into a new, independently selectable campaign. The copy starts **paused in the same transaction that inserts the campaign** — no temporary active state with a possible worker send.

Only campaign-level settings are copied: kind, send cap, timezone, weekday/window schedule, follow-up timing, approval mode, A/B variants, hypothesis, control variant and minimum sample size. There is no copy of recipient memberships, CRM contacts, draft text, outbound/inbound messages, outboxes, credentials, provider profiles or historical statistics. A new UUID is allocated; the event log records the source ID. The source remains unchanged.

Protected endpoint `POST /api/v1/campaigns/{source_id}/clone` takes a strictly validated name. The app's existing idempotency-key mechanism prevents duplicate copies on a repeated request with the same key. The screen describes exactly what is and is not copied and offers a paused copy action.

## Acceptance and gates

Given a campaign with contacts and sends, when duplicated, the new one has zero recipients, zero sends, status paused and the same settings. Given replay of the same idempotency key, the same new campaign is returned. Given an inaccessible source or disallowed payload fields, the API refuses. The saved copy must survive process restart and database migration. Regression tests in `tests/test_campaign_product_features.py` and frontend smoke tests.

No new migration. Rollback must not auto-resume a previously copied campaign. **Unverified:** full API/CI/PostgreSQL/browsers and real worker race acceptance.
