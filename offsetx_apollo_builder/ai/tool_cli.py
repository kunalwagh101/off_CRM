"""``offsetx-tools`` — register, inspect and run sandboxed tools.

Registration is the owner's act, and this is where it happens.  There is no
model-facing path to it by design: a model picks from the catalogue, it never
adds to it.

Usage::

    offsetx-tools register --name run-tests \\
        --repo https://github.com/you/thing \\
        --commit <40-char-sha> \\
        --image python:3.12-slim \\
        -- pytest -q

    offsetx-tools list
    offsetx-tools show run-tests
    offsetx-tools catalogue          # exactly what a model would be shown
    offsetx-tools run run-tests
    offsetx-tools disable run-tests
    offsetx-tools remove run-tests
    offsetx-tools runs

Everything after ``--`` is the command the tool runs inside the container.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from ..api.config import AppSettings
from .errors import AIModuleError
from .sandbox import SandboxWorkspace, sandbox_available
from .tools import ToolRegistry


def _registry(args: argparse.Namespace) -> ToolRegistry:
    data_dir = Path(args.data_dir) if args.data_dir else AppSettings.from_env().data_dir
    return ToolRegistry(data_dir / "ai_tools.db")


def _resolve(registry: ToolRegistry, reference: str, workspace: str):
    """Accept a name or an id, because typing a uuid is nobody's idea of fun."""
    tool = registry.by_name(reference, workspace_id=workspace)
    if tool is None:
        tool = registry.get(reference, workspace_id=workspace)
    return tool


def cmd_register(args: argparse.Namespace) -> int:
    registry = _registry(args)
    if not args.command:
        print(
            "No command given. Put it after `--`, for example:\n"
            "  offsetx-tools register --name run-tests ... -- pytest -q"
        )
        return 2
    tool = registry.register(
        name=args.name,
        repository_url=args.repo,
        commit_sha=args.commit,
        image=args.image,
        command=args.command,
        description=args.description,
        allows_arguments=args.allow_arguments,
        workspace_id=args.workspace,
    )
    print(f"Registered {tool.name!r} ({tool.id})")
    print(f"  repo    : {tool.repository_url}")
    print(f"  commit  : {tool.commit_sha}")
    print(f"  image   : {tool.image}")
    print(f"  command : {' '.join(tool.command)}")
    print(f"  args    : {'accepted' if tool.allows_arguments else 'not accepted'}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    registry = _registry(args)
    tools = registry.list(workspace_id=args.workspace)
    if not tools:
        print(
            "No tools registered. Add one with:\n"
            "  offsetx-tools register --name <n> --repo <url> --commit <sha> "
            "--image <image:tag> -- <command>"
        )
        return 0
    for tool in tools:
        state = "" if tool.enabled else "  [disabled]"
        print(f"  {tool.name}{state}")
        print(f"      {tool.description or '(no description)'}")
        print(f"      {tool.commit_sha[:12]}  {tool.image}  {' '.join(tool.command)}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    registry = _registry(args)
    tool = _resolve(registry, args.tool, args.workspace)
    if tool is None:
        print(f"No tool named {args.tool!r}.")
        return 2
    print(json.dumps(tool.to_dict(), indent=2))
    return 0


def cmd_catalogue(args: argparse.Namespace) -> int:
    """Exactly what a model would be shown — no image, no command, no repo."""
    registry = _registry(args)
    entries = registry.catalogue(workspace_id=args.workspace)
    print("This is the whole of what a model sees:\n")
    print(json.dumps(entries, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    registry = _registry(args)
    tool = _resolve(registry, args.tool, args.workspace)
    if tool is None:
        print(f"No tool named {args.tool!r}.")
        return 2

    available, reason = sandbox_available()
    if not available:
        print(reason)
        return 2

    root = Path(args.workdir) if args.workdir else (
        Path(args.data_dir or AppSettings.from_env().data_dir) / "sandbox" / tool.name
    )
    workspace = SandboxWorkspace(root=root)
    print(f"running {tool.name} @ {tool.commit_sha[:12]} in {root}")
    run = registry.run(
        tool.id,
        workspace=workspace,
        extra_arguments=args.args or (),
        workspace_id=args.workspace,
        timeout_seconds=args.timeout,
        fetch_source=not args.no_fetch,
    )
    if run.stdout:
        print(run.stdout.rstrip())
    if run.stderr:
        print(run.stderr.rstrip(), file=sys.stderr)
    print(f"\nexit {run.exit_code}  ({run.status}, {run.duration_ms}ms)")
    return 0 if run.ok else 1


def cmd_enable(args: argparse.Namespace) -> int:
    registry = _registry(args)
    tool = _resolve(registry, args.tool, args.workspace)
    if tool is None:
        print(f"No tool named {args.tool!r}.")
        return 2
    registry.set_enabled(tool.id, args.enabled, workspace_id=args.workspace)
    print(f"{tool.name} is now {'enabled' if args.enabled else 'disabled'}.")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    registry = _registry(args)
    tool = _resolve(registry, args.tool, args.workspace)
    if tool is None:
        print(f"No tool named {args.tool!r}.")
        return 2
    registry.remove(tool.id, workspace_id=args.workspace)
    print(f"Removed {tool.name}.")
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    registry = _registry(args)
    rows = registry.runs(workspace_id=args.workspace, limit=args.limit)
    if not rows:
        print("Nothing has run yet.")
        return 0
    for row in rows:
        print(
            f"  {row['started_at']}  {row['tool_name']:<20} "
            f"{row['commit_sha'][:12]}  exit {row['exit_code']:<4} "
            f"{row['status']:<8} {row['duration_ms']}ms"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="offsetx-tools",
        description="Register and run sandboxed tools. Registration is yours alone.",
    )
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--workspace", default="local")
    sub = parser.add_subparsers(dest="command_name", required=True)

    register = sub.add_parser("register", help="pin a tool (owner only)")
    register.add_argument("--name", required=True)
    register.add_argument("--repo", required=True, help="https://github.com/owner/repo")
    register.add_argument("--commit", required=True, help="full 40-character SHA")
    register.add_argument("--image", required=True, help="pinned image, not :latest")
    register.add_argument("--description", default="")
    register.add_argument(
        "--allow-arguments",
        action="store_true",
        help="let callers append values (off by default)",
    )
    register.add_argument("command", nargs=argparse.REMAINDER)
    register.set_defaults(func=cmd_register)

    listed = sub.add_parser("list", help="every registered tool")
    listed.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="the full record for one tool")
    show.add_argument("tool")
    show.set_defaults(func=cmd_show)

    catalogue = sub.add_parser("catalogue", help="what a model is shown")
    catalogue.set_defaults(func=cmd_catalogue)

    run = sub.add_parser("run", help="run a tool in the sandbox")
    run.add_argument("tool")
    run.add_argument("--workdir", default="")
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument(
        "--no-fetch", action="store_true", help="skip the git fetch (source already there)"
    )
    run.add_argument("args", nargs="*", help="extra values, if the tool allows them")
    run.set_defaults(func=cmd_run)

    disable = sub.add_parser("disable", help="hide a tool from the catalogue")
    disable.add_argument("tool")
    disable.set_defaults(func=cmd_enable, enabled=False)

    enable = sub.add_parser("enable", help="return a tool to the catalogue")
    enable.add_argument("tool")
    enable.set_defaults(func=cmd_enable, enabled=True)

    remove = sub.add_parser("remove", help="delete a registration")
    remove.add_argument("tool")
    remove.set_defaults(func=cmd_remove)

    runs = sub.add_parser("runs", help="run history")
    runs.add_argument("--limit", type=int, default=25)
    runs.set_defaults(func=cmd_runs)

    args = parser.parse_args(argv)
    # `register` collects its command with REMAINDER, which keeps a leading `--`.
    if getattr(args, "command", None) and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    try:
        return int(args.func(args))
    except AIModuleError as exc:
        print(str(exc))
        return 2
    except ValueError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
