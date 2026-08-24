"""``offsetx-evals`` — run the suites and print the verdict.

The question this answers, in one command:

    Does compare or orchestrated mode actually beat the best single model?

Usage::

    offsetx-evals list
    offsetx-evals run --suite email_first_contact
    offsetx-evals run --suite email_first_contact --modes
    offsetx-evals champion --suite email_first_contact

Running costs real tokens: every connected model answers every case.  A suite of
30 cases against 4 models is 120 calls.  ``--dry-run`` shows the plan and the
call count without spending anything.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from ..api.config import AppSettings
from .broker import EgressBroker
from .evals import EvalRunner, default_evals_path, load_suites, suite_summary
from .log import EgressLog
from .modes import ModeRunner
from .quota import QuotaTracker
from .registry import ProviderRegistry
from .scoreboard import Scoreboard, best_of, compare
from .workspace import WorkspaceAISettingsStore

#: Rough cost of a mode relative to one model answering once.  Compare fans out
#: to every permitted model; orchestrated adds a planning call on top of the
#: steps.  Used only for the affordability gate, so an estimate is enough.
MODE_COST_MULTIPLE = {"simple": 1.0, "compare": 3.0, "orchestrated": 2.5}


def _build(data_dir: Path):
    registry = ProviderRegistry()
    workspaces = WorkspaceAISettingsStore(data_dir, registry)
    # No cache, deliberately. An eval exists to measure a model; a cached
    # answer would make it measure the cache instead, and the numbers feed a
    # promotion decision. The same reasoning as the verify loop using the eval
    # harness's checks rather than inventing weaker ones: measurement and the
    # thing being measured must not share a shortcut.
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "",
        quota=QuotaTracker(data_dir),
        logger=EgressLog(data_dir / "ai_egress.db").record,
        cache=None,
    )
    board = Scoreboard(data_dir / "ai_evals.db")
    return registry, workspaces, broker, board


def _suite_path(explicit: str) -> Path:
    if explicit:
        return Path(explicit)
    return default_evals_path()


def cmd_list(args: argparse.Namespace) -> int:
    suites = load_suites(_suite_path(args.file))
    print(f"{len(suites)} suite(s) in {_suite_path(args.file)}\n")
    for suite in suites.values():
        checks = sum(len(case.checks) for case in suite.cases)
        print(f"  {suite.id}")
        print(f"    {suite.title}")
        print(f"    {len(suite.cases)} cases, {checks} checks")
        if len(suite.cases) < 20:
            print(
                f"    NOTE: {len(suite.cases)} cases is too few to detect a small "
                "difference. Aim for 30+ before trusting a close verdict."
            )
        print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir) if args.data_dir else AppSettings.from_env().data_dir
    registry, workspaces, broker, board = _build(data_dir)
    suites = load_suites(_suite_path(args.file))

    suite = suites.get(args.suite)
    if suite is None:
        print(f"No suite named {args.suite!r}. Known: {', '.join(sorted(suites))}")
        return 2

    settings = workspaces.egress_settings(args.workspace)
    if not settings.enabled_provider_ids:
        print(
            "No AI provider is connected for this workspace. Open Connectors and "
            "add one before running evals."
        )
        return 2

    # One (provider, model) pair per subject, so a key serving several models is
    # scored per model rather than as a single blob.
    subjects: list[tuple[str, str]] = []
    for provider_id in settings.enabled_provider_ids:
        models = settings.enabled_models.get(provider_id) or ()
        if models:
            subjects.extend((provider_id, model_id) for model_id in models)
        else:
            subjects.append((provider_id, ""))

    modes = ["compare", "orchestrated"] if args.modes else []
    calls = len(subjects) * len(suite.cases) + len(modes) * len(suite.cases) * 3

    print(f"suite     : {suite.id} ({len(suite.cases)} cases)")
    print(f"models    : {', '.join(f'{p}:{m}' if m else p for p, m in subjects)}")
    if modes:
        print(f"modes     : {', '.join(modes)}")
    print(f"calls     : ~{calls}")
    print()
    if args.dry_run:
        print("Dry run. Nothing was sent.")
        return 0

    runner = EvalRunner(broker)
    reports = []
    for provider_id, model_id in subjects:
        label = f"{provider_id}:{model_id}" if model_id else provider_id
        print(f"  running {label} ...", flush=True)
        report = runner.run_model(
            suite, settings, provider_id=provider_id, model_id=model_id
        )
        board.record(report, workspace_id=args.workspace)
        reports.append(report)

    champion = best_of(reports)
    mode_reports = []
    if modes:
        mode_runner = ModeRunner(broker)
        for mode in modes:
            print(f"  running mode {mode} ...", flush=True)
            report = runner.run_mode(suite, settings, mode=mode, runner=mode_runner)
            board.record(report, workspace_id=args.workspace)
            mode_reports.append(report)

    print()
    print("LEADERBOARD")
    print("-" * 64)
    for row in suite_summary(reports + mode_reports):
        flag = "  (errors)" if row["errors"] else ""
        print(
            f"  {row['score']:.3f}  {row['subject']:<32} "
            f"{row['kind']:<6} {row['duration_ms']:>6}ms{flag}"
        )

    if champion is None:
        print("\nNothing scored.")
        return 1

    print()
    print("VERDICT")
    print("-" * 64)
    if not mode_reports:
        print(f"  Champion: {champion.subject} at {champion.score:.3f}")
        print("  No modes were evaluated. Re-run with --modes to test them.")
        board.set_champion(
            workspace_id=args.workspace,
            suite_id=suite.id,
            subject=champion.subject,
            subject_kind="model",
            score=champion.score,
            reason="best single model; modes not evaluated",
        )
        return 0

    promoted = None
    for challenger in sorted(mode_reports, key=lambda r: -r.score):
        verdict = compare(
            champion,
            challenger,
            cost_multiple=MODE_COST_MULTIPLE.get(challenger.subject, 3.0),
        )
        print(f"  {verdict.reason}")
        if verdict.promoted and promoted is None:
            promoted = challenger

    winner = promoted or champion
    board.set_champion(
        workspace_id=args.workspace,
        suite_id=suite.id,
        subject=winner.subject,
        subject_kind="mode" if promoted else "model",
        score=winner.score,
        reason="promoted by eval" if promoted else "no challenger beat the champion",
    )
    print()
    print(f"  Routing {suite.id} to: {winner.subject}")
    return 0


def cmd_champion(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir) if args.data_dir else AppSettings.from_env().data_dir
    board = Scoreboard(data_dir / "ai_evals.db")
    current = board.champion(workspace_id=args.workspace, suite_id=args.suite)
    if not current:
        print(
            f"Nothing measured for {args.suite!r} yet, so traffic routes to a "
            "single model. Run: offsetx-evals run --suite " + args.suite + " --modes"
        )
        return 0
    print(f"  suite    : {args.suite}")
    print(f"  champion : {current['subject']} ({current['subject_kind']})")
    print(f"  score    : {current['score']:.3f}")
    print(f"  decided  : {current['decided_at']}")
    print(f"  because  : {current['reason']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="offsetx-evals",
        description="Measure whether orchestration beats one good model.",
    )
    parser.add_argument("--data-dir", default="", help="override the data directory")
    parser.add_argument("--workspace", default="local")
    parser.add_argument("--file", default="", help="path to evals.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    listed = sub.add_parser("list", help="show the suites and their case counts")
    listed.set_defaults(func=cmd_list)

    run = sub.add_parser("run", help="score every connected model on a suite")
    run.add_argument("--suite", required=True)
    run.add_argument(
        "--modes",
        action="store_true",
        help="also score compare and orchestrated, and decide the routing",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="show the plan and the call count without sending anything",
    )
    run.set_defaults(func=cmd_run)

    champ = sub.add_parser("champion", help="show what a suite currently routes to")
    champ.add_argument("--suite", required=True)
    champ.set_defaults(func=cmd_champion)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
