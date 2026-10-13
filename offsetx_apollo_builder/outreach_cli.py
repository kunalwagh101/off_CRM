from __future__ import annotations
from .observability import failure_message, report_failure, traced_command

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .campaigns import CampaignKindError
from .campaigns import list_kinds as list_campaign_kinds
from .data_paths import crm_target, data_dir, database_path, gmail_token_path
from .db import is_postgres_url
from .outreach.engine import OutreachEngine
from .outreach.gmail import (
    GmailMailProvider,
    LocalOutboxProvider,
    authorize_interactive,
)
from .outreach.models import MESSAGE_STAGES
from .outreach.provider_profiles import create_guarded_provider
from .outreach.providers import load_provider_config
from .outreach.workspace_lock import cli_workspace_leases


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="off_CRM local outreach CRM")
    parser.add_argument(
        "--db",
        # No default here: one baked in hid OFFSETX_DATABASE_URL, and this tool
        # opened a local file while the web app's CRM was in the database.
        help="CRM to open: a SQLite path or postgresql:// URL "
        "(default: OFFSETX_DATABASE_URL, then OFFSETX_OUTREACH_DB)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-campaign")
    create.add_argument("name")
    create.add_argument("--kind", default="email", help="campaign kind (see campaign-kinds)")
    create.add_argument("--daily-limit", type=int, default=25)
    create.add_argument("--timezone", default="Asia/Kolkata")

    listing = sub.add_parser("list-campaigns")
    listing.add_argument("--status", default="")
    listing.add_argument("--kind", default="")

    sub.add_parser("campaign-kinds", help="what kinds exist and which can run")

    import_contacts = sub.add_parser("import-contacts")
    import_contacts.add_argument("campaign_id")
    import_contacts.add_argument("file", type=Path)
    import_contacts.add_argument(
        "--default-category", default="Sustainability / ESG / Climate"
    )

    generate = sub.add_parser("generate")
    generate.add_argument("campaign_id")
    generate.add_argument("--stages", nargs="+", choices=MESSAGE_STAGES, default=list(MESSAGE_STAGES))
    generate.add_argument("--provider-config", type=Path)
    generate.add_argument(
        "--data-policy",
        choices=["strict", "minimal", "standard", "full"],
        default="minimal",
        help="How much of each contact reaches the provider. Defaults to minimal.",
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


def _gmail_token() -> Path:
    # The web app's rule, so a token authorised here is the one it reads (D-138).
    token = gmail_token_path()
    if token is None:
        raise SystemExit(
            "OFFSETX_GMAIL_TOKEN is set but empty, which turns Gmail off. Remove "
            "it to use gmail_token.json in the data directory."
        )
    return token


def _refuse_a_hidden_local_crm(crm: str) -> None:
    """Stop, as the web app does, while a local CRM file holds the owner's rows
    and the database's CRM would be opened instead (`S-06.03.03`)."""
    from .db.hosted import SECRETS_KEY_ENV, HostedStorageError
    from .outreach.store_copy import refuse_a_hidden_local_crm

    try:
        refuse_a_hidden_local_crm(crm, database_path(), os.getenv(SECRETS_KEY_ENV, ""))
    except HostedStorageError as exc:
        report_failure(exc, operation="offsetx-outreach")
        raise SystemExit(failure_message(exc, operation="offsetx-outreach")) from exc


@traced_command("offsetx-outreach")
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    if args.command == "campaign-kinds":
        # Opens nothing, so it needs no lease and answers even during a restore.
        _json({"items": list_campaign_kinds()})
        return 0
    # A named CRM/token can live under another installation's data root. Its
    # restore lock, not merely cwd's, must be acquired before opening it.
    targets = []
    if args.command == "gmail-authorize":
        token = args.token or _gmail_token()
        if token:
            targets.append(Path(token))
    else:
        crm = crm_target(args.db)
        if not is_postgres_url(crm):
            targets.append(Path(crm))
    with cli_workspace_leases(*targets, workspace=data_dir(Path.cwd())):
        return _run(args)


def _run(args: argparse.Namespace) -> int:
    if args.command == "gmail-authorize":
        client = args.client_secrets or Path(
            os.getenv("OFFSETX_GMAIL_CLIENT_SECRETS", "gmail_client_secret.json")
        )
        token = args.token or _gmail_token()
        authorize_interactive(
            client_secrets_path=client,
            token_path=token,
            open_browser=not args.no_browser,
        )
        _json({"connected": True, "token_path": str(token)})
        return 0

    crm = crm_target(args.db)
    if not args.db:
        _refuse_a_hidden_local_crm(crm)
    engine = OutreachEngine(crm)
    try:
        if args.command == "create-campaign":
            campaign_id = engine.create_campaign(
                name=args.name,
                kind=args.kind,
                daily_send_limit=args.daily_limit,
                timezone_name=args.timezone,
            )
            _json(engine.store.get_campaign(campaign_id))
        elif args.command == "list-campaigns":
            items, total = engine.store.list_campaigns(status=args.status, kind=args.kind)
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
            provider = (
                create_guarded_provider(
                    load_provider_config(args.provider_config),
                    data_policy=args.data_policy,
                    profile_id="cli",
                )
                if args.provider_config
                else None
            )
            _json(
                engine.generate_drafts(
                    args.campaign_id, stages=args.stages, provider=provider
                )
            )
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
            own_email = os.getenv("OFFSETX_OWN_EMAIL", "").strip().lower()
            if args.mode == "gmail":
                if args.confirm != "SEND LIVE EMAILS":
                    raise SystemExit("Gmail requires: --confirm \"SEND LIVE EMAILS\"")
                client = os.getenv("OFFSETX_GMAIL_CLIENT_SECRETS", "").strip()
                if not client or not own_email:
                    raise SystemExit(
                        "Set OFFSETX_GMAIL_CLIENT_SECRETS and OFFSETX_OWN_EMAIL"
                    )
                mail = GmailMailProvider(client_secrets_path=client, token_path=_gmail_token())
            else:
                # Beside a CRM file, as before; a database has no folder, so
                # the data folder's, where the web app keeps its outbox.
                outbox = data_dir(Path.cwd()) if is_postgres_url(crm) else Path(crm).parent
                mail = LocalOutboxProvider(outbox / "mail")
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
    except CampaignKindError as exc:
        # These carry a written explanation — which kind, and what is missing.
        # A traceback would bury it under a stack the reader cannot act on.
        report_failure(exc, operation="offsetx-outreach")
        print(failure_message(exc, operation="offsetx-outreach"), file=sys.stderr)
        return 2
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
