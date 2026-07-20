"""Persistent Apollo enrichment-attempt ledger.

The accepted-contact exclusion ledger is not enough for credit protection because
it only remembers contacts that returned an email. This module remembers every
person submitted to Apollo, including no-match and matched-without-email cases.

The ledger is CSV-backed for the current file-based application. It is designed
so the same service can later be moved behind SQLAlchemy without changing the
enrichment pipeline's behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .dedupe import norm_email, norm_linkedin, norm_text

LEDGER_COLUMNS = [
    "Primary Identity Key",
    "All Identity Keys JSON",
    "First Name",
    "Last Name",
    "Full Name",
    "Company / Organisation",
    "Company Domain",
    "LinkedIn URL",
    "Input Apollo Person ID",
    "Returned Apollo Person ID",
    "Returned Email",
    "Email Status",
    "Attempt Status",
    "Match Method",
    "First Attempt Run ID",
    "Last Attempt Run ID",
    "First Attempt At UTC",
    "Last Attempt At UTC",
    "Attempt Count",
    "Source File",
    "Source Row Number",
    "API Batch Credits Reported",
    "API Batch Size",
    "Backfill Source",
    "Last Error",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _person_name(candidate: dict[str, Any]) -> str:
    name = norm_text(candidate.get("name"))
    if name:
        return name
    return norm_text(f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}")


def attempt_identity_keys(candidate: dict[str, Any]) -> list[str]:
    """Return exact, deterministic keys used to prevent repeat Apollo attempts.

    Strong platform keys are preferred, but exact name + company/domain is also
    retained because many imported POI files do not contain LinkedIn or Apollo ID.
    """
    keys: list[str] = []

    apollo_id = norm_text(candidate.get("id") or candidate.get("apollo_id") or candidate.get("person_id"))
    if apollo_id:
        keys.append(f"apollo:{apollo_id}")

    linkedin = norm_linkedin(candidate.get("linkedin_url"))
    if linkedin:
        keys.append(f"linkedin:{linkedin}")

    email = norm_email(candidate.get("email") or candidate.get("work_email"))
    if email:
        keys.append(f"email:{email}")

    name = _person_name(candidate)
    domain = norm_text(candidate.get("organization_domain") or candidate.get("domain"))
    company = norm_text(candidate.get("organization_name") or candidate.get("company"))
    title = norm_text(candidate.get("title"))

    if name and domain:
        keys.append(f"name_domain:{name}||{domain}")
    if name and company:
        keys.append(f"name_company:{name}||{company}")
    if name and company and title:
        keys.append(f"name_company_title:{name}||{company}||{title}")

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(key for key in keys if key and not key.endswith(":")))


def _parse_keys(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            return [str(item) for item in loaded if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [piece.strip() for piece in text.split(";") if piece.strip()]


def _extract_matches(response: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("matches", "people", "persons"):
        value = response.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _pick_historical_match(detail: dict[str, Any], matches: list[dict[str, Any]], index: int) -> tuple[dict[str, Any] | None, str]:
    apollo_id = norm_text(detail.get("id") or detail.get("apollo_id"))
    if apollo_id:
        for match in matches:
            if norm_text(match.get("id") or match.get("person_id")) == apollo_id:
                return match, "apollo_id"

    linkedin = norm_linkedin(detail.get("linkedin_url"))
    if linkedin:
        for match in matches:
            if norm_linkedin(match.get("linkedin_url")) == linkedin:
                return match, "linkedin_url"

    detail_name = _person_name(detail)
    detail_company = norm_text(detail.get("organization_name"))
    for match in matches:
        org = match.get("organization") or {}
        match_candidate = {
            **match,
            "organization_name": org.get("name") or match.get("organization_name"),
        }
        if detail_name and detail_company and _person_name(match_candidate) == detail_name and norm_text(match_candidate.get("organization_name")) == detail_company:
            return match, "name_company"

    if 0 <= index < len(matches):
        return matches[index], "response_order_fallback"
    return None, "no_match"


@dataclass
class AttemptLedger:
    path: Path
    rows: list[dict[str, Any]] = field(default_factory=list)
    _key_to_index: dict[str, int] = field(default_factory=dict)
    dirty: bool = False

    @classmethod
    def load(cls, path: Path) -> "AttemptLedger":
        ledger = cls(path=path)
        if path.exists() and path.stat().st_size > 0:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
            for record in df.to_dict(orient="records"):
                normalized = {column: record.get(column, "") for column in LEDGER_COLUMNS}
                ledger.rows.append(normalized)
        ledger._rebuild_index()
        return ledger

    def _rebuild_index(self) -> None:
        self._key_to_index.clear()
        for index, row in enumerate(self.rows):
            keys = _parse_keys(row.get("All Identity Keys JSON"))
            primary = str(row.get("Primary Identity Key", "")).strip()
            if primary:
                keys.insert(0, primary)
            for key in keys:
                self._key_to_index.setdefault(key, index)

    def find(self, candidate: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        for key in attempt_identity_keys(candidate):
            index = self._key_to_index.get(key)
            if index is not None:
                return self.rows[index], key
        return None, ""

    def record_attempt(
        self,
        candidate: dict[str, Any],
        *,
        status: str,
        run_id: str,
        match: dict[str, Any] | None = None,
        match_method: str = "",
        credits_reported: int | str = "",
        batch_size: int | str = "",
        attempted_at: str | None = None,
        backfill_source: str = "",
        error: str = "",
    ) -> None:
        now = attempted_at or utcnow_iso()
        match = match or {}
        org = match.get("organization") or {}
        merged_candidate = {
            **candidate,
            "id": match.get("id") or match.get("person_id") or candidate.get("id") or candidate.get("apollo_id"),
            "email": match.get("email") or match.get("work_email") or candidate.get("email"),
            "linkedin_url": match.get("linkedin_url") or candidate.get("linkedin_url"),
            "organization_name": org.get("name") or match.get("organization_name") or candidate.get("organization_name"),
        }
        keys = attempt_identity_keys(merged_candidate)
        if not keys:
            # This should be rare because non-matchable candidates never reach Apollo,
            # but keeping a deterministic fallback protects crash recovery.
            keys = [
                "source_row:"
                + "||".join(
                    [
                        norm_text(candidate.get("source_file_name")),
                        norm_text(candidate.get("source_row_number")),
                        _person_name(candidate),
                    ]
                )
            ]

        existing_index: int | None = None
        for key in keys:
            if key in self._key_to_index:
                existing_index = self._key_to_index[key]
                break

        first_name = match.get("first_name") or candidate.get("first_name", "")
        last_name = match.get("last_name") or candidate.get("last_name", "")
        full_name = match.get("name") or candidate.get("name") or f"{first_name} {last_name}".strip()
        company = org.get("name") or match.get("organization_name") or candidate.get("organization_name", "")
        returned_id = match.get("id") or match.get("person_id") or ""
        returned_email = match.get("email") or match.get("work_email") or ""
        email_status = match.get("email_status") or ""

        if existing_index is None:
            row = {column: "" for column in LEDGER_COLUMNS}
            row.update(
                {
                    "Primary Identity Key": keys[0],
                    "All Identity Keys JSON": json.dumps(keys, ensure_ascii=False),
                    "First Name": first_name,
                    "Last Name": last_name,
                    "Full Name": full_name,
                    "Company / Organisation": company,
                    "Company Domain": candidate.get("organization_domain", ""),
                    "LinkedIn URL": match.get("linkedin_url") or candidate.get("linkedin_url", ""),
                    "Input Apollo Person ID": candidate.get("id") or candidate.get("apollo_id") or "",
                    "Returned Apollo Person ID": returned_id,
                    "Returned Email": returned_email,
                    "Email Status": email_status,
                    "Attempt Status": status,
                    "Match Method": match_method,
                    "First Attempt Run ID": run_id,
                    "Last Attempt Run ID": run_id,
                    "First Attempt At UTC": now,
                    "Last Attempt At UTC": now,
                    "Attempt Count": "1",
                    "Source File": candidate.get("source_file_name", ""),
                    "Source Row Number": candidate.get("source_row_number", ""),
                    "API Batch Credits Reported": str(credits_reported),
                    "API Batch Size": str(batch_size),
                    "Backfill Source": backfill_source,
                    "Last Error": error,
                }
            )
            self.rows.append(row)
            existing_index = len(self.rows) - 1
        else:
            row = self.rows[existing_index]
            old_keys = _parse_keys(row.get("All Identity Keys JSON"))
            all_keys = list(dict.fromkeys(old_keys + keys))
            row["All Identity Keys JSON"] = json.dumps(all_keys, ensure_ascii=False)
            row["Primary Identity Key"] = row.get("Primary Identity Key") or all_keys[0]
            row["First Name"] = first_name or row.get("First Name", "")
            row["Last Name"] = last_name or row.get("Last Name", "")
            row["Full Name"] = full_name or row.get("Full Name", "")
            row["Company / Organisation"] = company or row.get("Company / Organisation", "")
            row["Company Domain"] = candidate.get("organization_domain") or row.get("Company Domain", "")
            row["LinkedIn URL"] = match.get("linkedin_url") or candidate.get("linkedin_url") or row.get("LinkedIn URL", "")
            row["Input Apollo Person ID"] = candidate.get("id") or candidate.get("apollo_id") or row.get("Input Apollo Person ID", "")
            row["Returned Apollo Person ID"] = returned_id or row.get("Returned Apollo Person ID", "")
            row["Returned Email"] = returned_email or row.get("Returned Email", "")
            row["Email Status"] = email_status or row.get("Email Status", "")
            row["Attempt Status"] = status
            row["Match Method"] = match_method
            row["Last Attempt Run ID"] = run_id
            row["Last Attempt At UTC"] = now
            try:
                row["Attempt Count"] = str(int(row.get("Attempt Count") or 0) + 1)
            except ValueError:
                row["Attempt Count"] = "1"
            row["API Batch Credits Reported"] = str(credits_reported)
            row["API Batch Size"] = str(batch_size)
            row["Backfill Source"] = backfill_source or row.get("Backfill Source", "")
            row["Last Error"] = error

        self.dirty = True
        self._rebuild_index()

    def flush(self) -> None:
        if not self.dirty and self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(self.rows, columns=LEDGER_COLUMNS)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        df.to_csv(temp_path, index=False)
        temp_path.replace(self.path)
        self.dirty = False

    def write_snapshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.rows, columns=LEDGER_COLUMNS).to_csv(path, index=False)

    def backfill_from_output_root(self, output_root: Path) -> int:
        """Import historical bulk_match calls saved by earlier app versions.

        This makes the credit-protection patch immediately aware of live runs that
        happened before the ledger existed. The operation is idempotent.
        """
        added = 0
        runs_dir = output_root / "runs"
        if not runs_dir.exists():
            return 0

        for raw_path in sorted(runs_dir.glob("*/offsetx_apollo_bulk_match_raw_responses.jsonl")):
            run_id = raw_path.parent.name
            with raw_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    details = payload.get("details") or []
                    response = payload.get("response") or {}
                    matches = _extract_matches(response)
                    credits = payload.get("credits_reported", "")
                    batch_size = payload.get("batch_size") or len(details)
                    for index, detail in enumerate(details):
                        if not isinstance(detail, dict):
                            continue
                        candidate = {
                            **detail,
                            "name": f"{detail.get('first_name', '')} {detail.get('last_name', '')}".strip(),
                            "source_file_name": f"historical_raw_response:{raw_path.name}",
                            "source_row_number": line_number,
                        }
                        if self.find(candidate)[0] is not None:
                            continue
                        match, method = _pick_historical_match(detail, matches, index)
                        if match is None:
                            status = "no_match"
                        elif match.get("email") or match.get("work_email"):
                            status = "accepted_with_email"
                        else:
                            status = "matched_no_email"
                        self.record_attempt(
                            candidate,
                            status=status,
                            run_id=run_id,
                            match=match,
                            match_method=method,
                            credits_reported=credits,
                            batch_size=batch_size,
                            backfill_source=str(raw_path),
                        )
                        added += 1
        if added:
            self.flush()
        return added
