# OffsetX CRM v0.11 handoff

Prepared: **19 July 2026**  
Repository target: **kunalwagh101/off_CRM**

## Status

OffsetX CRM is a working local-first POI discovery, Apollo enrichment, email outreach and sales-tracking application. It has a FastAPI backend, React control centre, SQLite source of truth, protected Render demo configuration, provider-neutral AI generation, approval-first sending, prompt-driven discovery, a research graph and a setter/closer sales operating system.

It is suitable for local operation and disposable demo testing. It remains a single-user application, not a production multi-tenant SaaS.

## New in v0.11

- Seven-stage drag-and-drop sales Kanban with mobile status controls.
- Complete lead cards for contact, ownership, dates, meeting status, call outcome, loss reason, money and follow-up tracking.
- Required loss reason on Lost and deal value on Won.
- Filterable/sortable all-fields lead log.
- Setter activity and visibility: dials/DMs, conversations, conversations-to-booked, speed to lead, booking lag, scheduled/taken calls, declines, cancels, no-shows, reschedules, show rate and DQ rate.
- Closer visibility: offers, offer rate, both close rates, one-call/follow-up sales, average deal size, revenue per call and aging follow-ups.
- Money visibility: deposits, sales, revenue, cash, paid-in-full conversion, days to collect, refunds/clawbacks, net revenue, goals and net commissions.
- Required loss-reason breakdown.
- Best/expected/worst monthly revenue and cash forecast with assumption provenance.
- Red leak signals for booking lag over four days, untouched follow-ups at seven days and unpaid deposits at fourteen days.
- Optimistic revisions and an append-only event history prevent silent card overwrites.

All downstream sales outputs are calculated by the backend from lead cards. Setter daily activity and monthly goals are the only separate inputs explicitly required for their respective metrics.

## Existing completed systems

- Apollo search and existing-POI enrichment with credit and queue safety.
- Prompt-driven public-web discovery with guarded HTTP and optional Crawl4AI rendering.
- Research graph and visible Apollo rejection/permanent exclusion ledgers.
- Campaigns, contacts, draft review, corrections, approval, scheduling, queue, exports and reply-stop automation.
- Local outbox and explicit Gmail live-send gate.
- OpenAI, Anthropic, compatible-provider and future template-app adapter contract.
- Encrypted provider profiles, normalized output, health state, circuit breaking and failover.
- Per-provider data minimization and opt-in redacted request logs.
- Local memory/RAG boundary for approved human corrections and labelled outcomes.
- Versioned email templates, evidence requirements and A/B reporting.
- Password-protected Render demo, signed HTTP-only sessions and non-root Docker image.

## Verification

| Check | Result |
| --- | --- |
| Python tests | **69 passed** |
| Frontend tests | **4 passed** |
| React/TypeScript production build | **Passed** |
| Live FastAPI process and sales API smoke | **Passed** |
| Git whitespace/diff validation | **Passed** |
| SQLite schema | **v6** |
| Package version | **0.11.0** |

Two non-blocking dependency deprecation warnings remain: Starlette TestClient/httpx compatibility and an lxml parser option.

## Run locally

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run python run_offsetx_web.py
```

Open `http://127.0.0.1:8766`, then choose **Sales tracker** in the navigation.

## Render demo

The existing `render.yaml` and Dockerfile run the compiled React frontend and FastAPI backend as one free Render web service. Configure a demo username and a password of at least twelve characters; Render generates the session secret. Runtime data uses `/tmp/offsetx/local_data`, so it is disposable.

Use synthetic contacts, local outbox mode and no personal Gmail tokens, private expert material or live provider secrets on the free demo.

## Production boundary

Before remote multi-user use, add real identity/tenancy, PostgreSQL row-level ownership, durable job workers, centralized secrets, encrypted durable storage and an audited hosted Gmail OAuth callback. The current workspace IDs and provider/memory interfaces are designed to support that migration, but those controls are not claimed as implemented.

## Documentation

- `README.md`
- `CHANGELOG.md`
- `docs/SALES_TRACKER.md`
- `docs/LEAD_DISCOVERY.md`
- `docs/INTELLIGENCE_ARCHITECTURE.md`
- `docs/WEB_CRM.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`
- `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`

## GitHub handoff

This workspace still has no configured `origin` remote or injected GitHub credential. The completed source can be copied over the authenticated local clone while preserving its `.git` folder, then committed and pushed from that clone. The release archive intentionally excludes `.git`, local databases, mail data, OAuth tokens, provider secrets, environments and dependency caches.
