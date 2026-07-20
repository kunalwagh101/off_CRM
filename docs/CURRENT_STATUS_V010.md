# OffsetX CRM current status and handoff

Snapshot version: **0.10.0**  
Prepared: **19 July 2026**  
Repository target: **kunalwagh101/off_CRM**

## Executive status

OffsetX CRM is now a working local-first POI discovery, Apollo enrichment and email-outreach application. It has a FastAPI backend, React control centre, local SQLite data layer, protected Render demo configuration, provider-neutral AI generation, human approval, scheduling, reply-aware follow-ups, experiments, local memory, guarded public-web discovery and a research graph.

The application is suitable for local operation and disposable demo testing. It is not yet a production multi-tenant SaaS.

## What has been completed

### CRM and outreach

- Campaign, contact, draft, queue, experiment and settings screens.
- Three-touch sequence: first email, follow-up 1 and follow-up 2.
- Reply synchronization cancels unsent follow-ups.
- Exact pre-send preview for AI or template-generated emails.
- Manual editing, re-audit and bulk correction preview/apply.
- Draft approval required before sending.
- Per-draft scheduling plus campaign timezone, weekday and send-window controls.
- Hard campaign daily limits, atomic send claims and idempotency protection.
- Local outbox for safe testing and Gmail OAuth for live sending.
- Gmail live sending remains disabled until the exact activation confirmation is entered.
- CSV/Excel contact import and CRM export.

### AI provider portability and control

- Normalized provider contract for OpenAI, Anthropic and compatible HTTP APIs.
- Adapter contract for the future separate template-intelligence application.
- Multiple provider profiles with priority, round-robin and parallel-first-success routing.
- Provider health checks, failure state and circuit-breaking/failover behavior.
- Encrypted local provider profile and secret storage.
- Per-provider payload policies: minimal, standard or full.
- Optional local redacted request/response logs.
- The provider receives the approved CRM generation context, not Gmail credentials, browser cookies or unrestricted inbox access.

Consumer ChatGPT or Claude account login is not used as API authentication. Provider API keys or compatible provider endpoints are required.

### Email expert and templates

- Strict OffsetX email quality checks.
- Eight versioned template variants for experimentation.
- Locked POI categories and route-specific CTA rules.
- Required public-hook evidence and provenance before a first-touch email is sendable.
- Expert-source retrieval with source and rights provenance.
- Paid/private expert material is not bundled; only owned, licensed or permissioned content should be ingested.

### Memory, context and learning

- Replaceable local memory interface backed by SQLite.
- Approved human corrections can become reusable examples.
- Labelled and de-identified campaign outcomes can be retrieved for later generation.
- Research graph stores companies, people, source pages, reference-only social profiles and approved interaction evidence.
- Workspace boundaries exist in the graph schema for future tenancy.
- Raw Gmail inbox contents and raw crawled HTML are not placed in the graph.

This is the current context layer foundation. A centralized multi-user RAG/vector service, a dedicated small LLM and a Google knowledge-graph service are not yet deployed. The interfaces were designed so these can replace or extend the local backend later.

### A/B experimentation

- Explicit experiment hypothesis and control variant.
- Minimum sample configuration.
- Variant assignment and event tracking.
- Reply and outcome reporting.
- Wilson confidence intervals and measured lift.

### POI discovery and Crawl4AI

- Prompt box converts a research objective into an inspectable bounded plan.
- Controls for target count, desired roles, competitor expansion, seed URLs, domain allow-list, page count and crawl depth.
- Safe HTTP crawler for ordinary public pages.
- Optional Crawl4AI 0.9.x JavaScript-rendering adapter for local use.
- Scrapling-based structured-person parsing.
- robots.txt, rate, redirect, size, content-type, DNS/SSRF and domain controls.
- Browser worker runs without cookies, persistent profiles, proxies, stealth, user simulation or protection-bypass settings.
- Evidence, confidence, source and audit hashes are saved for review.
- Review actions: approve, reject, place in Apollo queue or import into CRM.

Crawl4AI is a crawler, not a web-wide search index. Finding 100 companies across the internet still requires seed URLs, a configured search API or an imported company list.

Authenticated LinkedIn/Instagram scraping, CAPTCHA bypass and Cloudflare bypass are intentionally not implemented. Social profiles may be stored as references. Interaction evidence must come from an approved official API or a verified manual import.

### Apollo enrichment and suppression

- Existing POI and new-search Apollo workflows remain available.
- Credit caps and queue lifecycle controls.
- Cross-run deduplication before credit use.
- Existing CRM contacts, `old_pois` records and previous outputs are excluded before enrichment.
- Accepted Apollo contacts automatically enter the permanent exclusion ledger.
- No-match, no-email and policy outcomes enter a visible rejection/attempt ledger.
- Rejected outcomes block wasteful automatic retries while preserving explicit retry policy.
- Retryable outcomes are kept separate from permanent exclusions.

### Security and deployment

- Local SQLite and local file storage by default.
- API token support for local API access.
- Temporary Render demo login with signed HTTP-only session cookies and login throttling.
- Security headers, restricted CORS and protected API documentation.
- Provider URL validation and upload size controls.
- Passphrase-encrypted backup with SQLite integrity verification before restore.
- Render Blueprint, automatic `PORT` support and writable runtime data path.
- Docker image runs as a non-root user.

The free Render filesystem is temporary. It should use synthetic contacts, local outbox and no personal Gmail tokens or private expert material.

## Main application flow

1. Create a campaign and choose its daily limit and schedule.
2. Research public seed pages through Lead Discovery or import a prepared POI list.
3. Review evidence and exclude previously known POIs.
4. Send approved candidates into Apollo enrichment.
5. Import accepted contacts into the CRM.
6. Generate the three-email sequence using templates or a configured AI provider.
7. Preview, edit, bulk-correct, schedule and approve drafts.
8. Test through the local outbox.
9. Connect Gmail locally and explicitly activate live sending.
10. Sync replies before sending; replies stop pending follow-ups.
11. Review A/B and provider performance reports.

## Verification for this snapshot

| Check | Result |
| --- | --- |
| Python tests | **63 passed** |
| Frontend tests | **3 passed** |
| React/TypeScript production build | **Passed** |
| Git whitespace/diff validation | **Passed** |
| Package version | **0.10.0** |

Two non-blocking dependency deprecation warnings remain: Starlette TestClient/httpx compatibility and an lxml parser option.

## Important remaining production boundaries

- Hosted Gmail OAuth callback and durable encrypted hosted token storage are not implemented.
- The Render free demo is disposable and not suitable for live automation.
- PostgreSQL tenancy, production identity management, durable workers and centralized secrets are not implemented.
- A web-search provider is not connected to the discovery prompt.
- Official LinkedIn/Instagram interaction connectors are not connected.
- The future centralized expert RAG/graph service and separate template-generation application are not integrated yet.
- AI provider API usage requires internet access; template-only and local outbox workflows can operate without an AI provider.

## Why this snapshot has not reached GitHub yet

Your Windows copy and this Codex workspace are separate Git checkouts.

Git stores its remote URL inside each checkout's `.git/config`, and authentication is stored on the machine where GitHub CLI or the credential manager was authorized. Copying or cloning the repository on your Windows computer does not add that remote or credential to this isolated Codex workspace.

Current evidence:

- This workspace is on local branch `master` at commit `ec46d53` plus the v0.9/v0.10 working changes.
- It has no `origin` remote configured.
- GitHub CLI (`gh`) is not installed in this workspace.
- The connected GitHub application can inspect `kunalwagh101/off_CRM` and reports push permission, but it does not inject an authentication credential into shell-based `git push`.
- GitHub `main` was last observed at commit `62fa2a3`, the v0.7 Render demo release.

The evidence indicates this workspace was reconstructed from a handoff/source snapshot rather than being the same authenticated clone used for the earlier GitHub push. Nothing is wrong with your GitHub account or your Windows clone.

The cleanest publishing path is to open your actual Windows clone in local Codex, copy this package over it while preserving its `.git` folder, and publish from there. That clone already has the `origin` remote and can use your authenticated GitHub CLI.

## Local run

From the repository root:

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run python run_offsetx_web.py
```

Open `http://127.0.0.1:8766`.

For the local JavaScript crawler:

```powershell
uv sync --extra dev --extra crawler
uv run crawl4ai-setup
```

## Documentation included

- `README.md`
- `CHANGELOG.md`
- `docs/LEAD_DISCOVERY.md`
- `docs/INTELLIGENCE_ARCHITECTURE.md`
- `docs/WEB_CRM.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`
- `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`

