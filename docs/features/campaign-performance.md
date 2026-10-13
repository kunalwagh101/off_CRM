# Product feature — Campaign Performance Intelligence

**Module:** Campaigns; branch develop; state **IN_REVIEW**.

The screen can open an on-demand read-only campaign performance panel, backed by the real CRM, not fabricated dashboard metrics. Protected endpoint `GET /api/v1/campaigns/{id}/performance`.

## Defined measurements

- Contacts: campaign memberships. Contacted: DISTINCT campaign recipients with at least one recorded outbound message. Messages sent: all recorded outbound rows.
- Replies: campaign contacts whose persisted status is replied. Replied contacted: replied records **among those with at least one outbound message**.
- **Reply rate = replied-contacted / unique-contacted × 100**. A manual replied status without an outbound message must not inflate a response rate; the denominator is explicit. Zero sent => 0%.
- Waiting on first contact: imported campaign memberships minus distinct contacted recipients. Completed and stopped counts from stored state.
- Draft statuses: grouped approved/pending/etc counts from persisted draft rows. No assumption that a draft is a real send.
- Only email campaigns get a reply-rate percentage. Other campaign kinds show operational counts and N/A for that email-specific metric. No claim of inbox placement, provider delivery or exact attributable revenue.

UI provides contact, distinct outreach, outbound, replies, rate, awaiting contact, completed, stopped, draft-status breakdown and refresh.

## Quality and release

Python integration regression exercises a real local-outbox send, an unsent manual reply, a subsequently replied sent recipient, API authentication and zero-denominator behavior. Frontend SSR test checks displayed denominator. PostgreSQL, full Python/frontend, live Chromium, independent review and CI remain **unrun**. All metrics describe database state. No external analytics provider is queried. No new table. Rollback endpoint/panel only; records unchanged.
