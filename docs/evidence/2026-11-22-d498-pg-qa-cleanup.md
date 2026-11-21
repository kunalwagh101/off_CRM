# D-498 — PostgreSQL QA teardown without elevated signal permissions

**2026-11-22 · off_CRM develop · F-06.02 reliability / F-06.03 hosted tests**

## Observed failed build

- Render disposable QA review image at commit `bae5db00`: deploy `dep-dc0vm8afngtc73e3lh40` status **build_failed**.
- The preceding Python/PostgreSQL suite reported **3,479 passed, 156 skipped, 1 error** in 531.86 seconds.
- The error was at teardown in `tests/test_install_import_boundaries.py` when `isolated_install_database` executed `DROP DATABASE … WITH (FORCE)`.
- The PostgreSQL test role `offcrmqa` is created with `LOGIN CREATEDB`, **not** `pg_signal_backend`. A `DROP ... FORCE` attempt to terminate a different role's process failed with `psycopg.errors.InsufficientPrivilege`.
- This error does **not** establish a production application defect, nor does it prove that PostgreSQL schema isolation or live CRM migration failed. The test's assertions passed; the disposable database teardown failed.

## Test and fix

- TDD test commit `189e2f8d1e68d2c852956d3155782156047116db` added three fake-server cases for: no FORCE/elevated role requirement; a transient active connection requiring a bounded retry; a persistent active connection which must still fail explicitly.
- Implementation commit `96c65db459a5e928f6fcea0417bb080ccd51fcea` replaces `DROP DATABASE WITH (FORCE)` with ordinary `DROP DATABASE` and at most five attempts. Retries apply **only** to `psycopg.errors.ObjectInUse`; other database errors immediately propagate. No `pg_signal_backend` privilege is added and no customer database is accessed.
- The physical test database name is random and remains `offcrm_install_<uuid>`; all cleanup is restricted to that per-test database. It never queries, drops or modifies other databases.

## Verification and release limits

- Exact-source GitHub CI [44947976626](https://github.com/kunalwagh101/off_CRM/actions/runs/44947976626): all **five jobs PASS** (Python 3.10, 3.11, 3.12, real PostgreSQL, quality/board). Its real PostgreSQL job logged **3,531 passed and 107 skipped**, with 221 focused checks also passing.
- Exact-source Render review deployment `dep-dc10602jnfac73f8usbg` reached **LIVE** at 2026-11-21 21:11:12 UTC on `96c65db`. Its full real PostgreSQL stage passed **3,482 tests, 156 skipped, 44 warnings, 0 errors**. The earlier teardown failure was not reproduced.
- **Observed RED:** a replay of the test-only `189e2f8` Python 3.11 job [44947941384](https://github.com/kunalwagh101/off_CRM/actions/runs/44947941384) failed exactly the three new D-498 tests: no-force permission, transient active-session retry and persistent-leak refusal. The run reported **3 failed, 3,417 passed, 149 skipped**. All three failures were `psycopg.errors.InsufficientPrivilege` from the original forced-drop fixture. No other test failed.
- **Observed GREEN:** fixed `96c65db` five-job CI [44947976626](https://github.com/kunalwagh101/off_CRM/actions/runs/44947976626) PASSED every job; real PG **3,531 passed, 107 skipped**.
- Keep all parent features unfinished until full application, offsite recovery, AI roles, per-user permissions and independent security checks pass. This QA fixture fix does not resolve durable customer storage, S3 key custody, authenticated hosted UI or provider acceptance.

## Repeatable commands

```sh
uv run pytest -q tests/test_install_import_boundaries.py
OFF_CRM_TEST_POSTGRES_URL=postgresql://<disposable-role>@127.0.0.1:5432/offcrmqa OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q tests/test_install_import_boundaries.py
OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q
uv run python scripts/verify_board.py
```

Use an isolated PostgreSQL test role with CREATEDB and no other customer database permissions. Never run these commands against a customer or production PostgreSQL database.
