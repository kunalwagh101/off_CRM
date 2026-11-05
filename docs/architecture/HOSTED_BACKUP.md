# F-06.03 / S-06.03.04 — encrypted offsite PostgreSQL backups

## Contract

A database snapshot is exported under a PostgreSQL repeatable-read snapshot,
encrypted with a separate AES-256-GCM key, and uploaded to an owner-controlled
private S3-compatible bucket. The uploaded object contains ciphertext only.
The uploader verifies object length and checksum after upload. An incomplete
upload never becomes a verified recovery point. Object keys contain UTC time
and a random suffix, so one run does not overwrite another.

This does not back up local image/video files, meeting artifacts or mail outboxes.
S-06.03.06 must give those a durable home before the install is production ready.

## Operator prerequisites

Configure a separate private S3-compatible bucket and scoped credentials. Grant
the backup identity PutObject/GetObject for the backup prefix, plus the minimum
bucket metadata permissions its provider requires. Do not grant DeleteObject.
Use private bucket access, versioning and an explicit lifecycle/retention rule.
Keep the backup key separately in a password manager or managed secrets service.
Do not reuse OFFSETX_SECRETS_KEY. This code cannot create a bucket or credentials.

Runtime prerequisites: the official PostgreSQL client (pg_dump, pg_restore),
the postgres dependency extra (psycopg), and the existing email extra (boto3).
The Dockerfile now installs the PostgreSQL client and the locked runtime
already includes both extras.

## First backup

Create a separate key on a trusted machine:

    uv run offsetx-db new-backup-key

Save it outside the database, application data directory and ephemeral storage.
Set these variables in the backup operator environment:

    OFFSETX_DATABASE_URL=<source PostgreSQL URL>
    OFFSETX_BACKUP_KEY=<independent generated key>
    OFFSETX_BACKUP_S3_BUCKET=<private owner-approved bucket>
    OFFSETX_BACKUP_S3_PREFIX=offcrm/nightly

Use scoped AWS credentials or a provider role for the backup process.
Do not print the database connection URL or any key in application logs.

Run:

    uv run offsetx-db backup-hosted

The command prints the remote ciphertext key, SHA-256 and table count. It
does not claim a scheduled job or a tested restore. The operator must configure
one external nightly scheduler with missed-backup alerting. Never schedule a
backup from every web instance or provision paid resources without approval.

## Recovery drill, without production overwrite

Download ciphertext to a NEW local file:

    uv run offsetx-db download-hosted --object-key "<key from export>" --output /private/backup.offcrm.enc

Create a separate, NEW EMPTY PostgreSQL database. Do not use the primary
database, a running application's schema or the same source under a different
connection-string spelling. Set:

    OFFSETX_RESTORE_DATABASE_URL=<new empty PostgreSQL URL>
    OFFSETX_BACKUP_KEY=<independent key used for export>

Then run:

    uv run offsetx-db restore-hosted --file /private/backup.offcrm.enc --yes-empty-target

The restore decrypts and verifies the whole ciphertext before invoking
pg_restore. It refuses a database with application tables, executes the restore
in one transaction, and reconciles exact row counts from the export snapshot.
It never switches production connection settings. The plaintext restore spool
is deleted on exit.

Verify login, provider-key decryptability, workspace access control and health
on the restored disposable app. Row counts alone are not full recovery proof.

## Failure behaviour and rollback

Invalid keys, tampering, missing tools, failed export, S3 checksum mismatch and
failed restore exit with an error. The normal secret-safe failure reference is
recorded. A failed recovery requires discarding the target, not rerunning
against partial data. Never delete good historical backups on rollback.
Keep independent decryption keys until every encrypted backup using them
has expired and a newer verified restore point is available.

## Release gates still open

- Owner-supplied bucket, restricted IAM identity, remote access and key custody.
- Independent nightly schedule, retention lifecycle and missed-backup alert.
- Real PostgreSQL plus remote-bucket restore after process destruction.
- Full repository regression, independent security and Render acceptance.
- Durable file and outbox storage for the remaining S-06.03.06 stores.

Do not mark S-06.03.04 DONE or enable production from source code alone.
