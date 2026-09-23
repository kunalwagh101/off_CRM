"""Portable artifacts from one verified agent trace.  S-07.01.04

No model call happens here. The trace already contains the facts that survived
schema validation, provenance resolution and deterministic claim verification.
Rendering them again through a model would make a verified result less
trustworthy, not more useful.

Three formats, using what the project already owns:

* XLSX: openpyxl is an existing production dependency.
* PPTX: Office Open XML is a ZIP of XML parts, so the standard library is enough
  for the small, deliberately plain deck this story needs.
* PDF: Chromium is already the browser boundary off_CRM depends on; it prints the
  existing escaped, offline HTML report. No second HTML renderer is introduced.

Every claim is refused unless its source step still resolves in the trace.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

from openpyxl import Workbook

from ..browser.session import BrowserUnavailable, find_browser
from ..browser.trace import Trace
from .report import findings as report_findings
from .report import write as write_html_report

XLSX_FILENAME = "report.xlsx"
PPTX_FILENAME = "report.pptx"
PDF_FILENAME = "report.pdf"
SUPPORTED_FORMATS = ("xlsx", "pptx", "pdf")

# Excel treats a leading '=' as a formula and spreadsheet applications also
# recognise the other characters as formula/DDE prefixes in import paths. An
# artifact is a presentation of untrusted web text, not a place for that text to
# become executable.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# XML 1.0 excludes most control characters. Page text is untrusted input, so
# strip only characters the format cannot represent rather than letting the ZIP
# become unreadable.
_INVALID_XML = re.compile(
    "[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
)


class ArtifactError(RuntimeError):
    """A report artifact could not be produced safely."""


@dataclass(frozen=True, slots=True)
class Claim:
    field: str
    value: str
    kind: str
    confidence: float
    source_url: str
    source_step_id: str
    quote: str
    captured_at: str

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Field", self.field),
            ("Value", self.value),
            ("Kind", self.kind),
            ("Confidence", f"{self.confidence:.2f}"),
            ("Source URL", self.source_url),
            ("Trace step", self.source_step_id),
            ("Captured at", self.captured_at),
            ("Quote", self.quote),
        )


def _private(path: Path) -> Path:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _xml(value: object) -> str:
    text = _INVALID_XML.sub("\uFFFD", str(value if value is not None else ""))
    return xml_escape(text, {'"': "&quot;", "'": "&apos;"})


def _cell(value: object) -> object:
    """Literal spreadsheet value; never let page text become executable."""
    if not isinstance(value, str):
        return value
    text = _INVALID_XML.sub("\uFFFD", value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def _goal(trace: Trace) -> str:
    started = next((step for step in trace.read() if step.kind == "run_started"), None)
    if started is None:
        return ""
    try:
        payload = json.loads(trace.captured_text(started) or "{}")
    except ValueError:
        return ""
    return str(payload.get("goal") or "")


def claims(trace: Trace) -> list[Claim]:
    """Verified report findings, with the trace reference re-resolved now.

    The agent already did this when it accepted a finding. Repeating the
    resolution at export is intentional: an artifact copied away from its trace
    must not preserve a claim whose evidence file or step no longer exists.
    """
    items: list[Claim] = []
    for raw in report_findings(trace):
        source = raw.get("source") if isinstance(raw, dict) else None
        if not isinstance(source, dict):
            raise ArtifactError("A report finding has no provenance record.")
        step_id = str(source.get("step_id") or "")
        if not step_id or trace.resolve(step_id) is None:
            raise ArtifactError(
                f"Finding {raw.get('field')!r} names trace step {step_id or '<missing>'!r}, "
                "but that step does not exist. The artifact was not written."
            )
        items.append(
            Claim(
                field=str(raw.get("field") or ""),
                value=str(raw.get("value") or ""),
                kind=str(raw.get("kind") or "observed"),
                confidence=float(raw.get("confidence") or 0.0),
                source_url=str(source.get("url") or ""),
                source_step_id=step_id,
                quote=str(source.get("quote") or ""),
                captured_at=str(source.get("captured_at") or ""),
            )
        )
    return items


def _atomic_workbook(workbook: Workbook, path: Path) -> Path:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        workbook.save(temporary)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return _private(path)


def write_xlsx(trace: Trace) -> Path:
    """One row per claim plus an internal link to the exact trace-step row."""
    items = claims(trace)
    workbook = Workbook()
    findings_sheet = workbook.active
    findings_sheet.title = "Findings"
    trace_sheet = workbook.create_sheet("Trace")

    trace_sheet.append(("Step ID", "Kind", "Detail", "URL", "OK", "At"))
    step_rows: dict[str, int] = {}
    for step in trace.read():
        trace_sheet.append(
            (
                _cell(step.step_id),
                _cell(step.kind),
                _cell(step.detail),
                _cell(step.url),
                bool(step.ok),
                _cell(step.at),
            )
        )
        step_rows[step.step_id] = trace_sheet.max_row

    headers = (
        "Field", "Value", "Kind", "Confidence", "Source URL",
        "Trace Step", "Quote", "Captured At",
    )
    findings_sheet.append(headers)
    for item in items:
        findings_sheet.append(
            (
                _cell(item.field),
                _cell(item.value),
                _cell(item.kind),
                item.confidence,
                _cell(item.source_url),
                _cell(item.source_step_id),
                _cell(item.quote),
                _cell(item.captured_at),
            )
        )
        row = findings_sheet.max_row
        target = step_rows[item.source_step_id]
        link_cell = findings_sheet.cell(row=row, column=6)
        link_cell.hyperlink = f"#'Trace'!A{target}"
        link_cell.style = "Hyperlink"

    findings_sheet.freeze_panes = "A2"
    trace_sheet.freeze_panes = "A2"
    findings_sheet.auto_filter.ref = findings_sheet.dimensions
    trace_sheet.auto_filter.ref = trace_sheet.dimensions
    for sheet in (findings_sheet, trace_sheet):
        sheet.column_dimensions["A"].width = 24
        sheet.column_dimensions["B"].width = 48
        sheet.column_dimensions["C"].width = 18
        sheet.column_dimensions["D"].width = 16
        sheet.column_dimensions["E"].width = 48
        sheet.column_dimensions["F"].width = 22
        sheet.column_dimensions["G"].width = 60
        sheet.column_dimensions["H"].width = 28

    workbook.properties.title = f"off_CRM run {trace.run_id}"
    workbook.properties.subject = _goal(trace)
    workbook.properties.creator = "off_CRM"
    return _atomic_workbook(workbook, Path(trace.directory) / XLSX_FILENAME)


def _paragraph(text: object, *, size: int = 1800, bold: bool = False) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        "<a:p><a:r>"
        f'<a:rPr lang="en-US" sz="{int(size)}"{bold_attr}/>'
        f"<a:t>{_xml(text)}</a:t>"
        "</a:r><a:endParaRPr lang=\"en-US\"/></a:p>"
    )


def _text_box(
    *,
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: Iterable[str],
) -> str:
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{_xml(name)}"/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/>'
        "</p:nvSpPr>"
        "<p:spPr>"
        "<a:xfrm>"
        f'<a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'
        "</a:xfrm>"
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "<a:noFill/><a:ln><a:noFill/></a:ln>"
        "</p:spPr>"
        "<p:txBody><a:bodyPr wrap=\"square\"><a:normAutofit/></a:bodyPr>"
        "<a:lstStyle/>"
        + "".join(paragraphs)
        + "</p:txBody></p:sp>"
    )


def _slide(title: str, lines: Iterable[tuple[str, str]]) -> str:
    title_box = _text_box(
        shape_id=2,
        name="Title",
        x=685800,
        y=365760,
        cx=10820400,
        cy=731520,
        paragraphs=(_paragraph(title, size=2800, bold=True),),
    )
    body = []
    for label, value in lines:
        body.append(_paragraph(label, size=1200, bold=True))
        body.append(_paragraph(value or "—", size=1650))
    body_box = _text_box(
        shape_id=3,
        name="Body",
        x=685800,
        y=1219200,
        cx=10820400,
        cy=4876800,
        paragraphs=body or (_paragraph("No verified findings.", size=1800),),
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/>"
        "</p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/>"
        "</a:xfrm></p:grpSpPr>"
        + title_box
        + body_box
        + "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


def _theme() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="off_CRM">
<a:themeElements>
<a:clrScheme name="off_CRM">
<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="1F1F1F"/></a:dk2><a:lt2><a:srgbClr val="F2F2F2"/></a:lt2>
<a:accent1><a:srgbClr val="4472C4"/></a:accent1><a:accent2><a:srgbClr val="70AD47"/></a:accent2>
<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="ED7D31"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="off_CRM">
<a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
</a:fontScheme>
<a:fmtScheme name="off_CRM">
<a:fillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
</a:fillStyleLst>
<a:lnStyleLst>
<a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
</a:lnStyleLst>
<a:effectStyleLst>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle>
</a:effectStyleLst>
<a:bgFillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
</a:bgFillStyleLst>
</a:fmtScheme>
</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"""


def _pptx_bytes(trace: Trace, items: list[Claim]) -> bytes:
    slides: list[str] = [
        _slide(
            f"Run {trace.run_id}",
            (
                ("Goal", _goal(trace) or "No goal recorded."),
                ("Verified findings", str(len(items))),
                ("Provenance", "Every claim slide names the exact trace step that supports it."),
            ),
        )
    ]
    for item in items:
        slides.append(_slide(item.field or "Finding", item.rows()))

    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, len(slides) + 1)
    )
    slide_ids = "".join(
        f'<p:sldId id="{255 + index}" r:id="rId{index + 1}"/>'
        for index in range(1, len(slides) + 1)
    )
    presentation_rels = [
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
    ]
    presentation_rels.extend(
        f'<Relationship Id="rId{index + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{index}.xml"/>'
        for index in range(1, len(slides) + 1)
    )

    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/ppt/presentation.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
            '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
            '<Override PartName="/ppt/theme/theme1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            + slide_overrides
            + "</Types>",
        )
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>",
        )
        package.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{_xml('off_CRM run ' + trace.run_id)}</dc:title>"
            "<dc:creator>off_CRM</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
            "</cp:coreProperties>",
        )
        package.writestr(
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>off_CRM</Application><PresentationFormat>Widescreen</PresentationFormat>"
            f"<Slides>{len(slides)}</Slides></Properties>",
        )
        package.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
            '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
            '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        )
        package.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(presentation_rels)
            + "</Relationships>",
        )
        package.writestr(
            "ppt/slideMasters/slideMaster1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>'
            '</p:grpSpPr></p:spTree></p:cSld>'
            '<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" '
            'accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" '
            'folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>'
            '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>'
            "</p:sldMaster>",
        )
        package.writestr(
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
            "</Relationships>",
        )
        package.writestr(
            "ppt/slideLayouts/slideLayout1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
            '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>'
            '</p:grpSpPr></p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>',
        )
        package.writestr(
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
            "</Relationships>",
        )
        package.writestr("ppt/theme/theme1.xml", _theme())
        for index, slide in enumerate(slides, 1):
            package.writestr(f"ppt/slides/slide{index}.xml", slide)
            package.writestr(
                f"ppt/slides/_rels/slide{index}.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                "</Relationships>",
            )
    return output.getvalue()


def write_pptx(trace: Trace) -> Path:
    items = claims(trace)
    path = Path(trace.directory) / PPTX_FILENAME
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(_pptx_bytes(trace, items))
        with zipfile.ZipFile(temporary, "r") as package:
            bad = package.testzip()
            if bad:
                raise ArtifactError(f"The PPTX ZIP is corrupt at {bad}.")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return _private(path)


def write_pdf(trace: Trace, *, browser_path: str = "", timeout_seconds: int = 60) -> Path:
    """Print the existing escaped offline report through installed Chromium."""
    # Validate provenance before creating/replacing either artifact.
    claims(trace)
    html_path = write_html_report(trace).resolve()
    path = Path(trace.directory) / PDF_FILENAME
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        executable = find_browser(browser_path)
    except BrowserUnavailable as exc:
        raise ArtifactError(
            "PDF generation needs Chrome, Edge, Brave or Chromium. "
            "Install one or pass --browser with its executable path."
        ) from exc

    try:
        temporary.unlink()
    except OSError:
        pass

    with tempfile.TemporaryDirectory(prefix="off-crm-pdf-") as profile:
        command = [
            executable,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={temporary.resolve()}",
            "--no-pdf-header-footer",
            html_path.as_uri(),
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=max(5, int(timeout_seconds)),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ArtifactError(f"Chromium could not render the PDF: {exc}") from exc

    if completed.returncode != 0 or not temporary.exists():
        detail = (completed.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else "no diagnostic output"
        raise ArtifactError(
            f"Chromium did not produce the PDF (exit {completed.returncode}): {tail}"
        )
    if not temporary.read_bytes().startswith(b"%PDF-"):
        raise ArtifactError("Chromium produced a file that is not a PDF.")

    os.replace(temporary, path)
    return _private(path)


def write_artifact(
    trace: Trace,
    format_name: str,
    *,
    browser_path: str = "",
) -> Path:
    format_name = str(format_name or "").strip().lower()
    if format_name == "xlsx":
        return write_xlsx(trace)
    if format_name == "pptx":
        return write_pptx(trace)
    if format_name == "pdf":
        return write_pdf(trace, browser_path=browser_path)
    raise ArtifactError(
        f"Unsupported artifact format {format_name!r}. "
        f"Choose one of: {', '.join(SUPPORTED_FORMATS)}."
    )
