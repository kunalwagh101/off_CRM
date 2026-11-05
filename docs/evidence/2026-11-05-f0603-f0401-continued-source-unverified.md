# 2026-11-05 — F-06.03 / F-04.01 owner-authorised source checkpoint

**Status:** code written to develop; NOT RELEASED; QA BLOCKED AND NOT RUN.
This is a handoff/evidence map, not proof of passing tests.

## Changes after 4237fe3

F-06.03 backup S-06.03.04:
- db/hosted_backup.py, db_cli.py and Dockerfile now support separately encrypted
  PostgreSQL snapshots into owner-supplied private S3 and guarded restore into
  a fresh empty PostgreSQL database. New tests/test_hosted_backup.py covers
  tamper, wrong key, remote checksum and disposable PostgreSQL restore.
- docs/architecture/HOSTED_BACKUP.md has the operator-only restore runbook.
  No actual bucket, IAM identity, nightly schedule, remote export or recovery
  demonstration exists.

F-06.03 durable profiles S-06.03.06:
- CompanionRegistry supports an existing HostedStorage connection for
  companion and procedure tables, preserving explicit owner selection and
  owner-scoped SQL operations. The app now passes hosted_storage at startup.
- A static cutover check fails closed if older local profile/procedure rows
  differ from the hosted destination. No automatic local migration or
  deletion has been performed.
- tests/test_hosted_companion_profiles.py targets deleted local folder,
  cross-workspace isolation, two-instance disable and real PostgreSQL reopen.
- Executable tool pins, traces, privacy erasure adapters, media, outboxes,
  meetings, several integrations and other local stores are STILL EPHEMERAL.

F-04.01 team S-04.01.02/.03/.04:
- Explicit owner-approved workspace skill rows and broker instructions; a
  deleted or disabled procedure is rejected before model egress.
- One-level, at-most-three child reasoning through the existing AI broker,
  child outputs treated as untrusted input to a parent synthesis. No model-
  selected tool, grandchild, autonomous publish or send.
- Five owner-provisioned roles dispatch to the EXISTING trend read, video
  director/assembler, approved-image-to-draft pipeline, campaign analytics,
  and GTM plan drafting; no independent second workflow engine created.
- New tests/test_companion_skills.py, test_companion_delegation.py,
  test_agent_role_team.py and updated Dockerfile.review focused gates.

New A05 source-review security findings:
- D-375: post-draft images, posts and topic history lacked workspace filters;
  mitigation in distribution/pipeline.py and store.py, two-workspace test in
  tests/test_pipeline.py.
- D-376: campaign goals and latest post metrics were read without workspace
  SQL predicates; mitigation in distribution/engine.py and store.py, test in
  tests/test_distribution.py.
- Both new defects were source-detected, not reproduced through a live
  exploit. Keep them open for independent security QA.

## Observed blockers

Render isolated review service off-crm-review-runner-20261015 in workspace
Kunal Wagh's Workspace showed pipeline_minutes_exhausted on
2026-11-05T10:06:54Z. A new code checkout was not available in the current
execution environment (external DNS blocked). The uploaded dev-prompt files
were materialised by Files tooling but were not accessible from the local
executable container. No code/tests were executed locally or on Render in
this iteration. No customer deployment or main-branch changes.

A read-only GitHub connector source check validated that expected symbols,
owner auth, workspace predicates, PG backup/restore flags and QA gate commands
are present. This is NOT an executable test pass.

## Ordered runnable QA, once environment is available

1. Pull the latest develop commit and read AGENTS.md, DEFINITION_OF_DONE.md,
   BOARD.md and the attached skill instructions before changing anything.
2. Red/green focused:
   uv run pytest -q tests/test_hosted_backup.py
   uv run pytest -q tests/test_hosted_companion_profiles.py
   uv run pytest -q tests/test_companion_skills.py tests/test_companion_delegation.py
   uv run pytest -q tests/test_agent_role_team.py
   uv run pytest -q tests/test_pipeline.py tests/test_distribution.py
3. Run:
   uv run ruff check --select E9,F63,F7,F82 .
   uv run pytest -q
   uv run python scripts/verify_board.py
   frontend npm tests, build, audit, Chromium owner/workspace acceptance.
4. Use disposable PostgreSQL, never live customer data:
   OFF_CRM_TEST_POSTGRES_URL=<disposable test database>
   uv run pytest -q tests/test_hosted_backup.py tests/test_hosted_companion_profiles.py
   OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q
5. On restored Render free-plan build minutes, trigger ONE isolated review build
   for the current develop source, examine exact logs, reproduce failures,
   fix and re-run until it is LIVE with full SQLite/PostgreSQL/browser gates.
   Do not change paid service tiers or touch production.
6. Separately run full offsite object-storage recovery drill only after the
   owner supplies an approved private bucket, isolated IAM, retention and key
   custody. This cannot be simulated as if it were an actual disaster recovery.
7. Penetration/security review the exact owner API session, cross-workspace
   image/metrics boundaries, deletion/retention and generation costs.

Do not call S-06.03.04/.06, S-04.01.02/.03/.04, or either full feature DONE
without these gates. Board WIP and source-of-truth stories remain unchanged.
