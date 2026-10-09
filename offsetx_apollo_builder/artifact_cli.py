"""CLI for S-07.01.04 report artifacts."""
from __future__ import annotations
from .observability import failure_message, report_failure, traced_command

import argparse
import sys
from contextlib import nullcontext
from pathlib import Path

from .agent.artifacts import SUPPORTED_FORMATS, ArtifactError, write_artifact
from .browser.trace import Trace, TraceIntegrityError
from .data_paths import data_dir
from .outreach.workspace_lock import cli_workspace_lease


def _trace(run_dir: str) -> Trace:
    directory = Path(run_dir).expanduser().resolve()
    trace_path = directory / "trace.jsonl"
    if not directory.is_dir() or not trace_path.is_file():
        raise ArtifactError(
            f"No agent trace at {trace_path}. Pass --run-dir pointing at one run directory."
        )
    return Trace.open(directory.parent, run_id=directory.name)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="offsetx-artifacts",
        description="Turn one verified agent run into XLSX, PPTX or PDF.",
    )
    result.add_argument(
        "--run-dir",
        required=True,
        help="Run directory containing trace.jsonl and its evidence artifacts.",
    )
    result.add_argument(
        "--format",
        dest="format_name",
        choices=(*SUPPORTED_FORMATS, "all"),
        default="all",
        help="Artifact format to write. Default: all.",
    )
    result.add_argument(
        "--browser",
        default="",
        help="Optional Chrome/Edge/Brave/Chromium executable used for PDF rendering.",
    )
    return result


@traced_command("offsetx-artifacts")
def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    # The app records agent runs under the data directory, and the reports are
    # written beside the trace, so rendering one writes into the workspace
    # (D-139). A run copied elsewhere is nothing a restore swaps.
    workspace = data_dir(Path.cwd())
    inside = Path(args.run_dir).expanduser().resolve().is_relative_to(workspace)
    with cli_workspace_lease(workspace) if inside else nullcontext():
        try:
            trace = _trace(args.run_dir)
            formats = SUPPORTED_FORMATS if args.format_name == "all" else (args.format_name,)
            for format_name in formats:
                path = write_artifact(trace, format_name, browser_path=args.browser)
                print(path)
            return 0
        except (ArtifactError, TraceIntegrityError, OSError, ValueError) as exc:
            report_failure(exc, operation="offsetx-artifacts")
            print(failure_message(exc, operation="offsetx-artifacts"), file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
