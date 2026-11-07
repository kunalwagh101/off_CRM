# Remaining work and next five features — 2026-11-07

Recomputed from BOARD.md on develop after reviewed import/recall follow-through; exact executable CI is distinguished below. This updates the historical November6 audit; it does not rewrite that snapshot. Implemented, IN_REVIEW and DONE are distinct. Open entries include existing code awaiting acceptance, not only missing code.

**172 tracked delivery entries: 72 DONE and 100 open.** Open: 81 stories plus 19 directly tracked feature entries. They span31 feature areas using story-ID prefixes plus direct feature entries. Do not add rollups and stories as separate work estimates.

| State | Entries |
|---|---:|
| DONE | 72 |
| IN_REVIEW | 74 |
| IN_PROGRESS | 1 |
| BACKLOG | 21 |
| BLOCKED | 4 |
| READY | 0 |
| DEFERRED | 0 |

There is no complete independently stateful task ledger. A truthful grand total of pending subtasks cannot be certified. The task breakdown below names the remaining implementation/acceptance work; each story retains its backlog criteria and work order. No completion percentage or invented time estimate is supplied.

## Delivery order

The first three areas below are the owner-authorized delivery scope; the next two are queued. CRM tenancy is a necessary privacy dependency of that scope, so its work is proceeding before claiming customer isolation. The first three contain58 open stories; all five contain65. These counts describe scope, not58 absent implementations.

## 1. F-06.02 — Production reliability and security

**49 open stories.**

| Story | State | Remaining story | Work order |
|---|---|---|---|
| S-06.02.01 | IN_REVIEW | No secret may enter a model prompt | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.02 | IN_REVIEW | Every endpoint authorises and validates | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.04 | IN_REVIEW | Data deletion and subject access | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.05 | IN_REVIEW | The UI is usable by keyboard and screen reader | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.16 | IN_REVIEW | Resolve frontend development dependency audit findings | [S-06.02.16-frontend-dependency-audit.md](../../docs/work-orders/S-06.02.16-frontend-dependency-audit.md) |
| S-06.02.19 | BLOCKED | One working branch holds everything built, and it is green | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.20 | IN_REVIEW | The verifier tells a shallow clone apart from a missing commit | [S-06.02.20-shallow-git-history.md](../../docs/work-orders/S-06.02.20-shallow-git-history.md) |
| S-06.02.21 | IN_REVIEW | Durable customer state and safe recovery (audit WP1) | [S-06.02.21-S-06.02.22-close-out.md](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md) |
| S-06.02.22 | IN_REVIEW | A created or selected campaign stays the active workspace | [S-06.02.21-S-06.02.22-close-out.md](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md) |
| S-06.02.23 | IN_PROGRESS | Re-check the 7 September production audit on `develop` | [S-06.02.23-audit-recheck.md](../../docs/work-orders/S-06.02.23-audit-recheck.md) |
| S-06.02.25 | IN_REVIEW | Every screen opens at its top, its warnings in view | [S-06.02.25-screen-opens-at-top.md](../../docs/work-orders/S-06.02.25-screen-opens-at-top.md) |
| S-06.02.27 | BACKLOG | The audit's live harness runs against `develop` | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.02.28 | IN_REVIEW | A command-line tool locks the workspace it actually opens | [S-06.02.28-path-aware-workspace-lock.md](../../docs/work-orders/S-06.02.28-path-aware-workspace-lock.md) |
| S-06.02.34 | IN_REVIEW | Connectors show how much is left | [S-06.02.34-usage-remaining.md](../../docs/work-orders/S-06.02.34-usage-remaining.md) |
| S-06.02.35 | BACKLOG | Drafts reach a model the owner set up on a screen | [S-06.02.35-drafts-connectors.md](../../docs/work-orders/S-06.02.35-drafts-connectors.md) |
| S-06.02.36 | IN_REVIEW | A second owner login is made on purpose | [S-06.02.36-explicit-owner-login.md](../../docs/work-orders/S-06.02.36-explicit-owner-login.md) |
| S-06.02.37 | IN_REVIEW | Skip navigation keeps the current screen | [S-06.02.37-skip-keeps-current-page.md](../../docs/work-orders/S-06.02.37-skip-keeps-current-page.md) |
| S-06.02.38 | IN_REVIEW | Any error can be traced back the next day | [S-06.02.38-traceable-errors.md](../../docs/work-orders/S-06.02.38-traceable-errors.md) |
| S-06.02.39 | IN_REVIEW | Valid low-bitrate WebM exports pass verification | [S-06.02.39-low-bitrate-export.md](../../docs/work-orders/S-06.02.39-low-bitrate-export.md) |
| S-06.02.40 | BACKLOG | A durable email worker runs beside the deployed web app | [S-06.02.40-durable-deployment-worker.md](../../docs/work-orders/S-06.02.40-durable-deployment-worker.md) |
| S-06.02.41 | IN_REVIEW | Contacts beyond row 500 are reachable | [S-06.02.41-contacts-pagination.md](../../docs/work-orders/S-06.02.41-contacts-pagination.md) |
| S-06.02.42 | IN_REVIEW | Enrichment exports cannot run spreadsheet formulas | [S-06.02.42-spreadsheet-formulas.md](../../docs/work-orders/S-06.02.42-spreadsheet-formulas.md) |
| S-06.02.43 | IN_REVIEW | Logout revokes the copied browser session | [S-06.02.43-logout-revocation.md](../../docs/work-orders/S-06.02.43-logout-revocation.md) |
| S-06.02.44 | IN_REVIEW | Download all filtered Contacts rows | [S-06.02.44-filtered-contact-download.md](../../docs/work-orders/S-06.02.44-filtered-contact-download.md) |
| S-06.02.45 | IN_REVIEW | Category and variant filters for contacts | [S-06.02.45-contact-facet-filters.md](../../docs/work-orders/S-06.02.45-contact-facet-filters.md) |
| S-06.02.46 | IN_REVIEW | Marked-only contacts remain reachable | [S-06.02.46-marked-only-contacts.md](../../docs/work-orders/S-06.02.46-marked-only-contacts.md) |
| S-06.02.47 | IN_REVIEW | Large send queues are paginated | [S-06.02.47-queue-pagination.md](../../docs/work-orders/S-06.02.47-queue-pagination.md) |
| S-06.02.48 | IN_REVIEW | Campaign-wide queue counters do not mislead | [S-06.02.48-global-queue-totals.md](../../docs/work-orders/S-06.02.48-global-queue-totals.md) |
| S-06.02.49 | IN_REVIEW | Queue views focus on actionable cohorts | [S-06.02.49-actionable-queue-views.md](../../docs/work-orders/S-06.02.49-actionable-queue-views.md) |
| S-06.02.50 | IN_REVIEW | Video media and renders obey configured upload limits (A15 partial remediation) | [S-06.02.50-bounded-video-uploads.md](../../docs/work-orders/S-06.02.50-bounded-video-uploads.md) |
| S-06.02.51 | IN_REVIEW | Video uploads have a bounded request stream and concurrency gate (A15) | [S-06.02.51-video-upload-stream-guard.md](../../docs/work-orders/S-06.02.51-video-upload-stream-guard.md) |
| S-06.02.52 | IN_REVIEW | Owner sees operational scheduler health separate from web readiness | [S-06.02.52-operational-health.md](../../docs/work-orders/S-06.02.52-operational-health.md) |
| S-06.02.53 | IN_REVIEW | Public visitor demo has its own visible login and isolated sample data | [S-06.02.53-public-visitor-demo.md](../../docs/work-orders/S-06.02.53-public-visitor-demo.md) |
| S-06.02.54 | IN_REVIEW | Restore actual AI and orchestration in the visitor demo | [S-06.02.54-restore-visitor-ai.md](../../docs/work-orders/S-06.02.54-restore-visitor-ai.md) |
| S-06.02.55 | IN_REVIEW | Verify numeric claims without changing sign, precision or magnitude (A18) | [S-06.02.55-numeric-claim-integrity.md](../../docs/work-orders/S-06.02.55-numeric-claim-integrity.md) |
| S-06.02.56 | IN_REVIEW | Reject corrupt image payloads safely (A21) | [S-06.02.56-complete-image-decoding.md](../../docs/work-orders/S-06.02.56-complete-image-decoding.md) |
| S-06.02.57 | IN_REVIEW | A09: Enter handlers cannot bypass human approval | [S-06.02.57-enter-approval.md](../../docs/work-orders/S-06.02.57-enter-approval.md) |
| S-06.02.58 | IN_REVIEW | Factual AI cache only reuses exact evidence (A12) | [S-06.02.58-exact-factual-cache.md](../../docs/work-orders/S-06.02.58-exact-factual-cache.md) |
| S-06.02.59 | IN_REVIEW | Cached AI outputs are scoped to the actual model and instructions (A13) | [S-06.02.59-cache-model-provenance.md](../../docs/work-orders/S-06.02.59-cache-model-provenance.md) |
| S-06.02.60 | BACKLOG | AI request and spending caps reserve atomically across workers (A11) | [S-06.02.60-atomic-ai-quota.md](../../docs/work-orders/S-06.02.60-atomic-ai-quota.md) |
| S-06.02.61 | BACKLOG | Email provider setup failures do not strand delivery jobs (A16) | [S-06.02.61-email-provider-setup.md](../../docs/work-orders/S-06.02.61-email-provider-setup.md) |
| S-06.02.62 | BACKLOG | HTTP idempotency safely prevents duplicate state-changing requests (A14) | [S-06.02.62-atomic-http-idempotency.md](../../docs/work-orders/S-06.02.62-atomic-http-idempotency.md) |
| S-06.02.63 | IN_REVIEW | Token-authenticated media works in review and video export (A20) | [S-06.02.63-token-media-auth.md](../../docs/work-orders/S-06.02.63-token-media-auth.md) |
| S-06.02.64 | IN_REVIEW | Restricted sandbox can write outputs without exposing host files (A32) | [S-06.02.64-sandbox-writable-workspace.md](../../docs/work-orders/S-06.02.64-sandbox-writable-workspace.md) |
| S-06.02.65 | IN_REVIEW | Reject malformed nested video edits without partial writes (A22) | [S-06.02.65-video-edit-input.md](../../docs/work-orders/S-06.02.65-video-edit-input.md) |
| S-06.02.66 | BACKLOG | Paid AI calls cannot silently count as free when usage receipts are invalid (A10) | [S-06.02.66-ai-billing-receipt-integrity.md](../../docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md) |
| S-06.02.67 | BACKLOG | Only install owners may access personal-data inventory and erasure (A24/A05) | [S-06.02.67-privacy-owner-authorization.md](../../docs/work-orders/S-06.02.67-privacy-owner-authorization.md) |
| S-06.02.68 | BACKLOG | Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05) | [S-06.02.68-video-workspace-ownership.md](../../docs/work-orders/S-06.02.68-video-workspace-ownership.md) |
| S-06.02.69 | BACKLOG | Image briefs, generated files and video handoff remain private to their workspace (A05) | [S-06.02.69-image-workspace-ownership.md](../../docs/work-orders/S-06.02.69-image-workspace-ownership.md) |

**Sub-features, tasks and QA to finish:**

1. Finish S-06.02.23 against current develop: reproduce each audit case and trace every entrypoint rather than treating a green suite as production acceptance.
2. Complete Drafts through Connectors, scoped context/memory, provider policy, safe errors and recorded usage. The connector/UI adapter and memory leak fixes exist; actual configured-provider acceptance remains.
3. Close access/privacy/media ownership, atomic quota and HTTP idempotency, corrupt upload/cache/billing handling, durable error references, keyboard/accessibility and the durable worker.
4. Run full supported Python/SQLite/PostgreSQL/frontend/container suites, actual app/browser scenarios, independent targeted security/penetration tests, restart/crash/restore and uncertain external-action checks.
5. CI runner availability and full Python matrix stories S-06.02.18/.26 are DONE with real run evidence. Do not recode or count them as remaining.

## 2. F-06.03 — Durable storage and recovery

**5 open stories.**

| Story | State | Remaining story | Work order |
|---|---|---|---|
| S-06.03.04 | BACKLOG | The hosted database is backed up outside itself | [S-06.03.04-hosted-backup-and-restore.md](../../docs/work-orders/S-06.03.04-hosted-backup-and-restore.md) |
| S-06.03.05 | BACKLOG | Production refuses a half-hosted install | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.03.06 | BACKLOG | Every other store has a decided home | [S-06.03.06-store-homes.md](../../docs/work-orders/S-06.03.06-store-homes.md) |
| S-06.03.07 | IN_REVIEW | A local install's decision belongs to that install | [S-06.03.07-single-install-database.md](../../docs/work-orders/S-06.03.07-single-install-database.md) |
| S-06.03.08 | IN_REVIEW | Install owner sees actual storage durability and production blockers | [S-06.03.08-storage-readiness-report.md](../../docs/work-orders/S-06.03.08-storage-readiness-report.md) |

**Sub-features, tasks and QA to finish:**

1. .04: finish real private offsite bucket/IAM, independent recovery-key custody, retention, scheduling and a separate empty-database recovery drill. Encrypted pg_dump/restore is implemented/tested; FakeS3 is not a live offsite proof.
2. .05: retain startup refusal for partial hosted layouts; prove every supported SQL/file home and recovery path before permitting production.
3. .06: tool pins/run receipts and companion grants now have tested hosted SQL wiring, staged archive migration/inverse and real sandbox/recovery checks. Finish recall, privacy artifacts and remaining crawler/integration/media/outbox/trace files, plus active-run crash/cancellation reconciliation. Existing metadata cutovers retain archive/reconcile/rollback and explicit stale-work reactivation.
4. .07: preserve one independent install per database; stable install UUID enforcement exists. Complete all CLI/runtime decision and recovery paths; never transfer a foreign install claim automatically.
5. .08: owner diagnostics must reflect actual homes and file limitations; preserve the mixed-routine trace-file readiness fix.
6. QA: real SQL clients, tamper/wrong-key/partial failures, source/target/archive identity refusal, concurrency, reconnect, exact counts/data/template state, cross-install denial and full-root/multi-schema restore.

## 3. F-04.01 — Agent team

**4 open stories.**

| Story | State | Remaining story | Work order |
|---|---|---|---|
| S-04.01.01 | IN_REVIEW | Companions: persisted agent profiles | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-04.01.02 | BACKLOG | Skills: procedures fetched on demand | [S-04.01.02-on-demand-agent-skills.md](../../docs/work-orders/S-04.01.02-on-demand-agent-skills.md) |
| S-04.01.03 | BACKLOG | Sub-agents for context isolation | [S-04.01.03-bounded-child-reasoning.md](../../docs/work-orders/S-04.01.03-bounded-child-reasoning.md) |
| S-04.01.04 | BACKLOG | The five roles, wired to what already exists | [S-04.01.04-five-role-integration.md](../../docs/work-orders/S-04.01.04-five-role-integration.md) |

**Sub-features, tasks and QA to finish:**

1. .01: finish persisted profile/tool-grant acceptance across restart, import and workspace boundaries; retain hostile-grant fail-closed tests.
2. .02: finish explicit skill CRUD/enable/disable/delete/context and missing/foreign/disabled cases. UI/API implementation exists; full governed acceptance remains.
3. .03: prove one-level bounded child delegation, one-to-three children, explicit context, cancellation/spend limits, safe partial failure and parent synthesis without unintended transcript/tool disclosure.
4. .04: finish Scout/Maker/Poster/Analyst/Director integration with the existing engines and human review queues; actual role forms/browser checks exist, configured provider/platform acceptance remains.
5. QA: desktop/mobile/keyboard flows, scoped memory and tool grants, actual persistence/recovery, errors/audit, budgets and no unapproved publish/send. Test doubles do not establish live provider or platform acceptance.

## 4. F-06.01 — Team permissions and operations

**5 open stories.**

| Story | State | Remaining story | Work order |
|---|---|---|---|
| S-06.01.01 | IN_REVIEW | Workspaces with their own keys and their own logins | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.01.02 | IN_REVIEW | Owner sets global, per-tool and chat-lifetime browser permissions | [S-06.01.02-three-level-agent-permissions.md](../../docs/work-orders/S-06.01.02-three-level-agent-permissions.md) |
| S-06.01.04 | IN_REVIEW | Routines that fire agent runs on a schedule or an event | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.01.05 | BACKLOG | Deployment, monitoring and rollback | Not linked on board; inspect backlog and complete decomposition before pulling |
| S-06.01.06 | BACKLOG | Campaigns, contacts and drafts belong to a workspace | [S-06.01.06-crm-tenancy.md](../../docs/work-orders/S-06.01.06-crm-tenancy.md) |

**Sub-features, tasks and QA to finish:**

1. .01/.02: finish login/key isolation, permission precedence and revocation across global/per-tool/chat settings; actual watch/cancel and concurrent-session denial.
2. .04: finish owner-scoped schedules, duplicate-worker claims, bounded execution, explicit enabled-routine import and cancellation/restart paths.
3. .05: finish durable deployment, health/monitoring, secret-safe diagnostics and tested restart/release rollback.
4. .06: Q-27 is answered. Preserve existing recorded owners, require a complete explicit legacy manifest, archive/reconcile/atomic cutover and guarded inverse; never assign legacy customers to local automatically.
5. .06: native namespace and leased registry components now exist with direct PostgreSQL, real prior pooler and encrypted recovery proofs. Finish all authenticated app/service/CLI/worker/recall/privacy factories, shared reputation/rate controls and restore draining before runtime activation.
6. QA: alpha/beta/local same-email and guessed-ID matrix across every list/count/search/export/bulk/raw-SQL path; concurrent claims, sender-scoped unsubscribe, install-wide reputation privacy, crash/cutover/retry/inverse and actual browser/security review.

## 5. F-12.02 — GTM strategy brain

**2 open stories.**

| Story | State | Remaining story | Work order |
|---|---|---|---|
| S-12.02.05 | IN_REVIEW | The brain drafts against the expert corpus and the owner's winners | [S-12.02.05-plans-with-expert-references.md](../../docs/work-orders/S-12.02.05-plans-with-expert-references.md) |
| S-12.02.06 | IN_REVIEW | A plan's posting channel runs from the screens | [S-12.02.06-posting-channel-from-the-screens.md](../../docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md) |

**Sub-features, tasks and QA to finish:**

1. .06: finish posting/image pairing, approval/skip, pause/resume and daily pacing from actual screens; preserve no-spend guards for paused pairs.
2. .05: obtain/classify the expert corpus and owner winners; run at least30 judged paired planning evaluations with/without references and preserve reproducible results.
3. QA: actual browser flow, workspace denial, duplicate-run/restart/pacing, classified broker egress and evaluation quality. Official publishing credentials/reviews remain necessary for live publication.

## Remaining open entries outside the next-five programme

These35 entries remain on the board; this turn does not silently expand the selected three-area scope into all remaining product work.

| ID | State | Title |
|---|---|---|
| S-02.02.03 | BACKLOG | Interrupt, steer, resume |
| S-07.01.01 | BACKLOG | An MCP client |
| S-07.01.02 | BACKLOG | Native OAuth integrations |
| F-06.22 | IN_REVIEW | Duplicate Contact Review (backend) |
| F-06.19 | IN_REVIEW | CRM Data Quality Centre |
| F-06.20 | IN_REVIEW | Campaign Comparison Dashboard |
| F-06.21 | IN_REVIEW | Follow-up Performance Centre |
| F-06.16 | IN_REVIEW | Unified CRM Search |
| F-06.17 | IN_REVIEW | Account Intelligence Workspace |
| F-06.18 | IN_REVIEW | Campaign-to-Revenue Attribution |
| F-06.13 | IN_REVIEW | Qualified Reply-to-Sales Conversion |
| F-06.14 | IN_REVIEW | Contact 360 Workspace |
| F-06.15 | IN_REVIEW | Daily Action Command Center |
| F-06.10 | IN_REVIEW | Reply Inbox & Human Triage |
| F-06.11 | IN_REVIEW | Contact Communication History |
| F-06.12 | IN_REVIEW | Human Follow-up Task Manager |
| F-06.07 | IN_REVIEW | Audience Management Workspace |
| F-06.08 | IN_REVIEW | Campaign Launch Readiness Center |
| F-06.09 | IN_REVIEW | Campaign Activity & Audit Timeline |
| F-06.04 | IN_REVIEW | Campaign Management |
| F-06.05 | IN_REVIEW | Campaign Blueprint Reuse |
| F-06.06 | IN_REVIEW | Campaign Performance Intelligence |
| S-12.01.03 | IN_REVIEW | The video director uses the product |
| S-05.01.04 | IN_REVIEW | Public-page fetches connect only to checked destinations |
| S-03.01.03 | IN_REVIEW | Browser blocks internal network access |
| S-07.01.03 | IN_REVIEW | Meeting transcription with no bot in the call |
| S-02.02.02 | IN_REVIEW | PLAN.md as the single source of truth |
| S-03.02.05 | IN_REVIEW | A platform is a row, not a code change |
| S-05.01.03 | IN_REVIEW | Take a competitor post apart and rebuild the shape |
| S-05.01.02 | IN_REVIEW | Extraction packs as declared data |
| S-05.01.01 | IN_REVIEW | A crawler with a frontier, not a loop |
| S-07.01.04 | IN_REVIEW | Reports and artifacts |
| S-01.05.01 | BLOCKED | Publish to YouTube through the official API |
| S-01.05.02 | BLOCKED | One adapter contract for the remaining platforms |
| S-01.05.03 | BLOCKED | Read real engagement back from the platform |

## Infrastructure and verification facts

- Render: the latest inspected review build failed with pipeline_minutes_exhausted (November5,10:06:54 UTC). No later review build was visible in the approved Kunal Wagh workspace at the last connector refresh. That proves the failed attempt's cause; it does not prove today's remaining billing balance. Services have auto-deploy off. No paid upgrade or customer deploy was performed.
- Local execution is available: actual app/browser flows, disposable PostgreSQL16, encrypted root/multi-schema recovery and tests have run. Managed Chromium blocks data-URL fixtures locally; the corresponding real remote CI runs pass. Do not describe those local blocked cases as passing.
- b4ded78 full CI42302820197 and container42302820195 both passed. Registry02422ec full42306456274 and container42306456325 also passed: Python3versions each3202 PASS, PostgreSQL3241 PASS, genuine direct/pooler20 PASS/1 deliberate startup-options skip, board72/72, frontend234/build PASS. Exact53a93a0 full42399243286/container42399243238 also SUCCESS: Python3versions each3231 PASS/97 skips, PostgreSQL3290 PASS/107 skips, pooler64 PASS/1 intentional skip, Docker3 PASS, board72/72, frontend237/build and actual desktop/mobile recovery browser PASS. Newer recall/import source needs its own CI.
- Registry current local bundle33 PASS/6 local pooler skips; independent SQLite registry20 PASS across two runs. Details in [registry evidence](../evidence/2026-11-07-workspace-crm-registry.md). Default application routing remains unchanged until complete cutover/factory/shared-control/recovery acceptance.
- Q-27 answered: workspace-owned customer CRM rows. Q-28 answered: Drafts use Connectors. Independent installs use separate databases. These are no longer unresolved owner decisions.
- Still external: private offsite bucket/region/endpoint/retention and secure credentials, real configured AI/provider acceptance, and official social platform approvals where applicable. Existing test transports and local outboxes are not live account proofs.

No whole-feature DONE or deployment claim is made by this report. Close individual stories only after their own criteria, dependencies, tests, independent review, documentation and verifier evidence pass.

2026-11-07 follow-through: recall mutations/counter workspace and unowned rebuild refusal pass96 affected checks. Import/recovery boundaries pass315 actual SQLite/PostgreSQL checks plus99 isolated install-database cases and8 encrypted real-PG recovery checks. Independent112 owner/import PASS and restricted-role RLS replay. S-06.03.07 now IN_REVIEW; totals remain100 open. Render health probes returned ProxyError here, so HTTP availability remains unverified; no deploy attempted.
