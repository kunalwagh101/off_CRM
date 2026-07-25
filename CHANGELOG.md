# Changelog

## 0.12.0

- Added a self-contained AI module (`offsetx_apollo_builder/ai/`) with a single egress broker that every outbound provider call must pass through.
- Added a config-driven provider registry in `config/providers.yaml` covering 17 providers with jurisdiction, data-retention terms, rate limits, context window, cost and a verification date; adding a provider is now a config edit rather than a code change.
- Added four-level trust tiers derived from both jurisdiction and retention terms, with per-model provenance caps, default-deny for unlisted providers, and failover that never crosses a tier boundary.
- Added four data policies (strict, minimal, standard, full) with per-tier ceilings, and owner overrides that require a written reason and record who decided and when.
- Added allowlist payload construction that starts from an empty dict, replacing the previous strip-fields-from-an-object approach.
- Added a pre-flight scanner that blocks and raises on email addresses, owner domains, twelve credential shapes, mail headers, internal field names, environment variables and local paths.
- Added local quota accounting with per-minute, per-day and spend caps, and a usage display for providers with no usage endpoint.
- Added an egress log storing the exact payload of every call, with an inspector screen so the data guarantee can be verified rather than trusted.
- Added mailbox egress lockout for every provider by default, unlockable only with an exact typed phrase and still refused for restricted tiers.
- Added per-workspace AI settings and Fernet-encrypted per-workspace provider keys with an environment-variable fallback for server deployments.
- Fixed an AI chat path that sent raw conversation text to a provider with no data policy applied, contradicting the module's own docstring.
- Fixed a scanner defect where patterns ran against JSON-serialised text, silently disabling every line-anchored mail-header rule.
- Fixed two paths that reached an AI provider without the policy guard, in the drafts API and the outreach CLI; an AST test now fails the build if a third appears.
- Moved Gmail and AI providers out of Settings into a dedicated Connectors screen showing country, trust tier, retention terms and usage per provider.
- Removed the hardcoded TypeScript provider catalogue in favour of the backend registry.
- Added a model selector, task mode, Markdown/HTML export and optional dictation to the AI chat screen.
- Expanded release coverage to 135 Python tests and 6 frontend tests, including 30 security acceptance tests for the zero-access data architecture.

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
