# D-468 — Refuse recovery over PostgreSQL collations/text search

Date 2026-11-21, branch develop. Work order: S-06.03.04. Test-first commit: `1fe027d21c330f5f35259c0d6fe1409b4c1d2dd9`. Source repair: `3002c8ab5c9fc5d19f30b674525f0a6ec08d1f00`.

The original empty-target check covered schemas, ordinary relations, views, functions, enums/domains and installed extensions, but did not check user-defined collations or text-search configurations. This gap matters because `pg_restore` must never operate on a destination containing customer-owned objects, even if it holds no tables.

## Assertions

- `tests/test_hosted_backup.py::test_restore_rejects_views_functions_types_schemas_and_extensions_without_dropping` now requires `pg_catalog.pg_collation` and `pg_catalog.pg_ts_config` to be checked in the guard.
- `tests/test_hosted_backup.py::test_real_postgres_snapshot_survives_object_copy_and_restores_equal_counts` now creates each object in a disposable target PostgreSQL database and expects a refusal. It then drops the object, performs an encrypted restore and reconciles full table counts and workspace records.
- Rollback is a source revert; the change creates no DB objects or migrations and performs no production operations.

## Not yet verified

Final-head CI outputs are not recorded here. Real owner-controlled offsite S3, key custody and an independent target recovery exercise are still required. No production release, DONE board movement or independently commissioned penetration assessment is claimed.
