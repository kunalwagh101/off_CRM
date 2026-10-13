"""``offsetx-notebook`` — build a research-notebook bundle from a campaign.

Usage::

    offsetx-notebook targets
    offsetx-notebook plan   --campaign <id> --target notebooklm
    offsetx-notebook export --campaign <id> --target notebooklm --out ./bundle-aug

``plan`` writes nothing. It prints what would be included, what would be held
back and why. Run it first — the answer at the default destination is usually
"less than you expected", and finding that out before you have a folder is
cheaper than after.
"""

from __future__ import annotations
from .observability import failure_message, report_failure, traced_command

import argparse
import os
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Sequence

from .ai.context import ContextLayer
from .data_paths import crm_target, data_dir, database_path, load_project_env
from .db import is_postgres_url
from .notebook import (
    NotebookExport,
    NotebookExportBlocked,
    NotebookExportError,
    list_targets,
    resolve_target,
)
from .outreach.store import OutreachStore
from .outreach.workspace_lock import cli_workspace_leases


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    widths = [len(head) for head in headers]
    cells = [[str(value) for value in row] for row in rows]
    for row in cells:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    line = "  ".join(head.ljust(widths[index]) for index, head in enumerate(headers))
    print(line.rstrip())
    print("  ".join("-" * width for width in widths))
    for row in cells:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip())


def _cmd_targets(_: argparse.Namespace) -> int:
    print("Where a bundle can go, and how far each place is trusted.\n")
    _print_table(
        ["id", "tier", "policy", "destination"],
        [
            (item["id"], item["tier"], item["policy"], item["label"])
            for item in list_targets()
        ],
    )
    print()
    for item in list_targets():
        print(f"  {item['id']}: {item['why']}")
    return 0


def _exporter(args: argparse.Namespace) -> tuple[NotebookExport, OutreachStore, ContextLayer | None]:
    crm = crm_target(args.db)
    if not args.db:
        # As the web app does: not while a local CRM file holds the owner's rows.
        from .db.hosted import SECRETS_KEY_ENV, HostedStorageError
        from .outreach.store_copy import refuse_a_hidden_local_crm

        try:
            refuse_a_hidden_local_crm(crm, database_path(), os.getenv(SECRETS_KEY_ENV, ""))
        except HostedStorageError as exc:
            report_failure(exc, operation="offsetx-notebook")
            raise SystemExit(failure_message(exc, operation="offsetx-notebook")) from exc
    store = OutreachStore(crm)
    store.initialize()
    context: ContextLayer | None = None
    context_path = Path(args.context)
    if context_path.exists():
        context = ContextLayer(context_path)
    return (
        NotebookExport(
            store,
            context=context,
            workspace_id=args.workspace,
            owner_domains=[item for item in (args.owner_domain or []) if item],
            owner_addresses=[item for item in (args.owner_address or []) if item],
        ),
        store,
        context,
    )


def _report_plan(plan) -> None:
    target = plan.target
    print(f"Campaign : {plan.campaign_id} ({plan.campaign_kind})")
    print(f"Going to : {target.label}")
    print(f"Tier     : {target.tier.value} — {target.tier.label}")
    print(f"Policy   : {plan.policy.value}")
    if target.override_reason:
        print(f"Override : {target.override_reason}")
    print()

    described = plan.to_dict()
    print("Included:")
    if described["included"]:
        _print_table(
            ["file", "section", "carries"],
            [
                (item["filename"], item["title"], item["data_class"])
                for item in described["included"]
            ],
        )
    else:
        print("  nothing — this destination receives no section of this campaign")
    print()

    print("Held back:")
    if plan.withheld:
        for item in plan.withheld:
            print(f"  {item.title}: {item.reason}")
            if item.fix:
                print(f"    fix: {item.fix}")
    else:
        print("  nothing")
    print()

    if plan.tokenised:
        print("People and companies will be tokenised. The key is written")
        print("outside the bundle folder and must not be uploaded.")
        print()


def _cmd_plan(args: argparse.Namespace) -> int:
    exporter, store, context = _exporter(args)
    try:
        target = resolve_target(
            args.target, tier_override=args.tier or None, override_reason=args.reason
        )
        _report_plan(exporter.plan(args.campaign, target))
    finally:
        store.close()
        if context is not None:
            context.close()
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    exporter, store, context = _exporter(args)
    try:
        target = resolve_target(
            args.target, tier_override=args.tier or None, override_reason=args.reason
        )
        result = exporter.export(args.campaign, target, args.out)
    except NotebookExportBlocked as exc:
        report_failure(exc, operation="offsetx-notebook")
        print("Export blocked. Nothing was written.\n", file=sys.stderr)
        print(failure_message(exc, operation="offsetx-notebook"), file=sys.stderr)
        print("Review the export policy and permitted fields before retrying.", file=sys.stderr)
        return 2
    finally:
        store.close()
        if context is not None:
            context.close()

    _report_plan(result.plan)
    print(f"Wrote {len(result.files)} files to {result.bundle_dir}")
    _print_table(
        ["file", "bytes"],
        [(item.name, str(item.bytes)) for item in result.files],
    )
    if result.key_path:
        print()
        print(f"Identity key: {result.key_path}")
        print("Do not upload it. It is outside the bundle folder for that reason.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offsetx-notebook",
        description="Build research-notebook sources from a campaign.",
    )
    # No default here, as in `offsetx-outreach`: the CRM the web app opens.
    parser.add_argument(
        "--db", help="CRM to open (default: OFFSETX_DATABASE_URL, then OFFSETX_OUTREACH_DB)"
    )
    # Where the web app keeps it, not beside the CRM: the two differ once the
    # CRM database is named elsewhere (D-141).
    parser.add_argument(
        "--context",
        default=str(data_dir(Path.cwd()) / "ai_context.db"),
        help="AI context database path",
    )
    parser.add_argument("--workspace", default="local")
    parser.add_argument(
        "--owner-domain",
        action="append",
        default=[],
        help="your own domain; the scan refuses a bundle containing it",
    )
    parser.add_argument("--owner-address", action="append", default=[])
    sub = parser.add_subparsers(dest="command", required=True)

    targets = sub.add_parser("targets", help="list export destinations")
    targets.set_defaults(func=_cmd_targets)

    for name, handler, help_text in (
        ("plan", _cmd_plan, "show what would be exported, writing nothing"),
        ("export", _cmd_export, "write the bundle"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--campaign", required=True)
        cmd.add_argument("--target", default="notebooklm")
        cmd.add_argument("--tier", default="", help="override the destination's trust tier")
        cmd.add_argument("--reason", default="", help="why the override is justified")
        if name == "export":
            cmd.add_argument("--out", required=True, help="an empty output directory")
        cmd.set_defaults(func=handler)
    return parser


@traced_command("offsetx-notebook")
def main(argv: list[str] | None = None) -> int:
    load_project_env()
    args = _parser().parse_args(argv)
    # `targets` reads nothing from the workspace, so it answers during a restore.
    crm = crm_target(args.db)
    targets = [Path(args.context)]
    if not is_postgres_url(crm):
        targets.append(Path(crm))
    if getattr(args, "out", None):
        targets.append(Path(args.out))
    lease = (
        nullcontext() if args.command == "targets"
        else cli_workspace_leases(*targets, workspace=data_dir(Path.cwd()))
    )
    try:
        with lease:
            return int(args.func(args))
    except NotebookExportError as exc:
        report_failure(exc, operation="offsetx-notebook")
        print(failure_message(exc, operation="offsetx-notebook"), file=sys.stderr)
        return 2
    except KeyError as exc:
        report_failure(exc, operation="offsetx-notebook")
        print(failure_message(exc, operation="offsetx-notebook"), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
