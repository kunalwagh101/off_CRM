# off_CRM
Version 0.12 adds user-controlled parallel discovery workers (1-4, with per-site politeness preserved), one-way Notion export for campaign contacts and sales leads (encrypted local token, schema-aware property matching), a clickable pipeline overview on the dashboard, and plain-language engine/worker controls on the Discovery page.

Version 0.11 adds a complete setter-and-closer sales tracker. Kanban lead cards now drive the lead log, visibility metrics, commissions, leak detection and evidence-labelled monthly forecasts without duplicate entry. The full POI-to-outreach workflow remains local-first and inspectable.

## What is included

- Apollo search for new POIs
- Sales Kanban with New, Proposal, Deposit, Follow-Up Ongoing, Meeting Follow-Up, Won and Lost stages
- Complete lead cards for ownership, dates, meeting disposition, call outcome, loss reason, money and last touch
- Filterable/sortable lead log, setter and closer scorecards, money goals and net commissions
- Best/expected/worst monthly revenue and cash projection with assumption provenance
- Automatic red flags for booking lag, aging follow-ups and unpaid deposits
- Public-page discovery using safe HTTP or optional Crawl4AI 0.9.x JavaScript rendering, with robots.txt, allow-list, rate, size and SSRF controls
- User-selected parallel discovery workers (1-4); a shared per-domain rate limiter keeps politeness identical to a sequential crawl, so extra workers only speed up multi-site runs
- One-way Notion export: contacts and sales leads upsert into your chosen Notion databases; the token is Fernet-encrypted on this device and only existing Notion properties are filled
- Bounded research prompts that compile into target, role, source and connector requirements
- Local person, company, source-page and reference-only social-profile graph
- Visible Apollo rejection outcomes plus automatic permanent exclusion of accepted Apollo contacts
- Reviewable discovery evidence before a POI enters Apollo or the CRM
- Automatic exclusion against `old_pois`, previous outputs and existing CRM contacts
- Existing POI CSV/XLSX/XLS enrichment with queue safety and credit caps
- Campaigns, contacts, draft review, send queue, A/B reporting and CRM exports
- Three-stage email sequences: first touch, follow-up 1 and follow-up 2
- Reply detection that cancels all unsent follow-ups
- Human approval before every eligible send
- Safe local outbox by default
- Gmail OAuth with explicit live-send confirmation
- Provider-neutral AI adapters for OpenAI, Anthropic, compatible APIs and the future template application
- Priority-ordered AI failover with normalized output and provider health tests
- Encrypted local provider profiles and API keys
- Reply-first automation with hard daily limits and a disabled-by-default Gmail gate
- Passphrase-encrypted local backup and restore
- Local SQLite storage with no third-party server between the user and their providers
- Expert-source retrieval with source and rights provenance
- Temporary demo login with signed, secure, HTTP-only sessions and login throttling
- Render Blueprint configuration and automatic `PORT` support
- Exact pre-send preview, correction, bulk apply, re-audit and scheduling controls
- Priority, round-robin and parallel-first-success AI routing
- Per-provider minimal, standard or full data policies with opt-in redacted payload logs
- Replaceable local memory/RAG backend that learns from human edits and labelled outcomes
- Experiment hypotheses, controls, minimum samples, confidence intervals and lift

The old Apollo workflows remain intact. Outreach does not use the legacy team-assignment engine.

## Sales tracker workflow

1. Open **Sales tracker** and create or move lead cards on the Kanban board.
2. Enter a setter's dials/DMs, conversations and declines once through **Daily activity**.
3. Review the **Lead log** for every card field, or filter the **Visibility dashboard** by rep, source and date.
4. Set the monthly revenue/cash goal, then open **Projection** for best, expected and worst end-of-month scenarios.

Earnings, conversion rates, revenue, cash, net revenue, commissions, loss analysis, aging and projections are calculated by the backend. See `docs/SALES_TRACKER.md`.

## Lead discovery workflow

1. Open **Lead discovery** inside a campaign.
2. Describe the target in the research prompt and add public company-team, event-speaker, association-directory or biography URLs.
3. Choose safe HTTP or the local Crawl4AI JavaScript worker. Both stay inside policy controls; Scrapling normalizes structured Person evidence and the CRM stores an audit hash instead of raw HTML.
4. Existing POIs are marked excluded before review.
5. Review the research graph, approve useful POIs, then add them to the CRM or place them in `local_data/poi_file_queue/inbox` for Apollo.
6. Apollo accepts enter the permanent exclusion ledger. No-match, no-email and policy rejects appear in the CRM rejection list with an explicit retry policy.

Authenticated LinkedIn or Instagram scraping is intentionally not enabled. Those sites require an approved official API or manual import. AI providers never receive browser sessions, cookies or connected-account credentials. See `docs/LEAD_DISCOVERY.md`.

## Quick start

Install Python and frontend dependencies:

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
```

Copy `.env.example` to `.env`. Keep the default loopback host.

Start the complete application:

```powershell
uv run python run_offsetx_web.py
```

Open `http://127.0.0.1:8766`.

To enable the local Crawl4AI JavaScript engine:

```powershell
uv sync --extra dev --extra crawler
uv run crawl4ai-setup
```

Keep the safe HTTP engine on the small free Render demo. Chromium-based crawling is intended for a local or separately sized worker.

The API reference is at `http://127.0.0.1:8766/api/docs`.

## Render demo

The checked-in `render.yaml` defines a free Docker web service in Singapore. A manual Render setup needs these private environment variables:

```env
OFFSETX_DEMO_USERNAME=choose-a-demo-username
OFFSETX_DEMO_PASSWORD=choose-at-least-12-characters
OFFSETX_SESSION_SECRET=generate-at-least-32-random-characters
OFFSETX_SESSION_HOURS=8
```

`OFFSETX_WEB_HOST=0.0.0.0` is already set by the Docker image. Render supplies `PORT` automatically. Do not add Gmail or AI keys for a basic UI demo.

The free Render filesystem is temporary. SQLite data, outbox files and configuration can disappear after a restart or redeploy. Use the Render service only for disposable demonstration data.

## First outreach workflow

1. Create a campaign and choose a daily limit, timezone and send window.
2. Import `examples/outreach_contacts_sample.csv` or an Excel file.
3. Generate the three-stage sequence using local templates or a configured AI provider.
4. Review the exact output, edit it, optionally apply a correction to selected drafts, schedule it, then approve it.
5. Run the local outbox first.
6. Connect Gmail only after reviewing the local results.
7. Sync replies before every send run. The backend also does this automatically.

Local outbox files are written under `local_data/mail/outbox`.

Configure the audited sender signature privately in `.env` or Render environment variables:

```env
OFFSETX_SENDER_NAME=Your name
OFFSETX_SENDER_ROLE=Building off_CRM - carbon-market infrastructure
OFFSETX_SENDER_EMAIL=you@example.com
OFFSETX_SENDER_LINKEDIN=https://www.linkedin.com/in/your-profile/
```

Personal sender details are intentionally not committed to Git.

## Required contact evidence

A sendable first touch requires:

- POI name
- valid email before sending
- one of the nine locked categories
- verified public hook
- public hook source
- route-specific CTA
- exact off_CRM signature
- one question mark
- no confidential or manipulative language

## AI provider portability

API keys are never stored in the database. They can remain in environment variables or be stored in an encrypted local provider vault. The Settings page manages multiple providers, health state, routing strategy, payload policy and call audit. Every provider is normalized to the same subject/body contract.

`minimal` removes recipient identity before a provider call, `standard` removes direct contact data and URLs, and `full` sends the generation context. Request/response bodies are not logged unless the operator explicitly enables local redacted payload logging for that profile.

Examples are in `config/`.

The separate template-intelligence application will integrate through:

```text
POST /v1/generate
```

The normalized contract is documented in `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`.

## Gmail connection

Create a Google OAuth desktop client and set:

```env
OFFSETX_GMAIL_CLIENT_SECRETS=path/to/client_secret.json
OFFSETX_GMAIL_TOKEN=local_data/gmail_token.json
OFFSETX_OWN_EMAIL=your-email@example.com
```

Then authorize locally:

```powershell
uv run python run_offsetx_outreach.py gmail-authorize
```

Gmail live send requires the exact confirmation `SEND LIVE EMAILS` in the UI or CLI.

The current Gmail authorization is a local desktop OAuth flow. Do not upload a personal Gmail token to the free Render demo. A hosted Gmail connection requires a separate web OAuth callback and durable encrypted credential storage.

## Tests

```powershell
uv run pytest -q
cd frontend
npm test
npm run build
```

Release result:

```text
63 Python tests passed
3 frontend tests passed
production frontend build passed
```

## Apollo workflows

Existing POI queue status:

```powershell
uv run python run_offsetx_apollo.py --queue-status
```

Existing POI dry run:

```powershell
uv run python run_offsetx_apollo.py `
  --enrich-existing-pois `
  --outdir output_existing_poi_enrichment `
  --run-id dry_existing_pois_001 `
  --credit-cap 10 `
  --batch-size 5 `
  --dry-run
```

Apollo search dry run:

```powershell
uv run python run_offsetx_apollo.py `
  --outdir output_dry_run `
  --run-id search_dry_001 `
  --target-count 250 `
  --credit-cap 250 `
  --dry-run
```

See `docs/EXISTING_POI_ENRICHMENT.md` for the full legacy workflow.

## Documentation

- `docs/INTELLIGENCE_ARCHITECTURE.md`
- `docs/LEAD_DISCOVERY.md`
- `docs/SYSTEM_ARCHITECTURE_V06.md` (historical v0.6 decision record)
- `docs/WEB_CRM.md`
- `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`

## Important safety rule

Do not upload copied paid courses or private material to the expert library. Use owned notes, licensed material, permissioned transcripts or public material with clear provenance.
