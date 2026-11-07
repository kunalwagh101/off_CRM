# Hosted tool storage acceptance — 2026-11-07

Scope: S-06.03.06 with S-04.01.01 grants and S-06.02.23 QA. Web and actual
offsetx-tools consumers now select the same hosted target. Local SQLite behavior
is preserved. Source changes remain on develop; no customer migration, main
promotion, paid provider call or deployment occurred.

## Actual checks

Pre-final affected SQLite/actual PostgreSQL/API/CLI/security/recovery bundle:
251 PASS. Subsequent forced-PostgreSQL CRM bundle:247 PASS/3 SQLite-only skips.
These precede the final safe-diagnostic and URL validation hunks; final exact
source rerun will be recorded below before commit.

Dedicated actual Docker plus unit checks:35 PASS. The two normal Docker cases
cover hosted SQLite and PostgreSQL; they fetch the exact current committed Git
SHA and run the official Python image by its inspected digest. Actual output
proves UID65534, only loopback, read-only root/inbox, no effective capabilities,
no-new-privileges, absence of private store/socket and absence of application
secret environment variables. Public work output and scoped SQL receipts survive
registry reopening. This is actual container execution, not subprocess stubs.

Actual pg_dump/pg_restore16.15 encrypted recovery:8 PASS. The disposable source
contains two CRM schemas, same-email contacts, exact private template wording,
disabled flags, tool registrations, run output and same-workspace profile grants.
Root and per-schema counts/data reconcile after restore to an empty database.
S3 transport is FakeS3; this is not a live external bucket or offsite drill.
Test-only local wrappers invoke actual version16 clients in the task-owned
PostgreSQL container and reject other host/port targets; credentials stay in
environment variables, never process arguments.

The tool/profile cutover test retains a complete private original archive,
verifies both phases, restarts the hosted consumers and exercises the inverse
on a disposable copy of the first archive. API/CLI tests delete the disposable
application folder and retain pins/profile grants in hosted SQL. Concurrency
checks cover duplicate registration, all-thread cache close/reopen and actual
PostgreSQL schema-lock waiters. CLI wrong-install/master-key cases refuse and
do not print either key.

## Failure-first findings

- Native hosted target support initially3 FAIL/3 PostgreSQL skips; correct actual
  SQLite/PostgreSQL implementation plus existing tool tests37 PASS.
- New migration recipe and grant acceptance2 FAIL/2 PG skips; explicit staged
  migration and recipe validation fixed them.
- Existing companion archive hardlink reproduction erased both aliases. The
  new refusal checks path and inode identity for every file pair.
- CLI/app and foreign-install path2 FAIL/2 PG skips before routing CLI through
  the same target and install/key checks.
- Companion consumer without a separate document store2 FAIL before adapting
  its initialization/transactions to the cached hosted transport.
- Independent actual PostgreSQL constructors returned ok/UniqueViolation. The
  deterministic shared-lock test failed before the direct302 transaction fix.
- Real timeout probe with a started marker found the container still running.
  Trusted-name cleanup now stops it. The first probe without a marker passed
  without proving execution; it is not acceptance evidence. One-second startup
  allowance was also too short in an independent run; the marker remains and
  the bounded timeout is now10s.
- Review reproduced arbitrary imported stderr in unknown-cleanup history.
  New tampered-history RED1; fixed diagnostic reconstruction33 tool tests PASS.
- Valid SQLite duration2**35 caused actual PostgreSQL NumericValueOutOfRange.
  Versioned BIGINT upgrade fixes it; forward/inverse2 PASS.
- Source/target alias and dangling-source-link3 RED then3 GREEN. Unsupported or
  Path-folded direct URLs2 RED; CLI already refused the malformed configuration.
  Guarded targets3 PASS with no URL credential canary in diagnostics.

Initial real-Docker fixture omitted creating the private canary directory and
failed before execution; corrected before container acceptance. An early command
referenced a nonexistent readiness test file and ran no tests; corrected paths
produced the recorded results. Environment resume stopped the disposable PG
container; one rerun produced connection-refusal errors, then the task-owned
container was restarted and real PostgreSQL verification resumed.

## Independent review

Successive cold reviews independently ran29,38,26 and39 checks, including actual
PostgreSQL and real Docker cases. They found the omitted CLI, schema race,
missing recovery identity and raw-history diagnostic issues; all were reproduced
and fixed. Final history fix review independently33 tool tests PASS, diff check
PASS, no remaining concrete defect in that delta. Broader feature completion is
not implied by these component reviews.

## Boundaries

Sandbox artifacts and other unresolved file homes remain outside this SQL move.
Process-crash/start journaling and complete runtime cancellation/recovery remain
open. CRM request routing/legacy ownership cutover is still not activated.
External private bucket/IAM/retention and live configured provider/platform
acceptance remain required. None of F-06.02/F-06.03/F-04.01 is marked DONE.

## Final exact-source checks before commit

```
PATH=<test-only PostgreSQL16 wrappers>:$PATH \
OFF_CRM_TEST_REAL_TOOLS=1 OFF_CRM_TEST_POSTGRES_URL=<disposable PostgreSQL16> \
UV_CACHE_DIR=/workspace/.uv-cache uv run pytest -q \
  tests/test_hosted_tool_registry.py tests/test_tool_registry_real_sandbox.py \
  tests/test_ai_tools.py tests/test_companion_import.py tests/test_content_import.py \
  tests/test_hosted_companion_profiles.py tests/test_hosted_storage_readiness.py \
  tests/test_storage_inventory.py tests/test_companion_catalog_api.py \
  tests/test_cli_workspace_lease.py tests/test_traceable_errors.py \
  tests/test_agent_companions.py tests/test_companion_skills.py \
  tests/test_companion_delegation.py tests/test_ai_egress_wall.py tests/test_hosted_backup.py
```

Actual **257 PASS**,39.60s, after final URL guard, safe diagnostic, BIGINT and
readiness changes. Raw local output: work/three-features/hosted-tools-final-all.log.
Whole-repository fatal-name/syntax lint and diff check pass. New CI step explicitly
provisions the official image, then runs the real sandbox cases in the PostgreSQL
job; the product sandbox still cannot pull an image. This new revision needs its
own full CI before a green-pipeline claim.

Added actual-pooler fixture variants to the early CI gate. Local tool module:
29 PASS/11 pooler skips; these are explicitly not local pooler acceptance. Final
independent URL/import/runbook scan found no blocker and targeted6 checks passed.

Fresh Render connector read in the already approved workspace: review's latest
failure remains pipeline_minutes_exhausted at2026-11-05T10:06:54Z, with no newer
build/deploy event. Review and off_CRM are not marked suspended and both have
auto-deploy off. These metadata facts do not establish HTTP health or the current
remaining billing balance. No Render build or infrastructure change was made.
