"""Main OffsetX Apollo search/enrich loop."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .apollo_client import ApolloClient
from .categories import CATEGORIES, SearchCategory
from .dedupe import ExclusionSet, build_exclusion_set, norm_domain, norm_text, split_name
from .io_utils import (
    append_apollo_rejection_ledger,
    append_exclusion_ledger,
    safe_get,
    write_outputs,
)
from .scoring import score_candidate


@dataclass
class RunConfig:
    exclusions: list[Path]
    outdir: Path
    exclusion_dir: Path = Path("old_pois")
    update_exclusion_ledger: bool = True
    target_count: int = 250
    credit_cap: int = 250
    per_page: int = 100
    pages_per_category: int = 5
    batch_size: int = 10
    max_per_company: int = 6
    dry_run: bool = False
    reveal_personal_emails: bool = False
    run_id: str | None = None
    write_latest_copy: bool = True


@dataclass
class RunState:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    raw_candidates: list[dict[str, Any]] = field(default_factory=list)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    credits_used: int = 0
    searched_candidates: int = 0
    fresh_candidates: int = 0
    category_counts: Counter = field(default_factory=Counter)
    category_selected_counts: Counter = field(default_factory=Counter)
    company_counts: Counter = field(default_factory=Counter)
    seen_apollo_ids: set[str] = field(default_factory=set)
    run_id: str = ""
    output_dir: Path | None = None


def make_run_id(config: RunConfig) -> str:
    """Create a stable human-readable id for one Apollo run."""
    if config.run_id:
        return config.run_id.strip()
    mode = "dry" if config.dry_run else "real"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:8]
    return f"{ts}_{mode}_target{config.target_count}_cap{config.credit_cap}_{short}"


def resolve_output_dir(root_outdir: Path, run_id: str) -> Path:
    """Every run gets its own immutable analytics folder under <outdir>/runs/<run_id>."""
    return root_outdir / "runs" / run_id


def copy_latest_snapshot(run_dir: Path, root_outdir: Path) -> None:
    """Maintain <outdir>/latest as a convenience copy of the most recent run."""
    latest = root_outdir / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(run_dir, latest)


def normalize_search_person(person: dict[str, Any], category_name: str) -> dict[str, Any]:
    org = person.get("organization") or {}
    full_name = person.get("name") or " ".join(str(x) for x in [person.get("first_name", ""), person.get("last_name", "")] if x).strip()
    first, last = split_name(full_name) if full_name and not person.get("first_name") else (str(person.get("first_name", "") or ""), str(person.get("last_name", "") or person.get("last_name_obfuscated", "") or ""))
    return {
        "id": person.get("id") or person.get("person_id"),
        "first_name": first,
        "last_name": last,
        "name": full_name or f"{first} {last}".strip(),
        "title": person.get("title") or "",
        "linkedin_url": person.get("linkedin_url") or "",
        "country": person.get("country") or org.get("country") or "",
        "city": person.get("city") or "",
        "state": person.get("state") or "",
        "organization_name": org.get("name") or person.get("organization_name") or "",
        "organization_domain": norm_domain(org.get("primary_domain") or org.get("website_url") or person.get("domain") or ""),
        "organization_size": str(org.get("estimated_num_employees") or ""),
        "industry": org.get("industry") or "",
        "seniority": person.get("seniority") or "",
        "has_email": bool(person.get("has_email") is True or str(person.get("has_email", "")).lower() == "true"),
        "email_status": "verified" if person.get("has_email") else str(person.get("email_status") or ""),
        "category": category_name,
        "raw_search_person": person,
    }


def enrichment_details(candidate: dict[str, Any]) -> dict[str, Any]:
    # Prefer Apollo ID because it is strongest. Add domain/company/LinkedIn if present.
    detail: dict[str, Any] = {"id": candidate["id"]}
    if candidate.get("linkedin_url"):
        detail["linkedin_url"] = candidate["linkedin_url"]
    if candidate.get("organization_domain"):
        detail["domain"] = candidate["organization_domain"]
    if candidate.get("organization_name"):
        detail["organization_name"] = candidate["organization_name"]
    if candidate.get("first_name"):
        detail["first_name"] = candidate["first_name"]
    if candidate.get("last_name") and "*" not in str(candidate.get("last_name")):
        detail["last_name"] = candidate["last_name"]
    return detail


def extract_matches(response: dict[str, Any]) -> list[dict[str, Any]]:
    # Apollo variants sometimes use matches, people, contacts, or a nested people array.
    for key in ["matches", "people", "contacts"]:
        val = response.get(key)
        if isinstance(val, list):
            return val
    if isinstance(response.get("person"), dict):
        return [response["person"]]
    return []


def pick_match_for_candidate(matches: list[dict[str, Any]], candidate_id: str) -> dict[str, Any] | None:
    candidate_id = norm_text(candidate_id)
    for m in matches:
        if norm_text(m.get("id")) == candidate_id or norm_text(m.get("person_id")) == candidate_id:
            return m
    if len(matches) == 1:
        return matches[0]
    return None


def compact_candidate_row(candidate: dict[str, Any]) -> dict[str, Any]:
    """Flat fields used for audit/analytics CSVs."""
    return {
        "Apollo Person ID": candidate.get("id", ""),
        "Full Name": candidate.get("name", ""),
        "First Name": candidate.get("first_name", ""),
        "Last Name": candidate.get("last_name", ""),
        "Position / Title": candidate.get("title", ""),
        "Company / Organisation": candidate.get("organization_name", ""),
        "Company Domain": candidate.get("organization_domain", ""),
        "Country / Region": candidate.get("country", ""),
        "City": candidate.get("city", ""),
        "State": candidate.get("state", ""),
        "Seniority Level": candidate.get("seniority", ""),
        "Industry": candidate.get("industry", ""),
        "LinkedIn URL": candidate.get("linkedin_url", ""),
        "Has Email Flag": candidate.get("has_email", ""),
        "Email Status From Search": candidate.get("email_status", ""),
        "Organisation Size": candidate.get("organization_size", ""),
    }


def raw_search_row(person: dict[str, Any], candidate: dict[str, Any], category_name: str, page: int, rank_on_page: int, global_rank: int) -> dict[str, Any]:
    row = {
        "Global Search Row No": global_rank,
        "Apollo Search Category": category_name,
        "Apollo Search Page": page,
        "Rank On Page": rank_on_page,
        **compact_candidate_row(candidate),
        "Raw Apollo JSON": json.dumps(person, ensure_ascii=False, default=str),
    }
    return row


def decision_audit_row(candidate: dict[str, Any], decision: str, reason: str, scores: dict[str, Any] | None = None, email: str = "") -> dict[str, Any]:
    scores = scores or {}
    row = {
        "Apollo Search Category": candidate.get("_search_category", candidate.get("category", "")),
        "Apollo Search Page": candidate.get("_search_page", ""),
        "Rank On Page": candidate.get("_search_rank_on_page", ""),
        "Decision": decision,
        "Reason": reason,
        "Email Returned": email,
        **compact_candidate_row(candidate),
        "Risk Level": scores.get("risk_level", ""),
        "Risk Score": scores.get("risk_score", ""),
        "Risk Reason": scores.get("risk_reason", ""),
        "Problem Relevance Score": scores.get("problem_relevance_score", ""),
        "Decision Influence Score": scores.get("decision_influence_score", ""),
        "Reachability Score": scores.get("reachability_score", ""),
        "Reply Probability Score": scores.get("reply_probability_score", ""),
        "Non-Competitor Safety Score": scores.get("non_competitor_safety_score", ""),
        "Source Confidence Score": scores.get("source_confidence_score", ""),
        "Overall Score": scores.get("overall_score", ""),
    }
    return row


def build_final_row(candidate: dict[str, Any], enriched: dict[str, Any], category: str, priority_no: int, scores: dict[str, Any]) -> dict[str, Any]:
    org = enriched.get("organization") or {}
    first = safe_get(enriched, "first_name") or candidate.get("first_name", "")
    last = safe_get(enriched, "last_name") or (candidate.get("last_name", "") if "*" not in str(candidate.get("last_name", "")) else "")
    full = safe_get(enriched, "name") or f"{first} {last}".strip()
    company = org.get("name") or candidate.get("organization_name", "")
    country = enriched.get("country") or candidate.get("country", "") or org.get("country", "")
    title = enriched.get("title") or candidate.get("title", "")
    email = enriched.get("email") or enriched.get("work_email") or ""
    email_status = enriched.get("email_status") or ("verified" if email else "")
    linkedin = enriched.get("linkedin_url") or candidate.get("linkedin_url", "")

    wave = "Wave 1" if priority_no <= 60 else "Wave 2" if priority_no <= 200 else "Later"
    assigned_to = ["Kunal", "Sahil", "Yashika", "Nishika"][(priority_no - 1) % 4]

    return {
        "Priority ID": f"NEW-P{priority_no:03d}",
        "Full Name": full,
        "First Name": first,
        "Last Name": last,
        "Position / Title": title,
        "Company / Organisation": company,
        "Category": category,
        "Country / Region": country,
        "Organisation Size": org.get("estimated_num_employees") or candidate.get("organization_size", ""),
        "Seniority Level": enriched.get("seniority") or candidate.get("seniority", ""),
        "Apollo Person ID": enriched.get("id") or candidate.get("id", ""),
        "LinkedIn URL or LinkedIn search route": linkedin or f"LinkedIn search: {full} {company}",
        "Email": email,
        "Email Status": email_status,
        "Public Source URL / Research Route": linkedin or f"Search web: {full} {company} {title}",
        "Apollo Search Route / Basis": f"Apollo People Search | category={category} | email_status=verified | id={candidate.get('id')}",
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
        "Dedupe Status": "Fresh against supplied exclusion files",
        "Source Status": "Apollo enriched with business email",
        "Next Action": "Review and send expert/client discovery outreach",
        "Notes": f"risk_reason={scores['risk_reason']}; no personal email or phone requested",
    }


def why_useful(category: str, title: str, company: str) -> str:
    return f"Relevant {category} stakeholder at {company}; role/title indicates workflow knowledge: {title}."


def why_reply(category: str, title: str) -> str:
    if "Policy" in category or "Consult" in title:
        return "Likely to engage on market/process questions if framed as expert research, not a sales pitch."
    return "May respond if the message is tied to operational pain around carbon reporting, trade compliance, or buyer pressure."


def outreach_angle(category: str) -> str:
    if "Trade" in category or "CBAM" in category:
        return "Ask about the practical data handoff between exporter, customs/trade compliance, and CBAM reporting."
    if "Aviation" in category:
        return "Ask about CORSIA/SAF data workflows and audit-ready sustainability reporting."
    if "Article 6" in category or "Carbon Markets" in category:
        return "Ask about Article 6/CORSIA implementation and what evidence buyers or project developers actually need."
    if "Finance" in category:
        return "Ask how carbon reporting affects credit, underwriting, trade finance, or climate-risk diligence."
    return "Ask where carbon data becomes manual, consultant-heavy, or audit-risky."


def first_question(category: str) -> str:
    if "Trade" in category or "CBAM" in category:
        return "Where does CBAM/carbon data collection become most manual between plant data, supplier evidence, and final reporting?"
    if "Aviation" in category:
        return "What part of CORSIA/SAF emissions evidence is hardest to collect and verify today?"
    if "Article 6" in category or "Carbon Markets" in category:
        return "Where do Article 6/CORSIA participants struggle most with MRV evidence and buyer confidence?"
    return "Where do teams still rely on spreadsheets, consultants, or manual checks to make carbon data audit-ready?"


def _total_progress(state: RunState, *, dry_run: bool) -> int:
    return sum(state.category_selected_counts.values()) if dry_run else len(state.accepted)


def _category_progress(state: RunState, category_name: str, *, dry_run: bool) -> int:
    return state.category_selected_counts[category_name] if dry_run else state.category_counts[category_name]


def _prepare_search_output_dir(root_outdir: Path, run_id: str) -> Path:
    output_dir = resolve_output_dir(root_outdir, run_id)
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise RuntimeError(f"Run output already exists and is not empty: {output_dir}. Use a new --run-id.")
        output_dir.rmdir()
    return output_dir


def _reject_unprocessed_candidates(state: RunState, candidates: list[dict[str, Any]], reason: str) -> None:
    for candidate in candidates:
        state.rejected.append({
            "reason": reason,
            "candidate_id": candidate.get("id"),
            "name": candidate.get("name"),
            "company": candidate.get("organization_name"),
        })
        state.decision_log.append(decision_audit_row(candidate, "rejected_before_enrichment", reason, candidate.get("scores")))


def run(config: RunConfig, client: ApolloClient | None = None) -> RunState:
    if not 1 <= config.batch_size <= 10:
        raise ValueError("batch_size must be between 1 and 10.")
    if config.target_count <= 0 or config.credit_cap <= 0:
        raise ValueError("target_count and credit_cap must be positive.")

    client = client or ApolloClient.from_env()
    exclusion = build_exclusion_set(config.exclusions)
    state = RunState()
    state.run_id = make_run_id(config)
    state.output_dir = _prepare_search_output_dir(config.outdir, state.run_id)

    for category in CATEGORIES:
        if _total_progress(state, dry_run=config.dry_run) >= config.target_count or state.credits_used >= config.credit_cap:
            break
        if _category_progress(state, category.name, dry_run=config.dry_run) >= category.max_accept:
            continue

        for page in range(1, config.pages_per_category + 1):
            if _total_progress(state, dry_run=config.dry_run) >= config.target_count or state.credits_used >= config.credit_cap:
                break
            if _category_progress(state, category.name, dry_run=config.dry_run) >= category.max_accept:
                break

            payload = category.payload(page=page, per_page=config.per_page)
            search_response = client.people_search(payload)
            people = search_response.get("people") or search_response.get("contacts") or []
            if not people:
                break

            candidates: list[dict[str, Any]] = []
            for rank_on_page, person in enumerate(people, start=1):
                state.searched_candidates += 1
                candidate = normalize_search_person(person, category.name)
                candidate["_search_category"] = category.name
                candidate["_search_page"] = page
                candidate["_search_rank_on_page"] = rank_on_page
                state.raw_candidates.append(
                    raw_search_row(person, candidate, category.name, page, rank_on_page, state.searched_candidates)
                )

                candidate_id = norm_text(candidate.get("id"))
                if not candidate_id or candidate_id in state.seen_apollo_ids:
                    state.rejected.append({"reason": "missing_or_seen_apollo_id", "candidate_id": candidate_id, "name": candidate.get("name"), "company": candidate.get("organization_name")})
                    state.decision_log.append(decision_audit_row(candidate, "rejected", "missing_or_seen_apollo_id"))
                    continue
                state.seen_apollo_ids.add(candidate_id)

                is_dup, reason = exclusion.is_duplicate_candidate(candidate)
                if is_dup:
                    state.rejected.append({"reason": reason, "candidate_id": candidate_id, "name": candidate.get("name"), "company": candidate.get("organization_name")})
                    state.decision_log.append(decision_audit_row(candidate, "rejected", reason))
                    continue

                scores = score_candidate(candidate, category.name)
                if scores["risk_level"] == "Hold":
                    state.rejected.append({"reason": "competitor_risk_hold", "candidate_id": candidate_id, "name": candidate.get("name"), "company": candidate.get("organization_name"), **scores})
                    state.decision_log.append(decision_audit_row(candidate, "rejected", "competitor_risk_hold", scores))
                    continue
                if state.company_counts[norm_text(candidate.get("organization_name"))] >= config.max_per_company:
                    state.rejected.append({"reason": "max_per_company_reached", "candidate_id": candidate_id, "company": candidate.get("organization_name")})
                    state.decision_log.append(decision_audit_row(candidate, "rejected", "max_per_company_reached", scores))
                    continue
                if not candidate.get("has_email"):
                    state.rejected.append({"reason": "apollo_search_no_email_flag", "candidate_id": candidate_id, "name": candidate.get("name"), "company": candidate.get("organization_name")})
                    state.decision_log.append(decision_audit_row(candidate, "rejected", "apollo_search_no_email_flag", scores))
                    continue

                candidate["scores"] = scores
                candidates.append(candidate)
                state.fresh_candidates += 1

            idx = 0
            while idx < len(candidates):
                total_progress = _total_progress(state, dry_run=config.dry_run)
                category_progress = _category_progress(state, category.name, dry_run=config.dry_run)

                if total_progress >= config.target_count:
                    _reject_unprocessed_candidates(state, candidates[idx:], "target_count_reached_before_enrichment")
                    break
                if state.credits_used >= config.credit_cap:
                    _reject_unprocessed_candidates(state, candidates[idx:], "credit_cap_reached_before_enrichment")
                    break
                if category_progress >= category.max_accept:
                    _reject_unprocessed_candidates(state, candidates[idx:], "category_cap_reached_before_enrichment")
                    break

                remaining_credit_room = config.credit_cap - state.credits_used
                remaining_target_room = config.target_count - total_progress
                remaining_category_room = category.max_accept - category_progress
                take = min(config.batch_size, remaining_credit_room, remaining_target_room, remaining_category_room, len(candidates) - idx)
                if take <= 0:
                    break

                batch = candidates[idx : idx + take]
                idx += take

                if config.dry_run:
                    for candidate in batch:
                        state.rejected.append({"reason": "dry_run_not_enriched", "candidate_id": candidate.get("id"), "name": candidate.get("name"), "company": candidate.get("organization_name")})
                        state.decision_log.append(decision_audit_row(candidate, "selected_for_enrichment", "dry_run_not_enriched", candidate.get("scores")))
                        state.category_selected_counts[category.name] += 1
                    continue

                details = [enrichment_details(candidate) for candidate in batch]
                response = client.bulk_people_enrich(details, reveal_personal_emails=config.reveal_personal_emails)
                matches = extract_matches(response)
                credits_value = response.get("credits_consumed")
                if credits_value is None:
                    credits_value = response.get("credits_used")
                credits = int(credits_value) if credits_value is not None else len(details)
                state.credits_used += credits

                for candidate in batch:
                    match = pick_match_for_candidate(matches, str(candidate.get("id")))
                    if not match:
                        state.rejected.append({"reason": "enriched_no_match", "candidate_id": candidate.get("id"), "name": candidate.get("name"), "company": candidate.get("organization_name")})
                        state.decision_log.append(decision_audit_row(candidate, "rejected_after_enrichment", "enriched_no_match", candidate.get("scores")))
                        continue
                    email = match.get("email") or match.get("work_email")
                    if not email:
                        state.rejected.append({"reason": "enriched_no_email", "candidate_id": candidate.get("id"), "name": candidate.get("name"), "company": candidate.get("organization_name")})
                        state.decision_log.append(decision_audit_row(candidate, "rejected_after_enrichment", "enriched_no_email", candidate.get("scores")))
                        continue

                    priority_no = len(state.accepted) + 1
                    row = build_final_row(candidate, match, category.name, priority_no, candidate["scores"])
                    state.accepted.append(row)
                    state.decision_log.append(decision_audit_row(candidate, "accepted", "accepted_with_email", candidate.get("scores"), email=email))
                    state.category_counts[category.name] += 1
                    state.company_counts[norm_text(row["Company / Organisation"])] += 1

                    exclusion.add_record({
                        "Apollo Person ID": row["Apollo Person ID"],
                        "Email": row["Email"],
                        "Full Name": row["Full Name"],
                        "Company / Organisation": row["Company / Organisation"],
                        "Title": row["Position / Title"],
                        "LinkedIn URL": row["LinkedIn URL or LinkedIn search route"],
                    })

            if _category_progress(state, category.name, dry_run=config.dry_run) >= category.max_accept:
                break

    run_meta = {
        "run_id": state.run_id,
        "output_dir": str(state.output_dir),
        "run_root_outdir": str(config.outdir),
        "target_count": config.target_count,
        "credit_cap": config.credit_cap,
        "credits_used_reported_by_apollo": state.credits_used,
        "accepted_email_count": len(state.accepted),
        "dry_run_selected_count": sum(state.category_selected_counts.values()),
        "searched_candidates": state.searched_candidates,
        "fresh_candidates_after_dedupe": state.fresh_candidates,
        "raw_apollo_rows_written": len(state.raw_candidates),
        "decision_audit_rows_written": len(state.decision_log),
        "unique_apollo_ids_seen": len(state.seen_apollo_ids),
        "rejected_count": len(state.rejected),
        "exclusion_files": ";".join(str(path) for path in config.exclusions),
        "exclusion_file_count": len(config.exclusions),
        "exclusion_rows_loaded": exclusion.raw_rows_loaded,
        "dry_run": config.dry_run,
        "personal_emails_requested": config.reveal_personal_emails,
        "locked_category_count": len(CATEGORIES),
    }
    assert state.output_dir is not None
    write_outputs(state.output_dir, state.accepted, state.rejected, run_meta, raw_candidates=state.raw_candidates, decision_log=state.decision_log)
    if config.write_latest_copy:
        copy_latest_snapshot(state.output_dir, config.outdir)
    if config.update_exclusion_ledger and not config.dry_run:
        append_exclusion_ledger(config.exclusion_dir, state.accepted, state.output_dir)
    if not config.dry_run:
        append_apollo_rejection_ledger(
            config.outdir,
            state.decision_log,
            state.output_dir,
            state.run_id,
        )
    return state
