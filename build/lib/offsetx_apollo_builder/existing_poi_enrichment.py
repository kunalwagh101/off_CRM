"""Existing POI file -> Apollo bulk enrichment pipeline.

This is intentionally separate from the Apollo search runner. Search creates new
POIs. This module enriches people the team already has in CSV/XLSX files.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .apollo_client import ApolloClient
from .attempt_ledger import AttemptLedger
from .dedupe import ExclusionSet, build_exclusion_set, name_company_key, norm_email, norm_linkedin, norm_text
from .file_queue import (
    QueuedInputFile,
    archive_failed,
    archive_processed,
    claim_input_file,
    discover_input_files,
    ensure_queue_dirs,
    inspect_queue,
    latest_supported_file,
)
from .input_loader import load_existing_pois
from .io_utils import (
    append_apollo_rejection_ledger,
    append_exclusion_ledger,
    safe_get,
    write_outputs,
)
from .locked_categories import DEFAULT_CATEGORY, normalize_category
from .runner import copy_latest_snapshot, decision_audit_row, why_reply, why_useful, outreach_angle, first_question
from .scoring import score_candidate

ASSIGNEES = ("Kunal", "Sahil", "Yashika", "Nishika")


class NoInputFilesError(RuntimeError):
    """Raised when an enrichment run has no explicit or queued input file."""

    def __init__(self, *, input_dir: Path, processed_dir: Path, latest_processed: Path | None = None):
        self.input_dir = input_dir
        self.processed_dir = processed_dir
        self.latest_processed = latest_processed
        message = f"No CSV/XLSX/XLS files are waiting in {input_dir}."
        if latest_processed is not None:
            message += f" Latest processed file: {latest_processed}. Use --reuse-latest-processed to test it again safely."
        else:
            message += " Put a CSV/XLSX/XLS file in the inbox or pass --enrich-input-file."
        super().__init__(message)


class RunOutputExistsError(RuntimeError):
    """Raised before queue claiming when a non-empty run directory already exists."""


@dataclass
class ExistingPoiEnrichmentConfig:
    exclusions: list[Path]
    outdir: Path
    input_file: Path | None = None
    input_dir: Path = Path("poi_file_queue/inbox")
    processing_dir: Path = Path("poi_file_queue/processing")
    processed_dir: Path = Path("poi_file_queue/processed")
    failed_dir: Path = Path("poi_file_queue/failed")
    exclusion_dir: Path = Path("old_pois")
    update_exclusion_ledger: bool = True
    credit_cap: int = 250
    batch_size: int = 10
    target_count: int | None = None
    dry_run: bool = False
    reveal_personal_emails: bool = False
    run_id: str | None = None
    write_latest_copy: bool = True
    default_category: str = DEFAULT_CATEGORY
    skip_existing_emails: bool = True
    continue_on_file_error: bool = True
    attempt_ledger_path: Path | None = None
    skip_previously_attempted: bool = True
    auto_backfill_attempt_ledger: bool = True
    reuse_latest_processed: bool = False


@dataclass
class ExistingPoiEnrichmentState:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    raw_input_rows: list[dict[str, Any]] = field(default_factory=list)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    raw_apollo_responses: list[dict[str, Any]] = field(default_factory=list)
    file_manifest: list[dict[str, Any]] = field(default_factory=list)
    credits_used: int = 0
    input_rows_seen: int = 0
    selected_for_enrichment: int = 0
    category_counts: Counter = field(default_factory=Counter)
    seen_keys: set[str] = field(default_factory=set)
    run_id: str = ""
    output_dir: Path | None = None
    previously_attempted_skipped: int = 0
    attempt_ledger_backfilled: int = 0
    attempt_ledger_path: Path | None = None
    files_claimed: int = 0


def make_existing_poi_run_id(config: ExistingPoiEnrichmentConfig) -> str:
    if config.run_id:
        return config.run_id.strip()
    mode = "dry" if config.dry_run else "real"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{mode}_existing_poi_enrichment_cap{config.credit_cap}"


def resolve_output_dir(root_outdir: Path, run_id: str) -> Path:
    return root_outdir / "runs" / run_id


def candidate_identity_key(candidate: dict[str, Any]) -> str:
    for field in ("email", "id", "apollo_id", "linkedin_url"):
        value = candidate.get(field)
        if not value:
            continue
        if field == "email":
            return f"email:{norm_email(value)}"
        if field in {"id", "apollo_id"}:
            return f"apollo:{norm_text(value)}"
        if field == "linkedin_url":
            return f"linkedin:{norm_linkedin(value)}"
    return "name_company_title:" + "||".join([
        norm_text(candidate.get("name")),
        norm_text(candidate.get("organization_name")),
        norm_text(candidate.get("title")),
    ])


def is_matchable_for_apollo(candidate: dict[str, Any]) -> tuple[bool, str]:
    if norm_text(candidate.get("id") or candidate.get("apollo_id")):
        return True, "apollo_id"
    if norm_linkedin(candidate.get("linkedin_url")):
        return True, "linkedin_url"
    if candidate.get("first_name") and candidate.get("last_name") and (candidate.get("organization_name") or candidate.get("organization_domain")):
        return True, "name_company_or_domain"
    if candidate.get("name") and (candidate.get("organization_name") or candidate.get("organization_domain")):
        return True, "full_name_company_or_domain"
    return False, "missing_name_company_linkedin_or_apollo_id"


def strong_exclusion_duplicate(exclusion: ExclusionSet, candidate: dict[str, Any]) -> tuple[bool, str]:
    """Use only strong keys for input enrichment.

    Existing POI files often intentionally contain old name/company rows that
    need enrichment. Rejecting by name+company here would block the exact use
    case this mode is built for. Strong keys still prevent re-buying known rows.
    """
    cid = norm_text(candidate.get("id") or candidate.get("apollo_id"))
    if cid and cid in exclusion.apollo_ids:
        return True, "duplicate_apollo_id"

    email = norm_email(candidate.get("email"))
    if email and email in exclusion.emails:
        return True, "duplicate_email"

    linkedin = norm_linkedin(candidate.get("linkedin_url"))
    if linkedin and linkedin in exclusion.linkedin_urls:
        return True, "duplicate_linkedin"

    return False, "fresh"


def enrichment_details_for_existing_poi(candidate: dict[str, Any]) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    cid = norm_text(candidate.get("id") or candidate.get("apollo_id"))
    if cid:
        detail["id"] = cid
    if candidate.get("linkedin_url"):
        detail["linkedin_url"] = candidate["linkedin_url"]
    if candidate.get("organization_domain"):
        detail["domain"] = candidate["organization_domain"]
    if candidate.get("organization_name"):
        detail["organization_name"] = candidate["organization_name"]
    if candidate.get("first_name"):
        detail["first_name"] = candidate["first_name"]
    if candidate.get("last_name"):
        detail["last_name"] = candidate["last_name"]
    elif candidate.get("name"):
        parts = str(candidate["name"]).split()
        if len(parts) >= 2:
            detail.setdefault("first_name", parts[0])
            detail["last_name"] = " ".join(parts[1:])
    return detail


def ordered_matches_from_response(response: dict[str, Any]) -> list[dict[str, Any] | None]:
    """Preserve Apollo's positional match list, including explicit null entries."""
    for key in ("matches", "people", "persons"):
        value = response.get(key)
        if isinstance(value, list):
            return [item if isinstance(item, dict) else None for item in value]
    return []


def pick_match_for_existing_poi(
    candidate: dict[str, Any],
    matches: list[dict[str, Any]],
    fallback_match: dict[str, Any] | None = None,
    *,
    allow_single_fallback: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    cid = norm_text(candidate.get("id") or candidate.get("apollo_id"))
    if cid:
        for match in matches:
            if norm_text(match.get("id") or match.get("person_id")) == cid:
                return match, "apollo_id"

    linkedin = norm_linkedin(candidate.get("linkedin_url"))
    if linkedin:
        for match in matches:
            if norm_linkedin(match.get("linkedin_url")) == linkedin:
                return match, "linkedin_url"

    cand_name = norm_text(candidate.get("name"))
    cand_company = norm_text(candidate.get("organization_name"))
    for match in matches:
        org = match.get("organization") or {}
        match_name = norm_text(match.get("name") or f"{match.get('first_name', '')} {match.get('last_name', '')}")
        match_company = norm_text(org.get("name") or match.get("organization_name"))
        if cand_name and cand_company and cand_name == match_name and cand_company == match_company:
            return match, "name_company"

    if fallback_match is not None:
        return fallback_match, "response_order_fallback"

    if allow_single_fallback and len(matches) == 1:
        return matches[0], "single_match_fallback"

    return None, "no_match"


def compact_input_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "Source File": candidate.get("source_file_name", ""),
        "Source Row Number": candidate.get("source_row_number", ""),
        "Apollo Person ID": candidate.get("id") or candidate.get("apollo_id") or "",
        "Full Name": candidate.get("name", ""),
        "First Name": candidate.get("first_name", ""),
        "Last Name": candidate.get("last_name", ""),
        "Position / Title": candidate.get("title", ""),
        "Company / Organisation": candidate.get("organization_name", ""),
        "Company Domain": candidate.get("organization_domain", ""),
        "Category": candidate.get("category", ""),
        "Country / Region": candidate.get("country", ""),
        "LinkedIn URL": candidate.get("linkedin_url", ""),
        "Input Email": candidate.get("email", ""),
        "Input Identity Key": candidate.get("input_identity_key", ""),
        "Raw Input JSON": json.dumps(candidate.get("raw_input_json", {}), ensure_ascii=False, default=str),
    }


def build_existing_poi_decision_row(candidate: dict[str, Any], decision: str, reason: str, scores: dict[str, Any] | None = None, email: str = "", match_method: str = "") -> dict[str, Any]:
    row = decision_audit_row(candidate, decision, reason, scores, email=email)
    row["Source File"] = candidate.get("source_file_name", "")
    row["Source Row Number"] = candidate.get("source_row_number", "")
    row["Input Identity Key"] = candidate.get("input_identity_key", "")
    row["Apollo Match Method"] = match_method
    return row


def build_existing_poi_final_row(candidate: dict[str, Any], enriched: dict[str, Any], priority_no: int, scores: dict[str, Any], *, source_status: str, match_method: str) -> dict[str, Any]:
    org = enriched.get("organization") or {}
    first = safe_get(enriched, "first_name") or candidate.get("first_name", "")
    last = safe_get(enriched, "last_name") or candidate.get("last_name", "")
    full = safe_get(enriched, "name") or candidate.get("name") or f"{first} {last}".strip()
    company = org.get("name") or enriched.get("organization_name") or candidate.get("organization_name", "")
    country = enriched.get("country") or candidate.get("country", "") or org.get("country", "")
    title = enriched.get("title") or candidate.get("title", "")
    email = enriched.get("email") or enriched.get("work_email") or candidate.get("email", "")
    email_status = enriched.get("email_status") or candidate.get("email_status") or ("verified" if email else "")
    linkedin = enriched.get("linkedin_url") or candidate.get("linkedin_url", "")
    category = normalize_category(candidate.get("category"))
    wave = "Wave 1" if priority_no <= 60 else "Wave 2" if priority_no <= 200 else "Later"
    assigned_to = ASSIGNEES[(priority_no - 1) % len(ASSIGNEES)]

    return {
        "Priority ID": f"ENR-P{priority_no:03d}",
        "Full Name": full,
        "First Name": first,
        "Last Name": last,
        "Position / Title": title,
        "Company / Organisation": company,
        "Category": category,
        "Country / Region": country,
        "Organisation Size": org.get("estimated_num_employees") or candidate.get("organization_size", ""),
        "Seniority Level": enriched.get("seniority") or candidate.get("seniority", ""),
        "Apollo Person ID": enriched.get("id") or enriched.get("person_id") or candidate.get("id") or candidate.get("apollo_id") or "",
        "LinkedIn URL or LinkedIn search route": linkedin or f"LinkedIn search: {full} {company}",
        "Email": email,
        "Email Status": email_status,
        "Public Source URL / Research Route": linkedin or f"Search web: {full} {company} {title}",
        "Apollo Search Route / Basis": f"Existing POI file -> Apollo bulk_match | source_file={candidate.get('source_file_name', '')} | row={candidate.get('source_row_number', '')} | match_method={match_method}",
        "Why Useful": why_useful(category, title, company),
        "Why They May Reply": why_reply(category, title),
        "Suggested Outreach Angle": outreach_angle(category),
        "Suggested First Question": first_question(category),
        "Risk Level": scores["risk_level"],
        "Risk Score": scores["risk_score"],
        "Problem Relevance Score": scores["problem_relevance_score"],
        "Decision Influence Score": scores["decision_influence_score"],
        "Reachability Score": scores["reachability_score"],
        "Reply Probability Score": scores["reply_probability_score"],
        "Non-Competitor Safety Score": scores["non_competitor_safety_score"],
        "Source Confidence Score": scores["source_confidence_score"],
        "Overall Score": scores["overall_score"],
        "Wave": wave,
        "Assigned To": assigned_to,
        "Dedupe Status": "Fresh against strong exclusion keys for input enrichment",
        "Source Status": source_status,
        "Next Action": "Review and send expert/client discovery outreach",
        "Notes": f"risk_reason={scores['risk_reason']}; source_file={candidate.get('source_file_name', '')}; source_row={candidate.get('source_row_number', '')}; match_method={match_method}",
    }


def _source_files(config: ExistingPoiEnrichmentConfig) -> list[tuple[Path, bool]]:
    """Return ``(path, preserve_source)`` pairs in deterministic order."""
    ensure_queue_dirs(config.input_dir, config.processing_dir, config.processed_dir, config.failed_dir)

    if config.input_file:
        return [(config.input_file, True)]

    inbox_files = discover_input_files(config.input_dir)
    if inbox_files:
        return [(path, False) for path in inbox_files]

    if config.reuse_latest_processed:
        latest = latest_supported_file(config.processed_dir)
        if latest is not None:
            return [(latest, True)]

    status = inspect_queue(config.input_dir, config.processing_dir, config.processed_dir, config.failed_dir)
    raise NoInputFilesError(
        input_dir=config.input_dir,
        processed_dir=config.processed_dir,
        latest_processed=status.latest_processed,
    )


def _claim_files(config: ExistingPoiEnrichmentConfig, run_id: str) -> list[QueuedInputFile]:
    queued: list[QueuedInputFile] = []
    for path, preserve_source in _source_files(config):
        queued.append(
            claim_input_file(
                path,
                processing_dir=config.processing_dir,
                processed_dir=config.processed_dir,
                failed_dir=config.failed_dir,
                run_id=run_id,
                preserve_source=preserve_source,
            )
        )
    return queued


def _prepare_run_output_dir(root_outdir: Path, run_id: str) -> Path:
    output_dir = resolve_output_dir(root_outdir, run_id)
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise RunOutputExistsError(
                f"Run output already exists and is not empty: {output_dir}. Use a new --run-id."
            )
        output_dir.rmdir()
    return output_dir


def _archive_all_failed(queued_files: list[QueuedInputFile]) -> list[Path]:
    failed_paths: list[Path] = []
    for queued in queued_files:
        if queued.processing_path.exists():
            failed_paths.append(archive_failed(queued))
    return failed_paths


def _record_rejection(state: ExistingPoiEnrichmentState, candidate: dict[str, Any], reason: str, scores: dict[str, Any] | None = None, decision: str = "rejected_before_enrichment") -> None:
    state.rejected.append({
        "reason": reason,
        "candidate_id": candidate.get("id") or candidate.get("apollo_id", ""),
        "name": candidate.get("name", ""),
        "company": candidate.get("organization_name", ""),
        "source_file": candidate.get("source_file_name", ""),
        "source_row_number": candidate.get("source_row_number", ""),
        **(scores or {}),
    })
    state.decision_log.append(build_existing_poi_decision_row(candidate, decision, reason, scores))


def _prepare_candidates_for_file(path: Path, config: ExistingPoiEnrichmentConfig, exclusion: ExclusionSet, state: ExistingPoiEnrichmentState, attempt_ledger: AttemptLedger) -> list[dict[str, Any]]:
    _raw_df, rows = load_existing_pois(path, default_category=config.default_category)
    candidates_to_enrich: list[dict[str, Any]] = []

    for candidate in rows:
        state.input_rows_seen += 1
        state.raw_input_rows.append(compact_input_row(candidate))

        # Normalize once more so future manually-edited files stay safe.
        candidate["category"] = normalize_category(candidate.get("category"), default=config.default_category)

        identity_key = candidate_identity_key(candidate)
        if identity_key in state.seen_keys:
            _record_rejection(state, candidate, "duplicate_inside_input_file")
            continue
        state.seen_keys.add(identity_key)

        if candidate.get("email") and config.skip_existing_emails:
            enriched_stub = {
                "first_name": candidate.get("first_name", ""),
                "last_name": candidate.get("last_name", ""),
                "name": candidate.get("name", ""),
                "title": candidate.get("title", ""),
                "email": candidate.get("email", ""),
                "email_status": candidate.get("email_status") or "input_provided",
                "linkedin_url": candidate.get("linkedin_url", ""),
                "organization": {"name": candidate.get("organization_name", "")},
            }
            scored_candidate = {**candidate, "has_email": True, "email_status": "input_provided"}
            scores = score_candidate(scored_candidate, candidate["category"])
            row = build_existing_poi_final_row(
                scored_candidate,
                enriched_stub,
                len(state.accepted) + 1,
                scores,
                source_status="Input file already had email; Apollo credit not spent",
                match_method="input_email",
            )
            state.accepted.append(row)
            state.category_counts[row["Category"]] += 1
            state.decision_log.append(build_existing_poi_decision_row(scored_candidate, "accepted", "input_already_had_email", scores, email=row["Email"], match_method="input_email"))
            exclusion.add_record(row)
            continue

        if config.skip_previously_attempted:
            prior_attempt, matched_attempt_key = attempt_ledger.find(candidate)
            if prior_attempt is not None:
                prior_status = norm_text(prior_attempt.get("Attempt Status")) or "unknown"
                state.previously_attempted_skipped += 1
                _record_rejection(
                    state,
                    candidate,
                    f"previously_attempted_apollo_{prior_status}",
                    decision="skipped_before_enrichment",
                )
                state.decision_log[-1]["Apollo Attempt Ledger Match Key"] = matched_attempt_key
                state.decision_log[-1]["Previous Attempt Run ID"] = prior_attempt.get("Last Attempt Run ID", "")
                continue

        is_dup, dup_reason = strong_exclusion_duplicate(exclusion, candidate)
        if is_dup:
            _record_rejection(state, candidate, dup_reason)
            continue

        scores = score_candidate(candidate, candidate["category"])
        if scores["risk_level"] == "Hold":
            _record_rejection(state, candidate, "competitor_risk_hold", scores)
            continue

        matchable, reason = is_matchable_for_apollo(candidate)
        if not matchable:
            _record_rejection(state, candidate, reason, scores)
            continue

        if config.dry_run:
            state.selected_for_enrichment += 1
            state.rejected.append({
                "reason": "dry_run_not_enriched",
                "candidate_id": candidate.get("id") or candidate.get("apollo_id", ""),
                "name": candidate.get("name", ""),
                "company": candidate.get("organization_name", ""),
                "source_file": candidate.get("source_file_name", ""),
                "source_row_number": candidate.get("source_row_number", ""),
                **scores,
            })
            state.decision_log.append(build_existing_poi_decision_row(candidate, "selected_for_enrichment", "dry_run_not_enriched", scores))
            continue

        candidate["scores"] = scores
        candidates_to_enrich.append(candidate)
        state.selected_for_enrichment += 1

    return candidates_to_enrich


def _enrich_candidates(candidates: list[dict[str, Any]], config: ExistingPoiEnrichmentConfig, state: ExistingPoiEnrichmentState, client: ApolloClient, exclusion: ExclusionSet, attempt_ledger: AttemptLedger) -> None:
    idx = 0
    while idx < len(candidates):
        if state.credits_used >= config.credit_cap:
            for candidate in candidates[idx:]:
                _record_rejection(state, candidate, "credit_cap_reached_before_enrichment", candidate.get("scores"))
            break

        if config.target_count is not None and len(state.accepted) >= config.target_count:
            for candidate in candidates[idx:]:
                _record_rejection(state, candidate, "target_count_reached_before_enrichment", candidate.get("scores"))
            break

        room = config.credit_cap - state.credits_used
        target_room = (config.target_count - len(state.accepted)) if config.target_count is not None else room
        take = min(config.batch_size, room, max(target_room, 0), len(candidates) - idx)
        if take <= 0:
            break

        batch = candidates[idx : idx + take]
        idx += take
        details = [enrichment_details_for_existing_poi(candidate) for candidate in batch]
        try:
            response = client.bulk_people_enrich(details, reveal_personal_emails=config.reveal_personal_emails)
        except Exception as exc:
            # We do not know whether Apollo charged the failed request. Record it
            # conservatively before re-raising so a rerun cannot silently spend
            # the same credits again.
            for candidate in batch:
                attempt_ledger.record_attempt(
                    candidate,
                    status="api_error_unknown",
                    run_id=state.run_id,
                    credits_reported="unknown",
                    batch_size=len(batch),
                    error=f"{type(exc).__name__}: {exc}",
                )
            attempt_ledger.flush()
            raise
        ordered_matches = ordered_matches_from_response(response)
        matches = [match for match in ordered_matches if match is not None]
        credits_value = response.get("credits_consumed")
        if credits_value is None:
            credits_value = response.get("credits_used")
        credits = int(credits_value) if credits_value is not None else len(details)
        state.credits_used += credits
        state.raw_apollo_responses.append({
            "batch_start_index": idx - take,
            "batch_size": len(batch),
            "credits_reported": credits,
            "details": details,
            "response": response,
        })

        used_match_object_ids: set[int] = set()
        for offset, candidate in enumerate(batch):
            positional_match = ordered_matches[offset] if offset < len(ordered_matches) else None
            match, match_method = pick_match_for_existing_poi(
                candidate,
                matches,
                fallback_match=positional_match,
                allow_single_fallback=len(batch) == 1,
            )
            if match is not None:
                match_obj_id = id(match)
                # Avoid assigning the same unordered fallback match twice in a batch.
                if match_method.endswith("fallback") and match_obj_id in used_match_object_ids:
                    match = None
                    match_method = "fallback_match_already_used"
                else:
                    used_match_object_ids.add(match_obj_id)

            scores = candidate.get("scores") or score_candidate(candidate, candidate.get("category", config.default_category))
            if not match:
                attempt_ledger.record_attempt(
                    candidate,
                    status="no_match",
                    run_id=state.run_id,
                    match_method=match_method,
                    credits_reported=credits,
                    batch_size=len(batch),
                )
                _record_rejection(state, candidate, "enriched_no_match", scores, decision="rejected_after_enrichment")
                continue

            email = match.get("email") or match.get("work_email") or ""
            if not email:
                state.rejected.append({
                    "reason": "enriched_no_email",
                    "candidate_id": candidate.get("id") or candidate.get("apollo_id", ""),
                    "name": candidate.get("name", ""),
                    "company": candidate.get("organization_name", ""),
                    "source_file": candidate.get("source_file_name", ""),
                    "source_row_number": candidate.get("source_row_number", ""),
                    **scores,
                })
                attempt_ledger.record_attempt(
                    candidate,
                    status="matched_no_email",
                    run_id=state.run_id,
                    match=match,
                    match_method=match_method,
                    credits_reported=credits,
                    batch_size=len(batch),
                )
                state.decision_log.append(build_existing_poi_decision_row(candidate, "rejected_after_enrichment", "enriched_no_email", scores, match_method=match_method))
                continue

            enriched_candidate = {
                **candidate,
                "has_email": True,
                "email_status": match.get("email_status") or "verified",
                "id": match.get("id") or match.get("person_id") or candidate.get("id") or candidate.get("apollo_id", ""),
            }
            scores_after_email = score_candidate(enriched_candidate, enriched_candidate.get("category", config.default_category))
            row = build_existing_poi_final_row(
                enriched_candidate,
                match,
                len(state.accepted) + 1,
                scores_after_email,
                source_status="Apollo bulk_match enriched with business email",
                match_method=match_method,
            )
            attempt_ledger.record_attempt(
                candidate,
                status="accepted_with_email",
                run_id=state.run_id,
                match=match,
                match_method=match_method,
                credits_reported=credits,
                batch_size=len(batch),
            )
            state.accepted.append(row)
            state.category_counts[row["Category"]] += 1
            state.decision_log.append(build_existing_poi_decision_row(enriched_candidate, "accepted", "accepted_with_email", scores_after_email, email=email, match_method=match_method))
            exclusion.add_record(row)

        # Atomic write after every API batch. If the process stops later, the
        # credit-protection history for this completed batch is still safe.
        attempt_ledger.flush()


def write_existing_poi_extra_outputs(state: ExistingPoiEnrichmentState) -> None:
    assert state.output_dir is not None
    outdir = state.output_dir
    pd.DataFrame(state.raw_input_rows).to_csv(outdir / "offsetx_input_pois_normalized.csv", index=False)
    pd.DataFrame(state.file_manifest).to_csv(outdir / "offsetx_input_file_manifest.csv", index=False)
    with (outdir / "offsetx_apollo_bulk_match_raw_responses.jsonl").open("w", encoding="utf-8") as f:
        for row in state.raw_apollo_responses:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _decision_stage_counts(state: ExistingPoiEnrichmentState) -> Counter:
    return Counter(str(row.get("Decision", "")) for row in state.decision_log)


def _reason_counts(state: ExistingPoiEnrichmentState) -> Counter:
    return Counter(str(row.get("reason", "")) for row in state.rejected)


def run_existing_poi_enrichment(config: ExistingPoiEnrichmentConfig, client: ApolloClient | None = None) -> ExistingPoiEnrichmentState:
    """Run the existing-POI enrichment pipeline with crash-safe queue handling.

    Queue guarantees:
    - inbox files are claimed into ``processing`` before work begins;
    - files reach ``processed`` only after enrichment, outputs, and ledgers succeed;
    - any claimed file still in ``processing`` after an exception is moved to
      ``failed``;
    - an empty inbox raises ``NoInputFilesError`` before a run folder is created.
    """
    if config.batch_size > 10:
        raise ValueError("batch_size cannot exceed 10 because Apollo bulk enrichment supports max 10 people per call.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if config.credit_cap <= 0:
        raise ValueError("credit_cap must be positive.")
    if config.target_count is not None and config.target_count <= 0:
        raise ValueError("target_count must be positive when provided.")

    exclusion = build_exclusion_set(config.exclusions)
    state = ExistingPoiEnrichmentState()
    state.run_id = make_existing_poi_run_id(config)

    # Reject collisions before claiming any queue file. Empty directories left by
    # old failed versions are safely removed and reused.
    final_output_dir = _prepare_run_output_dir(config.outdir, state.run_id)

    ledger_path = config.attempt_ledger_path or (config.exclusion_dir / "offsetx_apollo_enrichment_attempt_ledger.csv")
    attempt_ledger = AttemptLedger.load(ledger_path)
    state.attempt_ledger_path = ledger_path
    if config.auto_backfill_attempt_ledger:
        state.attempt_ledger_backfilled = attempt_ledger.backfill_from_output_root(config.outdir)
        # Persist historical recovery even when the inbox is empty.
        attempt_ledger.flush()

    queued_files = _claim_files(config, state.run_id)
    state.files_claimed = len(queued_files)
    state.output_dir = final_output_dir
    final_output_dir.mkdir(parents=True, exist_ok=False)

    successful_queued: list[QueuedInputFile] = []
    manifest_by_processing_path: dict[str, dict[str, Any]] = {}

    try:
        all_candidates_to_enrich: list[dict[str, Any]] = []
        for queued in queued_files:
            manifest_row: dict[str, Any] = {
                "original_path": str(queued.original_path),
                "source_preserved": queued.source_preserved,
                "processing_path": str(queued.processing_path),
                "processed_path": "",
                "failed_path": "",
                "status": "processing",
                "input_rows_before_file": state.input_rows_seen,
                "accepted_before_file": len(state.accepted),
                "rejected_before_file": len(state.rejected),
                "error": "",
            }
            manifest_by_processing_path[str(queued.processing_path)] = manifest_row
            try:
                before_input = state.input_rows_seen
                before_selected = state.selected_for_enrichment
                candidates = _prepare_candidates_for_file(queued.processing_path, config, exclusion, state, attempt_ledger)
                all_candidates_to_enrich.extend(candidates)
                successful_queued.append(queued)
                manifest_row.update({
                    "status": "validated_waiting_for_run_completion",
                    "input_rows_in_file": state.input_rows_seen - before_input,
                    "selected_for_enrichment_in_file": state.selected_for_enrichment - before_selected,
                })
            except Exception as exc:
                failed_path = archive_failed(queued)
                manifest_row.update({
                    "status": "failed",
                    "failed_path": str(failed_path),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                if not config.continue_on_file_error:
                    raise
            finally:
                manifest_row["input_rows_after_file"] = state.input_rows_seen
                manifest_row["accepted_after_file"] = len(state.accepted)
                manifest_row["rejected_after_file"] = len(state.rejected)
                state.file_manifest.append(manifest_row)

        if not successful_queued:
            raise RuntimeError("All claimed input files failed validation. Check poi_file_queue/failed and the error details.")

        if not config.dry_run:
            if client is None:
                client = ApolloClient.from_env()
            _enrich_candidates(all_candidates_to_enrich, config, state, client, exclusion, attempt_ledger)

        stage_counts = _decision_stage_counts(state)
        reason_counts = _reason_counts(state)
        run_meta = {
            "run_id": state.run_id,
            "run_status": "completed",
            "output_dir": str(final_output_dir),
            "run_root_outdir": str(config.outdir),
            "run_type": "existing_poi_file_enrichment",
            "input_file": str(config.input_file or ""),
            "input_dir": str(config.input_dir),
            "processing_dir": str(config.processing_dir),
            "processed_dir": str(config.processed_dir),
            "failed_dir": str(config.failed_dir),
            "reuse_latest_processed": config.reuse_latest_processed,
            "input_files_claimed": len(queued_files),
            "input_files_validated": len(successful_queued),
            "input_rows_seen": state.input_rows_seen,
            "selected_for_enrichment": state.selected_for_enrichment,
            "dry_run_selected_not_sent": reason_counts.get("dry_run_not_enriched", 0),
            "skipped_before_enrichment": stage_counts.get("rejected_before_enrichment", 0) + stage_counts.get("skipped_before_enrichment", 0),
            "rejected_after_enrichment": stage_counts.get("rejected_after_enrichment", 0),
            "target_count": config.target_count or "",
            "credit_cap": config.credit_cap,
            "credits_used_reported_by_apollo": state.credits_used,
            "accepted_email_count": len(state.accepted),
            "non_accepted_audit_rows": len(state.rejected),
            "decision_audit_rows_written": len(state.decision_log),
            "raw_apollo_bulk_match_calls": len(state.raw_apollo_responses),
            "exclusion_files": ";".join(str(path) for path in config.exclusions),
            "exclusion_file_count": len(config.exclusions),
            "exclusion_rows_loaded": exclusion.raw_rows_loaded,
            "dry_run": config.dry_run,
            "personal_emails_requested": config.reveal_personal_emails,
            "skip_existing_emails": config.skip_existing_emails,
            "skip_previously_attempted": config.skip_previously_attempted,
            "attempt_ledger_path": str(ledger_path),
            "attempt_ledger_backfilled_rows": state.attempt_ledger_backfilled,
            "previously_attempted_skipped": state.previously_attempted_skipped,
        }

        write_outputs(
            final_output_dir,
            state.accepted,
            state.rejected,
            run_meta,
            raw_candidates=state.raw_input_rows,
            decision_log=state.decision_log,
        )
        write_existing_poi_extra_outputs(state)
        attempt_ledger.flush()
        attempt_ledger.write_snapshot(final_output_dir / "offsetx_apollo_enrichment_attempt_ledger_snapshot.csv")

        if config.update_exclusion_ledger and not config.dry_run:
            append_exclusion_ledger(config.exclusion_dir, state.accepted, final_output_dir)
        if not config.dry_run:
            append_apollo_rejection_ledger(
                config.outdir,
                state.decision_log,
                final_output_dir,
                state.run_id,
            )

        # A file is "processed" only after the complete run has succeeded.
        for queued in successful_queued:
            processed_path = archive_processed(queued)
            manifest_row = manifest_by_processing_path[str(queued.processing_path)]
            manifest_row.update({
                "status": "processed",
                "processed_path": str(processed_path),
            })

        # Rewrite the final manifest after archival paths are known.
        pd.DataFrame(state.file_manifest).to_csv(final_output_dir / "offsetx_input_file_manifest.csv", index=False)

        if config.write_latest_copy:
            copy_latest_snapshot(final_output_dir, config.outdir)
        return state

    except Exception:
        failed_paths = _archive_all_failed(queued_files)
        failed_by_name = {path.name: path for path in failed_paths}
        for queued in queued_files:
            manifest_row = manifest_by_processing_path.get(str(queued.processing_path))
            if manifest_row is None or manifest_row.get("status") == "failed":
                continue
            matching = failed_by_name.get(queued.failed_path.name)
            manifest_row.update({
                "status": "failed",
                "failed_path": str(matching or queued.failed_path),
                "error": manifest_row.get("error") or "Run failed after file validation; see traceback/log.",
            })

        # Preserve a compact failure artifact without pretending the run completed.
        if final_output_dir.exists():
            pd.DataFrame(state.file_manifest).to_csv(final_output_dir / "offsetx_input_file_manifest.csv", index=False)
            (final_output_dir / "run_failed.json").write_text(
                json.dumps(
                    {
                        "run_id": state.run_id,
                        "run_status": "failed",
                        "input_rows_seen": state.input_rows_seen,
                        "selected_for_enrichment": state.selected_for_enrichment,
                        "credits_used_reported_by_apollo": state.credits_used,
                        "attempt_ledger_path": str(ledger_path),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        attempt_ledger.flush()
        raise
