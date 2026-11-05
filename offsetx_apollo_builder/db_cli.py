"""``offsetx-db`` — check the database backend and move the egress log.

Usage::

    offsetx-db check                                  # what would be opened, and can it be reached
    offsetx-db check --target postgresql://…
    offsetx-db copy-log --from <data dir>/ai_egress.db --to postgresql://…
    offsetx-db inventory                              # every store, where it lives, its size here
    offsetx-db new-secrets-key                        # the key for provider keys in a hosted database
    offsetx-db forget-provider-keys --yes             # a lost key: clear the stored keys to start again
    offsetx-db import-local --yes | --skip            # a data folder's keys and logins: copy in, or leave

The data directory is ``OFFSETX_DATA_DIR``, or ``local_data`` when it is unset.

off_CRM is SQLite-first and stays that way for one owner on one machine.
Postgres is for the case SQLite cannot serve: a deployment whose disk does not
survive a restart, or more than one process writing.
"""

from __future__ import annotations
from .observability import failure_message, report_failure, traced_command

import argparse
import os
import sys
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from cryptography.fernet import Fernet

from .ai.log import copy_egress_log
from .data_paths import data_dir, database_path, load_project_env
from .db import (
    DATABASE_URL_ENV,
    DatabaseError,
    describe_target,
    inventory,
    open_database,
    resolve_target,
)
from .db.connection import is_postgres_url
from .db.hosted import SECRETS_KEY_ENV, HostedStorage
from .outreach.workspace_lock import cli_workspace_lease, cli_workspace_leases


def _lease(*targets: object) -> AbstractContextManager[None]:
    """The workspace lease when any target is a file a restore swaps (D-134):
    one inside the data directory, or the CRM database, which a backup covers
    wherever it lives.

    Only then: a Postgres URL, or a SQLite copy kept elsewhere, is not part of
    the workspace, and checking one is what an operator does while a restore
    is stuck.
    """
    workspace = data_dir(Path.cwd())
    files = [Path(str(target)).resolve() for target in targets
             if target and not is_postgres_url(target)]
    if not files:
        return nullcontext()
    needs_default = any(path.is_relative_to(workspace) or path == database_path()
                        for path in files)
    return cli_workspace_leases(*files, workspace=workspace if needs_default else None)


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        target = resolve_target(args.target or None, default=args.default or None)
    except DatabaseError as exc:
        report_failure(exc, operation="offsetx-db")
        print("Reachable: no", file=sys.stderr)
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2

    print(f"Target  : {describe_target(target)}")
    with _lease(target):
        return _check(target, args)


def _check(target: str, args: argparse.Namespace) -> int:
    try:
        database = open_database(target)
    except DatabaseError as exc:
        report_failure(exc, operation="offsetx-db")
        print("Reachable: no", file=sys.stderr)
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    try:
        database.execute("SELECT 1")
        print(f"Backend : {database.name}")
        print("Reachable: yes")
        row = database.execute(
            "SELECT COUNT(*) AS total FROM ai_egress_log"
        ).fetchone()
        print(f"Egress log: {int(row['total'])} row(s)")
    except Exception as exc:  # noqa: BLE001 - the table may simply not exist yet
        print("Egress log: not initialised here yet")
        if args.verbose:
            print("  Create the store before checking its egress log.")
    finally:
        database.close()
    return 0


def _cmd_copy_log(args: argparse.Namespace) -> int:
    try:
        with _lease(args.source, args.destination):
            result = copy_egress_log(args.source, args.destination)
    except DatabaseError as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2

    print(f"From : {result.source}")
    print(f"To   : {result.destination}")
    print(result.summary())
    if not result.ok:
        print(
            "Row counts do not reconcile. The source was not modified; "
            "investigate before switching over.",
            file=sys.stderr,
        )
        return 2
    print()
    # Named, never repeated: the URL may carry a password, and this lands in
    # terminals and CI logs (D-225).
    print(f"The SQLite file was not modified. To switch over, set {DATABASE_URL_ENV} to the URL")
    print("passed with --to, and restart. To go back, unset it.")
    return 0


def _cmd_copy_crm(args: argparse.Namespace) -> int:
    """Copy a whole CRM into an empty one, either way (S-06.03.03): a local file
    into the database, or the database back to a file."""
    from .outreach.store_copy import CrmCopyError, copy_crm

    if not is_postgres_url(args.destination) and Path(args.destination).exists():
        # A file already there may be another store's: the CRM's tables went
        # into one and this said it had worked (review finding 9).
        print(
            f"{args.destination} already exists. Copy a CRM into a new file, or into an empty "
            "PostgreSQL database; nothing was copied.",
            file=sys.stderr,
        )
        return 2
    try:
        with _lease(args.source, args.destination):
            report = copy_crm(args.source, args.destination)
    except (CrmCopyError, DatabaseError) as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    print(report.describe())
    if not report.ok:
        print(
            "Row counts do not reconcile. The source was not modified; investigate before "
            "using the copy.",
            file=sys.stderr,
        )
        return 2
    print("Every table reconciles. The source was not modified.")
    return 0


def _size(count: int) -> str:
    if count < 1024:
        return f"{count} B"
    for unit in ("KB", "MB", "GB"):
        count /= 1024
        if count < 1024 or unit == "GB":
            return f"{count:.1f} {unit}"
    return f"{count:.1f} GB"  # pragma: no cover - the loop always returns


def _cmd_inventory(args: argparse.Namespace) -> int:
    """Every store, how it is kept, and what it holds on this install's disk.

    Read only, so it takes no lease: it is what an owner runs to see what a
    move to a hosted database involves, and what a free-plan deploy would wipe.
    """
    if args.markdown:
        print(inventory.markdown_table())
        return 0
    root = Path(args.data_dir) if args.data_dir else data_dir(Path.cwd())
    print(f"Data folder: {root}")
    width = max(len(thing.name) for thing in inventory.STORES)
    for thing, total in inventory.sizes(root):
        print(f"{thing.name.ljust(width)}  {_size(total).rjust(9)}  {thing.hosted}")
    return 0


def _cmd_new_secrets_key(args: argparse.Namespace) -> int:
    """Print a fresh key for the provider keys kept in a hosted database.

    Printed once and stored nowhere: the install owner sets it where the app's
    environment is set, and keeps a copy. Generated, never typed, so it cannot
    be a password someone could guess (`S-06.03.02`).
    """
    key = Fernet.generate_key().decode("ascii")
    print(f"Set {SECRETS_KEY_ENV} to this key, once, where the app's settings live")
    print("(on Render: the service's Environment page):")
    print()
    print(f"    {key}")
    print()
    print("Keep a copy somewhere safe, such as a password manager. It is stored nowhere")
    print("else, and without it nobody can read the provider keys saved in the database.")
    return 0


def _cmd_forget_provider_keys(args: argparse.Namespace) -> int:
    """The way back from a lost secrets key: clear the stored provider keys.

    Consequential — every workspace has to paste its keys again — so it does
    nothing without `--yes`. Settings, limits, trust and logins stay.
    """
    try:
        target = resolve_target(args.target or None, default="")
    except DatabaseError as exc:  # pragma: no cover - a default is always given
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    if not target:
        print(f"Set {DATABASE_URL_ENV}, or pass --target, to name the database.", file=sys.stderr)
        return 2
    if not args.yes:
        print(
            f"This clears every workspace's provider keys stored in {describe_target(target)}.\n"
            "Settings, limits, trust and logins stay; each workspace pastes its keys again\n"
            "in Connectors. Stop the app first, then run this again with --yes.",
            file=sys.stderr,
        )
        return 2
    storage = HostedStorage(target, None)
    try:
        with _lease(target):
            storage.forget_provider_keys()
    except DatabaseError as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    finally:
        storage.close()
    print(f"The stored provider keys in {describe_target(target)} are cleared.")
    print(f"Start the app with the new {SECRETS_KEY_ENV}, then paste each key in Connectors.")
    return 0



def _cmd_import_timers(args: argparse.Namespace) -> int:
    """Explicit archive-then-import/skip; not a background data migration."""
    from .db.hosted import HostedStorageError
    from .db.timer_import import TimerMigrationError, migrate_timers

    if args.yes == args.skip:
        print(
            "Choose --yes to import dormant timer settings or --skip to keep hosted "
            "settings. Stop the web app and worker before running the command.",
            file=sys.stderr,
        )
        return 2

    root = Path(args.data_dir) if args.data_dir else data_dir(Path.cwd())
    try:
        hosted = HostedStorage.configured(os.getenv(SECRETS_KEY_ENV, ""))
    except HostedStorageError as exc:
        report_failure(exc, operation="offsetx-db.import-timers")
        print(failure_message(exc, operation="offsetx-db.import-timers"), file=sys.stderr)
        return 2
    if hosted is None:
        print(f"Set {DATABASE_URL_ENV} and {SECRETS_KEY_ENV} first.", file=sys.stderr)
        return 2
    try:
        migrated = migrate_timers(
            hosted, root, Path(args.archive_dir), import_settings=args.yes
        )
    except (TimerMigrationError, HostedStorageError, DatabaseError, OSError, ValueError) as exc:
        report_failure(exc, operation="offsetx-db.import-timers")
        print(failure_message(exc, operation="offsetx-db.import-timers"), file=sys.stderr)
        return 2
    finally:
        hosted.close()

    print(f"Protected archive created for {len(migrated)} timer configuration file(s).")
    if args.yes:
        print("Imported with all automatic sending/posting disabled. Review and re-enable each plan explicitly.")
    else:
        print("Skipped old timer settings. Existing hosted configuration was not changed.")
    print("The old filenames were removed after backup and commit. Keep the archive on durable storage.")
    return 0


def _cmd_import_local(args: argparse.Namespace) -> int:
    """Say once what happens to a data folder's keys, settings and logins (D-210).

    `--yes` copies them into the hosted database; `--skip` keeps the database
    as it is. The files are left untouched either way.
    """
    from .ai.errors import RegistryError
    from .db.hosted import HostedStorageError
    from .hosted_import import import_local, skip_local

    if args.yes == args.skip:
        print(
            "Choose one: --yes copies the data folder's keys, settings, counters and logins into "
            "the database; --skip keeps the database as it is. The files stay where they are "
            "either way.",
            file=sys.stderr,
        )
        return 2
    root = Path(args.data_dir) if args.data_dir else data_dir(Path.cwd())
    try:
        hosted = HostedStorage.configured(os.getenv(SECRETS_KEY_ENV, ""))
    except HostedStorageError as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    if hosted is None:
        print(f"Set {DATABASE_URL_ENV} and {SECRETS_KEY_ENV} first: they name the database.", file=sys.stderr)
        return 2
    try:
        with cli_workspace_lease(root):
            hosted.check_secrets_key()
            names = import_local(hosted, root) if args.yes else skip_local(hosted, root)
    except (HostedStorageError, RegistryError, DatabaseError) as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    finally:
        hosted.close()
    listed = ", ".join(names) if names else "nothing"
    if args.yes:
        print(f"Copied into {describe_target(hosted.target)}: {listed}. The files are untouched.")
    else:
        print(f"The database stays as it is; {listed} stay in {root}, unread.")
    if (root / "ai_egress.db").is_file():
        print(f"The egress log has its own copy: offsetx-db copy-log --from {root / 'ai_egress.db'} "
              f"--to \"${DATABASE_URL_ENV}\"")
    return 0


def _cmd_import_context(args: argparse.Namespace) -> int:
    """Archive SQLite AI history, then explicitly import or skip."""
    from .db.context_import import ContextImportError, import_context
    from .db.hosted import HostedStorageError

    if args.yes == args.skip:
        print("Choose --yes or --skip for AI context migration.", file=sys.stderr)
        return 2
    source = Path(args.source) if args.source else data_dir(Path.cwd()) / "ai_context.db"
    try:
        hosted = HostedStorage.configured(os.getenv(SECRETS_KEY_ENV, ""))
        if hosted is None:
            print(f"Set {DATABASE_URL_ENV} and {SECRETS_KEY_ENV} first.", file=sys.stderr)
            return 2
        try:
            hosted.check_secrets_key()
            counts = import_context(
                source, hosted.target, Path(args.archive), skip=args.skip
            )
        finally:
            hosted.close()
    except (ContextImportError, HostedStorageError, DatabaseError, OSError, ValueError) as exc:
        report_failure(exc, operation="offsetx-db.import-context")
        print(failure_message(exc, operation="offsetx-db.import-context"), file=sys.stderr)
        return 2

    print(f"Preserved private AI context backup; {counts['ai_task_state']} tasks and "
          f"{counts['ai_template_stats']} template records.")
    if args.yes:
        print("Imported into hosted context; original local file removed after verification.")
    else:
        print("Skipped importing; existing hosted context remains unchanged.")
    print("Retain the archive on a genuinely durable, private disk.")
    return 0


def _cmd_import_crm(args: argparse.Namespace) -> int:
    """Say once what happens to a local CRM file (S-06.03.03), as `import-local`
    does for keys and logins: copied into the database's CRM, or left unread."""
    from .db.hosted import HostedStorageError
    from .outreach.store_copy import CrmCopyError, import_crm, skip_crm

    if args.yes == args.skip:
        print(
            "Choose one: --yes copies the CRM file into the database's CRM; --skip starts on "
            "the database's CRM as it is. The file stays where it is either way.",
            file=sys.stderr,
        )
        return 2
    crm_file = Path(args.database).resolve() if args.database else database_path(Path.cwd())
    try:
        hosted = HostedStorage.configured(os.getenv(SECRETS_KEY_ENV, ""))
    except HostedStorageError as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    if hosted is None:
        print(f"Set {DATABASE_URL_ENV} and {SECRETS_KEY_ENV} first: they name the database.", file=sys.stderr)
        return 2
    try:
        with cli_workspace_leases(crm_file, workspace=data_dir(Path.cwd())):
            hosted.check_secrets_key()
            if args.yes:
                report = import_crm(hosted, crm_file, hosted.target)
            else:
                rows = skip_crm(hosted, crm_file)
    except (HostedStorageError, CrmCopyError, DatabaseError) as exc:
        report_failure(exc, operation="offsetx-db")
        print(failure_message(exc, operation="offsetx-db"), file=sys.stderr)
        return 2
    finally:
        hosted.close()
    if args.yes:
        print(report.describe())
        print(f"Copied into {describe_target(hosted.target)}. The file is untouched.")
    else:
        print(f"The database's CRM stays as it is; {rows} rows stay in {crm_file}, unread.")
    return 0


def _cmd_new_backup_key(args: argparse.Namespace) -> int:
    from .db.hosted_backup import BACKUP_KEY_ENV, new_backup_key

    print(f"Set {BACKUP_KEY_ENV} on the backup/recovery operator only:")
    print()
    print(new_backup_key())
    print()
    print("Save this in an independent password manager or KMS. Losing it means losing")
    print("access to backups; never use OFFSETX_SECRETS_KEY as the backup key.")
    return 0


def _cmd_backup_hosted(args: argparse.Namespace) -> int:
    """Encrypt a consistent PostgreSQL snapshot before an S3 transfer."""
    from .db.hosted_backup import HostedBackupError, export_to_s3

    database_url = os.getenv(DATABASE_URL_ENV, "")
    if not is_postgres_url(database_url):
        print(f"Set {DATABASE_URL_ENV} to the source PostgreSQL URL first.", file=sys.stderr)
        return 2
    try:
        output = export_to_s3(database_url, bucket=args.bucket or None,
                              prefix=args.prefix or None)
    except Exception as exc:  # noqa: BLE001 - operator command needs a trace reference
        report_failure(exc, operation="offsetx-db.backup-hosted")
        print(failure_message(exc, operation="offsetx-db.backup-hosted"), file=sys.stderr)
        return 2
    print(f"Encrypted backup verified outside the database: s3://{output['bucket']}/{output['key']}")
    print(f"SHA-256: {output['sha256']}; tables: {output['tables']}")
    return 0


def _cmd_download_hosted(args: argparse.Namespace) -> int:
    from .db.hosted_backup import HostedBackupError, download_ciphertext

    try:
        saved = download_ciphertext(args.object_key, Path(args.output),
                                   bucket=args.bucket or None)
    except Exception as exc:  # noqa: BLE001 - no customer data changed
        report_failure(exc, operation="offsetx-db.download-hosted")
        print(failure_message(exc, operation="offsetx-db.download-hosted"), file=sys.stderr)
        return 2
    print(f"Verified encrypted backup saved to: {saved}")
    print("This file is ciphertext. Keep its separate decryption key safe.")
    return 0


def _cmd_restore_hosted(args: argparse.Namespace) -> int:
    from .db.hosted_backup import HostedBackupError, restore_to_empty_postgres

    target = os.getenv("OFFSETX_RESTORE_DATABASE_URL", "")
    if not args.yes_empty_target or not is_postgres_url(target):
        print(
            "Set OFFSETX_RESTORE_DATABASE_URL to a NEW EMPTY PostgreSQL database, "
            "stop its application and pass --yes-empty-target. "
            "Never restore over the live source.",
            file=sys.stderr,
        )
        return 2
    if target == os.getenv(DATABASE_URL_ENV, ""):
        print("Restore refused: source and destination are the same database.", file=sys.stderr)
        return 2
    try:
        counts = restore_to_empty_postgres(Path(args.file), target)
    except Exception as exc:  # noqa: BLE001 - no customer data changed
        report_failure(exc, operation="offsetx-db.restore-hosted")
        print(failure_message(exc, operation="offsetx-db.restore-hosted"), file=sys.stderr)
        return 2
    print(f"Restored into a new database; all {len(counts)} table counts reconciled.")
    print("Run service-specific health and auth checks before any cutover.")
    return 0


@traced_command("offsetx-db")
def main(argv: list[str] | None = None) -> int:
    load_project_env()
    parser = argparse.ArgumentParser(
        prog="offsetx-db",
        description="Inspect the database backend, list the stores and move the egress log.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="show the target and whether it can be reached")
    check.add_argument("--target", default="", help="path or postgresql:// URL")
    check.add_argument(
        "--default",
        default=str(data_dir(Path.cwd()) / "ai_egress.db"),
        help="fallback used when no target and no environment variable is set",
    )
    check.add_argument("--verbose", action="store_true")
    check.set_defaults(func=_cmd_check)

    copy = sub.add_parser("copy-log", help="copy the egress log into Postgres")
    copy.add_argument("--from", dest="source", required=True, help="SQLite file to read")
    copy.add_argument(
        "--to", dest="destination", required=True, help="postgresql:// URL to write"
    )
    copy.set_defaults(func=_cmd_copy_log)

    crm_copy = sub.add_parser(
        "copy-crm", help="copy a whole CRM into an empty one: a file into the database, or back"
    )
    crm_copy.add_argument(
        "--from", dest="source", required=True, help="the CRM to read: a SQLite path or postgresql:// URL"
    )
    crm_copy.add_argument(
        "--to", dest="destination", required=True, help="an empty CRM to write: a SQLite path or URL"
    )
    crm_copy.set_defaults(func=_cmd_copy_crm)

    stores = sub.add_parser("inventory", help="every store, where it lives and its size here")
    stores.add_argument("--data-dir", default="", help="the data folder to measure")
    stores.add_argument("--markdown", action="store_true", help="print the design document's table")
    stores.set_defaults(func=_cmd_inventory)

    fresh = sub.add_parser("new-secrets-key", help=f"print a new {SECRETS_KEY_ENV}")
    fresh.set_defaults(func=_cmd_new_secrets_key)

    forget = sub.add_parser(
        "forget-provider-keys", help="clear the stored provider keys after a lost secrets key"
    )
    forget.add_argument("--target", default="", help=f"postgresql:// URL; defaults to {DATABASE_URL_ENV}")
    forget.add_argument("--yes", action="store_true", help="really clear them")
    forget.set_defaults(func=_cmd_forget_provider_keys)

    move = sub.add_parser(
        "import-local", help="copy a data folder's keys, settings and logins into the database, or skip"
    )
    move.add_argument("--data-dir", default="", help="the data folder; defaults to OFFSETX_DATA_DIR")
    choice = move.add_mutually_exclusive_group()
    choice.add_argument("--yes", action="store_true", help="copy them in")
    choice.add_argument("--skip", action="store_true", help="keep the database as it is")
    move.set_defaults(func=_cmd_import_local)

    timers = sub.add_parser(
        "import-timers",
        help="archive legacy timer JSON, then import disabled settings or skip them",
    )
    timers.add_argument("--data-dir", default="", help="legacy data folder")
    timers.add_argument(
        "--archive-dir", required=True,
        help="PRIVATE durable directory outside the old data folder; no existing data overwritten",
    )
    timer_choice = timers.add_mutually_exclusive_group()
    timer_choice.add_argument("--yes", action="store_true", help="copy timer settings, disabled")
    timer_choice.add_argument("--skip", action="store_true", help="keep hosted values")
    timers.set_defaults(func=_cmd_import_timers)

    context = sub.add_parser(
        "import-context", help="privately archive old AI task history, then explicitly import or skip"
    )
    context.add_argument("--source", default="", help="old ai_context.db; defaults to data folder")
    context.add_argument("--archive", required=True, help="private durable backup outside the data folder")
    context_choice = context.add_mutually_exclusive_group()
    context_choice.add_argument("--yes", action="store_true", help="import into an empty hosted context")
    context_choice.add_argument("--skip", action="store_true", help="keep the hosted context untouched")
    context.set_defaults(func=_cmd_import_context)

    crm = sub.add_parser(
        "import-crm", help="copy a local CRM file into the database's CRM, or start without it"
    )
    crm.add_argument("--database", default="", help="the CRM file; defaults to OFFSETX_OUTREACH_DB")
    crm_choice = crm.add_mutually_exclusive_group()
    crm_choice.add_argument("--yes", action="store_true", help="copy it in")
    crm_choice.add_argument("--skip", action="store_true", help="start on the database's CRM as it is")
    crm.set_defaults(func=_cmd_import_crm)

    new_backup = sub.add_parser("new-backup-key", help="generate an independent 256-bit backup key")
    new_backup.set_defaults(func=_cmd_new_backup_key)

    export = sub.add_parser(
        "backup-hosted", help="encrypt a consistent hosted PostgreSQL snapshot into private S3"
    )
    export.add_argument("--bucket", default="", help="private S3 bucket; else OFFSETX_BACKUP_S3_BUCKET")
    export.add_argument("--prefix", default="", help="S3 key prefix; else OFFSETX_BACKUP_S3_PREFIX")
    export.set_defaults(func=_cmd_backup_hosted)

    download = sub.add_parser(
        "download-hosted", help="download and verify ciphertext without decrypting it"
    )
    download.add_argument("--object-key", required=True, help="object key from backup-hosted")
    download.add_argument("--bucket", default="", help="private bucket; else OFFSETX_BACKUP_S3_BUCKET")
    download.add_argument("--output", required=True, help="new private file, never an existing path")
    download.set_defaults(func=_cmd_download_hosted)

    restore = sub.add_parser(
        "restore-hosted", help="restore a downloaded ciphertext backup into a NEW empty PostgreSQL DB"
    )
    restore.add_argument("--file", required=True, help="verified encrypted backup file")
    restore.add_argument("--yes-empty-target", action="store_true", help="confirm empty disposable target")
    restore.set_defaults(func=_cmd_restore_hosted)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
