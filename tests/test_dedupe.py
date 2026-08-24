from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.dedupe import build_exclusion_set, ExclusionSet


def test_exclusion_by_apollo_id(tmp_path: Path):
    p = tmp_path / "old.csv"
    pd.DataFrame([{"Apollo Person ID": "000000000000000000000001", "Email": "x@example.com", "Full Name": "Sample Person", "Company": "Example Industries"}]).to_csv(p, index=False)
    ex = build_exclusion_set([p])
    dup, reason = ex.is_duplicate_candidate({"id": "000000000000000000000001", "name": "Other", "organization_name": "Other"})
    assert dup is True
    assert reason == "duplicate_apollo_id"


def test_exclusion_by_name_company():
    ex = ExclusionSet()
    ex.add_record({"Full Name": "Priya Example", "Company / Organisation": "Example Manufacturing"})
    dup, reason = ex.is_duplicate_candidate({"name": "Priya Example", "organization_name": "Example Manufacturing"})
    assert dup is True
    assert reason == "duplicate_name_company"


def test_fresh_candidate():
    ex = ExclusionSet()
    ex.add_record({"Full Name": "Old Person", "Company": "OldCo"})
    dup, reason = ex.is_duplicate_candidate({"id": "aaaaaaaaaaaaaaaaaaaaaaaa", "name": "New Person", "organization_name": "NewCo"})
    assert dup is False
    assert reason == "fresh"
