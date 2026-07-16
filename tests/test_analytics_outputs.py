from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.io_utils import write_outputs


def test_write_outputs_includes_raw_and_decision_analytics(tmp_path: Path):
    accepted = [{
        "Full Name": "A Person",
        "Company / Organisation": "A Co",
        "Category": "CBAM / Trade Compliance",
        "Country / Region": "Singapore",
        "Risk Level": "Safe",
        "Assigned To": "Person A",
        "Wave": "Wave 1",
        "Apollo Person ID": "abc",
        "Email": "a@example.com",
    }]
    rejected = [{"reason": "duplicate_apollo_id", "candidate_id": "old"}]
    raw = [{"Apollo Search Category": "CBAM / Trade Compliance", "Apollo Person ID": "abc"}]
    decision = [{"Apollo Search Category": "CBAM / Trade Compliance", "Decision": "accepted", "Reason": "accepted_with_email"}]

    write_outputs(tmp_path, accepted, rejected, {"dry_run": False}, raw_candidates=raw, decision_log=decision)

    assert (tmp_path / "offsetx_apollo_raw_search_candidates.csv").exists()
    assert (tmp_path / "offsetx_candidate_decision_audit.csv").exists()
    assert (tmp_path / "offsetx_analytics_reason_counts.csv").exists()
    assert (tmp_path / "offsetx_analytics_category_counts.csv").exists()
    assert (tmp_path / "offsetx_analytics_funnel.csv").exists()

    funnel = pd.read_csv(tmp_path / "offsetx_analytics_funnel.csv")
    assert "accepted_with_email" in set(funnel["metric"])
