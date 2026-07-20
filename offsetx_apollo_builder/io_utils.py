"""Input/output helpers for CSV/XLSX final artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

FINAL_COLUMNS = [
    "Priority ID", "Full Name", "First Name", "Last Name", "Position / Title",
    "Company / Organisation", "Category", "Country / Region", "Organisation Size",
    "Seniority Level", "Apollo Person ID", "LinkedIn URL or LinkedIn search route",
    "Email", "Email Status", "Public Source URL / Research Route", "Apollo Search Route / Basis",
    "Why Useful", "Why They May Reply", "Suggested Outreach Angle", "Suggested First Question",
    "Risk Level", "Risk Score", "Problem Relevance Score", "Decision Influence Score",
    "Reachability Score", "Reply Probability Score", "Non-Competitor Safety Score",
    "Source Confidence Score", "Overall Score", "Wave", "Assigned To", "Dedupe Status",
    "Source Status", "Next Action", "Notes",
]

APOLLO_REJECTION_LEDGER_COLUMNS = [
    "Ledger Identity",
    "Run ID",
    "Decision",
    "Reason",
    "Outcome Class",
    "Retry Policy",
    "Blocks Automatic Retry",
    "Permanent Exclusion",
    "Apollo Person ID",
    "Email Returned",
    "Input Email",
    "Full Name",
    "Company / Organisation",
    "Position / Title",
    "LinkedIn URL",
    "Source File",
    "Source Row Number",
    "First Seen At UTC",
    "Last Seen At UTC",
    "Occurrence Count",
    "Latest Run Output",
]


def safe_get(obj: dict, *keys: str) -> str:
    for key in keys:
        val = obj.get(key)
        if val not in (None, ""):
            return str(val)
    return ""


def _value_counts(df: pd.DataFrame, column: str, summary_type: str | None = None) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=["summary_type", "value", "count"])
    out = df[column].fillna("").astype(str).value_counts(dropna=False).reset_index()
    out.columns = ["value", "count"]
    out.insert(0, "summary_type", summary_type or column)
    return out


def build_analytics_tables(accepted_df: pd.DataFrame, rejected_df: pd.DataFrame, raw_df: pd.DataFrame, decision_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create audit summaries that explain what Apollo returned and what the script did with it."""
    reason_frames = []
    reason_frames.append(_value_counts(decision_df, "Reason", "decision_reason"))
    reason_frames.append(_value_counts(decision_df, "Decision", "decision_stage"))
    reason_frames.append(_value_counts(rejected_df, "reason", "legacy_rejected_reason"))
    reason_counts = pd.concat(reason_frames, ignore_index=True) if reason_frames else pd.DataFrame()

    category_rows = []
    if not raw_df.empty and "Apollo Search Category" in raw_df.columns:
        raw_counts = raw_df["Apollo Search Category"].fillna("").astype(str).value_counts().to_dict()
        categories = sorted(raw_counts)
        for cat in categories:
            row = {"Apollo Search Category": cat, "raw_apollo_candidates": raw_counts.get(cat, 0)}
            if not decision_df.empty and "Apollo Search Category" in decision_df.columns:
                sub = decision_df[decision_df["Apollo Search Category"].fillna("").astype(str) == cat]
                row["accepted"] = int((sub.get("Decision", pd.Series(dtype=str)) == "accepted").sum())
                row["selected_for_enrichment"] = int((sub.get("Decision", pd.Series(dtype=str)) == "selected_for_enrichment").sum())
                row["rejected_before_enrichment"] = int((sub.get("Decision", pd.Series(dtype=str)) == "rejected").sum())
                row["rejected_after_enrichment"] = int((sub.get("Decision", pd.Series(dtype=str)) == "rejected_after_enrichment").sum())
            category_rows.append(row)
    category_counts = pd.DataFrame(category_rows)

    funnel_rows = [
        {"metric": "raw_apollo_candidates_returned", "count": int(len(raw_df))},
        {"metric": "unique_apollo_ids_seen", "count": int(raw_df.get("Apollo Person ID", pd.Series(dtype=str)).astype(str).str.strip().replace("", pd.NA).dropna().nunique() if not raw_df.empty else 0)},
        {"metric": "decision_audit_rows", "count": int(len(decision_df))},
        {"metric": "accepted_with_email", "count": int(len(accepted_df))},
        {"metric": "rejected_or_not_enriched_rows", "count": int(len(rejected_df))},
    ]
    if not decision_df.empty and "Decision" in decision_df.columns:
        for value, count in decision_df["Decision"].fillna("").astype(str).value_counts().items():
            funnel_rows.append({"metric": f"decision_{value}", "count": int(count)})
    if not decision_df.empty and "Reason" in decision_df.columns:
        for value, count in decision_df["Reason"].fillna("").astype(str).value_counts().items():
            funnel_rows.append({"metric": f"reason_{value}", "count": int(count)})
    funnel = pd.DataFrame(funnel_rows)
    return reason_counts, category_counts, funnel




def _add_run_columns(df: pd.DataFrame, run_meta: dict) -> pd.DataFrame:
    """Add run identity columns so every CSV can be tied to one exact run."""
    run_id = str(run_meta.get("run_id", ""))
    if df.empty:
        # Keep empty CSV schemas readable where possible.
        if "Run ID" not in df.columns:
            df.insert(0, "Run ID", [])
        return df
    df = df.copy()
    if "Run ID" not in df.columns:
        df.insert(0, "Run ID", run_id)
    if "Run Mode" not in df.columns:
        df.insert(1, "Run Mode", "dry_run" if run_meta.get("dry_run") else "real_run")
    if "Run Output Dir" not in df.columns:
        df.insert(2, "Run Output Dir", str(run_meta.get("output_dir", "")))
    return df


def _append_dedup_csv(path: Path, new_df: pd.DataFrame, dedupe_subset: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        combined = pd.concat([old, new_df.astype(str)], ignore_index=True).fillna("")
    else:
        combined = new_df.astype(str).fillna("")
    subset = [c for c in dedupe_subset if c in combined.columns]
    if subset:
        combined = combined.drop_duplicates(subset=subset, keep="last")
    combined.to_csv(path, index=False)


def update_master_run_analytics(root_outdir: Path, run_meta: dict, reason_counts_df: pd.DataFrame, category_counts_df: pd.DataFrame, funnel_df: pd.DataFrame) -> None:
    """Append compact cross-run analytics while preserving per-run immutable folders."""
    root_outdir.mkdir(parents=True, exist_ok=True)
    meta_df = _add_run_columns(pd.DataFrame([run_meta]), run_meta)
    reason_df = _add_run_columns(reason_counts_df, run_meta)
    category_df = _add_run_columns(category_counts_df, run_meta)
    funnel_run_df = _add_run_columns(funnel_df, run_meta)

    _append_dedup_csv(root_outdir / "offsetx_runs_index.csv", meta_df, ["run_id", "Run ID"])
    _append_dedup_csv(root_outdir / "offsetx_all_run_reason_counts.csv", reason_df, ["Run ID", "summary_type", "value"])
    _append_dedup_csv(root_outdir / "offsetx_all_run_category_counts.csv", category_df, ["Run ID", "Apollo Search Category"])
    _append_dedup_csv(root_outdir / "offsetx_all_run_funnel.csv", funnel_run_df, ["Run ID", "metric"])

def write_outputs(outdir: Path, accepted: list[dict], rejected: list[dict], run_meta: dict, raw_candidates: list[dict] | None = None, decision_log: list[dict] | None = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(accepted)
    if not df.empty:
        for col in FINAL_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[FINAL_COLUMNS]
    else:
        df = pd.DataFrame(columns=FINAL_COLUMNS)

    rejected_df = pd.DataFrame(rejected)
    raw_df = pd.DataFrame(raw_candidates or [])
    decision_df = pd.DataFrame(decision_log or [])
    meta_df = pd.DataFrame([run_meta])
    summary_rows = []
    if not df.empty:
        for key in ["Category", "Country / Region", "Risk Level", "Assigned To", "Wave"]:
            summary = df[key].value_counts(dropna=False).reset_index()
            summary.columns = [key, "count"]
            summary["summary_type"] = key
            summary_rows.extend(summary.to_dict(orient="records"))
    summary_df = pd.DataFrame(summary_rows)
    reason_counts_df, category_counts_df, funnel_df = build_analytics_tables(df, rejected_df, raw_df, decision_df)

    df = _add_run_columns(df, run_meta)
    rejected_df = _add_run_columns(rejected_df, run_meta)
    raw_df = _add_run_columns(raw_df, run_meta)
    decision_df = _add_run_columns(decision_df, run_meta)
    meta_df = _add_run_columns(meta_df, run_meta)
    summary_df = _add_run_columns(summary_df, run_meta)
    reason_counts_df = _add_run_columns(reason_counts_df, run_meta)
    category_counts_df = _add_run_columns(category_counts_df, run_meta)
    funnel_df = _add_run_columns(funnel_df, run_meta)

    df.to_csv(outdir / "offsetx_final_pois_with_emails.csv", index=False)
    rejected_df.to_csv(outdir / "offsetx_rejected_duplicate_conflict_log.csv", index=False)
    raw_df.to_csv(outdir / "offsetx_apollo_raw_search_candidates.csv", index=False)
    decision_df.to_csv(outdir / "offsetx_candidate_decision_audit.csv", index=False)
    meta_df.to_csv(outdir / "offsetx_run_summary.csv", index=False)
    summary_df.to_csv(outdir / "offsetx_summary_tables.csv", index=False)
    reason_counts_df.to_csv(outdir / "offsetx_analytics_reason_counts.csv", index=False)
    category_counts_df.to_csv(outdir / "offsetx_analytics_category_counts.csv", index=False)
    funnel_df.to_csv(outdir / "offsetx_analytics_funnel.csv", index=False)

    with pd.ExcelWriter(outdir / "offsetx_final_pois_with_emails.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Final_POIs", index=False)
        summary_df.to_excel(writer, sheet_name="Summaries", index=False)
        rejected_df.to_excel(writer, sheet_name="Rejected_Log", index=False)
        decision_df.to_excel(writer, sheet_name="Decision_Audit", index=False)
        raw_df.to_excel(writer, sheet_name="Raw_Apollo_Search", index=False)
        reason_counts_df.to_excel(writer, sheet_name="Reason_Counts", index=False)
        category_counts_df.to_excel(writer, sheet_name="Category_Counts", index=False)
        funnel_df.to_excel(writer, sheet_name="Funnel", index=False)
        meta_df.to_excel(writer, sheet_name="Run_Metadata", index=False)

    (outdir / "run_meta.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    root_outdir_value = run_meta.get("run_root_outdir")
    if root_outdir_value:
        update_master_run_analytics(Path(str(root_outdir_value)), run_meta, reason_counts_df, category_counts_df, funnel_df)


def append_exclusion_ledger(exclusion_dir: Path, accepted: list[dict], outdir: Path) -> Path | None:
    """Persist newly accepted contacts so the next run automatically excludes them.

    The ledger is deliberately a small CSV with the strongest identity keys only.
    It prevents the common mistake: running a 5-contact test, then a 250-contact
    run, and having Apollo return the same first 5 again.
    """
    if not accepted:
        return None

    exclusion_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in accepted:
        rows.append({
            "Apollo Person ID": row.get("Apollo Person ID", ""),
            "Email": row.get("Email", ""),
            "Full Name": row.get("Full Name", ""),
            "First Name": row.get("First Name", ""),
            "Last Name": row.get("Last Name", ""),
            "Company / Organisation": row.get("Company / Organisation", ""),
            "Position / Title": row.get("Position / Title", ""),
            "LinkedIn URL": row.get("LinkedIn URL or LinkedIn search route", ""),
            "Source": "offsetx_apollo_builder_auto_ledger",
        })

    new_df = pd.DataFrame(rows)

    ledger_path = exclusion_dir / "offsetx_auto_exclusion_ledger.csv"
    if ledger_path.exists():
        existing = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
        combined = pd.concat([existing, new_df], ignore_index=True).fillna("")
    else:
        combined = new_df

    # Dedupe ledger by strongest available keys, preserving earliest row.
    for key in ["Apollo Person ID", "Email", "LinkedIn URL"]:
        if key in combined.columns:
            mask = combined[key].astype(str).str.strip().ne("")
            combined_nonempty = combined[mask].drop_duplicates(subset=[key], keep="first")
            combined_empty = combined[~mask]
            combined = pd.concat([combined_nonempty, combined_empty], ignore_index=True)

    combined.to_csv(ledger_path, index=False)

    # Also write a per-run exclusion artifact next to the final output.
    outdir.mkdir(parents=True, exist_ok=True)
    new_run_path = outdir / "offsetx_new_accepts_for_exclusion.csv"
    new_df.to_csv(new_run_path, index=False)
    return ledger_path


def _apollo_rejection_policy(reason: str) -> tuple[str, str, bool, bool]:
    reason = str(reason or "").strip().lower()
    if reason.startswith("duplicate_") or reason.startswith("near_duplicate_"):
        return "duplicate", "blocked_permanently", True, True
    if reason.startswith("previously_attempted_apollo_"):
        permanent = reason.endswith("accepted_with_email")
        return "prior_apollo_attempt", "manual_override", True, permanent
    if reason in {"enriched_no_match", "enriched_no_email"}:
        return "apollo_result", "manual_override", True, False
    if reason in {
        "credit_cap_reached_before_enrichment",
        "target_count_reached_before_enrichment",
    }:
        return "run_limit", "retry_next_run", False, False
    if reason in {"competitor_risk_hold"}:
        return "policy_hold", "manual_review", True, False
    if reason.startswith("missing_") or reason in {"not_matchable_for_apollo"}:
        return "input_quality", "fix_input_then_retry", False, False
    return "screening_rejection", "manual_review", True, False


def _apollo_rejection_identity(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("Apollo Person ID") or "").strip().lower(),
        str(row.get("LinkedIn URL") or "").strip().lower().rstrip("/"),
        str(row.get("Email Returned") or row.get("Input Email") or "").strip().lower(),
        str(row.get("Full Name") or "").strip().lower(),
        str(row.get("Company / Organisation") or "").strip().lower(),
        str(row.get("Source File") or "").strip().lower(),
        str(row.get("Source Row Number") or "").strip().lower(),
    ]
    material = "||".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def append_apollo_rejection_ledger(
    ledger_root: Path,
    decision_log: list[dict[str, Any]],
    run_output_dir: Path,
    run_id: str,
) -> Path | None:
    """Persist visible Apollo/screening rejects without polluting exclusions.

    This ledger lives beside output roots, never under ``old_pois``. Otherwise a
    generic exclusion scan would incorrectly treat retryable no-match rows as
    permanent duplicates. Accepted Apollo contacts still enter the separate
    permanent exclusion ledger through :func:`append_exclusion_ledger`.
    """
    now = datetime.now(timezone.utc).isoformat()
    additions: list[dict[str, Any]] = []
    for source in decision_log:
        decision = str(source.get("Decision") or "").strip()
        if decision in {"", "accepted", "selected_for_enrichment"}:
            continue
        reason = str(source.get("Reason") or "").strip()
        outcome_class, retry_policy, blocks_retry, permanent = _apollo_rejection_policy(reason)
        row = {
            "Run ID": run_id,
            "Decision": decision,
            "Reason": reason,
            "Outcome Class": outcome_class,
            "Retry Policy": retry_policy,
            "Blocks Automatic Retry": str(blocks_retry).lower(),
            "Permanent Exclusion": str(permanent).lower(),
            "Apollo Person ID": source.get("Apollo Person ID", ""),
            "Email Returned": source.get("Email Returned", ""),
            "Input Email": source.get("Input Email", ""),
            "Full Name": source.get("Full Name", ""),
            "Company / Organisation": source.get("Company / Organisation", ""),
            "Position / Title": source.get("Position / Title", ""),
            "LinkedIn URL": source.get("LinkedIn URL", ""),
            "Source File": source.get("Source File", ""),
            "Source Row Number": source.get("Source Row Number", ""),
            "First Seen At UTC": now,
            "Last Seen At UTC": now,
            "Occurrence Count": "1",
            "Latest Run Output": str(run_output_dir),
        }
        row["Ledger Identity"] = _apollo_rejection_identity(row)
        additions.append(row)
    if not additions:
        return None

    ledger_root.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_root / "offsetx_apollo_rejection_ledger.csv"
    existing_rows: list[dict[str, Any]] = []
    if ledger_path.exists() and ledger_path.stat().st_size:
        existing_rows = pd.read_csv(ledger_path, dtype=str, keep_default_na=False).to_dict(
            orient="records"
        )
    keyed: dict[tuple[str, str], dict[str, Any]] = {
        (str(row.get("Ledger Identity", "")), str(row.get("Reason", ""))): {
            column: row.get(column, "") for column in APOLLO_REJECTION_LEDGER_COLUMNS
        }
        for row in existing_rows
    }
    for row in additions:
        key = (row["Ledger Identity"], row["Reason"])
        prior = keyed.get(key)
        if prior:
            row["First Seen At UTC"] = prior.get("First Seen At UTC") or now
            try:
                row["Occurrence Count"] = str(int(prior.get("Occurrence Count") or 0) + 1)
            except ValueError:
                row["Occurrence Count"] = "1"
        keyed[key] = row

    frame = pd.DataFrame(keyed.values(), columns=APOLLO_REJECTION_LEDGER_COLUMNS)
    frame = frame.sort_values("Last Seen At UTC", ascending=False)
    temporary = ledger_path.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(ledger_path)
    frame.to_csv(run_output_dir / "offsetx_apollo_rejection_ledger_snapshot.csv", index=False)
    return ledger_path


def read_apollo_rejection_ledgers(
    paths: Iterable[Path],
    *,
    limit: int = 200,
    offset: int = 0,
    reason: str = "",
) -> tuple[list[dict[str, Any]], int]:
    frames: list[pd.DataFrame] = []
    seen_paths: set[str] = set()
    for path in paths:
        if not path.exists() or not path.is_file() or not path.stat().st_size:
            continue
        key = str(path.resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        frames.append(pd.read_csv(path, dtype=str, keep_default_na=False))
    if not frames:
        return [], 0
    frame = pd.concat(frames, ignore_index=True).fillna("")
    if reason:
        frame = frame[frame.get("Reason", pd.Series(dtype=str)).astype(str) == reason]
    if {"Ledger Identity", "Reason"}.issubset(frame.columns):
        frame = frame.sort_values("Last Seen At UTC", ascending=False).drop_duplicates(
            subset=["Ledger Identity", "Reason"], keep="first"
        )
    total = len(frame)
    selected = frame.iloc[max(0, offset) : max(0, offset) + max(1, min(limit, 1000))]
    items: list[dict[str, Any]] = []
    for raw in selected.to_dict(orient="records"):
        items.append(
            {
                "identity": raw.get("Ledger Identity", ""),
                "run_id": raw.get("Run ID", ""),
                "decision": raw.get("Decision", ""),
                "reason": raw.get("Reason", ""),
                "outcome_class": raw.get("Outcome Class", ""),
                "retry_policy": raw.get("Retry Policy", ""),
                "blocks_automatic_retry": str(raw.get("Blocks Automatic Retry", "")).lower() == "true",
                "permanent_exclusion": str(raw.get("Permanent Exclusion", "")).lower() == "true",
                "apollo_person_id": raw.get("Apollo Person ID", ""),
                "email": raw.get("Email Returned", "") or raw.get("Input Email", ""),
                "full_name": raw.get("Full Name", ""),
                "company": raw.get("Company / Organisation", ""),
                "title": raw.get("Position / Title", ""),
                "linkedin_url": raw.get("LinkedIn URL", ""),
                "source_file": raw.get("Source File", ""),
                "last_seen_at": raw.get("Last Seen At UTC", ""),
                "occurrence_count": int(raw.get("Occurrence Count") or 0),
            }
        )
    return items, total


def read_apollo_exclusion_ledgers(
    paths: Iterable[Path],
    *,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    frames: list[pd.DataFrame] = []
    seen_paths: set[str] = set()
    for path in paths:
        if not path.exists() or not path.is_file() or not path.stat().st_size:
            continue
        key = str(path.resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        frames.append(pd.read_csv(path, dtype=str, keep_default_na=False))
    if not frames:
        return [], 0
    frame = pd.concat(frames, ignore_index=True).fillna("")
    for key in ("Apollo Person ID", "Email", "LinkedIn URL"):
        if key not in frame.columns:
            continue
        populated = frame[key].astype(str).str.strip().ne("")
        frame = pd.concat(
            [
                frame[populated].drop_duplicates(subset=[key], keep="first"),
                frame[~populated],
            ],
            ignore_index=True,
        )
    total = len(frame)
    selected = frame.iloc[max(0, offset) : max(0, offset) + max(1, min(limit, 1000))]
    items = [
        {
            "apollo_person_id": row.get("Apollo Person ID", ""),
            "email": row.get("Email", ""),
            "full_name": row.get("Full Name", ""),
            "company": row.get("Company / Organisation", ""),
            "title": row.get("Position / Title", ""),
            "linkedin_url": row.get("LinkedIn URL", ""),
            "source": row.get("Source", ""),
        }
        for row in selected.to_dict(orient="records")
    ]
    return items, total
