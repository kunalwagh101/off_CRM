from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .apollo_client import ApolloApiError
from .dedupe import discover_exclusion_files
from .existing_poi_enrichment import (
    ExistingPoiEnrichmentConfig,
    NoInputFilesError,
    RunOutputExistsError,
    run_existing_poi_enrichment,
)
from .file_queue import inspect_queue
from .runner import RunConfig, run


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build or enrich off_CRM POIs with dedupe, analytics, and a hard Apollo credit cap."
    )
    p.add_argument("--exclusions", nargs="*", type=Path, default=[], help="Optional specific old POI files to exclude.")
    p.add_argument("--exclusion-dir", type=Path, default=Path("old_pois"), help="Folder scanned recursively for exclusion files.")
    p.add_argument("--include-previous-outputs", action=argparse.BooleanOptionalAction, default=True, help="Exclude previous final-output contacts.")
    p.add_argument("--update-exclusion-ledger", action=argparse.BooleanOptionalAction, default=True, help="Append newly accepted contacts to the permanent exclusion ledger.")
    p.add_argument("--outdir", type=Path, default=Path("output"), help="Run root. Outputs go to <outdir>/runs/<run_id>.")
    p.add_argument("--run-id", type=str, default=None, help="Optional run ID. Existing non-empty run IDs are never overwritten.")
    p.add_argument("--no-latest-copy", action="store_true", help="Do not refresh <outdir>/latest.")
    p.add_argument("--target-count", type=int, default=250, help="Maximum accepted POIs with emails.")
    p.add_argument("--credit-cap", type=int, default=250, help="Hard Apollo enrichment credit cap.")
    p.add_argument("--pages-per-category", type=int, default=5)
    p.add_argument("--per-page", type=int, default=100)
    p.add_argument("--batch-size", type=int, default=10, help="People per Apollo bulk call, 1 to 10.")
    p.add_argument("--max-per-company", type=int, default=6)
    p.add_argument("--dry-run", action="store_true", help="Validate, dedupe, and audit without calling Apollo.")
    p.add_argument("--env-file", type=Path, default=Path(".env"))

    # Existing POI file enrichment mode.
    p.add_argument("--enrich-existing-pois", action="store_true", help="Enrich POIs already present in CSV/XLSX/XLS files.")
    p.add_argument("--enrich-input-file", type=Path, default=None, help="Use one explicit input file. The source is preserved.")
    p.add_argument("--enrich-input-dir", type=Path, default=Path("poi_file_queue/inbox"))
    p.add_argument("--processing-dir", type=Path, default=Path("poi_file_queue/processing"))
    p.add_argument("--processed-dir", type=Path, default=Path("poi_file_queue/processed"))
    p.add_argument("--failed-dir", type=Path, default=Path("poi_file_queue/failed"))
    p.add_argument("--queue-status", action="store_true", help="Show enrichment queue counts and exit without calling Apollo.")
    p.add_argument(
        "--reuse-latest-processed",
        action="store_true",
        help="When inbox is empty, copy the latest processed file into a new run. The archived source is preserved.",
    )
    p.add_argument("--skip-existing-emails", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--attempt-ledger", type=Path, default=None, help="Defaults to old_pois/offsetx_apollo_enrichment_attempt_ledger.csv.")
    p.add_argument("--skip-previously-attempted", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--auto-backfill-attempt-ledger", action=argparse.BooleanOptionalAction, default=True)
    return p.parse_args(argv)


def _print_queue_status(args: argparse.Namespace) -> None:
    status = inspect_queue(args.enrich_input_dir, args.processing_dir, args.processed_dir, args.failed_dir)
    print("Existing-POI enrichment queue")
    print(f"  Inbox:     {len(status.inbox_files)} file(s) | {args.enrich_input_dir.resolve()}")
    print(f"  Processing:{len(status.processing_files)} file(s) | {args.processing_dir.resolve()}")
    print(f"  Processed: {len(status.processed_files)} file(s) | {args.processed_dir.resolve()}")
    print(f"  Failed:    {len(status.failed_files)} file(s) | {args.failed_dir.resolve()}")
    if status.latest_processed:
        print(f"  Latest processed: {status.latest_processed.resolve()}")


def _validate_args(args: argparse.Namespace) -> None:
    if not 1 <= args.batch_size <= 10:
        raise SystemExit("--batch-size must be between 1 and 10.")
    if args.credit_cap <= 0:
        raise SystemExit("--credit-cap must be positive.")
    if args.target_count <= 0:
        raise SystemExit("--target-count must be positive.")
    if args.enrich_input_file and args.reuse_latest_processed:
        raise SystemExit("Use either --enrich-input-file or --reuse-latest-processed, not both.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(args.env_file)
    _validate_args(args)

    if args.queue_status:
        _print_queue_status(args)
        return 0

    exclusion_files = discover_exclusion_files(
        explicit_paths=args.exclusions,
        exclusion_dir=args.exclusion_dir,
        include_previous_outputs=args.include_previous_outputs,
        project_root=Path.cwd(),
    )

    print(f"Exclusion files loaded: {len(exclusion_files)}")
    for path in exclusion_files:
        print(f"  - {path}")

    if args.enrich_existing_pois or args.enrich_input_file or args.reuse_latest_processed:
        cfg = ExistingPoiEnrichmentConfig(
            exclusions=exclusion_files,
            outdir=args.outdir,
            input_file=args.enrich_input_file,
            input_dir=args.enrich_input_dir,
            processing_dir=args.processing_dir,
            processed_dir=args.processed_dir,
            failed_dir=args.failed_dir,
            exclusion_dir=args.exclusion_dir,
            update_exclusion_ledger=args.update_exclusion_ledger,
            credit_cap=args.credit_cap,
            batch_size=args.batch_size,
            target_count=args.target_count,
            dry_run=args.dry_run,
            reveal_personal_emails=False,
            run_id=args.run_id,
            write_latest_copy=not args.no_latest_copy,
            skip_existing_emails=args.skip_existing_emails,
            attempt_ledger_path=args.attempt_ledger,
            skip_previously_attempted=args.skip_previously_attempted,
            auto_backfill_attempt_ledger=args.auto_backfill_attempt_ledger,
            reuse_latest_processed=args.reuse_latest_processed,
        )
        try:
            state = run_existing_poi_enrichment(cfg, client=None)
        except NoInputFilesError as exc:
            print("\nNo enrichment run started.")
            print(f"Reason: {exc}")
            print(f"Inbox: {exc.input_dir.resolve()}")
            if exc.latest_processed:
                print("To rerun the latest archived file without copying it manually, add:")
                print("  --reuse-latest-processed")
            print("No Apollo API call was made. No credits were used.")
            return 0
        except RunOutputExistsError as exc:
            print(f"\nRun stopped safely: {exc}")
            print("Choose a new --run-id. No queue file was claimed and no Apollo credits were used.")
            return 2
        except ApolloApiError as exc:
            print(f"\nApollo API error: {exc}")
            print(f"Claimed inputs were moved to: {args.failed_dir.resolve()}")
            return 2

        stage_counts = Counter(str(row.get("Decision", "")) for row in state.decision_log)
        reason_counts = Counter(str(row.get("reason", "")) for row in state.rejected)
        skipped_before = stage_counts.get("rejected_before_enrichment", 0) + stage_counts.get("skipped_before_enrichment", 0)

        print(f"Existing POI input files claimed: {state.files_claimed}")
        print(f"Existing POI input rows seen: {state.input_rows_seen}")
        print(f"Selected for Apollo enrichment: {state.selected_for_enrichment}")
        print(f"Previously attempted POIs skipped: {state.previously_attempted_skipped}")
        print(f"Historical Apollo attempts backfilled: {state.attempt_ledger_backfilled}")
        print(f"Genuine rows skipped before Apollo: {skipped_before}")
        if args.dry_run:
            print(f"Dry-run eligible rows not sent to Apollo: {reason_counts.get('dry_run_not_enriched', 0)}")
        print(f"Accepted POIs with emails: {len(state.accepted)}")
        print(f"Apollo enrichment credits reported used: {state.credits_used}")
        print(f"Non-accepted audit rows: {len(state.rejected)}")
        print(f"Run ID: {state.run_id}")
        print(f"Run outputs written to: {state.output_dir.resolve() if state.output_dir else args.outdir.resolve()}")
        print(f"Latest snapshot: {(args.outdir / 'latest').resolve()}")
        print(f"Run index: {(args.outdir / 'offsetx_runs_index.csv').resolve()}")
        return 0

    cfg = RunConfig(
        exclusions=exclusion_files,
        outdir=args.outdir,
        exclusion_dir=args.exclusion_dir,
        update_exclusion_ledger=args.update_exclusion_ledger,
        target_count=args.target_count,
        credit_cap=args.credit_cap,
        per_page=args.per_page,
        pages_per_category=args.pages_per_category,
        batch_size=args.batch_size,
        max_per_company=args.max_per_company,
        dry_run=args.dry_run,
        reveal_personal_emails=False,
        run_id=args.run_id,
        write_latest_copy=not args.no_latest_copy,
    )
    from .apollo_client import ApolloClient

    state = run(cfg, client=ApolloClient.from_env())
    print(f"Accepted POIs with emails: {len(state.accepted)}")
    print(f"Apollo enrichment credits reported used: {state.credits_used}")
    print(f"Rejected/duplicate/conflict rows: {len(state.rejected)}")
    print(f"Run ID: {state.run_id}")
    print(f"Run outputs written to: {state.output_dir.resolve() if state.output_dir else args.outdir.resolve()}")
    print(f"Latest snapshot: {(args.outdir / 'latest').resolve()}")
    print(f"Run index: {(args.outdir / 'offsetx_runs_index.csv').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
