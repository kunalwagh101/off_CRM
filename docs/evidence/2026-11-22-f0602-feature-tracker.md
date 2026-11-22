# F-06.02 — complete direct-story acceptance tracker

**Snapshot:** 2026-11-22, off_CRM `develop`. **Authoritative:** [board](../../BOARD.md), [backlog](../../PRODUCT_BACKLOG.md), [Done rules](../../DEFINITION_OF_DONE.md), [audit work order](../work-orders/S-06.02.23-audit-recheck.md). Do not treat this inventory as certification.

## Scope hierarchy

**One feature** F-06.02 with **69 directly contained stories**: 20 historical DONE, 37 IN_REVIEW, 10 BACKLOG, 1 IN_PROGRESS, 1 BLOCKED, 0 READY. **49 not DONE.** The roadmap does not number complete independent sub-feature/sub-story/task/sub-task trees for every story. The logical sub-feature clusters are: (i) identity, permissions, privacy, secrets; (ii) data safety, idempotency, hosting, scheduler/worker; (iii) AI/model cost, factuality and egress; (iv) media/browser safeguards; (v) operator UI, accessibility and live quality checks. These are labels, **not invented roadmap IDs**.

Each Given/When/Then below is a required *acceptance sub-case*. For each case: implement through the real API/UI/store/worker; run the failing test first where relevant, then unit/integration/API, adverse/security, regression and end-to-end; deploy the exact commit to isolated Render; manually test the API/UI/DB and error path, inspect responses/logs, verify reload/restart/rollback and evidence; run `uv run pytest -q`, frontend tests/build, real PostgreSQL, `uv run python scripts/verify_board.py`, independent penetration and owner acceptance where applicable. **Passing a mock does not prove real provider operation.**

## Directly contained stories and all written acceptance cases

### S-06.02.01 — No secret may enter a model prompt

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** No secret may enter a model prompt.

**Dependencies:** **Dependencies:** S-03.02.02. **Size:** M. **Indicator:** scanner findings.

**Acceptance sub-cases (1 written):**

1. **Given** the payload builder, **when** any request is assembled, **then** a

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.02 — Every endpoint authorises and validates

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Every endpoint authorises and validates.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated reachability.

**Acceptance sub-cases (2 written):**

1. **Given** any API endpoint outside the documented closed public bootstrap /
2. **Given** any body, **when** it is malformed, **then** the response is a 4xx

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.03 — Cost and latency budgets per run

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Cost and latency budgets per run.

**Dependencies:** **Dependencies:** S-06.01.03, S-11.01.04. **Size:** S. **Indicator:** new work

**Acceptance sub-cases (4 written):**

1. **Given** a positive spend ceiling, **when** the next model decision would
2. **Given** a positive latency ceiling, **when** a completed provider or browser
3. **Given** a run that is resumed, **when** no new latency ceiling is supplied,
4. **Given** a zero ceiling, **when** the run executes, **then** that dimension is

**Named tasks/subtasks:** **Tasks:** T-06.02.03.a integrate latency with the existing trace/run/resume

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.04 — Data deletion and subject access

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Data deletion and subject access.

**Dependencies:** **Dependencies:** S-05.01.01. **Size:** M. **Indicator:** deletion requests unfulfilled.

**Acceptance sub-cases (3 written):**

1. **Given** an identified person, **when** a subject-access request is executed,
2. **Given** a confirmed deletion request, **when** it succeeds, **then** the
3. **Given** any registered store fails deletion, **when** the operation runs,

**Named tasks/subtasks:** **Tasks:** T-06.02.04.a define one store inventory/subject-match contract and

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.05 — The UI is usable by keyboard and screen reader

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The UI is usable by keyboard and screen reader.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** accessibility audit findings.

**Acceptance sub-cases (1 written):**

1. **Given** any interactive screen, **when** navigated by keyboard alone, **then**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.06 — The delivery process is verifiable by the owner

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The delivery process is verifiable by the owner.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unverifiable DONE claims.

**Acceptance sub-cases (2 written):**

1. **Given** a DONE item whose named test does not exist, **when** the verifier
2. **Given** an orphan requirement, **when** the verifier runs, **then** it exits

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.07 — An answered question stops blocking

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** An answered question stops blocking.

**Dependencies:** **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** decisions recorded vs questions deleted.

**Acceptance sub-cases (2 written):**

1. **Given** a question marked answered, **when** an item citing it enters READY,
2. **Given** a question with no answer, **when** an item citing it enters READY,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.08 — One runner for every evidence command

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** One runner for every evidence command.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** verifier failures caused

**Acceptance sub-cases (2 written):**

1. **Given** the board, **when** every DONE evidence command is read, **then**
2. **Given** a clean checkout, **when** the documented setup is run and the

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.09 — Every database write goes through one guard

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** Every database write goes through one guard.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unguarded `.execute(` call

**Acceptance sub-cases (3 written):**

1. **Given** concurrent transactions on `OutreachStore`, **when** they run,
2. **Given** a bare `store.connection.execute(...)` outside a transaction,
3. **Given** a long-lived connection assigned anywhere in `outreach/`, **when**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.10 — The local API is not open to whatever can reach the port

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The local API is not open to whatever can reach the port.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated 200s on

**Acceptance sub-cases (3 written):**

1. **Given** no token and no demo login, **when** the app is constructed, **then**
2. **Given** a local install that has never been configured, **when** it starts
3. **Given** a request whose `Host` is not one this server answers to, **when** it

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.11 — The verifier catches a stale READY column

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The verifier catches a stale READY column.

**Dependencies:** **Dependencies:** S-06.02.06. **Size:** S. **Indicator:** stories found stale

**Acceptance sub-cases (3 written):**

1. **Given** a story in `BACKLOG` whose declared dependencies are all `DONE` and
2. **Given** a story in `READY` whose dependencies are not all `DONE`, **when**
3. **Given** a story whose dependency line names an id that does not exist,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.12 — A recorded commit must be on the branch

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A recorded commit must be on the branch.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** board shas not on the

**Acceptance sub-cases (3 written):**

1. **Given** a DONE entry whose `commit:` is reachable from `HEAD`, **when** the
2. **Given** a DONE entry whose `commit:` names an object that exists but is not
3. **Given** a DONE entry whose `commit:` names no object at all, **when** the

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.13 — A defect log and a decision log the next session can read

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A defect log and a decision log the next session can read.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** defects found twice —

**Acceptance sub-cases (4 written):**

1. **Given** `DEFECT_LOG.md`, **when** it is read, **then** every defect found
2. **Given** a defect recorded as `open`, **when** the verifier runs, **then** it
3. **Given** two rows sharing an id, **when** the verifier runs, **then** it
4. **Given** `DECISIONS.md`, **when** it is read, **then** every entry says what

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.14 — A test should not hardcode a trace step id

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A test should not hardcode a trace step id.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** tests broken by an

**Acceptance sub-cases (2 written):**

1. **Given** a test that needs a particular step's id, **when** it runs, **then**
2. **Given** a new step added anywhere in a run, **when** the suite runs, **then**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.15 — CI gives the verifier the repository it claims to verify

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** CI gives the verifier the repository it claims to verify.

**Dependencies:** **Dependencies:** S-06.02.08, S-06.02.12. **Size:** S. **Indicator:** verifier

**Acceptance sub-cases (3 written):**

1. **Given** a DONE evidence commit older than `HEAD`, **when** CI runs the
2. **Given** DONE frontend evidence, **when** CI runs the verifier, **then**
3. **Given** the CI workflow itself, **when** its regression test runs, **then**

**Named tasks/subtasks:** **Tasks:** T-06.02.15.a repair checkout/dependency ordering (<=1 day);

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.16 — Resolve frontend development dependency audit findings

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.16-frontend-dependency-audit.md).

**Requirement:** Resolve frontend development dependency audit findings.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** high-severity npm audit

**Acceptance sub-cases (3 written):**

1. **Given** a clean `npm ci`, **when** `npm audit --omit=dev` runs, **then** the
2. **Given** the full development dependency tree, **when** `npm audit` runs,
3. **Given** a remediation that requires a breaking upgrade, **when** it is

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.17 — DONE may not depend on unfinished work

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** DONE may not depend on unfinished work.

**Dependencies:** **Dependencies:** S-06.02.11. **Size:** S. **Indicator:** DONE stories whose

**Acceptance sub-cases (2 written):**

1. **Given** a DONE story that depends on a READY, BACKLOG or BLOCKED story,
2. **Given** a DONE story whose declared dependencies are all DONE, **when** the

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.18 — Restore executable CI runner capacity

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.18-ci-runner-capacity.md).

**Requirement:** Restore executable CI runner capacity.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** CI jobs with zero workflow

**Acceptance sub-cases (3 written):**

1. **Given** the current private repository and `.github/workflows/ci.yml`,
2. **Given** the hosted job cannot acquire a runner because of an account,
3. **Given** GitHub-hosted execution is unavailable but an approved self-hosted

**Named tasks/subtasks:** **Tasks:** verify owner Billing & licensing → Actions usage/budgets/payment

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.19 — One working branch holds everything built, and it is green

**Status:** BLOCKED. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** One working branch holds everything built, and it is green.

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** branches carrying unmerged

**Acceptance sub-cases (3 written):**

1. **Given** the thirty-odd branches of 2026-09-23, **when** they are consolidated,
2. **Given** two lines that used the same story, requirement, defect or decision
3. **Given** the consolidated branch, **when** the full Python suite, ruff gate,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.20 — The verifier tells a shallow clone apart from a missing commit

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.20-shallow-git-history.md).

**Requirement:** The verifier tells a shallow clone apart from a missing commit.

**Dependencies:** **Dependencies:** S-06.02.12. **Size:** S. **Indicator:** verifier failures **Dependencies:** none. **Size:** M. **Indicator:** products with every **Dependencies:** S-12.01.01. **Size:** M. **Indicator:** campaigns linked to **Dependencies:** S-12.01.02. **Size:** M. **Indicator:** model calls carrying **Dependencies:** S-12.01.01. **Size:** L. **Indicator:** plans drafted per **Dependencies:** S-12.02.01. **Size:** M. **Indicator:** plans applied. **Dependencies:** S-12.02.02. **Size:** L. **Indicator:** reviews whose first **Dependencies:** S-12.02.03. **Size:** M. **Indicator:** plan versions whose **Dependencies:** S-12.02.04. **Size:** L. **Indicator:** plan-suite score **Dependencies:** S-12.02.02. **Size:** M. **Indicator:** plans with a views

**Acceptance sub-cases (50 written):**

1. **Given** a shallow clone that lacks a recorded commit, **when** the verifier
2. **Given** the CI workflow, **when** it checks out the repository, **then** it
3. **Given** the required fields, **when** a product is created, **then** it is
4. **Given** a missing or out-of-bounds required field, a website that is not
5. **Given** an email address anywhere in the product, **when** it is saved,
6. **Given** an existing product, **when** it is edited, **then** its version
7. **Given** a forbidden claim, **when** text is checked, **then** the phrase is
8. **Given** a product in one workspace, **when** another workspace reads, edits
9. **Given** the Product screen, **when** it renders, **then** the required
10. **Given** a product and campaigns, **when** the owner sets the product's
11. **Given** an email template using `{product_offer}` and a campaign linked to a
12. **Given** a campaign with no product, **when** a draft is created from a
13. **Given** a rendered draft containing one of the linked product's forbidden
14. **Given** a distribution campaign linked to a product and no angle, **when**
15. **Given** an explicit angle, **when** the pipeline runs, **then** the explicit
16. **Given** a video campaign linked to a product, **when** the director runs,
17. **Given** any director call, **when** the egress log is read, **then** it
18. **Given** a model reply naming a channel kind or an audience source outside
19. **Given** a reply proposing more email volume than the connected identities
20. **Given** a reply whose angle contains one of the product's forbidden claims,
21. **Given** any plan with an email channel, **when** it is parsed or built,
22. **Given** the system prompt the brain sends, **when** it is built, **then** it
23. **Given** the request the brain sends, **when** it is built, **then** its data
24. **Given** no permitted model, **when** a plan is drafted, **then** a
25. **Given** a `replies` goal, **when** a plan is drafted, **then** its
26. **Given** an unknown goal kind, a target or horizon out of bounds, or an
27. **Given** the Strategy screen, **when** it renders, **then** the goal form and
28. **Given** a draft plan, **when** it is applied, **then** one campaign per
29. **Given** an email channel, **when** it is applied, **then** its campaign
30. **Given** a `views` goal with a distribution channel, **when** it is applied,
31. **Given** a plan that is not a draft, **when** apply is called, **then** it is
32. **Given** an apply, **when** it returns, **then** it lists next steps, each
33. **Given** an email channel whose delivery health is breached, **when** it is
34. **Given** each earlier condition in the order — paused, no contacts, drafts
35. **Given** fewer than 20 contacted, **when** it is reviewed, **then** the
36. **Given** enough contacted, **when** the 90% interval sits wholly below,
37. **Given** a distribution channel, **when** it is reviewed, **then** the
38. **Given** a model reply proposing a remedy the finding does not permit, a
39. **Given** no permitted model, **when** it is reviewed, **then** each finding
40. **Given** a review, **when** it is stored, **then** the measurements it read
41. **Given** an applied plan with a review and at least 20 contacted, **when** it
42. **Given** fewer than 20 contacted, **when** it is revised, **then** the
43. **Given** a revision that is applied, **when** it runs, **then** the same
44. **Given** a plan with no review, **when** revise is called, **then** it is
45. **Given** an imported expert library and a judged winning template, **when** a
46. **Given** fewer than 30 cases in `gtm_plan`, **when** the comparison runs,
47. **Given** an applied plan with posting and picture channels, **when** the
48. **Given** a drafted post, **when** the owner opens Posting, **then** they can
49. **Given** a paused campaign in a declared pair, **when** content automation
50. **Given** a plan's posts a day, **when** its posting runs, **then** that is

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.21 — Durable customer state and safe recovery (audit WP1)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md).

**Requirement:** Durable customer state and safe recovery (audit WP1).

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** restores that lose a

**Acceptance sub-cases (4 written):**

1. **Given** production configuration, **when** the durable root is ephemeral,
2. **Given** a backup, **when** it is made, **then** every durable file under the
3. **Given** a restore, **when** it succeeds or is rejected, **then** writers are
4. **Given** readiness, **when** a required store or durable path cannot be

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.22 — A created or selected campaign stays the active workspace

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.21-S-06.02.22-close-out.md).

**Requirement:** A created or selected campaign stays the active workspace.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** imports into a campaign the

**Acceptance sub-cases (2 written):**

1. **Given** a new campaign, **when** it is created, **then** it becomes the
2. **Given** a selected campaign outside the bounded list, **when** the list

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.23 — Re-check the 7 September production audit on `develop`

**Status:** IN_PROGRESS. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.23-audit-recheck.md).

**Requirement:** Re-check the 7 September production audit on `develop`.

**Dependencies:** **Dependencies:** none. **Size:** L. **Indicator:** audit findings with

**Acceptance sub-cases (1 written):**

1. **Given** a finding the consolidation did not re-check, **when** its

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.24 — Every process that writes the workspace holds its lease

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.24-workspace-lease-for-clis.md).

**Requirement:** Every process that writes the workspace holds its lease.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** processes that write the

**Acceptance sub-cases (3 written):**

1. **Given** a restore in progress, **when** the outreach, notebook or eval CLI
2. **Given** a CLI command running, **when** a restore starts, **then** the
3. **Given** a restore nobody has rolled back yet, **when** a CLI starts,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.25 — Every screen opens at its top, its warnings in view

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.25-screen-opens-at-top.md).

**Requirement:** Every screen opens at its top, its warnings in view.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** screens whose top is

**Acceptance sub-cases (3 written):**

1. **Given** any screen opened from the navigation, **when** it has rendered,
2. **Given** the campaign list failing, **when** a screen opens, **then** the
3. **Given** keyboard or screen-reader use, **when** the screen changes,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.26 — CI runs the suite on every Python the package supports

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.26-python-matrix.md).

**Requirement:** CI runs the suite on every Python the package supports.

**Dependencies:** **Dependencies:** `S-06.02.18` (CI runners). **Size:** S. **Indicator:**

**Acceptance sub-cases (2 written):**

1. **Given** a push, **when** CI runs, **then** the whole suite runs on 3.10,
2. **Given** a version added to `pyproject.toml`, or the image's version

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.27 — The audit's live harness runs against `develop`

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The audit's live harness runs against `develop`.

**Dependencies:** **Dependencies:** `S-06.02.18`. **Size:** M. **Indicator:** harness checks

**Acceptance sub-cases (1 written):**

1. **Given** the audit's live harness (`verification/` on the archived

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.28 — A command-line tool locks the workspace it actually opens

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.28-path-aware-workspace-lock.md).

**Requirement:** A command-line tool locks the workspace it actually opens.

**Dependencies:** **Dependencies:** `S-06.02.24`. **Size:** M. **Indicator:** writes made

**Acceptance sub-cases (3 written):**

1. **Given** an explicit `--db`, `--context` or `--token`, or an absolute
2. **Given** `OFFSETX_DATA_DIR` set only in `.env`, **when** any of the six tools
3. **Given** `offsetx-artifacts --run-dir .` from inside a run the app recorded,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.29 — The NVIDIA reasoning model answers in chat

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** The NVIDIA reasoning model answers in chat.

**Dependencies:** **Dependencies:** none. **Size:** XS. **Indicator:** provider 400s caused by

**Acceptance sub-cases (1 written):**

1. **Given** `nvidia/nemotron-3-ultra-550b-a55b` connected with a key, **when**

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.30 — A provider connects from the Connectors screen as shown

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md).

**Requirement:** A provider connects from the Connectors screen as shown.

**Dependencies:** **Dependencies:** none. **Size:** XS. **Indicator:** connect attempts refused

**Acceptance sub-cases (2 written):**

1. **Given** the Connectors form's defaults — call cap 0, spend cap 0 — **when**
2. **Given** a value the server refuses, **when** the screen shows the error,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.31 — Provider keys come only from the app

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.31-keys-only-from-the-app.md).

**Requirement:** Provider keys come only from the app.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** workspaces able to use a

**Acceptance sub-cases (3 written):**

1. **Given** `OFFSETX_AI_<PROVIDER>_KEY` set on the server, **when** any workspace
2. **Given** any web request — a draft, a provider profile — **when** it names
3. **Given** no stored key, **when** the owner connects a provider that needs one,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.32 — The connect form offers limit presets

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.32-limit-presets.md).

**Requirement:** The connect form offers limit presets.

**Dependencies:** **Dependencies:** `S-06.02.30`. **Size:** S. **Indicator:** caps set by typing

**Acceptance sub-cases (2 written):**

1. **Given** the Connect form, **when** the owner sets the call cap, **then** the
2. **Given** a saved cap, **when** the form opens again, **then** it shows that

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.33 — Trust is the owner's to change, per provider and per model

**Status:** DONE. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.33-trust-per-provider-and-model.md).

**Requirement:** Trust is the owner's to change, per provider and per model.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** trust changes made without

**Acceptance sub-cases (6 written):**

1. **Given** any provider, **when** the owner lowers its trust, **then** it
2. **Given** any model under a provider, **when** the owner sets its own trust,
3. **Given** a raise above a default, **when** the owner saves it, **then** a
4. **Given** a provider raised above its default, **when** one of its models is
5. **Given** any trust setting, **when** the owner has not typed the separate
6. **Given** a changed trust, **when** the owner saves the connection again,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** Historically DONE on board; not independently reverified here.

### S-06.02.34 — Connectors show how much is left

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.34-usage-remaining.md).

**Requirement:** Connectors show how much is left.

**Dependencies:** **Dependencies:** `S-06.02.32`. **Size:** M. **Indicator:** providers whose

**Acceptance sub-cases (3 written):**

1. **Given** every connected provider, **when** Connectors opens, **then** it
2. **Given** a provider that reports what is left — a key or balance endpoint,
3. **Given** a provider that reports nothing (NVIDIA, checked 2026-09-25),

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.35 — Drafts reach a model the owner set up on a screen

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.35-drafts-connectors.md).

**Requirement:** Drafts reach a model the owner set up on a screen.

**Dependencies:** **Dependencies:** `Q-28`. **Size:** M. **Indicator:** empty states pointing

**Acceptance sub-cases (3 written):**

1. **Given** the owner's answer to `Q-28`, **when** a model is connected the way
2. **Given** no model set up for the workspace, **when** Drafts opens, **then**
3. **Given** profiles saved before `DD-68`, **then** the owner can see and

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.36 — A second owner login is made on purpose

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.36-explicit-owner-login.md).

**Requirement:** A second owner login is made on purpose.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** owner logins created

**Acceptance sub-cases (2 written):**

1. **Given** the workspace form or API, **when** the id `local` is chosen,
2. **Given** existing logins in `local`, **then** they keep working.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.37 — Skip navigation keeps the current screen

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.37-skip-keeps-current-page.md).

**Requirement:** Skip navigation keeps the current screen.

**Dependencies:** **Dependencies:** none. **Size:** S. **Indicator:** skip activations changing

**Acceptance sub-cases (2 written):**

1. **Given** Settings or another screen, **when** Skip to main content is
2. **Given** a pointer activation of the same link, **when** it is used,

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.38 — Any error can be traced back the next day

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.38-traceable-errors.md).

**Requirement:** Any error can be traced back the next day.

**Dependencies:** **Dependencies:** none. **Size:** M. **Indicator:** failures with no log

**Acceptance sub-cases (5 written):**

1. **Given** any request that fails with a 5xx, **then** the response carries a
2. **Given** a failed worker cycle, command or background job, **then** the same:
3. **Given** a local install, **then** the lines also go to a size-capped
4. **Given** a failure whose message holds a password, key, token, cookie or a
5. **Given** a successful request, **then** nothing is logged beyond a one-line

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.39 — Valid low-bitrate WebM exports pass verification

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.39-low-bitrate-export.md).

**Requirement:** Valid low-bitrate WebM exports pass verification.

**Dependencies:** **Dependencies:** S-01.02.01 (DONE). **Size:** S. **Audit:** A34, D-122. **Scope:** small WebM only; do not weaken other codecs or remove the existing threshold for unproved data.

**Acceptance sub-cases (3 written):**

1. **Given** a genuine encoded WebM with a video track, encoded video samples, correct dimensions and duration, **when** its byte length is under 4096, **then** the export passes the non-empty gate and all the other applicable existing gates.
2. **Given** a short metadata-only, zero-sample or malformed WebM, **when** it is checked, **then** it remains rejected as incomplete; a larger valid export retains its old behaviour.
3. **Given** a declared duration, dimensions or audio requirement, **when** the media disagrees, **then** those gates still refuse the export regardless of file size.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.40 — A durable email worker runs beside the deployed web app

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.40-durable-deployment-worker.md).

**Requirement:** A durable email worker runs beside the deployed web app.

**Dependencies:** **Dependencies:** S-06.03.06 (durable homes for remaining state), S-06.02.38 (traceable worker failures). **Size:** M. **Audit:** A25 / D-270. **Indicator:** due jobs processed without a manual web session.

**Acceptance sub-cases (3 written):**

1. **Given** a deployed workspace with durable CRM and queue state, **when** an approved due email is queued, **then** the independently deployed worker opens the same hosted database and processes it within an operating bound; no duplicate send after restart or lease contention.
2. **Given** the worker crashes or loses the database/provider, **when** it restarts, **then** uncertain sends remain quarantined for reconciliation, a safe error reference is logged, and no operation is silently retried.
3. **Given** the production service configuration, **when** it is reviewed or deployed, **then** a supervised worker process, health/restart policy, ownership, secrets delivery and rollback steps are present and proven on the actual hosting tier; two web services alone do not meet this acceptance.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.41 — Contacts beyond row 500 are reachable

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.41-contacts-pagination.md).

**Requirement:** Contacts beyond row 500 are reachable.

**Dependencies:** **Dependencies:** none. **Size:** S. **Audit:** A23 / D-271. **Work order:** `docs/work-orders/S-06.02.41-contacts-pagination.md`.

**Acceptance sub-cases (2 written):**

1. **Given** more than 500 contacts, **when** the owner moves between pages, **then** each row is reachable through the existing authenticated offset API and the total/range remain correct.
2. **Given** search/status change, campaign change or records removed, **when** the list reloads, **then** the page index returns to a valid slice without mixing another campaign's data.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.42 — Enrichment exports cannot run spreadsheet formulas

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.42-spreadsheet-formulas.md).

**Requirement:** Enrichment exports cannot run spreadsheet formulas.

**Dependencies:** **Dependencies:** none. **Size:** S. **Audit:** A19 / D-272. **Work order:** `docs/work-orders/S-06.02.42-spreadsheet-formulas.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a leading formula/control sequence in a report cell, **when** CSV/XLSX is generated, **then** it is literal text in the actual saved document; numeric cells retain their numeric type.
2. **Given** the same text in persisted CRM or credit/exclusion/rejection ledger rows, **when** reports are generated, **then** original state and dedupe keys remain unchanged; readable snapshots are safely escaped.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.43 — Logout revokes the copied browser session

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.43-logout-revocation.md).

**Requirement:** Logout revokes the copied browser session.

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A06 / D-273. **Work order:** `docs/work-orders/S-06.02.43-logout-revocation.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a signed session, **when** logout succeeds, **then** replay of that exact token is denied across process restarts and PostgreSQL/SQLite backends; other valid devices remain signed in.
2. **Given** a storage outage during revocation, **when** logout is attempted, **then** the app does not claim the token was revoked.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.44 — Download all filtered Contacts rows

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.44-filtered-contact-download.md).

**Requirement:** Download all filtered Contacts rows.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** M. **Work order:** `docs/work-orders/S-06.02.44-filtered-contact-download.md`.

**Acceptance sub-cases (2 written):**

1. **Given** filters and 500+ contacts, **when** I download, **then** the attachment contains every matching contact, with stable named columns and spreadsheet-safe text; no private mail bodies or internal notes.
2. **Given** an oversized or changing result, **when** I export, **then** no believable incomplete file is returned. The prior full-campaign report remains unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.45 — Category and variant filters for contacts

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.45-contact-facet-filters.md).

**Requirement:** Category and variant filters for contacts.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.45-contact-facet-filters.md`.

**Acceptance sub-cases (2 written):**

1. **Given** the active campaign, **when** its filters load, **then** only campaign categories and variants appear; combining them with text/status searches uses the existing server query.
2. **Given** a filter change, **when** the list refreshes, **then** it restarts at page one with the right count.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.46 — Marked-only contacts remain reachable

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.46-marked-only-contacts.md).

**Requirement:** Marked-only contacts remain reachable.

**Dependencies:** **Dependencies:** S-06.02.41 (IN_REVIEW). **Size:** S. **Work order:** `docs/work-orders/S-06.02.46-marked-only-contacts.md`.

**Acceptance sub-cases (2 written):**

1. **Given** marked contacts, **when** I filter and export, **then** the SQL query counts/returns only them; no client-side 100-row approximation or implicit send occurs.
2. **Given** an uncheck or campaign switch, **when** records reload, **then** persistent selection remains associated with the correct campaign and empty/stale pages recover.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.47 — Large send queues are paginated

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.47-queue-pagination.md).

**Requirement:** Large send queues are paginated.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.47-queue-pagination.md`.

**Acceptance sub-cases (2 written):**

1. **Given** 211 contacts, **when** the Queue opens, **then** its default result has at most 100 items and the total and next-page controls make every contact reachable.
2. **Given** an invalid page limit or offset, **when** queried, **then** the API rejects it; the actual sender is unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.48 — Campaign-wide queue counters do not mislead

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.48-global-queue-totals.md).

**Requirement:** Campaign-wide queue counters do not mislead.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.48-global-queue-totals.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a filtered or later page, **when** loaded, **then** counts cover every campaign membership using the sender's due-time logic.
2. **Given** a future-scheduled approved draft or terminal contact, **when** counting, **then** it does not appear as ready; totals do not override final live-send preflight.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.49 — Queue views focus on actionable cohorts

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.49-actionable-queue-views.md).

**Requirement:** Queue views focus on actionable cohorts.

**Dependencies:** **Dependencies:** none. **Size:** S. **Work order:** `docs/work-orders/S-06.02.49-actionable-queue-views.md`.

**Acceptance sub-cases (2 written):**

1. **Given** a view change, **when** applied, **then** filtering happens before paging and starts at page one with a view-specific total.
2. **Given** an empty view, **when** opened, **then** the screen explains that this view has no members; switching views never approves or sends mail.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.50 — Video media and renders obey configured upload limits (A15 partial remediation)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.50-bounded-video-uploads.md).

**Requirement:** Video media and renders obey configured upload limits (A15 partial remediation).

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (3 written):**

1. **Given** a bounded upload budget, **when** the file exceeds it, **then** the API returns 413 without creating media/render records; both endpoints use `read(limit+1)`.
2. **Given** an empty or unauthenticated upload, **when** sent, **then** it is rejected before decoding/storage.
3. **Given** a valid WebM below the budget, **when** sent, **then** it is accepted and recorded.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

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
5. **Given** a restart, **when** the sample-only folder is reopened, **then** no duplicate sample records appear, no scheduler starts, and stale advertised credentials cause startup refusal.

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
6. **Given** protected sample CRM records, **when** a visitor attempts owner, mailbox, send or CRM mutation operations, **then** those operations remain refused.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** **Dependencies:** S-06.02.53 (corrective follow-up requested by owner; upstream release verification remains open). **Size:** S. **Tests:** tests/test_public_demo_ai.py, tests/test_public_demo.py, frontend login/connectors and real Chromium acceptance. **Status:** IN_REVIEW; real provider key and original-site backup access remain external blockers. This does not claim arbitrary CRM/browser automation from chat. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.55 — Verify numeric claims without changing sign, precision or magnitude (A18)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.55-numeric-claim-integrity.md).

**Requirement:** Verify numeric claims without changing sign, precision or magnitude (A18).

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (0 written):**

Consult the linked work order for full acceptance. No Given/When/Then bullet appears in this backlog section.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.56 — Reject corrupt image payloads safely (A21)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.56-complete-image-decoding.md).

**Requirement:** Reject corrupt image payloads safely (A21).

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (0 written):**

Consult the linked work order for full acceptance. No Given/When/Then bullet appears in this backlog section.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.57 — A09: Enter handlers cannot bypass human approval

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.57-enter-approval.md).

**Requirement:** A09: Enter handlers cannot bypass human approval.

**Dependencies:** Check board, source architecture and related-work table; no direct dependency text extracted here.

**Acceptance sub-cases (0 written):**

Consult the linked work order for full acceptance. No Given/When/Then bullet appears in this backlog section.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.58 — Factual AI cache only reuses exact evidence (A12)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.58-exact-factual-cache.md).

**Requirement:** Factual AI cache only reuses exact evidence (A12).

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A12 / D-360. **Work order:** `docs/work-orders/S-06.02.58-exact-factual-cache.md`.

**Acceptance sub-cases (3 written):**

1. **Given** a long factual document cached with 42 million or an approval statement, **when** the number or negation changes, **then** the broker must miss the old entry before any answer is returned.
2. **Given** the exact same canonical payload and same generation contract, **when** requested again, **then** the exact cached answer is returned without an additional provider call.
3. **Given** a private workspace or denied policy, **when** another workspace/policy or mailbox source requests the entry, **then** no cached data crosses that boundary or bypasses the scanner.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.59 — Cached AI outputs are scoped to the actual model and instructions (A13)

**Status:** IN_REVIEW. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.59-cache-model-provenance.md).

**Requirement:** Cached AI outputs are scoped to the actual model and instructions (A13).

**Dependencies:** **Dependencies:** none. **Size:** M. **Audit:** A13 / D-361. **Work order:** `docs/work-orders/S-06.02.59-cache-model-provenance.md`.

**Acceptance sub-cases (3 written):**

1. **Given** identical content but a changed selected model on the same provider key, **when** the broker runs, **then** the new model is called instead of reusing another model's output.
2. **Given** changed system instructions or generation options, **when** the same model is selected, **then** the cache misses even when payload and provider stay the same.
3. **Given** an identical canonical payload and generation contract, **when** the result is cached, **then** the log identifies a cache hit, not a billable send, and the actual model is reported without any raw prompt in the index.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.60 — AI request and spending caps reserve atomically across workers (A11)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.60-atomic-ai-quota.md).

**Requirement:** AI request and spending caps reserve atomically across workers (A11).

**Dependencies:** **Dependencies:** production egress, storage and traceable errors; Definition of Ready and current audit WIP gate still apply. **Size:** L. **Audit:** A11 / D-362. **Work order:** \`docs/work-orders/S-06.02.60-atomic-ai-quota.md\`.

**Acceptance sub-cases (3 written):**

1. **Given** one remaining request and two independent workers, **when** they race, **then** no more than one provider call begins.
2. **Given** a daily USD cap, **when** priced concurrent requests, retries, crashes or uncertain outcomes occur, **then** reservations and reconciled totals prevent unaccounted spend.
3. **Given** a corrupt/unavailable quota ledger or a different workspace account, **when** a request starts, **then** the system fails closed as needed and never leaks or resets another workspace's count.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.61 — Email provider setup failures do not strand delivery jobs (A16)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.61-email-provider-setup.md).

**Requirement:** Email provider setup failures do not strand delivery jobs (A16).

**Dependencies:** **Dependencies:** real durable email worker and traceable-errors contract before customer deployment; normal board readiness/WIP rules apply. **Size:** M. **Audit:** A16 / D-363. **Work order:** \`docs/work-orders/S-06.02.61-email-provider-setup.md\`.

**Acceptance sub-cases (3 written):**

1. **Given** a permanent factory error before transport, **when** a job is claimed, **then** it reaches a truthful terminal state with a traceable reason and no send.
2. **Given** temporary or unknown setup errors, **when** the worker continues, **then** it performs only bounded safe pre-send retry or an explicit failure and continues unrelated due jobs.
3. **Given** an actual ambiguous post-send outcome, **when** retries are considered, **then** existing do-not-resend quarantine is unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.62 — HTTP idempotency safely prevents duplicate state-changing requests (A14)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.62-atomic-http-idempotency.md).

**Requirement:** HTTP idempotency safely prevents duplicate state-changing requests (A14).

**Dependencies:** **Dependencies:** production authentication, CRM durable transaction and active audit review. **Size:** L. **Audit:** A14 / D-364. **Work order:** `docs/work-orders/S-06.02.62-atomic-http-idempotency.md`.

**Acceptance sub-cases (4 written):**

1. **Given** two app instances sharing SQLite or real PostgreSQL, **when** they receive the same key and request together, **then** exactly one database effect commits and both receive the original operation ID.
2. **Given** a different payload or authenticated principal, **when** an old key is reused, **then** return 409 without leaking the original result; malformed or excessive keys return 422.
3. **Given** a database-only operation that fails after mutation but before response, **when** the client retries, **then** the operation and reply roll back together and exactly one effect can complete.
4. **Given** an email or AI provider action with uncertain outcome, **when** the client retries, **then** a durable in-progress claim refuses replay until reconciled, not a second send; completed calls replay the saved result.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

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

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

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

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

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

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.66 — Paid AI calls cannot silently count as free when usage receipts are invalid (A10)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md).

**Requirement:** Paid AI calls cannot silently count as free when usage receipts are invalid (A10).

**Dependencies:** **Dependencies:** existing broker, provider adapter and quota implementation; audit S-06.02.23 remains IN_PROGRESS. This is A10 receipt integrity only; broader spending/provider billing verification remains outstanding. **Size:** M. Work order: `docs/work-orders/S-06.02.66-ai-billing-receipt-integrity.md`.

**Acceptance sub-cases (4 written):**

1. **Given** a priced valid provider receipt, **when** generation succeeds, **then** the single broker cost is reconciled into a durable account/workspace ledger and the next unaffordable request is refused before provider I/O.
2. **Given** a zero, missing, nonfinite or malformed token receipt after nonempty paid generation, **when** the broker accounts for it, **then** it estimates a positive cost and reports `usage_source=estimated`; it does not credit USD 0 as a confirmed invoice or raise a post-transport conversion error.
3. **Given** concurrent workers or a process restart, **when** a spend ceiling is almost reached, **then** the atomic quota reserve is honoured across requests and provider credentials. Corrupt storage refuses the call instead of resetting usage.
4. **Given** a failed or uncertain provider call, **when** the broker reconciles, **then** it never resends automatically only to repair the ledger; owner sees recorded limitations and an actionable error.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.67 — Only install owners may access personal-data inventory and erasure (A24/A05)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.67-privacy-owner-authorization.md).

**Requirement:** Only install owners may access personal-data inventory and erasure (A24/A05).

**Dependencies:** **Dependencies:** existing privacy service S-06.02.04 and owner identity; production audit S-06.02.23 remains active. **Size:** S. Work order: `docs/work-orders/S-06.02.67-privacy-owner-authorization.md`. This security boundary does not certify full A24 deletion/retention and backups.

**Acceptance sub-cases (3 written):**

1. **Given** an ordinary workspace session, **when** it requests subject access, erasure preview, confirmation or deletion execution, **then** the API returns a safe 403 before any personal-data read/write.
2. **Given** the install API token or explicitly provisioned `local` owner login, **when** it runs subject access, previews and confirms erasure, **then** synthetic subject data is removed with a truthful result and unrelated records remain.
3. **Given** a valid owner preview ID, **when** a nonowner knows both ID and deletion phrase, **then** deletion cannot occur. Spoofed workspace input and restart do not bypass the guard.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.68 — Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.68-video-workspace-ownership.md).

**Requirement:** Workspace-owned video projects, recordings and renders cannot cross account boundaries (A05).

**Dependencies:** **Dependencies:** existing workspace login and video stores. No CRM tenancy migration (Q-27). Audit S-06.02.23 IN_PROGRESS, **Size M**. Work order `docs/work-orders/S-06.02.68-video-workspace-ownership.md`. Production penetration and customer acceptance remain open.

**Acceptance sub-cases (3 written):**

1. **Given** two workspaces share a campaign ID, **when** either lists projects, media, reviews or approved exports, **then** SQL queries return only that workspace's rows before limits apply.
2. **Given** a foreign project, media or render ID, **when** a workspace uses direct HTTP read, download, edit, delete, transcript, assembly or publish surface, **then** it receives a bounded 404 without access to bytes or a state change.
3. **Given** the owning workspace, **when** it reads and edits its own records, **then** existing video functions work unchanged.

**Named tasks/subtasks:** None separately numbered in this backlog entry; the acceptance cases above are the implementation and testing obligations. Do not invent sub-story/task IDs.

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

### S-06.02.69 — Image briefs, generated files and video handoff remain private to their workspace (A05)

**Status:** BACKLOG. **Source:** [backlog](../../PRODUCT_BACKLOG.md), [work order](../../docs/work-orders/S-06.02.69-image-workspace-ownership.md).

**Requirement:** Image briefs, generated files and video handoff remain private to their workspace (A05).

**Dependencies:** **Dependencies:** existing workspace sessions, image/video stores; wider CRM tenancy Q-27 is not changed. Feature F-06.02, **Size M**. Work order `docs/work-orders/S-06.02.69-image-workspace-ownership.md`, BACKLOG during audit S-06.02.23 IN_PROGRESS. **Dependencies:** S-06.01.02. **Size:** L. **Indicator:** tools available per workspace. **Dependencies:** S-03.02.02, S-07.01.01. **Size:** L. **Indicator:** browser fallbacks avoided. **Dependencies:** S-03.01.01. **Size:** L. **Indicator:** meetings captured per week. **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** reports produced per research run. **Dependencies:** none. **Size:** M. **Indicator:** provider calls to ineligible recipients. **Dependencies:** S-08.01.01. **Size:** L. **Indicator:** duplicate-send incidents. **Dependencies:** S-08.01.01. **Size:** L. **Indicator:** authenticated accepted sends. **Dependencies:** S-08.01.02, S-08.01.03. **Size:** L. **Indicator:** sends after a complaint. **Dependencies:** S-08.01.01, S-08.01.02, S-08.01.03, S-08.01.04. **Size:** M. **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** runs ending `stuck` **Dependencies:** S-11.01.01. **Size:** M. **Indicator:** steps per fact returned. **Dependencies:** S-02.02.01, S-02.01.05. **Size:** M. **Indicator:** runs **Dependencies:** S-02.02.01, S-06.01.03. **Size:** M. **Indicator:** runs **Dependencies:** S-02.02.01. **Size:** L. **Indicator:** runs returning a **Dependencies:** S-11.02.01, S-02.01.05. **Size:** M. **Indicator:** share of **Dependencies:** S-11.02.02. **Size:** L. **Indicator:** claims dropped by **Dependencies:** S-02.02.01. **Size:** S. **Indicator:** duplicate fetches **Dependencies:** S-11.01.03. **Size:** M. **Indicator:** runs resumed after **Dependencies:** S-02.02.01. **Size:** M. **Indicator:** injection attempts **Dependencies:** S-02.02.04. **Size:** M. **Indicator:** consequential **Dependencies:** S-11.02.02. **Size:** M. **Indicator:** reports opened per run. **Dependencies:** S-11.04.01. **Size:** M. **Indicator:** runs stopped early **Dependencies:** S-03.02.04. **Size:** L. **Indicator:** concurrent runs **Dependencies:** S-11.01.03. **Size:** M. **Indicator:** duplicate side

**Acceptance sub-cases (63 written):**

1. **Given** two workspaces use the same CRM campaign, **when** they view image briefs/assets/queue/summary, **then** SQL returns only the caller's rows before limits apply.
2. **Given** another workspace's image or brief ID, **when** a user downloads, generates, approves, rejects, refreshes or places it in a video, **then** the app refuses with 404 before any media or usage change.
3. **Given** own assets and briefs, **when** used normally, **then** the image and video operations work unchanged.
4. **Given** a declared MCP server, **when** it is connected, **then** its tools
5. **Given** a tool the owner has not granted, **when** an agent names it, **then**
6. **Given** an OAuth grant, **when** it is stored, **then** it is held under the
7. **Given** a capture, **when** it completes, **then** audio never leaves the
8. **Given** a run's findings, **when** a report is generated, **then** every
9. **Given** the same verified findings, **when** XLSX, PPTX or PDF is requested,
10. **Given** page-controlled text beginning with spreadsheet formula characters,
11. **Given** permission marketing without an active recorded grant, **when**
12. **Given** an address that denied permission or is globally suppressed, **when**
13. **Given** a transactional lane, **when** its permission is checked, **then**
14. **Given** an approved due draft, **when** it is queued, **then** an immutable
15. **Given** an ambiguous provider result or an expired claim without a recorded
16. **Given** a reply, cancellation, closed send window, daily cap or lane delay,
17. **Given** a sending identity, **when** it is assigned to a campaign, **then**
18. **Given** a permission-marketing send, **when** authentication evidence is
19. **Given** an allowed SES job, **when** it is submitted, **then** raw MIME
20. **Given** an SNS envelope, **when** it reaches the public feedback endpoint,
21. **Given** a duplicate hard-bounce or complaint event, **when** it is processed,
22. **Given** health metrics beyond configured thresholds, **when** feedback is
23. **Given** an authenticated operator, **when** the delivery API or dashboard is
24. **Given** a recipient using the public unsubscribe route, **when** the signed
25. **Given** a live SES queue request, **when** the exact confirmation phrase is
26. **Given** an action that raises `ActionRefused`, **when** it fails, **then**
27. **Given** three consecutive failed actions, **when** the third fails, **then**
28. **Given** a transient failure, **when** it happens, **then** it is retried
29. **Given** the agent returns to a URL it has already acted on twice with no new
30. **Given** ten consecutive steps that produce nothing new, **when** the tenth
31. **Given** a run that is progressing, **when** these checks run, **then** they
32. **Given** a run interrupted at step N, **when** it is resumed, **then** it
33. **Given** a resumed run, **when** it finishes, **then** the trace is one
34. **Given** a run that already ended, **when** a resume is attempted, **then** it
35. **Given** a fact whose evidence artefact is gone, **when** the trace is
36. **Given** a run with a spend ceiling, **when** the next decision would cross
37. **Given** a run, **when** it is planned, **then** an estimate is produced
38. **Given** a finished run, **when** it is inspected, **then** actual spend per
39. **Given** a goal with a declared field schema, **when** the run finishes,
40. **Given** a model that returns a field not in the schema, **when** the result
41. **Given** no schema, **when** a run finishes, **then** it still returns the
42. **Given** a returned field, **when** it is inspected, **then** it carries the
43. **Given** a field with no source, **when** the result is assembled, **then**
44. **Given** a returned field, **when** it is verified, **then** its value must
45. **Given** a field that is a legitimate derivation (a count, a summary),
46. **Given** a page whose text was truncated by `MAX_READ_CHARS`, **when** a
47. **Given** a URL already read in this run, **when** the agent decides to read
48. **Given** two URLs that differ only by tracking parameters, **when** they are
49. **Given** a page that changed under an unchanged URL, **when** it is read
50. **Given** a page carrying a CAPTCHA, a sign-in form or a 2FA challenge,
51. **Given** a paused run, **when** the owner completes the challenge and
52. **Given** any of these, **when** they are encountered, **then** off_CRM
53. **Given** page text instructing the agent to ignore instructions, exfiltrate,
54. **Given** such a page, **when** the next decision is made, **then** the run
55. **Given** a page where clicking "Send" needs confirmation, **when** the agent
56. **Given** a key that cannot submit anything, **when** it is pressed, **then**
57. **Given** a finished run, **when** its report is opened, **then** every
58. **Given** a run that failed, **when** its report is opened, **then** it shows
59. **Given** a running agent, **when** the owner watches, **then** each step
60. **Given** two runs on the same browser, **when** both act, **then** each has
61. **Given** N concurrent runs, **when** they act on one host, **then** the
62. **Given** N concurrent runs on one account, **when** they act, **then** they
63. **Given** a consequential action already recorded in the trace, **when** a

**Named tasks/subtasks:** **Tasks:** T-07.01.04.a shared provenance-bound artifact model (<=1 day);

**QA:** All relevant unit, integration, API, negative/security, regression, real UI, Render, logs and recovery checks required. **Release gate:** PENDING full story and upstream verification; do not mark DONE.

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
