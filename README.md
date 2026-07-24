# OFF_CRM

OFF_CRM v0.12 is a local-first lead-discovery, outreach, sales-tracking, and AI workspace. Lead generation, Apollo enrichment, campaigns, draft review, Gmail sending, reply-stop automation, setter/closer tracking, and projections remain in one inspectable application.

The new OFF_AI Studio adds multi-model chat and campaign intake without giving any model a mailbox, CRM, memory, file, or database tool. OFF_CRM constructs one minimal packet, blocks prohibited data, sends it through one broker, and records the exact packet for the owner.

## What is included

- AI is the first item in the left navigation.
- The global left navigation and AI chat/project history drawer close and reopen independently.
- Persisted AI chats, projects, search, pin, rename, archive, Markdown/HTML project export, and browser dictation.
- Deterministic-first CSV, XLSX, XLS, PDF, TXT, and Markdown campaign intake.
- Auto-detected Generate and Parse & send modes with a masked preview and one mode choice when ambiguous.
- Per-draft view, edit, regenerate, bulk correction, scheduling, approval, and Gmail/local-outbox delivery.
- Config-driven, quota-aware provider routing with trust tiers, jurisdiction, retention, model provenance, costs, caps, and same-tier failover.
- Exact provider egress audit and owner-controlled Markdown/JSON activity export.
- In-app Gmail OAuth connection with the Gmail token isolated inside the mail module.
- Networkless, read-only execution for immutable, pinned public GitHub tools.
- Apollo search/enrichment queues, permanent accepted-contact exclusions, visible rejection outcomes, and credit controls.
- Public-web discovery with robots.txt, SSRF, domain, rate, redirect, size, and content-type controls.
- User-selected discovery workers from one to four. A shared per-domain limiter keeps the same request spacing as sequential crawling.
- One-way Notion export for campaign contacts and sales leads. The local token is encrypted and only matching properties in existing databases are written.
- Seven-stage sales Kanban, complete lead cards, lead log, setter/closer/money dashboards, leak alerts, commissions, goals, and projections.
- Local SQLite persistence, encrypted provider keys, encrypted backups, login protection, and audit history.

## Quick start

Requirements: Python 3.10+, Node.js 24+, and `uv`.

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
Copy-Item .env.example .env
uv run python run_off_crm.py
```

Open `http://127.0.0.1:8766`. API documentation is at `/api/docs`.

For local development, run the backend and Vite separately:

```powershell
uv run python run_off_crm.py
```

```powershell
cd frontend
npm run dev
```

## OFF_AI workflow

1. Open **AI**.
2. Open **Connectors** and add an API-capable provider.
3. Record the provider's jurisdiction, retention terms, host/model origin, terms-check date, trust tier, task allowlist, quotas, cost, and same-tier fallback.
4. Use automatic cheapest-eligible routing or select one eligible model.
5. Inspect any response's provider packet from the chat or Connectors audit.
6. Use the right drawer for chat/project history; close it independently of the global left navigation.

Consumer ChatGPT or Claude subscriptions are not application APIs. OFF_CRM uses API credentials only.

### Trust tiers

| Tier | Permitted use |
|---|---|
| A | Minimal public-person, public positioning, and owner-template payloads after verified no-training/no-retention terms |
| B | Fully public, non-personal work only |
| C | Explicitly enabled public, non-personal task types only; never failover |
| D | Default deny; receives nothing |

Unknown profiles and aggregators default to Tier D. China-jurisdiction hosts become Tier C. A Chinese-origin model on a Tier A host is limited to Tier B unless input isolation from the model developer is verified.

## Campaign intake

Open **AI → Attach campaign file**.

- **Generate** expects a POI list plus an owner template. It requires an eligible Tier A provider. Each call receives one public POI profile, the approved OffsetX positioning line, the template, and code-generated instructions. Email addresses stay local.
- **Parse & send** expects recipient, subject, and body fields. Parsing is deterministic and makes no AI call.

Both modes create pending review drafts. The intake path enforces a maximum of 20 messages per day, routes missing addresses to the Apollo queue, and excludes existing contacts before enrichment or drafting.

Use **Lead discovery** and Apollo before intake when the POI file needs public enrichment. Social data is accepted through official APIs or verified manual import only; authenticated LinkedIn/Instagram scraping and protection bypasses are not implemented.

## Gmail connection

Create a Google OAuth client and set:

```env
OFF_CRM_GMAIL_CLIENT_SECRETS=path/to/client_secret.json
OFF_CRM_GMAIL_TOKEN=local_data/gmail_token.json
OFF_CRM_OWN_EMAIL=you@example.com
```

Restart OFF_CRM, open **Connectors**, and select **Connect Gmail**. Gmail authorization is separate from CRM authentication. The token is never exposed to AI providers.

Reply synchronization retrieves only CRM-owned Gmail threads. Production Gmail mode does not perform a broad mailbox search. An inbound reply deterministically stops unsent follow-ups before another provider call.

## Provider registry and routing

Provider profiles live in `local_data/provider_profiles.json`; API keys are encrypted separately. The broker:

1. applies the data/trust hard filter;
2. constructs a field allowlist payload;
3. blocks email addresses, secrets, local paths, mailbox/CRM retrieval prompts, and forbidden internal fields;
4. applies deterministic PII redaction as a backstop;
5. checks RPM/RPD and daily/monthly cost caps;
6. selects the cheapest eligible model;
7. fails over only inside the same effective trust tier;
8. records the exact payload, provider response, tokens, cost, duration, and result.

No code outside `offsetx_apollo_builder/off_ai/broker.py` obtains provider runtime credentials.

## Bring-your-own tools

Under **Connectors**, register a public GitHub repository, a full 40-character commit SHA, a version-pinned container image, and a command. OFF_CRM fetches that exact commit without credentials or submodules, removes Git metadata, then executes it with:

- no network;
- read-only source and root filesystem;
- no added Linux capabilities;
- no-new-privileges;
- unprivileged user;
- PID, memory, CPU, timeout, and output caps;
- public-input preflight scanning.

Docker is required to execute tools. Tool preparation requires outbound GitHub access; execution does not.

## Code graph

Graphify 0.9.25 is pinned for build-time, code-only analysis. It never processes CRM data, contacts, email, documents, PDFs, or media.

```powershell
.\scripts\build_code_graph.ps1
uvx --from graphifyy==0.9.25 graphify query "how does the egress broker connect to campaign intake?"
```

The generated `graphify-out/graph.json` and `GRAPH_REPORT.md` are source-code intelligence artifacts, not runtime memory.

## Lead discovery and sales tracker

The v0.9-v0.11 modules remain intact:

- guarded public crawling with safe HTTP or optional Crawl4AI;
- one to four discovery workers with shared per-domain politeness;
- evidence review before Apollo or CRM import;
- local person/company/source/reference graph;
- Apollo credit, deduplication, accepted-exclusion, and rejection ledgers;
- lead-card Kanban as the sales source of truth;
- setter, closer, financial, leak, commission, goal, and forecast calculations.

Enable the local Crawl4AI browser worker with:

```powershell
uv sync --extra dev --extra crawler
uv run crawl4ai-setup
```

The worker setting only speeds up runs that span multiple sites. It does not increase the request rate to any one domain.

## Notion export

Open **Settings → Notion sync**, connect an internal Notion integration, and select existing contact and sales databases. OFF_CRM performs a one-way upsert from its local source of truth. It fills only properties whose names and types match the target database. Notion changes are never imported into OFF_CRM.

## Tests

```powershell
uv run pytest -q
cd frontend
npm test
npm run build
```

The mandatory zero-access suite covers tier refusal, email/secret/mailbox/context blocking, payload allowlists, same-tier failover, PII backstop behavior, sandbox construction, and public-input-only tools. To run the live Docker network-wall test with a pre-pulled image:

```powershell
$env:OFF_CRM_SANDBOX_TEST_IMAGE="python:3.12.10-slim-bookworm"
uv run pytest -q tests/test_off_ai_sandbox_runtime.py
```

## Deployment boundary

The checked-in Render configuration is a disposable, password-protected demo. Its filesystem is temporary. Do not upload live contacts, Gmail tokens, private expert material, or provider credentials.

This release is single-user and local-first. A production team deployment still requires authenticated tenancy, durable PostgreSQL, an encrypted secrets service, worker queues, migrations, backups, and a reviewed network boundary.

## Documentation

- `docs/OFF_AI_ARCHITECTURE.md`
- `docs/OFF_AI_SECURITY.md`
- `docs/OFF_AI_OPERATOR_GUIDE.md`
- `docs/OFF_AI_REBUILD_GUIDE.md`
- `docs/SALES_TRACKER.md`
- `docs/LEAD_DISCOVERY.md`
- `docs/WEB_CRM.md`
- `BUILD_STATE.md`

## Safety

Do not upload copied paid courses or private material to the expert library. Use owned notes, licensed material, permissioned transcripts, or public material with clear provenance.
