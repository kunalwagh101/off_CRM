# Audit WP1 — durable customer state and safe recovery

Repository: `kunalwagh101/off_CRM` · Stories: **S-06.02.09 / S-06.02.11**
Branch: `feature/audit-wp1-durable-state-safe-recovery` · [PR #13](https://github.com/kunalwagh101/off_CRM/pull/13)

**Integration certification pending:** the complete WP1 gate passed at
`b3fb49ce950b3b888a4c4f4e4fedbc9aa09d1e59` in
[run 34305738186](https://github.com/kunalwagh101/off_CRM/actions/runs/34305738186).
Main subsequently advanced; final acceptance is being repeated after integrating
its security and page-reuse work at `5b19a54e60233134ec3bda711a58f7f37a1a94a7`.

## What this delivers

One company installation can retain its customer workspace across container
replacement and recover it from an encrypted archive. Concurrent CRM requests
cannot commit or roll back another request's transaction. Restore validates the
archive before interrupting service, drains work, replaces all local state,
reopens every dependent service and verifies health. A failed restore recovers
the previous generation; a failed rollback blocks ordinary traffic.

The branch includes main's transaction, authentication-limiter, constant-time
username-comparison, required-authentication, host-allowlist and page-reuse fixes.
The original audit remains unchanged
as the historical baseline. WP1 addresses **five findings**, not the whole audit.

## Finding-to-evidence mapping

| Finding | Delivered behaviour | Acceptance evidence |
|---|---|---|
| **A01 / P0** — ephemeral customer state | One persistent mount; every durable local path within its data root; startup rejects missing mounts and temporary/split production paths; app runs as UID 10001 | `test_production_configuration_refuses_ephemeral_customer_state`, `test_configured_root_owns_default_database_and_gmail_token`, `test_production_rejects_missing_persistent_mount`; real container kill/recreate test |
| **A02 / P0** — transaction ownership | Connection and cursor operations share one ownership lock; bare writes autocommit; nested savepoints retain outer ownership; named SQL parameters stay intact | Interleaved failed writers, bare cursor writes, concurrent commit/rollback attempts, nested transactions, and 40 concurrent API writes checked after restart |
| **A03 / P1** — unsafe restore | Complete request lifetimes and timers drain; worker leases exclude replacement; all stores close and rebind; rollback restores service or leaves maintenance active | Rejected archive leaves routes healthy; successful restore rebinds CRM, sales, chat and delivery; streaming drain; worker exclusion; rebind/rollback failure injection; three actual subprocess crash boundaries |
| **A04 / P1** — incomplete backup | Versioned manifest inventories all durable local files; SQLite snapshots include committed WAL; asset references relocate; local keys remain usable; explicit cache exclusions | Populated workspace into a fresh root; empty file and changed database filename; encrypted provider key and signing-key preservation; malformed paths/symlinks/corrupt SQLite refusal; bounded encryption and multipart upload |
| **A17 / P1** — misleading readiness | Mounted/writable paths, actual live database connections, service bindings and local signing key are checked; maintenance and broken recovery return 503 | Missing database, closed auxiliary connection, missing/changed signing key, maintenance, failed rollback and missing mount tests |

The eight story criteria are covered by these tests in
`tests/test_audit_wp1.py`, `tests/test_wp1_recovery_edges.py`,
`tests/test_workspace_lock.py` and `verification/test_wp1_live.py`.

## Verification record

The release workflow is
`.github/workflows/wp1-verification.yml`. It installs locked dependencies, builds
the frontend and actual production image, requires real PostgreSQL, sandboxed
Chromium and Docker, runs the complete Python suite, exercises browser recovery
and container replacement, and re-runs all DONE story evidence commands.
Missing or skipped Python/live evidence fails the gate.

Final acceptance results will be recorded here after the run completes.

Main independently allocated S-06.02.10 and R-92–R-94 to authentication while
WP1 was in flight. Recovery is therefore S-06.02.11 / R-95. The authentication
story retains its original identity and evidence. S-06.02.09's statement guard
is extended to native cursor operations without changing its acceptance intent.

The container test uses a disposable persistent volume, a read-only root,
`no-new-privileges`, and only the startup capabilities needed to prepare ownership
and drop privileges. The running application has **UID 10001 and zero effective
capabilities**. It creates records/assets, exports a backup, kills the container,
recreates it on the same volume, verifies persistence and restores the archive.

The browser test uses the built frontend against a real Uvicorn process. It
downloads the encrypted archive through Settings, verifies the success message
and cleared passphrase, creates later data, uploads the archive, confirms restore,
checks the reload and verifies that the original records and dependent APIs work.

Native Windows CI independently proves overlapping shared leases and exclusive
cross-process recovery ownership. Linux remains the production container target.

All fixture data and credentials are synthetic and isolated. The PostgreSQL
backend tests use PostgreSQL 16; this does not imply that every application store
has been migrated to PostgreSQL.

## Defects found while completing the story

- Reproduced and removed import-time patching and fragile database wrapping;
  retained SQLite's native connection, backup and named-binding semantics.
- Closed archive destination traversal, empty-file handling, symlink escape,
  oversize allocation, live auxiliary-store readiness and corrupt legacy-archive
  failure paths with regression tests.
- Added crash-safe generation swaps, a durable recovery journal and startup
  rollback/cleanup so process death cannot leave a half-replaced workspace.
- Closed old thread-local handles and coordinated API requests, timers and
  delivery workers with the same recovery boundary.
- Fixed the production Docker build's missing shared video conformance fixture
  and startup directory permissions under restricted capabilities.
- Fixed the frontend export handler's use of its form after an asynchronous
  download. The live test initially chose the restore passphrase field because
  the export label includes help text; its locator now scopes to the export
  form, while retaining the real download and restore assertions.

## Operational limits and remaining work

The supported deployment is **one web process and one persistent disk for one
company installation**. It is not a multi-tenant or horizontally scaled service.
Mixed PostgreSQL/local recovery is explicitly refused by the local archive API.

The default encrypted archive limit is **64 MiB**, with bounded ZIP construction
and limits on expansion, members and manifest size. Large media workspaces may
need a separately sized archive limit and enough RAM/disk for staging plus the
previous generation. Export fails clearly when the cap is reached. Recovery
copies must be stored off the live disk with their passphrase kept separately.

Environment credentials, provider-side authorisations and OS secret stores must
be configured on the recovery host. Old schema-v1 archives are accepted as
`legacy_partial: true`; they cannot restore data they never contained. The full
deployment, migration, rollback and recovery procedure is in
[WP1_OPERATIONS.md](../architecture/WP1_OPERATIONS.md).

This evidence uses real infrastructure in disposable CI. It does not certify a
specific customer deployment, account credentials or live provider delivery.
The original live-audit assertions remain intact. Its six known failing checks
for **A09/A32/A33/A34/A35** remain tracked outside WP1, as do the other findings
in the original audit. No external messages or provider sends were performed.
