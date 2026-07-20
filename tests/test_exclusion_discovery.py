from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.dedupe import discover_exclusion_files


def test_discover_exclusion_files_from_folder_and_previous_outputs(tmp_path: Path):
    old = tmp_path / "old_pois"
    old.mkdir()
    pd.DataFrame([{"Email": "a@example.com"}]).to_csv(old / "a.csv", index=False)
    pd.DataFrame([{"Email": "b@example.com"}]).to_excel(old / "b.xlsx", index=False)

    out = tmp_path / "output_real_test_5"
    out.mkdir()
    pd.DataFrame([{"Email": "c@example.com"}]).to_csv(out / "offsetx_final_pois_with_emails.csv", index=False)

    files = discover_exclusion_files(exclusion_dir=old, include_previous_outputs=True, project_root=tmp_path)
    names = {p.name for p in files}
    assert names == {"a.csv", "b.xlsx", "offsetx_final_pois_with_emails.csv"}
