# off_CRM

[![CI](https://github.com/kunalwagh101/off_CRM/actions/workflows/ci.yml/badge.svg)](https://github.com/kunalwagh101/off_CRM/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

**A local-first, open-source GTM operating system for finding opportunities, creating approved outreach and content, and learning from the results.**

off_CRM combines a working outreach CRM, public-web lead discovery, multi-model AI orchestration, image campaigns, a browser-rendered video editor, and a content distribution pipeline. Human approval remains between generation and every important external action.

> **Current status:** strong single-user/local application and disposable hosted demo. It is not yet a multi-tenant production SaaS.

## The product flow

```text
public evidence
      |
      v
people and trends -> campaigns -> emails, images and videos
                                      |
                                      v
                              human review and approval
                                      |
                                      v
                         local outbox or official adapters
                                      |
                                      v
                           replies and engagement signals
```

The parts share one safety boundary: models do not pull data from the CRM. off_CRM builds an allowlisted payload and pushes only the permitted fields through one audited AI egress gate.

## What works today

| Capability | Status | What it does |
|---|---|---|
| Outreach CRM | Working | Imports contacts, creates three-stage sequences, supports review, scheduling, local outbox or Gmail sending, and stops follow-ups after a reply. |
| Email deliverability | Beta | Adds consent and suppression controls, stream-isolated identities, SPF/DKIM/DMARC preflight, durable jobs, Amazon SES, one-click unsubscribe, feedback health and auto-pause. Live AWS validation is still required. |
| Sales tracker | Working | Kanban pipeline, lead log, setter/closer metrics, commissions, leak flags, goals and evidence-labelled revenue projections. |
| Public-web lead discovery | Working | Extracts people and evidence from user-approved public pages with robots.txt, domain allowlists, rate limits, redirect checks, response limits and SSRF controls. |
| Apollo enrichment | Working, optional | Searches or enriches POIs with deduplication, permanent exclusions, visible rejection reasons and a hard credit cap. Requires the user's Apollo credentials. |
| AI orchestration | Working | Routes across configured chat and image models using trust tiers, data policies, quotas, failover, comparison, verification, caching and audit logs. |
| Local memory and recall | Working | Learns from approved human edits and retrieves only sent-mail context. Received mailbox content is inaccessible by default. |
| Image campaigns | Working | Generates batches through configured image models, applies deterministic image gates, collects owner approval/rejection labels and learns generator preference. |
| Video editor | Beta | Browser-rendered timeline editing, still/video import, transitions, effects, retiming, audio mixdown, captions, review queue and WebM/MP4-oriented workflows. AI editing and generated footage/audio remain incomplete. |
| Content distribution | Beta | Goals, posts, approval, scheduling, owner-set caps, pacing recommendations, engagement snapshots, content automation and a working local outbox. Live Instagram, Facebook, TikTok, LinkedIn and X publishing adapters are not built. |
| Trend intelligence | Beta | YouTube public-data trend detection, topic clustering and trend-to-post planning. Other platforms depend on their official API permissions. |
| Browser agent | Alpha | Low-level CDP browser control, accessibility-tree perception, real input events, screenshots, policy checks and append-only traces. It is not yet wired into the main AI/API/UI loop and needs further network hardening. |
| Hosted multi-user service | Not ready | The current workspace is effectively single-user, most state is local, and the included Render configuration is for disposable demonstrations only. |

## Free and open source

The off_CRM source code is free under the [Apache License 2.0](LICENSE).

A useful local workflow can run with local templates, SQLite, the safe public-page discovery engine and local outboxes. Optional integrations can have their own costs or limits:

- Apollo may charge for enrichment credits.
- AI and image providers may charge after their free allowance.
- Gmail, Notion, YouTube and social platforms apply their own API rules and quotas.
- Hosted infrastructure is separate from the software licence.

The project does not bypass authentication, robots.txt, platform restrictions or account permissions. Authenticated LinkedIn and Instagram scraping is intentionally not supported.

## Core capabilities

### Outreach and CRM

- Campaigns, contacts, drafts, queues and CRM exports
- First touch plus two follow-ups
- Reply sync and automatic cancellation of unsent follow-ups
- Exact preview, editing, bulk corrections, scheduling and approval
- Safe local outbox by default
- Gmail OAuth with an explicit live-send confirmation
- Durable local/SES delivery jobs with consent, suppression, authentication, feedback and health controls
- A/B results, memory from approved edits and outcome-labelled learning
- Setter/closer sales workflow with revenue and cash projections

### Lead discovery and enrichment

- Research prompts compiled into target, role, source and connector requirements
- Safe HTTP discovery and optional local Crawl4AI JavaScript rendering
- Public person, company, source-page and social-reference graph
- Evidence review before a person enters Apollo or the CRM
- Duplicate checks across existing contacts, exclusions and earlier output
- CSV, XLSX, XLS and text-based PDF contact intake
- Apollo search and existing-POI enrichment with hard credit controls
- Rejection and attempt ledgers that explain whether a record may be retried

Public-page discovery works without Apollo. Apollo is an optional enrichment step when a verified email or provider record is required.

### AI safety and orchestration

- One central broker for model-provider calls
- Allowlist payload construction instead of after-the-fact redaction
- Blocking sensitive-data scanner
- Provider and per-model trust tiers
- Minimal, standard and full data policies with explicit overrides
- Same-tier failover, quota tracking and health checks
- Simple, verified, compare and orchestrated run modes
- Deterministic evaluation suites and a repair loop
- Response caching with privacy-separated partitions
- Metadata-first egress audit logs
- No model-facing mailbox, context-store query or recall-search tool

### Images, video and content

- Image generation through the same AI safety boundary
- Decode, blank-image, header, aspect-ratio and duplicate gates
- Owner review as the preference signal
- Generator traffic allocation only after enough evidence exists
- Timeline-based video editing and browser rendering
- Effects, transitions, presets, captions, audio and retiming
- Content goals, post approval, scheduling and engagement measurement
- Per-account posting caps and explainable pacing suggestions
- Local distribution outbox and official-API-first platform policy

## Quick start

### Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 24 and npm

### Install

```bash
git clone https://github.com/kunalwagh101/off_CRM.git
cd off_CRM

uv sync --locked
cd frontend
npm ci
npm run build
cd ..

cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.

### Run

```bash
uv run offsetx-web
```

Open:

- Application: <http://127.0.0.1:8766>
- API documentation: <http://127.0.0.1:8766/api/docs>

The default host is loopback-only. Non-loopback binding is refused unless authentication is configured.

### Optional JavaScript-rendered discovery

```bash
uv sync --locked --extra crawler
uv run crawl4ai-setup
```

Keep the safe HTTP engine for ordinary public pages. The Chromium worker is intended for local use or a separately sized worker.

### Optional Amazon SES bulk delivery

```bash
uv sync --locked --extra email
```

Configure a verified SES identity, configuration set, SNS feedback topic and a public HTTPS unsubscribe URL before live use. See [email delivery architecture](docs/architecture/EMAIL_DELIVERY.md). This improves deliverability controls; it does not guarantee inbox placement.

## First outreach run

1. Create an email campaign.
2. Import `examples/outreach_contacts_sample.csv`.
3. Generate a three-stage sequence using local templates or a configured provider.
4. Review and edit the exact output.
5. Schedule and approve the drafts.
6. Run the local outbox.
7. Connect Gmail only after reviewing the local result.
8. Sync replies before later sends.

Local mail is written under `local_data/mail/outbox`.

## Configuration

Copy `.env.example` to `.env`. Never commit real values.

Common optional settings:

```env
APOLLO_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
NVIDIA_API_KEY=

OFFSETX_SENDER_NAME=
OFFSETX_SENDER_ROLE=
OFFSETX_SENDER_EMAIL=
OFFSETX_SENDER_LINKEDIN=

OFFSETX_WEB_HOST=127.0.0.1
OFFSETX_WEB_PORT=8766
OFFSETX_LOCAL_API_TOKEN=
OFFSETX_OUTREACH_DB=local_data/offsetx_outreach.db
OFFSETX_PUBLIC_BASE_URL=
OFFSETX_UNSUBSCRIBE_SECRET=
```

Provider registry examples are under `config/`. Connected provider profiles and locally managed keys are encrypted on the device.

## Command-line tools

| Command | Purpose |
|---|---|
| `offsetx-web` | Run the FastAPI application and built React frontend. |
| `offsetx-apollo` | Run POI search, deduplication and enrichment workflows. |
| `offsetx-outreach` | Manage campaigns, contacts, drafts, approvals and sending. |
| `offsetx-evals` | Run deterministic AI evaluation suites and compare routing modes. |
| `offsetx-tools` | Manage the closed, sandboxed tool registry. |
| `offsetx-notebook` | Export a privacy-controlled research notebook bundle. |
| `offsetx-db` | Inspect and copy supported database boundaries. |
| `offsetx-codegraph` | Build or verify the source-only code graph. |
| `offsetx-email-worker` | Process durable local or Amazon SES email jobs. |

Use `uv run <command> --help` for the complete options.

## Tests and quality checks

```bash
uv sync --extra dev --extra email --locked
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest -q

cd frontend
npm ci
npm test
npm run build
```

The repository has more than 1,400 Python tests plus more than 115 frontend tests. CI performs the locked install, critical Python static checks, CLI smoke tests, backend tests, frontend tests and the production frontend build.

Live Chromium, Docker sandbox and Postgres cases are environment-gated. Their skipped status does not mean the mocked/unit coverage replaces a real deployment test.

## Security model

Important controls include:

- Loopback-only default binding
- Authentication required for non-loopback hosting
- Encrypted local provider secrets and backups
- Human approval before email sending, publishing and reviewed media release
- Restricted discovery with robots, rate, redirect, size and SSRF controls
- Formula-safe spreadsheet exports
- Upload limits and temporary-file cleanup
- Strict browser security headers
- Append-only campaign, provider and browser traces
- No AI access to received mail by default

Read [docs/SECURITY.md](docs/SECURITY.md) before connecting real accounts.

For a security problem, do not open a public issue containing credentials, personal data or an exploit that puts users at risk.

## Storage and deployment

The default installation stores data locally using SQLite, JSON and local files.

The checked-in Render blueprint is a disposable demonstration configuration. Its `/tmp` data can disappear after a restart or redeploy. Do not put personal contacts, Gmail tokens or production credentials there.

A production shared service still needs complete PostgreSQL migration, tenant isolation, object storage, durable background jobs, managed secrets, monitoring and tested recovery.

## Documentation

Start here:

- [BUILD_STATE.md](BUILD_STATE.md) — current implementation record and known gaps
- [AGENTS.md](AGENTS.md) — invariants and commands for contributors and coding agents
- [AI module](docs/AI_MODULE.md)
- [Security](docs/SECURITY.md)
- [Lead discovery](docs/LEAD_DISCOVERY.md)
- [Sales tracker](docs/SALES_TRACKER.md)
- [Email delivery and deliverability controls](docs/architecture/EMAIL_DELIVERY.md)
- [Image campaigns](docs/architecture/IMAGE_CAMPAIGNS.md)
- [Content distribution](docs/architecture/DISTRIBUTION_CAMPAIGNS.md)
- [Video editor](docs/architecture/VIDEO_EDITOR.md)
- [Browser agent blueprint](docs/architecture/BROWSER_AGENT_BLUEPRINT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

Some architecture documents are historical decision records. `BUILD_STATE.md` is the source of truth for current implementation status.

## Contributing

Issues and focused pull requests are welcome. Before changing runtime behaviour, read `AGENTS.md` and the relevant section of `BUILD_STATE.md`. Preserve the central AI egress wall, campaign-kind gates and human approval boundaries.

## Licence

Copyright 2026 Kunal Wagh.

Licensed under the [Apache License 2.0](LICENSE).
