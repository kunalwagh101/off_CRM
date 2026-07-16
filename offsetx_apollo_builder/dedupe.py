"""Deduplication and exclusion logic for OffsetX Apollo POI building."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd
from rapidfuzz import fuzz

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
APOLLO_ID_RE = re.compile(r"\b[a-f0-9]{24}\b", re.I)
SUPPORTED_EXCLUSION_SUFFIXES = {".csv", ".xlsx", ".xls", ".pdf"}



def norm_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def norm_domain(value: object) -> str:
    text = norm_text(value)
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    text = text.split("/")[0].split("?")[0].strip()
    return text


def norm_email(value: object) -> str:
    return norm_text(value)


def norm_linkedin(value: object) -> str:
    text = norm_text(value)
    text = text.replace("https://", "").replace("http://", "").replace("www.", "")
    text = text.rstrip("/")
    return text


def name_company_key(name: object, company: object) -> str:
    return f"{norm_text(name)}||{norm_text(company)}"


def split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


@dataclass
class ExclusionSet:
    apollo_ids: set[str] = field(default_factory=set)
    emails: set[str] = field(default_factory=set)
    linkedin_urls: set[str] = field(default_factory=set)
    name_company_pairs: set[str] = field(default_factory=set)
    company_title_pairs: set[str] = field(default_factory=set)
    raw_rows_loaded: int = 0

    def add_record(self, row: dict[str, object]) -> None:
        def pick(*names: str) -> str:
            for name in names:
                for k, v in row.items():
                    if norm_text(k) == norm_text(name):
                        val = str(v).strip() if v is not None else ""
                        if val and val.lower() != "nan":
                            return val
            return ""

        apollo_blob = " ".join(str(v) for v in row.values() if v is not None)
        for match in APOLLO_ID_RE.findall(apollo_blob):
            self.apollo_ids.add(match.lower())

        for match in EMAIL_RE.findall(apollo_blob):
            self.emails.add(match.lower())

        linkedin = pick("linkedin", "linkedin url", "person linkedin url", "linkedin search route")
        if linkedin:
            self.linkedin_urls.add(norm_linkedin(linkedin))

        first = pick("first name", "firstname")
        last = pick("last name", "lastname")
        full = pick("full name", "name", "person name", "contact name")
        if not full:
            full = f"{first} {last}".strip()

        company = pick("company", "company/organisation", "company / organisation", "organization", "organization name", "organisation", "account name")
        title = pick("title", "job title", "position", "position / title")

        if full and company:
            self.name_company_pairs.add(name_company_key(full, company))
        if company and title:
            self.company_title_pairs.add(f"{norm_text(company)}||{norm_text(title)}")

    def is_duplicate_candidate(self, candidate: dict[str, object], fuzzy_company_title_threshold: int = 96) -> tuple[bool, str]:
        cid = norm_text(candidate.get("id") or candidate.get("apollo_id"))
        if cid and cid in self.apollo_ids:
            return True, "duplicate_apollo_id"

        email = norm_email(candidate.get("email"))
        if email and email in self.emails:
            return True, "duplicate_email"

        linkedin = norm_linkedin(candidate.get("linkedin_url"))
        if linkedin and linkedin in self.linkedin_urls:
            return True, "duplicate_linkedin"

        full_name = candidate.get("name") or f"{candidate.get('first_name','')} {candidate.get('last_name','')}".strip()
        company = candidate.get("organization_name") or candidate.get("company") or candidate.get("organization")
        title = candidate.get("title")

        if full_name and company and name_company_key(full_name, company) in self.name_company_pairs:
            return True, "duplicate_name_company"

        if company and title:
            exact = f"{norm_text(company)}||{norm_text(title)}"
            if exact in self.company_title_pairs:
                return True, "duplicate_company_title"
            # Fuzzy guard catches tiny title/company formatting changes.
            for existing in self.company_title_pairs:
                if fuzz.ratio(existing, exact) >= fuzzy_company_title_threshold:
                    return True, "near_duplicate_company_title"

        return False, "fresh"


def read_any_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    if suffix == ".pdf":
        # Best-effort PDF parser: enough for text-review PDFs, not reliable for scanned PDFs.
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        rows = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                if line.strip():
                    rows.append({"source_pdf_page": str(page_no), "text": line.strip()})
        return pd.DataFrame(rows)
    raise ValueError(f"Unsupported exclusion file type: {path}")


def is_supported_exclusion_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in SUPPORTED_EXCLUSION_SUFFIXES
        and not path.name.startswith("~$")
    )


def discover_exclusion_files(
    explicit_paths: Iterable[Path] | None = None,
    exclusion_dir: Path | None = None,
    include_previous_outputs: bool = True,
    project_root: Path | None = None,
) -> list[Path]:
    """Collect exclusion files from explicit paths, an old_pois folder, and prior outputs.

    This is intentionally file-based so the operator does not need to keep editing
    the command every time a new old POI CSV/XLSX is added.
    """
    files: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        path = path.expanduser()
        if path.exists():
            try:
                key = str(path.resolve()).lower()
            except Exception:
                key = str(path).lower()
            if key not in seen and is_supported_exclusion_file(path):
                files.append(path)
                seen.add(key)

    for path in explicit_paths or []:
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                add(child)
        else:
            add(path)

    if exclusion_dir and exclusion_dir.exists():
        for child in sorted(exclusion_dir.rglob("*")):
            add(child)

    if include_previous_outputs:
        root = project_root or Path.cwd()
        for child in sorted(root.glob("output*/offsetx_final_pois_with_emails.csv")):
            add(child)
        for child in sorted(root.glob("output*/offsetx_new_accepts_for_exclusion.csv")):
            add(child)

    return files


def build_exclusion_set(paths: Iterable[Path]) -> ExclusionSet:
    exclusion = ExclusionSet()
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        df = read_any_table(path)
        exclusion.raw_rows_loaded += len(df)
        for row in df.to_dict(orient="records"):
            exclusion.add_record(row)
    return exclusion
