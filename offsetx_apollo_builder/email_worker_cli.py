from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .api.config import AppSettings
from .outreach.deliverability.models import PermanentDeliveryError
from .outreach.deliverability.service import EmailDeliveryService
from .outreach.deliverability.ses import SesMailProvider
from .outreach.deliverability.store import DeliverabilityStore
from .outreach.deliverability.unsubscribe import UnsubscribeService
from .outreach.engine import OutreachEngine
from .outreach.gmail import LocalOutboxProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offsetx-email-worker",
        description="Process off_CRM's durable email delivery jobs.",
    )
    parser.add_argument("--database", type=Path, help="Override OFFSETX_OUTREACH_DB")
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.max_jobs <= 500:
        raise SystemExit("--max-jobs must be between 1 and 500")
    if args.poll_seconds < 0.25:
        raise SystemExit("--poll-seconds must be at least 0.25")
    settings = AppSettings.from_env()
    if args.database:
        settings.database_path = args.database.resolve()
    if args.data_dir:
        settings.data_dir = args.data_dir.resolve()
    settings.prepare()
    engine = OutreachEngine(settings.database_path)
    service = _service(settings, engine)
    try:
        while True:
            result = service.work_once(max_jobs=args.max_jobs)
            print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
            if not args.watch:
                return 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 130
    finally:
        engine.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
