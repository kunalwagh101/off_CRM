"""Two-mode campaign intake (§4D).

The property this file exists to protect is not a parsing one.

A contact list is the densest concentration of exactly the material the whole
system guards: real names, real addresses, real companies. If a model parsed it,
that one feature would leak more than every other path combined. So parsing is
deterministic and local, and the structural test at the bottom is the one that
matters most — it fails the build if this module ever gains a route to a
provider.

The second property is honesty about PDFs. A CSV column is exact. A PDF is a
picture of a table, and which name belongs to which address is guessed from the
layout. Guessing wrong means emailing a real person by the wrong name, so PDF
rows are always flagged and can never be sent unreviewed.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from offsetx_apollo_builder.intake import (
    GenerateBrief,
    IntakeError,
    IntakeMode,
    describe_modes,
    extract_pdf_lines,
    parse_file,
    supported_suffixes,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder"


def _write_pdf(path: Path, lines: list[str]) -> Path:
    """A minimal one-page PDF with a real text layer.

    Built by hand rather than with a PDF library so the test exercises genuine
    extraction rather than a mock of it, and so the suite gains no dependency
    purely for testing.
    """
    text = "BT /F1 10 Tf 40 750 Td 14 TL\n"
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        text += f"({escaped}) Tj T*\n"
    text += "ET"
    stream = text.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    path.write_bytes(bytes(out))
    return path


@pytest.fixture()
def csv_file(tmp_path) -> Path:
    path = tmp_path / "list.csv"
    path.write_text(
        "Full Name,Email,Company,Title\n"
        "Ana Silva,ana@acme.example,Acme GmbH,CTO\n"
        "Tom Berg,tom@nordkap.example,Nordkap,Ops Director\n"
        "Nobody Here,,Ghost Ltd,CEO\n"
    )
    return path


# ── the rule that matters most ─────────────────────────────────────────────


def test_intake_can_never_reach_a_model():
    """A contact list is the densest concentration of protected material in the
    system. This module must have no route to a provider, and living outside the
    `ai` package is the structural reminder of that."""
    source = (PACKAGE_ROOT / "intake.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    banned = {"requests", "httpx", "openai", "socket", "urllib", "urllib.request"}
    assert not (imported & banned), f"intake imports transport: {imported & banned}"
    assert not any(name.startswith("ai") or ".ai" in name for name in imported), (
        f"intake reaches the AI module: {imported}"
    )
    assert not any("create_provider" in name for name in imported)


def test_intake_lives_outside_the_ai_package():
    """If it ever moves inside `ai/`, the reminder is gone."""
    assert (PACKAGE_ROOT / "intake.py").exists()
    assert not (PACKAGE_ROOT / "ai" / "intake.py").exists()


# ── the two modes ──────────────────────────────────────────────────────────


def test_both_modes_explain_themselves():
    modes = {item["value"]: item for item in describe_modes()}
    assert set(modes) == {"generate", "parse"}
    for mode in modes.values():
        assert mode["label"] and mode["description"]
    # The privacy promise is the thing worth saying on the upload screen.
    assert "no AI model sees the file" in modes["parse"]["description"]


def test_supported_types_are_listed():
    assert set(supported_suffixes()) == {".csv", ".xls", ".xlsx", ".pdf"}


# ── tables are exact ───────────────────────────────────────────────────────


def test_a_csv_reads_every_field(csv_file):
    result = parse_file(csv_file)
    assert result.mode is IntakeMode.PARSE
    assert result.parsed_with == "table"
    first = result.rows[0]
    assert first.email == "ana@acme.example"
    assert first.full_name == "Ana Silva"
    assert first.company == "Acme GmbH"
    assert first.title == "CTO"


def test_a_csv_needs_no_review_because_a_column_is_a_column(csv_file):
    result = parse_file(csv_file)
    assert result.review_rows == []
    assert result.ready_to_send is True


def test_a_row_with_no_address_is_rejected_with_a_reason(csv_file):
    result = parse_file(csv_file)
    assert len(result.rows) == 2
    assert result.rejected[0]["reason"] == "no_email"
    assert "nothing can be sent to it" in result.rejected[0]["detail"]


def test_a_table_with_no_email_column_says_what_to_fix(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Name,Company\nAna Silva,Acme\n")
    result = parse_file(path)
    assert result.rows == []
    assert result.ready_to_send is False
    assert any("email" in warning.lower() for warning in result.warnings)


def test_the_field_mapping_matches_what_the_loader_emits(csv_file):
    """Regression. The loader emits the CRM's own field names — `name` and
    `organization_name` — not the header text. Reading the wrong keys produced
    rows with no name at all, which looked like a parsing failure and was really
    a mapping one."""
    result = parse_file(csv_file)
    assert all(row.full_name for row in result.rows)
    assert all(row.company for row in result.rows)


# ── PDFs, and being honest about them ──────────────────────────────────────


@pytest.fixture()
def contact_pdf(tmp_path) -> Path:
    return _write_pdf(
        tmp_path / "contacts.pdf",
        [
            "Contact List - Q3",
            "Name Email Company",
            "Ana Silva ana@acme.example Acme GmbH",
            "Tom Berg",
            "tom@nordkap.example Nordkap",
            "loner@ghost.example",
        ],
    )


def test_a_pdf_yields_its_addresses(contact_pdf):
    result = parse_file(contact_pdf)
    assert result.parsed_with == "pdf"
    found = {row.email for row in result.rows}
    assert found == {
        "ana@acme.example",
        "tom@nordkap.example",
        "loner@ghost.example",
    }


def test_every_pdf_row_needs_review_and_none_can_be_sent(contact_pdf):
    """The central honesty property. Guessing which name belongs to which
    address, and being wrong, means emailing a real person by the wrong name."""
    result = parse_file(contact_pdf)
    assert all(row.needs_review for row in result.rows)
    assert result.ready_to_send is False
    assert "need checking before anything is sent" in result.summary()


def test_a_name_on_the_same_line_is_picked_up(contact_pdf):
    result = parse_file(contact_pdf)
    ana = next(row for row in result.rows if row.email == "ana@acme.example")
    assert ana.full_name == "Ana Silva"
    assert ana.first_name == "Ana"


def test_a_name_on_the_line_above_is_picked_up_and_said_so(contact_pdf):
    """The other layout a printed table uses. The note matters as much as the
    name — the owner should know it was inferred."""
    result = parse_file(contact_pdf)
    tom = next(row for row in result.rows if row.email == "tom@nordkap.example")
    assert tom.full_name == "Tom Berg"
    assert any("line above" in note for note in tom.notes)


def test_an_address_with_no_name_nearby_reports_that_rather_than_guessing(contact_pdf):
    """A wrong name is worse than a missing one: it gets sent to a real person."""
    result = parse_file(contact_pdf)
    loner = next(row for row in result.rows if row.email == "loner@ghost.example")
    assert loner.full_name == ""
    assert any("no name found" in note for note in loner.notes)


def test_a_column_header_is_not_mistaken_for_a_person(contact_pdf):
    result = parse_file(contact_pdf)
    names = {row.full_name for row in result.rows}
    assert "Name Email Company" not in names
    assert "Contact List" not in names


def test_the_same_address_twice_is_read_once(tmp_path):
    path = _write_pdf(
        tmp_path / "dupes.pdf",
        ["Ana Silva ana@acme.example", "Ana Silva ana@acme.example"],
    )
    assert len(parse_file(path).rows) == 1


def test_a_pdf_with_no_text_layer_says_it_is_probably_a_scan(tmp_path):
    """No OCR here. A scanned page has no text, and pretending otherwise would
    produce confident nonsense."""
    path = _write_pdf(tmp_path / "blank.pdf", [])
    result = parse_file(path)
    assert result.rows == []
    assert any("scan" in warning.lower() for warning in result.warnings)


def test_a_pdf_with_text_but_no_addresses_says_so(tmp_path):
    path = _write_pdf(tmp_path / "prose.pdf", ["Minutes of the meeting.", "Nothing here."])
    result = parse_file(path)
    assert result.rows == []
    assert any("No email addresses" in warning for warning in result.warnings)


def test_page_numbers_are_recorded_so_a_row_can_be_found_again(contact_pdf):
    result = parse_file(contact_pdf)
    assert all(row.page == 1 for row in result.rows)


def test_extraction_is_capped_so_a_printed_database_is_not_scraped(contact_pdf):
    assert extract_pdf_lines(contact_pdf, max_pages=0) == []


# ── refusals ───────────────────────────────────────────────────────────────


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(IntakeError, match="no file at"):
        parse_file(tmp_path / "nope.csv")


def test_an_unsupported_type_lists_what_is_supported(tmp_path):
    path = tmp_path / "notes.docx"
    path.write_text("x")
    with pytest.raises(IntakeError, match="cannot read"):
        parse_file(path)


def test_a_file_that_is_not_really_a_pdf_is_refused(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("this is not a pdf at all")
    with pytest.raises(IntakeError, match="could not be opened as a PDF"):
        parse_file(path)


# ── generate mode ──────────────────────────────────────────────────────────


def test_a_brief_needs_a_description():
    assert "Say who you want to reach" in GenerateBrief(description="  ").validate()[0]
    assert GenerateBrief(description="Importers in Rotterdam").validate() == []


def test_a_brief_keeps_the_batch_reviewable():
    assert GenerateBrief(description="x", limit=0).validate()
    assert any(
        "5,000 or fewer" in problem
        for problem in GenerateBrief(description="x", limit=99999).validate()
    )


def test_a_brief_is_plain_data():
    """No contact in a generated list is invented by a model — the data source
    produces them. The brief is only the search."""
    brief = GenerateBrief(description="Importers", country="NL", limit=50)
    payload = brief.to_dict()
    assert payload["description"] == "Importers"
    assert all(isinstance(value, (str, int)) for value in payload.values())


# ── the summary the owner reads ────────────────────────────────────────────


def test_the_summary_says_what_happens_next(csv_file, contact_pdf):
    assert "ready to review" in parse_file(csv_file).summary()
    assert "need checking" in parse_file(contact_pdf).summary()


def test_the_result_serialises_for_the_screen(csv_file):
    payload = parse_file(csv_file).to_dict()
    assert payload["counts"] == {"total": 2, "usable": 2, "needs_review": 0}
    assert payload["ready_to_send"] is True
    assert payload["mode"] == "parse"
