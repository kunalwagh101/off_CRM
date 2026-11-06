# Native CRM registry component — 2026-11-07

Scope: S-06.01.06 under the owner-approved Q-27 choice. This is a component proof, not an activated customer migration or a completed feature.

`WorkspaceCrmRegistry` owns a transactional routing receipt and bounded leased engines. Known workspace/install/generation identities derive native targets; requests never supply a schema or file. Ready books refuse missing storage, altered ownership, replaced files and lost routing. Concurrent independent registry instances converge on one customer book. Legacy names become blocked views only after proving every legacy CRM table empty. Existing customer rows require explicit reviewed ownership; they remain untouched. SQLite control and books stay inside the durable root for complete recursive recovery. New files are0600 and directories0700; existing permissions remain unchanged.

## Actual execution

```
OFF_CRM_TEST_POSTGRES_URL=<disposable local PostgreSQL16 target> \
UV_CACHE_DIR=/workspace/.uv-cache uv run pytest -q \
  tests/test_workspace_crm_registry.py \
  tests/test_workspace_crm_registry_postgres.py \
  tests/test_workspace_namespace_backup.py \
  tests/test_ci_verifier_environment.py
```

Result: **33 passed, 6 skipped** in4.32s. Six pooler fixture variants skip locally because no pooler is installed. These skips are not pooler acceptance. Actual direct PostgreSQL uses dedicated disposable databases, not SQLite substitution. GitHub CI now runs this registry module explicitly beside the existing genuine PgBouncer isolation proof; retrieve that revision's results before claiming pooler acceptance.

The encrypted SQLite recovery test creates the actual routing receipt, blocked legacy views and two private native books, closes the registry, validates the encrypted backup, removes the source root, restores into a new directory and reopens both customer books with exact private campaign assertions. The earlier independent-file memory/template recovery check also passes. This proves local encrypted recovery, not offsite S3 or live provider acceptance.

Lint: `uv run ruff check --select E9,F63,F7,F82` on the four affected Python files passed before final layout additions; rerun included in commit checks. CI configuration checks5 PASS are included in33 above.

## Failure-first and independent review

- Initial component7 tests failed nested SQLite transactions; moved schema setup outside the routing transaction and all7 passed.
- Closed-auth access and failed-close resource drain:2 failed/9 passed; after fixes11 passed.
- Real PostgreSQL split search_path:1 failed/1 passed/2 skipped; fixed visible-schema validation.
- Missing root/empty root both exposed silent parallel generation; missing receipt already refused via blocked views but lacked the requested recovery error. Added explicit existing-book refusal; all3 variants pass.
- Real PostgreSQL missing routing table and cached missing schema:2 failed/2 passed/4 skipped; now refuse before yielding.
- Cached ownership mutation:1 failed before fix. Live control-file deletion/replacement:2 failed before fix. Per-lease identity/control checks now pass.
- External SQLite layout and fresh control-file mode:2 failed before fix; layout refusal and private creation now pass.

Independent reviewer reproduced missing-control, cached-owner and live-control defects. After fixes the reviewer independently ran18 SQLite registry tests and reported no remaining component blocker. A subsequent independent review and run of the final two file-layout/permission cases also passed2 tests. These20 independent SQLite checks do not substitute for PostgreSQL/pooler or runtime acceptance.

Raw local outputs: `work/three-features/workspace-registry-*-red.log`, `workspace-registry-final-green.log`. These generated logs are not committed. Initial final-command typo referenced a nonexistent CI test file, exited4 with no tests; corrected paths produced the33-pass result above.

## Gates still open

No `create_app`, CLI, worker, sender, recall, privacy or service-factory routing is enabled by this change. Activation requires explicit legacy manifest/archive/apply/quarantine, shared bounce/complaint/rate protection, constructor/startup and restore fencing, cache draining/reopening, the full authenticated three-workspace API/browser/security matrix and independent acceptance. Arbitrary qualified SQL is not a supported customer interface; PostgreSQL schemas under one role are not a database privilege boundary. No DONE status or deployment claim.
