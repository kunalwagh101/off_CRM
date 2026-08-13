"""``offsetx-db`` — check the database backend and move the egress log.

Usage::

    offsetx-db check                                  # what would be opened, and can it be reached
    offsetx-db check --target postgresql://…
    offsetx-db copy-log --from local_data/ai_egress.db --to postgresql://…

off_CRM is SQLite-first and stays that way for one owner on one machine.
Postgres is for the case SQLite cannot serve: a deployment whose disk does not
survive a restart, or more than one process writing.
"""

from __future__ import annotations

import argparse
import sys

from .db import DATABASE_URL_ENV, DatabaseError, describe_target, open_database, resolve_target
from .ai.log import copy_egress_log


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        target = resolve_target(args.target or None, default=args.default or None)
    except DatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Target  : {describe_target(target)}")
    try:
        database = open_database(target)
    except DatabaseError as exc:
        print(f"Reachable: no — {exc}", file=sys.stderr)
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
            print(f"  ({exc})")
    finally:
        database.close()
    return 0


def _cmd_copy_log(args: argparse.Namespace) -> int:
    try:
        result = copy_egress_log(args.source, args.destination)
    except DatabaseError as exc:
        print(str(exc), file=sys.stderr)
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
    print("The SQLite file was not modified. To switch over, set:")
    print(f"    {DATABASE_URL_ENV}={args.destination}")
    print("and restart. To go back, unset it.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="offsetx-db",
        description="Inspect the database backend and move the egress log.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="show the target and whether it can be reached")
    check.add_argument("--target", default="", help="path or postgresql:// URL")
    check.add_argument(
        "--default",
        default="local_data/ai_egress.db",
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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
