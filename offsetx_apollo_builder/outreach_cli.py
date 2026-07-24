from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .off_ai.broker import EgressBroker
from .off_ai.store import OffAIStore
from .outreach.engine import OutreachEngine
from .outreach.gmail import (
    GmailMailProvider,
    LocalOutboxProvider,
    authorize_interactive,
)
from .outreach.models import MESSAGE_STAGES
from .outreach.provider_profiles import ProviderProfileStore


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OFF_CRM local outreach CRM")
    parser.add_argument(
        "--db",
        default=_env("OFF_CRM_DB", "OFFSETX_OUTREACH_DB", default="local_data/off_crm.db"),
        help="Local SQLite database path",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-campaign")
    create.add_argument("name")
    create.add_argument("--daily-limit", type=int, default=25)
    create.add_argument("--timezone", default="Asia/Kolkata")

    listing = sub.add_parser("list-campaigns")
    listing.add_argument("--status", default="")

    import_contacts = sub.add_parser("import-contacts")
    import_contacts.add_argument("campaign_id")
    import_contacts.add_argument("file", type=Path)
    import_contacts.add_argument(
        "--default-category", default="Sustainability / ESG / Climate"
    )

    generate = sub.add_parser("generate")
    generate.add_argument("campaign_id")
    generate.add_argument("--stages", nargs="+", choices=MESSAGE_STAGES, default=list(MESSAGE_STAGES))
    generate.add_argument(
        "--provider-profile",
        default="",
        help="Classified provider profile ID from Connectors",
    )
    generate.add_argument(
        "--provider-config",
        type=Path,
        help=argparse.SUPPRESS,
    )

    drafts = sub.add_parser("list-drafts")
    drafts.add_argument("campaign_id")
    drafts.add_argument("--status", default="")

    approve = sub.add_parser("approve")
    approve.add_argument("campaign_id")
    approve.add_argument("--draft-id", action="append", default=[])
    approve.add_argument("--stage", action="append", choices=MESSAGE_STAGES, default=[])

    send = sub.add_parser("send")
    send.add_argument("campaign_id")
    send.add_argument("--mode", choices=("local", "gmail"), default="local")
    send.add_argument("--max-messages", type=int)
    send.add_argument("--confirm", default="")

    export = sub.add_parser("export")
    export.add_argument("campaign_id")
    export.add_argument("destination", type=Path)

    auth = sub.add_parser("gmail-authorize")
    auth.add_argument("--client-secrets", type=Path)
    auth.add_argument("--token", type=Path)
    auth.add_argument("--no-browser", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("campaign_id", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    if args.command == "gmail-authorize":
        client = args.client_secrets or Path(
            _env(
                "OFF_CRM_GMAIL_CLIENT_SECRETS",
                "OFFSETX_GMAIL_CLIENT_SECRETS",
                default="gmail_client_secret.json",
            )
        )
        token = args.token or Path(
            _env(
                "OFF_CRM_GMAIL_TOKEN",
                "OFFSETX_GMAIL_TOKEN",
                default="local_data/gmail_token.json",
            )
        )
        authorize_interactive(
            client_secrets_path=client,
            token_path=token,
            open_browser=not args.no_browser,
        )
        _json({"connected": True, "token_path": str(token)})
        return 0

    engine = OutreachEngine(Path(args.db))
    try:
        if args.command == "create-campaign":
            campaign_id = engine.create_campaign(
                name=args.name,
                daily_send_limit=args.daily_limit,
                timezone_name=args.timezone,
            )
            _json(engine.store.get_campaign(campaign_id))
        elif args.command == "list-campaigns":
            items, total = engine.store.list_campaigns(status=args.status)
            _json({"items": items, "total": total})
        elif args.command == "import-contacts":
            _json(
                engine.import_contacts(
                    args.campaign_id,
                    args.file,
                    default_category=args.default_category,
                )
            )
        elif args.command == "generate":
            if args.provider_config:
                raise SystemExit(
                    "Direct provider config files are disabled. Add and classify the "
                    "provider under Connectors, then pass --provider-profile ID."
                )
            provider = None
            ai_store = None
            if args.provider_profile:
                data_dir = Path(args.db).resolve().parent
                ai_store = OffAIStore(Path(args.db))
                ai_store.initialize()
                broker = EgressBroker(
                    store=ai_store,
                    profiles=ProviderProfileStore(data_dir),
                    owner_domains=(
                        item.strip()
                        for item in (
                            _env("OFF_CRM_OWNER_DOMAINS", "OFFSETX_OWNER_DOMAINS")
                        ).split(",")
                        if item.strip()
                    ),
                )
                provider = broker.email_provider(
                    profile_ids=[args.provider_profile],
                    sender_positioning=(
                        _env(
                            "OFF_CRM_PUBLIC_POSITIONING",
                            "OFFSETX_PUBLIC_POSITIONING",
                        )
                    ).strip(),
                )
            try:
                _json(
                    engine.generate_drafts(
                        args.campaign_id, stages=args.stages, provider=provider
                    )
                )
            finally:
                if ai_store is not None:
                    ai_store.close()
        elif args.command == "list-drafts":
            items, total = engine.store.list_drafts(
                args.campaign_id, approval_status=args.status
            )
            _json({"items": items, "total": total})
        elif args.command == "approve":
            if not args.draft_id and not args.stage:
                raise SystemExit("Choose --draft-id or --stage")
            _json(
                engine.approve_drafts(
                    args.campaign_id, draft_ids=args.draft_id, stages=args.stage
                )
            )
        elif args.command == "send":
            own_email = _env("OFF_CRM_OWN_EMAIL", "OFFSETX_OWN_EMAIL").strip().lower()
            if args.mode == "gmail":
                if args.confirm != "SEND LIVE EMAILS":
                    raise SystemExit("Gmail requires: --confirm \"SEND LIVE EMAILS\"")
                client = _env(
                    "OFF_CRM_GMAIL_CLIENT_SECRETS",
                    "OFFSETX_GMAIL_CLIENT_SECRETS",
                ).strip()
                token = _env(
                    "OFF_CRM_GMAIL_TOKEN",
                    "OFFSETX_GMAIL_TOKEN",
                    default="local_data/gmail_token.json",
                ).strip()
                if not client or not own_email:
                    raise SystemExit(
                        "Set OFF_CRM_GMAIL_CLIENT_SECRETS and OFF_CRM_OWN_EMAIL"
                    )
                mail = GmailMailProvider(client_secrets_path=client, token_path=token)
            else:
                mail = LocalOutboxProvider(Path(args.db).parent / "mail")
            _json(
                engine.run_due(
                    args.campaign_id,
                    mail_provider=mail,
                    own_email=own_email,
                    max_messages=args.max_messages,
                )
            )
        elif args.command == "export":
            _json({"path": str(engine.export_crm(args.campaign_id, args.destination))})
        elif args.command == "status":
            _json(
                engine.store.campaign_summary(args.campaign_id)
                if args.campaign_id
                else engine.store.dashboard_summary()
            )
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
