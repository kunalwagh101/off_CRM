"""``offsetx-codegraph`` — build and inspect the repository's code graph.

Usage::

    offsetx-codegraph policy     # the locked invocation, and what is refused
    offsetx-codegraph build      # write the ignore file, extract, cluster, verify
    offsetx-codegraph status     # how stale the graph is against HEAD
    offsetx-codegraph verify     # re-check an existing graph without rebuilding

`build` runs Graphify with `--code-only` and `--no-label`, which keeps the whole
operation on your machine. Without those flags Graphify posts your source to a
model. `policy` prints exactly what is enforced and why, so the answer does not
have to be taken on trust.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codegraph import (
    FORBIDDEN_USES,
    GRAPHIFY_PACKAGE,
    GRAPHIFY_VERSION,
    RUNTIME_DATA_PATHS,
    CodeGraph,
    CodeGraphError,
    GraphRejected,
    cluster_command,
    extract_command,
    graphify_available,
    render_ignore_file,
)


def _repo_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[1]


def _cmd_policy(args: argparse.Namespace) -> int:
    graph = CodeGraph(_repo_root(args.root))
    available, note = graphify_available()

    print(f"Package : {GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION} (pinned)")
    print(f"Runner  : {note}")
    print(f"Ready   : {'yes' if available else 'no'}")
    print()
    print("Extract :", " ".join(extract_command(graph.root)))
    print("Cluster :", " ".join(cluster_command(graph.root)))
    print()
    print("Refused, and why:")
    for item in FORBIDDEN_USES:
        print(f"  {item.what}")
        print(f"    {item.why}")
    print()
    print("Never indexed:")
    for path in RUNTIME_DATA_PATHS:
        print(f"  {path}/")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    graph = CodeGraph(_repo_root(args.root), out_dir=args.out or None, timeout=args.timeout)
    print(f"Building the code graph for {graph.root}")
    try:
        result = graph.build(workers=args.workers)
    except GraphRejected as exc:
        print("\nGraph rejected and deleted.\n", file=sys.stderr)
        print(exc.check.summary(), file=sys.stderr)
        for path in exc.check.offending[:20]:
            print(f"  {path}: {exc.check.reasons[path]}", file=sys.stderr)
        print(
            "\nThis means something under a runtime-data path was indexed. Check "
            f"{graph.root / '.graphifyignore'} and .gitignore before rebuilding.",
            file=sys.stderr,
        )
        return 2

    print()
    print(f"Ignore file : {result.ignore_path}")
    print(f"Graph       : {result.graph_path}")
    print(f"Report      : {result.report_path}")
    print(f"Checked     : {result.check.summary()}")
    print(f"Size        : {result.status.nodes} nodes, {result.status.edges} edges")
    if not result.pinned:
        print("Version     : NOT pinned — an explicit binary was used")
    print()
    print("Query it with:")
    print(f'  uvx --from {GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION} graphify query "your question"')
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    status = CodeGraph(_repo_root(args.root), out_dir=args.out or None).status()
    print(status.summary())
    if status.exists:
        print(f"{status.nodes} nodes, {status.edges} edges")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    graph = CodeGraph(_repo_root(args.root), out_dir=args.out or None)
    check = graph.verify()
    print(check.summary())
    for path in check.offending[:20]:
        print(f"  {path}: {check.reasons[path]}")
    return 0 if check.ok else 2


def _cmd_ignore(args: argparse.Namespace) -> int:
    sys.stdout.write(render_ignore_file())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="offsetx-codegraph",
        description="Build a queryable map of this repository, locally.",
    )
    parser.add_argument("--root", default="", help="repository root (default: this repo)")
    parser.add_argument("--out", default="", help="write graphify-out/ under this directory")
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("policy", help="show the locked invocation and refusals")
    policy.set_defaults(func=_cmd_policy)

    build = sub.add_parser("build", help="build the graph and verify it")
    build.add_argument("--workers", type=int, default=2)
    build.add_argument("--timeout", type=int, default=1800)
    build.set_defaults(func=_cmd_build)

    status = sub.add_parser("status", help="how stale the graph is")
    status.set_defaults(func=_cmd_status)

    verify = sub.add_parser("verify", help="re-check an existing graph")
    verify.set_defaults(func=_cmd_verify)

    ignore = sub.add_parser("ignore", help="print the generated .graphifyignore")
    ignore.set_defaults(func=_cmd_ignore)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CodeGraphError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
