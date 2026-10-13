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
from ..observability import traced_command

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from ..data_paths import data_dir, resolved, load_project_env
from ..db import resolve_target
from ..db.hosted import SECRETS_KEY_ENV, HostedStorage
from ..outreach.workspace_lock import cli_workspace_lease
from .broker import EgressBroker
from .evals import EvalRunner, default_evals_path, load_suites, suite_summary, without_references, judged_gtm_case_count, trustworthy_gtm_suite
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
    # The app's own stores: with OFFSETX_DATABASE_URL the keys, the counters
    # and the log are in that database, and a file in the data folder would be
    # an empty key store and a second, partial log (S-06.03.02).
    hosted = HostedStorage.configured(os.getenv(SECRETS_KEY_ENV, ""))
    if hosted is not None:
        hosted.check_secrets_key()
    workspaces = WorkspaceAISettingsStore(data_dir, registry, hosted=hosted)
    # No cache, deliberately. An eval exists to measure a model; a cached
    # answer would make it measure the cache instead, and the numbers feed a
    # promotion decision. The same reasoning as the verify loop using the eval
    # harness's checks rather than inventing weaker ones: measurement and the
    # thing being measured must not share a shortcut.
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "",
        quota=QuotaTracker(data_dir, hosted=hosted),
        logger=EgressLog(resolve_target(default=data_dir / "ai_egress.db")).record,
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


def _data_dir(args: argparse.Namespace) -> Path:
    # Resolved: the lease is named after the folder, and `--data-dir .` has no
    # name until it is. Not through the web app's settings: loading them
    # writes an API token into the workspace, before any lease is held.
    return resolved(args.data_dir, Path.cwd()) if args.data_dir else data_dir(Path.cwd())


def cmd_run(args: argparse.Namespace) -> int:
    registry, workspaces, broker, board = _build(_data_dir(args))
    suites = load_suites(_suite_path(args.file))

    suite = suites.get(args.suite)
    if suite is None:
        print(f"No suite named {args.suite!r}. Known: {', '.join(sorted(suites))}")
        return 2

    ablate = str(getattr(args, "ablate", "") or "")
    if ablate and (ablate != "references" or suite.id != "gtm_plan"):
        print("--ablate references is supported only for the gtm_plan suite.")
        return 2
    if ablate and args.modes:
        print("Choose either --ablate references or --modes; a mode is not an A/B model.")
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
    calls = len(subjects) * len(suite.cases) * (2 if ablate else 1) + len(modes) * len(suite.cases) * 3

    print(f"suite     : {suite.id} ({len(suite.cases)} cases)")
    print(f"models    : {', '.join(f'{p}:{m}' if m else p for p, m in subjects)}")
    if modes:
        print(f"modes     : {', '.join(modes)}")
    print(f"calls     : ~{calls}")
    print()
    if suite.id == "gtm_plan" and not trustworthy_gtm_suite(suite):
        real = judged_gtm_case_count(suite)
        print(f"Only {real} judged real cases of {len(suite.cases)} configured: "
              "no verdict is trustworthy yet. "
              f"Provide at least {max(0, 30-real)} more judged real cases and "
              "replace synthetic/unverified entries before promotion.")
    if args.dry_run:
        print("Dry run. Nothing was sent.")
        return 0

    runner = EvalRunner(broker)
    reports = []
    comparisons = []
    for provider_id, model_id in subjects:
        label = f"{provider_id}:{model_id}" if model_id else provider_id
        print(f"  running {label} ...", flush=True)
        report = runner.run_model(
            suite, settings, provider_id=provider_id, model_id=model_id
        )
        board.record(report, workspace_id=args.workspace)
        reports.append(report)
        if ablate:
            stripped = runner.run_model(
                without_references(suite), settings,
                provider_id=provider_id, model_id=model_id,
            )
            comparisons.append((label, report.score, stripped.score))

    if ablate:
        print()
        print("REFERENCE A/B (same tasks, goals and scoring checks)")
        for label, with_refs, without_refs in comparisons:
            print(f"  {label}: with {with_refs:.3f}; without {without_refs:.3f}")
    if suite.id == "gtm_plan" and not trustworthy_gtm_suite(suite):
        print("No champion promoted: no verdict is trustworthy yet.")
        return 0

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
    board = Scoreboard(_data_dir(args) / "ai_evals.db")
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


@traced_command("offsetx-evals")
def main(argv: Sequence[str] | None = None) -> int:
    load_project_env()
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
        "--ablate", choices=("references",), default="",
        help="for gtm_plan, compare each model with and without reference fields",
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
    if args.command == "list":
        # Reads the suites file only, so it answers during a restore.
        return int(args.func(args))
    with cli_workspace_lease(_data_dir(args)):
        return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
