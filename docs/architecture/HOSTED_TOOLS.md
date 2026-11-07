# Hosted tool registrations, receipts and companion grants

`ToolRegistry` uses the configured SQL target in the web runtime and in
`offsetx-tools`. PostgreSQL and explicit SQLite test targets preserve the same
workspace predicates, pinned recipes, disabled state and run receipts. Local
mode retains its existing SQLite registry. No provider calls or tool execution
occur during migration.

Hosted transports are cached per thread. Each context owns a real transaction
and commits or rolls back without closing the transport. Direct readiness reads
remain valid. Registry close reaches every thread's transport; its existing
generation protocol reopens the same durable target when needed. Short claims
serialize on304. Companion schema setup shares302 across both construction
styles; imports take302 before304. External Git/Docker work runs outside these
database transactions. Tool schema version2 widens PostgreSQL duration_ms to
BIGINT so existing SQLite64-bit history remains exact.

## Operator cutover

Stop app and worker processes. Preserve an independent verified database backup
and use the installation's existing database, master key and stable UUID. Keep
credentials in secure environment settings. Use private durable archive storage
outside the old data directory; the importer requires directory0700/file0600.
Archives are complete private SQLite snapshots. Offsite hosted backups are a
separate encrypted recovery path.

With `OLD_DATA` and `PRIVATE_ARCHIVE` set to the reviewed directories:

```sh
offsetx-db import-content --kind tools \
  --source "$OLD_DATA/ai_tools.db" \
  --archive "$PRIVATE_ARCHIVE/tools-before.sqlite" --yes
```

Enabled registrations require a separate `--reactivate-tools` flag. Alternatively,
disable them locally before importing. The flag retains eligibility for future
explicit tool runs; importing never executes a tool. Existing recipe validators
check executable fields before copying. Source/archive/target identity checks
reject path and inode aliases, unsupported schemas, mismatched install identity
and conflicting target rows. Exact reconciliation precedes clearing only the
local tool/run rows. Companion rows remain in the source and in the complete
first archive.

Then migrate profiles and procedures with a distinct archive:

```sh
offsetx-db import-companions \
  --source "$OLD_DATA/ai_tools.db" \
  --archive "$PRIVATE_ARCHIVE/profiles-before.sqlite" \
  --yes --accept-tool-grants
```

`--accept-tool-grants` is required only when profiles retain executable grants.
Every referenced tool must already exist in the same hosted workspace. Disabled
tools remain disabled. Missing/foreign grants refuse copying and retain the
source. Import retries reconcile exact target rows before cleanup. Do not reuse
the first archive path for the changed second-stage source.

Verify `offsetx-tools --workspace <workspace> list` and `runs`, the authenticated
companion catalogue, disabled state and profile grants. CLI disable/enable must
appear in the app immediately. Use disposable copies for folder-loss and
encrypted recovery drills. SQL placement does not preserve sandbox working
files, media, outboxes or other remaining file stores.

## Inverse and later changes

Stop actors, retain the hosted data and an independent current backup, and copy
the complete first private archive to a disposable local ai_tools.db. Reopen
the prior local registry/profile configuration and reconcile IDs, recipes,
disabled state, grants and run history. This inverse is exercised on disposable
copies in tests/test_hosted_tool_registry.py, including64-bit history. The
original archive stays unchanged.

If hosted permissions or data changed after cutover, reconcile those changes
before selecting an older archive. Restoring an older permission snapshot must
not silently undo a later revocation. No migration or rollback was run on real
customer records in this work.

## Actual execution and timeout recovery

The sandbox continues to require an explicitly provisioned local image, pinned
Git commit and public input. It uses no network, an unprivileged UID, read-only
root/inbox, no capabilities, no-new-privileges and no private-store/Docker-socket
mount. Hosted metadata does not enable Docker on unsupported hosts such as a
standard Render service.

Each invocation receives a fresh trusted random container name. A client timeout
explicitly removes only that container; killing the attached client alone does
not stop it. Cleanup calls are bounded. A confirmed stop records `timeout`.
An unavailable/failed cleanup records `timeout_cleanup_unknown`, retains the
owned name in its private receipt and directs the operator to inspect it before
rerunning. Metadata history reconstructs a fixed diagnostic from a strictly
validated identifier; imported arbitrary stderr is never printed as that
diagnostic. No automatic rerun follows an uncertain stop.

Process-crash journaling, restart reconciliation and full cancellation remain
broader lifecycle acceptance gates. This document does not establish complete
hosted storage or Agent team release readiness.
