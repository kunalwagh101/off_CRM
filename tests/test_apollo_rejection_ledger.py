from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.io_utils import (
    append_apollo_rejection_ledger,
    read_apollo_rejection_ledgers,
)


def _decision(reason: str, decision: str = "rejected_after_enrichment") -> dict[str, str]:
    return {
        "Decision": decision,
        "Reason": reason,
        "Apollo Person ID": "a" * 24,
        "Full Name": "Asha Rao",
        "Company / Organisation": "Example Exports",
        "Position / Title": "Sales Director",
        "LinkedIn URL": "https://www.linkedin.com/in/asha-rao",
        "Email Returned": "",
        "Source File": "discovery.csv",
        "Source Row Number": "2",
    }


def test_rejection_ledger_is_visible_deduped_and_separate_from_permanent_exclusions(
    tmp_path: Path,
):
    output_root = tmp_path / "output_existing"
    run_dir = output_root / "runs" / "run-one"
    run_dir.mkdir(parents=True)
    path = append_apollo_rejection_ledger(
        output_root,
        [
            _decision("enriched_no_match"),
            _decision("credit_cap_reached_before_enrichment", "rejected_before_enrichment"),
            _decision("accepted_with_email", "accepted"),
        ],
        run_dir,
        "run-one",
    )
    assert path == output_root / "offsetx_apollo_rejection_ledger.csv"
    assert path is not None and path.exists()
    assert not (tmp_path / "old_pois" / path.name).exists()
    assert (run_dir / "offsetx_apollo_rejection_ledger_snapshot.csv").exists()

    items, total = read_apollo_rejection_ledgers([path])
    assert total == 2
    no_match = next(item for item in items if item["reason"] == "enriched_no_match")
    assert no_match["blocks_automatic_retry"] is True
    assert no_match["permanent_exclusion"] is False
    cap = next(
        item for item in items if item["reason"] == "credit_cap_reached_before_enrichment"
    )
    assert cap["blocks_automatic_retry"] is False
    assert cap["retry_policy"] == "retry_next_run"

    append_apollo_rejection_ledger(
        output_root,
        [_decision("enriched_no_match")],
        run_dir,
        "run-two",
    )
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    row = frame[frame["Reason"] == "enriched_no_match"].iloc[0]
    assert row["Occurrence Count"] == "2"
    assert row["Run ID"] == "run-two"
