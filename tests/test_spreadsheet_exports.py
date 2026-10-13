"""A19: external spreadsheet cells must never become executable formulas."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from offsetx_apollo_builder.io_utils import (
    spreadsheet_safe_cell,
    spreadsheet_safe_frame,
    write_outputs,
)


def test_formulas_are_escaped_in_csv_and_xlsx_without_changing_numeric_values(tmp_path: Path):
    values = [
        "=HYPERLINK(\"https://evil.invalid\",\"click\")",
        "+SUM(1,2)",
        "-1+2",
        "@SUM(1,2)",
        " \t=SUM(1,2)",
        "\t=HYPERLINK(\"https://evil.invalid\",\"open\")",
        "normal text",
    ]
    original = pd.DataFrame({"External": values, "Count": list(range(len(values)))})
    safe = spreadsheet_safe_frame(original)
    assert original["External"].tolist() == values
    assert safe["Count"].tolist() == list(range(len(values)))
    assert safe["External"].tolist()[:6] == ["'" + value for value in values[:6]]
    assert safe["External"].iloc[-1] == "normal text"
    assert spreadsheet_safe_cell(123) == 123
    assert spreadsheet_safe_cell("'-literal") == "'-literal"

    csv_path = tmp_path / "safe.csv"
    xlsx_path = tmp_path / "safe.xlsx"
    safe.to_csv(csv_path, index=False)
    safe.to_excel(xlsx_path, index=False)
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert rows[0]["External"].startswith("'=HYPERLINK")
    assert rows[4]["External"].startswith("' \t=")
    book = load_workbook(xlsx_path, data_only=False)
    sheet = book.active
    for row_number in range(2, 8):
        cell = sheet.cell(row_number, 1)
        assert cell.data_type != "f"
        assert cell.value.startswith("'")
    assert sheet.cell(8, 1).value == "normal text"
    assert isinstance(sheet.cell(2, 2).value, int)


def test_real_enrichment_export_escapes_formula_but_leaves_source_unchanged(tmp_path: Path):
    source = [{"Full Name": "=HYPERLINK(\"https://evil.invalid\",\"click\")",
               "Company / Organisation": "@RISK", "Email": "a@example.test"}]
    out = tmp_path / "results"
    write_outputs(out, source, [], {"run_id": "run-1", "output_dir": str(out)})
    assert source[0]["Full Name"].startswith("=")
    with (out / "offsetx_final_pois_with_emails.csv").open(newline="", encoding="utf-8") as fp:
        row = next(csv.DictReader(fp))
    assert row["Full Name"].startswith("'=HYPERLINK")
    assert row["Company / Organisation"] == "'@RISK"
    book = load_workbook(out / "offsetx_final_pois_with_emails.xlsx", data_only=False)
    sheet = book["Final_POIs"]
    headers = {cell.value: cell.column for cell in sheet[1]}
    cell = sheet.cell(2, headers["Full Name"])
    assert cell.data_type != "f"
    assert cell.value.startswith("'=HYPERLINK")
