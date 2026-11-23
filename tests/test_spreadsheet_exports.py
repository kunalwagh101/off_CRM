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


def test_every_report_tab_escapes_untrusted_rows_without_mutating_source(tmp_path: Path):
    """S-06.02.42: accepted, rejected, raw, decision and metadata tabs stay inert."""
    accepted = [{"Full Name": "=HYPERLINK(\"https://evil.invalid\",\"open\")",
                 "Company / Organisation": "+SUM(1,1)", "Email": "safe@example.test"}]
    rejected = [{"reason": "@RISK", "name": "-1+2"}]
    raw = [{"name": "\t=SUM(1,1)", "website": "https://example.test"}]
    decisions = [{"Reason": "  =2+2", "Decision": "rejected"}]
    meta = {"run_id": "=INDIRECT(A1)", "output_dir": str(tmp_path)}
    import copy
    before = copy.deepcopy((accepted, rejected, raw, decisions, meta))
    write_outputs(tmp_path, accepted, rejected, meta, raw_candidates=raw, decision_log=decisions)
    assert (accepted, rejected, raw, decisions, meta) == before

    checks = [
        ("Final_POIs", "Full Name", "=HYPERLINK"),
        ("Final_POIs", "Company / Organisation", "+SUM"),
        ("Rejected_Log", "reason", "@RISK"),
        ("Rejected_Log", "name", "-1+2"),
        ("Raw_Apollo_Search", "name", "\t=SUM"),
        ("Decision_Audit", "Reason", "  =2+2"),
        ("Run_Metadata", "run_id", "=INDIRECT"),
    ]
    book = load_workbook(tmp_path / "offsetx_final_pois_with_emails.xlsx", data_only=False)
    for sheet_name, heading, raw_value in checks:
        sheet = book[sheet_name]
        columns = {cell.value: cell.column for cell in sheet[1]}
        cell = sheet.cell(2, columns[heading])
        assert cell.data_type == "s", (sheet_name, heading, cell.data_type)
        assert str(cell.value).startswith("'" + raw_value), (sheet_name, heading, cell.value)

    report_csv = tmp_path / "offsetx_rejected_duplicate_conflict_log.csv"
    with report_csv.open(encoding="utf-8", newline="") as fp:
        saved = next(csv.DictReader(fp))
    assert saved["reason"].startswith("'@RISK")
    assert saved["name"].startswith("'-1+2")



def test_A19_invalid_openxml_controls_do_not_crash_human_exports_or_change_source(
    tmp_path: Path,
):
    """D-518: hostile source text must not break XLSX generation or run formulas."""
    import copy

    accepted = [{
        "Full Name": "Person\x00Zero",
        "Notes": "\x0b=HYPERLINK(\"https://attacker.invalid\",\"Open\")",
        "Email": "safe@example.test",
        "Overall Score": 42,
    }]
    rejected = [{"reason": "\x1f+SUM(1,2)", "name": "normal"}]
    raw = [{"name": "Info\x0cmore"}]
    decision = [{"Reason": "Invalid\x0etext", "Decision": "rejected"}]
    meta = {"run_id": "r\x07-123", "output_dir": str(tmp_path)}
    original = copy.deepcopy((accepted, rejected, raw, decision, meta))

    write_outputs(
        tmp_path, accepted, rejected, meta, raw_candidates=raw, decision_log=decision,
    )
    assert (accepted, rejected, raw, decision, meta) == original

    workbook = load_workbook(
        tmp_path / "offsetx_final_pois_with_emails.xlsx", data_only=False,
    )
    expected = (
        ("Final_POIs", "Full Name", r"Person\x00Zero"),
        ("Final_POIs", "Notes", r"\x0b=HYPERLINK"),
        ("Rejected_Log", "reason", r"\x1f+SUM"),
        ("Raw_Apollo_Search", "name", r"Info\x0cmore"),
        ("Decision_Audit", "Reason", r"Invalid\x0etext"),
        ("Run_Metadata", "run_id", r"r\x07-123"),
    )
    for sheet_name, column, prefix in expected:
        sheet = workbook[sheet_name]
        headers = {cell.value: cell.column for cell in sheet[1]}
        cell = sheet.cell(2, headers[column])
        assert cell.data_type == "s", (sheet_name, column, cell.value)
        assert str(cell.value).startswith(prefix), (sheet_name, column, cell.value)

    score_col = {
        cell.value: cell.column for cell in workbook["Final_POIs"][1]
    }["Overall Score"]
    assert workbook["Final_POIs"].cell(2, score_col).value == 42

    # CSV report mirrors the same display-safe representation.
    with (tmp_path / "offsetx_final_pois_with_emails.csv").open(
        newline="", encoding="utf-8",
    ) as handle:
        row = next(csv.DictReader(handle))
    assert row["Full Name"] == r"Person\x00Zero"
    assert row["Notes"].startswith(r"\x0b=HYPERLINK")

    # Structured source metadata remains exact, including control characters.
    import json
    persisted_meta = json.loads((tmp_path / "run_meta.json").read_text())
    assert persisted_meta == meta


def test_A19_control_character_escape_is_readable_and_only_at_export_boundary():
    """D-518: do not create actual Excel-forbidden characters or mutate numbers."""
    for invalid in ("\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x1f"):
        safe = spreadsheet_safe_cell("field" + invalid + "value")
        assert safe == "field" + f"\\x{ord(invalid):02x}" + "value"
        assert invalid not in safe
    assert spreadsheet_safe_cell(10) == 10
    assert spreadsheet_safe_cell(True) is True
    assert spreadsheet_safe_cell(None) is None
    assert spreadsheet_safe_cell("=2+2") == "'=2+2"
    assert spreadsheet_safe_cell(" \t=2+2") == "' \t=2+2"
    assert spreadsheet_safe_cell("ordinary") == "ordinary"



def test_A19_untrusted_column_names_are_never_spreadsheet_formulas(tmp_path: Path):
    """D-519: pandas.map only guards values, while headers can be raw API keys."""
    hostile = '=HYPERLINK("https://attacker.invalid","click")'
    original = [{"=HYPERLINK(\"https://attacker.invalid\",\"click\")": "first",
                 "'=HYPERLINK(\"https://attacker.invalid\",\"click\")": "second",
                 "\x0b=SUM(1,2)": "third"}]
    write_outputs(
        tmp_path, [], [], {"run_id": "audit-header", "output_dir": str(tmp_path)},
        raw_candidates=original,
    )
    assert list(original[0]) == [hostile, "'" + hostile, "\x0b=SUM(1,2)"]

    sheet = load_workbook(
        tmp_path / "offsetx_final_pois_with_emails.xlsx", data_only=False,
    )["Raw_Apollo_Search"]
    headers = [cell.value for cell in sheet[1]]
    assert len(headers) == len(set(headers)), "Escaping must not merge unrelated fields"
    assert "'=HYPERLINK" in headers[0]
    assert headers[0].startswith("'=HYPERLINK")
    assert headers[1].startswith("'=HYPERLINK")
    assert headers[1] != headers[0]
    assert headers[2].startswith(r"\x0b=SUM")
    assert all(cell.data_type != "f" for cell in sheet[1])
    assert [sheet.cell(2, i).value for i in (1, 2, 3)] == [
        "first", "second", "third",
    ]

    # A CSV reader must retain all three data fields under distinct safe names.
    with (tmp_path / "offsetx_apollo_raw_search_candidates.csv").open(
        newline="", encoding="utf-8",
    ) as handle:
        rows = csv.DictReader(handle)
        assert rows.fieldnames == headers
        assert list(next(rows).values()) == ["first", "second", "third"]


def test_A19_column_name_safety_does_not_rename_original_frame():
    """The internal source keys still drive ledgers and programme logic."""
    original = pd.DataFrame([{"=SUM(1,1)": 5, "'=SUM(1,1)": 6}])
    safe = spreadsheet_safe_frame(original)
    assert list(original.columns) == ["=SUM(1,1)", "'=SUM(1,1)"]
    assert list(safe.columns) == ["'=SUM(1,1)", "'=SUM(1,1) [2]"]
    assert list(safe.iloc[0]) == [5, 6]
