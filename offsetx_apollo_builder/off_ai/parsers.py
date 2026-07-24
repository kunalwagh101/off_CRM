from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

from ..outreach.models import clean_text, normalize_email


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SUPPORTED_INTAKE_SUFFIXES = {".csv", ".xlsx", ".xls", ".pdf", ".txt", ".md"}

ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": (
        "full name",
        "name",
        "person",
        "person name",
        "contact",
        "contact name",
        "poi",
        "poi name",
        "recipient name",
    ),
    "first_name": ("first name", "firstname", "given name"),
    "last_name": ("last name", "lastname", "surname", "family name"),
    "email": (
        "email",
        "email address",
        "work email",
        "business email",
        "recipient",
        "recipient email",
        "to",
    ),
    "company": (
        "company",
        "company name",
        "organisation",
        "organization",
        "employer",
        "account",
    ),
    "title": ("title", "job title", "role", "position", "designation"),
    "linkedin_url": ("linkedin", "linkedin url", "linkedin profile"),
    "public_hook": ("public hook", "hook", "personalisation", "personalization"),
    "hook_source": ("hook source", "source url", "public source", "evidence url"),
    "subject": ("subject", "email subject", "subject line"),
    "body": ("body", "email body", "message", "email copy", "draft"),
    "category": ("category", "segment", "stakeholder category"),
}


def _canonical(value: Any) -> str:
    text = clean_text(value).lower().replace("&", "and")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _lookup(columns: list[Any]) -> dict[str, str]:
    available = {_canonical(column): str(column) for column in columns}
    result: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            original = available.get(_canonical(alias))
            if original is not None:
                result[field] = original
                break
    return result


def _header_score(values: list[Any]) -> int:
    canonical = {_canonical(value) for value in values}
    aliases = {
        _canonical(alias)
        for values_for_field in ALIASES.values()
        for alias in values_for_field
    }
    return len(canonical & aliases)


def _spreadsheet_table(path: Path) -> tuple[pd.DataFrame, int, str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw: pd.DataFrame | None = None
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                raw = pd.read_csv(
                    path,
                    dtype=str,
                    keep_default_na=False,
                    header=None,
                    encoding=encoding,
                    sep=None,
                    engine="python",
                ).fillna("")
                break
            except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                last_error = exc
        if raw is None:
            raise ValueError(f"CSV could not be read: {last_error}")
        sheet_name = ""
    else:
        workbook = pd.ExcelFile(path)
        best: tuple[int, int, str, pd.DataFrame] | None = None
        for sheet_name in workbook.sheet_names[:20]:
            candidate = pd.read_excel(
                path, sheet_name=sheet_name, dtype=str, header=None
            ).fillna("")
            for index in range(min(15, len(candidate.index))):
                score = _header_score(candidate.iloc[index].tolist())
                marker = (score, -index, sheet_name, candidate)
                if best is None or marker[:2] > best[:2]:
                    best = marker
        if best is None:
            raise ValueError("Workbook contains no readable sheet")
        _, negative_header, sheet_name, raw = best
        header_index = -negative_header
        headers = [
            clean_text(value) or f"Column {position + 1}"
            for position, value in enumerate(raw.iloc[header_index].tolist())
        ]
        table = raw.iloc[header_index + 1 :].copy()
        table.columns = headers
        table = table.loc[
            ~table.apply(lambda row: all(not clean_text(value) for value in row), axis=1)
        ]
        return table.reset_index(drop=True), header_index, sheet_name

    best_index = 0
    best_score = -1
    for index in range(min(15, len(raw.index))):
        score = _header_score(raw.iloc[index].tolist())
        if score > best_score:
            best_score = score
            best_index = index
    headers = [
        clean_text(value) or f"Column {position + 1}"
        for position, value in enumerate(raw.iloc[best_index].tolist())
    ]
    table = raw.iloc[best_index + 1 :].copy()
    table.columns = headers
    table = table.loc[
        ~table.apply(lambda row: all(not clean_text(value) for value in row), axis=1)
    ]
    return table.reset_index(drop=True), best_index, sheet_name


def _text_blocks(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    normalized = text.replace("\r\n", "\n")
    explicit_blocks = re.split(
        r"\n(?=(?:recipient|to|email)\s*:)", normalized, flags=re.IGNORECASE
    )
    for block in explicit_blocks:
        email_match = re.search(
            r"(?im)^(?:recipient|to|email)\s*:\s*(?P<value>[^\n]+)", block
        )
        subject_match = re.search(r"(?im)^subject(?:\s+line)?\s*:\s*(?P<value>[^\n]+)", block)
        body_match = re.search(
            r"(?ims)^(?:body|message|email\s+body)\s*:\s*(?P<value>.+)$", block
        )
        if email_match and subject_match and body_match:
            email_value = EMAIL_RE.search(email_match.group("value"))
            if not email_value:
                continue
            name_match = re.search(r"(?im)^(?:name|recipient name)\s*:\s*(?P<value>[^\n]+)", block)
            company_match = re.search(r"(?im)^company\s*:\s*(?P<value>[^\n]+)", block)
            rows.append(
                {
                    "full_name": clean_text(name_match.group("value")) if name_match else "",
                    "email": email_value.group(0),
                    "company": clean_text(company_match.group("value")) if company_match else "",
                    "subject": clean_text(subject_match.group("value")),
                    "body": body_match.group("value").strip(),
                }
            )
    if rows:
        return rows

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    pipe_lines = [line for line in lines if line.count("|") >= 2]
    if len(pipe_lines) >= 2:
        headers = [part.strip() for part in pipe_lines[0].strip("|").split("|")]
        lookup = _lookup(headers)
        if lookup:
            for line in pipe_lines[1:]:
                values = [part.strip() for part in line.strip("|").split("|")]
                if len(values) != len(headers) or all(set(value) <= {"-", ":"} for value in values):
                    continue
                raw = dict(zip(headers, values))
                rows.append(
                    {
                        field: clean_text(raw.get(column, ""))
                        for field, column in lookup.items()
                    }
                )
    return rows


def _pdf_or_text_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        source = f"{len(reader.pages)} PDF page(s)"
    else:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="cp1252")
        source = "plain text"
    return _text_blocks(text), source


def _normalise_rows(table: pd.DataFrame) -> tuple[list[dict[str, str]], dict[str, str]]:
    mapping = _lookup(list(table.columns))
    rows: list[dict[str, str]] = []
    for raw in table.to_dict(orient="records"):
        result = {
            field: clean_text(raw.get(column, ""))
            for field, column in mapping.items()
        }
        if not result.get("full_name"):
            result["full_name"] = " ".join(
                item
                for item in (result.get("first_name", ""), result.get("last_name", ""))
                if item
            ).strip()
        result["email"] = normalize_email(result.get("email", ""))
        if any(result.values()):
            rows.append(result)
    return rows, mapping


def _public_preview(
    rows: list[dict[str, str]], *, detected_mode: str, limit: int = 12
) -> dict[str, Any]:
    preview: list[dict[str, str]] = []
    for index, row in enumerate(rows[:limit], start=1):
        item = {
            key: value
            for key, value in row.items()
            if key not in {"email"} and value
        }
        if row.get("email"):
            item["recipient_token"] = f"RECIPIENT_{index}"
        preview.append(item)
    return {
        "mode": detected_mode,
        "row_count": len(rows),
        "rows": preview,
        "emails_masked": sum(1 for row in rows if row.get("email")),
    }


def mask_identifiers_for_fallback(text: str) -> tuple[str, dict[str, str]]:
    """Mask e-mail addresses and obvious names before an optional model fallback."""
    replacements: dict[str, str] = {}

    def replace_email(match: re.Match[str]) -> str:
        token = f"RECIPIENT_{len(replacements) + 1}"
        replacements[token] = match.group(0)
        return token

    masked = EMAIL_RE.sub(replace_email, text)
    return masked, replacements


class CampaignIntakeParser:
    """Deterministic-first CSV, workbook, PDF and text inspection."""

    def inspect(
        self,
        path: Path | str,
        *,
        template_text: str = "",
        selected_mode: str = "",
    ) -> dict[str, Any]:
        source = Path(path)
        suffix = source.suffix.lower()
        if suffix not in SUPPORTED_INTAKE_SUFFIXES:
            raise ValueError(
                "Unsupported intake file. Use CSV, XLSX, XLS, PDF, TXT, or Markdown."
            )
        header_row = 0
        sheet_name = ""
        mapping: dict[str, str] = {}
        if suffix in {".csv", ".xlsx", ".xls"}:
            table, header_row, sheet_name = _spreadsheet_table(source)
            rows, mapping = _normalise_rows(table)
            source_description = (
                f"sheet {sheet_name}, header row {header_row + 1}"
                if sheet_name
                else f"header row {header_row + 1}"
            )
        else:
            rows, source_description = _pdf_or_text_rows(source)
            rows = [
                {
                    **row,
                    "email": normalize_email(row.get("email", "")),
                }
                for row in rows
            ]
            mapping = {
                field: field
                for field in {key for row in rows for key in row}
            }

        fields = {key for row in rows for key, value in row.items() if value}
        parse_send_ready = {"email", "subject", "body"}.issubset(fields)
        generate_ready = bool(
            {"full_name", "company", "linkedin_url"} & fields
        ) and bool(template_text.strip())
        ambiguous = parse_send_ready and generate_ready

        if selected_mode:
            if selected_mode not in {"generate", "parse_send"}:
                raise ValueError("selected_mode must be generate or parse_send")
            detected_mode = selected_mode
            ambiguous = False
        elif parse_send_ready and not generate_ready:
            detected_mode = "parse_send"
        elif generate_ready and not parse_send_ready:
            detected_mode = "generate"
        elif ambiguous:
            detected_mode = ""
        elif parse_send_ready:
            detected_mode = "parse_send"
        elif bool({"full_name", "company", "linkedin_url"} & fields):
            detected_mode = "generate" if template_text.strip() else ""
        else:
            detected_mode = ""

        missing: list[str] = []
        if detected_mode == "parse_send":
            missing = [
                field for field in ("email", "subject", "body") if field not in fields
            ]
        elif detected_mode == "generate":
            if not template_text.strip():
                missing.append("template_text")
            if not ({"full_name", "company", "linkedin_url"} & fields):
                missing.append("person identity")
        else:
            if not rows:
                missing.append("readable rows")
            if not parse_send_ready and not template_text.strip():
                missing.append("template or pre-written subject/body")

        row_errors: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=2 + header_row):
            if detected_mode == "parse_send":
                absent = [
                    field for field in ("email", "subject", "body") if not row.get(field)
                ]
            else:
                absent = [] if any(
                    row.get(field) for field in ("full_name", "company", "linkedin_url")
                ) else ["person identity"]
            if absent:
                row_errors.append({"row": index, "missing": absent})

        status = "needs_choice" if ambiguous else "needs_mapping" if missing else "ready"
        return {
            "status": status,
            "detected_mode": detected_mode,
            "ambiguous": ambiguous,
            "mapping": mapping,
            "private_result": {
                "rows": rows,
                "row_count": len(rows),
                "source_description": source_description,
                "row_errors": row_errors,
                "missing": missing,
            },
            "public_preview": {
                **_public_preview(rows, detected_mode=detected_mode),
                "source_description": source_description,
                "row_errors": row_errors[:20],
                "missing": missing,
                "available_fields": sorted(fields),
                "choice_required": ambiguous,
            },
        }
