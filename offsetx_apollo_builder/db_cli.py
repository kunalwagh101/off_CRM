"""``offsetx-db`` — check the database backend and move the egress log.

Usage::

    offsetx-db check                                  # what would be opened, and can it be reached
    offsetx-db check --target postgresql://…
    offsetx-db copy-log --from <data dir>/ai_egress.db --to postgresql://…

The data directory is ``OFFSETX_DATA_DIR``, or ``local_data`` when it is unset.

off_CRM is SQLite-first and stays that way for one owner on one machine.
Postgres is for the case SQLite cannot serve: a deployment whose disk does not
survive a restart, or more than one process writing.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from .ai.log import copy_egress_log
from .data_paths import data_dir, database_path
from .db import (
    DATABASE_URL_ENV,
    DatabaseError,
    describe_target,
    open_database,
    resolve_target,
)
from .db.connection import is_postgres_url
from .outreach.workspace_lock import cli_workspace_lease


def _lease(*targets: object) -> AbstractContextManager[None]:
    """The workspace lease when any target is a file a restore swaps (D-134):
    one inside the data directory, or the CRM database, which a backup covers
    wherever it lives.

    Only then: a Postgres URL, or a SQLite copy kept elsewhere, is not part of
    the workspace, and checking one is what an operator does while a restore
    is stuck.
    """
    workspace = data_dir(Path.cwd())
    for target in targets:
        if is_postgres_url(target):
            continue
        path = Path(str(target)).resolve()
        if path.is_relative_to(workspace) or path == database_path():
            return cli_workspace_lease(workspace)
    return nullcontext()


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        target = resolve_target(args.target or None, default=args.default or None)
    except DatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Target  : {describe_target(target)}")
    with _lease(target):
        return _check(target, args)


def _check(target: str, args: argparse.Namespace) -> int:
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
        with _lease(args.source, args.destination):
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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
