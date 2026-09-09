# off_CRM — production audit

**Verdict: the audited main branch is not ready for company production use under the supplied deployment.**

The application has substantial working code and a useful automated test base. However, the audit reproduced failures in data integrity, recovery, browser safety, AI spending controls, cached answers, claim verification and user workflows. The deployment and access model also need production changes before this can safely serve company users.

**Initial audit:** 6 September 2026 UTC / 7 September 2026 IST. **Live verification revision:** 7 September 2026 UTC.\
**Repository:** [kunalwagh101/off_CRM](https://github.com/kunalwagh101/off_CRM).\
**Main snapshot:** [`9f71f3c07f32`](https://github.com/kunalwagh101/off_CRM/commit/9f71f3c07f32407857311a1c4ed756925a612e6d) — S-11.02.03: refuse unsupported browser claims.\
**Deliverable:** source audit, real browser/database/container verification, reproducible regressions, feature readiness matrix and remediation acceptance criteria. Application code is unchanged. A test-only audit branch and CI workflow were pushed for review; no application fix was merged or deployed.

## Read this first

There are **35 findings: 2 P0, 25 P1 and 8 P2**. Of these, **24 findings have reproductions**. The original supplied regression suite contains **31 failing Python cases plus one failing frontend case** on the audited code. Additional live acceptance results are listed below. Several cases test different symptoms of the same finding, so test count and finding count are different.

The next engineering milestone should be **production reliability and safe operation**. Start with durable storage, transaction isolation and complete restore. Then close the identity, browser safety, spending and workflow defects before enabling those capabilities for company users. Adding another visible feature first would increase the amount of state and behaviour that must later be repaired.

P0 means stop before placing customer data in the affected setup. P1 means fix before the affected capability is used in production, or explicitly keep that capability unavailable. P2 means a confirmed product or maintenance issue that belongs in the production backlog. These are engineering priorities, not CVSS security scores.

## Scope and limits

The audit inventoried **375 tracked files**, **130 Python modules** with **55,150 source lines**, **75 Python test files**, **23 frontend page files**, **8 frontend test files**, and **198 FastAPI operations**, including health endpoints. It combined this inventory with full automated suites, targeted source reviews of feature boundaries and failure paths, dependency checks and new fault reproductions. It is not a claim that every line received the same depth of manual review or that every possible bug has been found.

The review standard is the user's stated company production application: real records, reliable repeated work, individual access, truthful status and AI evidence, safe external actions, and recoverable operations. A shared company installation is sufficient as a target; this audit does not require microservices or a multi-tenant SaaS rewrite as an end in itself.

Tests used temporary synthetic workspaces. The original offline provider tests used controlled doubles; the later checks used real PostgreSQL, Chrome and Docker, a safe read-only Apollo connector profile request, and the actual application's provider-configuration endpoints. The DNS test connected only to an ephemeral loopback HTTP fixture. No customer mailbox was read, no external mail/post was sent, and no paid model generation was invoked. The existing working checkout and its uncommitted work were left untouched.

The live hosting account, production database, customer traffic, external account permissions and deployment settings were not available for direct verification. Therefore, deployment findings refer to the checked-in configuration. A different actual deployment needs separate validation.

## Live verification completed on 7 September

The earlier local audit runner could not reach the app from its interactive browser, had no configured PostgreSQL test service and had no usable pre-pulled sandbox image. Those limitations explained the skipped tests; they did not establish that the features worked. A dedicated GitHub Actions environment now provisions the required services and fails if tests skip or evidence is missing.

**Latest run:** [Production integration verification](https://github.com/kunalwagh101/off_CRM/actions/runs/34125981674), test commit [`30dc5a9d4d84`](https://github.com/kunalwagh101/off_CRM/commit/30dc5a9d4d840f8feb0e859a51ab2900a71ea581). **Review:** [draft PR #11](https://github.com/kunalwagh101/off_CRM/pull/11). The underlying application remains exactly at `9f71f3c07f32407857311a1c4ed756925a612e6d`. Only four test/CI/documentation files were added. The run deliberately remains red because production assertions fail. The ordinary quality workflow passed.

| Live check | Actual result | What this establishes |
|---|---|---|
| Existing suite with real services | **1,611 passed, zero skips** | All 23 formerly skipped cases execute, plus 14 PostgreSQL parameterisations that were absent locally |
| PostgreSQL | **17 real cases passed** on PostgreSQL 16.15 | Egress persistence/filtering/statistics, migration and repeat-migration behaviour; video schema, edit/history/reopen, media/transcripts and JSON round trips |
| Existing browser integration cases | **19 real Chrome cases passed** | The repository's existing CDP, page and browser-agent integration coverage now executes |
| New acceptance suite | **24 passed, 6 failed, zero skips, 0 fixture errors** out of 30 cases | The stronger production requirements expose faults despite the green existing suite; these are not skipped checks |
| Frontend navigation | **18 screen shells rendered** in actual Chrome | Real production frontend, loaded through HTTP, with screenshots and JS/server-error capture. Functional acceptance is narrower than the screen count |
| Campaign and contacts workflows | Create/pause/reload and explicitly selected campaign CSV import/search/reload **passed** | Persistence and correct import association were checked through browser actions and API readback. Automatic post-creation selection fails separately: A33 |
| Login | Sign in, refresh and log out **passed** for a synthetic account | UI session lifecycle works; existing replay/revocation finding A06 remains open |
| Sandbox isolation | Unprivileged execution, zero capabilities, no-new-privileges, read-only root/inbox, absent private store/socket and network denial **passed** | Network denial has a successful network-enabled control. A failed container launch cannot count as successful isolation |
| Sandbox useful output | **Failed** with EACCES writing `/work/result.txt` | A32: host-directory permissions prevent the actual container user from writing its promised output |
| Browser approval | **Failed**: local form became SUBMITTED while needs_confirmation=False | A09 is now demonstrated with a real Enter-handler form. No external message was sent |
| Real video export and decoding | **VP9/WebM encoding and decoding passed; server acceptance failed** | The default Colour clip produces a valid 60-frame, 1080×1920, two-second file. Its 3,773 bytes trigger a false minimum-size rejection: A34 |
| Connectors Gmail panel | **Failed**, HTTP 404 from `/api/v1/status` | A35: the panel uses a missing route; the implemented `/api/v1/settings/status` endpoint responds successfully |

The runtime was Python **3.12.14**, **Google Chrome 152.0.7977.64**, Docker **28.0.4** and PostgreSQL **16.15**, running as host UID **1001**. Chrome's sandbox remained enabled. The tool container used the immutable image `python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`. Independent media decoding used **ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers**. Exact per-case results, versions, screenshots, server logs, exported WebM and decoder outputs are preserved in the bundle.

The shared-workspace video journey also failed in earlier completed runs: one produced an actual SQLite InterfaceError/HTTP 500; another returned campaign-not-found for a newly created, visible campaign while sibling requests for it succeeded. Both are preserved. The precise scheduling trigger of those live connection failures remains to be isolated when fixing A02; the original deterministic transaction-rollback reproduction already proves unsafe shared transaction ownership. Successful later loading does not close those failures.

The browser screenshots were inspected for the failing campaign and video paths. This is real automated Chrome interaction plus targeted visual inspection, not a claim of comprehensive accessibility, cross-browser, mobile, audio, arbitrary-media, performance or production-host acceptance. The tool-container probes cover the listed boundaries; they do not certify resistance to every kernel/container exploit or prove the separately deployed BrowserBox runtime.

### External-provider checks and exact remaining access

The accessible audit checkouts and runtime did not contain configured application provider credentials at the known application configuration locations. A separate, temporary actual application was started to verify its truthful missing-configuration behaviour. This is **not** evidence that the company's deployed installation lacks credentials.

| Integration | Check actually performed | Result and missing requirement |
|---|---|---|
| Apollo connected app | Read-only authenticated profile request | **Authentication passed for the connector.** Its credential is not the CRM's separate APOLLO_API_KEY and cannot establish application enrichment success |
| Apollo CRM adapter | Application adapter initialisation/configuration check | Correctly refuses missing APOLLO_API_KEY. Needs the key configured securely in the test application and bounded synthetic enrichment inputs |
| Gmail | Actual `/settings/status` response | gmail_configured=False in the audit workspace. Needs application OAuth/test-mailbox configuration; delivery/reply acceptance also needs an explicitly authorised test recipient |
| SES / durable email | Actual delivery-identities response | Zero configured identities in the audit workspace. Needs a test AWS/SES identity, permissions/region and safe recipient; no delivery or SNS receipt is claimed |
| Notion | Actual settings and connection-test endpoints | Disconnected; `/notion/test` returns actionable 422. Needs an integration token and authorised test databases |
| All 17 AI provider configurations | Actual discover-models endpoints | All returned source=config, with **zero authenticated application-provider successes**. HTTP 200 with a configured model catalogue is not a live model-provider test. Needs keys for the supported providers or reachable self-hosted model endpoints |
| YouTube | Application client configuration check | Refuses the missing Data API key. Needs a configured test key before live data acceptance |
| Social publishing | Implementation review and existing tests | Live platform publishing/readback is not implemented: A27. Credentials alone cannot complete a missing adapter |

**To finish authenticated application-provider and deployed-environment acceptance:** supply the staging URL and configure the intended test accounts/keys through the application's Settings or deployment environment. Do not paste keys into chat. Sending tests also require an explicitly authorised recipient and operation. Connector availability does not grant the application those credentials.

Company-host TLS/proxy configuration, production database permissions/backups, full deployed BrowserBox/runtime packaging, real worker supervision, load/soak targets, alerts and infrastructure restart/restore remain separate release gates because that deployment is not accessible here. Their status is recorded as missing deployment evidence, not as failed local tests or successful provider integrations.


## Historical baseline and other verification results

The local results below are retained for reproducibility and coverage provenance. Their 23 environment skips were subsequently executed in the real-service run above; they are not current browser/database/container execution blockers.

| Check | Result | What it establishes |
|---|---|---|
| Full existing Python suite | **1,574 passed; 23 skipped** | Existing behaviour under the test environment; no baseline failures |
| Fresh complete run with coverage | **1,574 passed; 23 skipped** | The coverage measurement comes from a completed suite |
| Python statement coverage | **80.19%** — 17,415 / 21,717 statements | Line execution coverage, not branch coverage, security assurance or user acceptance |
| Existing frontend suite | **116 passed across 8 files** | Node-based component/rendering and video algorithm checks |
| Frontend production build | **Passed** | TypeScript compilation and Vite production bundling |
| Ruff gate | **Passed** | The repository's E9/F63/F7/F82 syntax/name checks; not a full static-security review |
| Nine installed CLI entry points | **All `--help` checks passed** | Entrypoint packaging and import smoke checks, not live command workflows |
| Board verifier | **Passed in the project environment** | The current board conforms to its verifier; does not reconcile every prose map or prove live integrations |
| Empty-workspace GET sweep | **87 requests; 48 × 200, 35 × 404, 4 × 422; no 5xx** | Read-route startup/missing-ID behaviour; 404/422 are expected for synthetic missing IDs or required inputs |
| Python dependency audit | **No known vulnerabilities reported** | Advisory scan of the installed environment, including audit tooling; not a scan of a built production image |
| Frontend dependency audit | **1 high + 1 moderate advisory** | Affected build dependency versions are present; see A31 for exposure limits |
| New Python audit regressions | **31 failures, 0 skips, 0 fixture errors** | Assertions of required production behaviour fail on the audited snapshot |
| New frontend audit regression | **1 failure** | Token authentication is dropped by the audio loader |
| PLAN branch targeted tests | **12 passed** | PLAN and RunLoop tests on the separate branch |
| Page-cache branch targeted tests | **20 passed; 2 browser cases skipped** | Cache, RunLoop and claim-verification tests on that separate branch |

The historical 23 main-suite skips comprised **19 browser cases, 3 PostgreSQL cases and 1 live sandbox egress case**. Enabling the PostgreSQL service also adds 14 parameterised cases, giving 1,611 passing existing tests in the live run. The earlier coverage run measured browser CDP/page code at roughly 24–26%, Gmail at about 32% and Apollo at about 37%. Those coverage percentages were not recalculated for the live run. BrowserBox's earlier 100% line coverage included command-construction tests; line coverage alone does not establish container runtime safety. The full historical per-file coverage report is in the evidence bundle.

## Findings at a glance

| ID | Priority | Finding | Evidence |
|---|---|---|---|
| A01 | P0 | The supplied hosted deployment discards customer state | Source/configuration confirmed |
| A02 | P0 | Concurrent CRM transactions can roll back each other's work | Reproduced |
| A03 | P1 | Backup restore breaks sales, delivery and AI chats—even when the archive is rejected | Reproduced |
| A04 | P1 | The backup cannot recover the full workspace and can exceed its own restore limit | Reproduced |
| A05 | P1 | Company users have no individual identity or enforced permissions | Source confirmed |
| A06 | P1 | Logging out does not revoke the session | Reproduced |
| A07 | P1 | The browser network guard permits private-network addresses | Reproduced at the policy boundary |
| A08 | P1 | The public-page fetcher is vulnerable to DNS rebinding | Reproduced with a local HTTP fixture |
| A09 | P1 | Enter can bypass the browser's consequential-action confirmation | Reproduced in real Chrome |
| A10 | P1 | The AI dollar-spend cap is not accounted for | Reproduced |
| A11 | P1 | Quota checks race and separate processes overwrite usage | Reproduced at the accounting boundary |
| A12 | P1 | The AI cache can return an old answer after the facts change | Reproduced |
| A13 | P1 | A cached answer can be falsely attributed to the newly selected model | Reproduced |
| A14 | P1 | HTTP idempotency permits duplicate operations under a race | Reproduced |
| A15 | P1 | Media uploads bypass the configured size limit and read the whole file into memory | Reproduced |
| A16 | P1 | Provider construction failure strands a durable email job | Reproduced |
| A17 | P1 | Readiness stays green when required product components are unavailable | Reproduced |
| A18 | P1 | Claim verification accepts the wrong numeric value | Reproduced |
| A19 | P1 | Enrichment exports turn untrusted text into spreadsheet formulas | Reproduced |
| A20 | P2 | API-token authentication breaks media loading and misreports login status | Reproduced with frontend and API tests |
| A21 | P2 | Image quality gates accept corrupt data and can raise on malformed headers | Reproduced |
| A22 | P2 | Several write APIs lack typed validation and malformed input produces 500 | Reproduced; wider surface inventoried |
| A23 | P2 | The contact screen stops at 500 rows without pagination | Source confirmed |
| A24 | P1 | There is no complete customer-data deletion and retention workflow | Source/API inventory confirmed |
| A25 | P1 | The deployment does not run the durable email worker; other automation is process-local | Source/configuration confirmed |
| A26 | P1 | The Docker build omits feature dependencies and does not reproduce the Python lock | Source/configuration confirmed |
| A27 | P1 | Real social publishing and engagement feedback are not implemented | Source and board confirmed |
| A28 | P1 | The autonomous browser work is not yet a complete customer workflow | Source/API inventory and branch tests confirmed |
| A29 | P1 | Release evidence omits important live integrations and operational failure checks | Test execution and configuration confirmed |
| A30 | P2 | The source-of-truth documents and login copy still contradict the production direction | Source and board comparison confirmed |
| A31 | P2 | Two frontend build dependencies have published advisories | npm audit and installed dependency tree confirmed |
| A32 | P1 | The sandbox's advertised writable output directory rejects writes | Reproduced in real Docker |
| A33 | P1 | Creating a campaign can silently select an older campaign | Reproduced in real Chrome |
| A34 | P2 | The editor's default Colour clip fails its own export acceptance gate | Reproduced through real browser export |
| A35 | P2 | Connectors loads Gmail status from a nonexistent API route | Reproduced in live HTTP and Chrome |

## Feature-by-feature production readiness

All rows inherit the storage, access, recovery and release requirements above. “Tested” below means the automated scope recorded in this report, not a completed live customer acceptance test.

| Area | What is built | Production status and missing work |
|---|---|---|
| Application shell, dashboard and settings | React navigation, campaign selection, status/settings APIs, cookie or API-token access | All 18 screen shells render in real Chrome. Login/refresh/logout works for the synthetic account. Individual users/permissions, session revocation, correct campaign selection and production deployment remain incomplete: A01, A05, A06, A20, A30, A33. Shell rendering does not establish every screen's functionality. |
| Contacts and intake | CSV/Excel intake, mapping/deduplication, contact editing, search/filtering, controlled source intake including PDF paths | Actual CSV import, search and reload pass when the campaign is explicitly selected; an API read confirms the correct association. Automatic selection after creation fails separately. Shared transactions, complete browsing, export safety and lifecycle need work: A02, A19, A23, A24, A33. Customer-format and large-file acceptance remains necessary. |
| Campaign lifecycle | Email, image and distribution kinds with kind gates | Creation, pause and reload persist in real Chrome. Newly created campaigns can lose selection: A33. Video projects belong to the **image** campaign kind; there is no separate `video` kind. Durable idempotency and request validation also need work: A14, A22. |
| Email drafts and templates | Generation, template variants, human approval, local outbox, follow-up scheduling, stop-on-reply logic | Important safety checks exist and are tested. Shared storage, quotas/cache semantics and unattended operation need the fixes below. Provider rendering/live mail acceptance remains unverified. |
| Gmail | OAuth/local credentials, confirmed sending, reply sync and CRM status updates | Real Gmail transport is not exercised here. Preserve the distinction between CRM reply sync and AI access: the AI egress/recall design is intended to exclude received mailbox content. Team identity and deployment credential lifecycle still need work. |
| Durable email / deliverability | SES adapter code, snapshotted queue, leases, suppression, permission records, preflight, domain checks, signed SNS feedback, unsubscribe links | Strong deterministic tests, including ambiguous-send quarantine. Production worker deployment, runtime dependencies, provider construction errors and recovery remain blockers: A03, A04, A16, A25, A26. SES/DNS/SNS acceptance needs an authorised environment. |
| Sales tracker | Board, leads, stage changes, events, filters, forecasting and conflict handling | Existing tests pass. Restore breaks its store, shared writes are unsafe, and staff permissions/large-list handling are missing: A02, A03, A05, A23. No real-user concurrency/load acceptance. |
| Lead discovery / enrichment | Apollo client, local ledgers and scoring, public fetcher, Scrapling parser, optional Crawl4AI route | Existing tests cover parsing, caps and refusals. DNS rebinding and formula export are reproduced defects: A08, A19. Apollo connector account authentication passed; the CRM adapter correctly refuses its absent APOLLO_API_KEY. Actual application enrichment and optional crawler runtime acceptance still need configured test access. |
| Notion connector | Encrypted settings and controlled sync/upsert code | Controlled transport tests pass. The running application reports disconnected and refuses its connection test with an actionable 422 because no token is stored. Live workspace permission/rate-limit/reconciliation acceptance needs a test token and database. Recovery remains part of A04, A24, A29. |
| AI connectors and egress | Configured providers/models, tier/data-class rules, payload construction, scanning, permitted routing/failover and egress logs | Actual discovery endpoints for all 17 configured providers return configuration fallback; no application keys or reachable self-hosted service were configured. HTTP 200 is not authenticated provider success. Financial controls and identity remain incomplete: A05, A10, A11. Connectors also calls a missing Gmail status endpoint: A35. |
| AI Studio, model comparison and experiments | Selection, compare/chaining modes, eval tools, bandit/scoreboard mechanisms and verification helpers | Existing tests pass, but cached model attribution and changed-fact reuse invalidate important trust assumptions: A12, A13. Actual paid/provider model behaviour was not tested. |
| AI chat, projects, memory and recall | Chat/project storage, context layer, sent-mail recall, cache management and index forget actions | Restore breaks chat services; whole-product deletion is absent; near-cache reuse can return stale facts: A03, A12, A24. Existing sent-mail privacy/egress checks should be preserved. |
| Image studio and review | Briefs, multi-provider candidates, header/size/aspect/hash gates, review decisions and generator statistics | The no-campaign screen renders in Chrome. Corrupt-image acceptance, malformed-header crashes, malformed-body 500s and token-auth media loading remain defects: A20, A21, A22. Provider-generated image and review acceptance needs configured test models. |
| Video editor | Persistent timelines/history/undo, trim/split/retime, effects/transitions, audio mixing, captions, recipes/director, browser export, server render gates and review | Actual browser creation/edit/export ran in a fresh workspace; the default Colour export fails the minimum-size gate: A34. Shared-workspace loading also produced a SQLite 500 and a false campaign-not-found response. Upload limits, token media access and recovery remain A02, A04, A15, A20. Detailed codec evidence and its limits are above; complex media, audio, other browsers and performance remain release acceptance. |
| Distribution / posting | Local accounts/posts, approval/schedule state, local publisher, content pipeline, goals and pacing | Local artifacts are real test outputs, but live platform publishing/readback is not implemented: A27. Durable scheduling, production state and external receipts/reconciliation are needed: A01, A25. |
| Trends and content generation | Topic/trend store, YouTube public-data code, planning/drafting pipeline and in-process automation | Synthetic/client tests pass. Real competitor coverage, data freshness, scale, worker ownership and provider/account acceptance are not proved: A25, A27, A29. |
| Browser box, sign-in, vault and revocation | Hardened command construction, profile/session management, encrypted vault and revoke/forget components, pacing/budgets | The 19 existing real-browser cases now run. A real Enter-handler form submits without approval: A09. Private-network policy remains A07. Docker tool isolation checks passed within the recorded scope; the complete deployed BrowserBox image/profile/vault/sign-in lifecycle still needs its own acceptance. |
| Autonomous RunLoop and results | Bounded action loop, structured result schema, provenance and claim verification on main | Numeric verification is wrong in demonstrated cases: A18. Customer run UI, persisted recovery/approval/resume and adversarial-page acceptance are incomplete: A28. |
| PLAN.md and page-read cache | Separate branch implementations with targeted tests | These are **not part of the audited main snapshot**. See the branch table below; passing their tests does not establish a merged end-to-end feature. |
| Sandbox, tool registry, notebook and code graph | Policies, discovery/introspection helpers, export and command-line interfaces | Real Docker probes prove unprivileged startup, removed capabilities, no-new-privileges, read-only root/inbox, absent private store/socket and network denial with a working positive control. Writing the promised /work output fails: A32. Complete runtime packaging and release gates remain A26, A29. |
| Data backend, backup, deployment and release | SQLite stores; PostgreSQL abstraction used by selected stores; encrypted legacy backup; Docker/Render/Compose and CI | Seventeen real PostgreSQL cases pass, covering egress logs/migration and video persistence/history/JSON. The PostgreSQL switch remains partial; this does not test the company's deployed database. Durability, transaction boundaries, full restore, worker topology, monitoring and release gates remain A01–A04, A17, A25, A26, A29. |

## Separate branch review

| Branch | Audited commit | Scope | Result and limit |
|---|---|---|---|
| `feature/s-02-02-02-plan-md` | `0c2a04a54694a8e30d8dd15c41a20b21aa44103e` | Owner-editable fixed PLAN.md, guarded file reads, RunLoop integration | 12 targeted tests passed. Reviewed as an unmerged implementation. No UI or live browser acceptance. |
| `feature/s-11-02-04-page-read-cache` | `253449965c1f4313d90c08d10225e1de858e9f6c` | Run-scoped read cache, conservative URL normalization, invalidation rules and RunLoop changes | 20 targeted tests passed; 2 browser cases skipped. No claim of merged behaviour or live-page freshness correctness. |

Both branches change RunLoop. Their integration with each other and current main needs a merge/rebase review and a combined suite. The audit did not merge them or treat branch-only behaviour as shipped. The separate page-read cache is also distinct from the AI response-cache defects in A12/A13.

## Detailed findings and acceptance criteria

### A01 · P0 · The supplied hosted deployment discards customer state

**Classification:** Production gap. **Evidence:** Source/configuration confirmed.

**What was found.** render.yaml selects a free web service, writes OFFSETX_DATA_DIR and the CRM SQLite database under /tmp, and auto-deploys main. The Docker volume at /app/local_data does not cover those overridden paths. OFFSETX_DATABASE_URL is used for the egress log and video documents; it does not migrate the CRM, image/distribution stores, credentials or media files.

**Why it matters.** A restart or replacement of this service can remove CRM records, credentials, generated assets and operational history. This is a release blocker for customer data. The audit did not inspect the live hosting account or observe an actual customer loss.

**Required fix.** Provide an explicitly production deployment with durable databases and asset storage, stable secret management, backups and a tested upgrade/rollback path. Keep the modular monolith if useful; microservices are not required. Inventory every state location before moving anything.

**Acceptance.** Create records, media and credentials in a fresh production-shaped environment; restart, redeploy and replace the instance; verify all records and assets survive. Prove restoration into an empty environment and declare recovery time/data-loss targets.

**Source:** [render.yaml:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/render.yaml#L1), [Dockerfile:8](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/Dockerfile#L8), [offsetx_apollo_builder/api/app.py:304](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L304).

**External verification:** [Render free-service limitations](https://render.com/docs/free).

### A02 · P0 · Concurrent CRM transactions can roll back each other's work

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** OutreachStore shares one SQLite connection with check_same_thread=False. Its transaction context starts and rolls back transactions without a connection-wide lock. In a deterministic two-thread test, writer A inserted a row; writer B's nested BEGIN failed and rolled back A's transaction; A then completed with zero rows persisted. The real Chrome run at verification commit 54d18fab8a3b also received HTTP 500 while creating/loading a video project. Its server trace ends in OutreachStore._row -> connection.execute with sqlite3.InterfaceError: bad parameter or other API misuse. The frontend makes parallel project, image, media and queue requests. This is an additional live failure on the shared-connection path; the deterministic rollback test remains the proof of transaction interference. The precise scheduling trigger of the live InterfaceError was not separately isolated.

**Why it matters.** A successful-looking write can disappear. FastAPI handlers and services share this store; separate engine/service locks do not establish one transaction boundary across all callers.

**Required fix.** Use a connection per transaction/request or one correctly shared transaction lock as appropriate for the supported topology. Define transaction ownership and eliminate access that bypasses it. A team-hosted topology should use a database design that supports its actual concurrency.

**Acceptance.** Run interleaved CRM and sales/delivery writes, failure injection and concurrent API requests. No transaction may commit or roll back another request's work; acknowledged writes must remain durable.

**Source:** [offsetx_apollo_builder/outreach/store.py:29](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/store.py#L29), [offsetx_apollo_builder/outreach/store.py:52](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/store.py#L52), [offsetx_apollo_builder/api/app.py:309](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L309).

**Reproduction:** `test_failed_concurrent_transaction_cannot_rollback_another_writer`.

**Saved live evidence:** `live-integration-final/frontend-server.log`, `live-integration-final/test_video_editor_exports_a_real_webm_and_passes_server_gates.png`, `live-integration-complete/test_video_editor_exports_a_real_webm_and_passes_server_gates.png`.

### A03 · P1 · Backup restore breaks sales, delivery and AI chats—even when the archive is rejected

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** Restore closes the current engine and replaces only app.state.engine. SalesTracker, AIChatService and EmailDeliveryService retain the closed store. After a successful restore, /sales/board, /email-delivery/jobs and /ai/chats return 500. Uploading an invalid archive returns 422 but still breaks the existing sales service. The maintenance lock is not a gate for normal requests.

**Why it matters.** The recovery operation itself leaves an active installation partly unusable. Requests or content automation can overlap the swap. Reopening only the engine does not restore the complete service graph or delivery wiring.

**Required fix.** Validate the archive before touching live services. Drain requests and both background services, restore atomically, rebuild and reconnect every dependent service, and resume only after health checks pass. Make rollback restore the complete previous state.

**Acceptance.** Successful and rejected restores must leave all product routes usable. Test restore with active requests and background work, provider/preflight wiring, failures at every replacement step and application restart.

**Source:** [offsetx_apollo_builder/api/app.py:921](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L921), [offsetx_apollo_builder/api/app.py:309](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L309).

**Reproduction:** `test_restore_keeps_dependent_services_working`; `test_rejected_backup_does_not_break_the_existing_workspace`.

### A04 · P1 · The backup cannot recover the full workspace and can exceed its own restore limit

**Classification:** Bug and production gap. **Evidence:** Reproduced.

**What was found.** The encrypted archive includes outreach.db and four legacy settings files. It omits AI context/recall/egress, imagery/distribution/video stores, generated media and email_unsubscribe.key, among other state. The UI describes a limited CRM/settings backup, but full-product recovery is absent. A database with an 8 MiB incompressible synthetic record produced an approximately 11.2 MB backup which export accepted and restore rejected with 413 under default settings.

**Why it matters.** A machine-loss recovery cannot restore the whole product. Losing the unsubscribe signing secret can invalidate already-issued links. Backup success does not mean that the resulting file is restorable.

**Required fix.** Define and version a complete backup manifest across databases, assets, settings and secrets, explicitly distinguishing rebuildable caches from durable state. Make export/restore limits consistent and use bounded streaming. Include retention, encryption, key recovery and integrity checks.

**Acceptance.** Restore a fully populated installation into an empty directory or replacement host. Compare records, files, settings and hashes; verify old unsubscribe links. Repeat beyond the present 10 MiB upload limit and inject partial failures.

**Source:** [offsetx_apollo_builder/outreach/backup.py:23](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/backup.py#L23), [offsetx_apollo_builder/api/app.py:928](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L928), [frontend/src/pages/Settings.tsx:411](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Settings.tsx#L411).

**Reproduction:** `test_backup_includes_new_durable_stores_and_unsubscribe_secret`; `test_backup_export_can_be_restored_under_default_upload_limits`.

### A05 · P1 · Company users have no individual identity or enforced permissions

**Classification:** Production gap. **Evidence:** Source confirmed.

**What was found.** The web app has one configured username/password or one shared API token. _workspace_id returns 'local'. API access is a single authenticated/unauthenticated decision; there is no per-user membership or role check for contacts, settings, credentials, exports, deletion, approval or sending.

**Why it matters.** A company cannot give staff separate access, remove one person reliably, or attribute consequential actions to the actual employee. Library-level workspace parameters do not create isolation at the web boundary.

**Required fix.** Implement individual accounts or an identity provider, membership and server-side permissions. Resolve workspace identity from authentication and enforce it consistently. One company installation can remain single-tenant; separate employee identities are still required.

**Acceptance.** Use two real test users with different roles. Exercise all API operations and cross-user/workspace IDs. Verify forbidden reads, exports, credential changes and sends fail, and actions record the responsible user.

**Source:** [offsetx_apollo_builder/api/auth.py:31](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/auth.py#L31), [offsetx_apollo_builder/api/app.py:461](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L461), [offsetx_apollo_builder/api/app.py:2221](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L2221).

### A06 · P1 · Logging out does not revoke the session

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** Logout deletes the browser cookie but does not invalidate the signed session token. Replaying the captured pre-logout cookie after logout still accesses /dashboard with HTTP 200.

**Why it matters.** A copied session remains usable until expiry. Logging out cannot terminate an exposed session, and the existing nonce has no server-side revocation record.

**Required fix.** Use revocable server-side sessions or a durable session/version revocation mechanism. Revoke on logout and security events, with scoped token rotation rather than relying only on browser deletion.

**Acceptance.** Replay a logged-out or administratively revoked session from a second client and after a server restart; it must fail. Keep valid unrelated sessions working according to the intended policy.

**Source:** [offsetx_apollo_builder/api/auth.py:60](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/auth.py#L60), [offsetx_apollo_builder/api/app.py:584](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L584).

**Reproduction:** `test_logout_revokes_the_previous_session`.

### A07 · P1 · The browser network guard permits private-network addresses

**Classification:** Bug. **Evidence:** Reproduced at the policy boundary.

**What was found.** RequestGuard in attended mode allows http://10.0.0.1, http://192.168.1.1, http://172.17.0.1 and http://[fd00::1]. check_navigation uses a short exact-host list, not complete IP-range or resolved-address checks. BrowserBox enables Docker bridge networking; its command does not add private-network egress filtering.

**Why it matters.** An agent or a hostile page can target internal services where the browser runtime can reach them. Container filesystem isolation does not establish a network boundary. No live internal service was probed by these policy tests.

**Required fix.** Enforce private, loopback, link-local, reserved and metadata destination blocking across IPv4, IPv6 and DNS resolution. Apply network-level restrictions as well as browser policy, including redirects, subresources, workers and new tabs.

**Acceptance.** Run real-browser and container tests against controlled private-network fixtures, DNS changes and alternate address forms. Verify no request leaves to forbidden destinations in either attended or unattended mode.

**Source:** [offsetx_apollo_builder/browser/policy.py:206](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/browser/policy.py#L206), [offsetx_apollo_builder/browser/guard.py:91](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/browser/guard.py#L91), [offsetx_apollo_builder/browser/box.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/browser/box.py#L1).

**Reproduction:** `test_browser_network_guard_blocks_private_network_destinations`.

### A08 · P1 · The public-page fetcher is vulnerable to DNS rebinding

**Classification:** Bug. **Evidence:** Reproduced with a local HTTP fixture.

**What was found.** SafePublicFetcher validates DNS, then requests the original hostname through a transport that resolves it again. A test returned a public IP to the validation resolver and loopback to the connection resolver. The fetcher then read a synthetic private-only HTTP endpoint.

**Why it matters.** A hostname controlled by an attacker can pass the public-host check and subsequently direct the crawler to an internal service. Redirect checks and request size limits do not fix this resolution race.

**Required fix.** Bind the connection to the validated destination addresses while preserving the correct Host header and TLS verification, or use an egress proxy that enforces the destination policy. Repeat validation on redirects and connection changes.

**Acceptance.** The included loopback rebinding test must be blocked before connection. Add redirect, IPv6, mixed public/private answers and connection-pooling cases without contacting real internal or metadata services.

**Source:** [offsetx_apollo_builder/discovery.py:382](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/discovery.py#L382), [offsetx_apollo_builder/discovery.py:410](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/discovery.py#L410).

**Reproduction:** `test_public_fetcher_does_not_connect_to_private_ip_after_dns_changes`.

### A09 · P1 · Enter can bypass the browser's consequential-action confirmation

**Classification:** Bug. **Evidence:** Reproduced in real Chrome.

**What was found.** click classifies the target and checks confirmation. press('Enter') dispatches key events without checking the focused form or invoking the consequential-action gate. RunLoop explicitly allows press. The original transport-double regression records needs_confirmation=False. A real Chrome 152 test now confirms the effect: a synthetic composer form with an Enter keydown handler calling requestSubmit changed from UNSENT to SUBMITTED, while Page.press returned ok=True and needs_confirmation=False. Its submit handler changes only local page text; no real message or network submission occurred. An earlier plain native form remained UNSENT; this evidence establishes the bypass for an Enter-handler form, not every browser form implementation.

**Why it matters.** Keyboard activation can execute page-defined submission logic without the approval required for the corresponding consequential click. Real sending, posting, purchasing and deletion were deliberately not performed; the live controlled submission demonstrates the missing action gate.

**Required fix.** Put consequential-action approval at a boundary shared by every input path. Inspect focused controls and form intent, bind approval to the exact action and target, and fail closed when intent is unknown. Include keyboard activation and non-English/custom controls.

**Acceptance.** Use controlled real-browser forms for Enter, Space and click. Each consequential operation must require explicit, action-bound approval, including after navigation or DOM changes. A model must not manufacture the approval.

**Source:** [offsetx_apollo_builder/browser/page.py:299](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/browser/page.py#L299), [offsetx_apollo_builder/browser/page.py:457](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/browser/page.py#L457), [offsetx_apollo_builder/agent/run.py:959](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/agent/run.py#L959).

**Reproduction:** `test_enter_requires_confirmation_before_possible_form_submission`; `test_enter_on_a_real_form_requires_confirmation`.

**Saved live evidence:** `live-integration-final/acceptance.xml`.

### A10 · P1 · The AI dollar-spend cap is not accounted for

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** The broker records text calls with spend_usd=0.0. Other generation paths default to zero accounting. A successful synthetic call through a paid-provider configuration increases usage but leaves day_spend_usd at zero despite a configured dollar cap. RunLoop's cost estimate is not a quota reservation.

**Why it matters.** The displayed/configured daily dollar cap does not act as a reliable spending limit. Calls can continue while the local spend counter remains zero.

**Required fix.** Capture billable usage or a conservative priced estimate, reserve budget before starting, and reconcile after completion. Handle unknown pricing, failed requests, retries and image/audio costs explicitly. Show estimated versus provider-confirmed costs.

**Acceptance.** Use priced provider fixtures to cross a small dollar budget. The next request must be refused before transport, including under concurrency, failover and restart. Unknown costs must not silently count as free.

**Source:** [offsetx_apollo_builder/ai/broker.py:634](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/broker.py#L634), [offsetx_apollo_builder/ai/quota.py:145](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/quota.py#L145).

**Reproduction:** `test_paid_provider_calls_record_spend_toward_the_configured_dollar_cap`.

### A11 · P1 · Quota checks race and separate processes overwrite usage

**Classification:** Bug. **Evidence:** Reproduced at the accounting boundary.

**What was found.** check and record are separate operations. Two overlapping checks pass a one-request limit before either records. Two QuotaTracker instances load the same JSON state once, each record a call, and leave a persisted count of one rather than two. Corrupt counters reset to empty and save errors are suppressed.

**Why it matters.** Concurrent requests, workers or a restart after a failed write can undercount use and exceed provider/request budgets. A per-instance thread lock does not coordinate different processes.

**Required fix.** Use a durable atomic reservation ledger keyed by the correct workspace/account/provider budget. Make persistence failures explicit and preserve accounting across processes. Define how retries and reservations expire.

**Acceptance.** Run simultaneous broker calls and independent workers against a one-call budget; only one may proceed. Repeat with process crashes, disk failure, corrupted state and restart, verifying that usage cannot reset silently.

**Source:** [offsetx_apollo_builder/ai/quota.py:85](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/quota.py#L85), [offsetx_apollo_builder/ai/quota.py:145](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/quota.py#L145).

**Reproduction:** `test_quota_reservation_blocks_overlapping_requests_at_the_limit`; `test_separate_quota_trackers_do_not_lose_each_others_counts`.

### A12 · P1 · The AI cache can return an old answer after the facts change

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** Near-match caching uses word-triple similarity with a 0.92 threshold for factual tasks. Changing a document's revenue from 42 million to 420 million still produced a near-cache hit, similarity approximately 0.981, returning '42 million'.

**Why it matters.** Extraction, classification, enrichment and other cached work can silently reuse an answer to different evidence. A high text similarity score does not establish factual equivalence.

**Required fix.** Use exact content identity for factual decisions unless there is a proven task-specific equivalence rule. Include the source version and relevant parameters in the key. Do not treat numerical or negation changes as harmless formatting.

**Acceptance.** Test changed numbers, units, negation, dates, entities and instructions in long otherwise-similar documents. Every meaningful change must miss the old cache and preserve correct source attribution.

**Source:** [offsetx_apollo_builder/ai/cache.py:67](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/cache.py#L67), [offsetx_apollo_builder/ai/cache.py:311](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/cache.py#L311).

**Reproduction:** `test_near_match_cache_does_not_reuse_an_answer_after_a_numeric_fact_changes`.

### A13 · P1 · A cached answer can be falsely attributed to the newly selected model

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** The cache partition distinguishes providers but not models. The broker returns the cached text with candidate.model_id rather than the model that generated it. Selecting a Phi model, then a Llama model on NVIDIA for the same request, returned Phi's answer labelled as Llama; only Phi was called.

**Why it matters.** Model selection, model comparisons and the audit trail become misleading. A user paying for or validating a particular model may receive an answer generated by another one.

**Required fix.** Include model identity, generation settings and system-prompt/version identity in cache eligibility, or preserve original provenance where cross-model reuse is explicitly intended. Never label an uncalled model as the generator.

**Acceptance.** Repeat the same task across two models on the same provider and across changed system instructions. Verify the requested model runs when required, and every cache hit displays and logs its actual origin.

**Source:** [offsetx_apollo_builder/ai/cache.py:210](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/cache.py#L210), [offsetx_apollo_builder/ai/broker.py:575](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/broker.py#L575).

**Reproduction:** `test_cached_answer_is_not_reattributed_to_a_different_model`.

### A14 · P1 · HTTP idempotency permits duplicate operations under a race

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** _idempotent performs a cache lookup, executes the operation, then saves the result. Two concurrent operations on separate engines using the same scope and key created two campaigns and returned different IDs. The persistence method uses INSERT OR REPLACE rather than an atomic operation reservation.

**Why it matters.** Client retries or multiple workers can duplicate state-changing operations even when the caller supplies an Idempotency-Key. This finding concerns the generic API helper; the mail sender has separate duplicate-send protections.

**Required fix.** Reserve the key atomically before execution, bind it to the request fingerprint and principal, and persist operation state/result transactionally. Define in-progress retries, crash recovery and conflicting reuse of the same key.

**Acceptance.** Issue simultaneous identical requests across multiple workers and simulate a crash after mutation but before response. Produce one effect and a consistent replay; reject the same key with a different payload.

**Source:** [offsetx_apollo_builder/api/app.py:250](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L250), [offsetx_apollo_builder/outreach/store.py:1378](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/store.py#L1378).

**Reproduction:** `test_one_idempotency_key_creates_only_one_campaign_under_race`.

### A15 · P1 · Media uploads bypass the configured size limit and read the whole file into memory

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** Video media and render endpoints call await file.read() without a bound. An 8,236-byte WAV upload was accepted with HTTP 201 when max_upload_bytes was 2,048. Other upload paths apply the configured limit.

**Why it matters.** Large or concurrent uploads can consume application memory and disk beyond the stated limit. This is an availability issue; the audit did not deliberately exhaust memory.

**Required fix.** Set explicit media and overall request limits, validate them while streaming, and store large files outside the web process's heap. Bound concurrent processing, disk usage, decoded dimensions and duration; clean up aborted uploads.

**Acceptance.** Oversized and chunked uploads must fail predictably before full buffering. Test interrupted uploads and concurrent uploads with memory/disk measurements, using limits appropriate for real video rather than reusing a small document limit blindly.

**Source:** [offsetx_apollo_builder/api/app.py:1362](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L1362), [offsetx_apollo_builder/api/app.py:1455](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L1455).

**Reproduction:** `test_media_upload_obeys_the_configured_upload_limit`.

### A16 · P1 · Provider construction failure strands a durable email job

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** EmailDeliveryService claims a job, then calls provider_factory outside its send exception handler. A synthetic PermanentDeliveryError from provider construction leaves the job in 'sending' even though no send was attempted. The worker cycle raises instead of recording the definite pre-send failure.

**Why it matters.** Missing provider dependencies or invalid setup can block queued mail and later present a misleading delivery-unknown state. Other jobs in the cycle may not get processed.

**Required fix.** Include provider acquisition and pre-send setup in the classified worker lifecycle. Persist definite pre-send failures distinctly from ambiguous post-send failures, release/finish the claim safely, and continue processing unrelated jobs.

**Acceptance.** Inject missing dependencies, invalid credentials/configuration and provider factory errors before transport. The job must become a truthful failed/blocked/retryable state, with no false send ambiguity and no duplicate delivery.

**Source:** [offsetx_apollo_builder/outreach/deliverability/service.py:308](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/deliverability/service.py#L308), [offsetx_apollo_builder/outreach/deliverability/service.py:354](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/deliverability/service.py#L354).

**Reproduction:** `test_provider_construction_failure_does_not_strand_an_email_job`.

### A17 · P1 · Readiness stays green when required product components are unavailable

**Classification:** Bug and production gap. **Evidence:** Reproduced.

**What was found.** /health/ready checks only SELECT 1 on the CRM engine. Closing the image store still returns HTTP 200 with status ready. The restore failures also leave several services broken while the replacement engine can answer this query.

**Why it matters.** A deployment can be marked healthy and continue receiving users while major workflows fail. The current check does not cover required stores, writable asset storage or worker progress.

**Required fix.** Separate liveness from component readiness and operational health. Check the dependencies required for the enabled feature set with bounded checks, and expose actionable degraded states. Monitor worker heartbeat/queue age separately from basic web availability.

**Acceptance.** Inject unavailable stores, read-only/full asset storage and stalled workers. The relevant health signal must fail or show degradation and trigger the configured alert without making optional provider outages unnecessarily take down the whole app.

**Source:** [offsetx_apollo_builder/api/app.py:523](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L523), [render.yaml:10](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/render.yaml#L10).

**Reproduction:** `test_readiness_detects_unavailable_required_product_stores`.

### A18 · P1 · Claim verification accepts the wrong numeric value

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** The verifier marks value '42' as supported by each of 'Revenue is -42.', 'Revenue is 42.7.' and 'Revenue is 42,000.'. Its text-span matching does not preserve the numeric sign, decimal or magnitude.

**Why it matters.** Structured research can present an incorrect number as verified. A traceable quotation is useful evidence, but the current check is insufficient to certify the extracted numerical claim.

**Required fix.** Verify typed values with their sign, precision, grouping, units and context. Define locale handling and abstain on ambiguous representations. Keep observed facts distinct from calculations and inferred claims.

**Acceptance.** Add adversarial cases for signed numbers, decimals, thousands separators, percentages, dates, units and conflicting values. A mismatched value must not be marked supported. Derived arithmetic needs its own validation if offered as verified.

**Source:** [offsetx_apollo_builder/agent/verify.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/agent/verify.py#L1).

**Reproduction:** `test_numeric_claim_must_preserve_sign_decimal_and_magnitude`.

### A19 · P1 · Enrichment exports turn untrusted text into spreadsheet formulas

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** io_utils.write_outputs writes input values directly to CSV/XLSX. A contact name '=1+1' became an Excel cell with formula type 'f'. The separate CRM export already uses _spreadsheet_safe, so protection is inconsistent across exporters.

**Why it matters.** Opening exported untrusted contact/research data can execute spreadsheet formulas. The reproduction uses a harmless arithmetic expression; no external formula or exploit was run.

**Required fix.** Apply one reviewed spreadsheet-safe export policy to every exporter and every relevant sheet, including raw candidates and logs. Preserve original data separately where exact round-trip storage is needed.

**Acceptance.** Export values beginning with formula markers, leading whitespace and control characters through all CSV/XLSX paths. Inspect cell types and open representative files in supported spreadsheet software without executing untrusted expressions.

**Source:** [offsetx_apollo_builder/io_utils.py:151](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/io_utils.py#L151), [offsetx_apollo_builder/io_utils.py:188](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/io_utils.py#L188), [offsetx_apollo_builder/outreach/engine.py:938](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/engine.py#L938).

**Reproduction:** `test_enrichment_workbook_exports_untrusted_names_as_text`.

### A20 · P2 · API-token authentication breaks media loading and misreports login status

**Classification:** Bug. **Evidence:** Reproduced with frontend and API tests.

**What was found.** api.get adds the session-storage bearer token, but video audio/footage loaders use independent fetch calls with cookies only; image URLs also rely on browser-native loading. The frontend regression proves api.get succeeds against a token-checking transport while loadAudioAssets reports the same asset missing. Separately, /auth/session returns authenticated=true when only token auth is configured and no token is supplied, while /dashboard returns 401.

**Why it matters.** The Docker Compose token-auth workflow can show inaccessible images/audio/video despite normal API calls succeeding. Authentication state and missing-asset errors can mislead users. Cookie-login installations do not have the same header-loss condition.

**Required fix.** Use an authenticated binary-fetch path or appropriately scoped session/signed asset access for all media. Align the session-status contract with token mode and surface authentication errors instead of silently classifying media as missing.

**Acceptance.** Run image review, video preview and export in both cookie-login and token-only modes. Include expiry, logout, missing files and a fresh tab; verify correct media access and clear login state.

**Source:** [frontend/src/api.ts:39](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/api.ts#L39), [frontend/src/video/audio.ts:138](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/video/audio.ts#L138), [frontend/src/video/footage.ts:389](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/video/footage.ts#L389), [frontend/src/pages/ImageReview.tsx:138](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/ImageReview.tsx#L138), [offsetx_apollo_builder/api/app.py:545](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L545).

**Reproduction:** `test_auth_status_requires_a_valid_token_when_token_auth_is_configured`.

**Frontend reproduction:** `video audio loading preserves the configured API token` in `audit.production.test.ts`.

### A21 · P2 · Image quality gates accept corrupt data and can raise on malformed headers

**Classification:** Bug. **Evidence:** Reproduced.

**What was found.** A padded PNG header with no decodable pixel data passed every image gate. A six-byte GIF89a payload raised struct.error instead of returning a failed GateReport. Current checks decode base64 and inspect dimensions; they do not prove the image can be decoded.

**Why it matters.** Broken images can enter review as valid candidates, and malformed provider output can abort a generation path. This can also contaminate generator-quality statistics.

**Required fix.** Validate complete image structure with a maintained decoder under resource limits, including pixel-count and decompression limits. Convert malformed-data errors into controlled failed gates without aborting unrelated candidates.

**Acceptance.** Test truncated PNG/JPEG/GIF/WebP, plausible headers with invalid payloads, unsupported encodings, extreme dimensions and valid images. Bad candidates must fail safely; good candidates must still render.

**Source:** [offsetx_apollo_builder/imagery/gates.py:116](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/imagery/gates.py#L116), [offsetx_apollo_builder/imagery/gates.py:186](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/imagery/gates.py#L186).

**Reproduction:** `test_image_gate_rejects_a_header_only_corrupt_png`; `test_truncated_gif_is_a_failed_gate_instead_of_an_uncaught_exception`.

### A22 · P2 · Several write APIs lack typed validation and malformed input produces 500

**Classification:** Bug. **Evidence:** Reproduced; wider surface inventoried.

**What was found.** The inventory found 46 route handlers with raw dict body parameters. For image brief creation, width=[1] raises an unhandled TypeError in int(...) and returns HTTP 500 rather than a validation error. Similar conversion patterns occur in video and other write endpoints; not every possible payload was fuzzed.

**Why it matters.** Malformed clients receive server failures, schema documentation is weak and validation differs between features. This increases integration failures and makes limits harder to enforce.

**Required fix.** Define explicit request models with types, lengths, ranges and cross-field validation. Handle expected domain errors consistently and keep internal exceptions out of client responses.

**Acceptance.** Run a bounded malformed-body matrix across all write APIs, including nested objects, wrong scalar types, nulls, invalid enums and boundary values. Client mistakes must return stable 4xx errors without partial writes.

**Source:** [offsetx_apollo_builder/api/app.py:996](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L996), [offsetx_apollo_builder/api/app.py:1185](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L1185), [offsetx_apollo_builder/api/schemas.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/schemas.py#L1).

**Reproduction:** `test_malformed_image_dimensions_return_a_client_error`.

### A23 · P2 · The contact screen stops at 500 rows without pagination

**Classification:** Bug and scale gap. **Evidence:** Source confirmed.

**What was found.** Contacts.tsx requests limit=500, displays the server's total count, and renders only returned items. It has no offset/cursor or next-page control. The app's campaign selector likewise loads a bounded campaign list. Sales uses another large fixed limit rather than a full scalable browsing contract.

**Why it matters.** Users can see a total larger than the number of browsable contacts and cannot walk through the complete list. Search can retrieve some hidden records, but it does not replace complete navigation.

**Required fix.** Implement server-backed pagination or a bounded virtualized list with stable ordering, accurate displayed ranges and clear loading states. Preserve selection and filters across pages; define bulk-action scope explicitly.

**Acceptance.** Use more than 500 contacts and more campaigns than the selector limit. Verify every row can be reached, filters/counts agree, and selecting a page does not accidentally imply selecting all records.

**Source:** [frontend/src/pages/Contacts.tsx:23](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Contacts.tsx#L23), [frontend/src/pages/Contacts.tsx:123](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Contacts.tsx#L123), [frontend/src/App.tsx:122](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/App.tsx#L122), [frontend/src/pages/SalesTracker.tsx:332](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/SalesTracker.tsx#L332).

### A24 · P1 · There is no complete customer-data deletion and retention workflow

**Classification:** Production gap. **Evidence:** Source/API inventory confirmed.

**What was found.** The recall index has forget_message/forget_contact and the browser vault has revoke/forget capabilities. The API inventory has no full CRM-contact/workspace erasure workflow spanning contacts, messages, sales, AI logs/context/recall, exports, assets and backups. The existing recall operation removes only its own indexed records.

**Why it matters.** A company cannot reliably remove a person's data or apply a documented retention policy across the product. Partial 'forget' operations can leave other copies behind. This is an engineering data-lifecycle finding, not a legal compliance certification.

**Required fix.** Map every copy of personal data and define retention, deletion, legal-hold exceptions where applicable, backup expiry and re-indexing rules. Implement a resumable, auditable deletion workflow with appropriate permissions.

**Acceptance.** Seed one synthetic person's data across all stores, exports and indexes. Delete through the supported workflow and verify each intended copy is removed or retained for a documented reason, including after restore and re-indexing.

**Source:** [offsetx_apollo_builder/ai/recall.py:631](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/recall.py#L631), [offsetx_apollo_builder/api/app.py:2846](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L2846), [offsetx_apollo_builder/outreach/schema.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/schema.py#L1), [docs/REVOKE_AND_FORGET.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/docs/REVOKE_AND_FORGET.md#L1).

### A25 · P1 · The deployment does not run the durable email worker; other automation is process-local

**Classification:** Production gap. **Evidence:** Source/configuration confirmed.

**What was found.** The durable email service has an explicit work endpoint and offsetx-email-worker --watch CLI. Neither render.yaml nor docker-compose.yml defines that worker. The in-process email timer calls the legacy run_due path; it does not drain durable email jobs. Content/email timers use local process tasks and locks, without a shared scheduler lease.

**Why it matters.** Queued durable mail needs a manual work action or an independently operated worker. A sleeping or restarting web process cannot provide continuous automation, and adding replicas does not establish one scheduler owner.

**Required fix.** Deploy and supervise the durable worker explicitly, with heartbeat, retry/unknown-delivery handling and queue-age alerts. Move scheduling to a durable ownership model, or make the single scheduler topology explicit and enforce it. Preserve existing send-safety checks.

**Acceptance.** Queue real-shaped jobs, close the UI and restart the web service; work must progress under the worker. Kill/restart workers and run two instances; verify no duplicate sends or duplicated scheduled cycles.

**Source:** [render.yaml:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/render.yaml#L1), [docker-compose.yml:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/docker-compose.yml#L1), [offsetx_apollo_builder/email_worker_cli.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/email_worker_cli.py#L1), [offsetx_apollo_builder/api/email_delivery.py:95](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/email_delivery.py#L95), [offsetx_apollo_builder/outreach/automation.py:91](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/automation.py#L91), [offsetx_apollo_builder/distribution/automation.py:273](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/distribution/automation.py#L273).

### A26 · P1 · The Docker build omits feature dependencies and does not reproduce the Python lock

**Classification:** Production gap. **Evidence:** Source/configuration confirmed.

**What was found.** Dockerfile runs pip install . rather than installing uv.lock. boto3, psycopg and Crawl4AI are optional extras and are not installed by that command. Chromium and the browser sandbox runtime are also not provisioned by the web image. CI installs dev+email extras, so the tested Python environment differs from the shipped image.

**Why it matters.** A successful build does not mean SES, PostgreSQL or optional browser/crawler capabilities can run in that image. Python package versions can also drift between builds. A web-only image can be valid, but the complete feature deployment is not declared.

**Required fix.** Define the supported production capability set and build locked, versioned runtime images for it. Include required extras or separate services, browser/runtime prerequisites and startup checks. Pin or otherwise control base-image updates and test the produced image.

**Acceptance.** Build from a clean environment using the production recipe. Smoke-test every advertised enabled capability inside its actual runtime, record dependency versions/SBOM, and fail early with an actionable message for intentionally disabled capabilities.

**Source:** [Dockerfile:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/Dockerfile#L1), [pyproject.toml:46](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/pyproject.toml#L46), [offsetx_apollo_builder/outreach/deliverability/ses.py:24](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/outreach/deliverability/ses.py#L24), [.github/workflows/ci.yml:23](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/.github/workflows/ci.yml#L23).

### A27 · P1 · Real social publishing and engagement feedback are not implemented

**Classification:** Incomplete feature. **Evidence:** Source and board confirmed.

**What was found.** distribution/publishers.py provides LocalOutboxPublisher. Real platforms are declared but have no production publisher adapters. The board marks YouTube publishing, the remaining platform contract/adapters and real engagement readback as BLOCKED. The current code refuses unsupported scheduling instead of falsely claiming a real post was published.

**Why it matters.** Planning, approving and writing a local post artifact cannot fulfil a promise to operate live YouTube/Meta/TikTok/LinkedIn accounts or learn from real engagement automatically.

**Required fix.** Complete the adapter and credential lifecycle for the first agreed customer platform, including approval, rate limits, receipts, ambiguous delivery reconciliation and metrics ingestion. Keep unsupported integrations clearly unavailable until their end-to-end acceptance is complete.

**Acceptance.** With an authorised test account, publish an approved item, verify its actual external receipt, reconcile a timeout without duplicates, and ingest genuine metrics. Record platform permissions and revocation behaviour.

**Source:** [offsetx_apollo_builder/distribution/publishers.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/distribution/publishers.py#L1), [offsetx_apollo_builder/distribution/platforms.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/distribution/platforms.py#L1), [BOARD.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/BOARD.md#L1).

### A28 · P1 · The autonomous browser work is not yet a complete customer workflow

**Classification:** Incomplete feature. **Evidence:** Source/API inventory and branch tests confirmed.

**What was found.** Main contains RunLoop, budgets, structured results, provenance and claim verification, plus browser/session/vault components. The web API and frontend do not expose a complete run-launch/monitor/approval/resume flow. RunLoop documents steering/resume and continuation as separate work. PLAN.md and page-read caching exist on separate unmerged branches audited here.

**Why it matters.** Passing library tests does not let a company user reliably start, supervise, approve, resume and recover an autonomous job from the product. Prompt-injection containment and crash recovery still require end-to-end acceptance.

**Required fix.** Finish a bounded user workflow with persisted run state, permissions, approval ownership, progress, cancellation, recovery and results. Integrate the chosen PLAN/cache work only after review against the current main branch and the security findings above.

**Acceptance.** Run a controlled task through the actual UI, edit its plan, request approval, cancel, close/reopen the tab and restart the worker. Verify results/provenance, action limits and isolation under adversarial page content.

**Source:** [offsetx_apollo_builder/agent/run.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/agent/run.py#L1), [offsetx_apollo_builder/api/app.py:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L1), [frontend/src/App.tsx:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/App.tsx#L1), [BOARD.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/BOARD.md#L1).

### A29 · P1 · Release evidence omits important live integrations and operational failure checks

**Classification:** Production gap. **Evidence:** Test execution and configuration confirmed.

**What was found.** The original local run passed 1,574 cases with 23 environment skips. The later audit workflow provisioned real Chrome, PostgreSQL 16 and Docker and passed all 1,611 existing cases with zero skips, closing those specific execution gaps. It also added actual frontend and container acceptance checks which expose production failures. These tests and the required-service/no-skips gate exist on an unmerged audit branch. Main's release workflow still does not provision PostgreSQL or a sandbox test image, require these frontend acceptance tests, or reject integration skips. Readiness, logs and board evidence are not a complete operational monitoring/release system.

**Why it matters.** The ordinary green test workflow is not the failing live acceptance gate. Running the audit once does not close deployment, worker, recovery or operational acceptance. The company installation's configured providers, alerting, load targets, backup drill and full release-image smoke gate still require evidence.

**Required fix.** Add a release pipeline for the actual production image and topology: required integration services, real UI flows, restart/restore/worker tests, security regression tests, versioned migrations and bounded load checks. Wire actionable metrics, alerts and runbooks to an owner.

**Acceptance.** Required release suites must execute rather than skip. Record supported browsers/codecs, measured request/queue latency at an agreed customer load, failure/recovery drills, alert delivery and rollback evidence. External provider checks need authorised credentials.

**Source:** [.github/workflows/ci.yml:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/.github/workflows/ci.yml#L1), [frontend/vite.config.ts:21](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/vite.config.ts#L21), [offsetx_apollo_builder/api/app.py:523](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L523).

### A30 · P2 · The source-of-truth documents and login copy still contradict the production direction

**Classification:** Documentation and product gap. **Evidence:** Source and board comparison confirmed.

**What was found.** The login screen still says 'Protected demo' and refers to temporary Render credentials. DEPLOYMENT.md describes a disposable deployment and a local single-user product. FEATURE_TREE marks S-02.02.01 unbuilt/next while BOARD marks it DONE. BUILD_STATE has an old headline status. The prior production-contract work is not present in the audited main AGENTS.md.

**Why it matters.** Contributors can select already-completed work or use an obsolete deployment standard. Customer-facing language also conflicts with the current product commitment. Renaming the copy alone would not fix the engineering gaps.

**Required fix.** Merge/reconcile the production contract and maintain one verifiable feature/branch/release state. Link each claimed capability to its current acceptance evidence and deployment prerequisites. Update customer-facing copy after the supported behaviour is accurate.

**Acceptance.** The board, feature map, handoff and deployment guide must agree on main and unmerged branches. A new contributor must identify the next actual blocker from these files, and no DONE label should imply unperformed customer acceptance.

**Source:** [frontend/src/App.tsx:101](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/App.tsx#L101), [docs/DEPLOYMENT.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/docs/DEPLOYMENT.md#L1), [FEATURE_TREE.md:488](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/FEATURE_TREE.md#L488), [BOARD.md:121](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/BOARD.md#L121), [BUILD_STATE.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/BUILD_STATE.md#L1), [AGENTS.md:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/AGENTS.md#L1).

### A31 · P2 · Two frontend build dependencies have published advisories

**Classification:** Dependency maintenance. **Evidence:** npm audit and installed dependency tree confirmed.

**What was found.** The installed chain is vite 8.1.4 → postcss 8.5.19 → nanoid 3.3.16. npm audit reports one high advisory for Nano ID and one moderate advisory for PostCSS. These are development/build dependencies in this project. No demonstrated customer-facing runtime exploit was established. pip-audit reported no known Python package vulnerabilities in the installed audit environment.

**Why it matters.** The build chain includes known vulnerable versions and needs a controlled update. Raw advisory severity must not be confused with demonstrated exposure in the shipped static app.

**Required fix.** Update the lockfile to compatible patched releases, rebuild and rerun tests; verify the actual production dependency tree and document advisory applicability. Add dependency scanning to the release process.

**Acceptance.** npm audit must no longer report these affected installed versions, the production build must pass, and the locked deployment should have a recorded dependency scan. Keep any justified exception explicit and time-limited.

**Source:** [frontend/package-lock.json:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/package-lock.json#L1), [frontend/package.json:1](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/package.json#L1).

**External verification:** [Nano ID advisory](https://github.com/advisories/GHSA-2v37-7h3g-55p8), [PostCSS maintainer advisory](https://github.com/postcss/postcss/security/advisories/GHSA-fxqj-rqcc-2cmp).

### A32 · P1 · The sandbox's advertised writable output directory rejects writes

**Classification:** Bug. **Evidence:** Reproduced in real Docker.

**What was found.** SandboxWorkspace.prepare creates inbox/work directories with the host process's ownership and default 0755 permissions. SandboxPolicy runs the container as 65534:65534. On the ordinary GitHub runner (UID 1001), the actual pinned Python container starts, but writing /work/result.txt fails with PermissionError EACCES. The test uses the application's real workspace and Docker command, with no chmod/chown adjustment in the harness. Separate positive controls prove that code starts and that the isolation assertions are not mistaking startup failure for safety.

**Why it matters.** A sandboxed tool cannot produce its promised output in /work on this standard deployment. A read-write mount flag does not override Unix ownership. The feature can appear available while ordinary useful jobs fail.

**Required fix.** Provision each job's output directory with a narrowly scoped writable ownership/permission mapping for the actual container user and host runtime, while preserving isolation between jobs and from private stores. Verify host-side artifact retrieval and cleanup. Do not solve this by running tools as root or making unrelated directories world-writable.

**Acceptance.** On every supported rootful/rootless or user-namespace topology, an ordinary host user can run a tool that writes and reads back an artifact under /work; the host can retrieve it. Root/inbox remain read-only, private storage and the Docker socket remain absent, and egress stays denied with a successful network-enabled positive control.

**Source:** [offsetx_apollo_builder/ai/sandbox.py:112](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/sandbox.py#L112), [offsetx_apollo_builder/ai/sandbox.py:128](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/sandbox.py#L128), [offsetx_apollo_builder/ai/sandbox.py:408](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/ai/sandbox.py#L408).

**Reproduction:** `test_sandbox_work_directory_really_accepts_output`.

**Saved live evidence:** `live-integration-final/acceptance.xml`, `live-integration-final/runtime.json`.

### A33 · P1 · Creating a campaign can silently select an older campaign

**Classification:** Bug. **Evidence:** Reproduced in real Chrome.

**What was found.** Campaign creation selects the new ID before the refreshed campaign list arrives. App's fallback effect sees that ID missing from the old list, selects the first old campaign and overwrites localStorage. The live browser regression creates a second/later campaign successfully, then finds the active selector still pointing to the preceding campaign. An earlier live run also recorded a synthetic CSV import POST against the prior campaign and the video editor requesting an email campaign after creating an image campaign, receiving HTTP 422.

**Why it matters.** Users can attach contacts to the wrong campaign or open subsequent work against the wrong campaign kind immediately after successful creation. That puts later campaign-specific review and sending context at risk; no real customer send was attempted.

**Required fix.** Make campaign creation, list refresh and selection coherent. Preserve an explicitly selected newly created ID during refresh, update the list with the returned campaign or await an authoritative refreshed list before selection, and reject stale responses. Only choose a fallback after an authoritative result establishes that the selection is no longer valid.

**Acceptance.** With existing campaigns and delayed/out-of-order refresh responses, the new campaign remains selected through navigation and reload. Import must persist only in that campaign. Image/video routes must use the intended image campaign. Deleting a genuinely absent selected campaign must still choose a valid fallback.

**Source:** [frontend/src/pages/Campaigns.tsx:55](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Campaigns.tsx#L55), [frontend/src/App.tsx:134](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/App.tsx#L134).

**Reproduction:** `test_new_campaign_remains_the_active_campaign`.

**Saved live evidence:** `live-integration-final/acceptance.xml`, `live-integration-final/test_new_campaign_remains_the_active_campaign.png`, `live-integration-latest/frontend-server.log`.

### A34 · P2 · The editor's default Colour clip fails its own export acceptance gate

**Classification:** Bug. **Evidence:** Reproduced through real browser export.

**What was found.** In a fresh synthetic workspace, the actual UI creates an image campaign and an Empty project, adds the default two-second Colour clip, and exports 1080x1920 video at 30 fps. Chrome produces a 3,773-byte WebM and the server stores it with HTTP 201, but passed=False. Its sole displayed failure is not_empty: below 4096 bytes, accompanied by the claim that such a file contains a header and no frames. MIN_BYTES is fixed at 4096 and the gate makes this decision from length alone. Independent ffprobe decoding of both captured actual exports confirms VP9, 60 frames, 1080x1920, 2.000000 seconds, exit code zero and no decoder errors. Both files have SHA-256 6d0a53921188c94ee197535fde1f3ff5bd08c4e04cdb9412b84368731b27709a. This is a false rejection of valid encoded video.

**Why it matters.** A standard editor operation creates an export which the product itself refuses to mark ready. A size threshold cannot distinguish a compact solid-colour encode from a header-only file. It can reject useful output and provide an inaccurate explanation of what failed.

**Required fix.** Validate actual video samples/frames and supported media structure within explicit resource limits. Keep size ceilings and malformed-file protections, but replace the fixed minimum-size claim with evidence of missing/truncated samples. Align editor-supported short clips with server acceptance and retain actionable failure details.

**Acceptance.** The real Chrome Empty project -> Colour -> Export path creates a decodable 60-frame, two-second render accepted by the server. Small valid media must pass; genuine header-only/truncated media and wrong dimensions/duration must fail. Verify the resulting file independently of the application's header parser.

**Source:** [offsetx_apollo_builder/video/gates.py:41](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/video/gates.py#L41), [offsetx_apollo_builder/video/gates.py:513](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/video/gates.py#L513), [offsetx_apollo_builder/video/engine.py:949](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/video/engine.py#L949), [frontend/src/pages/VideoEditor.tsx:1151](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/VideoEditor.tsx#L1151).

**Reproduction:** `test_video_export_in_a_fresh_workspace`.

**Saved live evidence:** `live-integration-complete/acceptance.xml`, `live-integration-complete/test_video_export_in_a_fresh_workspace.png`, `live-integration-captured/video-export-6f53758a-142d-4359-9e45-9f4b2a8535ac.webm`, `decoded-video-export-6f53758a-142d-4359-9e45-9f4b2a8535ac.json`.

### A35 · P2 · Connectors loads Gmail status from a nonexistent API route

**Classification:** Bug. **Evidence:** Reproduced in live HTTP and Chrome.

**What was found.** Connectors.tsx calls api.get('/status'), producing GET /api/v1/status. That route does not exist and returns 404 in every recorded screen sweep. The actual status endpoint is /api/v1/settings/status, which returns 200. The Connectors Gmail panel renders the Loadable error branch, hiding its configured/not-configured information and normal Manage/Connect action. This does not require Gmail credentials to reproduce.

**Why it matters.** The connector overview cannot show Gmail's actual configuration state or its normal management action. A screen-heading smoke test can pass while this embedded feature is broken. Settings is a separate working route, not evidence that the Connectors panel works.

**Required fix.** Use the implemented settings-status contract through a shared typed API function. Retain actionable loading/error states and verify the panel for connected and disconnected configurations.

**Acceptance.** The actual Connectors browser request returns 200 from the supported route. The panel accurately renders both configuration states and its management action; a real transport failure produces an actionable retry instead of incorrect connection information.

**Source:** [frontend/src/pages/Connectors.tsx:34](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Connectors.tsx#L34), [frontend/src/pages/Connectors.tsx:170](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/frontend/src/pages/Connectors.tsx#L170), [offsetx_apollo_builder/api/app.py:755](https://github.com/kunalwagh101/off_CRM/blob/9f71f3c07f32407857311a1c4ed756925a612e6d/offsetx_apollo_builder/api/app.py#L755).

**Reproduction:** `test_connectors_can_load_its_gmail_status`.

**Saved live evidence:** `live-integration-complete/frontend-server.log`, `live-provider-results.json`.

## Existing protections worth keeping

The audit did not find that the entire application is fake or nonfunctional. The current tests provide meaningful evidence for several controls. Non-loopback deployment fails closed without configured strong authentication. Login cookies use security attributes, and login attempts have a local rate limiter. CRM export already escapes formula-like values on its own path.

Email preflight and durable delivery have useful protections: global suppression, permission checks, send-window handling, queue snapshots, claim/cancel rules, signed SNS verification and quarantine of ambiguous delivery instead of blindly resending. The audit did **not** reproduce an automatic duplicate send in the direct mail sender; A14 concerns the separate generic HTTP idempotency helper.

The AI layer has explicit data classes, tier/policy gates, payload scanning, unknown-provider/model handling, workspace-aware library storage and restrictions on caching drafted messages. Recall is designed around CRM-sent mail. These protections need to survive the fixes, especially when adding real user identity or changing cache/storage implementation.

Video timeline/history and algorithms have substantial deterministic coverage. Unsupported social publishing is refused. Browser vault/revoke and bounded-run code have useful local tests. None of these positives removes the need to test the complete deployed workflow.

A bounded high-signal secret-pattern scan found no matches in current tracked text files up to 2 MB. It covered common private-key, AWS-access-ID, GitHub-token and OpenAI-key patterns and redacted any potential values by design. This is not an exhaustive secret scan of Git history, deployment variables or credentials in the running environment.

## Remediation order

| Order | Work package | Findings | Evidence needed to close it |
|---|---|---|---|
| 1 | Durable customer state and safe recovery | A01, A02, A03, A04, A17 | Data survives concurrent failures, restart/redeploy and complete restore; dependent services recover; health reflects failures. |
| 2 | Individual access and safe external actions | A05, A06, A07, A08, A09, A15, A19, A24 | Permission/revocation tests, network-boundary tests, action approval tests, bounded input handling and verified data lifecycle. |
| 3 | Trustworthy AI and reliable customer workflows | A10, A11, A12, A13, A14, A16, A18, A20, A21, A22, A23, A33, A34, A35 | Correct spending reservations, truthful evidence/model attribution, one-effect retries, correct campaign association, working media/review/connectors and complete record navigation. |
| 4 | Deploy the complete supported product | A25, A26, A27, A28, A29, A30, A31, A32 | Locked production runtime, writable isolated job outputs, supervised worker, configured-provider acceptance, aligned docs and a release pipeline that requires the live tests. |

Independent fixes can be developed in parallel by the team, but restore depends on the final storage design, user-scoped controls depend on real identity, and worker scaling depends on correct transaction/claim ownership. Do not mark a finding closed solely because a code patch exists. Close it only when its acceptance evidence is attached.

## Production release exit criteria

These are the concrete remaining gates for the agreed company workflow. They should be represented in the project backlog and linked to evidence.

| Gate | Required evidence |
|---|---|
| Data durability | Inventory of all stores/files/secrets; successful restart, redeploy, disk-failure and restore drills; declared recovery objectives and backup retention. |
| Access | Individual test users, roles, offboarding/session revocation, server-side permissions and attributable actions across all enabled APIs. |
| External effects | Approval tied to an exact send/post/browser operation; duplicate prevention; truthful accepted/failed/unknown states; recovery that never blindly repeats an uncertain action. |
| AI trust and cost | Enforced budgets with priced usage; exact factual cache behaviour; correct model provenance; adversarial numeric/negation checks; no received-mail egress. |
| Core customer journey | A real browser completes import → draft → approve → queue/send → reply/stop → sales update → export, and the selected media/distribution workflows. Use authorised test accounts and synthetic contacts before customer data. |
| Runtime | The actual locked release images start with all enabled dependencies; assets persist; workers progress without the UI; unsupported capabilities are explicitly unavailable. |
| Integration | Browser/PostgreSQL/Docker execution with no skips is now demonstrated in audit CI; fix its failing acceptance checks and make the gate part of release CI. Verify selected Gmail/SES/Apollo/Notion/provider/platform contracts using configured test accounts. |
| Operations | Agreed load and queue-latency targets; visible errors and job states; working alerts; migration/rollback drill; incident and recovery runbooks with an owner. |
| Evidence and documentation | Each finding links to a fix and acceptance run. Main, branch status, feature map and deployment instructions agree. Customer-facing capability claims match the tested release. |

## How to reproduce and use this audit

The accompanying evidence bundle contains the finding register, source/API inventory, complete test summaries, dependency audit outputs, failing regression tests, live CI XML/screenshots/logs, provider configuration probes and instructions. `live_verification.md` and `live-verification-summary.json` record exact run/commit provenance and current results. Run the original Python audit tests from the audited checkout with `PYTHONPATH=.`. They intentionally assert the desired production behaviour and therefore fail on this snapshot. They are acceptance targets for fixes; their present failures must not be hidden with xfail or ignored assertions.

`run_frontend_regression.sh` temporarily copies its test into `frontend/src`, runs the existing Vitest configuration and removes the temporary file on exit. The main repository's existing test suite remains separate from these new audit cases. See the bundle's `README.md` for exact commands, branch-test scope and safety limits.

The report is bounded to the commits and evidence above. A new main commit, changed hosting topology or new production credentials can change the result and requires focused re-verification. This audit supplies a concrete production backlog and evidence; it does not certify an untested live installation.
