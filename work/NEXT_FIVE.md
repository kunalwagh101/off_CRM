# Next five capabilities · planned 2026-11-17, certified 2026-11-19

Owner: Codex /root. Delivery mode: TASK. Implementer: senior engineer.
The user authorised the first three capabilities, including all their acceptance
criteria. Work follows the existing story IDs and two-item WIP limit. Claim each
story in BOARD.md before code; unclaimed stories remain available to others.

1. S-03.02.05 — Configurable browser platforms (F-03.02)
   - AC1: a declared platform supports sign-in, connection state, pace and budgets.
   - AC2: missing required fields fail at load time with the platform name.
   - Tasks: extract current defaults into packaged YAML; validate closed schema,
     URLs, domains, signals and finite limits; wire existing consumers; preserve
     built-in behaviour; prove a new platform without code edits.
2. S-02.02.02 — Editable run plans (F-02.02)
   - AC1: exactly one PLAN.md exists per started run.
   - AC2: owner edits are read before each subsequent model decision.
   - Tasks: private create-once Markdown plan; fresh bounded reads; pass through
     the existing broker; preserve on restart; checklist rendering; fail closed
     on missing, oversized or redirected plan files.
3. S-04.01.01 — Persisted companions (F-04.01)
   - AC1: a companion run uses only granted tools and permitted memory scopes.
   - Tasks: validated named profiles, workspace-scoped persistence and CRUD;
     run binding; enforce grants in host code; push only explicitly permitted
     memory; preserve profile binding across resume; document use.
4. S-05.01.01 — Crawler frontier (F-05.01), DONE after CI run 2291
   - AC1: honour robots.txt and crawl delay.
   - AC2: unchanged pages are revisited less often than changing pages.
   - AC3: exclude session-gated platforms.
   - Tasks: persisted frontier, host scheduling, content change history,
     inspection, robots and navigation security tests.
5. S-06.01.01 — Workspace isolation (F-06.01), planned only
   - Tasks: inspect existing key and connection boundaries; define workspace
     selection contract; isolate storage and access; test cross-workspace
     requests, credentials, lifecycle and recovery.

## Architecture and contracts

Reuse browser identity, policy, pacing, budget and sign-in modules. One validated
registry supplies their existing interfaces; no new provider or network path.
Plans live beside each trace and enter EgressRequest.instructions through the
broker. Companions constrain the existing ten browser verbs; no arbitrary code,
provider retrieval, implicit recall or auto-confirmation is added. Persist
workspace-scoped profiles locally. No cache: these small owner-edited files must
be read fresh. Revisit caching only with measured read latency.

## Checks and completion

Establish locked dependencies, full Python baseline and board verifier first.
For each behaviour: acceptance test RED, implementation GREEN, affected regression.
Probe malformed config, URL/domain confusion, path traversal, symlinks, secret
scanning and attempted tool/scope escalation locally. Run full Python regression,
critical Ruff gate, frontend tests/build, and the board verifier after changes.
Review diffs separately; label self-review honestly. Record exact results in the
board, update BUILD_STATE, CHANGELOG, DEMO, TRACEABILITY and logs. No live provider
calls, remote penetration testing or deployment is implied by local checks.

## Execution record and task ownership

All three selected stories were claimed and committed before their code edits.
They are now IN_REVIEW, owned by Codex /root. No items remain IN_PROGRESS.
S-05.01.01 was subsequently claimed and implemented on continuation (2026-11-19);
S-06.01.01 remains READY and unclaimed. See CRAWLER_WORK_ORDER.md and CRAWLER_EVIDENCE.md.

| Task | Story | Work | Status |
|---|---|---|---|
| T-03.02.05.a | S-03.02.05 | Extract six built-in identities, pace, rules and budgets into packaged YAML | DONE (CI 2291) |
| T-03.02.05.b | S-03.02.05 | Validate declarations and reject duplicate/unsafe policy fields | DONE (CI 2291) |
| T-03.02.05.c | S-03.02.05 | Integrate sign-in, status, account catalogue and budget consumers | DONE (CI 2291) |
| T-03.02.05.d | S-03.02.05 | Prove new platform and registry removal/restoration without losing accounts | DONE (CI 2291) |
| T-02.02.02.a | S-02.02.02 | Create one private, owner-editable plan per run | DONE (CI 2291) |
| T-02.02.02.b | S-02.02.02 | Read edits before the next decision through the existing broker | DONE (CI 2291) |
| T-02.02.02.c | S-02.02.02 | Preserve plans on resume and render safe report checklists | DONE (CI 2291) |
| T-02.02.02.d | S-02.02.02 | Refuse unsafe/missing plans and prove real broker secret blocking | DONE (CI 2291) |
| T-04.01.01.a | S-04.01.01 | Persist validated companion CRUD with workspace separation | DONE (CI 2291) |
| T-04.01.01.b | S-04.01.01 | Enforce grants for all ten browser verbs | DONE (CI 2291) |
| T-04.01.01.c | S-04.01.01 | Filter explicit scoped memory and preserve INTERNAL classification | DONE (CI 2291) |
| T-04.01.01.d | S-04.01.01 | Refuse grant widening/removal on resume, bound context and scan secrets | DONE (CI 2291) |
| T-05.01.01.a | S-05.01.01 | Persist crawl frontier and inspect pending URLs | DONE (CI 2291) |
| T-05.01.01.b | S-05.01.01 | Honour robots rules and host delays | DONE (CI 2291) |
| T-05.01.01.c | S-05.01.01 | Schedule revisits from observed changes | DONE (CI 2291) |
| T-05.01.01.d | S-05.01.01 | Exclude session-gated platforms and test navigation safety | DONE (CI 2291) |
| T-06.01.01.a | S-06.01.01 | Trace existing workspace key and session consumers | Planned, unclaimed |
| T-06.01.01.b | S-06.01.01 | Enforce workspace selection and storage boundaries | Planned, unclaimed |
| T-06.01.01.c | S-06.01.01 | Test cross-workspace credential and connection access | Planned, unclaimed |
| T-06.01.01.d | S-06.01.01 | Verify lifecycle, failure and recovery behaviour | Planned, unclaimed |

## Evidence limits

The test-first RED checks cover registry behaviour, owner plans and the companion
tool boundary. Additional edge/security tests were added during implementation
and review; they are not represented as having been written first. Separate
self-review found ambiguous duplicate YAML keys and corrected the loader with a
reproducing test. Review was by the implementer, not an independent agent.

The three new acceptance suites contain 75 cases. The combined acceptance,
resume, report, broker-wall and security-audit run passes 175. The full Python
suite passes 1994, skips 4 environment-gated cases and fails 21 existing
Chromium cases. The original baseline passed 1918, skipped 4 and failed 22;
UV_TOOL_DIR resolved Graphify, leaving the same 21 browser failures. Browser
policy was not modified. Frontend: 116 passed; production build passed. Wheel
contents include all new runtime modules and the YAML declaration.

Local probes cover configuration ambiguity, malformed URLs, domain lookalikes,
path traversal, symlinks, XSS, cross-workspace inputs, secret egress, tool grants
and resume escalation. They are not a remote or independent penetration test.
No live model/provider calls, remote release, or deployment were performed.
The required live-browser and full board-evidence gate remains unmet (D-51).

Continuation 2026-11-19: the crawler adds persisted queues, shared host pacing,
robots/redirect continuation, change-based revisit scheduling, leases, retries,
CLI management and rollback proof. Its 45 acceptance cases and wider 125-check
suite pass. The same D-51 browser gate prevents DONE certification.

## Current certification · 2026-11-19

The first four capabilities are DONE after GitHub run 2291 passed 2060 Python
tests, all 55 historical evidence commands, frontend 116 and the build. The
earlier IN_REVIEW paragraphs describe the local-only stage before CI. The fifth
capability, S-06.01.01, remains READY and unclaimed. See CI_VERIFICATION.json,
ci-run-2291.log and REMOTE_VERIFICATION.md. The review branch is not merged.
