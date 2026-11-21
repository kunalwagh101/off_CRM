# 2026-11-21 — D-476 restore safety verification

Feature: F-06.03 / S-06.03.04. Branch: develop only.

## Problem

A PostgreSQL database with no application tables can still contain user-created objects. The restore-target preflight did not inspect `pg_ts_dict` or `pg_publication`. A restore could start against this nonempty target.

## TDD checkpoints

- RED test source `efe47007a2dfcc541ea6f0a1d06a3a20a7397238`: extended the disposable real-Postgres target matrix with CREATE TEXT SEARCH DICTIONARY and CREATE PUBLICATION, asserting HostedBackupError before restore.
- GREEN source `248851393969b88248cba27637527a37a68e56f8`: added the two PostgreSQL catalogue checks in `_ensure_empty_restore_target` and maintained fail-closed error text.
- Test command: `uv run pytest tests/test_hosted_backup.py -q` with actual disposable PostgreSQL plus full suite and board verification.
- Observation: results pending exact-source CI and QA review. A committed test or patch is not proof of PASS or observed RED.

## Safety / rollback

No customer service, production database or backup object was modified. There is no new schema or storage format. Restore still refuses nonempty targets before running `pg_restore`. Reverting the source would remove the extra refusal and is not a safe production rollback; if tests fail, correct forward on develop.

## Open gates

Real independent S3 credentials, approved backup key custody, scheduled offsite snapshots, full operator disaster recovery, independent penetration testing, live customer-app acceptance and complete story dependency/DoD evidence remain open. No DONE claim.
