# Board

**The single source of truth for what is happening.** Chat is not state — if it
is not in this file, it did not happen.

`scripts/verify_board.py` parses this file. One fixed-format line per item:

```
- <ID> · <title>
```

`DONE` items carry an indented evidence block. `BLOCKED` items carry an
indented `blocked: <Q-nn or a named external dependency>`. An item with a build
plan carries an indented `work_order: <path>` — the file an implementer follows
without asking. An open item with none needs its work order written before
anyone pulls it.

**Pulling an item.** Only from READY. Read its work order to the end, then its
story in `PRODUCT_BACKLOG.md`. Write the test first and watch it fail. Run the
gates in `AGENTS.md`; log defects and design calls; push to `develop`. It
reaches DONE only with the evidence block `DEFINITION_OF_DONE.md` describes.

**WIP limit: `IN_PROGRESS` ≤ 2.** Nothing is pulled while an item sits in
`IN_PROGRESS` or `BLOCKED`.

The owner's selected five-feature queue and its prerequisites are recorded in
`docs/DEVELOP_NEXT_WORK.md`. Its first delivery slice is `S-06.02.38`; selection
does not waive READY, evidence or existing escalations. Use `develop` only.

---

## BACKLOG

- S-06.02.40 · A durable email worker runs beside the deployed web app
  work_order: docs/work-orders/S-06.02.40-durable-deployment-worker.md

*(E-11, waiting on an upstream story rather than on a decision. Each names it.)*



*(Production-audit security findings, not yet READY; the required live integration checks have not run.)*

- S-02.02.03 · Interrupt, steer, resume
- S-04.01.02 · Skills: procedures fetched on demand
  work_order: docs/work-orders/S-04.01.02-on-demand-agent-skills.md
- S-04.01.03 · Sub-agents for context isolation
- S-04.01.04 · The five roles, wired to what already exists
- S-06.01.05 · Deployment, monitoring and rollback
- S-07.01.01 · An MCP client
- S-07.01.02 · Native OAuth integrations

*(E-12, opened 2026-09-22 — the GTM engine. Phase 1 and 2 are DONE (2026-09-23),
so every story below could be pulled; none is, because the owner asked for Phase
1 and 2. `S-12.01.03` also waits on `D-81`. `S-12.02.05` needs the expert library
the owner said they will source. `S-06.02.20` is the fix for `D-80`.)*



*(Filed 2026-09-22 for `D-82`, found while building the review: a plan's posting
channel cannot reach a published post from the screens. Not pulled — it is the
posting screens' work, and the owner asked for Phase 1 and 2.)*


*(Split 2026-09-23 from `S-06.02.23`: the audit's live harness waits for CI
runners. The per-finding re-check itself is READY.)*

- S-06.02.27 · The audit's live harness runs against `develop`

*(Filed 2026-09-24 from the review of `S-06.02.24` for `D-146`. Needs its
work order before it is pulled.)*


*(Filed 2026-09-25 from the owner's requests. `S-06.02.34` starts by finding
out what each provider reports. `F-06.03` is the owner's answer to `Q-26`.)*

*(Filed 2026-09-25 for `D-173`: the Drafts screen's model option points at a
profile form that no screen has had since the providers moved to Connectors.
Waits on the owner's answer to `Q-28`.)*

- S-06.02.35 · Drafts reach a model the owner set up on a screen

*(Filed 2026-09-28 for `D-196`, from the sixth check: a login made in
workspace `local` acts as the install owner with nothing asking for that.)*


*(Filed 2026-10-04 from the owner's instruction: every error traceable the
next day, `AGENTS.md` "Logging".)*

- S-06.03.04 · The hosted database is backed up outside itself
  design: docs/architecture/HOSTED_STORAGE.md
  work_order: docs/work-orders/S-06.03.04-hosted-backup-and-restore.md
- S-06.03.05 · Production refuses a half-hosted install
  design: docs/architecture/HOSTED_STORAGE.md

*(Filed 2026-10-02 from the inventory, `S-06.03.01`: stores with no phase.)*

- S-06.03.06 · Every other store has a decided home
  work_order: docs/work-orders/S-06.03.06-store-homes.md
  design: docs/architecture/HOSTED_STORAGE.md

*(Filed 2026-10-03 from the fresh-context review of `S-06.03.03`, finding 10.)*

- S-06.03.07 · A local install's decision belongs to that install
  design: docs/architecture/HOSTED_STORAGE.md

*(Filed 2026-09-23 for `D-128`: it needs CI runners first, `S-06.02.18`.
Work order: `docs/work-orders/S-06.02.26-python-matrix.md`.)*

- S-06.02.26 · CI runs the suite on every Python the package supports
  work_order: docs/work-orders/S-06.02.26-python-matrix.md

## READY


*(2026-09-23 — the handoff after the consolidation. The owner asked for the
remaining work to be written down, not built: each item below has a work order
an implementer can follow without asking. `S-06.02.24` is `D-134` and `D-138`;
`S-06.02.25` is `D-137`.)*



*(Q-01, Q-02, Q-03 and Q-06 were answered by the owner. The decisions are
recorded in `OPEN_QUESTIONS.md` rather than the questions being deleted, so the
reasoning survives the unblocking.)*

*(E-11 — the autonomous browsing epic. Only the stories whose upstream
dependencies are already DONE are READY; the rest wait in BACKLOG, because the
Definition of Ready is not a formality and an item whose shape can still change
is an item that gets built twice. S-11.02.01 through S-11.02.03 are DONE; the
remaining independent stories below stay READY.)*

*(Moved out of BACKLOG on 2026-09-10 after an audit: every dependency these
declare is DONE, and no open question is filed against any of them. They had
been sitting in BACKLOG because nothing moves an item to READY when the story
it waited on finishes — that is a manual step and nobody was doing it.)*


## IN_PROGRESS

- S-06.02.57 · A09: Enter handlers cannot bypass human approval
  work_order: docs/work-orders/S-06.02.57-enter-approval.md



- S-06.02.23 · Re-check the 7 September production audit on `develop`
  work_order: docs/work-orders/S-06.02.23-audit-recheck.md

## IN_REVIEW

- S-06.02.56 · Reject corrupt image payloads safely (A21)
  work_order: docs/work-orders/S-06.02.56-complete-image-decoding.md
  review: TDD RED 2 failed/2 passed on Render dep-dbkolbnb9u1s73819ns0. Corrected source e45469a isolated Render dep-dbkp0b7b9u1s738244k0: A21 10 PASS, image/video 113 PASS, full SQLite 2950 PASS/50 skip, real PostgreSQL 2973 PASS/96 skip, focused PG 215 PASS, verifier unit 67 PASS, concurrency 12/12, Ruff/frontend/audits/desktop-mobile Chromium PASS. Structural board verifier PASS with evidence commands skipped. Review service dep-dbkp0b7b9u1s738244k0 LIVE at 08:04:59 UTC on exact tested e45469a (QA marker only). Unverified independent penetration, image decoder resource peaks, live model output, full-history board replay and production acceptance. No main/customer deployment. Evidence docs/evidence/2026-11-03-corrupt-images-a21.md.


- S-06.02.55 · Verify numeric claims without changing sign, precision or magnitude (A18)
  work_order: docs/work-orders/S-06.02.55-numeric-claim-integrity.md
  review: TDD RED isolated Render dep-dbkn8p59fdbs73bquspg at 00b1657: 15 fail/13 pass/8 deselected. Corrected c1eefe2 isolated Render dep-dbkni7fb9u1s73fubjl0 LIVE: A18 focused 48 PASS/2 skipped/8 deselected, A18 real Chromium 2 PASS, full SQLite 2940 PASS/50 skipped, full PostgreSQL 2963 PASS/96 skipped, focused PostgreSQL 215 PASS, verifier unit 67 PASS, repeated concurrency 12/12 PASS, contacts/visitor Chromium PASS and frontend/audit/Ruff gates PASS. Structural `verify_board.py --skip-tests` PASS; full-history verifier/independent live penetration and production acceptance unverified. No main/customer release; evidence docs/evidence/2026-11-03-numeric-claim-integrity.md.

- F-06.22 · Duplicate Contact Review (backend)
  work_order: docs/features/crm-duplicate-review.md
  review: F-06.22 TDD RED (2 failed/4 passed) in dep-dbk9k6ijnfac73a0jpjg, fixed D-351/352 and test harness D-353; final pinned source f6de8a1 isolated Render dep-dbk9o0gn74is73brdodg LIVE. New 7 tests PASS, SQLite 2892 PASS/48 skipped, real PostgreSQL 2915 PASS/94 skipped, focused PG 215 PASS, verifier unit 67 PASS, concurrency 12/12, Chromium desktop/mobile PASS, frontend and audit stages PASS. Q-27 workspace ownership, independent live penetration, full-history board verifier and beyond-5k query-scale proof remain open. No customer/main deployment.


- S-06.02.54 · Restore actual AI and orchestration in the visitor demo
  work_order: docs/work-orders/S-06.02.54-restore-visitor-ai.md
  review: Visitor AI repair LIVE on 39084d3 via dep-dbj8g5h42hec73ca9vd0; original updated to reviewed 97e1e7b via dep-dbj8r2tg1s2s73f2oghg, LIVE 00:55:24Z after owner-approved temporary-data reset. Real visitor HTTPS 37 checks and live AI/provider-setup browser flow passed. Final Render review 97e1e7b / dep-dbj8jdgu01pc73eomva0 LIVE: SQLite 2847, focused PostgreSQL 215, full PostgreSQL 2867, frontend 214/build, desktop/mobile Chromium and verifier unit 67 PASS. D-344/D-345 harness fixes verified. Original real HTTPS readiness/private-auth/anonymous protection/frontend match PASS; private authenticated login not exercised. Live model needs a valid key; arbitrary CRM actions from chat, independent security/recovery and full-history verifier remain open. Evidence docs/evidence/2026-11-01-restore-demo-ai.md. IN_REVIEW; no main change.

- S-06.02.53 · Public visitor demo has its own visible login and isolated sample data
  work_order: docs/work-orders/S-06.02.53-public-visitor-demo.md
  review: Dedicated visitor service LIVE on aaa0a59; live login/sample data/read-only/logout/readiness verified. Render core 5e5039c: 2838 SQLite PASS, visitor Chromium 1440px/390px PASS, frontend 213/build PASS. Core PostgreSQL 2858 PASS, focused PostgreSQL 215 PASS. Startup delta has 4 local checks plus live service acceptance; independent security/recovery review and exact-latest-source full review remain open. Evidence docs/evidence/2026-11-01-public-visitor-demo.md. No private/QA data or credential reuse.

- S-06.02.52 · Owner sees operational scheduler health separate from web readiness
  work_order: docs/work-orders/S-06.02.52-operational-health.md
  review: TDD RED 7/7 missing route on Render dep-dbhsga67bikc73fr5nrg; initial GREEN 7/7 on b7d9bbd; error-reference hardening at 3e5058c, full Render SQLite 2806 and PostgreSQL 2826 PASS on 3e5058c, QA deploy dep-dbhsifajnfac73c7bu4g LIVE; external email worker heartbeat, actual alert delivery, penetration and full-history verifier remain unverified.

- S-06.01.02 · Owner sets global, per-tool and chat-lifetime browser permissions
  work_order: docs/work-orders/S-06.01.02-three-level-agent-permissions.md
  review: prior chat isolation/temporary owner grants egress-safe (8a35417, Render 2837 PG PASS); added owner-initiated read-oriented browser-run API through existing RoutineAgentExecutor/AgentRun with live chat policy, leased workspace, limited steps/spend and forced unattended social-host restrictions. TDD RED f92a3e5 4 failed/33 passed; D-335 RED b6cc20e 1 failed/36 passed. Corrected source 3150fbb Render dep-dbiskimc6qcc739ivrcg targeted 40 PASS, full SQLite 2824 PASS, focused PG 215 PASS, full PG 2844 PASS, Chromium desktop/mobile PASS, Ruff/verifier 67 PASS; Render dep-dbiskimc6qcc739ivrcg LIVE on exact 3150fbb; evidence docs/evidence/2026-10-31-read-only-chat-browser-run.md. Remains IN_REVIEW: true attended watch/cancel UI, real provider/browser smoke, D-330 missing-settings, upstream S-04.01.01, external penetration, full-history verifier and production storage/egress. D-337 owner cancellation: owner-only active-run GET/DELETE, real async task cancellation and lease cleanup; Render RED cf31c14 / dep-dbiugrm7bikc73dtnrr0 3 failed/40 passed, current GREEN fd8a73a / dep-dbiuigg473hc73ambq30 targeted 44 PASS, SQLite 2828 PASS, focused PG 215 PASS, full PG 2848 PASS, Chromium desktop/mobile PASS, verifier unit 67 PASS; isolated Render dep-dbiuigg473hc73ambq30 LIVE on fd8a73a. Evidence docs/evidence/2026-10-31-chat-browser-cancellation.md; remains IN_REVIEW with live browser, cross-instance, UI and penetration gaps.

- S-06.03.08 · Install owner sees actual storage durability and production blockers
  work_order: docs/work-orders/S-06.03.08-storage-readiness-report.md
  review: real Render TDD RED 5/5 absent API, initial GREEN 5/5, then added non-owner 403 and OS-root false mount regression; full final Render QA required

- S-06.02.51 · Video uploads have a bounded request stream and concurrency gate (A15)
  work_order: docs/work-orders/S-06.02.51-video-upload-stream-guard.md
  review: 11 new adversarial HTTP and ASGI regressions passed within full Render SQLite (2777) and PostgreSQL (2797) suites on 71fb99c; standalone penetration/load tests, cross-process quotas and full-history board verification remain open

- S-06.02.50 · Video media and renders obey configured upload limits (A15 partial remediation)
  work_order: docs/work-orders/S-06.02.50-bounded-video-uploads.md
  review: 6 authenticated API/security cases passed in Render full SQLite (2766) and PostgreSQL (2786) suites on 0c28d7c; only endpoint byte limit fixed, request-stream/disk/concurrency and real-world penetration gates open

- F-06.19 · CRM Data Quality Centre
  work_order: docs/features/crm-data-quality.md
  review: read-only incomplete-contact and sales-email-overlap review screen, authenticated filtered API and tests authored; real environment, privacy and tenant gates open

- F-06.20 · Campaign Comparison Dashboard
  work_order: docs/features/campaign-comparison.md
  review: unique-contact outreach comparison with explicit denominator, paginated UI and tests authored; PostgreSQL/performance/browser gates open

- F-06.21 · Follow-up Performance Centre
  work_order: docs/features/followup-performance.md
  review: saved human-task workload by free-text assignee label, truthful overdue/on-time totals, UI and tests authored; execution/tenancy review pending


- F-06.16 · Unified CRM Search
  work_order: docs/features/unified-crm-search.md
  review: full API/UI literal-safe contact and lead search, server pagination and cross-campaign membership navigation; regression tests authored, not executed

- F-06.17 · Account Intelligence Workspace
  work_order: docs/features/account-intelligence-workspace.md
  review: company-grouped contacts/leads, campaign/message/task coverage and interactive account profile; regression and performance/security review pending

- F-06.18 · Campaign-to-Revenue Attribution
  work_order: docs/features/campaign-revenue-attribution.md
  review: first-link unique lead assignment, won/cash metrics and no-causal-claim UI, database and frontend tests authored; financial semantics and hosted acceptance pending


- F-06.13 · Qualified Reply-to-Sales Conversion
  work_order: docs/features/reply-to-sales-conversion.md
  review: source-backed explicit positive-reply conversion, durable campaign-to-lead link, duplicate fail-closed and API/frontend test source prepared; runtime and migration gates open

- F-06.14 · Contact 360 Workspace
  work_order: docs/features/contact-360-workspace.md
  review: field-allowlisted campaign relationship overview, integrated modal across four operator screens and tests prepared; UX/privacy gates open

- F-06.15 · Daily Action Command Center
  work_order: docs/features/daily-action-command-center.md
  review: read-only combined human priorities, source-backed counts, SQL paging and navigation implemented; performance/postgres/browser gates open


- F-06.10 · Reply Inbox & Human Triage
  work_order: docs/features/reply-inbox-triage.md
  review: campaign-scoped response inbox, per-membership triage and human task linkage implemented; tests authored, actual execution/tenancy gates open

- F-06.11 · Contact Communication History
  work_order: docs/features/contact-communication-history.md
  review: bounded member-scoped correspondence API and UI from Contacts/Reply Inbox/tasks implemented; tests authored, auth/browser/recovery gates open

- F-06.12 · Human Follow-up Task Manager
  work_order: docs/features/human-followup-tasks.md
  review: durable task creation, editing, due dates, labels, optimistic revisions, SQLite/Postgres migration and UI implemented; migration/backup/CI tests pending


- F-06.07 · Audience Management Workspace
  work_order: docs/features/audience-workspace.md
  review: manual contact capture, safe linking, bounded exact-ID mark/unmark/stop and UI/tests authored; executable/worker-concurrency gates open

- F-06.08 · Campaign Launch Readiness Center
  work_order: docs/features/campaign-launch-readiness.md
  review: read-only stored-state launch checks and guided screen authored; Python/frontend/Chrome/PostgreSQL gates pending

- F-06.09 · Campaign Activity & Audit Timeline
  work_order: docs/features/campaign-activity-timeline.md
  review: server event facets/filter/paging, authenticated screen and privacy-minimising display authored; regression execution and review pending


- F-06.04 · Campaign Management
  work_order: docs/features/campaign-management.md
  review: real UI editor, safe archive/restore, IANA backend validation, and integration tests authored; execution/live browser/hosted checks pending

- F-06.05 · Campaign Blueprint Reuse
  work_order: docs/features/campaign-blueprints.md
  review: configuration-only paused clone endpoint, idempotency and UI, persistence tests authored; execution/worker-race tests pending

- F-06.06 · Campaign Performance Intelligence
  work_order: docs/features/campaign-performance.md
  review: CRM-based unique-contacted reply-rate, draft-state metrics and UI, local-outbox regression authored; execution/live verification pending


- S-06.02.47 · Large send queues are paginated
  work_order: docs/work-orders/S-06.02.47-queue-pagination.md
  review: bounded queue details, API page controls, Python/Vitest regressions committed; execution and release gates pending

- S-06.02.48 · Campaign-wide queue counters do not mislead
  work_order: docs/work-orders/S-06.02.48-global-queue-totals.md
  review: full-campaign due/approval/replied counts, sender-aligned timestamp logic and regressions prepared; runtime validation pending

- S-06.02.49 · Queue views focus on actionable cohorts
  work_order: docs/work-orders/S-06.02.49-actionable-queue-views.md
  review: validated server view filters, accessible UI and regressions prepared; frontend/browser/CI gates pending


- S-06.02.44 · Download all filtered Contacts rows
  work_order: docs/work-orders/S-06.02.44-filtered-contact-download.md
  review: in-memory authenticated all-pages CSV export and Python/frontend tests prepared; live and complete tests pending

- S-06.02.45 · Category and variant filters for contacts
  work_order: docs/work-orders/S-06.02.45-contact-facet-filters.md
  review: campaign facets API and UI filters prepared; browser/PostgreSQL suite pending

- S-06.02.46 · Marked-only contacts remain reachable
  work_order: docs/work-orders/S-06.02.46-marked-only-contacts.md
  review: persisted checkbox predicate across API, filters and export prepared; full tests and end-to-end proof pending


- S-06.02.41 · Contacts beyond row 500 are reachable
  work_order: docs/work-orders/S-06.02.41-contacts-pagination.md
  review: Render QA dep-db93t2mi0phs73c6msq0 executed 503-persisted-contact real FastAPI pagination/auth regression PASS; prior 212 Vitest and frontend build PASS; live Chromium keyboard/visual, shrinking-page and independent review still required (docs/evidence/2026-10-16-S-06.02.41-42-validation.md)

- S-06.02.42 · Enrichment exports cannot run spreadsheet formulas
  work_order: docs/work-orders/S-06.02.42-spreadsheet-formulas.md
  review: Render QA dep-db93t2mi0phs73c6msq0 spreadsheet CSV/XLSX full-report tabs/source-immutability security regression PASS; isolated Excel/LibreOffice open and independent review still required (docs/evidence/2026-10-16-S-06.02.41-42-validation.md)

- S-06.02.43 · Logout revokes the copied browser session
  work_order: docs/work-orders/S-06.02.43-logout-revocation.md
  review: docs/evidence/S-06.02.43-validation.md; disposable PostgreSQL two-instance replay/restart 1 passed, hosted suite 215 passed, PG full suite 2772 passed; real browser and old-hosted-data upgrade acceptance open


- S-12.02.05 · The brain drafts against the expert corpus and the owner's winners
  work_order: docs/work-orders/S-12.02.05-plans-with-expert-references.md
  review: docs/evidence/S-12.02.05-validation.md; D-268 reference A/B context-isolation regression committed, owner corpus/30 real cases and full verification pending

- S-06.02.16 · Resolve frontend development dependency audit findings
  work_order: docs/work-orders/S-06.02.16-frontend-dependency-audit.md
  review: docs/evidence/S-06.02.16-validation.md; npm-regenerated Vitest/lockfile fixed 5 advisories; clean npm ci, 212 Vitest, build, both npm audits zero findings; full CI/board history review pending

- S-12.01.03 · The video director uses the product
  work_order: docs/work-orders/S-12.01.03-video-director-uses-the-product.md
  review: docs/evidence/S-12.01.03-validation.md; application and logging patches committed, full repo/live provider checks unrun

- S-06.02.34 · Connectors show how much is left
  work_order: docs/work-orders/S-06.02.34-usage-remaining.md
  review: docs/evidence/S-06.02.34-validation.md; local usage and on-demand balance built, provider header capture/live integration unverified

- S-06.02.28 · A command-line tool locks the workspace it actually opens
  work_order: docs/work-orders/S-06.02.28-path-aware-workspace-lock.md
  review: docs/evidence/S-06.02.28-validation.md; lock and CLI changes committed, real concurrent restore still unverified

- S-06.02.36 · A second owner login is made on purpose
  work_order: docs/work-orders/S-06.02.36-explicit-owner-login.md
  review: docs/evidence/S-06.02.36-validation.md; code and API regression tests committed, full tests unrun

- S-05.01.04 · Public-page fetches connect only to checked destinations
  work_order: docs/work-orders/S-05.01.04-verified-destinations.md
  review: docs/evidence/S-05.01.04-validation.md; verified-IP HTTP plus JS-rendered fail-closed guard (DD-92), full egress proof/tests pending; upstream S-05.01.01 IN_REVIEW

- S-03.01.03 · Browser blocks internal network access
  work_order: docs/work-orders/S-03.01.03-network-isolation.md
  review: docs/evidence/S-03.01.03-validation.md; production Docker-bridge start refused (DD-91), local bridge remains unsafe; full Docker/network proof pending

- S-06.02.37 · Skip navigation keeps the current screen
  work_order: docs/work-orders/S-06.02.37-skip-keeps-current-page.md
  review: docs/evidence/S-06.02.37-validation.md; code/tests committed, frontend and Chromium acceptance unrun

- S-06.02.20 · The verifier tells a shallow clone apart from a missing commit
  work_order: docs/work-orders/S-06.02.20-shallow-git-history.md
  review: docs/evidence/S-06.02.20-validation.md; 67 real Git-fixture and CI tests passed in Render QA; full historical Git ancestry and GitHub Actions verification pending

- S-06.02.39 · Valid low-bitrate WebM exports pass verification
  work_order: docs/work-orders/S-06.02.39-low-bitrate-export.md
  review: docs/evidence/S-06.02.39-validation.md; isolated encode/sample scan verified, full regression and browser pending

- S-12.02.06 · A plan's posting channel runs from the screens
  work_order: docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md
  review: docs/evidence/S-12.02.06-validation.md; browser, full-board and live drafting gates remain open

- S-06.02.38 · Any error can be traced back the next day
  work_order: docs/work-orders/S-06.02.38-traceable-errors.md
  review: docs/evidence/S-06.02.38-validation.md; independent code review clear; Chromium, full-board and hosted verification gated

*(Code and tests pass; DONE waits for a review in a context that did not
write the code, then the evidence block.)*

- S-06.02.25 · Every screen opens at its top, its warnings in view
  work_order: docs/work-orders/S-06.02.25-screen-opens-at-top.md
  tests: frontend/src/components.test.tsx, tests/test_frontend_accessibility_contract.py, scripts/live/screen_opens_at_top.mjs
  command: uv run pytest tests/test_frontend_accessibility_contract.py -q && (cd frontend && npm test && npm run build)
  result: 12 accessibility tests passed; frontend 175 passed and production build passed; Chromium 32 checks passed at 1280x900 and 390x900 (2026-10-04)
  code: frontend/src/App.tsx, frontend/src/styles.css
  commit: 815c72bbc7affdef29b2c288e4d7494a836ea292
  live: Real web entry point and API with disposable SQLite data; complete campaign warning, title, first panel start/header visible; focus main and scroll 0. Long forms/chat can extend below the viewport. Fresh-context review passed. Full board verification re-ran 70 existing DONE commands: 70 passed. Git ancestry was not checked in this source snapshot; historical ancestry and develop CI remain release checks. Work order records browser command/output and limitations; not deployed.

- S-06.02.21 · Durable customer state and safe recovery (audit WP1)
  work_order: docs/work-orders/S-06.02.21-S-06.02.22-close-out.md
  review: docs/evidence/S-06.02.21-security-review-2026-10-15.md; D-313 RED reproduced and fixed; 3 focused, full SQLite 2754 and PostgreSQL 2774 PASS; independent review, live browser, backup/recovery and original Git-history/CI gates still open
- S-06.02.22 · A created or selected campaign stays the active workspace
  work_order: docs/work-orders/S-06.02.21-S-06.02.22-close-out.md

- S-07.01.03 · Meeting transcription with no bot in the call
- S-06.02.05 · The UI is usable by keyboard and screen reader
- S-06.02.02 · Every endpoint authorises and validates
- S-06.02.01 · No secret may enter a model prompt
- S-06.01.04 · Routines that fire agent runs on a schedule or an event
- S-06.01.01 · Workspaces with their own keys and their own logins
- S-04.01.01 · Companions: persisted agent profiles
- S-02.02.02 · PLAN.md as the single source of truth
- S-03.02.05 · A platform is a row, not a code change
- S-06.02.04 · Data deletion and subject access
- S-05.01.03 · Take a competitor post apart and rebuild the shape
- S-05.01.02 · Extraction packs as declared data
- S-05.01.01 · A crawler with a frontier, not a loop
- S-07.01.04 · Reports and artifacts

## BLOCKED

- S-06.02.19 · One working branch holds everything built, and it is green
  blocked: external — the old branches must be kept as `archive/<branch>` tags and then deleted, and GitHub refused both to this session (HTTP 403, 2026-09-23; it may push commits, not tags or deletions). The owner runs `bash scripts/archive_old_branches.sh --delete` from a clone with push rights (`docs/BRANCHING.md`). The rest of the story is met: `develop` holds everything and is green.

- S-06.01.06 · Campaigns, contacts and drafts belong to a workspace
  blocked: Q-27 — built only if the owner chooses option 2, workspace-owned CRM rows (`D-135`).
  design: docs/architecture/CRM_TENANCY.md

- S-06.02.18 · Restore executable CI runner capacity
  blocked: external — GitHub-hosted `ubuntu-latest` jobs are created but fail before runner allocation with zero steps/no logs. Owner must inspect Actions billing/budgets/payment state and repository Actions policy; if those are clean, GitHub Support must resolve hosted-runner provisioning.

- S-01.05.01 · Publish to YouTube through the official API
  blocked: external — a Google Cloud project with YouTube Data API v3 enabled, and OAuth consent for the channel. Only the owner can create it.
- S-01.05.02 · One adapter contract for the remaining platforms
  blocked: external — Meta app review, TikTok content-posting audit, LinkedIn partner programme. Weeks of calendar time, and none of it is engineering.
- S-01.05.03 · Read real engagement back from the platform
  blocked: external — depends on S-01.05.01, which is itself waiting on the Google Cloud project.

## DONE

- S-06.03.03 · The CRM lives in the hosted database
  work_order: docs/work-orders/S-06.03.03-crm-hosted.md
  tests: tests/test_crm_hosted.py::test_a_contact_and_a_campaign_outlive_the_store_that_wrote_them, tests/test_crm_hosted.py::test_an_immediate_transaction_holds_other_processes_back, tests/test_crm_hosted.py::test_no_postgres_column_is_narrower_than_its_sqlite_value, tests/test_crm_hosted.py::test_a_url_in_the_crm_file_setting_is_refused_however_it_arrives, tests/test_crm_hosted.py::test_search_ignores_case_on_every_backend, tests/test_crm_hosted.py::test_concurrent_transactions_lose_no_writes, tests/test_crm_hosted.py::test_a_closed_store_stays_closed, tests/test_crm_hosted.py::test_a_campaign_made_in_the_app_outlives_the_disk, tests/test_crm_hosted.py::test_a_local_crm_left_behind_stops_the_start_and_names_both_choices, tests/test_crm_hosted.py::test_with_no_database_url_the_crm_stays_in_its_file, tests/test_crm_hosted.py::test_import_crm_brings_the_file_in_once, tests/test_crm_hosted.py::test_the_email_worker_sends_from_the_crm_the_app_opens, tests/test_crm_hosted.py::test_the_copy_reconciles_every_table_and_so_does_the_inverse, tests/test_crm_hosted.py::test_copy_crm_copies_a_file_into_the_database_and_back_value_for_value, tests/test_crm_hosted.py::test_a_copy_reads_its_source_at_one_moment, tests/test_crm_hosted.py::test_the_status_says_where_the_crm_really_is, tests/test_crm_hosted.py::test_import_crm_works_after_something_already_started_on_the_database, tests/test_crm_hosted.py::test_every_tool_waits_while_a_local_crm_is_left_behind, tests/test_crm_hosted.py::test_a_value_postgresql_would_change_stops_the_copy_and_is_named, tests/test_crm_hosted.py::test_a_writer_waits_for_another_at_most_five_seconds, tests/test_crm_hosted.py::test_a_watching_worker_rides_out_a_database_that_is_away, tests/test_crm_hosted.py::test_the_worker_opens_the_database_its_option_names, tests/test_crm_hosted.py::test_only_the_install_owner_is_told_where_the_database_is, tests/test_crm_hosted.py::test_a_nul_in_outside_text_is_dropped_on_every_backend, tests/test_crm_harness.py, frontend/src/components.test.tsx
  command: uv run pytest tests/test_crm_hosted.py tests/test_crm_harness.py -q && (cd frontend && npm test -- src/components.test.tsx)
  result: with OFF_CRM_TEST_POSTGRES_URL on a real PostgreSQL 16, tests/test_crm_hosted.py 96 passed (2026-10-03); whole suite 2681 passed, 1 skipped, 0 failed; whole suite with every CRM on PostgreSQL (OFF_CRM_TEST_CRM_ON_POSTGRES=1) 2612 passed, 70 skipped (each marked SQLite-only or about a CRM file, 1 sandbox image), 0 failed; egress wall 42 passed; frontend 175 passed, build clean. Without the URL the PostgreSQL cases skip, as in CI until its new postgres job runs (S-06.02.18)
  live: the real server (run_offsetx_web.py) with the built screens on PostgreSQL 16 in headless Chromium: a campaign, a contact from CSV and an approved draft made through the screens; server stopped, data folder deleted, a new server on an empty folder showed all three, and no CRM file was written (task h, which also found D-226). An engine-written CRM of 9,442 rows copied into PostgreSQL and back, every value equal (task f). The fresh-context review found 11 defects (D-227 to D-237): 10 fixed test-first, 1 filed as S-06.03.07. Its worst one walked with the real commands after the fix: local CRM left behind, hosting switched on, offsetx-email-worker and offsetx-outreach each refused with the import-crm sentence; the worker run with --database at the URL anyway seeded it (8 templates), and import-crm --yes then copied the campaign in, every table reconciled; that walk found D-238, fixed. Not run against Neon or Render: latency there is unmeasured. The fixes were checked by tests and that walk, not by a second review
  code: offsetx_apollo_builder/outreach/store.py, offsetx_apollo_builder/outreach/schema.py, offsetx_apollo_builder/outreach/store_copy.py, offsetx_apollo_builder/outreach/models.py, offsetx_apollo_builder/outreach/sales.py, offsetx_apollo_builder/outreach/deliverability/store.py, offsetx_apollo_builder/db/connection.py, offsetx_apollo_builder/data_paths.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/api/production_runtime.py, offsetx_apollo_builder/db_cli.py, offsetx_apollo_builder/email_worker_cli.py, offsetx_apollo_builder/outreach_cli.py, offsetx_apollo_builder/notebook_cli.py, frontend/src/components.tsx, frontend/src/pages/Settings.tsx, tests/conftest.py, .github/workflows/ci.yml
  commit: 2a8ac3f

- S-06.02.30 · A provider connects from the Connectors screen as shown
  tests: tests/test_ai_api.py::test_the_connect_form_s_own_defaults_are_accepted, tests/test_ai_api.py::test_a_refused_value_is_named_in_the_message_the_screen_shows, tests/test_api_boundary_contract.py::test_validation_error_never_echoes_a_secret_request_body
  command: uv run pytest tests/test_ai_api.py tests/test_api_boundary_contract.py -q
  result: 42 passed (2026-09-25)
  live: in a real headless Chromium against the running app with the built screens: Connectors → NVIDIA NIM → Connect, key pasted, defaults left as shown (call cap 0, spend cap 0); the request carried requests_per_day 0 and the screen said "NVIDIA NIM connected. Key encrypted on this machine.", card On. The RED run reproduced the owner's exact response. Not re-checked on Render from here.
  code: offsetx_apollo_builder/api/schemas.py, offsetx_apollo_builder/api/app.py
  commit: 4d37889

- S-06.02.29 · The NVIDIA reasoning model answers in chat
  tests: tests/test_ai_model_selection.py::test_model_request_options_reach_the_http_payload, tests/test_security_audit.py::test_health_checks_answer_whatever_host_the_platform_sends, tests/test_security_audit.py::test_render_s_own_hostname_is_answered_without_configuration
  command: uv run pytest tests/test_ai_model_selection.py tests/test_security_audit.py -q
  result: 56 passed (2026-09-25)
  live: not yet — both fixes are proven against the real app in-process and the real provider payload, but no call reached NVIDIA (the owner's key is not in this session) and no Render deploy was watched. The owner retries the chat and redeploys develop; D-148 (the 421 health check, S-06.02.10's host guard) ships in the same commit.
  code: config/providers.yaml, offsetx_apollo_builder/ai/providers.yaml, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/api/config.py
  commit: 12afdb6

- S-06.03.02 · Keys, settings and logins live in the hosted database
  work_order: docs/work-orders/S-06.03.02-keys-settings-logins-hosted.md
  tests: tests/test_hosted_storage.py::test_keys_settings_trust_counters_logins_and_the_log_outlive_the_disk, tests/test_hosted_storage.py::test_the_database_holds_each_key_only_as_ciphertext_its_key_opens, tests/test_hosted_storage.py::test_a_database_without_a_secrets_key_is_refused_with_the_next_step, tests/test_hosted_storage.py::test_a_different_key_on_the_same_database_is_refused_at_start, tests/test_hosted_storage.py::test_two_writers_at_once_lose_neither_change, tests/test_hosted_storage.py::test_a_connection_the_server_dropped_is_reopened, tests/test_hosted_storage.py::test_a_statement_that_failed_is_not_sent_again, tests/test_hosted_storage.py::test_a_privacy_request_reaches_a_hosted_login, tests/test_hosted_storage.py::test_a_lost_key_is_given_up_only_on_purpose, tests/test_hosted_storage.py::test_a_database_setting_that_is_not_a_url_is_refused_and_never_becomes_a_file, tests/test_hosted_storage.py::test_an_answer_already_billed_survives_the_database_going_away, tests/test_hosted_storage.py::test_a_signed_in_browser_gets_the_sentence_during_an_outage, tests/test_hosted_storage.py::test_import_local_brings_the_folder_into_the_database, tests/test_hosted_storage.py::test_a_key_read_the_database_could_not_answer_is_not_the_providers_fault, frontend/src/components.test.tsx
  command: uv run pytest tests/test_hosted_storage.py tests/test_db_backend.py -q && (cd frontend && npm test -- src/components.test.tsx)
  result: 55 passed, 6 skipped, then 42 passed (2026-10-02); with OFF_CRM_TEST_POSTGRES_URL on a real PostgreSQL 16, 95 passed with the inventory's tests; full suite 2519 -> 2535 passed, 0 failed
  live: real app processes (run_offsetx_web.py) on a real PostgreSQL 16, in headless Chromium: a key with the 200-a-day and $5 presets, a trust raise with its reason, a colleague's login and a logged call; the process stopped and its data folder deleted; a new process on an empty folder with the two settings showed all of it, "Used today: 1 / 200" included, and the colleague signed in. A different key and no key each refused the start with a sentence; the database held no plain-text key. PostgreSQL stopped under a signed-in browser: the screen said off_CRM cannot reach its database, /health/live stayed 200, readiness named the stores; started again, the app recovered with no restart. The fresh-context review of 646c593 found ten defects, six medium (D-206 to D-215); all fixed test-first, plus D-216 found under load. 8 of the reviewer's 12 reproductions pass; the other 4 expected the old flow and now meet the refusal or 503 the reviewer proposed. The fixes were checked by tests, the reviewer's reproductions and these walks, not by a second review.
  code: offsetx_apollo_builder/db/hosted.py, offsetx_apollo_builder/db/schema.py, offsetx_apollo_builder/db/connection.py, offsetx_apollo_builder/hosted_import.py, offsetx_apollo_builder/ai/workspace.py, offsetx_apollo_builder/ai/quota.py, offsetx_apollo_builder/ai/broker.py, offsetx_apollo_builder/ai/failures.py, offsetx_apollo_builder/ai/eval_cli.py, offsetx_apollo_builder/api/auth.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/api/config.py, offsetx_apollo_builder/api/production_runtime.py, offsetx_apollo_builder/privacy.py, offsetx_apollo_builder/db_cli.py, frontend/src/pages/Connectors.tsx, render.yaml
  commit: 3e48e8a
- S-06.03.01 · Every store's backend is known
  work_order: docs/work-orders/S-06.03.01-store-inventory.md
  tests: tests/test_storage_inventory.py::test_every_service_the_app_opens_is_classified, tests/test_storage_inventory.py::test_every_file_the_app_writes_belongs_to_a_store, tests/test_storage_inventory.py::test_the_design_document_shows_the_inventory_as_generated, tests/test_storage_inventory.py::test_the_inventory_command_reports_each_store_and_what_it_holds_on_disk, tests/test_storage_inventory.py::test_every_file_the_code_names_in_the_data_folder_belongs_to_a_store
  command: uv run pytest tests/test_storage_inventory.py -q
  result: 5 passed (2026-10-02); full suite 2535 passed, 0 failed
  live: offsetx-db inventory on the hosted walk's data folder: every phase-1 store 0 B on disk, the CRM 1.3 MB and the stores with no phase yet listed with their sizes. The review's code scan found the Gmail token, the eval scoreboard and the prospecting ledgers in no entry (D-215); now listed, and S-06.03.06 is filed for every store with no phase. The owner's real install has not been measured: none was available.
  code: offsetx_apollo_builder/db/inventory.py, offsetx_apollo_builder/db_cli.py, docs/architecture/HOSTED_STORAGE.md
  commit: 3e48e8a
- S-06.02.31 · Provider keys come only from the app
  work_order: docs/work-orders/S-06.02.31-keys-only-from-the-app.md
  tests: tests/test_ai_api.py::test_a_key_in_the_server_environment_serves_no_workspace, tests/test_ai_api.py::test_connecting_with_no_key_says_to_paste_one, tests/test_ai_api.py::test_saving_changes_with_the_key_box_blank_keeps_the_stored_key, tests/test_ai_api.py::test_a_local_server_needs_no_key, tests/test_ai_api.py::test_a_rejected_key_points_at_connectors_not_the_environment, tests/test_provider_profile_isolation.py::test_a_draft_request_cannot_name_an_environment_variable_or_a_url, tests/test_provider_profile_isolation.py::test_a_profile_cannot_name_an_environment_variable, tests/test_provider_profile_isolation.py::test_a_stored_profile_naming_a_variable_never_reads_the_environment, tests/test_provider_profile_isolation.py::test_a_client_login_sees_none_of_the_owners_profiles, tests/test_provider_profile_isolation.py::test_a_client_login_cannot_repoint_test_or_delete_the_owners_profile, tests/test_provider_profile_isolation.py::test_a_client_login_drafts_with_its_own_profiles_only, tests/test_provider_profile_isolation.py::test_a_client_logins_new_profile_is_its_own, tests/test_provider_profile_isolation.py::test_the_owners_drafts_never_run_through_another_workspaces_profile, tests/test_provider_profile_isolation.py::test_with_no_profile_of_its_own_the_owner_is_told_so, tests/test_provider_profile_isolation.py::test_a_workspace_named_default_gets_none_of_the_owners_profiles, tests/test_provider_profile_isolation.py::test_a_profile_saved_before_ownership_is_in_no_chain_until_the_owner_confirms_it, tests/test_provider_profile_isolation.py::test_confirming_never_takes_another_workspaces_profile, tests/test_provider_profile_isolation.py::test_a_request_cannot_choose_whose_profiles_it_saves_or_drafts_with, tests/test_provider_profile_isolation.py::test_the_provider_call_log_shows_a_client_only_its_own_calls, tests/test_provider_profile_isolation.py::test_the_owner_learns_that_old_profiles_wait_for_them, tests/test_provider_profile_isolation.py::test_the_owner_is_never_told_a_clients_profile_is_theirs, tests/test_provider_profile_isolation.py::test_confirming_returns_a_profile_to_the_workspace_it_was_saved_for, tests/test_provider_profile_isolation.py::test_a_profile_labelled_for_no_workspace_is_the_owners_once_its_key_is_proved, tests/test_provider_profile_isolation.py::test_an_unconfirmed_profile_is_confirmed_or_removed_never_resaved, tests/test_provider_profile_isolation.py::test_confirm_goes_by_the_profiles_label_whoever_the_cookie_names, tests/test_provider_profile_isolation.py::test_an_edit_checks_whose_the_profile_is_as_it_writes, tests/test_provider_profile_isolation.py::test_confirming_needs_the_key_the_profile_holds, tests/test_provider_profile_isolation.py::test_a_profile_with_no_key_cannot_be_confirmed, tests/test_provider_profile_isolation.py::test_the_owners_default_profile_stays_the_owners_whatever_a_workspace_is_called, tests/test_provider_profile_isolation.py::test_the_panel_knows_where_confirm_puts_each_profile, tests/test_provider_profile_isolation.py::test_a_profile_with_no_key_is_refused_for_the_true_reason, tests/test_provider_profile_isolation.py::test_confirm_goes_only_where_the_button_said, tests/test_provider_profile_isolation.py::test_a_profile_saved_for_a_client_can_go_back_to_it_or_be_the_owners, frontend/src/components.test.tsx
  command: uv run pytest tests/test_ai_api.py tests/test_provider_profile_isolation.py -q && (cd frontend && npm test -- src/components.test.tsx)
  result: 70 passed, then 41 passed (2026-09-28); full suite 2501 passed, 0 failed; frontend 171 passed
  live: real headless Chromium: a blank-key connect says to paste the key and stores nothing. The fresh-context review then found two critical holes in older code (D-154, D-155) - a draft request or a profile could make the server send any environment variable to any URL, and a client login could re-point the owner's profile to receive the owner's key; its reproductions are these tests, red before the fix, acting as a real second workspace login through the API. The second review found the owner's own fallback drafts used every workspace's profiles (D-165), ownership was a typed label (D-166) and the call log was unscoped (D-168); its reproductions are the seven tests after the D-155 ones, red before the fix. The third review found old profiles stopped with no screen to settle them and one saved for a client could be confirmed into the owner's chain (D-177), confirm read a cookie (D-181) and an edit raced a delete (D-182); real headless Chromium on a server seeded with two old profiles: Settings listed both with where each sends, confirming the owner's said "confirmed as yours", confirming one labelled for a workspace that does not exist was refused with its sentence. The fourth review found a "default" label proved nothing (D-185) and Confirm was offered where it could not work (D-187); real headless Chromium: a keyless old profile offered only Remove, a wrong key was refused with its sentence, the right key confirmed it. After the fifth check (D-190, a client workspace named "default" received the owner's profile): each Confirm button names where it puts the profile — "Confirm as yours" for a "default" one — in real headless Chromium. After the sixth check (D-194): a page loaded before a workspace named like the profile's label was made still confirmed it exactly where its pressed button said, in real headless Chromium. Six fresh-context review rounds; every finding fixed test-first except D-196, filed as S-06.02.36. Re-reading the D-194 fix found D-197, red in real headless Chromium before the fix: Enter, and a click on "Confirm as yours" in a browser that does not report the pressed button, sent the profile to the client workspace; after it, Enter with two places to go said to press a button and sent nothing, and both clicks went where they said.
  code: offsetx_apollo_builder/ai/workspace.py, offsetx_apollo_builder/ai/failures.py, offsetx_apollo_builder/api/schemas.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/outreach/provider_profiles.py, offsetx_apollo_builder/outreach/providers.py, offsetx_apollo_builder/outreach/store.py, frontend/src/pages/Drafts.tsx, frontend/src/pages/Settings.tsx, frontend/src/types.ts
  commit: 2b9fa17
- S-06.02.32 · The connect form offers limit presets
  work_order: docs/work-orders/S-06.02.32-limit-presets.md
  tests: frontend/src/components.test.tsx, tests/test_ai_api.py::test_the_connect_form_s_own_defaults_are_accepted, tests/test_ai_trust.py::test_saving_the_model_list_keeps_the_caps_and_what_is_sent
  command: uv run pytest tests/test_ai_api.py::test_the_connect_form_s_own_defaults_are_accepted tests/test_ai_trust.py::test_saving_the_model_list_keeps_the_caps_and_what_is_sent -q && (cd frontend && npm test -- src/components.test.tsx)
  result: 2 passed, then 41 passed (2026-09-28); frontend 171 passed, build clean
  live: real headless Chromium: "200 a day" and "$5 a day" posted 200 and 5 and reopened as selected; after the review, a blank custom cap showed "Type a number of 0 or more..." and sent no request (D-161). Saving the model list no longer resets the caps (D-159).
  code: frontend/src/pages/CapPicker.tsx, frontend/src/pages/Connectors.tsx, offsetx_apollo_builder/ai/workspace.py
  commit: 2b9fa17
- S-06.02.33 · Trust is the owner's to change, per provider and per model
  work_order: docs/work-orders/S-06.02.33-trust-per-provider-and-model.md
  tests: tests/test_ai_trust.py::test_lowering_a_provider_applies_to_its_models_with_no_reason_asked, tests/test_ai_trust.py::test_raising_needs_a_typed_reason_and_records_who_and_when, tests/test_ai_trust.py::test_a_model_can_be_trusted_less_than_its_provider_never_more, tests/test_ai_trust.py::test_blocking_a_provider_blocks_every_model_under_it, tests/test_ai_trust.py::test_a_provider_raise_never_lifts_a_model_capped_by_who_built_it, tests/test_ai_trust.py::test_a_raise_never_stands_without_its_reason, tests/test_ai_trust.py::test_withdrawing_full_access_keeps_the_trust_settings, tests/test_ai_trust.py::test_a_full_access_grant_never_lifts_what_a_limited_model_sends, tests/test_ai_trust.py::test_every_trust_change_is_kept_with_who_when_and_why, tests/test_ai_trust.py::test_no_trust_setting_opens_the_mailbox, tests/test_ai_trust.py::test_the_connect_ceiling_follows_a_changed_trust, tests/test_ai_trust.py::test_who_decided_is_the_login_not_what_the_request_claims, tests/test_ai_trust.py::test_find_models_shows_the_owners_trust_not_the_default, tests/test_ai_trust.py::test_lowering_the_provider_never_raises_what_a_capped_model_is_sent, tests/test_ai_trust.py::test_a_model_the_owner_lowered_never_gains_the_grant, tests/test_ai_trust.py::test_the_full_data_grant_really_sends_full_data, tests/test_ai_trust.py::test_withdrawing_the_grant_returns_what_is_sent_to_the_ceiling, tests/test_ai_trust.py::test_lowering_the_provider_pauses_the_grant_and_its_default_resumes_it, tests/test_ai_trust.py::test_a_grant_is_refused_where_it_could_change_nothing, tests/test_ai_trust.py::test_the_card_shows_the_limit_the_owners_trust_sets, tests/test_ai_trust.py::test_disconnect_takes_the_record_and_the_key_together, tests/test_ai_trust.py::test_a_click_that_changes_nothing_records_nothing, tests/test_ai_trust.py::test_trust_history_and_reasons_are_bounded, tests/test_ai_trust.py::test_returning_to_the_default_resumes_the_grant_after_a_save_made_while_paused, tests/test_ai_trust.py::test_withdrawing_the_grant_stops_full_data_even_after_a_raise, tests/test_ai_trust.py::test_a_save_made_while_trust_is_lowered_keeps_the_owners_choice, tests/test_ai_trust.py::test_sends_is_what_the_switched_on_models_are_sent, tests/test_ai_trust.py::test_the_grant_is_refused_and_not_offered_where_no_switched_on_model_can_use_it, tests/test_ai_trust.py::test_the_card_says_why_a_grant_is_not_in_force, tests/test_ai_trust.py::test_the_card_describes_the_trust_the_owner_set, tests/test_ai_trust.py::test_disconnect_disconnects_when_the_stored_keys_cannot_be_read, tests/test_ai_trust.py::test_the_models_a_provider_can_hold_are_bounded, tests/test_ai_trust.py::test_the_card_never_claims_a_ceiling_no_switched_on_model_gets, tests/test_ai_trust.py::test_a_save_that_is_cut_says_so, tests/test_ai_trust.py::test_the_form_offers_levels_up_to_the_providers_standing_trust, tests/test_ai_trust.py::test_withdrawing_a_grant_never_raises_what_is_sent, tests/test_ai_trust.py::test_a_provider_whose_models_are_all_blocked_sends_nothing, tests/test_ai_trust.py::test_a_damaged_key_store_says_what_the_install_owner_can_do, tests/test_ai_trust.py::test_a_damaged_master_key_is_fixed_by_the_step_the_message_gives, frontend/src/components.test.tsx
  command: uv run pytest tests/test_ai_trust.py tests/test_ai_egress_wall.py -q && (cd frontend && npm test -- src/components.test.tsx)
  result: 93 passed, then 41 passed (2026-09-28); egress wall 42 of 42
  live: real headless Chromium, after the review's fixes: deepseek-ai/deepseek-r1 stayed Restricted under Highest-trust NVIDIA and its own setting lifted it after a reason; blocking NVIDIA showed Llama (own setting Highest) and DeepSeek (own setting Default) both Blocked; setting a model above its provider was refused with the sentence. The first rule (a model's setting wins both ways) failed the review (D-156); DD-65 is amended. After the second review, real headless Chromium on NVIDIA: "Send full data to NVIDIA NIM anyway..." with a reason made Sends read Full access and the card say "Full data granted by you"; lowering NVIDIA to Restricted showed Sends Pseudonymous and "Full data paused"; its default resumed it; withdraw returned Sends to Standard. DeepSeek's form showed Pseudonymous selected (D-174); a blocked card had no Allow anyway button; the console showed no errors once the icon was declared (D-175). After the third review, in real headless Chromium: grant, pause, a save while paused, then resume sent Full again (D-176); raise to Highest then withdraw showed "Up to Standard", the owner's level; with only DeepSeek-R1 on, no grant was offered and Sends read Pseudonymous (D-179); a blocked card read Sends: Nothing. The reviewer's 2,800-sequence random test still finds no lowering that raises what is sent. After the fourth review: the form offered Strict to Standard only at Default trust, its hint followed the grant, and a provider with its only model blocked read Sends: Nothing; the fourth reviewer's extended random test (400 seeds, five providers) finds 0 violations and 0 cards that disagree with the router.
  code: offsetx_apollo_builder/ai/registry.py, offsetx_apollo_builder/ai/workspace.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/api/schemas.py, config/providers.yaml, frontend/src/pages/TrustSelect.tsx, frontend/src/pages/Connectors.tsx, frontend/src/types.ts, frontend/src/styles.css, frontend/index.html
  commit: 2b9fa17
- S-06.02.24 · Every process that writes the workspace holds its lease
  work_order: docs/work-orders/S-06.02.24-workspace-lease-for-clis.md
  tests: tests/test_cli_workspace_lease.py::test_a_tool_refuses_while_a_restore_holds_the_workspace, tests/test_cli_workspace_lease.py::test_a_tool_refuses_while_a_restore_waits_to_be_rolled_back, tests/test_cli_workspace_lease.py::test_a_tool_lets_a_restore_in_once_it_finishes, tests/test_cli_workspace_lease.py::test_a_command_that_opens_nothing_still_runs_during_a_restore, tests/test_cli_workspace_lease.py::test_offsetx_db_still_checks_postgres_during_a_restore, tests/test_cli_workspace_lease.py::test_offsetx_artifacts_still_renders_a_run_kept_outside_the_workspace, tests/test_cli_workspace_lease.py::test_a_lock_file_is_readable_by_the_apps_own_user, tests/test_cli_workspace_lease.py::test_a_lock_file_this_process_cannot_write_still_locks, tests/test_cli_workspace_lease.py::test_a_refused_tool_writes_nothing_into_the_workspace, tests/test_cli_workspace_lease.py::test_a_restore_left_committed_is_not_called_interrupted, tests/test_cli_workspace_lease.py::test_copy_log_locks_when_it_would_write_into_the_workspace, tests/test_cli_workspace_lease.py::test_check_locks_the_crm_database_even_outside_the_data_dir, tests/test_default_data_paths.py::test_gmail_authorize_writes_the_token_where_the_web_app_reads_it, tests/test_default_data_paths.py::test_offsetx_db_checks_the_egress_log_the_web_app_writes, tests/test_default_data_paths.py::test_the_notebook_reads_the_web_apps_context_when_the_crm_lives_elsewhere, tests/test_default_data_paths.py::test_the_env_template_leaves_every_durable_path_to_the_data_dir
  command: uv run pytest tests/test_cli_workspace_lease.py tests/test_default_data_paths.py tests/test_workspace_lock.py -q
  result: 51 passed (2026-09-24); full suite 2371 -> 2413 passed, 0 failed; Python 3.10 full suite 2404 passed before the review fixes
  live: installed tools against a running web app: all six refused while a separate process held the exclusive lease; a real HTTP restore answered 409 while a real offsetx-outreach import held its lease, and succeeded after it ended. Lock-file permissions checked with two real users (root makes the file, nobody still leases it and is refused under root's exclusive). Two fresh-context reviews: D-142..D-145 fixed test-first (the first D-142 fix was wrong and the second review caught it); D-146 filed as S-06.02.28, not claimed.
  code: offsetx_apollo_builder/outreach/workspace_lock.py, offsetx_apollo_builder/data_paths.py, offsetx_apollo_builder/outreach_cli.py, offsetx_apollo_builder/notebook_cli.py, offsetx_apollo_builder/ai/eval_cli.py, offsetx_apollo_builder/ai/tool_cli.py, offsetx_apollo_builder/db_cli.py, offsetx_apollo_builder/artifact_cli.py, offsetx_apollo_builder/api/config.py, .env.example
  commit: c9d2cc8

- S-12.02.04 · A review becomes the next version of the plan
  tests: tests/test_gtm_revise.py::test_a_measured_rate_replaces_the_assumption, tests/test_gtm_revise.py::test_too_few_contacted_carries_the_assumption_forward, tests/test_gtm_revise.py::test_applying_a_revision_updates_the_same_campaigns, tests/test_gtm_revise.py::test_a_plan_with_no_review_is_not_revised, tests/test_gtm_revise.py::test_the_deadline_stays_and_the_target_is_what_is_left, tests/test_gtm_revise.py::test_the_review_of_a_revision_counts_only_its_own_sends, tests/test_gtm_revise.py::test_replies_between_a_review_and_the_next_apply_count_for_the_next_version, tests/test_gtm_revise.py::test_a_revised_angle_reaches_the_posts_and_the_emails, tests/test_gtm_revise.py::test_a_deleted_campaign_is_made_again_when_the_revision_is_applied, tests/test_gtm_revise.py::test_an_older_database_gains_the_baseline_column, tests/test_gtm_revise.py::test_revise_over_http
  command: uv run pytest tests/test_gtm_revise.py -q
  result: 24 passed (2026-09-23)
  live: walked in a real headless Chromium against the running app — draft, apply, review, then "Write the next version from this review": version 2 appears as a draft beside the applied version 1, keeps the 2026-10-23 deadline and says why the assumed rate carried forward. The rollback was executed once: all four gtm tables dropped under a real app, the CRM kept every campaign with the same ids, and the tables came back on the next write. The migration test fails with the add-column line removed. The cold review found D-89, D-90, D-95 and D-96 here; each has a test that failed first.
  code: offsetx_apollo_builder/gtm/review.py, offsetx_apollo_builder/gtm/service.py, offsetx_apollo_builder/gtm/store.py, offsetx_apollo_builder/api/gtm.py, frontend/src/pages/Strategy.tsx
  commit: 03203ac

- S-12.02.03 · The brain says where it is going wrong, in a fixed order
  tests: tests/test_gtm_review.py::test_delivery_is_diagnosed_before_copy, tests/test_gtm_review.py::test_a_campaign_paused_for_bouncing_is_never_told_to_resume, tests/test_gtm_review.py::test_the_order_is_fixed, tests/test_gtm_review.py::test_no_verdict_without_enough_data, tests/test_gtm_review.py::test_verdict_uses_an_interval_not_a_threshold, tests/test_gtm_review.py::test_distribution_review_follows_the_pacers_action, tests/test_gtm_review.py::test_remedies_outside_the_permitted_set_are_dropped, tests/test_gtm_review.py::test_a_review_with_no_model_uses_rules_and_says_so, tests/test_gtm_review.py::test_review_stores_what_it_measured, tests/test_gtm_review.py::test_what_the_brain_needs_survives_the_shape_filter, tests/test_pacing_cap.py::test_the_pacer_steers_by_the_newest_views_goal
  command: uv run pytest tests/test_gtm_review.py tests/test_pacing_cap.py -q
  result: 64 passed (2026-09-23)
  live: walked in a real headless Chromium: "Review against what was measured" on an applied plan shows email "not started — the email campaign is paused" with "Resume the campaign." linking to Campaigns, and says the remedies are the rules' because no model is connected. The first RED run was a collection error (no review module). The real pacer drives the distribution tests, not a dict shaped like it.
  code: offsetx_apollo_builder/gtm/review.py, offsetx_apollo_builder/gtm/service.py, offsetx_apollo_builder/api/gtm.py, offsetx_apollo_builder/api/app.py
  commit: 03203ac

- S-12.02.02 · An approved plan becomes paused campaigns, and nothing sends by itself
  tests: tests/test_gtm_apply.py::test_apply_creates_one_paused_campaign_per_channel, tests/test_gtm_apply.py::test_only_a_draft_can_be_applied, tests/test_gtm_apply.py::test_two_applies_at_once_cannot_both_run, tests/test_gtm_apply.py::test_a_failed_apply_resumes_without_duplicates, tests/test_gtm_apply.py::test_a_campaign_is_paused_before_it_is_linked, tests/test_gtm_apply.py::test_apply_returns_next_steps_and_spends_nothing, tests/test_gtm_apply.py::test_next_steps_say_plainly_that_posting_has_no_screen_yet, tests/test_distribution.py::test_a_paused_campaign_publishes_nothing_and_the_post_waits, tests/test_content_automation.py::test_a_paused_campaign_makes_nothing
  command: uv run pytest tests/test_gtm_apply.py tests/test_distribution.py tests/test_content_automation.py -q
  result: 78 passed (2026-09-23)
  live: walked in a real headless Chromium: Apply's confirm dialog, then the email campaign read back from the CRM as paused and nothing sent. The cold review showed "paused" did not stop posting (D-87); publishing and content automation now skip a paused campaign and fail closed when one cannot be read.
  code: offsetx_apollo_builder/gtm/service.py, offsetx_apollo_builder/gtm/store.py, offsetx_apollo_builder/distribution/engine.py, offsetx_apollo_builder/distribution/automation.py, frontend/src/pages/Strategy.tsx
  commit: 03203ac

- S-12.02.01 · A goal becomes a checked plan that fits what is connected
  tests: tests/test_gtm_strategy.py::test_envelope_counts_only_what_is_connected, tests/test_gtm_strategy.py::test_unknown_kind_is_refused_by_name, tests/test_gtm_strategy.py::test_volume_is_clamped_to_the_envelope, tests/test_gtm_strategy.py::test_email_always_uses_targeted_outreach, tests/test_gtm_strategy.py::test_forbidden_claim_is_removed_and_named, tests/test_gtm_strategy.py::test_system_prompt_carries_no_product_text, tests/test_gtm_strategy.py::test_product_travels_in_classified_fields, tests/test_gtm_strategy.py::test_no_permitted_model_returns_the_rules_plan, tests/test_gtm_strategy.py::test_feasibility_is_arithmetic_the_owner_can_check, tests/test_gtm_strategy.py::test_never_claim_survives_the_notes_limit, tests/test_gtm_strategy.py::test_an_infinite_volume_is_treated_as_no_number
  command: uv run pytest tests/test_gtm_strategy.py -q
  result: 50 passed (2026-09-23)
  live: DEMO.md section 15 (section 14 before the branches were consolidated) run exactly as written: with no provider connected the plan is the rules plan and its first note says why ("No model could write this plan: No AI provider is connected…"), never an error. Walked in a real headless Chromium: the goal form drafts a plan whose feasibility is arithmetic on the page.
  code: offsetx_apollo_builder/gtm/strategy.py, offsetx_apollo_builder/gtm/service.py, offsetx_apollo_builder/api/gtm.py, frontend/src/pages/Strategy.tsx
  commit: 03203ac

- S-12.01.02 · Everything that writes for a campaign uses its product
  tests: tests/test_gtm_product_wiring.py::test_links_replace_and_one_product_per_campaign, tests/test_gtm_product_wiring.py::test_links_are_scoped_to_the_workspace_and_die_with_the_product, tests/test_gtm_product_wiring.py::test_email_template_placeholders_come_from_the_linked_product, tests/test_gtm_product_wiring.py::test_draft_audit_flags_a_forbidden_claim, tests/test_gtm_product_wiring.py::test_product_angle_is_resolved_before_the_data_class_is_chosen, tests/test_gtm_product_wiring.py::test_automation_resolves_the_product_angle, tests/test_gtm_product_wiring.py::test_a_campaign_linked_in_another_workspace_cannot_be_taken, tests/test_gtm_product_wiring.py::test_every_engine_is_built_with_products, tests/test_gtm_product_wiring.py::test_a_template_can_say_the_angle_and_gets_the_one_liner_without_a_plan
  command: uv run pytest tests/test_gtm_product_wiring.py tests/test_gtm_products.py -q
  result: 53 passed (2026-09-23)
  live: walked in a real headless Chromium on the Product screen: a campaign linked and saved; "New product" opens an empty form; a box ticked and not saved does not follow to another product; a linked campaign deleted from the CRM shows "no longer exist. Save to drop them." and Save drops it (D-99). The structural engine test was mutation-checked: an unwrapped engine site is caught.
  code: offsetx_apollo_builder/gtm/store.py, offsetx_apollo_builder/outreach/email_expert.py, offsetx_apollo_builder/distribution/automation.py, offsetx_apollo_builder/api/app.py, frontend/src/pages/Product.tsx
  commit: 03203ac

- S-12.01.01 · The owner records the product once
  tests: tests/test_gtm_products.py::test_a_product_is_created_at_version_one_and_read_back, tests/test_gtm_products.py::test_bad_input_is_refused_with_the_field_named, tests/test_gtm_products.py::test_an_email_address_is_refused_at_the_door, tests/test_gtm_products.py::test_an_edit_raises_the_version, tests/test_gtm_products.py::test_a_stale_version_is_a_conflict_not_a_lost_update, tests/test_gtm_products.py::test_another_workspace_cannot_see_the_product, tests/test_gtm_products.py::test_delete_removes_the_product, tests/test_gtm_products.py::test_the_product_round_trips_over_http, tests/test_gtm_products.py::test_http_refusals_are_sentences_not_stack_traces, tests/test_gtm_products.py::test_gtm_owns_no_transport, tests/test_gtm_products.py::test_nothing_gtm_loads_reaches_a_model_or_the_network
  command: uv run pytest tests/test_gtm_products.py -q
  result: 36 passed (2026-09-23)
  live: walked in a real headless Chromium: the Product form saves at version 1 and reads back. A clean interpreter that imports the gtm package loads nothing from ai/ and no network library — the check the cold review showed the AST walk alone could not make (D-98).
  code: offsetx_apollo_builder/gtm/products.py, offsetx_apollo_builder/gtm/store.py, offsetx_apollo_builder/api/gtm.py, frontend/src/pages/Product.tsx
  commit: 03203ac

- S-06.02.17 · DONE may not depend on unfinished work
  tests: tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails, tests/test_verify_board.py::test_done_with_only_done_dependencies_passes
  command: uv run pytest tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails tests/test_verify_board.py::test_done_with_only_done_dependencies_passes -q
  result: 7 passed in 0.57s; full Python regression 1940 passed, 4 skipped, 4 warnings in 139.98s (0:02:19)
  live: the acceptance fixture places the upstream story in BACKLOG, READY, IN_PROGRESS, IN_REVIEW, BLOCKED and DEFERRED and the verifier refuses every impossible DONE chain while naming both story IDs and the upstream state; an all-DONE chain passes.
  code: scripts/verify_board.py, tests/test_verify_board.py, DEFINITION_OF_DONE.md
  commit: bafb973

- S-06.02.08 · One runner for every evidence command
  tests: tests/test_verify_board.py::test_done_evidence_must_enter_the_locked_uv_runner, tests/test_ci_verifier_environment.py::test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier, tests/test_ci_verifier_environment.py::test_clean_checkout_docs_prepare_both_evidence_environments_before_verification
  command: uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q
  result: 58 passed in 5.34s; full Python regression 1933 passed, 4 skipped, 4 warnings in 151.84s (0:02:31)
  live: every DONE command now starts with uv run; the verifier rejects ambient-Python evidence even with --skip-tests; clean-checkout docs and CI prepare the locked Python and frontend evidence dependencies before verification.
  code: scripts/verify_board.py, tests/test_verify_board.py, tests/test_ci_verifier_environment.py, DEFINITION_OF_DONE.md, README.md, CONTINUE.md
  commit: 93ad48b

- S-06.02.03 · Cost and latency budgets per run
  tests: tests/test_agent_run_budgets.py, tests/test_agent_money_ceiling.py
  command: uv run pytest tests/test_agent_run_budgets.py tests/test_agent_money_ceiling.py -q
  result: 33 passed (2026-09-16); full Python regression 1928 passed, 4 skipped
  live: the run stops before a browser action when the model call consumes the remaining latency; stops before another model call when a browser action crosses it; resume preserves prior measured latency; raising the ceiling explicitly resumes; existing spend pre-check still prevents the provider call. A first full-suite run also exposed an unrelated Chromium startup timeout; the clean rerun passed all 1928 Python tests before this code was committed.
  code: offsetx_apollo_builder/agent/run.py, tests/test_agent_run_budgets.py
  commit: 7071213

- S-06.02.15 · CI gives the verifier the repository it claims to verify
  tests: tests/test_ci_verifier_environment.py, tests/test_verify_board.py
  command: uv run pytest tests/test_ci_verifier_environment.py tests/test_verify_board.py -q
  result: 55 passed (2026-09-16); GitHub Actions test run 393 passed end to end
  live: the pre-fix CI passed 1915 Python tests and then the verifier failed because checkout depth 1 hid historical evidence commits and frontend evidence ran before npm dependencies existed. Run 393, commit 0434081, passed after fetch-depth 0 and npm ci were moved before verification.
  code: .github/workflows/ci.yml, scripts/verify_board.py, tests/test_ci_verifier_environment.py
  commit: 0434081

- S-06.02.14 · A test should not hardcode a trace step id
  tests: tests/test_trace_ids.py::test_inserting_a_step_moves_the_number_but_not_the_answer, tests/test_trace_ids.py::test_a_scripted_answer_is_filled_in_with_what_was_offered, tests/test_trace_ids.py::test_the_most_recent_offer_wins, tests/test_trace_ids.py::test_the_first_step_of_a_kind_is_found_not_counted, tests/test_trace_ids.py::test_asking_for_a_step_that_is_not_there_says_so, tests/test_trace_ids.py::test_an_answer_that_cites_nothing_is_left_exactly_alone
  command: uv run pytest tests/test_trace_ids.py tests/test_agent_provenance.py tests/test_agent_structured_result.py tests/test_agent_claim_verification.py tests/test_agent_report.py tests/test_agent_resume.py -q
  result: 58 passed (2026-09-12)
  live: the criterion is "adding a step anywhere breaks nothing", which cannot be asserted from inside the tests it protects — so it was proven by doing it. A junk `Step(kind="noise")` inserted into `agent/run.py` shifts every trace id in every run; the five converted files then ran **49 passed**, and the step was removed. The first attempt at this found a straggler nothing else would have: `screenshot == "0002.png"` failed, because artefact filenames encode the step index too and it was the same defect in another costume.
  code: tests/trace_ids.py, tests/test_agent_provenance.py, tests/test_agent_structured_result.py, tests/test_agent_claim_verification.py, tests/test_agent_resume.py
  commit: 122871f

- S-06.02.12 · A recorded commit must be on the branch
  tests: tests/test_verify_board.py::test_a_commit_that_exists_but_was_orphaned_fails, tests/test_verify_board.py::test_a_commit_that_does_not_exist_at_all_fails, tests/test_verify_board.py::test_a_commit_that_is_on_the_branch_passes, tests/test_verify_board.py::test_a_repository_with_no_git_is_noted_rather_than_failed
  command: uv run pytest tests/test_verify_board.py -q
  result: 53 passed (2026-09-12)
  live: git clone -q . /tmp/gate2, then a real orphan built in the clone the way it really happens — commit, note the sha, `git commit --amend`. `git cat-file -e` still finds the object, which is the trap; the verifier refused it: "S-06.02.11 records commit 16c89e0, which exists but is not an ancestor of HEAD." Against the real board it reports 48 recorded commits, all on this branch. Run in a throwaway clone rather than the working tree, because the first attempt at this check used `git reset --hard` here and discarded the work it was checking — `D-45`.
  code: scripts/verify_board.py
  commit: e8dbaa6

- S-06.02.11 · The verifier catches a stale READY column
  tests: tests/test_verify_board.py::test_ready_with_a_dependency_that_is_not_done_fails, tests/test_verify_board.py::test_a_dependency_on_a_story_that_does_not_exist_fails, tests/test_verify_board.py::test_a_backlog_story_whose_dependencies_are_all_done_is_named, tests/test_verify_board.py::test_a_backlog_story_with_an_open_question_against_it_is_not_named, tests/test_verify_board.py::test_a_story_id_is_read_whole_and_not_cut_at_its_first_full_stop, tests/test_verify_board.py::test_a_question_that_names_its_story_only_in_the_heading_still_blocks, tests/test_verify_board.py::test_an_answered_question_in_the_heading_does_not_block, tests/test_verify_board.py::test_ready_with_every_dependency_done_passes
  command: uv run pytest tests/test_verify_board.py -q
  result: 49 passed (2026-09-12)
  live: python scripts/verify_board.py --skip-tests, then each new rule broken on purpose against the real repository and restored. As it stands it reports `1 story(s) could be pulled today: S-06.02.03` — which became available when S-06.01.03 landed the day before. Moving S-02.02.03 into READY while S-02.02.02 is still BACKLOG: refused. Pointing S-06.02.03's dependency at S-99.99.99: refused. Moving S-06.01.02 into READY: refused by Q-04 — the rule that `D-44` had kept silent since the verifier was written, firing for the first time on real data.
  code: scripts/verify_board.py
  commit: a9cee44

- S-11.05.01 · Concurrent runs share one browser safely
  tests: tests/test_browser_concurrency.py::test_two_runs_on_one_host_share_the_floor, tests/test_browser_concurrency.py::test_the_floor_holds_as_the_number_of_runs_grows, tests/test_browser_concurrency.py::test_runs_arriving_together_are_spaced_rather_than_all_waved_through, tests/test_browser_concurrency.py::test_concurrent_runs_draw_on_one_budget_not_one_each, tests/test_browser_concurrency.py::test_separate_ledger_objects_over_one_file_share_a_lock, tests/test_browser_concurrency.py::test_the_ceiling_can_be_overshot_by_the_runs_in_flight_and_no_more, tests/test_browser_concurrency.py::test_neither_run_can_resolve_a_handle_from_the_others_page, tests/test_browser_concurrency.py::test_different_hosts_do_not_wait_for_each_other, tests/test_browser_concurrency.py::test_a_session_hands_out_one_pace_so_there_is_a_right_answer
  command: uv run pytest tests/test_browser_concurrency.py tests/test_browser_budget.py tests/test_browser_agent.py tests/test_browser_countdown.py tests/test_browser_enter_gate.py tests/test_agent_run.py tests/test_browser_signin.py tests/test_browser_revoke.py -q
  result: 161 passed (2026-09-11)
  live: python scripts/live/two_runs_one_browser.py — one real headless Chromium, two tabs acting at the same time, all four steps checked and exit 0 only if every one holds. Separate tabs, separate traces, separate snapshots; a handle from the other run's page refused with LookupError; eight actions across both runs took 2.80s against a floor that a per-run clock would have satisfied in ~1.4s; all ten charges reached one ledger. Measured concurrently on purpose — a sequential probe of the same two things passed while both were broken.
  code: offsetx_apollo_builder/browser/pace.py, offsetx_apollo_builder/browser/page.py, offsetx_apollo_builder/browser/budget.py, offsetx_apollo_builder/browser/session.py
  commit: 117ee87

- S-11.03.03 · Enter is gated like the button beside it
  tests: tests/test_browser_enter_gate.py::test_enter_in_a_field_whose_form_submits_with_send_needs_confirmation, tests/test_browser_enter_gate.py::test_enter_and_click_agree_about_what_needs_a_human, tests/test_browser_enter_gate.py::test_a_key_that_cannot_submit_asks_nothing, tests/test_browser_enter_gate.py::test_a_key_that_cannot_submit_does_not_even_ask_the_page, tests/test_browser_enter_gate.py::test_if_the_page_cannot_be_asked_it_fails_closed, tests/test_browser_enter_gate.py::test_enter_in_a_search_box_is_ordinary, tests/test_browser_enter_gate.py::test_enter_is_sent_with_the_character_it_produces, tests/test_browser_enter_gate.py::test_a_key_that_produces_no_character_sends_none, tests/test_browser_enter_gate.py::test_an_unattended_run_cannot_countdown_its_way_past_enter_either
  command: uv run pytest tests/test_browser_enter_gate.py tests/test_browser_countdown.py tests/test_browser_agent.py tests/test_agent_run.py tests/test_agent_wall.py tests/test_agent_no_duplicate_effects.py tests/test_browser_revoke.py tests/test_browser_signin.py -q
  result: 150 passed (2026-09-11)
  live: python scripts/live/enter_is_gated.py — real headless Chromium, a real `<form>` with a real submit button, all six steps checked and exit 0 only if every one holds. Step 0 proves the hole is real: with the gate waived, Enter submits the form (`COMPOSE SUBMITTED`). Gated, the same keystroke is refused and **the page reports `nothing happened`**. Tab, ArrowDown and Escape pass straight through. Enter in a `<textarea>` beside a Send button is ordinary, because there it makes a newline and cannot submit. Enter in a search box runs the search. Cleared by a countdown, Enter submits. The proof is asked of the page every time, which is how `D-40` was found — every previous test of `press` asked the return value, and the return value said `ok=True` the whole time the key was doing nothing.
  code: offsetx_apollo_builder/browser/page.py
  commit: 99d5219

- S-02.02.04 · Safety countdowns before consequential actions
  tests: tests/test_browser_countdown.py::test_a_cancelled_countdown_sends_nothing_to_the_site, tests/test_browser_countdown.py::test_an_unattended_run_cannot_use_a_countdown, tests/test_browser_countdown.py::test_cancelling_is_prompt_rather_than_eventually, tests/test_browser_countdown.py::test_it_can_be_cancelled_from_another_thread, tests/test_browser_countdown.py::test_somebody_watching_sees_it_count_down, tests/test_browser_countdown.py::test_a_countdown_covers_one_action_and_no_more, tests/test_browser_countdown.py::test_without_a_countdown_a_send_still_refuses_and_asks, tests/test_browser_countdown.py::test_a_countdown_that_elapses_lets_the_click_through, tests/test_browser_countdown.py::test_an_ordinary_click_never_waits_for_anything
  command: uv run pytest tests/test_browser_countdown.py tests/test_browser_agent.py tests/test_agent_run.py tests/test_agent_wall.py tests/test_agent_no_duplicate_effects.py tests/test_browser_revoke.py -q
  result: 95 passed (2026-09-11)
  live: python scripts/live/cancel_the_countdown.py — real headless Chromium on a real page, all four steps checked and exit 0 only if every one holds. A harmless link ignored the five-second countdown it was offered (1.78s, all of it the page-settle every click pays). A Send button with the countdown cancelled after 0.4s was refused, the owner saw it counting, and **the page itself reported `nothing sent`** — the proof is asked of the page, not of the return value, because an action that reports failure and still sends the click is exactly the defect this feature would have. The same button left alone waited, clicked, and the page reported `SENT`. An unattended page was refused a countdown outright and sent back to the owner.
  code: offsetx_apollo_builder/browser/countdown.py, offsetx_apollo_builder/browser/page.py
  commit: e822fcc

- S-08.01.05 · Operators control delivery without hidden live sends
  tests: tests/test_email_delivery.py::test_email_delivery_api_and_public_one_click_unsubscribe, tests/test_email_delivery.py::test_live_ses_queue_requires_exact_operator_confirmation, frontend/src/components.test.tsx
  command: uv run pytest tests/test_email_delivery.py::test_email_delivery_api_and_public_one_click_unsubscribe tests/test_email_delivery.py::test_live_ses_queue_requires_exact_operator_confirmation -q && (cd frontend && npm test -- src/components.test.tsx)
  result: 2 passed + 11 passed (2026-09-11) — both halves, at last
  live: `npm ci` in frontend/ then `npm test -- src/components.test.tsx` — 1 test file, 11 tests, 1.52s. The dependency that could not be installed on 2026-08-27 installs cleanly now, so the dashboard half of this story is proven rather than argued.
  code: offsetx_apollo_builder/api/email_delivery.py, frontend/src/pages/Deliverability.tsx
  commit: d96ea9d

- S-11.01.04 · A run has a money ceiling, not only a step ceiling
  tests: tests/test_agent_money_ceiling.py::test_a_run_stops_at_the_ceiling_with_the_right_status, tests/test_agent_money_ceiling.py::test_the_decision_that_would_cross_is_never_asked_for, tests/test_agent_money_ceiling.py::test_a_resumed_run_keeps_the_ceiling_it_was_given, tests/test_agent_money_ceiling.py::test_raising_the_ceiling_on_purpose_lets_the_run_carry_on, tests/test_agent_money_ceiling.py::test_a_resumed_run_counts_what_its_earlier_life_spent, tests/test_agent_money_ceiling.py::test_the_next_decision_is_predicted_from_the_worst_so_far_not_the_average, tests/test_agent_money_ceiling.py::test_what_it_gathered_before_the_ceiling_is_kept, tests/test_agent_money_ceiling.py::test_an_unpriced_model_costs_one_decision_of_headroom_and_no_more, tests/test_agent_money_ceiling.py::test_no_ceiling_behaves_exactly_as_before, tests/test_agent_money_ceiling.py::test_the_trace_says_why_it_stopped_and_by_how_much
  command: uv run pytest tests/test_agent_money_ceiling.py tests/test_ai_cost_ledger.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_report.py tests/test_agent_wall.py tests/test_agent_watch.py tests/test_agent_progress.py tests/test_agent_recovery.py tests/test_agent_no_duplicate_effects.py -q
  result: 155 passed (2026-09-11)
  live: python scripts/live/stop_at_the_ceiling.py — real headless Chromium on a real page, decisions priced at $0.05 against a $0.20 ceiling, all four steps checked and exit 0 only if every one holds. The run made exactly four decisions and spent exactly $0.2000; the fifth was never asked for (4 model calls, not 5). Resumed with no argument it stopped again at `over_budget` after **0** model calls — the ceiling was read back off the trace. Resumed with the ceiling raised on purpose it completed with the answer, and reported $0.2500 spent across the whole run rather than $0.05 for its own part. One continuous trace: over_budget → resumed → run_continued → decision → completed.
  code: offsetx_apollo_builder/agent/run.py
  commit: b659b79

- S-06.01.03 · Cost estimated before a run and ledgered after
  tests: tests/test_ai_cost_ledger.py::test_the_daily_spend_cap_now_stops_something, tests/test_ai_cost_ledger.py::test_recording_zero_would_never_reach_the_cap, tests/test_ai_cost_ledger.py::test_every_provider_shape_is_read, tests/test_ai_cost_ledger.py::test_a_response_with_no_usage_block_reports_nothing_rather_than_zero, tests/test_ai_cost_ledger.py::test_the_provider_receipt_is_preferred_over_our_guess, tests/test_ai_cost_ledger.py::test_a_guess_is_labelled_a_guess, tests/test_ai_cost_ledger.py::test_the_model_method_and_the_function_are_the_same_arithmetic, tests/test_ai_cost_ledger.py::test_an_estimate_is_produced_before_anything_runs, tests/test_ai_cost_ledger.py::test_the_estimate_is_recorded_before_the_first_action, tests/test_ai_cost_ledger.py::test_the_trace_total_is_the_sum_of_what_each_call_reported, tests/test_ai_cost_ledger.py::test_the_outcome_carries_the_estimate_and_what_was_actually_spent
  command: uv run pytest tests/test_ai_cost_ledger.py tests/test_ai_egress_wall.py tests/test_ai_model_selection.py tests/test_ai_registry_packaging.py tests/test_outreach_providers.py tests/test_agent_report.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_watch.py tests/test_agent_wall.py tests/test_agent_provenance.py tests/test_agent_structured_result.py -q
  result: 200 passed (2026-09-11)
  live: python scripts/live/what_a_run_costs.py — a stand-in provider answering real HTTP in the Chat Completions shape, spoken to by the real `openai_compatible` adapter, through the real `measure`, into a real quota file on disk. The adapter read the reported 1842 in / 97 out; `measure` priced it at $0.004460 and labelled the source `provider` rather than `estimated`; the ledger reached the owner's $1.00 cap after 225 calls and refused the 226th with "daily spend cap reached ($1.00/$1.00)". The same script then records 10,000 calls the old way, at $0.00 each, and confirms nothing is refused — which is `D-35` as it stood before this.
  code: offsetx_apollo_builder/ai/broker.py, offsetx_apollo_builder/ai/registry.py, offsetx_apollo_builder/outreach/providers.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/agent/report.py
  commit: 97cda8f

- S-06.02.13 · A defect log and a decision log the next session can read
  tests: tests/test_verify_board.py::test_an_open_defect_that_names_no_backlog_item_fails, tests/test_verify_board.py::test_an_open_defect_naming_an_id_that_does_not_exist_fails, tests/test_verify_board.py::test_an_open_defect_naming_a_real_backlog_item_passes, tests/test_verify_board.py::test_the_same_defect_id_twice_fails, tests/test_verify_board.py::test_a_defect_that_does_not_say_what_went_wrong_fails, tests/test_verify_board.py::test_a_defect_with_no_date_found_fails, tests/test_verify_board.py::test_a_decision_with_no_cost_fails, tests/test_verify_board.py::test_a_missing_defect_log_fails_rather_than_passing_vacuously, tests/test_verify_board.py::test_a_missing_decision_log_fails_rather_than_passing_vacuously
  command: uv run pytest tests/test_verify_board.py -q
  result: 39 passed (2026-09-11)
  live: python scripts/verify_board.py --skip-tests — reports "34 defect(s) logged, 12 design decision(s) recorded" against the real repository, counted by parsing rather than read from prose. Each of the three new rules was then broken on purpose against the real files and the verifier named it: an open defect with its backlog id removed (D-25), a duplicated id (D-33), and a decision with its cost column emptied (DD-04). Restored, and green.
  code: DEFECT_LOG.md, DECISIONS.md, scripts/verify_board.py, DEFINITION_OF_DONE.md, AGENTS.md

- S-11.03.01 · A wall the agent must not climb pauses the run and asks
  tests: tests/test_agent_wall.py::test_a_sign_in_form_is_a_wall, tests/test_agent_wall.py::test_a_marketing_page_with_a_sign_in_link_is_not_a_wall, tests/test_agent_wall.py::test_a_help_article_about_two_factor_is_not_a_wall, tests/test_agent_wall.py::test_a_wall_pauses_the_run_and_spends_nothing_deciding_what_to_do, tests/test_agent_wall.py::test_the_browser_is_left_on_the_page_the_owner_has_to_deal_with, tests/test_agent_wall.py::test_the_owner_deals_with_it_and_the_run_carries_on_from_the_same_step, tests/test_agent_wall.py::test_the_pause_is_in_the_trace_without_putting_the_page_in_it, tests/test_agent_wall.py::test_nothing_in_this_module_could_solve_a_challenge
  command: uv run pytest tests/test_agent_wall.py tests/test_agent_report.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_injection.py tests/test_agent_watch.py tests/test_agent_progress.py tests/test_agent_recovery.py tests/test_agent_structured_result.py tests/test_agent_no_duplicate_effects.py tests/test_agent_provenance.py tests/test_browser_agent.py tests/test_browser_signin.py -q
  result: 221 passed (2026-09-11)
  live: python scripts/live/pause_at_a_wall.py — real headless Chromium on a real sign-in page, all four steps checked and exit 0 only if every one holds. The agent met the wall (`needs_human`, "A sign-in form is in the way (password_field)", **0** model calls, 10 of 10 budget left); the tab was still on that URL afterwards and no page text reached `trace.jsonl`; a person signed in and the tab was reloaded; `resume()` carried on from the same step to `completed` with the answer that was behind the wall. One continuous trace: run_started → needs_human → resumed → run_continued → decision → action → decision → completed. Chrome's own accessibility tree named the field "Password", so the rule is verified against a real browser rather than a fixture.
  code: offsetx_apollo_builder/agent/wall.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/agent/report.py, offsetx_apollo_builder/browser/perceive.py
  commit: 7f69c9a

- S-11.04.02 · Progress is visible while it happens
  tests: tests/test_agent_watch.py::test_a_watcher_sees_the_run_step_by_step, tests/test_agent_watch.py::test_a_read_answered_from_the_memo_still_reports_its_verb, tests/test_agent_watch.py::test_updates_arrive_during_the_run_not_in_a_batch_at_the_end, tests/test_agent_watch.py::test_an_update_carries_the_action_the_url_and_the_running_cost, tests/test_agent_watch.py::test_the_verb_comes_from_the_signature_not_from_the_prose, tests/test_agent_watch.py::test_a_listener_hears_only_what_is_already_durable, tests/test_agent_watch.py::test_a_watcher_that_throws_does_not_end_the_run, tests/test_agent_watch.py::test_a_run_with_nobody_watching_behaves_exactly_as_before
  command: uv run pytest tests/test_agent_watch.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_no_duplicate_effects.py tests/test_agent_progress.py tests/test_agent_provenance.py tests/test_agent_recovery.py tests/test_agent_report.py tests/test_browser_agent.py -q
  result: 132 passed (2026-09-11)
  live: python scripts/live/watch_a_run.py — real headless Chromium, real page served over HTTP, real trace on disk, a watcher attached through `on_progress`. Exits 0 only if the run completes AND its nine steps arrived spread over more than half a second rather than in a batch at the end; observed spread 1.6s, each line carrying its verb from the recorded signature (`action read`, `action click`), the live page URL, and the running cost climbing $0.0000 -> $0.0071. The refused step printed marked `!` the moment it happened, which is the case this story exists for. That refusal is the loopback rule in `policy.py` doing its job and was left alone — this container's egress proxy will not serve Chromium, so no public page was reachable to click instead.
  code: offsetx_apollo_builder/agent/watch.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: 7a502b0

- S-11.04.01 · A run report a person can audit
  tests: tests/test_agent_report.py::test_every_returned_fact_appears_with_its_evidence, tests/test_agent_report.py::test_a_run_that_got_stuck_says_so_at_the_top, tests/test_agent_report.py::test_a_hostile_quote_comes_back_inert, tests/test_agent_report.py::test_a_screenshot_filename_that_tries_to_leave_the_directory_is_dropped, tests/test_agent_report.py::test_a_finished_run_writes_its_own_report
  command: uv run pytest tests/test_agent_report.py tests/test_agent_run.py tests/test_agent_injection.py tests/test_agent_resume.py tests/test_agent_structured_result.py -q
  result: 82 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/report.py, offsetx_apollo_builder/agent/run.py
  commit: cd25d9d

- S-11.03.02 · A page that tries to give orders is reported, not obeyed
  tests: tests/test_agent_injection.py::test_an_attack_in_the_page_text_is_flagged_in_the_trace, tests/test_agent_injection.py::test_the_run_carries_on_under_the_owners_goal, tests/test_agent_injection.py::test_ordinary_page_text_is_left_alone, tests/test_agent_injection.py::test_an_attack_split_across_lines_is_still_caught, tests/test_agent_injection.py::test_the_quote_stays_out_of_the_audit_log
  command: uv run pytest tests/test_agent_injection.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_no_duplicate_effects.py tests/test_agent_progress.py -q
  result: 81 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/injection.py, offsetx_apollo_builder/agent/run.py
  commit: 2f5c19e

- S-11.05.02 · Re-running does not duplicate what it already did
  tests: tests/test_agent_no_duplicate_effects.py::test_a_resumed_run_does_not_send_the_message_twice, tests/test_agent_no_duplicate_effects.py::test_pressing_enter_again_after_a_resume_does_not_submit_twice, tests/test_agent_no_duplicate_effects.py::test_navigating_back_to_where_it_was_still_works, tests/test_agent_no_duplicate_effects.py::test_within_one_run_the_guard_does_not_fire
  command: uv run pytest tests/test_agent_no_duplicate_effects.py tests/test_agent_resume.py tests/test_agent_run.py tests/test_agent_provenance.py tests/test_agent_progress.py tests/test_agent_recovery.py -q
  result: 59 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py
  commit: 1e1bd0d

- S-11.01.03 · A run survives the process dying
  tests: tests/test_agent_resume.py::test_a_resumed_run_keeps_the_facts_it_already_gathered, tests/test_agent_resume.py::test_resuming_continues_the_same_trace_and_marks_where, tests/test_agent_resume.py::test_a_finished_run_is_not_resumed, tests/test_agent_resume.py::test_a_fact_whose_artefact_is_gone_is_dropped_not_invented
  command: uv run pytest tests/test_agent_resume.py tests/test_agent_provenance.py tests/test_agent_run.py tests/test_agent_structured_result.py tests/test_agent_progress.py tests/test_agent_recovery.py -q
  result: 56 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/agent/result.py
  commit: 8e759b9

- S-11.01.02 · A run that stops making progress is stopped
  tests: tests/test_agent_progress.py::test_filling_a_long_form_is_never_called_stalled, tests/test_agent_progress.py::test_a_search_and_browse_pattern_is_never_called_looping, tests/test_agent_progress.py::test_bouncing_between_two_pages_is_looping, tests/test_agent_progress.py::test_clicking_the_same_working_button_forever_is_stalled, tests/test_agent_progress.py::test_a_real_run_going_nowhere_is_stopped
  command: uv run pytest tests/test_agent_progress.py tests/test_agent_recovery.py tests/test_agent_run.py tests/test_agent_page_memo.py tests/test_agent_structured_result.py -q
  result: 51 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py
  commit: 1b3c519

- S-11.01.01 · A failed action is recovered from, not repeated
  tests: tests/test_agent_recovery.py::test_the_same_failing_action_reaches_the_browser_only_once, tests/test_agent_recovery.py::test_three_failures_in_a_row_stop_the_run, tests/test_agent_recovery.py::test_a_timeout_is_retried_with_backoff_and_recorded_as_a_retry, tests/test_agent_recovery.py::test_a_success_clears_the_failure_streak
  command: uv run pytest tests/test_agent_recovery.py tests/test_agent_run.py tests/test_agent_page_memo.py tests/test_agent_structured_result.py -q
  result: 37 passed (2026-09-09)
  code: offsetx_apollo_builder/agent/run.py
  commit: ce3a994

- S-11.02.04 · The same page is never read twice in one run
  tests: tests/test_agent_page_memo.py::test_reading_the_same_page_twice_asks_the_page_once, tests/test_agent_page_memo.py::test_acting_on_a_page_forgets_it, tests/test_agent_page_memo.py::test_a_parameter_that_changes_the_page_is_never_stripped, tests/test_agent_page_memo.py::test_a_real_page_is_read_once_through_the_real_loop
  command: uv run pytest tests/test_agent_page_memo.py tests/test_agent_run.py tests/test_agent_structured_result.py -q
  result: 25 passed (2026-09-09)
  code: offsetx_apollo_builder/agent/run.py
  commit: 4acf68e

- S-11.02.03 · A claim the page does not support is refused
  tests: tests/test_agent_claim_verification.py::test_number_inside_a_larger_number_is_refused_even_at_high_confidence, tests/test_agent_claim_verification.py::test_derived_finding_is_allowed_only_from_individually_verified_inputs, tests/test_agent_claim_verification.py::test_missing_support_in_a_truncated_capture_is_reported_as_inconclusive, tests/test_agent_claim_verification.py::test_real_chromium_page_refuses_a_plausible_but_unsupported_number
  command: uv run pytest tests/test_agent_claim_verification.py -q
  result: 8 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/verify.py, offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py
  commit: ebd2556add2251e6663e24f6b7f66f0aa1b017f2

- S-11.02.02 · Every fact carries where it came from
  tests: tests/test_agent_provenance.py::test_returned_finding_resolves_url_time_step_and_screenshot_from_trace, tests/test_agent_provenance.py::test_an_unresolvable_source_is_refused_instead_of_returned, tests/test_agent_provenance.py::test_a_sourced_fact_survives_navigation_without_relying_on_model_memory, tests/test_agent_provenance.py::test_provenance_is_bound_to_real_chromium_evidence
  command: uv run pytest tests/test_agent_provenance.py -q
  result: 6 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: 1374d7e18a0028a40005192528bd5ed6902fe6e4

- S-11.02.01 · A run declares the shape of its answer and is held to it
  tests: tests/test_agent_structured_result.py::test_declared_schema_returns_a_valid_record_not_prose, tests/test_agent_structured_result.py::test_missing_required_field_makes_the_run_incomplete_and_names_it, tests/test_agent_structured_result.py::test_model_field_outside_schema_is_dropped_and_the_drop_is_recorded, tests/test_agent_structured_result.py::test_no_schema_keeps_the_existing_free_text_result_contract, tests/test_agent_structured_result.py::test_structured_result_flows_through_the_real_browser_loop
  command: uv run pytest tests/test_agent_structured_result.py -q
  result: 7 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py
  commit: 4ffef3de8cd2f5e681e4d49d39cb6ae154e02dc0

- S-02.02.01 · A goal becomes a bounded sequence of actions
  tests: tests/test_agent_run.py::test_goal_stops_at_step_budget_and_reports_progress, tests/test_agent_run.py::test_every_decision_uses_broker_and_trace_records_provider_model_and_cost
  command: uv run pytest tests/test_agent_run.py -q
  result: 7 passed (2026-09-05)
  code: offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: 08eb2cd46e24f791a44a4aceca4f1e6272f803b0

- S-03.02.03 · Revoke and forget
  tests: tests/test_browser_revoke.py::test_disconnect_destroys_vault_clears_browser_forgets_record_and_traces, tests/test_browser_revoke.py::test_browser_failure_retains_encrypted_vault_and_connected_record_for_retry, tests/test_browser_revoke.py::test_real_browser_session_cookie_is_gone_after_disconnect
  command: uv run pytest tests/test_browser_revoke.py -q
  result: 6 passed (2026-09-04)
  code: offsetx_apollo_builder/browser/revoke.py, offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/trace.py
  commit: 5090be48801b2a776d89e5a05da7de3204a559aa

- S-03.02.02 · A vault the model cannot read
  tests: tests/test_browser_vault.py::test_cookie_token_and_password_fields_are_blocked_even_at_full_policy, tests/test_browser_vault.py::test_two_platforms_use_different_account_keys_and_plaintext_is_absent, tests/test_browser_vault.py::test_passphrase_derives_master_key_and_no_raw_key_file_is_written, tests/test_browser_vault_wiring.py::test_connected_state_is_vaulted_before_it_is_recorded, tests/test_browser_vault_wiring.py::test_vault_failure_refuses_the_connection_and_writes_no_green_state
  command: uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py -q
  result: 15 passed (2026-09-04)
  code: offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/ai/scanner.py
  commit: 008d4928ae8048d85a804b628d9e76f0ee1c8c77

- S-01.01.01 · A timeline that cannot represent an invalid edit
  tests: tests/test_video_timeline.py
  command: uv run pytest tests/test_video_timeline.py -q
  result: 49 passed (2026-08-25)
  code: offsetx_apollo_builder/video/timeline.py
  commit: d96ea9d

- S-01.01.02 · Two resolvers held to one answer by a fixture
  tests: tests/test_video_mixdown.py
  command: uv run pytest tests/test_video_mixdown.py -q
  result: 29 passed (2026-08-25)
  code: tests/fixtures/timeline_conformance.json
  commit: d96ea9d

- S-01.02.01 · Video, audio and footage in one exported file
  tests: tests/test_video_engine.py
  command: uv run pytest tests/test_video_engine.py -q
  result: 46 passed (2026-08-25)
  code: offsetx_apollo_builder/video/mixdown.py
  commit: d96ea9d

- S-01.02.02 · Time remapping as one integral
  tests: tests/test_video_retime.py
  command: uv run pytest tests/test_video_retime.py -q
  result: 34 passed (2026-08-25)
  code: offsetx_apollo_builder/video/presets.py
  commit: d96ea9d

- S-01.02.03 · 48 pixel primitives and a catalogue of looks
  tests: tests/test_video_effects.py
  command: uv run pytest tests/test_video_effects.py -q
  result: 49 passed (2026-08-25)
  code: offsetx_apollo_builder/video/effects.py
  commit: d96ea9d

- S-01.03.01 · Material in, finished timeline out
  tests: tests/test_video_assembly.py
  command: uv run pytest tests/test_video_assembly.py -q
  result: 94 passed (2026-08-25)
  code: offsetx_apollo_builder/video/assembly.py
  commit: d96ea9d

- S-01.03.02 · A topic in, a finished project out
  tests: tests/test_video_director.py
  command: uv run pytest tests/test_video_director.py -q
  result: 31 passed (2026-08-25)
  code: offsetx_apollo_builder/video/director.py
  commit: d96ea9d

- S-01.04.01 · Push, ignore, edit
  tests: tests/test_video_review.py
  command: uv run pytest tests/test_video_review.py -q
  result: 37 passed (2026-08-25)
  code: offsetx_apollo_builder/video/engine.py
  commit: d96ea9d

- S-01.04.02 · The owner's posting cap, and advice about the rate
  tests: tests/test_pacing_cap.py
  command: uv run pytest tests/test_pacing_cap.py -q
  result: 19 passed (2026-08-25)
  code: offsetx_apollo_builder/distribution/pacing.py
  commit: d96ea9d

- S-02.01.01 · A hand-written DevTools client
  tests: tests/test_browser_agent.py::test_a_command_the_browser_does_not_know_raises_rather_than_hangs
  command: uv run pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/cdp.py
  commit: d96ea9d

- S-02.01.02 · The page as an accessibility outline with stable handles
  tests: tests/test_browser_agent.py::test_a_snapshot_reads_in_document_order_and_not_cdps_order
  command: uv run pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/perceive.py
  commit: d96ea9d

- S-02.01.03 · Ten verbs, real input, no arbitrary code
  tests: tests/test_browser_agent.py::test_the_vocabulary_is_ten_verbs_and_none_of_them_runs_code
  command: uv run pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/page.py
  commit: d96ea9d

- S-02.01.04 · Per-domain policy, enforced in code
  tests: tests/test_browser_agent.py::test_the_machine_itself_is_never_reachable
  command: uv run pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/policy.py
  commit: d96ea9d

- S-02.01.05 · An append-only work trace
  tests: tests/test_browser_agent.py::test_a_trace_is_append_only_with_no_way_to_remove_a_step
  command: uv run pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/trace.py
  commit: d96ea9d

- S-03.01.01 · A browser box: network yes, host filesystem never
  tests: tests/test_browser_box.py::test_the_only_mount_is_a_docker_volume_and_not_a_path_on_your_disk, tests/test_browser_box.py::test_a_real_browser_cannot_reach_an_off_list_domain
  command: uv run pytest tests/test_browser_box.py -q
  result: 30 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/box.py, offsetx_apollo_builder/browser/guard.py
  commit: 91c7cb2

- S-03.02.04 · Several accounts per platform, each with its own budget
  tests: tests/test_browser_budget.py::test_spending_one_account_does_not_spend_the_other, tests/test_browser_budget.py::test_real_browser_stops_when_the_account_is_spent, tests/test_browser_budget.py::test_looking_costs_nothing_and_acting_costs_one, tests/test_browser_budget.py::test_a_record_written_before_accounts_existed_still_reads
  command: uv run pytest tests/test_browser_budget.py tests/test_browser_agent.py tests/test_browser_signin.py -q
  result: 81 passed (2026-09-06)
  code: offsetx_apollo_builder/browser/budget.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/page.py, offsetx_apollo_builder/browser/signin.py
  commit: fd5ad0b

- S-06.02.09 · Every database write goes through one guard
  tests: tests/test_security_audit.py::test_a_bare_write_is_not_rolled_back_by_someone_else_s_failure, tests/test_security_audit.py::test_a_bare_write_is_not_committed_early_by_someone_else, tests/test_security_audit.py::test_no_shared_connection_escapes_the_guard, tests/test_security_audit.py::test_the_guard_still_behaves_like_a_connection
  command: uv run pytest tests/test_security_audit.py tests/test_outreach_api.py tests/test_sales_tracker.py tests/test_email_delivery.py -q
  result: 53 passed (2026-09-09)
  code: offsetx_apollo_builder/outreach/store.py
  commit: 4acf68e

- S-06.02.10 · The local API is not open to whatever can reach the port
  tests: tests/test_security_audit.py::test_a_local_install_will_not_start_without_authentication, tests/test_security_audit.py::test_loopback_requires_the_token_like_everywhere_else, tests/test_security_audit.py::test_a_host_this_server_does_not_answer_to_is_refused, tests/test_security_audit.py::test_a_provisioned_token_is_strong_stable_and_private
  command: uv run pytest tests/test_security_audit.py tests/test_api_auth.py tests/test_outreach_api.py -q
  result: 33 passed (2026-09-08)
  code: offsetx_apollo_builder/api/config.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/web_cli.py
  commit: e4f91a4

- S-03.02.01 · Sign in to a platform once, inside the box
  tests: tests/test_browser_signin.py::test_the_whole_flow_and_the_password_is_nowhere_afterwards, tests/test_browser_signin.py::test_a_session_survives_the_browser_being_restarted, tests/test_browser_signin.py::test_no_function_in_the_sign_in_path_accepts_a_credential, tests/test_browser_agent.py::test_a_lock_left_behind_by_a_browser_that_died_is_not_a_lock, tests/test_browser_agent.py::test_a_handle_from_before_the_page_changed_is_refused
  command: uv run pytest tests/test_browser_signin.py tests/test_browser_agent.py tests/test_browser_box.py -q
  result: 87 passed (2026-08-28)
  code: offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/browser/session.py, offsetx_apollo_builder/browser/page.py
  commit: 9bd1ee7

- S-03.01.02 · The existing code box keeps its no-network guarantee
  tests: tests/test_browser_box.py::test_the_box_asks_for_the_network_and_the_code_box_still_cannot_have_it, tests/test_browser_box.py::test_host_networking_cannot_be_asked_for_at_all
  command: uv run pytest tests/test_ai_sandbox.py tests/test_browser_box.py -q
  result: 72 passed, 1 skipped (2026-08-25)
  code: offsetx_apollo_builder/ai/sandbox.py
  commit: 91c7cb2

- S-06.02.07 · An answered question stops blocking
  tests: tests/test_verify_board.py::test_an_answered_question_stops_blocking_ready
  command: uv run pytest tests/test_verify_board.py -q
  result: 29 passed (2026-08-25)
  code: scripts/verify_board.py
  commit: 8b6876e

- S-06.02.06 · The delivery process is verifiable by the owner
  tests: tests/test_verify_board.py
  command: uv run pytest tests/test_verify_board.py -q
  result: 29 passed (2026-08-25)
  code: scripts/verify_board.py
  commit: d96ea9d

*Retrospective certification, 2026-08-27: the protected email implementation
arrived in `d96ea9d` before it had backlog IDs. The entries below certify the
current code and rerun evidence; they do not claim the earlier build followed
the pull-before-code process.*

- S-08.01.01 · Permission and suppression fail closed
  tests: tests/test_email_delivery.py::test_permission_marketing_fails_closed_and_suppression_is_global, tests/test_email_delivery.py::test_direct_sender_checks_global_suppression_before_provider_call, tests/test_email_delivery.py::test_transactional_lane_requires_relationship_basis_not_marketing_consent
  command: uv run pytest tests/test_email_delivery.py::test_permission_marketing_fails_closed_and_suppression_is_global tests/test_email_delivery.py::test_direct_sender_checks_global_suppression_before_provider_call tests/test_email_delivery.py::test_transactional_lane_requires_relationship_basis_not_marketing_consent -q
  result: 3 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/preflight.py, offsetx_apollo_builder/outreach/deliverability/store.py
  commit: d96ea9d

- S-08.01.02 · Durable jobs survive crashes without duplicate sends
  tests: tests/test_email_delivery.py::test_durable_local_job_is_snapshotted_claimed_once_and_recorded, tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried, tests/test_email_delivery.py::test_stale_claim_without_a_recorded_message_becomes_delivery_unknown, tests/test_email_delivery.py::test_job_cancellation_is_terminal_and_only_allowed_before_claim, tests/test_email_delivery.py::test_reply_cancels_an_already_queued_email_before_delivery, tests/test_email_delivery.py::test_worker_defers_outside_send_window_without_spending_a_provider_attempt
  command: uv run pytest tests/test_email_delivery.py::test_durable_local_job_is_snapshotted_claimed_once_and_recorded tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried tests/test_email_delivery.py::test_stale_claim_without_a_recorded_message_becomes_delivery_unknown tests/test_email_delivery.py::test_job_cancellation_is_terminal_and_only_allowed_before_claim tests/test_email_delivery.py::test_reply_cancels_an_already_queued_email_before_delivery tests/test_email_delivery.py::test_worker_defers_outside_send_window_without_spending_a_provider_attempt -q
  result: 6 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/service.py, offsetx_apollo_builder/outreach/deliverability/store.py
  commit: d96ea9d

- S-08.01.03 · Authenticated SES lanes carry bulk mail
  tests: tests/test_email_delivery.py::test_domain_auth_uses_dns_and_ses_identity_evidence, tests/test_email_delivery.py::test_ses_provider_builds_raw_mime_with_one_click_headers
  command: uv run pytest tests/test_email_delivery.py::test_domain_auth_uses_dns_and_ses_identity_evidence tests/test_email_delivery.py::test_ses_provider_builds_raw_mime_with_one_click_headers -q
  result: 2 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/domain_auth.py, offsetx_apollo_builder/outreach/deliverability/ses.py
  commit: d96ea9d

- S-08.01.04 · Provider feedback stops unhealthy sending
  tests: tests/test_email_delivery.py::test_ses_feedback_is_idempotent_suppresses_and_auto_pauses, tests/test_email_delivery.py::test_sns_envelope_signature_is_verified_before_parsing, tests/test_email_delivery.py::test_public_feedback_paths_bypass_login_but_still_verify_their_tokens
  command: uv run pytest tests/test_email_delivery.py::test_ses_feedback_is_idempotent_suppresses_and_auto_pauses tests/test_email_delivery.py::test_sns_envelope_signature_is_verified_before_parsing tests/test_email_delivery.py::test_public_feedback_paths_bypass_login_but_still_verify_their_tokens -q
  result: 3 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/events.py, offsetx_apollo_builder/outreach/deliverability/service.py
  commit: d96ea9d

## DEFERRED

*(Nothing is deferred. S-03.01.02's trigger fired when S-03.01.01 was pulled.)*
