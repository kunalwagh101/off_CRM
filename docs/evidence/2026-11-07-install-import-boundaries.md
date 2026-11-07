# Install ownership — imports, recovery and physical PostgreSQL boundary

2026-11-07, develop only. S-06.03.07 IN_REVIEW; F-06.03 remains open.

## Failures and fixes

Independent actual CLI demonstrated a foreign UUID setting import-local --skip successfully. New table-driven16 SQLite REDs cover four import families, yes/skip and reusable helpers. These now claim before customer/source/archive work. Missing/invalid UUIDs refuse. Failure logs are intentionally outside the byte-for-byte source comparison; logging a refusal is required.

Claim-owner metadata RED3 showed key-check writes before foreign/malformed refusal. Lost-key RED1 showed foreign key clearing. Owner/key checks are now one transaction; reset validates existing owner without old key. First implementation nested SQLite BEGIN (47 failures/30 errors); a private lock-owned key-check helper fixed that before commit. Post-recovery content/profile RED2 exposed ordering and private archive/source WAL side effects; guards now run before opening local sources.

Three-pair context inode checks cover source-target/source-archive/target-archive. Initial third fixture was lazy/nonexistent; corrected fixture then reproduced missing preflight before the fix. All alias checks precede ownership writes and preserve existing bytes.

Actual PostgreSQL RED1 showed distinct schema targets accepting different installs on one physical database. Database-global advisory lock302 now fences an inspection of all hosted metadata roots. Same logical UUID may use internal schemas; a foreign/malformed owner or nonempty unclaimed root refuses. Metadata must be readable, use supported base tables, have no RLS/forced-RLS, and span at most128 roots. Catalog identifiers are quoted; errors never echo credentials. Independent restricted-role reproduction confirmed RLS-hidden original ownership bypass, then verified refusal after flags were checked. Foreign-table/view/materialized ownership metadata also refuses. No extra persistent identity authority is introduced.

## Commands and actual results

```bash
OFF_CRM_TEST_POSTGRES_URL=<disposable-test-url> uv run pytest tests/test_install_import_boundaries.py tests/test_install_database_owner.py tests/test_context_import.py tests/test_hosted_timer_settings.py tests/test_hosted_storage.py tests/test_crm_hosted.py tests/test_companion_import.py tests/test_content_import.py -q
OFF_CRM_TEST_POSTGRES_URL=<disposable-test-url> uv run pytest tests/test_install_import_boundaries.py -q
OFF_CRM_TEST_POSTGRES_URL=<disposable-test-url> uv run pytest tests/test_hosted_backup.py -q
```

Affected8-file bundle315 PASS. The final owner matrix uses separate generated physical databases per test (schemas no longer isolate independent install tests):99 PASS. Two-writer tests prove exactly one owner on SQLite, real PostgreSQL and across simultaneous schema targets. Real encrypted PostgreSQL16 pg_dump/restore8 PASS preserves install claim and customer/native/tool/grant data; object transport remains FakeS3. Host client wrappers only forward to the task-owned local test container, never production. Independent reviewer112 owner/import PASS and actual restricted-role RLS replay PASS, with all private test databases/roles removed.

Exact previous browser source53a93a0 full42399243286/container42399243238 SUCCESS: supported Python3versions each3231 PASS/97 skips; PostgreSQL3290 PASS/107 skips; pooler64 PASS/1 intentional skip; Docker3 PASS; board72/72; frontend237/build and actual recovery browser PASS. That does not establish CI for newer recall/import code.

## Operator upgrade, recovery and rollback

Set one stable non-secret OFFSETX_INSTALL_ID UUID and the existing master key for this logical installation before startup/import. Keep both settings across replicas/restarts; another install uses a new database and UUID. Tested real app restart/foreign boot refusal and CLI decisions preserve sources. Context imports now require the master key through the same deployment setting as other imports.

For a lost master key, stop app/workers and retain a verified encrypted backup. Reuse the existing UUID, target the actual owned database and explicitly run offsetx-db forget-provider-keys --yes. The old key is not needed. Only provider keys/key-check clear; customer state and install claim stay. Start with a replacement master key and paste provider keys through Connectors. Actual same-install command + application regression passes. Unknown claims require recovery of verified identity, never manual ownership replacement.

Restore into a new empty independently verified database with the same UUID and key; the actual encrypted restore reclaims that UUID and reopens records. Keep the claim during a code rollback and retain post-upgrade data. Never delete/edit ownership to admit another install or automatically revert a migrated customer source. New code changes no identity document format; prefer forward fixes over restoring known import bypasses. Explicit raw copy-crm/copy-log are trusted offline admin tools, separate from import decisions; they do not grant tenant access.

Full exact-source CI, final board evidence and whole-feature release gates remain required. No real S3/provider/customer/Render deployment or main promotion occurred.

## Final current-root preflight correction

D-438: an unsupported current-root view could execute before the later catalog refusal. A transactional marker rolled back and gave a false negative; an actual PostgreSQL sequence probe (nextval survives rollback) then reproduced RED1. Normal claim and key reset now catalog-check before reading root rows. New regression raises the isolated-database matrix to100 cases; focused owner pair113 PASS after the final change. Earlier315/99 results precede this final two-line ordering change. Additional2f0 actual HTTP/auth/workspace/upload/privacy/egress security bundle171 PASS. No comprehensive penetration certification is claimed. New exact-source CI remains required.
