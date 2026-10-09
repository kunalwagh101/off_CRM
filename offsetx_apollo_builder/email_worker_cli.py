from __future__ import annotations
from .observability import failure_message, failure_scope, traced_command

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .api.config import AppSettings
from .db import DatabaseBusy, DatabaseError, DatabaseUnavailable, resolve_target
from .db.hosted import HostedStorageError
from .outreach.store import names_a_url
from .outreach.store_copy import refuse_a_hidden_local_crm
from .outreach.deliverability.models import PermanentDeliveryError
from .outreach.deliverability.service import EmailDeliveryService
from .outreach.deliverability.ses import SesMailProvider
from .outreach.deliverability.store import DeliverabilityStore
from .outreach.deliverability.unsubscribe import UnsubscribeService
from .outreach.backup import restore_pending
from .outreach.engine import OutreachEngine
from .outreach.workspace_lock import WorkspaceBusy, WorkspaceLock
from .outreach.gmail import LocalOutboxProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offsetx-email-worker",
        description="Process off_CRM's durable email delivery jobs.",
    )
    # A string, not a Path: Path folds `postgresql://` to `postgresql:/`, and
    # the URL this help offers ended in a traceback.
    parser.add_argument(
        "--database",
        help="A SQLite path or postgresql:// URL; overrides OFFSETX_DATABASE_URL and OFFSETX_OUTREACH_DB",
    )
    parser.add_argument("--data-dir", type=Path, help="Override OFFSETX_DATA_DIR")
    parser.add_argument("--max-jobs", type=int, default=25)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling. Without this flag exactly one bounded cycle runs.",
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser


def _service(settings: AppSettings, engine: OutreachEngine) -> EmailDeliveryService:
    delivery_store = DeliverabilityStore(engine.store)
    unsubscribe = UnsubscribeService.from_path(
        delivery_store,
        settings.data_dir / "email_unsubscribe.key",
        public_base_url=settings.public_base_url,
        configured_secret=settings.unsubscribe_secret,
    )

    def provider(job: dict[str, Any], identity: dict[str, Any] | None) -> Any:
        if job["provider_type"] == "local":
            return LocalOutboxProvider(settings.data_dir / "mail")
        if job["provider_type"] == "ses":
            if not identity:
                raise PermanentDeliveryError("Amazon SES requires a sending identity")
            return SesMailProvider(
                region=str(identity["aws_region"]),
                configuration_set=str(identity["configuration_set"]),
            )
        raise PermanentDeliveryError(
            "The durable worker supports local and SES jobs. Use confirmed Gmail sending for small outreach."
        )

    return EmailDeliveryService(
        engine,
        unsubscribe=unsubscribe,
        provider_factory=provider,
    )


@traced_command("offsetx-email-worker")
def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.max_jobs <= 500:
        raise SystemExit("--max-jobs must be between 1 and 500")
    if args.poll_seconds < 0.25:
        raise SystemExit("--poll-seconds must be at least 0.25")
    settings = AppSettings.from_env()
    if args.database and not names_a_url(args.database):
        args.database = settings.database_path = Path(args.database).resolve()
    if args.data_dir:
        settings.data_dir = args.data_dir.resolve()
    settings.validate()
    failures = 0
    try:
        while True:
            with failure_scope():
                try:
                    # Reopen each cycle after taking the shared lease, so a worker
                    # never keeps a connection to the old generation after a
                    # restore swaps the workspace (S-06.02.21).
                    with WorkspaceLock(settings.data_dir):
                        # Checked under the lease: a restore writes its journal while
                        # holding the exclusive one, so this cannot race it. A journal
                        # seen here is a half-restored workspace nobody has rolled
                        # back yet — the web app's start-up does that (D-129).
                        if restore_pending(settings.data_dir):
                            raise WorkspaceBusy("restore pending")
                        settings.prepare()
                        # The CRM the web app opens: `--database`, then
                        # OFFSETX_DATABASE_URL, then the file. Reopening only the
                        # file sent nothing once the CRM was in the database.
                        crm = resolve_target(args.database, default=settings.database_path)
                        if not args.database:
                            # Not while a local CRM file holds the owner's rows: it
                            # would work the database's CRM and leave theirs unsent.
                            try:
                                refuse_a_hidden_local_crm(crm, settings.database_path, settings.secrets_key)
                            except HostedStorageError as exc:
                                raise SystemExit(failure_message(exc, operation="email.worker.cycle", data_dir=settings.data_dir)) from exc
                        engine = OutreachEngine(crm)
                        try:
                            result = _service(settings, engine).work_once(max_jobs=args.max_jobs)
                        finally:
                            engine.close()
                        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
                        failures = 0
                except (DatabaseUnavailable, DatabaseBusy) as exc:
                    # Away for a moment — a sleeping Neon compute, a dropped
                    # connection, a busy writer — ended a watching worker and mail
                    # stopped until someone restarted it (review finding 4). A
                    # setting that is wrong is a DatabaseError of another kind, and
                    # still stops it: retrying would only hide it.
                    if not args.watch:
                        raise SystemExit(failure_message(exc, operation="email.worker.cycle", data_dir=settings.data_dir)) from exc
                    failures += 1
                    wait = min(args.poll_seconds * 2 ** failures, 60.0)
                    print(f"{failure_message(exc, operation='email.worker.cycle', data_dir=settings.data_dir)} Trying again in {wait:g} s.", file=sys.stderr, flush=True)
                    time.sleep(wait)
                    continue
                except DatabaseError as exc:
                    # A target that is wrong, not away: say so and stop, rather than
                    # a traceback, or a retry that would only hide it.
                    raise SystemExit(failure_message(exc, operation="email.worker.cycle", data_dir=settings.data_dir)) from exc
                except WorkspaceBusy:
                    if not args.watch:
                        raise SystemExit(
                            "A backup restore is in progress or waiting to be rolled back. Start "
                            "the web app if it is stopped, and retry the worker once its "
                            "readiness check passes."
                        )
            if not args.watch:
                return 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
