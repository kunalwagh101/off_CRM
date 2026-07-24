# Sales tracker

OFF_CRM v0.11 introduced a local-first sales operating system for setters and closers. A lead card is the source of truth. The board, lead log, dashboard, commissions, leak signals and forecast read the same SQLite records, so no downstream result is entered twice.

## Views

### Kanban board

Statuses are New, Proposal, Deposit, Follow-Up Ongoing, Meeting Follow-Up, Won and Lost. Cards can be dragged on desktop or moved through the card status control on mobile. Moving to Lost requires a loss reason. Moving to Won requires a positive total deal value.

Each card stores:

- lead name, company, email, phone, source, setter and closer;
- created, first-contact, meeting-booked, meeting, deposit, paid-in-full and last-touch timestamps;
- meeting status, offer-made state, sale type and required loss reason;
- deposit, deal value, collected cash, refunds/clawbacks and commission percentage;
- notes, position, revision and audit timestamps.

Earnings are calculated as `(total deal value - refund/clawback) × commission percentage`. Net revenue is `total deal value - refund/clawback`.

### Lead log

The lead log exposes the card data as one horizontally scrollable table. It supports search, status, rep, source and date filters plus sortable lead, creation, meeting, deal, cash, earnings and last-touch columns.

### Visibility dashboard

The dashboard is filtered by lead creation date, rep and source. It calculates:

- setter activity, conversations-to-booked, speed to lead, booking lag, scheduled/taken calls, declines, cancels, no-shows, reschedules, show rate and DQ rate;
- closer offer rate, close rate on calls, close rate on offers, one-call/follow-up sales, average deal size, revenue per call and aging follow-ups;
- deposits, sales, revenue, cash, paid-in-full conversion, collection time, refunds/clawbacks, net revenue, goals and commission by closer;
- required Lost-reason distribution.

Daily setter activity uses an upsert key of workspace + date + setter. Re-saving a date corrects the existing row rather than adding duplicate activity.

### Projection

The projection estimates incremental and end-of-month revenue/cash from meetings scheduled × show-up rate × offer rate × close rate × average deal size. It produces worst, expected and best cases. Rates use observed history when available; average deal size can use won history or open pipeline. Any manual override and conservative fallback is labelled in the response and UI.

## Leak rules

The backend, board, log and dashboard highlight:

- booking lag greater than four days;
- Follow-Up Ongoing with no touch for seven or more days;
- a received deposit not paid in full for fourteen or more days.

Deposit receipt time is stored separately from amount so the fourteen-day rule is deterministic. If a deposit amount is entered without a receipt time, the backend records the save time.

## Consistency and audit

Every lead has a revision number. Edits and moves include the revision observed by the browser; a stale write receives HTTP 409 and cannot overwrite a teammate's newer change. Create, edit and status-change events are appended to `sales_lead_events`.

SQLite schema version 6 adds `sales_leads`, `sales_setter_activity`, `sales_monthly_goals` and `sales_lead_events`. Existing databases receive these tables automatically on startup.

## API

- `GET /api/v1/sales/meta`
- `GET /api/v1/sales/board`
- `GET|POST /api/v1/sales/leads`
- `GET|PATCH /api/v1/sales/leads/{lead_id}`
- `POST /api/v1/sales/leads/{lead_id}/move`
- `GET /api/v1/sales/leads/{lead_id}/events`
- `GET|POST /api/v1/sales/activity`
- `GET|PATCH /api/v1/sales/goals/{YYYY-MM}`
- `GET /api/v1/sales/dashboard`
- `POST /api/v1/sales/projection`

The interactive API reference is available at `/api/docs` while the app is running.
