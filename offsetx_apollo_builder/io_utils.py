"""Input/output helpers for CSV/XLSX final artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

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
