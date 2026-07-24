# Changelog

## 0.12.0

- Renamed current product surfaces and runtime configuration to OFF_CRM while preserving legacy environment aliases.
- Added OFF_AI Studio at the top of the left navigation with prompt/model controls, persisted chats/projects, search, pin, rename, archive, dictation, and Markdown/HTML export.
- Added independently closable global left navigation and right-side chat/project history, including mobile overlay behavior.
- Added deterministic-first CSV/XLSX/XLS/PDF/TXT/Markdown campaign intake with masked previews, Generate and Parse & send modes, row diagnostics, deduplication, Apollo queueing, and pending-review campaigns capped at 20/day.
- Added a config-driven Tier A/B/C/D provider registry with jurisdiction, retention, host/model provenance, terms date, task eligibility, quota/cost caps, and same-tier failover.
- Added a single provider egress broker with constructed allowlist payloads, hard preflight blocking, deterministic PII redaction, exact packet logging, usage accounting, and provider-response inspection.
- Added in-app Gmail OAuth with token isolation and CRM-owned-thread-only production reply retrieval.
- Added deterministic runtime context state, owner-controlled CRM activity export, and numeric reply-rate template recommendations requiring human review.
- Added immutable, pinned public GitHub tools executed in read-only, unprivileged, networkless Docker sandboxes.
- Added pinned Graphify 0.9.25 code-only source graph generation with runtime/user data exclusions.
- Added zero-access security acceptance tests, AI/operator/architecture documentation, and a hand-rebuild guide.
- Added user-controlled public-discovery workers from one to four while keeping one shared per-domain politeness gate.
- Added one-way Notion export for campaign contacts and sales leads with an encrypted local token and schema-aware property matching.
- Added a clickable pipeline overview and plain-language discovery engine and worker controls.
- Combined release verification covers 94 backend tests and 9 frontend tests.

## 0.11.0

- Added a complete sales-tracker CRM whose Kanban lead cards are the single source of truth for the lead log, metrics, commissions, leak alerts and forecast.
- Added seven drag-and-drop stages, mobile status controls, required Lost reasons, optimistic revision checks and an immutable lead event trail.
- Added setter activity, speed-to-lead, booking lag, schedule disposition, show-up and DQ visibility.
- Added closer offer and close rates, one-call/follow-up sales, average deal size, revenue per call and loss-reason reporting.
- Added deposit, cash, paid-in-full, refund/clawback, net revenue, goal and net commission calculations.
- Added red leak detection for booking lag over four days, untouched follow-ups at seven days and deposits unpaid at fourteen days.
- Added best, expected and worst end-of-month revenue/cash projections with historical, pipeline, manual and fallback assumption provenance.
- Added schema v6, dedicated sales APIs, responsive React views, audit tests and operating documentation.
- Expanded release coverage to 69 Python tests and 4 frontend tests.

## 0.10.0

- Added a guarded Crawl4AI 0.9.2 JavaScript-rendering adapter with fixed non-evasive settings, browser-route SSRF checks, robots.txt enforcement and no cookies, proxies, stealth or persistent profiles.
- Added a bounded prompt compiler for target counts, role focus, competitor expansion, social-handle collection and connector requirements.
- Added a persistent local research graph for people, companies, source pages, reference-only social profiles and approved/manual interaction evidence.
- Added an official-API/manual-import boundary for social interactions without exposing social OAuth sessions to AI providers.
- Added a visible Apollo rejection ledger with retry policy, automatic-repeat blocking and strict separation from the permanent accepted-contact exclusion ledger.
- Added CRM controls for crawler choice, research prompts, compiled plans, graph relationships and Apollo outcomes.
- Expanded release coverage to 63 Python tests and 3 frontend tests.

## 0.9.0

- Added guarded Scrapling parsing and public-web crawling with robots.txt, rate, redirect, size, content-type, domain allow-list and SSRF controls.
- Added persisted discovery runs and candidates with evidence, confidence, status and exclusion reasons.
- Added exclusion against `old_pois`, previous Apollo outputs and existing CRM contacts before review or enrichment.
- Added a React Lead Discovery screen with approval, rejection, Apollo queue and CRM-import controls.
- Added an explicit account boundary: no AI provider receives browser cookies or social-account credentials, and authenticated social scraping remains disabled.
- Expanded release coverage to 60 Python tests and 3 frontend tests.

## 0.8.0

- Added pre-send generation traces, exact bulk correction previews, re-audit, approval reset and per-draft not-before scheduling.
- Added campaign send windows, weekday controls, timezone enforcement and backwards-compatible all-day API defaults.
- Added provider data policies, optional redacted payload logging, persistent health state and priority, round-robin or parallel routing.
- Added a replaceable memory boundary with approved human corrections, de-identified outcome learning and local SQLite retrieval.
- Added provider-call observability and memory control APIs plus React control-centre surfaces.
- Added explicit experiment hypotheses, controls, minimum samples, Wilson intervals and lift reporting.
- Hardened Render writable storage and expanded release coverage to 56 Python tests and 3 frontend tests.

## 0.7.0

- Added a temporary single-user CRM login with signed HTTP-only sessions and login throttling.
- Added Render Blueprint configuration, automatic `PORT` handling, and a readiness health check.
- Added a dedicated responsive login screen and logout control.
- Documented disposable Render data and the hosted Gmail OAuth boundary.

## 0.6.0

- Added encrypted local AI provider profiles and secret storage.
- Added priority-ordered provider failover, response normalization and circuit breaking.
- Added reply-first campaign automation with daily caps and explicit Gmail activation.
- Added passphrase-encrypted local backup and verified restore.
- Added provider, automation and backup controls to the React Settings page.
- Expanded the release suite to 45 Python tests and 2 frontend tests.

## 0.5.0

- Added FastAPI local CRM API and React control centre.
- Added campaigns, contacts, drafts, queue, reply stop, exports and A/B reports.
- Added local SQLite schema, migrations, FTS expert library and event audit.
- Added strict OffsetX email expert and eight versioned A/B templates.
- Added OpenAI, Anthropic, compatible API and template-application adapters.
- Added Gmail OAuth and safe local outbox providers.
- Added daily limits, working-day scheduling, atomic send claims and idempotency.
- Added API token, upload, provider URL and spreadsheet export security controls.
- Preserved both Apollo search and existing-POI enrichment workflows.
- Expanded the release suite to 38 Python tests and 2 frontend tests.
