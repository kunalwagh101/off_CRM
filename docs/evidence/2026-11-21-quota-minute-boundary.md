# D-469 — A11 quota rollover versus atomic reservations

GitHub Actions run `44831804205`, Python 3.10 on 2026-11-21 IST. At 22:49:01 UTC, the A11 hosted-SQLite per-minute multi-process test failed with two successful fake provider sends. All other 3,326 tests of that job passed; the Python 3.11 job on the same commit succeeded.

The current quota source uses `_minute_window() = floor(UTC epoch / 60)` and resets `minute_count` at a boundary. The hosted-SQLite `exclusive()` uses SQLite `BEGIN IMMEDIATE` across read, check, reserve and write. The original test launched processes at an uncontrolled time and asserted only one send even if those calls landed in different calendar-minute windows. The observed minute-boundary timestamp makes a test-timing false failure likely, but the log alone cannot prove exactly when each worker reserved.

## Test repair (source commit `a4cb8951df61e185f89c7e2727b9ab3983b808f3`)

- Both spawned child processes now override only the quota minute-window function with the same parent's snapshot, preserving the actual hosted SQLite lock and transaction.
- A separate single-process test proves one reservation is accepted in a minute, another refused in that minute, and a fresh reservation accepted after the minute changes.
- This change makes a deterministic atomicity test. It is not proof of a rolling 60-second rate limit, does not erase legitimate prior failures and does not change production behavior.

Current-HEAD CI, PgBouncer, real-provider quota and independent security acceptance remain required. D-451 shared CRM data and D-452 suppression re-import still block customer release.
