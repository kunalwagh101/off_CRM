# Current backlog, Render and local CI audit — 2026-11-06

**Scope:** `develop` at `a1073c0d5e5c6220348c3eba15343e27bab5eb9a`, plus test-fixture corrections `79fce1d` and CI configuration corrections `62f60da` / `4eaca8f`, plus container checks `3f50738` / `e6105bd` made in this audit. The previous chat used older `main` plus local work; it is not the current development backlog. That work was preserved before switching to the existing develop branch. No main promotion or customer deployment is authorized by this audit.

**Final verification:** full regression workflow [42185594224](https://github.com/kunalwagh101/off_CRM/actions/runs/42185594224) PASS on 4eaca8f; final container workflow [42187777222](https://github.com/kunalwagh101/off_CRM/actions/runs/42187777222) PASS on e6105bd. All 70 recorded board commands pass remotely. Render remains quota-blocked and production acceptance remains open. Later commits changed only the separate container workflow and audit records; repeated full-suite runs may still be in progress.

## Counts and definitions

The board contains **172 delivery entries: 153 stories and 19 directly tracked feature entries**. **102 are open: 83 stories plus 19 directly tracked features.** These are open tracker entries, not 102 brand-new features to code. Feature rollups and story entries can describe related scope; do not add them as independent units of effort.

| State as found | Story entries | Direct feature entries | Total |
|---|---:|---:|---:|
| DONE | 70 | 0 | 70 |
| IN_REVIEW | 54 | 19 | 73 |
| IN_PROGRESS | 1 | 0 | 1 |
| READY | 0 | 0 | 0 |
| BACKLOG | 22 | 0 | 22 |
| BLOCKED | 6 | 0 | 6 |
| DEFERRED | 0 | 0 | 0 |

There are **46 declared feature IDs** in the backlog, including future/organizational headings. Using stable story-ID prefixes, open stories span **12 feature groups**; adding the **19 directly tracked CRM features** gives **31 feature areas with open tracked delivery**. This is a derived grouping rule, not a claim that all 31 areas have zero code. F-11.06 is a cross-cutting process grouping using S-06.02 IDs; future F-12.03–F-12.05 headings have no separately tracked delivery stories. Physical heading order is inconsistent because later S-06.02 stories were appended under unrelated headings; prefixes avoid silently inventing parents.

After checking executed runner logs, S-06.02.18 moved from BLOCKED to IN_REVIEW. **Current states: 70 DONE, 74 IN_REVIEW (55 stories + 19 features), 1 IN_PROGRESS, 0 READY, 22 BACKLOG, 5 BLOCKED. Open total remains 102.** The table above preserves the as-found snapshot.

The requirement register maps **158 requirements** and the backlog parser counts **453 acceptance criteria**. The structural verifier reports 193 criteria behind DONE (43% traceability coverage); this is not runtime code coverage or production-readiness percentage. Historical DONE claims still need their recorded checks to reproduce.

## Tasks: why a truthful grand total is unavailable

The repository has 71 work-order documents. Outside fenced examples, 26 distinct T-... task IDs occur in the backlog/work orders; their parent-story states are {'DONE': 6, 'IN_REVIEW': 20}. These are not a complete task ledger and carry no independent per-task execution state. Many features instead use numbered steps, criteria and checklist bullets. Therefore a total number of remaining tasks cannot currently be certified. Reporting a multiplied story×task estimate would be invented precision.

Of the 102 open board entries, **74 link a work order (55 stories and all 19 direct features); 28 open stories have no `work_order` field**. An absent board link is not proof that no historical design document exists. It is a concrete traceability/decomposition gap to resolve before pulling that story.

Before pulling a new story, convert its actual remaining acceptance work into a work order with stable task IDs, dependencies, tests and state. Use the existing code first: contract/source audit; failing acceptance reproduction; smallest necessary implementation; SQLite/PostgreSQL and browser integration; negative security/concurrency/recovery; documentation/rollback; independent review and release evidence. Do not recreate source just because its status is BACKLOG.

## Remaining feature groups

| Feature | Open stories | DONE stories | Work to finish or prove |
|---|---:|---:|---|
| F-01.05 — Publishing to a real platform | 3 | 0 | Enable the official publishing credentials/reviews; verify a real publish and engagement readback. YouTube, Meta, TikTok and LinkedIn access are external dependencies. |
| F-02.02 — The run loop | 2 | 2 | Finish interrupt/steer/resume as a complete owner flow; close editable-plan acceptance. Reuse the existing bounded loop and process-replay implementation. |
| F-03.01 — Isolation | 1 | 2 | Prove private-network blocking with an actual browser/container across DNS, redirects, subresources and new tabs. Do not weaken the separate no-network code sandbox. |
| F-03.02 — Identity and secrets | 1 | 4 | Close declared-platform registry proof through sign-in, vault, pacing and budgets. Existing vault/revoke stories are recorded DONE. |
| F-04.01 — The agent team | 4 | 0 | Validate explicit skill selection, bounded child reasoning, real role orchestration and scoped memory/tool grants. Profile durability, live provider/browser paths and upstream companion acceptance remain gates. |
| F-05.01 — Intelligence | 4 | 0 | Close frontier/politeness/revisit, extraction-pack and competitor-analysis acceptance; prove DNS/redirect defenses and review-queue handoff with actual public sources. |
| F-06.01 — Team and production | 5 | 1 | Close global/tool/chat permissions and owner watch/cancel flows; implement/verify durable operations and recovery. CRM tenant boundaries await Q-27 and must not be assumed from credential isolation. |
| F-06.02 — Non-functional work, with its own IDs | 51 | 18 | Close the production audit and its security remediations; verify identity/media isolation, quotas/billing, idempotency, cache integrity, uploads, error references, accessibility, CI and the actual email worker. |
| F-06.03 — Data that survives a deploy on the free plan | 5 | 3 | Prove encrypted offsite backup and restore, complete durable homes for all stores, half-hosted startup refusal and per-install choices. A real private bucket/IAM/key/retention/scheduler and offsite recovery drill remain necessary. |
| F-07.01 — Integrations and artifacts | 4 | 0 | Build/finish MCP and OAuth integrations; close actual meeting capture/transcription and reports/artifacts acceptance with real provider/configuration and privacy/access checks. |
| F-12.01 — One source of truth about the product | 1 | 2 | Close product-aware director proof, keeping owner product text classified and exact egress auditable; verify product/workspace ownership through the supported flow. |
| F-12.02 — The strategy brain | 2 | 4 | Close posting-pair/approve-skip/pacing UI proof and expert-corpus evaluations. Expert references/evaluation material and live social platform access remain dependencies. |

## Nineteen directly tracked CRM features

All nineteen are recorded IN_REVIEW with implementations/specifications. The remaining work is feature-specific end-to-end acceptance, privacy/authorization and real-database/query/performance proof, independent security/release acceptance and, where applicable, the unresolved Q-27 CRM ownership decision. These rows are not nineteen absent codebases.

| ID | Feature | State |
|---|---|---|
| F-06.04 | Campaign Management | IN_REVIEW |
| F-06.05 | Campaign Blueprint Reuse | IN_REVIEW |
| F-06.06 | Campaign Performance Intelligence | IN_REVIEW |
| F-06.07 | Audience Management Workspace | IN_REVIEW |
| F-06.08 | Campaign Launch Readiness Center | IN_REVIEW |
| F-06.09 | Campaign Activity & Audit Timeline | IN_REVIEW |
| F-06.10 | Reply Inbox & Human Triage | IN_REVIEW |
| F-06.11 | Contact Communication History | IN_REVIEW |
| F-06.12 | Human Follow-up Task Manager | IN_REVIEW |
| F-06.13 | Qualified Reply-to-Sales Conversion | IN_REVIEW |
| F-06.14 | Contact 360 Workspace | IN_REVIEW |
| F-06.15 | Daily Action Command Center | IN_REVIEW |
| F-06.16 | Unified CRM Search | IN_REVIEW |
| F-06.17 | Account Intelligence Workspace | IN_REVIEW |
| F-06.18 | Campaign-to-Revenue Attribution | IN_REVIEW |
| F-06.19 | CRM Data Quality Centre | IN_REVIEW |
| F-06.20 | Campaign Comparison Dashboard | IN_REVIEW |
| F-06.21 | Follow-up Performance Centre | IN_REVIEW |
| F-06.22 | Duplicate Contact Review (backend) | IN_REVIEW |

## Ordered programme already selected by the owner

1. **F-06.02 production reliability:** finish S-06.02.23 audit, current CI/fixture/browser failures, full-history verification, access/privacy/security gates and the durable worker. Do not substitute more feature code for missing proof.
2. **F-06.03 durable storage and recovery:** complete store inventory/homes, independently configured encrypted backup destination, empty-target restoration and restart/recovery proof.
3. **F-04.01 agent team:** prove existing companions, explicit procedures, bounded children and five real role paths with the broker and human gates intact.
4. **F-06.01 permissions and operations:** actual supported owner watch/cancel workflow, global/tool/chat permissions, monitoring/release recovery and the Q-27 tenancy decision.
5. **F-12.02 GTM strategy:** posting/image pairs, approval/skip, pacing and source-backed expert/winner evaluations. Do not fabricate reference material or claim local-outbox tests prove social publishing.

## Next five features: stories, remaining tasks and acceptance

These are delivery tasks for existing stories, not an invented total for the whole project. Complete the first three feature areas in order; do not call them DONE while their dependencies or release checks are open. There are currently no READY board entries; S-06.02.23 is already in progress.

### 1. F-06.02 — Production reliability and verification

- **Stories:** active S-06.02.23; CI runner/history/matrix/harness S-06.02.18/.20/.26/.27; logs .38; dependency security .16; keyboard .37; command locks .28; second-owner login .36; draft routing .35; email worker .40; newer authorization, media, quota, billing and idempotency remediations listed in the open-entry inventory below.
- **Tasks:** reproduce every still-open audit finding; close real source defects test-first; correct fixture defects without weakening assertions; execute locked SQLite and PostgreSQL regressions; replay DONE evidence with full history; exercise real browser desktop/mobile flows; verify error-reference/redaction, worker restart and uncertain-send behavior; document rollback and unresolved findings. Obtain Q-28 before changing Drafts routing.
- **QA/exit:** negative authorization, workspace isolation, secret egress, upload/path validation, concurrency, crash recovery and duplicate-action tests; frontend tests/build and dependency audits; supported-Python matrix; independent live penetration and acceptance evidence. A passing unit suite alone does not close the audit. Confirm current hosted CI separately from Render capacity.

### 2. F-06.03 — Hosted data and recovery

- **Stories:** S-06.03.04 backups, .06 remaining stores, .05 half-hosted production refusal, .07 per-install decisions; .08 owner storage readiness remains IN_REVIEW.
- **Tasks:** reconcile every store with the inventory and choose its durable/disposable home; preserve/import existing data; finish guarded startup and migration paths; provision backup/recovery clients compatible with the actual hosted server; configure the approved private S3-compatible destination with bounded access, separate recovery-key custody, retention and scheduler; run an offsite restore into an empty database and reconcile counts; document owner download and rollback. Resolve shared-install policy before assuming shared database semantics.
- **QA/exit:** real PostgreSQL dump/restore; refuse tables and other preexisting user objects; tamper/truncation/wrong-key and partial-upload failure; restart durability; two-install choice isolation; half-hosted startup refusal; real external recovery drill. In-memory object transport does not prove offsite recovery.

### 3. F-04.01 — Agent team

- **Stories:** S-04.01.01 persisted companion profiles; .02 explicit on-demand skills; .03 bounded children; .04 Scout/Maker/Poster/Analyst/Director roles.
- **Tasks:** accept upstream profile persistence and scoped tool/memory grants; validate explicitly selected skill CRUD/context and disabled/missing/cross-workspace cases; prove bounded child depth, fan-out, spend and cancellation; pass only child results to the parent; wire all five roles to existing engines through the broker and human review queue; complete owner-visible error, audit and recovery paths.
- **QA/exit:** profile restart/import, hostile grant rejection, skill owner authorization and prompt scope; child budget/depth/fan-out and failure propagation; role integration with existing assembler/director; no tool/publishing side effects without approval; live configured-provider/browser acceptance. Product child-agent stories do not authorize development-agent spawning.

### 4. F-06.01 — Team permissions and operations

- **Stories:** S-06.01.01 workspace keys/logins; .02 three-level permissions; .04 routines; .05 deployment/monitoring/rollback; .06 CRM tenancy. Cost ledger .03 is recorded DONE.
- **Tasks:** finish global/per-tool/chat permission resolution and actual watch/cancel screens; prove routine ownership and bounded scheduling; configure health, monitoring and secret-safe operator diagnostics; exercise release/restart/rollback without losing durable state; obtain Q-27 before any CRM tenancy migration.
- **QA/exit:** session and cross-workspace denial; permission precedence/revocation; cancel during active work; duplicated scheduler/worker claims; restart and rollback recovery. Key/login isolation is not proof of CRM row isolation.

### 5. F-12.02 — GTM strategy brain

- **Stories:** S-12.02.06 paired posting/image screens, approval/skip and pacing; .05 expert references and judged winner corpus. Existing .01–.04 planning/apply/review/revise remain recorded DONE.
- **Tasks:** verify applied campaign pairing and resume/pause from screens; make approval/skip and per-plan daily pacing complete; preserve paused-pair no-spend guards; obtain and classify actual expert references and owner winners; compare plans with/without references over at least 30 judged cases; report insufficient evidence honestly.
- **QA/exit:** actual browser pair/approval/skip flow; cross-workspace denial; restart/pacing and duplicate-run prevention; classified provider payloads and egress audit; reproducible paired evaluations. Live publication still requires official platform access; local outbox success is not a live publish.

## Decisions and external dependencies

- **Q-27 open:** whether all CRM rows are workspace/customer owned. Current login/key separation does not prove separate customer data. This is a release/privacy dependency, not a routine implementation guess.
- **Q-28 open:** whether Drafts use Connectors or the older provider-profile path. The selection changes routing, policy and migration scope.
- **Q-29 answered:** private S3-compatible backup architecture approved. Physical bucket/IAM, independent key custody, retention, scheduling and an actual offsite recovery drill remain external dependencies.
- **Q-30 answered:** only explicit owner-selected procedure IDs enter a companion run; live acceptance and upstream profile verification remain.
- Official YouTube credentials and Meta/TikTok/LinkedIn approvals still block real publishing and engagement feedback.
- Historical branch archive/deletion is an owner-only workflow. GitHub currently exposes 48 branches; the intended two-branch policy is not evidence that cleanup was completed.
- S-06.02.18 had a stale blocker reason and has been moved to IN_REVIEW: the latest GitHub jobs allocated runners and executed dependency, audit and test steps. Current failures are test/browser failures, not proof of zero runner capacity. Capacity restoration must be distinguished from a passing pipeline.

## All open entries — inspect before starting more code

| State | ID | Title | Existing work order |
|---|---|---|---|
| BACKLOG | S-06.02.69 | Image briefs, generated files and video handoff remain private to their workspace (A05) | docs/work-orders/S-06.02.69-image-workspace-ownership.md |
| BACKLOG | S-06.02.68 | Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05) | docs/work-orders/S-06.02.68-video-workspace-ownership.md |
| BACKLOG | S-06.02.67 | Only install owners may access personal-data inventory and erasure (A24/A05) | docs/work-orders/S-06.02.67-privacy-owner-authorization.md |
| BACKLOG | S-06.02.66 | Paid AI calls cannot silently count as free when usage receipts are invalid (A10) | docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md |
| BACKLOG | S-06.02.62 | HTTP idempotency safely prevents duplicate state-changing requests (A14) | docs/work-orders/S-06.02.62-atomic-http-idempotency.md |
| BACKLOG | S-06.02.61 | Email provider setup failures do not strand delivery jobs (A16) | docs/work-orders/S-06.02.61-email-provider-setup.md |
| BACKLOG | S-06.02.60 | AI request and spending caps reserve atomically across workers (A11) | docs/work-orders/S-06.02.60-atomic-ai-quota.md |
| BACKLOG | S-06.02.40 | A durable email worker runs beside the deployed web app | docs/work-orders/S-06.02.40-durable-deployment-worker.md |
| BACKLOG | S-02.02.03 | Interrupt, steer, resume | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-04.01.02 | Skills: procedures fetched on demand | docs/work-orders/S-04.01.02-on-demand-agent-skills.md |
| BACKLOG | S-04.01.03 | Sub-agents for context isolation | docs/work-orders/S-04.01.03-bounded-child-reasoning.md |
| BACKLOG | S-04.01.04 | The five roles, wired to what already exists | docs/work-orders/S-04.01.04-five-role-integration.md |
| BACKLOG | S-06.01.05 | Deployment, monitoring and rollback | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-07.01.01 | An MCP client | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-07.01.02 | Native OAuth integrations | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-06.02.27 | The audit's live harness runs against `develop` | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-06.02.35 | Drafts reach a model the owner set up on a screen | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-06.03.04 | The hosted database is backed up outside itself | docs/work-orders/S-06.03.04-hosted-backup-and-restore.md |
| BACKLOG | S-06.03.05 | Production refuses a half-hosted install | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-06.03.06 | Every other store has a decided home | docs/work-orders/S-06.03.06-store-homes.md |
| BACKLOG | S-06.03.07 | A local install's decision belongs to that install | No work_order field; inspect backlog/spec and finish decomposition |
| BACKLOG | S-06.02.26 | CI runs the suite on every Python the package supports | docs/work-orders/S-06.02.26-python-matrix.md |
| IN_PROGRESS | S-06.02.23 | Re-check the 7 September production audit on `develop` | docs/work-orders/S-06.02.23-audit-recheck.md |
| IN_REVIEW | S-06.02.65 | Reject malformed nested video edits without partial writes (A22) | docs/work-orders/S-06.02.65-video-edit-input.md |
| IN_REVIEW | S-06.02.64 | Restricted sandbox can write outputs without exposing host files (A32) | docs/work-orders/S-06.02.64-sandbox-writable-workspace.md |
| IN_REVIEW | S-06.02.63 | Token-authenticated media works in review and video export (A20) | docs/work-orders/S-06.02.63-token-media-auth.md |
| IN_REVIEW | S-06.02.58 | Factual AI cache only reuses exact evidence (A12) | docs/work-orders/S-06.02.58-exact-factual-cache.md |
| IN_REVIEW | S-06.02.59 | Cached AI outputs are scoped to the actual model and instructions (A13) | docs/work-orders/S-06.02.59-cache-model-provenance.md |
| IN_REVIEW | S-06.02.57 | A09: Enter handlers cannot bypass human approval | docs/work-orders/S-06.02.57-enter-approval.md |
| IN_REVIEW | S-06.02.56 | Reject corrupt image payloads safely (A21) | docs/work-orders/S-06.02.56-complete-image-decoding.md |
| IN_REVIEW | S-06.02.55 | Verify numeric claims without changing sign, precision or magnitude (A18) | docs/work-orders/S-06.02.55-numeric-claim-integrity.md |
| IN_REVIEW | F-06.22 | Duplicate Contact Review (backend) | docs/features/crm-duplicate-review.md |
| IN_REVIEW | S-06.02.54 | Restore actual AI and orchestration in the visitor demo | docs/work-orders/S-06.02.54-restore-visitor-ai.md |
| IN_REVIEW | S-06.02.53 | Public visitor demo has its own visible login and isolated sample data | docs/work-orders/S-06.02.53-public-visitor-demo.md |
| IN_REVIEW | S-06.02.52 | Owner sees operational scheduler health separate from web readiness | docs/work-orders/S-06.02.52-operational-health.md |
| IN_REVIEW | S-06.01.02 | Owner sets global, per-tool and chat-lifetime browser permissions | docs/work-orders/S-06.01.02-three-level-agent-permissions.md |
| IN_REVIEW | S-06.03.08 | Install owner sees actual storage durability and production blockers | docs/work-orders/S-06.03.08-storage-readiness-report.md |
| IN_REVIEW | S-06.02.51 | Video uploads have a bounded request stream and concurrency gate (A15) | docs/work-orders/S-06.02.51-video-upload-stream-guard.md |
| IN_REVIEW | S-06.02.50 | Video media and renders obey configured upload limits (A15 partial remediation) | docs/work-orders/S-06.02.50-bounded-video-uploads.md |
| IN_REVIEW | F-06.19 | CRM Data Quality Centre | docs/features/crm-data-quality.md |
| IN_REVIEW | F-06.20 | Campaign Comparison Dashboard | docs/features/campaign-comparison.md |
| IN_REVIEW | F-06.21 | Follow-up Performance Centre | docs/features/followup-performance.md |
| IN_REVIEW | F-06.16 | Unified CRM Search | docs/features/unified-crm-search.md |
| IN_REVIEW | F-06.17 | Account Intelligence Workspace | docs/features/account-intelligence-workspace.md |
| IN_REVIEW | F-06.18 | Campaign-to-Revenue Attribution | docs/features/campaign-revenue-attribution.md |
| IN_REVIEW | F-06.13 | Qualified Reply-to-Sales Conversion | docs/features/reply-to-sales-conversion.md |
| IN_REVIEW | F-06.14 | Contact 360 Workspace | docs/features/contact-360-workspace.md |
| IN_REVIEW | F-06.15 | Daily Action Command Center | docs/features/daily-action-command-center.md |
| IN_REVIEW | F-06.10 | Reply Inbox & Human Triage | docs/features/reply-inbox-triage.md |
| IN_REVIEW | F-06.11 | Contact Communication History | docs/features/contact-communication-history.md |
| IN_REVIEW | F-06.12 | Human Follow-up Task Manager | docs/features/human-followup-tasks.md |
| IN_REVIEW | F-06.07 | Audience Management Workspace | docs/features/audience-workspace.md |
| IN_REVIEW | F-06.08 | Campaign Launch Readiness Center | docs/features/campaign-launch-readiness.md |
| IN_REVIEW | F-06.09 | Campaign Activity & Audit Timeline | docs/features/campaign-activity-timeline.md |
| IN_REVIEW | F-06.04 | Campaign Management | docs/features/campaign-management.md |
| IN_REVIEW | F-06.05 | Campaign Blueprint Reuse | docs/features/campaign-blueprints.md |
| IN_REVIEW | F-06.06 | Campaign Performance Intelligence | docs/features/campaign-performance.md |
| IN_REVIEW | S-06.02.47 | Large send queues are paginated | docs/work-orders/S-06.02.47-queue-pagination.md |
| IN_REVIEW | S-06.02.48 | Campaign-wide queue counters do not mislead | docs/work-orders/S-06.02.48-global-queue-totals.md |
| IN_REVIEW | S-06.02.49 | Queue views focus on actionable cohorts | docs/work-orders/S-06.02.49-actionable-queue-views.md |
| IN_REVIEW | S-06.02.44 | Download all filtered Contacts rows | docs/work-orders/S-06.02.44-filtered-contact-download.md |
| IN_REVIEW | S-06.02.45 | Category and variant filters for contacts | docs/work-orders/S-06.02.45-contact-facet-filters.md |
| IN_REVIEW | S-06.02.46 | Marked-only contacts remain reachable | docs/work-orders/S-06.02.46-marked-only-contacts.md |
| IN_REVIEW | S-06.02.41 | Contacts beyond row 500 are reachable | docs/work-orders/S-06.02.41-contacts-pagination.md |
| IN_REVIEW | S-06.02.42 | Enrichment exports cannot run spreadsheet formulas | docs/work-orders/S-06.02.42-spreadsheet-formulas.md |
| IN_REVIEW | S-06.02.43 | Logout revokes the copied browser session | docs/work-orders/S-06.02.43-logout-revocation.md |
| IN_REVIEW | S-12.02.05 | The brain drafts against the expert corpus and the owner's winners | docs/work-orders/S-12.02.05-plans-with-expert-references.md |
| IN_REVIEW | S-06.02.16 | Resolve frontend development dependency audit findings | docs/work-orders/S-06.02.16-frontend-dependency-audit.md |
| IN_REVIEW | S-12.01.03 | The video director uses the product | docs/work-orders/S-12.01.03-video-director-uses-the-product.md |
| IN_REVIEW | S-06.02.34 | Connectors show how much is left | docs/work-orders/S-06.02.34-usage-remaining.md |
| IN_REVIEW | S-06.02.28 | A command-line tool locks the workspace it actually opens | docs/work-orders/S-06.02.28-path-aware-workspace-lock.md |
| IN_REVIEW | S-06.02.36 | A second owner login is made on purpose | docs/work-orders/S-06.02.36-explicit-owner-login.md |
| IN_REVIEW | S-05.01.04 | Public-page fetches connect only to checked destinations | docs/work-orders/S-05.01.04-verified-destinations.md |
| IN_REVIEW | S-03.01.03 | Browser blocks internal network access | docs/work-orders/S-03.01.03-network-isolation.md |
| IN_REVIEW | S-06.02.37 | Skip navigation keeps the current screen | docs/work-orders/S-06.02.37-skip-keeps-current-page.md |
| IN_REVIEW | S-06.02.20 | The verifier tells a shallow clone apart from a missing commit | docs/work-orders/S-06.02.20-shallow-git-history.md |
| IN_REVIEW | S-06.02.39 | Valid low-bitrate WebM exports pass verification | docs/work-orders/S-06.02.39-low-bitrate-export.md |
| IN_REVIEW | S-12.02.06 | A plan's posting channel runs from the screens | docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md |
| IN_REVIEW | S-06.02.38 | Any error can be traced back the next day | docs/work-orders/S-06.02.38-traceable-errors.md |
| IN_REVIEW | S-06.02.25 | Every screen opens at its top, its warnings in view | docs/work-orders/S-06.02.25-screen-opens-at-top.md |
| IN_REVIEW | S-06.02.21 | Durable customer state and safe recovery (audit WP1) | docs/work-orders/S-06.02.21-S-06.02.22-close-out.md |
| IN_REVIEW | S-06.02.22 | A created or selected campaign stays the active workspace | docs/work-orders/S-06.02.21-S-06.02.22-close-out.md |
| IN_REVIEW | S-07.01.03 | Meeting transcription with no bot in the call | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.02.05 | The UI is usable by keyboard and screen reader | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.02.02 | Every endpoint authorises and validates | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.02.01 | No secret may enter a model prompt | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.01.04 | Routines that fire agent runs on a schedule or an event | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.01.01 | Workspaces with their own keys and their own logins | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-04.01.01 | Companions: persisted agent profiles | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-02.02.02 | PLAN.md as the single source of truth | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-03.02.05 | A platform is a row, not a code change | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.02.04 | Data deletion and subject access | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-05.01.03 | Take a competitor post apart and rebuild the shape | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-05.01.02 | Extraction packs as declared data | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-05.01.01 | A crawler with a frontier, not a loop | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-07.01.04 | Reports and artifacts | No work_order field; inspect backlog/spec and finish decomposition |
| BLOCKED | S-06.02.19 | One working branch holds everything built, and it is green | No work_order field; inspect backlog/spec and finish decomposition |
| BLOCKED | S-06.01.06 | Campaigns, contacts and drafts belong to a workspace | No work_order field; inspect backlog/spec and finish decomposition |
| IN_REVIEW | S-06.02.18 | Restore executable CI runner capacity | No work_order field; inspect backlog/spec and finish decomposition |
| BLOCKED | S-01.05.01 | Publish to YouTube through the official API | No work_order field; inspect backlog/spec and finish decomposition |
| BLOCKED | S-01.05.02 | One adapter contract for the remaining platforms | No work_order field; inspect backlog/spec and finish decomposition |
| BLOCKED | S-01.05.03 | Read real engagement back from the platform | No work_order field; inspect backlog/spec and finish decomposition |

A BACKLOG status does not mean no code exists. In particular image/video/owner-privacy guards, billing, idempotency, email setup, atomic quota, skills, children, role wiring and hosted backup/store work have build-ahead checkpoints. Inspect and test these first; implement only the actual missing paths. IN_REVIEW means implemented but not accepted, not shipped.

## Render: confirmed build-minute failure, separate from runtime health

- Confirmed workspace: Kunal Wagh’s Workspace (user selected it for this audit).
- Review service `srv-db86p4u89jmc73cehns0`: latest attempted deploy `dep-dbm5af95efls73chr69g` on source `80173d6` is build_failed. Event `evt-dbm5afhph17c73dp1ggg` is pipeline_minutes_exhausted at 2026-11-05 10:06:54 UTC (**5 November, 3:36 PM IST**). Render log explicitly says the build was canceled because the workspace ran out of build pipeline minutes for the billing period. No test ran in that attempt.
- The review runner’s previous live deployment is `dep-dbm4lgrbc2fs738acn6g` on `246741b`, completed 5 November 3:13 PM IST.
- Public demo `srv-dbj5q5vb9u1s73d4fe1g` still has a deployment marked live on source `39084d3` from 1 November. Original `off_CRM` service `srv-d9d4i8ok1i2s73cv41ig` is marked live on `97e1e7b`, also 1 November. Both are configured for develop with auto-deploy OFF. A push is not a customer rollout.
- Therefore the latest review build is quota-blocked, while “the whole site is down” is not established. Direct external HTTP readiness probes hit this execution environment’s proxy restriction, so current customer HTTP health is unverified. No paid plan, spend limit, service setting or production deploy was changed. Current remaining minutes/reset date is not exposed by the inspected connector; the latest failed attempt is what is proven.

## GitHub CI: actual executed failures

Previously failing run: https://github.com/kunalwagh101/off_CRM/actions/runs/42068912692 on develop a1073c0. Both jobs started. Quality installed dependencies and passed both npm audit gates, lint, CLI smoke and vault checks, then failed the real Chromium revoke test because its debugging endpoint did not become available within 30 seconds. Subsequent quality steps were skipped. This is not Render-minute exhaustion.

The PostgreSQL job passed focused storage tests, then completed the whole-suite run with 3140 passed, 74 skipped and two failures: an uncommitted hostile fixture and malformed function-creation SQL. The local audit reproduced each failure and corrected only those fixture errors. Import refusal, source retention, nonempty-target protection and restore/data-integrity assertions remain intact. Independent review found no masked production defect. The next remote run passed the previously failing Chromium acceptance step and the complete SQLite suite. The original browser startup cause remains unproven; one successful rerun does not establish it was fixed.

## Local verification and limits

The full current application was launched natively with disposable state and actual Chromium. Contacts: 503 persisted imports, six pages, final-row access, search and controls passed at 1280px and 390px. Visitor flow: actual login, AI landing/Plan controls, provider-setup empty state, sample contacts, write refusal and logout passed at 1440px and 390px. No customer data, real provider request, email or social publication was used.

Frontend: 223 tests across 19 files passed and the production build passed. Production npm audit: zero advisories. Full development audit: two moderate advisories, no high/critical; it is not completely clean. Ruff broken-name/syntax checks passed. Real PostgreSQL 16 backup/import focused tests: 22 passed after the fixture corrections, including guarded nonempty-object refusal and successful empty-database restore. External object storage is a test transport; no real offsite bucket recovery is claimed.

The full production Docker build was attempted twice and stopped with no space left on device on this 8GB/vfs environment. Dependency and frontend stages executed, but no full-image/runtime success is claimed. Failed local build caches were removed; the production Dockerfile was restored unchanged. Native app/database/browser verification continues independently of Render minutes.

Local full SQLite: **3,101 passed, 13 failed, 33 skipped** in 640.61s. The failures are real-Chromium data-URL cases; observed pages report the managed environment blocks the site. The matching remote SQLite run passed all 3,114 tests, including those 13. No browser policy was bypassed and no test was disabled. Local full PostgreSQL execution was interrupted with the execution session; its partial log has no completion summary and is not passing evidence. A later complete local board replay ran all 70 commands: **47 passed, 23 failed**, repeating the managed-browser cases already failing locally; it is not a green verifier. No observed failure ID in the board summary falls outside those known local browser failures. The structural full-history check passed: 70 recorded commits all on this branch. Managed-browser data-URL restrictions, configured live providers, external recovery, independent live penetration and production rollout are separate gates. No “everything is perfect” or production-ready claim follows from these checks.


## Fresh GitHub results and CI corrections

Run https://github.com/kunalwagh101/off_CRM/actions/runs/42120555626 on `79fce1d`:

- Quality: all **3,114 passed, 33 skipped**, including real Chromium acceptance. Canceled at the job's 15-minute limit while replaying DONE evidence; frontend steps were skipped. The complete job was not green.
- PostgreSQL: focused storage **215 passed**; full suite **3,141 passed, 1 failed, 74 skipped**. The remaining real restore failure is confirmed by the server log: unsupported `SET transaction_timeout = 0`. A newer runner-default client emitted a header PostgreSQL 16 cannot accept. Matching local PG16 dump/restore passed the actual guarded restore test.
- `62f60da` explicitly installs/selects PostgreSQL client 16 for the PostgreSQL 16 job and prints both versions. It increases quality's bounded timeout to 45 minutes to include the whole suite plus all 70 evidence commands. No assertion, evidence command, suite or security gate was removed.
- Run https://github.com/kunalwagh101/off_CRM/actions/runs/42185372859 exposed Ubuntu 26.04 package availability: postgresql-client-16 was not found. `4eaca8f` pins only the PostgreSQL job to Ubuntu 24.04, whose supported repository contains that client. New exact-source validation: https://github.com/kunalwagh101/off_CRM/actions/runs/42185594224. Its completed results are recorded below.

Targeted authorization/security command: `UV_CACHE_DIR=/workspace/.uv-cache uv run pytest -q tests/test_audit_a05_image_workspace_isolation.py tests/test_ai_egress_wall.py` — **52 passed**, including all 9 image cases whose Render attempt was canceled before execution. This is automated local security regression, not independent live penetration or customer release evidence.


## Reproduction commands and evidence locations

Use the locked dependency setup from `AGENTS.md`: `uv sync --extra dev --extra email --extra postgres --locked`, then `npm ci` in frontend. Local commands used `UV_CACHE_DIR=/workspace/.uv-cache`. Actual browser checks needed execution-environment permission to open localhost sockets.

| Check | Command | Recorded result |
|---|---|---|
| SQLite whole suite | `uv run pytest -q` | Local 3101 PASS / 13 browser-policy failures / 33 skips; remote 3114 PASS / 33 skips on 79fce1d |
| Actual PostgreSQL backup/import | `uv run pytest -q tests/test_hosted_backup.py tests/test_companion_import.py` with disposable `OFF_CRM_TEST_POSTGRES_URL` and PG16 client PATH | 22 PASS |
| Image access and model egress | `uv run pytest -q tests/test_audit_a05_image_workspace_isolation.py tests/test_ai_egress_wall.py` | 52 PASS |
| Frontend | `npm test`; `npm run build` in frontend | 223 PASS; build PASS |
| Registry security | `npm audit --omit=dev --json`; `npm audit --json` | Production 0 advisories; development 2 moderate, no high/critical |
| Syntax/names | `uv run ruff check --select E9,F63,F7,F82 .` | PASS |
| Actual owner contacts UI | `uv run --no-sync python scripts/live/review_contacts_browser.py` | Desktop/mobile PASS |
| Actual read-only visitor UI | `uv run --no-sync python scripts/live/review_public_demo_browser.py` | Desktop/mobile PASS |
| Structural board and Git history | `uv run python scripts/verify_board.py --skip-tests` | PASS; evidence replay explicitly not claimed by this command |
| Full board evidence | `uv run python scripts/verify_board.py` | Local completed: 47/70 commands PASS, 23 fail on known browser cases; remote final result below |

Browser review scripts used their existing Playwright helper (1.56.0), installed only into this disposable review environment; lockfiles were not changed. Raw command outputs remain under ignored `work/current-audit/`; selected raw-output SHA-256 hashes are in `2026-11-06-local-evidence-hashes.json`. Do not publish raw traceback locals as a substitute for sanitized evidence.

Independent read-only review verified all computed counts, stable-ID grouping and complete open-entry inventory against the board/backlog. It found no material issue in the CI changes or evidence limitations; the opening scope was corrected to include the runner pin.


PostgreSQL CI on exact source `4eaca8f` is now **SUCCESS** (run 42185594224, job 127785037477): focused storage **215 PASS**; whole application with every CRM on PostgreSQL **3,142 PASS / 74 skipped / 0 failed** in 586.49s. Printed clients are pg_dump/pg_restore 16.15, matching the PostgreSQL 16 service. This includes successful actual backup restoration and the retained nonempty-object refusal checks. The quality job subsequently passed; see completed results below.


## Production container verification outside Render

The local Docker no-space limitation is recorded above. To close the image validation gap on a capable runner, `3f50738` adds `.github/workflows/container.yml`. It builds the unmodified production Dockerfile, launches actual visitor-mode web app with disposable volume and synthetic credentials, requires HTTP readiness and served HTML, asserts PID 1 runs as UID 10001, restarts the same container and requires readiness again. Cleanup removes only that disposable container/volume. It makes no provider calls and does not deploy a customer service. Startup/restart smoke does not establish offsite recovery or all feature acceptance.

Container run: https://github.com/kunalwagh101/off_CRM/actions/runs/42187573006. Full test workflow also retriggered on 3f50738: https://github.com/kunalwagh101/off_CRM/actions/runs/42187572759. Application source and existing test workflow are unchanged from 4eaca8f; the new workflow was independently reviewed and passed, as recorded below.


## Completed full regression and container results

Full test workflow **42185594224 SUCCESS** on `4eaca8f`: quality and PostgreSQL jobs both green. Quality: **3,114 PASS / 33 skipped**; **70/70 recorded board evidence commands PASS**, all evidence commits valid ancestors; **223 frontend tests PASS**, production frontend build PASS; configured dependency audits, syntax/name and browser acceptance gates PASS. PostgreSQL: **215 focused PASS**, **3,142 whole-suite PASS / 74 skipped / 0 FAIL**. This verifies D-382–D-385 corrections; development dependency audit still has the two permitted moderate advisories.

Production-container workflow **42187573006 SUCCESS** on `3f50738`: actual Dockerfile builds, image boots, `/health/ready` and served HTML pass, PID 1 UID 10001 assertion passes, same-container restart readiness passes, disposable container/volume removed. This closes the image-build check outside Render even though local Docker ran out of disk. It proves the built image with visitor configuration, not production-mode configuration or real customer storage/recovery.

Independent container review identified a path-filter omission for runtime `config/**` changes. `e6105bd` adds that pattern to push and PR filters. No production/application source, tests or existing test workflow changed after 4eaca8f; subsequent whole-suite runs are redundant validations, while the new container workflow is checked on its own source. Final filtered-workflow container rerun **42187777222 SUCCESS** on e6105bd, job 127792112500: build, startup/readiness/frontend/UID, restart and cleanup all pass. No assertions were weakened.


2026-11-06 continuation checkpoint: Render events refreshed in the previously owner-approved workspace. Latest review deploy still shows the Nov5 pipeline_minutes_exhausted cancellation, no later review build event, and off_CRM/public/visitor/review auto-deploy remains disabled. This confirms the reason for that attempted build; it does not measure remaining billing minutes now. No new paid resource/build/customer deployment was requested or triggered. Drafts/CLI ownership commitd06435a full GitHub workflow42243010453 and container42243010523 SUCCESS. Hosted meeting/routine commit47efdad container42244691442 SUCCESS; full suites caught mixed routine trace-file readiness overclaim (D-402), corrected with targeted12 PASS. Explicit legacy ownership foundation is read-only and does not close Q-27 tenancy implementation. Board completion counts remain unchanged.
