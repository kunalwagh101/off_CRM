from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from openpyxl import load_workbook

from offsetx_apollo_builder.agent.artifacts import (
    ArtifactError,
    PDF_FILENAME,
    PPTX_FILENAME,
    XLSX_FILENAME,
    write_pdf,
    write_pptx,
    write_xlsx,
)
from offsetx_apollo_builder.artifact_cli import main as artifact_cli
from offsetx_apollo_builder.browser.session import BrowserUnavailable
from offsetx_apollo_builder.browser.trace import Step, Trace


def _trace(tmp_path: Path, *, value: str = "42", quote: str = "Employees: 42") -> Trace:
    trace = Trace.open(tmp_path / "runs", run_id="run_artifacts")
    trace.append(
        Step(kind="run_started", url="https://acme.test/about"),
        captured_text=json.dumps(
            {
                "goal": "Find Acme employee count",
                "step_budget": 4,
                "result_schema": ["employees"],
            }
        ),
    )
    source = trace.append(
        Step(kind="action", detail="read the page", url="https://acme.test/about"),
        captured_text=f"Company: Acme Ltd {quote}",
    )
    trace.append(
        Step(kind="finding", detail="employees recorded", url=source.url),
        captured_text=json.dumps(
            {
                "field": "employees",
                "value": value,
                "kind": "observed",
                "confidence": 0.97,
                "source": {
                    "url": source.url,
                    "captured_at": source.at,
                    "step_id": source.step_id,
                    "screenshot": "",
                    "quote": quote,
                },
            }
        ),
    )
    trace.append(Step(kind="completed", detail="done", url=source.url))
    return trace





def test_artifact_renderer_has_no_model_or_provider_transport():
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "offsetx_apollo_builder"
        / "agent"
        / "artifacts.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert not any(
        name.startswith("offsetx_apollo_builder.ai") or ".ai." in name
        for name in imports
    )
    assert not any(
        token in source.read_text(encoding="utf-8")
        for token in ("EgressBroker(", ".call(", "create_provider(")
    )


def test_xlsx_claim_links_to_the_exact_trace_step(tmp_path):
    trace = _trace(tmp_path)
    path = write_xlsx(trace)

    assert path.name == XLSX_FILENAME
    workbook = load_workbook(path, data_only=False)
    findings = workbook["Findings"]
    trace_sheet = workbook["Trace"]

    assert findings["A2"].value == "employees"
    assert findings["B2"].value == "42"
    assert findings["F2"].value == "step-000001"
    assert findings["F2"].hyperlink is not None
    assert findings["F2"].hyperlink.target == "#'Trace'!A3"
    assert trace_sheet["A3"].value == "step-000001"


def test_xlsx_page_text_cannot_become_a_formula(tmp_path):
    formula = '=HYPERLINK("https://attacker.test","click")'
    trace = _trace(tmp_path, value=formula, quote=formula)
    path = write_xlsx(trace)
    workbook = load_workbook(path, data_only=False)
    findings = workbook["Findings"]

    assert findings["B2"].data_type == "s"
    assert findings["B2"].value == "'" + formula
    assert findings["G2"].value == "'" + formula


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not meaningful on Windows")
def test_xlsx_is_private_because_it_contains_harvested_values(tmp_path):
    path = write_xlsx(_trace(tmp_path))
    assert path.stat().st_mode & 0o777 == 0o600


def test_pptx_is_a_well_formed_office_package_with_provenance(tmp_path):
    trace = _trace(tmp_path, value="42 & growing", quote="<b>Employees: 42</b>")
    path = write_pptx(trace)

    assert path.name == PPTX_FILENAME
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        names = set(package.namelist())
        required = {
            "[Content_Types].xml",
            "_rels/.rels",
            "ppt/presentation.xml",
            "ppt/slideMasters/slideMaster1.xml",
            "ppt/slideLayouts/slideLayout1.xml",
            "ppt/theme/theme1.xml",
            "ppt/slides/slide1.xml",
            "ppt/slides/slide2.xml",
            "ppt/slides/_rels/slide2.xml.rels",
        }
        assert required <= names

        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                ElementTree.fromstring(package.read(name))

        claim_slide = package.read("ppt/slides/slide2.xml").decode("utf-8")
        assert "employees" in claim_slide
        assert "42 &amp; growing" in claim_slide
        assert "step-000001" in claim_slide
        assert "&lt;b&gt;Employees: 42&lt;/b&gt;" in claim_slide
        assert "<b>Employees: 42</b>" not in claim_slide


def test_broken_provenance_refuses_every_artifact_before_writing(tmp_path):
    trace = _trace(tmp_path)
    finding = next(step for step in trace.steps if step.kind == "finding")
    payload = json.loads(trace.captured_text(finding))
    payload["source"]["step_id"] = "step-999999"
    Path(trace.directory, finding.capture).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ArtifactError, match="does not exist"):
        write_xlsx(trace)
    with pytest.raises(ArtifactError, match="does not exist"):
        write_pptx(trace)

    assert not (trace.directory / XLSX_FILENAME).exists()
    assert not (trace.directory / PPTX_FILENAME).exists()


def test_pdf_prints_the_existing_offline_provenance_report(monkeypatch, tmp_path):
    trace = _trace(tmp_path)
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        "offsetx_apollo_builder.agent.artifacts.find_browser",
        lambda _: "/usr/bin/fake-chrome",
    )

    def fake_run(command, **kwargs):
        seen["command"] = list(command)
        html_url = command[-1]
        assert html_url.startswith("file://")
        html_path = Path(html_url.removeprefix("file://"))
        report = html_path.read_text(encoding="utf-8")
        assert "employees" in report
        assert "step step-000001" in report

        output_arg = next(item for item in command if item.startswith("--print-to-pdf="))
        output = Path(output_arg.split("=", 1)[1])
        output.write_bytes(b"%PDF-1.7\n% fake test pdf\n")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(
        "offsetx_apollo_builder.agent.artifacts.subprocess.run",
        fake_run,
    )

    path = write_pdf(trace)
    assert path.name == PDF_FILENAME
    assert path.read_bytes().startswith(b"%PDF-")
    command = seen["command"]
    assert "--disable-background-networking" in command
    assert "--disable-sync" in command
    assert "--no-pdf-header-footer" in command


def test_pdf_missing_browser_fails_with_the_next_action(monkeypatch, tmp_path):
    trace = _trace(tmp_path)

    def missing(_):
        raise BrowserUnavailable("none")

    monkeypatch.setattr(
        "offsetx_apollo_builder.agent.artifacts.find_browser",
        missing,
    )
    with pytest.raises(ArtifactError, match="Install one or pass --browser"):
        write_pdf(trace)


def test_cli_turns_a_real_trace_directory_into_a_sheet(tmp_path, capsys):
    trace = _trace(tmp_path)
    result = artifact_cli(
        ["--run-dir", str(trace.directory), "--format", "xlsx"]
    )

    assert result == 0
    assert (trace.directory / XLSX_FILENAME).exists()
    assert str(trace.directory / XLSX_FILENAME) in capsys.readouterr().out


def test_cli_refuses_a_directory_that_is_not_an_agent_run(tmp_path, capsys):
    result = artifact_cli(["--run-dir", str(tmp_path), "--format", "xlsx"])
    assert result == 2
    assert "No agent trace" in capsys.readouterr().err
