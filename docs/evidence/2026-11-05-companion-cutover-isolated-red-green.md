# F-06.03.06 / D-377 — companion import isolated SQLite red-green

Date: 2026-11-05. Branch: develop. **Tested module only; not a product release.**

## Actual result (small isolated fixture, real Python and SQLite)

The local execution container could not download the whole repository (DNS
to GitHub was unavailable); the isolated Render review service reported
pipeline_minutes_exhausted. A focused harness was therefore assembled with
the **exact source bytes** of db/companion_import.py copied from the GitHub
connector. Its git-blob SHA-1 was calculated locally and compared to the
GitHub file blob, proving the migration module itself was identical.

Original imported module SHA-1: 24b674181ea46a6d02c4d4b1512462df27e5ef5d
After fix imported module SHA-1: 8419eb15cd699ec1247e2c1ebb7b71c6b50abca4

The harness replaced dependencies with narrow test implementations of the
hosted database, app schema, workspace lock and restore-pending check. It did
NOT run the repository's actual hosted connection implementation or real
application entry point. SQLite's executescript was left with its native
transaction semantics, which caught a real defect.

**RED command:** PYTHONPATH=/mnt/data/isolated_offcrm pytest -q tests/test_isolated_companion_import.py

RED: 3 failed, 5 passed (0.35s). All three failures were:
sqlite3.OperationalError: cannot commit/rollback - no transaction is active.
Root cause: calling Database.executescript(SCHEMA) inside the active
HostedStorage.exclusive transaction.

**Fix:** D-377 at e601f34 and 4b98b63. Added trusted static
ensure_companion_schema(), issuing each DDL statement through Database.execute
rather than SQLite executescript. Applied both to companion registry startup
and the archive-first migration.

**GREEN command:** PYTHONPATH=/mnt/data/isolated_offcrm pytest -q tests/test_isolated_companion_import.py

First green: 8 passed (0.32s), exact migration SHA-1 verified.
Additional negative/legacy scenarios added to isolated harness:
11 passed (0.33s).

Isolated cases cover:
- Archive-first copy, exact row counts and keeping executable tool rows local.
- Refusal of conflicting hosted data without deleting local rows.
- Idempotent retry after committed remote copy but failed local cleanup.
- Refusal of non-empty executable tool grants (still locally stored).
- Rejection of source/destination SQLite alias and world-readable archive.
- Rejection of archive inside local data folder or altered local schema.
- Old schema without procedure table.
- Existing archive mismatch not overwritten.
- Uncooperative writer changing local rows after hosted copy (local untouched).

## Required real acceptance, NOT RUN

Run the actual test sources tests/test_companion_import.py,
tests/test_hosted_companion_profiles.py, tests/test_companion_skills.py,
tests/test_agent_role_team.py and tests/test_pipeline.py under uv run in the
real repository, first SQLite then disposable PostgreSQL, followed by all
other Dockerfile.review QA including security, frontend and Chromium.

External backups, cross-install safety, real Render build and independent
penetration remain open. These isolated checks support a bug fix; they do
NOT meet DEFINITION_OF_DONE.md and cannot be called full QA.


## 2026-11-05 — D-379 full-registry archive integrity extension

D-379 source review found the archive verification compared companion rows
only, despite archiving executable tools too. Added SHA-256 of the whole
logical SQLite database (schema, indexes, tools and other rows), read under
one source transaction, compared with the private archive and rechecked
in the exclusive local cleanup transaction. Source 15ca74f5.

Local copy of exact source checked against GitHub blob with git hash-object:
3e4b9428e77d9e04c8943fe09be3fd264d8268df.

Actual command: PYTHONPATH=. pytest -q tests/test_isolated_companion_import.py
Final isolated test result: 13 passed in 0.35s on real SQLite.

The added cases changed the archived executable tools while profiles still
matched, and inserted a new unarchived tool before local cleanup. Both
operations failed closed; local companion records remained intact.

The local tests used stand-in HostedStorage, lock and application settings.
This is NOT the complete committed product test suite, PostgreSQL QA,
customer migration, external security test or production release evidence.
A previous one-case failed harness run used a world-readable test archive;
after correcting its private 0600 mode, all 13 isolated tests passed.
Repository regression tests are committed but still unexecuted.
