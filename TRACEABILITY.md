# Traceability

Snapshot from `BOARD.md` and `PRODUCT_BACKLOG.md`, 9 September 2026. Each row
connects a requirement to its story, acceptance criteria and current evidence.
The board keeps the runnable commands, results and implementation commits.

`uv run python scripts/verify_board.py` recomputes coverage, verifies code/test
references and runs every DONE evidence command. A story's status does not
certify unrelated audit findings in the same subsystem.

**95 requirements; 74 stories; 34 DONE, 1 IN_REVIEW, 0 IN_PROGRESS, 6 READY, 3 BLOCKED, 30 BACKLOG.**

## Delivered

| Requirement | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-95 | S-06.02.11 | 8 | `tests/test_audit_wp1.py`, `tests/test_wp1_recovery_edges.py`, `tests/test_workspace_lock.py`, `verification/test_wp1_live.py` | `offsetx_apollo_builder/outreach/backup.py`, `offsetx_apollo_builder/outreach/sqlite_ownership.py`, `offsetx_apollo_builder/outreach/workspace_lock.py`, `offsetx_apollo_builder/api/production_runtime.py`, `offsetx_apollo_builder/api/config.py`, `frontend/src/pages/Settings.tsx`, `render.yaml` |
| R-83 | S-11.02.04 | 3 | `tests/test_agent_page_memo.py` | `offsetx_apollo_builder/agent/run.py` |
| R-82 | S-11.02.03 | 3 | `tests/test_agent_claim_verification.py` | `offsetx_apollo_builder/agent/verify.py`, `offsetx_apollo_builder/agent/result.py`, `offsetx_apollo_builder/agent/run.py` |
| R-81 | S-11.02.02 | 2 | `tests/test_agent_provenance.py` | `offsetx_apollo_builder/agent/result.py`, `offsetx_apollo_builder/agent/run.py`, `offsetx_apollo_builder/browser/trace.py` |
| R-80 | S-11.02.01 | 3 | `tests/test_agent_structured_result.py` | `offsetx_apollo_builder/agent/result.py`, `offsetx_apollo_builder/agent/run.py` |
| R-17 | S-02.02.01 | 2 | `tests/test_agent_run.py` | `offsetx_apollo_builder/agent/run.py`, `offsetx_apollo_builder/browser/trace.py` |
| R-30 | S-03.02.03 | 1 | `tests/test_browser_revoke.py` | `offsetx_apollo_builder/browser/revoke.py`, `offsetx_apollo_builder/browser/vault.py`, `offsetx_apollo_builder/browser/identity.py`, `offsetx_apollo_builder/browser/trace.py` |
| R-27, R-28, R-29 | S-03.02.02 | 3 | `tests/test_browser_vault.py`, `tests/test_browser_vault_wiring.py` | `offsetx_apollo_builder/browser/vault.py`, `offsetx_apollo_builder/browser/signin.py`, `offsetx_apollo_builder/ai/scanner.py` |
| R-01 | S-01.01.01 | 2 | `tests/test_video_timeline.py` | `offsetx_apollo_builder/video/timeline.py` |
| R-02 | S-01.01.02 | 1 | `tests/test_video_mixdown.py` | `tests/fixtures/timeline_conformance.json` |
| R-03, R-04 | S-01.02.01 | 2 | `tests/test_video_engine.py` | `offsetx_apollo_builder/video/mixdown.py` |
| R-05 | S-01.02.02 | 1 | `tests/test_video_retime.py` | `offsetx_apollo_builder/video/presets.py` |
| R-06 | S-01.02.03 | 2 | `tests/test_video_effects.py` | `offsetx_apollo_builder/video/effects.py` |
| R-07 | S-01.03.01 | 2 | `tests/test_video_assembly.py` | `offsetx_apollo_builder/video/assembly.py` |
| R-08 | S-01.03.02 | 2 | `tests/test_video_director.py` | `offsetx_apollo_builder/video/director.py` |
| R-09 | S-01.04.01 | 3 | `tests/test_video_review.py` | `offsetx_apollo_builder/video/engine.py` |
| R-10, R-11 | S-01.04.02 | 3 | `tests/test_pacing_cap.py` | `offsetx_apollo_builder/distribution/pacing.py` |
| R-12 | S-02.01.01 | 2 | `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/cdp.py` |
| R-13 | S-02.01.02 | 2 | `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/perceive.py` |
| R-14 | S-02.01.03 | 2 | `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/page.py` |
| R-15, R-40 | S-02.01.04 | 2 | `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/policy.py` |
| R-16 | S-02.01.05 | 2 | `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/trace.py` |
| R-21, R-22, R-23 | S-03.01.01 | 2 | `tests/test_browser_box.py` | `offsetx_apollo_builder/browser/box.py`, `offsetx_apollo_builder/browser/guard.py` |
| R-72, R-73, R-74 | S-03.02.04 | 3 | `tests/test_browser_budget.py` | `offsetx_apollo_builder/browser/budget.py`, `offsetx_apollo_builder/browser/identity.py`, `offsetx_apollo_builder/browser/page.py`, `offsetx_apollo_builder/browser/signin.py` |
| R-91 | S-06.02.09 | 3 | `tests/test_security_audit.py` | `offsetx_apollo_builder/outreach/store.py`, `offsetx_apollo_builder/outreach/sqlite_ownership.py` |
| R-92, R-93, R-94 | S-06.02.10 | 3 | `tests/test_security_audit.py` | `offsetx_apollo_builder/api/config.py`, `offsetx_apollo_builder/api/app.py`, `offsetx_apollo_builder/web_cli.py` |
| R-25, R-26, R-42 | S-03.02.01 | 2 | `tests/test_browser_signin.py`, `tests/test_browser_agent.py` | `offsetx_apollo_builder/browser/identity.py`, `offsetx_apollo_builder/browser/signin.py`, `offsetx_apollo_builder/browser/session.py`, `offsetx_apollo_builder/browser/page.py` |
| R-21, R-24 | S-03.01.02 | 1 | `tests/test_browser_box.py` | `offsetx_apollo_builder/ai/sandbox.py` |
| R-57 | S-06.02.07 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-52 | S-06.02.06 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-61, R-62 | S-08.01.01 | 3 | `tests/test_email_delivery.py` | `offsetx_apollo_builder/outreach/deliverability/preflight.py`, `offsetx_apollo_builder/outreach/deliverability/store.py` |
| R-64, R-65, R-66 | S-08.01.02 | 3 | `tests/test_email_delivery.py` | `offsetx_apollo_builder/outreach/deliverability/service.py`, `offsetx_apollo_builder/outreach/deliverability/store.py` |
| R-67, R-68 | S-08.01.03 | 3 | `tests/test_email_delivery.py` | `offsetx_apollo_builder/outreach/deliverability/domain_auth.py`, `offsetx_apollo_builder/outreach/deliverability/ses.py` |
| R-69, R-70 | S-08.01.04 | 3 | `tests/test_email_delivery.py` | `offsetx_apollo_builder/outreach/deliverability/events.py`, `offsetx_apollo_builder/outreach/deliverability/service.py` |

## In progress

No stories in this state.

## In review

| Requirement | Story | Criteria | Tests | Code |
|---|---|---|---|---|
| R-63, R-71 | S-08.01.05 | 3 | `tests/test_email_delivery.py`, `frontend/src/components.test.tsx` | `offsetx_apollo_builder/api/email_delivery.py`, `frontend/src/pages/Deliverability.tsx` |

S-08.01.05 remains in its own review. Its Python and frontend checks now pass;
WP1 does not silently certify the remaining delivery story.

## Ready

| Requirement | Story | Criteria | Scope / dependency |
|---|---|---|---|
| R-75 | S-03.02.05 | 2 | A platform is a row, not a code change |
| R-76 | S-11.01.01 | 3 | A failed action is recovered from, not repeated |
| R-78 | S-11.01.03 | 2 | A run survives the process dying |
| R-85 | S-11.03.02 | 2 | A page that tries to give orders is reported, not obeyed |
| R-88 | S-11.05.01 | 3 | Concurrent runs share one browser safely |
| R-90 | S-06.02.08 | 2 | One runner for every evidence command |

## Blocked externally

| Requirement | Story | Criteria | Scope / dependency |
|---|---|---|---|
| R-58 | S-01.05.01 | 3 | external — a Google Cloud project with YouTube Data API v3 enabled, and OAuth consent for the channel. Only the owner can create it. |
| R-59 | S-01.05.02 | 2 | external — Meta app review, TikTok content-posting audit, LinkedIn partner programme. Weeks of calendar time, and none of it is engineering. |
| R-60 | S-01.05.03 | 2 | external — depends on S-01.05.01, which is itself waiting on the Google Cloud project. |

## Backlog

| Requirement | Story | Criteria | Scope / dependency |
|---|---|---|---|
| R-77 | S-11.01.02 | 3 | A run that stops making progress is stopped |
| R-79 | S-11.01.04 | 3 | A run has a money ceiling, not only a step ceiling |
| R-84 | S-11.03.01 | 3 | A wall the agent must not climb pauses the run and asks |
| R-86 | S-11.04.01 | 2 | A run report a person can audit |
| R-87 | S-11.04.02 | 1 | Progress is visible while it happens |
| R-89 | S-11.05.02 | 1 | Re-running does not duplicate what it already did |
| R-18 | S-02.02.02 | 2 | PLAN.md as the single source of truth |
| R-19 | S-02.02.03 | 1 | Interrupt, steer, resume |
| R-20 | S-02.02.04 | 1 | Safety countdowns before consequential actions |
| R-31, R-35 | S-04.01.01 | 1 | Companions: persisted agent profiles |
| R-32 | S-04.01.02 | 1 | Skills: procedures fetched on demand |
| R-33 | S-04.01.03 | 2 | Sub-agents for context isolation |
| R-34, R-35 | S-04.01.04 | 2 | The five roles, wired to what already exists |
| R-36, R-37, R-40 | S-05.01.01 | 3 | A crawler with a frontier, not a loop |
| R-38 | S-05.01.02 | 1 | Extraction packs as declared data |
| R-39 | S-05.01.03 | 2 | Take a competitor post apart and rebuild the shape |
| R-41, R-42 | S-06.01.01 | 1 | Workspaces with their own keys and their own logins |
| R-43 | S-06.01.02 | 2 | Three-level permissions |
| R-44 | S-06.01.03 | 2 | Cost estimated before a run and ledgered after |
| R-45, R-46 | S-06.01.04 | 2 | Routines that fire agent runs on a schedule or an event |
| R-47 | S-06.01.05 | 2 | Deployment, monitoring and rollback |
| R-29 | S-06.02.01 | 1 | No secret may enter a model prompt |
| R-48 | S-06.02.02 | 2 | Every endpoint authorises and validates |
| R-49 | S-06.02.03 | 1 | Cost and latency budgets per run |
| R-50 | S-06.02.04 | 1 | Data deletion and subject access |
| R-51 | S-06.02.05 | 1 | The UI is usable by keyboard and screen reader |
| R-53 | S-07.01.01 | 2 | An MCP client |
| R-54 | S-07.01.02 | 1 | Native OAuth integrations |
| R-55 | S-07.01.03 | 1 | Meeting transcription with no bot in the call |
| R-56 | S-07.01.04 | 1 | Reports and artifacts |

## Deferred

No stories in this state.

## WP1 recovery evidence

R-91 / S-06.02.09 covers CRM connection ownership. R-95 / S-06.02.11 covers
complete durable-state recovery. Together they carry audit A01, A02, A03, A04
and A17. The [closure report](docs/audits/2026-09-08-wp1-completion.md) maps
each finding to its acceptance tests and records the real-service CI evidence.
The [operations guide](docs/architecture/WP1_OPERATIONS.md) defines deployment,
migration, archive limits, recovery and rollback.
