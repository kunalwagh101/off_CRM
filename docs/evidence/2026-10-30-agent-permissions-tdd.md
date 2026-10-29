# F-06.01.02 — Three-level agent permissions, test-first evidence (2026-10-30)

## Scope and code
The install token can `PUT /api/v1/agent-permissions` using a strict request model and inspect a workspace's policy via `GET`. The current workspace member may read its own policy, not edit global policy. Modes are allow/ask/deny and rules are limited to the existing ten declared browser verbs. Stored policies follow the existing WorkspaceAISettingsStore (local root or hosted database), not a new ephemeral permissions database.

AgentRun checks before any chosen action or cached `read`, returning `needs_permission` or `permission_denied` with a secret-safe permission_gate trace. The scheduled RoutineAgentExecutor also checks its initial `goto` before creating a browser, preventing bypass D-324. ChatPermissionGrants are in-memory only, valid within one hour/close, and cannot override deny. **No authenticated attended chat grant/close UI/API exists yet.**

## Actual Render timeline
| Stage | Exact source, deploy | Observed |
|---|---|---|
| Test-first RED | `926144d67617214134a74afe8de51a9f20c7da92`, `dep-dbhrl9d9fdbs73aejus0` | Targeted test collection ERROR because `agent.permissions` was missing; existing hosted storage 7 passed |
| Initial GREEN | `2e9872f26c706ab2253737266232f1f03f0ba392`, `dep-dbhrmilg1s2s73fgfpbg` | **20 targeted permission and AgentRun tests passed** |
| Initial navigation bypass closed | `27aad6e7fb88b139dda13a52c44ec31ba6a0ae14` | Added two pre-browser `goto` deny/ask tests and rejection before any container/network access |
| Full QA uncovered D-325 | `b27d6de1a260ba03549311a59afbe07c37be1032`, `dep-dbhro9nlk1mc738sjic0` | Full SQLite **2798 passed, 1 failed, 45 skipped, 44 warnings**. Existing API contract test rejected raw dict request body. This was a real failure, not waived. |
| Strict typed request fix | `851d6debc44c9c38f64b331d5f923e1dcdd0d15b`, `dep-dbhrs0l9fdbs73af8e60` | Targeted **22 passed**, typed-body contract **1 passed**, prior hosted-readiness **7 passed**, Ruff clean. Full suites and final deploy status were still pending at first entry. |

## Required completion evidence, still pending
- Actual full SQLite and PostgreSQL test summaries on corrected source `851d6de`; frontend npm test/build/security audit and Chromium QA, independent pen test for wider agent tool adapters, live owner grant + authenticated chat close/expiry; full Git-history board verifier.
- S-04.01.01 upstream companion feature remains IN_REVIEW, so this cannot become DONE even if all local tests pass.
- No `main` changes, no production deployment, no real provider credentials or customer records used. API/UI for attended grant requests and chat lifecycle not yet available; do not claim that all three levels work for customers today.
- Remaining production and developer-tool security issues tracked elsewhere (including D-321 two moderate dev advisories).
