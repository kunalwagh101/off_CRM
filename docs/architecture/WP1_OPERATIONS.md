# Durable workspace operations — S-06.02.11 / Audit WP1

This runbook covers the supported production topology: one Linux web process,
its local workers, and one persistent disk for one company installation. It does
not make the application multi-tenant or move every store onto PostgreSQL.

## Deployment contract

`render.yaml` provisions one `1c-2g` Docker web instance with a 10 GB disk at
`/var/lib/offcrm`. Customer state is in its `local_data` subdirectory. Render
preserves files under the mounted disk across restarts and replaces a service
with a disk by stopping the previous instance first. The Blueprint uses the
[documented compute plans](https://render.com/docs/blueprint-spec) and
[persistent disk lifecycle](https://render.com/docs/disks), checked 8 September 2026.
Automatic deployment uses `autoDeployTrigger: checksPass`, so it waits for the
linked branch's CI checks. The recovery workflow also runs on `main` after merge;
it is not limited to this feature branch. Apply the Blueprint setting to the
actual service before relying on that deployment gate.

Required settings:

| Setting | Production value / rule |
|---|---|
| `OFFSETX_PRODUCTION` | `1` |
| `OFFSETX_PERSISTENT_MOUNT` | `/var/lib/offcrm`; must actually be mounted |
| `OFFSETX_DATA_DIR` | `/var/lib/offcrm/local_data`; a child of the mount |
| `OFFSETX_OUTREACH_DB` | Defaults to `OFFSETX_DATA_DIR/offsetx_outreach.db` |
| `OFFSETX_GMAIL_TOKEN` | Defaults to `OFFSETX_DATA_DIR/gmail_token.json` |
| `OFFSETX_GMAIL_CLIENT_SECRETS` | If used, a file within the data directory |
| `OFFSETX_BACKUP_MAX_BYTES` | Defaults to 67108864 (64 MiB), shared by export and restore |
| Authentication | Existing strong API token or complete session-login settings |
| `OFFSETX_ALLOWED_HOSTS` | The public hostname(s), comma separated; unknown Host headers return 421 |
| `OFFSETX_DATABASE_URL` | Unset for this complete local recovery topology |

Temporary directories, missing mounts and durable paths outside the root are
refused. A second production web process cannot acquire the instance lease.
The container prepares only the mount root as root, then drops to UID/GID 10001
before starting the application. It works with a read-only root filesystem and
a writable `/tmp` mount. Installation uses `uv.lock`, including email/Postgres extras.

Example with an operator-provided strong token already in the environment:

```bash
docker build -t offcrm:wp1 .
docker volume create offcrm-data
docker run --name offcrm --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  -p 127.0.0.1:8766:8766 -v offcrm-data:/var/lib/offcrm \
  -e OFFSETX_PRODUCTION=1 -e OFFSETX_PERSISTENT_MOUNT=/var/lib/offcrm \
  -e OFFSETX_LOCAL_API_TOKEN offcrm:wp1
```

Terminate HTTPS at the deployment proxy. Do not scale this disk across web
instances. PostgreSQL-backed video and egress stores retain their backend tests;
a mixed local/remote workspace explicitly refuses local backup and restore
rather than presenting a partial image as complete recovery.

## What a backup contains

The encrypted archive inventories every regular file under the data root plus
the CRM database. Each entry declares its type, byte count and SHA-256. SQLite
stores are copied through SQLite's backup API and integrity-checked, including
committed WAL contents. The supported application opens all required stores at
startup so unused components cannot hide an unavailable database.

Included: CRM/sales/delivery/chat tables, AI context and recall, egress history,
image/video/distribution/trend stores, imported and generated assets, exports,
mail and post outboxes, provider/Notion/workspace settings, encrypted local keys,
automation state, browser state stored under this root, and the local unsubscribe
signing key. Known image/video path columns are relocated when the destination
folder changes; user text and prompts are never rewritten.

An automatically provisioned `local_api_token` is part of the workspace. Restore
activates that restored token immediately; failed restore reactivates the old
one. If you use this file-managed login, retrieve the restored token securely on
the application host and enter it through **Key** in the browser after reload. An explicit
environment API token and environment-managed session login keep their host's
configuration. Readiness also detects a missing or changed file-managed token.

Explicit exclusions: the rebuildable AI response cache and old `restore_safety/`
scratch files. SQLite WAL/SHM/journal sidecars are represented by the consistent
database snapshot, never copied as live sidecars. Symlinks and special files are
refused rather than following them outside the workspace.

Environment-managed credentials, session secrets, AWS SDK credentials, external
OAuth authorisations and OS secret stores are not filesystem data. Reconfigure
those on the recovery host. Export never claims to back up a remote provider or
an external database. Keep the downloaded encrypted archive off the live disk
and keep its passphrase separately; losing the passphrase makes it unrecoverable.

The 64 MiB limit covers the complete encrypted archive, not general file uploads.
ZIP writes are bounded before encryption. Multipart input is bounded before it
can be spooled without limit. Expansion is limited to 2 GiB total, 512 MiB per
member, 10,000 members and a 2 MiB manifest. Fernet authentication still uses
bounded in-memory buffers, so raising the archive cap requires reserving several
times that cap in RAM and enough disk for staging plus the previous generation.
The Blueprint's 2 GiB instance leaves room for the default limit and the app.

## Export and restore

Open **Settings → Encrypted backup**. Supply a passphrase of at least 12
characters and download the file. The app briefly drains requests and timers to
capture one consistent workspace. Ordinary requests receive 503 with retry
instructions during maintenance; another backup operation receives 409.

To restore, choose the archive, enter the passphrase and confirm replacement.
Authentication, size, archive paths, manifest membership, hashes and SQLite
integrity are checked before live services close. The runtime then:

1. Drains complete request lifetimes, including streaming/background responses,
   and awaits both automation timers. A drain exceeding 60 seconds is refused.
2. Acquires the exclusive workspace lease. An active delivery worker causes a
   retryable refusal; the worker reopens its stores each cycle under a shared lease.
3. Closes all database connections, including those created on other threads.
4. Writes a staged generation and a synced journal on the persistent filesystem.
5. Renames the old generation into recovery storage and installs the new one.
6. Recreates the same service graph used at startup and checks readiness.
7. Records the commit decision, removes recovery files and resumes the timers.

A service reopening failure restores the previous generation and checks it before
reopening traffic. If rollback itself cannot restore health, readiness stays red
and ordinary work remains blocked. The response tells the operator to retain
recovery files and inspect server logs. Logs record outcomes and component names,
not backup passphrases or raw archives. A disconnected browser cannot release
maintenance while a filesystem worker is still replacing data.

Schema-v1 archives remain readable. They contained only CRM and four settings
files, so restoring them preserves the current unrelated files and reports
`legacy_partial: true`. They cannot recover data that was never in that old format.
Schema-v2 restores replace the complete declared local workspace.

## Restart, interrupted restore and rollback

At startup, before preparing paths or opening any database, the runtime checks
`.local_data.restore-journal.json` beside the data directory. A pending restore
rolls back to the previous generation. A committed journal preserves the restored
generation and retries cleanup. The journal covers a crash between either rename
and before/after the commit record. Do not delete or hand-edit it.

For an ordinary restart, retain the disk/volume and replace only the application
container. `/health/ready` verifies the mounted root, writable durable directories,
required databases, the local signing key and current service bindings.
`/health/live` answers whether the process is running. It intentionally stays
available during recovery.

Before upgrading an existing installation, export a recovery copy and record the
current image digest. Copy all existing local state to the new mounted root while
all web processes, CLI jobs and workers are stopped; keep the original disk/copy.
Move Gmail files into the root and remove split database overrides only after
recovering any remote stores through their own database tools. Never silently
replace a PostgreSQL store with an empty SQLite store.

For a code rollback, stop the new process and run the recorded prior image on the
same persistent root. There is no application-table schema migration in WP1.
SQLite files and existing encrypted archives remain readable. If state also needs
rollback, use the WP1 recovery endpoint before reverting code; older versions do
not understand complete schema-v2 archives. Never use an ephemeral `/tmp` location
as a rollback target. Restart/kill and rollback failure scenarios are exercised
in `tests/test_wp1_recovery_edges.py` and the actual container test below.

## Evidence and audit scope

The release gate is `.github/workflows/wp1-verification.yml`. It builds the actual
production image, runs every Python test with real PostgreSQL/Chrome/Docker,
runs all frontend tests/build, drives backup/download/restore in Chromium and
kills/recreates the production container against the same volume. It rejects
skipped or missing test evidence and uploads logs, screenshots and JUnit results.

`verification/test_live.py` retains the original audit assertions. The unrelated
sandbox, form-confirmation, connector, selection and media defects remain tracked
by their original audit findings; WP1 does not weaken those assertions or claim
to close them. The [WP1 closure record](../audits/2026-09-08-wp1-completion.md) certifies
A01, A02, A03, A04 and A17 against the integrated acceptance run. Production account/deployment verification remains separate
from the disposable, real-service acceptance environment.

Native Windows development uses shared/exclusive byte-range leases through
[LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex)
so normal dashboard requests may overlap. The WP1 workflow checks cross-process
lease exclusion and release on Windows as well as Linux; the production-container
acceptance environment remains Linux.
