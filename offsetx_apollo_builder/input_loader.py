"""Load and normalize existing POI CSV/XLSX files for Apollo email enrichment."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .dedupe import norm_domain, norm_email, norm_linkedin, norm_text, split_name
from .locked_categories import normalize_category

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "source_row_number": ("source row number", "row number", "row", "sr no", "s no"),
    "apollo_id": ("apollo person id", "apollo id", "person id", "id"),
    "full_name": ("full name", "name", "person name", "contact name"),
    "first_name": ("first name", "firstname"),
    "last_name": ("last name", "lastname"),
    "title": ("position / title", "title", "job title", "position", "designation", "role"),
    "company": (
        "company / organisation",
        "company / organization",
        "company name",
        "company",
        "organisation name",
        "organization name",
        "organisation",
        "organization",
        "employer name",
        "employer",
        "firm name",
        "firm",
        "account name",
    ),
    "company_domain": ("company domain", "domain", "website", "website url", "company website", "organization domain"),
    "linkedin_url": ("linkedin url or linkedin search route", "linkedin url", "person linkedin url", "linkedin", "linkedin profile"),
    "email": ("email", "work email", "business email", "verified email"),
    "email_status": ("email status", "email_status"),
    "category": ("category", "locked category", "apollo search category", "stakeholder category"),
    "country": ("country / region", "country", "region"),
    "city": ("city",),
    "state": ("state", "state / province"),
    "seniority": ("seniority level", "seniority"),
    "organization_size": ("organisation size", "organization size", "company size", "employees"),
    "industry": ("industry",),
}


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _canonicalize_header(header: object) -> str:
    text = _clean_cell(header).lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_lookup(columns: list[object]) -> dict[str, str]:
    normalized_to_original = {_canonicalize_header(c): str(c) for c in columns}
    out: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _canonicalize_header(alias)
            if key in normalized_to_original:
                out[canonical] = normalized_to_original[key]
                break
    return out


def read_input_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    raise ValueError(f"Unsupported input type: {path}. Use CSV, XLSX, or XLS.")


def _valid_linkedin_url(value: str) -> str:
    text = _clean_cell(value)
    if not text:
        return ""
    low = text.lower()
    if "linkedin.com/in/" not in low and "linkedin.com/pub/" not in low:
        return ""
    return text


def normalize_input_rows(df: pd.DataFrame, *, source_file: Path, default_category: str) -> list[dict[str, Any]]:
    lookup = _alias_lookup(list(df.columns))
    rows: list[dict[str, Any]] = []

    def get(row: dict[str, Any], canonical: str) -> str:
        original = lookup.get(canonical)
        if not original:
            return ""
        return _clean_cell(row.get(original, ""))

    for idx, raw in enumerate(df.to_dict(orient="records"), start=1):
        full_name = get(raw, "full_name")
        first_name = get(raw, "first_name")
        last_name = get(raw, "last_name")
        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()
        if full_name and (not first_name or not last_name):
            guessed_first, guessed_last = split_name(full_name)
            first_name = first_name or guessed_first
            last_name = last_name or guessed_last

        company = get(raw, "company")
        title = get(raw, "title")
        linkedin = _valid_linkedin_url(get(raw, "linkedin_url"))
        email = norm_email(get(raw, "email"))
        company_domain = norm_domain(get(raw, "company_domain"))
        category = normalize_category(get(raw, "category"), default=default_category)

        rows.append({
            "source_file": str(source_file),
            "source_file_name": source_file.name,
            "source_row_number": get(raw, "source_row_number") or str(idx),
            "id": norm_text(get(raw, "apollo_id")),
            "apollo_id": norm_text(get(raw, "apollo_id")),
            "first_name": first_name,
            "last_name": last_name,
            "name": full_name or f"{first_name} {last_name}".strip(),
            "title": title,
            "organization_name": company,
            "organization_domain": company_domain,
            "linkedin_url": linkedin,
            "email": email,
            "email_status": get(raw, "email_status"),
            "category": category,
            "country": get(raw, "country"),
            "city": get(raw, "city"),
            "state": get(raw, "state"),
            "seniority": get(raw, "seniority"),
            "organization_size": get(raw, "organization_size"),
            "industry": get(raw, "industry"),
            "has_email": bool(email),
            "input_identity_key": "||".join([
                norm_text(full_name),
                norm_text(company),
                norm_text(title),
                norm_linkedin(linkedin),
            ]),
            "raw_input_json": raw,
        })
    return rows


def load_existing_pois(path: Path, *, default_category: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    df = read_input_table(path)
    rows = normalize_input_rows(df, source_file=path, default_category=default_category)
    return df, rows
