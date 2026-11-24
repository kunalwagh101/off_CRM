# F-06.02 — complete direct-story acceptance tracker

**Snapshot:** 2026-11-24, off_CRM `develop` (scope corrected against backlog; board statuses updated through S-06.02.20 verified closeout). **Authoritative:** [board](../../BOARD.md), [backlog](../../PRODUCT_BACKLOG.md), [Done rules](../../DEFINITION_OF_DONE.md), [audit work order](../work-orders/S-06.02.23-audit-recheck.md). Do not treat this inventory as certification.

## Scope integrity check (2026-11-24)

Corrected five story blocks to match `PRODUCT_BACKLOG.md`: S-06.02.20 (2 cases, not 50), S-06.02.55 (3, not 0), S-06.02.56 (3, not 0), S-06.02.57 (4, not 0), and S-06.02.69 (3, not 63). Earlier extraction accidentally crossed F-12.01/F-07.01 boundaries and included unrelated requirements. `tests/test_f0602_tracker_scope.py` now checks all 69 story IDs, exact acceptance text and case counts. This is **scope documentation only**, not verification of those stories or hosted acceptance.

## Acceptance-text integrity (2026-11-24)

The initial count-only comparison missed 30 cut-off acceptance cases in the pre-existing generated tracker. All 198 Given/When/Then cases have now been reconciled word-for-word (whitespace-normalised) against the original 69 story sections in `PRODUCT_BACKLOG.md`; four explicitly numbered task descriptions are also restored in full. The automated guard compares text as well as counts. This establishes an accurate development checklist, **not** implementation or manual hosted acceptance.

## Scope hierarchy

**One feature** F-06.02 with **69 directly contained stories**: 22 DONE, 42 IN_REVIEW, 3 BACKLOG, 1 IN_PROGRESS, 1 BLOCKED, 0 READY. **47 not DONE.** The roadmap does not number complete independent sub-feature/sub-story/task/sub-task trees for every story. The logical sub-feature clusters are: (i) identity, permissions, privacy, secrets; (ii) data safety, idempotency, hosting, scheduler/worker; (iii) AI/model cost, factuality and egress; (iv) media/browser safeguards; (v) operator UI, accessibility and live quality checks. These are labels, **not invented roadmap IDs**.

**Owner override (2026-11-24):** Render is excluded for F-06.02. Substitute GitHub-hosted disposable real-app Docker/HTTP, Chromium and PostgreSQL evidence for the Render-specific QA instruction and per-story QA labels below; do not deploy or contact Render. Customer deployment and other external acceptance remain separately unverified. No statuses or acceptance criteria changed by this override.

Each Given/When/Then below is a required *acceptance sub-case*. For each case: implement through the real API/UI/store/worker; run the failing test first where relevant, then unit/integration/API, adverse/security, regression and end-to-end; start the exact commit on a disposable GitHub runner or local environment; test the API/UI/DB and error path, inspect responses/logs, verify reload/restart/rollback and evidence; run `uv run pytest -q`, frontend tests/build, real PostgreSQL, `uv run python scripts/verify_board.py`, independent penetration and owner acceptance where applicable. **Passing a mock does not prove real provider operation.**

## 2026-11-24 — Disposable release image verification

- At `84d82fb`, the [five-job regression run](https://github.com/kunalwagh101/off_CRM/actions/runs/45407238801) passed Python 3.10–3.12, real PostgreSQL, the frontend build and tests, Chromium logout and campaign selection, and the full-history board verifier. The [real release image](https://github.com/kunalwagh101/off_CRM/actions/runs/45407238577) passed Docker build, readiness, authenticated HTTP, logout revocation across container restart, dependency parity and cleanup.
- D-525 / A17: the original workflow inspected only HTTP 200 in both readiness probes. A source check failed on both original probes. At `3dbc890` both require the JSON status `ready`. The [actual release-image run](https://github.com/kunalwagh101/off_CRM/actions/runs/45413181058) passed initial and restart readiness. The workflow regression executes both probe scripts with degraded and ready HTTP 200 responses.
- D-526 / A17: the local Compose health check also accepted any successful HTTP response. It now requires HTTP 200 and JSON status `ready`. The regression executes the Compose command with both readiness responses. The container workflow also resolves it with `docker compose config` and executes it against the running release image.
- Local commands were blocked by `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. The GitHub runs use disposable data and test services. Customer deployment, independent recovery, real provider and security review evidence remain open. S-06.02.23 stays IN_PROGRESS.

## 2026-11-24 — Focused acceptance for seven implemented fixes

The SQLite and PostgreSQL jobs at `94e89b6` both passed the focused regression step in [run 45424459700](https://github.com/kunalwagh101/off_CRM/actions/runs/45424459700). S-06.02.60 (quota), .61 (provider setup failure), .62 (HTTP idempotency), .66 (billing receipts), .67 (owner-only privacy), .68 (video isolation) and .69 (image isolation) moved to IN_REVIEW. The tests use disposable state and simulated transport where specified. Customer data migration, independent recovery, hosted worker operation, real providers and the release audit remain open.

## 2026-11-24 — Archived WP1 recovery checks on develop

On `631079d`, [production container run 45434745341](https://github.com/kunalwagh101/off_CRM/actions/runs/45434745341) passed the archived WP1 recovery path with a real release image, a disposable named volume, a read-only container root and an unprivileged app. The check killed and replaced the container, confirmed the campaign and file survived, and restored both after post-backup changes. At `26e3b10`, [Chromium run 45437636843](https://github.com/kunalwagh101/off_CRM/actions/runs/45437636843) downloaded an encrypted backup in Settings, restored it through the UI and confirmed that the original campaign was recovered. D-528 records and resolves the browser harness setup failures. These checks cover WP1 recovery under the audit. S-06.02.21, S-06.02.23 and S-06.02.27 retain their board statuses pending the remaining acceptance evidence.

## Directly contained stories and all written acceptance cases

### S-06.02.01 — No secret may enter a model prompt

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** No secret may enter a model prompt.

**Dependencies:** **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** scanner findings.

**Acceptance sub-cases (1 written):**

1. **Given** the payload builder, **when** any request is assembled, **then** a scan for credential-shaped material passes.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.02 — Every endpoint authorises and validates

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Every endpoint authorises and validates.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated reachability.

**Acceptance sub-cases (2 written):**

1. **Given** any API endpoint outside the documented closed public bootstrap / signed-callback allowlist, **when** called without an authenticated session or install token, **then** it refuses before business logic runs.
2. **Given** any body, **when** it is malformed, **then** the response is a 4xx with a bounded message, never a stack trace and never an echo of sensitive request-body content.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.03 — Cost and latency budgets per run

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Cost and latency budgets per run.

**Dependencies:** **Dependencies:** S-06.01.03, S-11.01.04. **Size:** S. **Indicator:** new work

**Acceptance sub-cases (4 written):**

1. **Given** a positive spend ceiling, **when** the next model decision would cross it, **then** no provider call starts and the run ends `over_budget` with the ceiling and projected next spend recorded.
2. **Given** a positive latency ceiling, **when** a completed provider or browser operation makes cumulative recorded `took_ms` reach or exceed it, **then** no new unit of work starts and the run ends `over_latency` with ceiling, actual latency and any in-flight overrun recorded.
3. **Given** a run that is resumed, **when** no new latency ceiling is supplied, **then** its original ceiling and all earlier measured latency still count; raising the ceiling requires an explicit argument.
4. **Given** a zero ceiling, **when** the run executes, **then** that dimension is uncapped exactly as before; a negative, boolean or non-integer latency ceiling is refused before the run starts.

**Named tasks/subtasks:** **Tasks:** T-06.02.03.a integrate latency with the existing trace/run/resume path (<=1 day); T-06.02.03.b acceptance and regression tests (<=1 day); T-06.02.03.c demo, traceability, evidence and verifier certification (<=1 day).

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.04 — Data deletion and subject access

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Data deletion and subject access.

**Dependencies:** **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** deletion requests unfulfilled.

**Acceptance sub-cases (3 written):**

1. **Given** an identified person, **when** a subject-access request is executed, **then** every registered store reports the matching records/artifacts it holds with store name, record class and provenance, without exposing another subject's data.
2. **Given** a confirmed deletion request, **when** it succeeds, **then** the person's data is removed from every registered mutable store including CRM research/discovery records, crawler URL/cache state that identifies the subject, trace captures/screenshots and generated subject-specific artifacts, and a non-personal deletion receipt records what store classes were cleared.
3. **Given** any registered store fails deletion, **when** the operation runs, **then** the request is not reported complete: the receipt names the failed store, retry is safe/idempotent, and no false success is returned.

**Named tasks/subtasks:** **Tasks:** T-06.02.04.a define one store inventory/subject-match contract and enumerate current personal-data stores (<=1 day); T-06.02.04.b implement subject access plus idempotent deletion adapters using existing transactions and filesystem primitives (<=1 day); T-06.02.04.c cross-store failure, isolation and retry tests (<=1 day); T-06.02.04.d docs, rollback/receipt, demo, traceability and verifier evidence (<=1 day).

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.05 — The UI is usable by keyboard and screen reader

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The UI is usable by keyboard and screen reader.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** accessibility audit findings.

**Acceptance sub-cases (1 written):**

1. **Given** any interactive screen, **when** navigated by keyboard alone, **then** every action is reachable and focus is visible.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.06 — The delivery process is verifiable by the owner

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The delivery process is verifiable by the owner.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unverifiable DONE claims.

**Acceptance sub-cases (2 written):**

1. **Given** a DONE item whose named test does not exist, **when** the verifier runs, **then** it exits non-zero.
2. **Given** an orphan requirement, **when** the verifier runs, **then** it exits non-zero.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.07 — An answered question stops blocking

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** An answered question stops blocking.

**Dependencies:** **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** decisions recorded vs questions deleted.

**Acceptance sub-cases (2 written):**

1. **Given** a question marked answered, **when** an item citing it enters READY, **then** the verifier passes.
2. **Given** a question with no answer, **when** an item citing it enters READY, **then** the verifier still fails.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.08 — One runner for every evidence command

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** One runner for every evidence command.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** verifier failures caused

**Acceptance sub-cases (2 written):**

1. **Given** the board, **when** every DONE evidence command is read, **then** they all invoke the same runner.
2. **Given** a clean checkout, **when** the documented setup is run and the verifier follows, **then** it passes without a second, undocumented step.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.09 — Every database write goes through one guard

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Every database write goes through one guard.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unguarded `.execute(` call

**Acceptance sub-cases (3 written):**

1. **Given** concurrent transactions on `OutreachStore`, **when** they run, **then** no write is lost and no transaction error is raised. **(fixed 2026-09-08)**
2. **Given** a bare `store.connection.execute(...)` outside a transaction, **when** another thread holds an open transaction, **then** it does not read uncommitted rows or get committed by that transaction. **(fixed 2026-09-09)**
3. **Given** a long-lived connection assigned anywhere in `outreach/`, **when** the package is parsed, **then** it is wrapped by `GuardedConnection`. **(fixed 2026-09-09)**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.10 — The local API is not open to whatever can reach the port

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The local API is not open to whatever can reach the port.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated 200s on

**Acceptance sub-cases (3 written):**

1. **Given** no token and no demo login, **when** the app is constructed, **then** it refuses to start and says how to fix it. **(done)**
2. **Given** a local install that has never been configured, **when** it starts through `run_offsetx_web.py`, **then** a token is generated at `0600`, printed once, and stable across restarts. **(done)**
3. **Given** a request whose `Host` is not one this server answers to, **when** it arrives, **then** it is refused with 421 before any other check, including the public-path exemption. **(done)**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.11 — The verifier catches a stale READY column

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The verifier catches a stale READY column.

**Dependencies:** **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** stories found stale

**Acceptance sub-cases (3 written):**

1. **Given** a story in `BACKLOG` whose declared dependencies are all `DONE` and which has no open question against it, **when** the verifier runs, **then** it names the story as ready to move.
2. **Given** a story in `READY` whose dependencies are not all `DONE`, **when** the verifier runs, **then** it fails — the Definition of Ready is not advisory.
3. **Given** a story whose dependency line names an id that does not exist, **when** the verifier runs, **then** it fails rather than treating the dependency as satisfied.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.12 — A recorded commit must be on the branch

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A recorded commit must be on the branch.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** board shas not on the

**Acceptance sub-cases (3 written):**

1. **Given** a DONE entry whose `commit:` is reachable from `HEAD`, **when** the verifier runs, **then** it passes.
2. **Given** a DONE entry whose `commit:` names an object that exists but is not on the branch — the usual cause is `git commit --amend` after the sha was written down — **when** the verifier runs, **then** it fails and names the entry.
3. **Given** a DONE entry whose `commit:` names no object at all, **when** the verifier runs, **then** it fails.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.13 — A defect log and a decision log the next session can read

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A defect log and a decision log the next session can read.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** defects found twice —

**Acceptance sub-cases (4 written):**

1. **Given** `DEFECT_LOG.md`, **when** it is read, **then** every defect found carries an id, the date it was found, its kind, one plain-English line saying what went wrong, and whether it is fixed or filed.
2. **Given** a defect recorded as `open`, **when** the verifier runs, **then** it fails unless that row names a backlog id that exists — an unfixed defect with nowhere to go is a defect nobody will fix.
3. **Given** two rows sharing an id, **when** the verifier runs, **then** it fails. An id that points at two things points at neither.
4. **Given** `DECISIONS.md`, **when** it is read, **then** every entry says what was given up, because a decision with no cost was not a decision.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.14 — A test should not hardcode a trace step id

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A test should not hardcode a trace step id.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** tests broken by an

**Acceptance sub-cases (2 written):**

1. **Given** a test that needs a particular step's id, **when** it runs, **then** it locates the step by kind or content, not by a literal like `step-000002`.
2. **Given** a new step added anywhere in a run, **when** the suite runs, **then** no test fails because the numbering moved.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.15 — CI gives the verifier the repository it claims to verify

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** CI gives the verifier the repository it claims to verify.

**Dependencies:** **Dependencies:** S-06.02.08, S-06.02.12. **Size:** S. **Indicator:** verifier

**Acceptance sub-cases (3 written):**

1. **Given** a DONE evidence commit older than `HEAD`, **when** CI runs the verifier, **then** full ancestry is available and a reachable commit passes.
2. **Given** DONE frontend evidence, **when** CI runs the verifier, **then** `npm ci` has already completed and the named frontend test can execute.
3. **Given** the CI workflow itself, **when** its regression test runs, **then** both ordering constraints above are pinned in code.

**Named tasks/subtasks:** **Tasks:** T-06.02.15.a repair checkout/dependency ordering (<=1 day); T-06.02.15.b pin the workflow contract with regression tests (<=1 day); T-06.02.15.c record the defect and evidence (<=1 day).

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.16 — Resolve frontend development dependency audit findings

**Status:** DONE (source/CI frontend dependency audit only; live npm audits, patched rollback/recovery, full CI and isolated Render same-lock review verified). **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.16-frontend-dependency-audit.md).

**Requirement:** Resolve frontend development dependency audit findings.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit

**Acceptance sub-cases (3 written):**

1. **Given** a clean `npm ci`, **when** `npm audit --omit=dev` runs, **then** the production dependency tree reports zero known vulnerabilities.
2. **Given** the full development dependency tree, **when** `npm audit` runs, **then** no high-severity finding remains unresolved or silently ignored.
3. **Given** a remediation that requires a breaking upgrade, **when** it is applied, **then** frontend tests and the production build prove the upgrade rather than relying on `npm audit fix --force`.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Source/CI dependencies audit satisfied in GitHub 45266709119 5/5 and isolated Render same package-lock review. Parent F-06.02, current app Render release and customer security acceptance remain OPEN.

### S-06.02.17 — DONE may not depend on unfinished work

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** DONE may not depend on unfinished work.

**Dependencies:** **Dependencies:** S-06.02.11. **Size:** S. **Indicator:** DONE stories whose

**Acceptance sub-cases (2 written):**

1. **Given** a DONE story that depends on a READY, BACKLOG or BLOCKED story, **when** the verifier runs, **then** it fails and names both stories.
2. **Given** a DONE story whose declared dependencies are all DONE, **when** the verifier runs, **then** the dependency check passes.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.18 — Restore executable CI runner capacity

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.18-ci-runner-capacity.md).

**Requirement:** Restore executable CI runner capacity.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** CI jobs with zero workflow

**Acceptance sub-cases (3 written):**

1. **Given** the current private repository and `.github/workflows/ci.yml`, **when** a push or pull-request run starts, **then** the `quality` job reaches at least runner setup/checkout and exposes workflow steps and logs.
2. **Given** the hosted job cannot acquire a runner because of an account, repository or GitHub Actions service restriction, **when** the failure is inspected, **then** the blocker is recorded explicitly and no application story uses that run as passing evidence.
3. **Given** GitHub-hosted execution is unavailable but an approved self-hosted runner is intentionally configured, **when** the same locked commands run, **then** the evidence contract remains unchanged; runner choice may not weaken tests or the verifier.

**Named tasks/subtasks:** **Tasks:** verify owner Billing & licensing → Actions usage/budgets/payment state; verify repository Settings → Actions → General; if both are clean, provide GitHub Support the failing run/job IDs and timestamps; re-run the unchanged locked workflow only after runner capacity is restored.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.19 — One working branch holds everything built, and it is green

**Status:** BLOCKED. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** One working branch holds everything built, and it is green.

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** branches carrying unmerged

**Acceptance sub-cases (3 written):**

1. **Given** the thirty-odd branches of 2026-09-23, **when** they are consolidated, **then** every branch is either merged, ported, or shown by a line-coverage and status comparison to be contained or superseded, and archived under `archive/<branch>` before it is deleted.
2. **Given** two lines that used the same story, requirement, defect or decision IDs for different things, **when** they meet, **then** the later ones are renumbered and each renumbered entry says what it was called before.
3. **Given** the consolidated branch, **when** the full Python suite, ruff gate, frontend tests and build, and the board verifier run, **then** all pass; a test that passed only because it checked nothing is repaired and shown to fail when the code is broken on purpose.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.20 — The verifier tells a shallow clone apart from a missing commit

**Status:** DONE (repository-only story, GitHub full-depth CI 45262723267 all five jobs successful; board verifier 73/73; isolated Render Git fixtures 67/67). **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.20-shallow-git-history.md).

**Requirement:** The verifier tells a shallow clone apart from a missing commit.

**Dependencies:** S-06.02.12. **Size:** S. **Indicator:** verifier failures

**Acceptance sub-cases (2 written):**

1. **Given** a shallow clone that lacks a recorded commit, **when** the verifier runs, **then** it fails with a message naming the shallow clone and `git fetch --unshallow`, not one saying the commit does not exist.
2. **Given** the CI workflow, **when** it checks out the repository, **then** it fetches full history so the ancestry rule can run there.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Direct source/CI acceptance satisfied for Git history diagnostics; no customer-host functionality is claimed and the F-06.02 parent remains IN_PROGRESS.

### S-06.02.21 — Durable customer state and safe recovery (audit WP1)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md).

**Requirement:** Durable customer state and safe recovery (audit WP1).

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** restores that lose a

**Acceptance sub-cases (4 written):**

1. **Given** production configuration, **when** the durable root is ephemeral, **then** the app refuses to start rather than silently losing state.
2. **Given** a backup, **when** it is made, **then** every durable file under the data directory is in it — new stores included without editing a list — with a versioned, hashed manifest; only named rebuildable caches are left out.
3. **Given** a restore, **when** it succeeds or is rejected, **then** writers are drained first, the whole workspace is swapped under a journal, every service is reopened and health-checked, and a failure rolls back to the previous generation; an interrupted swap rolls back at the next start.
4. **Given** readiness, **when** a required store or durable path cannot be opened or written, or recovery is in progress, **then** `/health/ready` is red.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.22 — A created or selected campaign stays the active workspace

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md).

**Requirement:** A created or selected campaign stays the active workspace.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** imports into a campaign the

**Acceptance sub-cases (2 written):**

1. **Given** a new campaign, **when** it is created, **then** it becomes the selected campaign and stays so after the campaign list refreshes.
2. **Given** a selected campaign outside the bounded list, **when** the list refreshes, **then** the selection is kept by reading its detail; only a 404 for that campaign lets the selection fall back.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.23 — Re-check the 7 September production audit on `develop`

**Status:** IN_PROGRESS. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.23-audit-recheck.md).

**Requirement:** Re-check the 7 September production audit on `develop`.

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** audit findings with

**Acceptance sub-cases (1 written):**

1. **Given** a finding the consolidation did not re-check, **when** its reproduction from `docs/audits/2026-09-07-production-audit.md` is run against `develop`, **then** it becomes a test that fails while the finding holds — or the finding is closed with the test that shows it no longer does.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.24 — Every process that writes the workspace holds its lease

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.24-workspace-lease-for-clis.md).

**Requirement:** Every process that writes the workspace holds its lease.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** processes that write the

**Acceptance sub-cases (3 written):**

1. **Given** a restore in progress, **when** the outreach, notebook or eval CLI starts, **then** it refuses with a sentence saying to retry once readiness returns, and writes nothing.
2. **Given** a CLI command running, **when** a restore starts, **then** the restore waits for it within its bound, or is refused — as for the worker.
3. **Given** a restore nobody has rolled back yet, **when** a CLI starts, **then** it refuses, as the email worker does (`D-129`).

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.25 — Every screen opens at its top, its warnings in view

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.25-screen-opens-at-top.md).

**Requirement:** Every screen opens at its top, its warnings in view.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** screens whose top is

**Acceptance sub-cases (3 written):**

1. **Given** any screen opened from the navigation, **when** it has rendered, **then** its title and first panel are fully visible below the top bar, at desktop and phone widths.
2. **Given** the campaign list failing, **when** a screen opens, **then** the "Could not refresh campaigns" panel is visible without scrolling.
3. **Given** keyboard or screen-reader use, **when** the screen changes, **then** focus still moves to the main content, as `S-06.02.05` requires.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.26 — CI runs the suite on every Python the package supports

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.26-python-matrix.md).

**Requirement:** CI runs the suite on every Python the package supports.

**Dependencies:** **Dependencies:** `S-06.02.18` (CI runners). **Size:** S. **Indicator:**

**Acceptance sub-cases (2 written):**

1. **Given** a push, **when** CI runs, **then** the whole suite runs on 3.10, 3.11 and 3.12, each installed from the lock, and a failure on any fails the check.
2. **Given** a version added to `pyproject.toml`, or the image's version changed, **when** the suite runs, **then** a test fails until CI names it.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.27 — The audit's live harness runs against `develop`

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The audit's live harness runs against `develop`.

**Dependencies:** **Dependencies:** `S-06.02.18`. **Size:** M. **Indicator:** harness checks

**Acceptance sub-cases (1 written):**

1. **Given** the audit's live harness (`verification/` on the archived `integration/main-consolidation`), **when** it can run — CI runners (`S-06.02.18`) or a trusted machine with Docker, Chrome and PostgreSQL — **then** it runs against `develop` and its results are recorded, skips counted as failures.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.28 — A command-line tool locks the workspace it actually opens

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.28-path-aware-workspace-lock.md).

**Requirement:** A command-line tool locks the workspace it actually opens.

**Dependencies:** **Dependencies:** `S-06.02.24`. **Size:** M. **Indicator:** writes made

**Acceptance sub-cases (3 written):**

1. **Given** an explicit `--db`, `--context` or `--token`, or an absolute `OFFSETX_OUTREACH_DB` or `OFFSETX_GMAIL_TOKEN`, naming the web app's files, run from any folder, **when** a restore holds the web app's workspace, **then** the tool refuses — it does not lock a `local_data` beside the current folder.
2. **Given** `OFFSETX_DATA_DIR` set only in `.env`, **when** any of the six tools runs, **then** it resolves the same data directory as `offsetx-web`; today only `offsetx-web` and `offsetx-outreach` read `.env`.
3. **Given** `offsetx-artifacts --run-dir .` from inside a run the app recorded, **when** a restore runs, **then** it refuses.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.29 — The NVIDIA reasoning model answers in chat

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The NVIDIA reasoning model answers in chat.

**Dependencies:** **Dependencies:** none. **Size:** XS. **Indicator:** provider 400s caused by

**Acceptance sub-cases (1 written):**

1. **Given** `nvidia/nemotron-3-ultra-550b-a55b` connected with a key, **when** the owner chats, **then** the request carries only options NVIDIA accepts: `max_tokens`, `temperature`, `top_p`, `chat_template_kwargs` — not `reasoning_budget`.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.30 — A provider connects from the Connectors screen as shown

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A provider connects from the Connectors screen as shown.

**Dependencies:** **Dependencies:** none. **Size:** XS. **Indicator:** connect attempts refused

**Acceptance sub-cases (2 written):**

1. **Given** the Connectors form's defaults — call cap 0, spend cap 0 — **when** the owner connects a provider, **then** it connects, and 0 means no cap of ours.
2. **Given** a value the server refuses, **when** the screen shows the error, **then** the message names the field and what was wrong.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.31 — Provider keys come only from the app

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.31-keys-only-from-the-app.md).

**Requirement:** Provider keys come only from the app.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** workspaces able to use a

**Acceptance sub-cases (3 written):**

1. **Given** `OFFSETX_AI_<PROVIDER>_KEY` set on the server, **when** any workspace lists or uses providers, **then** that variable supplies nothing.
2. **Given** any web request — a draft, a provider profile — **when** it names a server environment variable or brings its own provider, **then** it is refused; and a login sees and uses only its own workspace's profiles (`D-154`, `D-155`, found by the story's fresh-context review).
3. **Given** no stored key, **when** the owner connects a provider that needs one, **then** it is refused with a sentence saying to paste the key first; a local server that needs no key still connects.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.32 — The connect form offers limit presets

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.32-limit-presets.md).

**Requirement:** The connect form offers limit presets.

**Dependencies:** **Dependencies:** `S-06.02.30`. **Size:** S. **Indicator:** caps set by typing

**Acceptance sub-cases (2 written):**

1. **Given** the Connect form, **when** the owner sets the call cap, **then** the choices are the provider's own limit (0), 50, 200, 1,000 or a typed number; the spend cap offers no cap (0), $1, $5, $20 or a typed amount.
2. **Given** a saved cap, **when** the form opens again, **then** it shows that cap, as its preset or as a typed number.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.33 — Trust is the owner's to change, per provider and per model

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.33-trust-per-provider-and-model.md).

**Requirement:** Trust is the owner's to change, per provider and per model.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** trust changes made without

**Acceptance sub-cases (6 written):**

1. **Given** any provider, **when** the owner lowers its trust, **then** it applies at once to every model under it, with no reason asked.
2. **Given** any model under a provider, **when** the owner sets its own trust, **then** it applies at or below the provider's tier, never above it — the provider sees everything sent to it (`DD-65`, amended after review).
3. **Given** a raise above a default, **when** the owner saves it, **then** a typed reason is required and recorded with who and when; without one nothing changes.
4. **Given** a provider raised above its default, **when** one of its models is capped because of who built it, **then** the provider's raise does not lift that model — only the model's own setting can.
5. **Given** any trust setting, **when** the owner has not typed the separate mailbox unlock phrase, **then** received mail reaches no model — no trust setting opens the mailbox (`AGENTS.md` rule 5).
6. **Given** a changed trust, **when** the owner saves the connection again, **then** the data ceiling follows the changed trust, not the default.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.34 — Connectors show how much is left

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.34-usage-remaining.md).

**Requirement:** Connectors show how much is left.

**Dependencies:** **Dependencies:** `S-06.02.32`. **Size:** M. **Indicator:** providers whose

**Acceptance sub-cases (3 written):**

1. **Given** every connected provider, **when** Connectors opens, **then** it shows today's calls counted by off_CRM against the owner's cap.
2. **Given** a provider that reports what is left — a key or balance endpoint, or rate-limit headers on its replies — **when** it has been checked or called, **then** the screen shows the provider's own figure and when it was read.
3. **Given** a provider that reports nothing (NVIDIA, checked 2026-09-25), **then** the screen says the provider does not report it, never a guess.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.35 — Drafts reach a model the owner set up on a screen

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.35-drafts-connectors.md).

**Requirement:** Drafts reach a model the owner set up on a screen.

**Dependencies:** **Dependencies:** `Q-28`. **Size:** M. **Indicator:** empty states pointing

**Acceptance sub-cases (3 written):**

1. **Given** the owner's answer to `Q-28`, **when** a model is connected the way it names, **then** the Drafts screen offers it and drafts through it, and the trust tiers, scanner and egress log apply as they do to every other model call (answer 1), or the profile form is back in Settings and lists each profile with whose it is (answer 2).
2. **Given** no model set up for the workspace, **when** Drafts opens, **then** its empty state names the screen that sets one up — a screen that exists.
3. **Given** profiles saved before `DD-68`, **then** the owner can see and confirm or remove each one there, not only through the API.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.36 — A second owner login is made on purpose

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.36-explicit-owner-login.md).

**Requirement:** A second owner login is made on purpose.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** owner logins created

**Acceptance sub-cases (2 written):**

1. **Given** the workspace form or API, **when** the id `local` is chosen, **then** the login is created only with an explicit owner choice, and the answer says what an owner login can do.
2. **Given** existing logins in `local`, **then** they keep working.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.37 — Skip navigation keeps the current screen

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.37-skip-keeps-current-page.md).

**Requirement:** Skip navigation keeps the current screen.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** skip activations changing

**Acceptance sub-cases (2 written):**

1. **Given** Settings or another screen, **when** Skip to main content is activated with Enter, **then** the route and screen stay unchanged and main receives focus.
2. **Given** a pointer activation of the same link, **when** it is used, **then** the same screen stays open and its top is visible.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.38 — Any error can be traced back the next day

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.38-traceable-errors.md).

**Requirement:** Any error can be traced back the next day.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** failures with no log

**Acceptance sub-cases (5 written):**

1. **Given** any request that fails with a 5xx, **then** the response carries a readable sentence and an error id, and standard output carries one JSON line with that id, the time, the route, the workspace and the traceback.
2. **Given** a failed worker cycle, command or background job, **then** the same: one line, an id, and the id printed with the sentence.
3. **Given** a local install, **then** the lines also go to a size-capped rotating file under `OFFSETX_DATA_DIR/logs/`; on Render, standard output only.
4. **Given** a failure whose message holds a password, key, token, cookie or a database URL with credentials, **then** none of it reaches a log line.
5. **Given** a successful request, **then** nothing is logged beyond a one-line access record (method, route, status, time taken) — no bodies.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.39 — Valid low-bitrate WebM exports pass verification

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.39-low-bitrate-export.md).

**Requirement:** Valid low-bitrate WebM exports pass verification.

**Dependencies:** **Dependencies:** S-01.02.01 (DONE). **Size:** S. **Audit:** A34, D-122. **Scope:** small WebM only; do not weaken other codecs or remove the existing threshold for unproved data.

**Acceptance sub-cases (3 written):**

1. **Given** a genuine encoded WebM with a video track, encoded video samples, correct dimensions and duration, **when** its byte length is under 4096, **then** the export passes the non-empty gate and all the other applicable existing gates.
2. **Given** a short metadata-only, zero-sample or malformed WebM, **when** it is checked, **then** it remains rejected as incomplete; a larger valid export retains its old behaviour.
3. **Given** a declared duration, dimensions or audio requirement, **when** the media disagrees, **then** those gates still refuse the export regardless of file size.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.40 — A durable email worker runs beside the deployed web app

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.40-durable-deployment-worker.md).

**Requirement:** A durable email worker runs beside the deployed web app.

**Dependencies:** **Dependencies:** S-06.03.06 (durable homes for remaining state), S-06.02.38 (traceable worker failures). **Size:** M. **Audit:** A25 / D-270. **Indicator:** due jobs processed without a manual web session.

**Acceptance sub-cases (3 written):**

1. **Given** a deployed workspace with durable CRM and queue state, **when** an approved due email is queued, **then** the independently deployed worker opens the same hosted database and processes it within an operating bound; no duplicate send after restart or lease contention.
2. **Given** the worker crashes or loses the database/provider, **when** it restarts, **then** uncertain sends remain quarantined for reconciliation, a safe error reference is logged, and no operation is silently retried.
3. **Given** the production service configuration, **when** it is reviewed or deployed, **then** a supervised worker process, health/restart policy, ownership, secrets delivery and rollback steps are present and proven on the actual hosting tier; two web services alone do not meet this acceptance.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.41 — Contacts beyond row 500 are reachable

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.41-contacts-pagination.md).

**Requirement:** Contacts beyond row 500 are reachable.

**Dependencies:** **Dependencies:** none. **Size:** S. **Audit:** A23 / D-271. **Work order:** `docs/work-orders/S-06.02.41-contacts-pagination.md`.

**Acceptance sub-cases (2 written):**

1. **Given** more than 500 contacts, **when** the owner moves between pages, **then** each row is reachable through the existing authenticated offset API and the total/range remain correct.
2. **Given** search/status change, campaign change or records removed, **when** the list reloads, **then** the page index returns to a valid slice without mixing another campaign's data.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.42 — Enrichment exports cannot run spreadsheet formulas

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.42-spreadsheet-formulas.md).

**Requirement:** Enrichment exports cannot run spreadsheet formulas.

**Dependencies:** **Dependencies:** none. **Size:** S. **Audit:** A19 / D-272. **Work order:** `docs/work-orders/S-06.02.42-spreadsheet-formulas.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a leading formula/control sequence in a report cell, **when** CSV/XLSX is generated, **then** it is literal text in the actual saved document; numeric cells retain their numeric type.
2. **Given** the same text in persisted CRM or credit/exclusion/rejection ledger rows, **when** reports are generated, **then** original state and dedupe keys remain unchanged; readable snapshots are safely escaped.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.43 — Logout revokes the copied browser session

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.43-logout-revocation.md).

**Requirement:** Logout revokes the copied browser session.

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A06 / D-273. **Work order:** `docs/work-orders/S-06.02.43-logout-revocation.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a signed session, **when** logout succeeds, **then** replay of that exact token is denied across process restarts and PostgreSQL/SQLite backends; other valid devices remain signed in.
2. **Given** a storage outage during revocation, **when** logout is attempted, **then** the app does not claim the token was revoked.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.44 — Download all filtered Contacts rows

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.44-filtered-contact-download.md).

**Requirement:** Download all filtered Contacts rows.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** M. **Work order:** `docs/work-orders/S-06.02.44-filtered-contact-download.md`.

**Acceptance sub-cases (2 written):**

1. **Given** filters and 500+ contacts, **when** I download, **then** the attachment contains every matching contact, with stable named columns and spreadsheet-safe text; no private mail bodies or internal notes.
2. **Given** an oversized or changing result, **when** I export, **then** no believable incomplete file is returned. The prior full-campaign report remains unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.45 — Category and variant filters for contacts

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.45-contact-facet-filters.md).

**Requirement:** Category and variant filters for contacts.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.45-contact-facet-filters.md`.

**Acceptance sub-cases (2 written):**

1. **Given** the active campaign, **when** its filters load, **then** only campaign categories and variants appear; combining them with text/status searches uses the existing server query.
2. **Given** a filter change, **when** the list refreshes, **then** it restarts at page one with the right count.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.46 — Marked-only contacts remain reachable

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.46-marked-only-contacts.md).

**Requirement:** Marked-only contacts remain reachable.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.46-marked-only-contacts.md`.

**Acceptance sub-cases (2 written):**

1. **Given** marked contacts, **when** I filter and export, **then** the SQL query counts/returns only them; no client-side 100-row approximation or implicit send occurs.
2. **Given** an uncheck or campaign switch, **when** records reload, **then** persistent selection remains associated with the correct campaign and empty/stale pages recover.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.47 — Large send queues are paginated

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.47-queue-pagination.md).

**Requirement:** Large send queues are paginated.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.47-queue-pagination.md`.

**Acceptance sub-cases (2 written):**

1. **Given** 211 contacts, **when** the Queue opens, **then** its default result has at most 100 items and the total and next-page controls make every contact reachable.
2. **Given** an invalid page limit or offset, **when** queried, **then** the API rejects it; the actual sender is unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.48 — Campaign-wide queue counters do not mislead

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.48-global-queue-totals.md).

**Requirement:** Campaign-wide queue counters do not mislead.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.48-global-queue-totals.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a filtered or later page, **when** loaded, **then** counts cover every campaign membership using the sender's due-time logic.
2. **Given** a future-scheduled approved draft or terminal contact, **when** counting, **then** it does not appear as ready; totals do not override final live-send preflight.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.49 — Queue views focus on actionable cohorts

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.49-actionable-queue-views.md).

**Requirement:** Queue views focus on actionable cohorts.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.49-actionable-queue-views.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a view change, **when** applied, **then** filtering happens before paging and starts at page one with a view-specific total.
2. **Given** an empty view, **when** opened, **then** the screen explains that this view has no members; switching views never approves or sends mail.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.50 — Video media and renders obey configured upload limits (A15 partial remediation)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.50-bounded-video-uploads.md).

**Requirement:** Video media and renders obey configured upload limits (A15 partial remediation).

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (3 written):**

1. **Given** a bounded upload budget, **when** the file exceeds it, **then** the API returns 413 without creating media/render records; both endpoints use `read(limit+1)`.
2. **Given** an empty or unauthenticated upload, **when** sent, **then** it is rejected before decoding/storage.
3. **Given** a valid WebM below the budget, **when** sent, **then** it is accepted and recorded.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.51 — Video uploads have a bounded request stream and concurrency gate (A15)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.51-video-upload-stream-guard.md).

**Requirement:** Video uploads have a bounded request stream and concurrency gate (A15).

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (4 written):**

1. **Given** a video-media or render POST, **when** its request body exceeds the configured per-file limit plus 16 KiB multipart overhead, **then** the ASGI reader sends 413 without invoking the endpoint or reading the rest.
2. **Given** two concurrent video upload requests on one worker, **when** a third arrives, **then** the third receives 429 and capacity is restored when an active request finishes.
3. **Given** a stalled or disconnected sender, **when** it times out or disconnects, **then** temporary data and capacity are released without media rows.
4. **Given** a small valid upload or a nonvideo request, **when** sent, **then** the previous API behaviour is preserved.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** **Tests:** `tests/test_video_upload_body_guard.py`; existing `tests/test_video_upload_security.py`. **No schema changes.** Deployment-wide multi-instance/global quotas and independent load testing remain separate production gates. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.52 — Owner sees operational scheduler health separate from web readiness

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.52-operational-health.md).

**Requirement:** Owner sees operational scheduler health separate from web readiness.

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (5 written):**

1. **Given** the install owner, **when** they call `GET /api/v1/operations/health`, **then** the report lists email automation, content automation and all-workspace agent-routine scheduler health with static codes, without secrets, customer content or raw exceptions.
2. **Given** an enabled but stopped scheduler, **when** the report is requested, **then** the relevant component is degraded and `alert_required=true`, while optional automation does not turn `/health/ready` into an HTTP 503.
3. **Given** disabled optional schedulers, **when** read, **then** they are explicitly disabled, not falsely failed.
4. **Given** invalid config or inaccessible routine inventory, **when** inspected, **then** it reports unknown and a logged error reference, never healthy.
5. **Given** no install-owner authorization, **when** requested, **then** the response is 401/403 without topology details.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** **Status:** IN_REVIEW. Real external email worker heartbeat, queue age, configured alerts and independent penetration/load testing still separate production gates. **Tests:** `tests/test_operational_health.py`. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.53 — Public visitor demo has its own visible login and isolated sample data

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.53-public-visitor-demo.md).

**Requirement:** Public visitor demo has its own visible login and isolated sample data.

**Dependencies:** **Dependencies:** none. **Size:** S. **Tests:** `tests/test_public_demo.py`, frontend login rendering, `scripts/live/review_public_demo_browser.py`. **Status:** IN_REVIEW until separate Render deployment and real browser acceptance.

**Acceptance sub-cases (5 written):**

1. **Given** a separate sample-only installation, **when** a visitor opens sign-in, **then** its public username and password are displayed and prefilled; private installations never disclose credentials.
2. **Given** the visitor credentials, **when** signed in, **then** the account is in `public-demo`, sees one paused sample campaign and three fictional contacts, and can log out without affecting another session.
3. **Given** any anonymous or visitor request, **when** it attempts a mutation other than login/logout or a connected-service read, **then** the server refuses before validation or execution.
4. **Given** private/QA storage, external database, escaped paths or private integration settings, **when** public demo mode starts, **then** startup refuses rather than publishing existing data.
5. **Given** a restart, **when** the sample-only folder is reopened, **then** no duplicate sample records appear, no scheduler starts, and stale advertised credentials cause startup refusal. **Dependencies:** none. **Size:** S. **Tests:** `tests/test_public_demo.py`, frontend login rendering, `scripts/live/review_public_demo_browser.py`. **Status:** IN_REVIEW until separate Render deployment and real browser acceptance.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** **Dependencies:** none. **Size:** S. **Tests:** `tests/test_public_demo.py`, frontend login rendering, `scripts/live/review_public_demo_browser.py`. **Status:** IN_REVIEW until separate Render deployment and real browser acceptance. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.54 — Restore actual AI and orchestration in the visitor demo

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.54-restore-visitor-ai.md).

**Requirement:** Restore actual AI and orchestration in the visitor demo.

**Dependencies:** **Dependencies:** S-06.02.53 (corrective follow-up requested by owner; upstream release verification remains open). **Size:** S. **Tests:** tests/test_public_demo_ai.py, tests/test_public_demo.py, frontend login/connectors and real Chromium acceptance. **Status:** IN_REVIEW; real provider key and original-site backup access remain external blockers. This does not claim arbitrary CRM/browser automation from chat.

**Acceptance sub-cases (6 written):**

1. **Given** a public visitor login, **when** signed in, **then** the app opens AI and exposes Chat, Compare, Plan and Image, plus provider setup.
2. **Given** two signed visitor sessions, **when** they connect keys, create chats or inspect AI logs, **then** each sees only its own AI workspace and cannot use the other's key.
3. **Given** an instruction and a connected eligible model, **when** Plan is run, **then** the existing broker calls the planner and routes each returned step to workers; missing provider setup produces a clear setup response rather than fake success.
4. **Given** logout, **when** the session is revoked, **then** its connected keys are removed and another visitor's keys remain.
5. **Given** a foreign AI log ID, **when** inspected, **then** it is not found rather than exposing a payload.
6. **Given** protected sample CRM records, **when** a visitor attempts owner, mailbox, send or CRM mutation operations, **then** those operations remain refused. **Dependencies:** S-06.02.53 (corrective follow-up requested by owner; upstream release verification remains open). **Size:** S. **Tests:** tests/test_public_demo_ai.py, tests/test_public_demo.py, frontend login/connectors and real Chromium acceptance. **Status:** IN_REVIEW; real provider key and original-site backup access remain external blockers. This does not claim arbitrary CRM/browser automation from chat.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** **Dependencies:** S-06.02.53 (corrective follow-up requested by owner; upstream release verification remains open). **Size:** S. **Tests:** tests/test_public_demo_ai.py, tests/test_public_demo.py, frontend login/connectors and real Chromium acceptance. **Status:** IN_REVIEW; real provider key and original-site backup access remain external blockers. This does not claim arbitrary CRM/browser automation from chat. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.55 — Verify numeric claims without changing sign, precision or magnitude (A18)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.55-numeric-claim-integrity.md).

**Requirement:** Verify numeric claims without changing sign, precision or magnitude (A18).

**Dependencies:** S-11.02.03 (existing verifier). **Size:** M. **Open audit:** A18 / D-354. **Work order:** docs/work-orders/S-06.02.55-numeric-claim-integrity.md. Not READY; test-first fix requires normal verification gates.

**Acceptance sub-cases (3 written):**

1. **Given** `value='42'`, **when** the host-captured quote says `-42`, `42.7`, `42,000` or `42%` as a different figure, **then** the claimed `42` must not be marked supported by the observed-finding verification path.
2. **Given** a matching signed, decimal or grouped figure, **when** a quote belongs to the captured page, **then** it may be supported with correct sign/unit/locale handling; conflicting or ambiguous representations fail closed.
3. **Given** a derived number, **when** its inputs exist, **then** unverified arithmetic cannot be reported as an observed fact merely because the model claims a total.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.56 — Reject corrupt image payloads safely (A21)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.56-complete-image-decoding.md).

**Requirement:** Reject corrupt image payloads safely (A21).

**Dependencies:** existing image gate and image runner; bounded decoder choice and limits must be decided before READY. **Size:** M. **Open audit:** A21 / D-355. **Work order:** docs/work-orders/S-06.02.56-complete-image-decoding.md.

**Acceptance sub-cases (3 written):**

1. **Given** a well-shaped PNG header but no image data, **when** the image-gate entry point processes it, **then** the candidate fails the decodes gate, even above the byte threshold.
2. **Given** truncated GIF/JPEG/WebP/PNG or hostile dimensions, **when** the gate checks it, **then** it returns a failed `GateReport`, not an uncaught parsing exception or an unsafe memory allocation.
3. **Given** a real valid image, **when** checked with supported format, dimensions and aspect ratio, **then** the result succeeds; rejecting bad images must not reject ordinary good ones.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.57 — A09: Enter handlers cannot bypass human approval

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.57-enter-approval.md).

**Requirement:** A09: Enter handlers cannot bypass human approval.

**Dependencies:** S-11.03.03 (previously implemented). **Size:** S. **Work order:** docs/work-orders/S-06.02.57-enter-approval.md. **Audit:** A09, partial remediation pending independent confirmation/DOM-change tests.

**Acceptance sub-cases (4 written):**

1. **Given** a focused textarea, rich-text editor, ordinary input without a form, non-English button or an event handler attached to the document, **when** the agent requests Enter without human approval, **then** no Enter key event is dispatched and the run needs confirmation.
2. **Given** a failed or ambiguous focused-element inspection, **when** Enter is requested, **then** it fails closed without sending the key; failure to identify a safe target is not permission.
3. **Given** an actual safe navigation key or an explicit trusted confirmation, **when** the action is invoked, **then** the original key behaviour is retained; the model cannot supply confirmed=true.
4. **Given** a controlled real Chromium form with JavaScript Enter handlers, **when** the agent tries unconfirmed Enter, **then** the page does not change to SUBMITTED; the same action with trusted owner confirmation is observable.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.58 — Factual AI cache only reuses exact evidence (A12)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.58-exact-factual-cache.md).

**Requirement:** Factual AI cache only reuses exact evidence (A12).

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A12 / D-360. **Work order:** `docs/work-orders/S-06.02.58-exact-factual-cache.md`.

**Acceptance sub-cases (3 written):**

1. **Given** a long factual document cached with 42 million or an approval statement, **when** the number or negation changes, **then** the broker must miss the old entry before any answer is returned.
2. **Given** the exact same canonical payload and same generation contract, **when** requested again, **then** the exact cached answer is returned without an additional provider call.
3. **Given** a private workspace or denied policy, **when** another workspace/policy or mailbox source requests the entry, **then** no cached data crosses that boundary or bypasses the scanner.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.59 — Cached AI outputs are scoped to the actual model and instructions (A13)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.59-cache-model-provenance.md).

**Requirement:** Cached AI outputs are scoped to the actual model and instructions (A13).

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A13 / D-361. **Work order:** `docs/work-orders/S-06.02.59-cache-model-provenance.md`.

**Acceptance sub-cases (3 written):**

1. **Given** identical content but a changed selected model on the same provider key, **when** the broker runs, **then** the new model is called instead of reusing another model's output.
2. **Given** changed system instructions or generation options, **when** the same model is selected, **then** the cache misses even when payload and provider stay the same.
3. **Given** an identical canonical payload and generation contract, **when** the result is cached, **then** the log identifies a cache hit, not a billable send, and the actual model is reported without any raw prompt in the index.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.60 — AI request and spending caps reserve atomically across workers (A11)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.60-atomic-ai-quota.md).

**Requirement:** AI request and spending caps reserve atomically across workers (A11).

**Dependencies:** **Dependencies:** production egress, storage and traceable errors; Definition of Ready and current audit WIP gate still apply. **Size:** L. **Audit:** A11 / D-362. **Work order:** \`docs/work-orders/S-06.02.60-atomic-ai-quota.md\`.

**Acceptance sub-cases (3 written):**

1. **Given** one remaining request and two independent workers, **when** they race, **then** no more than one provider call begins.
2. **Given** a daily USD cap, **when** priced concurrent requests, retries, crashes or uncertain outcomes occur, **then** reservations and reconciled totals prevent unaccounted spend.
3. **Given** a corrupt/unavailable quota ledger or a different workspace account, **when** a request starts, **then** the system fails closed as needed and never leaks or resets another workspace's count.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.61 — Email provider setup failures do not strand delivery jobs (A16)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.61-email-provider-setup.md).

**Requirement:** Email provider setup failures do not strand delivery jobs (A16).

**Dependencies:** **Dependencies:** real durable email worker and traceable-errors contract before customer deployment; normal board readiness/WIP rules apply. **Size:** M. **Audit:** A16 / D-363. **Work order:** \`docs/work-orders/S-06.02.61-email-provider-setup.md\`.

**Acceptance sub-cases (3 written):**

1. **Given** a permanent factory error before transport, **when** a job is claimed, **then** it reaches a truthful terminal state with a traceable reason and no send.
2. **Given** temporary or unknown setup errors, **when** the worker continues, **then** it performs only bounded safe pre-send retry or an explicit failure and continues unrelated due jobs.
3. **Given** an actual ambiguous post-send outcome, **when** retries are considered, **then** existing do-not-resend quarantine is unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.62 — HTTP idempotency safely prevents duplicate state-changing requests (A14)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.62-atomic-http-idempotency.md).

**Requirement:** HTTP idempotency safely prevents duplicate state-changing requests (A14).

**Dependencies:** **Dependencies:** production authentication, CRM durable transaction and active audit review. **Size:** L. **Audit:** A14 / D-364. **Work order:** `docs/work-orders/S-06.02.62-atomic-http-idempotency.md`.

**Acceptance sub-cases (4 written):**

1. **Given** two app instances sharing SQLite or real PostgreSQL, **when** they receive the same key and request together, **then** exactly one database effect commits and both receive the original operation ID.
2. **Given** a different payload or authenticated principal, **when** an old key is reused, **then** return 409 without leaking the original result; malformed or excessive keys return 422.
3. **Given** a database-only operation that fails after mutation but before response, **when** the client retries, **then** the operation and reply roll back together and exactly one effect can complete.
4. **Given** an email or AI provider action with uncertain outcome, **when** the client retries, **then** a durable in-progress claim refuses replay until reconciled, not a second send; completed calls replay the saved result.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.63 — Token-authenticated media works in review and video export (A20)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.63-token-media-auth.md).

**Requirement:** Token-authenticated media works in review and video export (A20).

**Dependencies:** **Dependencies:** existing API authentication and asset endpoints. **Audit:** A20. **Size:** M. **Work order:** `docs/work-orders/S-06.02.63-token-media-auth.md`.

**Acceptance sub-cases (5 written):**

1. **Given** a local API token, **when** the user previews or exports image, audio or video content, **then** the same-origin binary request includes the bearer token, with no credential in a URL.
2. **Given** cookie-only login, **when** the user previews or exports media, **then** the same path uses cookies without needing a token.
3. **Given** a 401 or 403 response, **when** an asset is loaded, **then** a clear authentication or access message is shown instead of reporting a missing asset. A 404 may still report missing.
4. **Given** a token and an untrusted media URL, **when** the frontend attempts to load it, **then** the bearer token is never sent outside the application's same-origin API routes.
5. **Given** token-only mode, **when** an anonymous user checks /auth/session, **then** authenticated is false; a valid token reports authenticated and opens the dashboard.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.64 — Restricted sandbox can write outputs without exposing host files (A32)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.64-sandbox-writable-workspace.md).

**Requirement:** Restricted sandbox can write outputs without exposing host files (A32).

**Dependencies:** **Dependencies:** S-03.01.02 is DONE; active production audit S-06.02.23 remains IN_PROGRESS. Size M. Audit A32 / defect D-121. Work order: `docs/work-orders/S-06.02.64-sandbox-writable-workspace.md`.

**Acceptance sub-cases (4 written):**

1. **Given** a newly prepared workspace or one created with older modes, **when** a sandbox job runs as container UID/GID 65534, **then** it can create output under its sole writable mount `/work`.
2. **Given** another unprivileged host user, **when** the workspace exists, **then** the job root remains private to the host owner; `store` and host secrets are not mounted and `/inbox` stays read-only.
3. **Given** a symlink pretending to be the job root, inbox or work folder, **when** prepare runs, **then** it refuses without changing the linked target's permissions.
4. **Given** a real pinned Docker image, **when** the container starts, **then** writing `/work/result.txt` succeeds under the existing non-root, no-network, read-only-root flags.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.65 — Reject malformed nested video edits without partial writes (A22)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.65-video-edit-input.md).

**Requirement:** Reject malformed nested video edits without partial writes (A22).

**Dependencies:** **Dependencies:** existing video store and API, production audit S-06.02.23 still IN_PROGRESS. Scope is A22 nested video edit safety only; wider A22 write-API matrix requires separate audit. **Size:** M. Work order: `docs/work-orders/S-06.02.65-video-edit-input.md`.

**Acceptance sub-cases (4 written):**

1. **Given** an authenticated permitted user, **when** a video-edit batch has non-object params, unexpected nested keys, conflicting op names or ambiguous single/batch fields, **then** the HTTP API returns a bounded 4xx without exposing internal errors or submitted text.
2. **Given** a batch containing an invalid later edit, **when** it is submitted, **then** the current project and version remain unchanged.
3. **Given** excessive per-edit text or a batch over 500 edits, **when** submitted, **then** the API rejects it before applying edits.
4. **Given** a valid single edit and a valid two-step batch, **when** submitted, **then** saved version, redo/undo and read-back still work.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.66 — Paid AI calls cannot silently count as free when usage receipts are invalid (A10)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md).

**Requirement:** Paid AI calls cannot silently count as free when usage receipts are invalid (A10).

**Dependencies:** **Dependencies:** existing broker, provider adapter and quota implementation; audit S-06.02.23 remains IN_PROGRESS. This is A10 receipt integrity only; broader spending/provider billing verification remains outstanding. **Size:** M. Work order: `docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md`.

**Acceptance sub-cases (4 written):**

1. **Given** a priced valid provider receipt, **when** generation succeeds, **then** the single broker cost is reconciled into a durable account/workspace ledger and the next unaffordable request is refused before provider I/O.
2. **Given** a zero, missing, nonfinite or malformed token receipt after nonempty paid generation, **when** the broker accounts for it, **then** it estimates a positive cost and reports `usage_source=estimated`; it does not credit USD 0 as a confirmed invoice or raise a post-transport conversion error.
3. **Given** concurrent workers or a process restart, **when** a spend ceiling is almost reached, **then** the atomic quota reserve is honoured across requests and provider credentials. Corrupt storage refuses the call instead of resetting usage.
4. **Given** a failed or uncertain provider call, **when** the broker reconciles, **then** it never resends automatically only to repair the ledger; owner sees recorded limitations and an actionable error.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.67 — Only install owners may access personal-data inventory and erasure (A24/A05)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.67-privacy-owner-authorization.md).

**Requirement:** Only install owners may access personal-data inventory and erasure (A24/A05).

**Dependencies:** **Dependencies:** existing privacy service S-06.02.04 and owner identity; production audit S-06.02.23 remains active. **Size:** S. Work order: `docs/work-orders/S-06.02.67-privacy-owner-authorization.md`. This security boundary does not certify full A24 deletion/retention and backups.

**Acceptance sub-cases (3 written):**

1. **Given** an ordinary workspace session, **when** it requests subject access, erasure preview, confirmation or deletion execution, **then** the API returns a safe 403 before any personal-data read/write.
2. **Given** the install API token or explicitly provisioned `local` owner login, **when** it runs subject access, previews and confirms erasure, **then** synthetic subject data is removed with a truthful result and unrelated records remain.
3. **Given** a valid owner preview ID, **when** a nonowner knows both ID and deletion phrase, **then** deletion cannot occur. Spoofed workspace input and restart do not bypass the guard.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.68 — Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.68-video-workspace-ownership.md).

**Requirement:** Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05).

**Dependencies:** **Dependencies:** existing workspace login and video stores. No CRM tenancy migration (Q-27). Audit S-06.02.23 IN_PROGRESS, **Size M**. Work order `docs/work-orders/S-06.02.68-video-workspace-ownership.md`. Production penetration and customer acceptance remain open.

**Acceptance sub-cases (3 written):**

1. **Given** two workspaces share a campaign ID, **when** either lists projects, media, reviews or approved exports, **then** SQL queries return only that workspace's rows before limits apply.
2. **Given** a foreign project, media or render ID, **when** a workspace uses direct HTTP read, download, edit, delete, transcript, assembly or publish surface, **then** it receives a bounded 404 without access to bytes or a state change.
3. **Given** the owning workspace, **when** it reads and edits its own records, **then** existing video functions work unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.69 — Image briefs, generated files and video handoff remain private to their workspace (A05)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.69-image-workspace-ownership.md).

**Requirement:** Image briefs, generated files and video handoff remain private to their workspace (A05).

**Dependencies:** existing workspace sessions, image/video stores; wider CRM tenancy Q-27 is not changed. Feature F-06.02, **Size M**. Work order `docs/work-orders/S-06.02.69-image-workspace-ownership.md`, BACKLOG during audit S-06.02.23 IN_PROGRESS.

**Acceptance sub-cases (3 written):**

1. **Given** two workspaces use the same CRM campaign, **when** they view image briefs/assets/queue/summary, **then** SQL returns only the caller's rows before limits apply.
2. **Given** another workspace's image or brief ID, **when** a user downloads, generates, approves, rejects, refreshes or places it in a video, **then** the app refuses with 404 before any media or usage change.
3. **Given** own assets and briefs, **when** used normally, **then** the image and video operations work unchanged.

**Named tasks/subtasks:** No separately numbered tasks or sub-stories are declared for this story. Follow its three acceptance cases and linked work order.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, disposable runner/local app, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

## Related external work required for F-06.02 (not separate selected features)

| External item | Functional dependency | Needed evidence |
|---|---|---|
| S-06.01.06 CRM tenancy | A05 workspace ownership for campaigns/contacts/drafts | Controlled legacy ownership migration, API/DB/worker/private media denial and privacy tests |
| F-06.03, especially S-06.03.03 / .04 / .06 / .07 | Durable PostgreSQL, offsite encrypted backup/restore, media/outbox home, install/database policy | Independent DB; restart, empty-database restore with a protected external S3-style bucket, retention and rollback |
| S-03.01.03, S-05.01.04 | A07/A08 browser and crawler network isolation | Real network, DNS rebinding, IPv4/IPv6 private destinations, redirect, resource limits in sandbox |
| S-04.01.04 | Real agent-team/workspace interactions needed for A05/A28 | Authenticated owner browser, safe approval, real provider receipts and separate workspace denial |
| S-07.01.* | A27 social publishing and readback, without pretending mock adapters are live | Official authorized publishing/metrics, duplicate guards and reconciliation |
| Release/operator environment | A24/A25/A29 provider/worker/privacy and penetration checks | Genuine authorized non-customer test account/provider, supervised worker, actual hosted state, independent security assessment |

## Actual D-507 evidence and blocker

- Added `tests/test_render_smoke_redirects.py` first: commit `8ae954b`. Two GET/POST local loopback checks reproduced the unintended redirect-following behaviour under the original Python urllib client and passed after the fix. These are **local behaviour checks**, not a complete new-container test.
- Corrected `scripts/live/remote_render_smoke.py` at `226e9a6`: refuse all 30x following, preventing a QA probe from accepting responses from a different origin.
- Real existing-host public HTTPS smoke [45013807759](https://github.com/kunalwagh101/off_CRM/actions/runs/45013807759) PASS, eight checks, but the remote app is running its earlier image.
- Full five-job GitHub [45013807674](https://github.com/kunalwagh101/off_CRM/actions/runs/45013807674) started but no final result available at this checkpoint.
- New Render QA image `dep-dc1celtg1s2s73cvt52g` on workspace `majors_97` **build_failed before code execution**: build pipeline minutes exhausted. No current-source Render manual acceptance. F-06.02 and S-06.02.23 remain **NOT DONE**.
