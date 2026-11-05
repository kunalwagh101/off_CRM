# Traceability

Every row is completable. A row that cannot be filled in is a gap, and the gap
is the point of the table.

**Read the columns as a chain:** a requirement you asked for → the story that
carries it → the acceptance criteria that define "carried" → the test that
proves it → the code it lives in. A break anywhere in that chain means the
requirement is an intention rather than a feature.

`scripts/verify_board.py` checks columns 1–2 (no orphan requirement, no orphan
story) and, for `DONE` rows, columns 4–5 (the test exists, the command passes,
the code exists and holds no stub).

---

## Delivered — the chain is complete

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-01 | S-01.01.01 | 2 | `tests/test_video_timeline.py` | `video/timeline.py` |
| R-02 | S-01.01.02 | 1 | `tests/test_video_mixdown.py` | `tests/fixtures/timeline_conformance.json` |
| R-03, R-04 | S-01.02.01 | 2 | `tests/test_video_engine.py` | `video/mixdown.py`, `video/gates.py` |
| R-05 | S-01.02.02 | 1 | `tests/test_video_retime.py` | `video/presets.py`, `video/timeline.py` |
| R-06 | S-01.02.03 | 2 | `tests/test_video_effects.py` | `video/effects.py`, `frontend/src/video/shaders/` |
| R-07 | S-01.03.01 | 2 | `tests/test_video_assembly.py` | `video/assembly.py`, `video/recipes.py` |
| R-08 | S-01.03.02 | 2 | `tests/test_video_director.py` | `video/director.py` |
| R-09 | S-01.04.01 | 3 | `tests/test_video_review.py` | `video/engine.py`, `video/store.py` |
| R-10, R-11 | S-01.04.02 | 3 | `tests/test_pacing_cap.py` | `distribution/pacing.py`, `distribution/engine.py` |
| R-12 | S-02.01.01 | 2 | `tests/test_browser_agent.py` | `browser/cdp.py`, `browser/session.py` |
| R-13 | S-02.01.02 | 2 | `tests/test_browser_agent.py` | `browser/perceive.py` |
| R-14 | S-02.01.03 | 2 | `tests/test_browser_agent.py` | `browser/page.py` |
| R-15, R-40 | S-02.01.04 | 2 | `tests/test_browser_agent.py` | `browser/policy.py` |
| R-16 | S-02.01.05 | 2 | `tests/test_browser_agent.py` | `browser/trace.py` |
| R-17 | S-02.02.01 | 2 | `tests/test_agent_run.py` | `agent/run.py`, `browser/trace.py` |
| R-27, R-28, R-29 | S-03.02.02 | 3 | `tests/test_browser_vault.py`, `tests/test_browser_vault_wiring.py` | `browser/vault.py`, `browser/signin.py`, `ai/scanner.py` |
| R-30 | S-03.02.03 | 1 | `tests/test_browser_revoke.py` | `browser/revoke.py`, `browser/vault.py`, `browser/identity.py`, `browser/trace.py` |
| R-52 | S-06.02.06 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-57 | S-06.02.07 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-61, R-62 | S-08.01.01 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/preflight.py`, `outreach/deliverability/store.py` |
| R-64, R-65, R-66 | S-08.01.02 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/service.py`, `outreach/deliverability/store.py` |
| R-67, R-68 | S-08.01.03 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/domain_auth.py`, `outreach/deliverability/ses.py` |
| R-69, R-70 | S-08.01.04 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/events.py`, `outreach/deliverability/service.py` |

| R-49 | S-06.02.03 | 4 | `tests/test_agent_run_budgets.py`, `tests/test_agent_money_ceiling.py` | `agent/run.py` |
| R-100 | S-06.02.15 | 3 | `tests/test_ci_verifier_environment.py`, `tests/test_verify_board.py` | `.github/workflows/ci.yml`, `scripts/verify_board.py` |
| R-90 | S-06.02.08 | 2 | `tests/test_verify_board.py`, `tests/test_ci_verifier_environment.py` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md`, `README.md`, `CONTINUE.md` |
| R-102 | S-06.02.17 | 2 | `tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails`, `tests/test_verify_board.py::test_done_with_only_done_dependencies_passes` | `scripts/verify_board.py`, `DEFINITION_OF_DONE.md` |

## In review — built, but this session cannot complete the proof

| Req | Story | Criteria | Current proof | Missing proof |
|---|---|---|---|---|
| R-135 | S-12.01.03 | 2 | product and style classified in video direction, system prompt persisted in egress log; API and migration tests committed | full suites, live video refusal and real hosted-log verification unrun |
| R-101 | S-06.02.16 | 3 | mandatory production all-severity and dev high-severity npm audit steps in CI; ordering tests committed | real npm registry audit, dependency remediation, frontend tests/build and runner execution unavailable |
| R-136 | S-12.02.05 | 2 | expert and judged winner references injected into classified GTM fields; GTM reference ablation and 3 synthetic starter cases committed | owner corpus, 30 judged real cases, live A/B run and full tests missing |
| R-164 | S-06.02.36 | 2 | owner confirmation required for local login at authenticated API boundary; regression cases committed | full API/auth suites, real login, independent review and board verification unrun |
| R-155 | S-06.02.28 | 3 | path-aware lease resolver, CLI wiring and shared dotenv loader; cross-cwd and config regression cases committed | all real CLIs against concurrent restore, symlink/filesystem checks, full suite and verifier unrun |
| R-161 | S-06.02.34 | 3 | per-provider local usage visible without cap; documented OpenRouter/DeepSeek balance endpoints, workspace-key endpoint, safe parser and UI tests committed | headers capture for OpenAI/Anthropic/Groq, real provider check, frontend/API/full suites and verifier unrun |

| R-165 | S-06.02.37 | 2 | skip event handler and Settings/Contacts route preservation regression committed | frontend Vitest/build, full regression and real Chromium keyboard/pointer flows unrun |
| R-167 | S-03.01.03 | 3 | IP-literal/noncanonical/local-name denial plus guard tests committed, isolated 16-case classification smoke passed | DNS-rebind/Chrome Docker network gateway and zero-private-connection tests absent; full suite unrun |
| R-168 | S-05.01.04 | 3 | Requests source uses DNS-approved IP for TCP while retaining HTTP Host/TLS identity; local HTTP/HTTPS socket and cert checks passed | Crawl4AI render transport still unpinned; live rebinding, full suite and S-05.01.01 upstream DONE gate outstanding |
| R-140 | S-06.02.20 | 2 | real shallow-clone regression test and full-depth CI checkout guard committed; isolated three-case Git reproduction passed | `uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q`, full regression, board verifier and hosted CI remain unrun |
| R-169 | S-06.02.39 | 3 | sample-aware small WebM check plus real encoded 60-frame VP9 test fixture and three named regression tests | full Python/frontend regression, real video-editor browser export, rollback and board verifier are unrun; CI runners unavailable |
| R-48 | S-06.02.02 | 2 | closed public-route allowlist + global auth middleware + secret-safe validation handler + exhaustive registered-route/body contract in `tests/test_api_boundary_contract.py` | `uv run pytest tests/test_api_boundary_contract.py tests/test_api_auth.py -q`, full regression, owner API review and verifier |
| R-51 | S-06.02.05 | 1 | skip navigation/current-page/live regions + focus-trapped/restoring modal + global focus-visible/reduced-motion + keyboard alternatives across AI/Sales/Video + recursive repo-wide `tests/test_frontend_accessibility_contract.py` | `uv run pytest tests/test_frontend_accessibility_contract.py -q && npm test --prefix frontend && npm run build --prefix frontend`, owner keyboard/screen-reader pass and verifier |
| R-55 | S-07.01.03 | 1 | localhost-only mic+system-audio MediaRecorder capture, transient raw chunks, immutable declared transcription provider/model, governed broker egress, transcript privacy/backup; `tests/test_meeting_transcription.py` committed | `uv run pytest tests/test_meeting_transcription.py tests/test_privacy.py -q && npm test --prefix frontend && npm run build --prefix frontend`, real localhost browser capture/manual audio check, full regression and verifier |
| R-41, R-42 | S-06.01.01 | 1 | persistent workspace-bound scrypt logins + corrected username validation + cross-process serialized AI settings/key writes + isolated encrypted provider keys/browser vaults + immutable per-workspace broker credentials (D-80/D-81); `tests/test_workspace_isolation.py` committed | `uv run pytest tests/test_workspace_isolation.py tests/test_api_auth.py tests/test_ai_api.py tests/test_browser_vault.py -q`, full regression, owner review and verifier; CI runner blocked by S-06.02.18 |
| R-45, R-46 | S-06.01.04 | 2 | durable interval/event routines + creation-time unattended refusal + workspace/event isolation + dedupe + renewable workspace browser lease + verified-record-only notifications; CHECK cold review found no contract drift; `tests/test_agent_routines.py` committed | `uv run pytest tests/test_agent_routines.py tests/test_agent_run.py tests/test_agent_provenance.py -q`, full regression, owner review and verifier; CI runner blocked by S-06.02.18 |
| R-29 | S-06.02.01 | 1 | one `scan_model_input` boundary covers payload, system prompt and transcription metadata before text/image/transcription provider I/O; generic credential assignments/field names are blocked (D-79); adversarial `tests/test_ai_prompt_secret_scan.py` committed | `uv run pytest tests/test_ai_prompt_secret_scan.py tests/test_ai_egress_wall.py -q`, full regression, owner review and verifier; CI runner blocked by S-06.02.18 |
| R-75 | S-03.02.05 | 2 | packaged validated `browser/platforms.json` drives identity, policy and budgets; Reddit added data-only; `tests/test_browser_platform_registry.py` committed | `uv run pytest tests/test_browser_platform_registry.py tests/test_browser_signin.py tests/test_browser_budget.py -q`, full regression, owner review and verifier |
| R-18 | S-02.02.02 | 2 | one `PLAN.md` per trace run, fresh-read before every decision, exact plan version captured in trace, managed-plan loss refuses rather than regenerates (D-78); `tests/test_agent_plan.py` committed | `uv run pytest tests/test_agent_plan.py tests/test_agent_run.py tests/test_agent_resume.py -q`, full regression, owner review and verifier; CI runner blocked by S-06.02.18 |
| R-31, R-35 | S-04.01.01 | 1 | transactional companion rows + production exact-scope memory isolation (no implicit global merge, D-77) + runtime tool grant enforcement + authenticated CRUD/context API; `tests/test_agent_companions.py` committed | `uv run pytest tests/test_agent_companions.py tests/test_privacy.py -q`, full regression, owner review and verifier; CI runner blocked by S-06.02.18 |
| R-38 | S-05.01.02 | 4 | `extraction_packs.py` + config registry + registry-load CSS syntax validation + `tests/test_extraction_packs.py` committed and wired into existing Scrapling discovery path | `uv run pytest tests/test_extraction_packs.py tests/test_discovery.py -q`, full regression, owner review and board verifier |
| R-39 | S-05.01.03 | 4 | deterministic structure-only analyser + finite numeric-evidence validation + existing recipe/assembly/review wiring + `tests/test_competitor_teardown.py` committed | `uv run pytest tests/test_competitor_teardown.py tests/test_video_assembly.py tests/test_video_review.py -q`, full regression, owner review and verifier |
| R-50 | S-06.02.04 | 3 | authenticated subject-access/deletion API + twelve-store inventory + retry revalidation of prior successes (D-76) + `tests/test_privacy.py` committed | `uv run pytest tests/test_privacy.py tests/test_api_auth.py -q`, full regression, owner privacy review and verifier; CI runner blocked by S-06.02.18 |
| R-36, R-37, R-40 | S-05.01.01 | 3 | durable frontier + shared host pacing + stale-policy revalidation + 7 focused acceptance/concurrency cases committed | `uv run pytest tests/test_crawler_frontier.py -q`, full regression, and board verifier must execute; current GitHub Actions jobs fail before step 1 |

## Ready — decision and dependencies resolved, not yet pulled

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-56 | S-07.01.04 | 3 | `tests/test_agent_artifacts.py` | `offsetx_apollo_builder/agent/artifacts.py`, `offsetx_apollo_builder/artifact_cli.py` |

## Blocked externally — engineering is waiting on access

| Req | Story | Blocked on |
|---|---|---|
| R-58 | S-01.05.01 | Owner-created Google Cloud project, YouTube Data API v3 and channel OAuth consent |
| R-59 | S-01.05.02 | Meta review, TikTok audit and LinkedIn partner access |
| R-60 | S-01.05.03 | S-01.05.01 and its Google Cloud access |
| R-103 | S-06.02.18 | GitHub-hosted runner allocation/account Actions state; owner settings or GitHub Support action required |

## Planned — story and criteria written, nothing built

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-19 | S-02.02.03 | 1 | — | — |
| R-32 | S-04.01.02 | 1 | — | — |
| R-33 | S-04.01.03 | 2 | — | — |
| R-34, R-35 | S-04.01.04 | 2 | — | — |
| R-43 | S-06.01.02 | 2 | — | — |
| R-47 | S-06.01.05 | 2 | — | — |
| R-53 | S-07.01.01 | 2 | — | — |
| R-54 | S-07.01.02 | 1 | — | — |

## Deferred — cut, with the trigger to bring it back

*(Empty. The former S-03.01.02 trigger fired and that story is delivered.)*

---

## The honest reading of this table

Board column counts are deliberately not copied into this file. The board
verifier recomputes authoritative counts and acceptance coverage from the
repository; duplicated hand-written totals are exactly the kind of state that
drifts.

Run `uv run python scripts/verify_board.py` for the current counts.

### Gaps that were open, and are now closed

- **S-02.02.01 closes the browser autonomy gap.** The browser already had safe
  perception, a closed ten-verb action vocabulary and an append-only trace, but
  nothing could turn an owner goal into repeated decisions and actions. The new
  bounded run loop does that through the existing egress broker, refuses lower-
  trust planning, treats page content as untrusted input, stops at consequential
  human gates and records provider/model plus estimated usage in the trace.
- **`tests/test_email_delivery.py` had a failing test** on `d96ea9d`, and that
  work had no backlog ID — it entered the repository without passing through
  this process. It has IDs now (E-07 / F-08.01, R-61 to R-71) and the failing
  test is fixed: its queue time was derived from a hardcoded 2026-08-24 fixture
  and expired when the date passed.
- **S-03.02.02 closed the browser-session custody gap.** The browser can retain
  an attended login, but off_CRM now keeps its managed copy under a different
  random key per workspace/platform account. The master source is OS-backed,
  with an explicit scrypt passphrase fallback, and sign-in refuses to record a
  green connection until vault capture succeeds. Generic cookie/token/password
  shapes are also refused by the shared AI egress scanner even at `full` policy.
- **S-03.02.03 closes the browser-session exit path.** Disconnect requires an
  attached page target, deletes the exact vaulted cookies from real Chromium,
  destroys that account's encrypted vault envelope, forgets the public
  connection record, and writes the action—not the secret—to the append-only
  trace. Browser deletion failure keeps the encrypted vault and green record so
  the owner can retry instead of seeing a false disconnected state.

### Two defects in already-`DONE` code, found by building on it

Both were fixed inside `S-03.02.01` rather than given new IDs, because neither
adds capability — they are the slice's own acceptance criteria failing in code
the slice depends on. Change control is about scope, not about bugs.

- **`profile_is_locked` counted a lock rather than reading it.** A browser
  stopped by a signal leaves `SingletonLock` behind and nothing ever removes it,
  so off_CRM refused a profile nobody held — permanently. The lock is now
  interrogated and a proven-stale one is cleared before launch.
- **`BrowserSession.close` killed the browser instead of closing it.** Chrome
  batches writes to the cookie jar and flushes on shutdown, so the login that
  had just been completed could be lost. `Browser.close` is sent first; the
  signal is the fallback.

### Gaps still open

- **Frontend tests are not named in most evidence blocks.** The video work has
  real frontend coverage, but most story evidence commands do not reach it.
- **S-06.02.01 is built and IN_REVIEW.** The broader adversarial boundary now
  covers payload, system prompt and transcription metadata across every provider
  path. Executable locked-suite/CI evidence is still required before DONE.

---

## Delivered since the original table was written

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-20 | S-02.02.04 | 1 | `tests/test_browser_countdown.py` | `browser/countdown.py`, `browser/page.py` |
| R-44 | S-06.01.03 | 2 | `tests/test_ai_cost_ledger.py` | `ai/broker.py`, `ai/registry.py`, `outreach/providers.py`, `agent/run.py`, `agent/report.py` |
| R-63, R-71 | S-08.01.05 | 3 | `tests/test_email_delivery.py`, `frontend/src/components.test.tsx` | `api/email_delivery.py`, `frontend/src/pages/Deliverability.tsx` |
| R-17 | S-02.02.01 | 2 | `tests/test_agent_run.py` | `agent/run.py`, `browser/trace.py` |
| R-21, R-22, R-23 | S-03.01.01 | 2 | `tests/test_browser_box.py` | `browser/box.py`, `browser/guard.py` |
| R-24 | S-03.01.02 | 1 | `tests/test_ai_sandbox.py`, `tests/test_browser_box.py` | `ai/sandbox.py` |
| R-72, R-73, R-74 | S-03.02.04 | 3 | `tests/test_browser_budget.py` | `browser/budget.py`, `browser/identity.py`, `browser/page.py` |
| R-25, R-26, R-42 | S-03.02.01 | 2 | `tests/test_browser_signin.py`, `tests/test_browser_agent.py` | `browser/identity.py`, `browser/signin.py`, `browser/session.py`, `browser/page.py` |
| R-27, R-28, R-29 | S-03.02.02 | 3 | `tests/test_browser_vault.py`, `tests/test_browser_vault_wiring.py` | `browser/vault.py`, `browser/signin.py`, `ai/scanner.py` |
| R-30 | S-03.02.03 | 1 | `tests/test_browser_revoke.py` | `browser/revoke.py`, `browser/vault.py`, `browser/identity.py`, `browser/trace.py` |
| R-120, R-121, R-122 | S-12.01.01 | 7 | `tests/test_gtm_products.py` | `gtm/products.py`, `gtm/store.py`, `api/gtm.py`, `frontend/src/pages/Product.tsx` |
| R-123, R-124 | S-12.01.02 | 6 | `tests/test_gtm_product_wiring.py` | `gtm/store.py`, `outreach/email_expert.py`, `distribution/automation.py`, `api/app.py` |
| R-125, R-126, R-127, R-128, R-129 | S-12.02.01 | 10 | `tests/test_gtm_strategy.py` | `gtm/strategy.py`, `gtm/service.py`, `frontend/src/pages/Strategy.tsx` |
| R-130 | S-12.02.02 | 5 | `tests/test_gtm_apply.py`, `tests/test_distribution.py`, `tests/test_content_automation.py` | `gtm/service.py`, `distribution/engine.py`, `distribution/automation.py` |
| R-131, R-132 | S-12.02.03 | 8 | `tests/test_gtm_review.py`, `tests/test_pacing_cap.py` | `gtm/review.py`, `gtm/service.py`, `api/gtm.py` |
| R-133, R-134 | S-12.02.04 | 4 | `tests/test_gtm_revise.py` | `gtm/review.py`, `gtm/service.py`, `gtm/store.py` |


## 2026-10-14 — Product feature traceability, IN_REVIEW

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-170 | F-06.07 | 3 | `tests/test_audience_launch_activity.py`, `frontend/src/pages/AudienceLaunchActivity.test.tsx` | `offsetx_apollo_builder/outreach/store.py`, `frontend/src/pages/AudienceOperations.tsx`, `frontend/src/pages/Contacts.tsx` |
| R-171 | F-06.08 | 3 | `tests/test_audience_launch_activity.py`, `frontend/src/pages/AudienceLaunchActivity.test.tsx` | `offsetx_apollo_builder/outreach/launch.py`, `frontend/src/pages/LaunchReadiness.tsx` |
| R-172 | F-06.09 | 3 | `tests/test_audience_launch_activity.py`, `frontend/src/pages/AudienceLaunchActivity.test.tsx` | `offsetx_apollo_builder/outreach/store.py`, `frontend/src/pages/CampaignActivity.tsx` |

No executed verification or DONE claim for these requirements.


## 2026-10-14 — Relationship workflow product features (IN_REVIEW)

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-173 | F-06.10 | 3 | `tests/test_relationship_workflows.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx` | `outreach/relationships.py`, `api/app.py`, `frontend/src/pages/ReplyInbox.tsx` |
| R-174 | F-06.11 | 3 | `tests/test_relationship_workflows.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx` | `outreach/relationships.py`, `frontend/src/pages/ContactConversation.tsx`, `Contacts.tsx` |
| R-175 | F-06.12 | 3 | `tests/test_relationship_workflows.py`, `tests/test_crm_hosted.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx` | `outreach/{schema,store,relationships}.py`, `frontend/src/pages/Followups.tsx` |

All three remain IN_REVIEW; tests, migration and hosted rollback/restore still require actual execution.


## 2026-10-15 — Relationship product features, IN_REVIEW

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-176 | F-06.13 | 3 | tests/test_relationship_intelligence.py, frontend/src/pages/RelationshipIntelligence.test.tsx | outreach/relationship_ops.py, outreach/schema.py, api/app.py, frontend/src/pages/Contact360.tsx |
| R-177 | F-06.14 | 3 | tests/test_relationship_intelligence.py, frontend/src/pages/RelationshipIntelligence.test.tsx | outreach/relationship_ops.py, frontend/src/pages/Contact360.tsx |
| R-178 | F-06.15 | 3 | tests/test_relationship_intelligence.py, frontend/src/pages/RelationshipIntelligence.test.tsx | outreach/relationship_ops.py, frontend/src/pages/ActionCenter.tsx |

These are authored test paths, not passed test evidence. All features IN_REVIEW.


## 2026-10-15 — CRM intelligence product features, IN_REVIEW

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-179 | F-06.16 | 3 | `tests/test_crm_insights.py`, `frontend/src/pages/CRMIntelligence.test.tsx` | `outreach/crm_insights.py`, `api/app.py`, `frontend/src/pages/CRMSearch.tsx` |
| R-180 | F-06.17 | 3 | `tests/test_crm_insights.py`, `frontend/src/pages/CRMIntelligence.test.tsx` | `outreach/crm_insights.py`, `frontend/src/pages/AccountIntelligence.tsx` |
| R-181 | F-06.18 | 3 | `tests/test_crm_insights.py`, `frontend/src/pages/CRMIntelligence.test.tsx` | `outreach/crm_insights.py`, `frontend/src/pages/RevenueAttribution.tsx` |

IN_REVIEW = authored but not tested or deployed.


## 2026-10-15 — CRM operations product features, IN_REVIEW

| Req | Feature | Criteria | Test source | Source |
|---|---|---|---|---|
| R-182 | F-06.19 | 3 | `tests/test_crm_operations.py`, `frontend/src/pages/CRMOperations.test.tsx` | `outreach/crm_operations.py`, `api/app.py`, `frontend/src/pages/CRMOperations.tsx` |
| R-183 | F-06.20 | 3 | `tests/test_crm_operations.py`, `frontend/src/pages/CRMOperations.test.tsx` | `outreach/crm_operations.py`, `api/app.py`, `frontend/src/pages/CRMOperations.tsx` |
| R-184 | F-06.21 | 3 | `tests/test_crm_operations.py`, `frontend/src/pages/CRMOperations.test.tsx` | `outreach/crm_operations.py`, `api/app.py`, `frontend/src/pages/CRMOperations.tsx` |

Tests are **authored**, not evidence of a passing run. Q-27 customer isolation remains unresolved.


## 2026-11-02 — F-06.22 duplicate contact review (IN_REVIEW)

| Req | Feature / sub-stories | Criteria | Tests | Source |
|---|---|---|---|---|
| R-185 | F-06.22a / F-06.22b / F-06.22c | 3 | `tests/test_crm_duplicate_review.py` (4 tests) | `outreach/crm_operations.py`, `api/app.py` |

TDD RED and GREEN observed on isolated Render; independent release security, tenancy Q-27, full-history verifier and live operator acceptance remain open. No DONE claim.

## 2026-11-03 — F-06.02 A12/A13 cache-integrity repair (IN_REVIEW)

| Req | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-186 | S-06.02.58 | 3 | `tests/test_ai_cache_integrity.py::test_A12_changed_numeric_evidence_cannot_reuse_near_cache`, `tests/test_ai_cache_integrity.py::test_A12_changed_negation_cannot_reuse_near_cache`, `tests/test_ai_cache.py` | `offsetx_apollo_builder/ai/cache.py` |
| R-187 | S-06.02.59 | 3 | `tests/test_ai_cache_integrity.py::test_A13_model_id_partitions_identical_payload`, `tests/test_ai_cache_integrity.py::test_A13_system_instructions_partition_identical_payload`, `tests/test_ai_cache.py::test_A13_broker_reexecutes_when_model_changes`, `tests/test_ai_cache.py::test_A13_broker_reexecutes_when_system_instructions_change` | `offsetx_apollo_builder/ai/cache.py`, `offsetx_apollo_builder/ai/broker.py` |

New restart test: `tests/test_ai_cache_integrity.py::test_A12_A13_restart_keeps_fact_and_model_provenance_isolated` covers R-186 and R-187 through persisted storage. Render dep-dbl0abqjnfac73a521g0 on 6528060 LIVE: 9 targeted, SQLite 2965, PostgreSQL 2988 PASS; independent penetration, real provider and full-history verifier open. Both requirements are code-complete but IN_REVIEW. A12/A13 RED and initial targeted GREEN were executed on isolated Render. The final exact-source full regression, independent penetration and operator production acceptance are separate gates.

## 2026-11-04 — A16 claimed-email job factory failures (BACKLOG, remediation implemented)

| Req | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-188 | S-06.02.61 | 5 | `tests/test_email_delivery.py -k A16` (5 parameterised cases); `tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried` | `offsetx_apollo_builder/outreach/deliverability/service.py` |

RED isolated Render on 61cc4fa 5 failures; GREEN focused 5 PASS on 144e1cb. Owner-approved build-ahead code is not DONE and story remains BACKLOG under active audit and worker deployment dependency. PostgreSQL/full suite, independent security and operational worker integration pending.

A16 final isolated QA: `dep-dbldur942hec73fvgeq0` on `144e1cb` LIVE 2026-11-04 07:52:04 UTC; A16 5 PASS, SQLite 2970 PASS, PostgreSQL 2993 PASS, browser and verifier-unit gates PASS. R-188 still BACKLOG pending actual worker + independent security/release certification.

## 2026-11-04 — A11 atomic quota reservation (BACKLOG; build-ahead implementation)

| Req | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-189 | S-06.02.60 | Cross-worker atomic call/minute/day caps; capped priced calls; corrupt/read/write failure; crash and idempotent reconciliation; separate/shared accounts and key rotation | `tests/test_ai_quota_atomic.py` (15 cases including conditional PostgreSQL multi-process race); `tests/test_ai_cost_ledger.py`; `tests/test_ai_egress_wall.py` | `offsetx_apollo_builder/ai/quota.py`, `offsetx_apollo_builder/ai/broker.py` |

RED 8 cases on b57c971 and key-rotation RED 1 case on e488c30, both isolated Render builds. Source 8957a27 focused 14 PASS/1 PostgreSQL-only skipped on early gate dep-dblffhijnfac73fs3770; final exact-source full PostgreSQL and security release evidence pending. Keep S-06.02.60 BACKLOG until audit and readiness gates.

A11 exact-source full review: code `8957a27`, Render `dep-dblffhijnfac73fs3770`, 14 focused A11 PASS/1 conditional PG skip, SQLite 2,984 PASS, PostgreSQL 3,008 PASS with A11 PG-specific test enabled, focused PG 215 PASS, real Chromium desktop/mobile PASS. Structural board verification only (`--skip-tests`); independent penetration and customer acceptance remain OPEN. Story BACKLOG pending audit.

A11 review runner dep-dblffhijnfac73fs3770 **LIVE** 2026-11-04T09:35:47.896966Z on exact code 8957a27. This is not independent penetration, full-history evidence replay, real paid-provider acceptance or customer release.

## 2026-11-04 — A14 HTTP idempotency (R-190, S-06.02.62)

| Req | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-190 | S-06.02.62 | Cross-process database effect exactly once, canonical request and authenticated caller binding, rollback on crash, pre-send in-progress hold, no external auto-retry, legacy/corrupt key denial | `tests/test_api_idempotency_a14.py` (SQLite and real PostgreSQL API instances, principal replay, external send, crash); `tests/test_outreach_api.py` replay/409 | `offsetx_apollo_builder/api/app.py` and existing `OutreachStore.transaction(immediate=True)` |

RED isolated Render `ac10fa0`: five failures; initial GREEN `19682d5`: five passes. Additional tests `7c47b34` and full review are pending. Source result is not an independent penetration certification; no main/customer release.

A14 additional test coverage on executable source `2e709a5`: adversarial concurrently changed payload (409 and single effect), bound SQL-metacharacter key, and true OS-process crash before transaction commit. Real provider setup replay test added at `0b66f15`, code fixed at `c6d1192`. Final exact-source Docker/Render QA pending; no customer release.

## A14 exact-source QA verification — 2026-11-04

`S-06.02.62 / R-190`, source `1c1d3a2` (executable `2e709a5`), isolated Render `dep-dblg7k8u01pc73a4m7lg`: 12 focused A14 PASS/1 PG-only SKIP; full SQLite 2,996 PASS/56 skipped; real disposable PG 3,020 PASS/101 skipped with the PG-specific two-instance race included; focused PG 215 PASS; desktop/mobile Chromium and frontend/security gates PASS. Full-history Git evidence replay, independent security, real mail-provider acceptance and customer/main release remain OPEN; story still BACKLOG.

A14 source 1c1d3a2 / Render dep-dblg7k8u01pc73a4m7lg confirmed LIVE 2026-11-04T10:27:18.435081Z with the above complete SQLite/PG/browser QA. This is isolated QA, not provider acceptance or customer release.

## 2026-11-04 — A32 restricted sandbox output (R-191, S-06.02.64)

| Req | Story | Acceptance | Tests | Code |
|---|---|---|---|---|
| R-191 | S-06.02.64 | Private root, restricted UID write, legacy mode repair, symlink refusal, unchanged mount/network boundary | `tests/test_ai_sandbox.py -k A32`; existing sandbox isolation and egress suite | `offsetx_apollo_builder/ai/sandbox.py` |

A32 RED isolated review `dep-dblipuff3r2c73a96th0` at test-only `64af3c5`: 5 expected failures. Corrected source `c63fe5c`, isolated Render `dep-dbliqluc6qcc73bht1hg`: focused A32 5 passed (43 deselected); broad gates in progress. Real pinned Docker writing under /work and independent penetration remain open. No customer/main rollout.

## 2026-11-04 — A32 final exact-source regression evidence

R-191 / S-06.02.64: source c63fe5c, isolated Render dep-dbliqluc6qcc73bht1hg LIVE at 2026-11-04 13:24:37 UTC. Focused A32 5 PASS; full SQLite 3,002 PASS/56 skipped; full disposable PostgreSQL 3,026 PASS/101 skipped; PG focused 215 PASS; Chrome desktop/mobile, frontend, static/security gates PASS. This does **not** close native Docker output, independent penetration, failure logging, complete Git-history verifier, customer rollout or the active S-06.02.23 audit. The board state is IN_REVIEW, not DONE.

## 2026-11-04 — A22 nested video-edit validation (R-192, S-06.02.65)

| Req | Story | Acceptance | Tests | Code |
|---|---|---|---|---|
| R-192 | S-06.02.65 | Malformed nested edits return bounded 4xx, do not save a project version; valid single/batch persist and undo | `tests/test_video_edit_validation_a22.py` (10 HTTP tests: 6 invalid-shape cases, 2 Unicode cases, and 2 valid/boundary cases) | `offsetx_apollo_builder/api/schemas.py`, `offsetx_apollo_builder/api/app.py` |

RED 86da047 / Render dep-dbln67d6e07s739droo0: 6 fail, 2 pass. Fixed source 384070d / Render dep-dbln72ff3r2c73e4r2q0: 8 pass focused. Final full QA and independent pen/customer acceptance separate. A22 whole API surface remains open.

## 2026-11-04 — R-192 malformed Unicode hardening

Follow-up source 1201495 expands R-192 from 8 to 10 named HTTP tests, adding invalid Unicode escape in a nested parameter value and a nested parameter key. The new `_check_video_edit_parameters` rejects surrogate code points before UTF-8 serialization; the size check uses `ensure_ascii=True`. Final exact-source isolated Render dep-dblnc3tg1s2s73cvcvn0 and all broader gates are pending, not yet claimed passed. Defect D-368, design DD-145.

## R-192 — Final exact-source automated review (2026-11-04)

Final review evidence: executable/test source `12014959e82b27c4fce65cc4f5c983c65c28174b`, isolated Render `dep-dblnc3tg1s2s73cvcvn0` **LIVE** on 2026-11-04 at 18:34:14 UTC. A22 focused **10 passed**; full SQLite **3,012 passed, 56 skipped, 44 warnings**; full real disposable PostgreSQL **3,036 passed, 101 skipped, 44 warnings**; focused PG **215 passed**; 12 real repeated concurrency probes PASS. Frontend tests/build/npm audits, Chromium desktop/mobile Contacts/Public Demo, A09 and A18 browser security checks, Ruff, API auth and structural board verifier PASS. Docker board verifier used `--skip-tests`: no historical evidence replay. No independent penetration, actual customer video browser acceptance, full A22 write-API matrix, customer deployment or `main` promotion.

A22 across **all** write routes remains open; independent penetration and full-history evidence replay are not certified. No customer/main release.

## Active audit recheck — A05 identity and workspace administration (2026-11-05)

| Finding | Active story | Verified criteria | Test | Existing code boundary | Remaining gate |
|---|---|---|---|---|---|
| A05 | S-06.02.23 | Another user's permission policy is refused; ordinary sessions cannot administer accounts; disabling a user invalidates their cookie without invalidating a peer | `tests/test_audit_a05_workspace_identity.py` (3 PASS on source `94fa650`; isolated Render `dep-dblr106i0phs7385jao0`) | `offsetx_apollo_builder/api/app.py`, `offsetx_apollo_builder/api/auth.py` | Wider per-user role checks, CRM tenancy Q-27, independent penetration, full-history verifier, and customer production acceptance |

This is a verification mapping, not a new backlog requirement or a DONE claim. S-06.02.23 stays IN_PROGRESS.


## R-193 — A10 paid AI receipt integrity (build-ahead; not released)

| Requirement | Story | Accepted contract | Regression | Code | Missing gate |
|---|---|---|---|---|---|
| R-193 | S-06.02.66 | Valid paid receipts persist cost and refuse unaffordable follow-up; unusable/zero provider counts become positive labelled estimates rather than free calls/post-send exceptions; provider errors retain counted usage; two workers compete against one durable USD cap | `tests/test_ai_billing_integrity_a10.py` (RED 7 expected failures/2 passed; exact-source Render 822ffa8 A10 12 PASS/1 early PG-only skip, full SQLite 3,027 PASS, full PG 3,052 PASS including real two-process A10 PG race; QA marker LIVE 2026-11-04 23:28 UTC) | `offsetx_apollo_builder/ai/broker.py`, `offsetx_apollo_builder/outreach/providers.py`, `offsetx_apollo_builder/ai/quota.py` (unchanged reservation) | Automated SQLite/PostgreSQL/browser/security QA verified; still missing full Git-history evidence replay, actual paid-provider invoices/unknown multimodal pricing, independent penetration and customer production acceptance |

Audit A10 and S-06.02.23 remain open. This row must not be mistaken for a production DONE claim.

## R-194 — A24 API owner-only personal-data safety (build-ahead; not production-released)

| Requirement | Story | Current proven criteria | Test | Code | Remaining gates |
|---|---|---|---|---|---|
| R-194 | S-06.02.67 | Normal workspace login cannot access private inventory, preview erasure, run even a known owner request ID, or obtain the deletion phrase; install token and deliberately provisioned local owner login retain confirmed deletion; unaffected contacts preserved | `tests/test_audit_a24_privacy_owner_authorization.py`, RED 4 expected FAIL/1 PASS, GREEN 5 PASS; exact-source `4117704` / Render `dep-dbm3oj8ae00c7389h7d0` LIVE 2026-11-05 08:41 UTC; full SQLite 3,032 PASS, real PG 3,057 PASS, focused PG 215 PASS, Chromium/security gates PASS | `offsetx_apollo_builder/api/app.py` (`require_install_owner` reused), `offsetx_apollo_builder/privacy.py` (unchanged existing 12-store workflow) | Automated PostgreSQL/SQLite/Chromium review passed; still missing backup/restore/retention and reindex full A24 acceptance, Q-27 ownership, independent penetration, full-history DONE verifier and production acceptance |

The broader A24 finding remains OPEN in production audit S-06.02.23.

## R-195 — Video ownership requires the authenticated workspace (build-ahead)

| Requirement | Story | Acceptance and current evidence | Tests | Code | Remaining release checks |
|---|---|---|---|---|---|
| R-195 | S-06.02.68 | Ordinary workspace cannot read/download another workspace's video projects, media or rendered files; undo/redo/history/reviews and media placement/transcription do not cross workspace; all lists and summaries are filtered in SQL before LIMIT; own records remain usable. TDD RED 4 expected failures on d22d3a8 / Render dep-dbm4isu1egvs73bau35g; intermediate 3 PASS/1 FAIL on de92a5a revealed 409 classification; GREEN 4 PASS on exact code/test source 246741b / isolated Render dep-dbm4lgrbc2fs738acn6g; full SQLite 3,036 PASS / PG 3,061 PASS / Chromium PASS | `tests/test_audit_a05_video_workspace_isolation.py` (real cookie sessions, two workspaces, synthetic video records); existing video engine and hosted regressions | `offsetx_apollo_builder/video/store.py`, `offsetx_apollo_builder/video/engine.py`, `offsetx_apollo_builder/api/app.py` | Full source-bound SQLite (3,036 pass), real PostgreSQL (3,061 pass), focused PostgreSQL (215 pass), real Chromium and static/frontend gates passed; full historical verifier, Q-27 CRM tenancy, independent penetration and customer acceptance remain open |

Source QA status is updated in `docs/evidence/2026-11-05-a05-video-workspace-isolation.md`. A05 audit S-06.02.23 remains IN_PROGRESS.
