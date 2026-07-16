from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.existing_poi_enrichment import ExistingPoiEnrichmentConfig, run_existing_poi_enrichment


class FakeBulkApolloClient:
    def __init__(self):
        self.enrich_calls = 0
        self.details_seen = []

    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        self.enrich_calls += 1
        self.details_seen.extend(details)
        matches = []
        for i, detail in enumerate(details, start=1):
            first = detail.get("first_name") or f"First{i}"
            last = detail.get("last_name") or f"Last{i}"
            company = detail.get("organization_name") or "Example Co"
            matches.append({
                "id": detail.get("id") or f"{i:024x}",
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}".strip(),
                "title": "Trade Compliance Manager",
                "email": f"{first.lower()}.{last.lower()}@example.com",
                "email_status": "verified",
                "linkedin_url": detail.get("linkedin_url", ""),
                "organization": {"name": company, "estimated_num_employees": 500},
            })
        return {"matches": matches, "credits_consumed": len(matches)}


def test_existing_poi_enrichment_moves_file_and_writes_outputs(tmp_path: Path):
    inbox = tmp_path / "queue" / "inbox"
    processing = tmp_path / "queue" / "processing"
    processed = tmp_path / "queue" / "processed"
    failed = tmp_path / "queue" / "failed"
    inbox.mkdir(parents=True)

    input_file = inbox / "pois.xlsx"
    pd.DataFrame([
        {
            "Full Name": "Asha Rao",
            "Position / Title": "Trade Compliance Manager",
            "Company / Organisation": "Exporter One",
            "LinkedIn URL": "https://www.linkedin.com/in/asha-rao/",
            "Category": "CBAM / Trade Compliance",
        },
        {
            "Full Name": "Ben Shah",
            "Position / Title": "Sustainability Manager",
            "Company / Organisation": "Exporter Two",
            "Email": "ben.shah@example.com",
            "Category": "ESG",
        },
    ]).to_excel(input_file, index=False)

    exclusions = tmp_path / "exclusions.csv"
    pd.DataFrame(columns=["Email", "Apollo Person ID", "LinkedIn URL"]).to_csv(exclusions, index=False)

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[exclusions],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=processing,
        processed_dir=processed,
        failed_dir=failed,
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=10,
        batch_size=10,
        run_id="test_existing_pois",
        write_latest_copy=True,
    )
    state = run_existing_poi_enrichment(cfg, client=FakeBulkApolloClient())

    assert not input_file.exists()
    assert list(processing.glob("*")) == []
    assert len(list(processed.glob("*.xlsx"))) == 1
    assert list(failed.glob("*")) == []
    assert state.input_rows_seen == 2
    assert state.credits_used == 1
    assert len(state.accepted) == 2

    run_dir = tmp_path / "out" / "runs" / "test_existing_pois"
    assert (run_dir / "offsetx_final_pois_with_emails.csv").exists()
    assert (run_dir / "offsetx_input_pois_normalized.csv").exists()
    assert (run_dir / "offsetx_input_file_manifest.csv").exists()
    assert (run_dir / "offsetx_apollo_bulk_match_raw_responses.jsonl").exists()

    final_df = pd.read_csv(run_dir / "offsetx_final_pois_with_emails.csv")
    assert set(final_df["Assigned To"]) == {"Kunal", "Sahil"}
    assert "Sustainability / ESG / Climate" in set(final_df["Category"])


def test_existing_poi_enrichment_dry_run_spends_zero_credits(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    pd.DataFrame([{
        "Name": "Cara Mehta",
        "Title": "Carbon Markets Manager",
        "Company": "Carbon Buyer Co",
        "LinkedIn": "https://www.linkedin.com/in/cara-mehta/",
    }]).to_csv(inbox / "pois.csv", index=False)
    exclusions = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email"]).to_csv(exclusions, index=False)

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[exclusions],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "processing",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        dry_run=True,
        run_id="dry_existing_pois",
    )
    state = run_existing_poi_enrichment(cfg, client=FakeBulkApolloClient())

    assert state.credits_used == 0
    assert len(state.accepted) == 0
    assert len(state.rejected) == 1
    assert state.rejected[0]["reason"] == "dry_run_not_enriched"


def test_company_name_header_is_recognized_and_does_not_require_linkedin(tmp_path: Path):
    """Regression test for the exact header used by OffsetX Apollo-ready CSVs."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    pd.DataFrame([
        {
            "First Name": "Nicola",
            "Last Name": "Kimm",
            "Title": "Chief Sustainability Officer",
            "Company Name": "Heidelberg Materials",
            "Email": "",
            "Person Linkedin Url": "",
        },
        {
            "First Name": "Nollaig",
            "Last Name": "Forrest",
            "Title": "Chief Sustainability Officer",
            "Company Name": "Holcim",
            "Email": "",
            "Person Linkedin Url": "",
        },
    ]).to_csv(inbox / "apollo_ready.csv", index=False)

    exclusions = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email", "Apollo Person ID", "LinkedIn URL"]).to_csv(exclusions, index=False)

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[exclusions],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "processing",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        dry_run=True,
        run_id="company_name_header_regression",
    )
    state = run_existing_poi_enrichment(cfg, client=FakeBulkApolloClient())

    assert state.input_rows_seen == 2
    assert state.selected_for_enrichment == 2
    assert {row["reason"] for row in state.rejected} == {"dry_run_not_enriched"}
    assert {row["company"] for row in state.rejected} == {"Heidelberg Materials", "Holcim"}


def test_company_name_header_is_sent_to_apollo(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    pd.DataFrame([{
        "First Name": "Caroline",
        "Last Name": "Drischel",
        "Title": "Head of Corporate Responsibility",
        "Company Name": "Lufthansa Group",
        "Person Linkedin Url": "",
    }]).to_csv(inbox / "apollo_ready.csv", index=False)

    exclusions = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email"]).to_csv(exclusions, index=False)
    client = FakeBulkApolloClient()

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[exclusions],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "processing",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=1,
        batch_size=1,
        run_id="company_name_live_regression",
    )
    state = run_existing_poi_enrichment(cfg, client=client)

    assert state.selected_for_enrichment == 1
    assert state.credits_used == 1
    assert client.details_seen[0]["organization_name"] == "Lufthansa Group"


class CountingNoEmailApolloClient:
    def __init__(self):
        self.enrich_calls = 0

    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        self.enrich_calls += 1
        matches = []
        for i, detail in enumerate(details, start=1):
            matches.append({
                "id": f"noemail-{i}",
                "first_name": detail.get("first_name", ""),
                "last_name": detail.get("last_name", ""),
                "name": f"{detail.get('first_name', '')} {detail.get('last_name', '')}".strip(),
                "email": "",
                "email_status": "unavailable",
                "linkedin_url": detail.get("linkedin_url", ""),
                "organization": {"name": detail.get("organization_name", "")},
            })
        return {"matches": matches, "credits_consumed": len(details)}


def _write_repeat_person(path: Path) -> None:
    pd.DataFrame([{
        "First Name": "Repeat",
        "Last Name": "Person",
        "Title": "Sustainability Director",
        "Company Name": "Repeat Company",
        "Person Linkedin Url": "",
    }]).to_csv(path, index=False)


def test_attempt_ledger_prevents_repeat_credit_after_no_email(tmp_path: Path):
    inbox = tmp_path / "queue" / "inbox"
    inbox.mkdir(parents=True)
    _write_repeat_person(inbox / "first.csv")
    exclusions = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email"]).to_csv(exclusions, index=False)
    client = CountingNoEmailApolloClient()

    common = dict(
        exclusions=[exclusions],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=tmp_path / "queue" / "processed",
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        batch_size=1,
    )
    first_state = run_existing_poi_enrichment(
        ExistingPoiEnrichmentConfig(**common, run_id="first_live"),
        client=client,
    )
    assert client.enrich_calls == 1
    assert first_state.credits_used == 1
    assert (tmp_path / "old_pois" / "offsetx_apollo_enrichment_attempt_ledger.csv").exists()

    _write_repeat_person(inbox / "second.csv")
    second_state = run_existing_poi_enrichment(
        ExistingPoiEnrichmentConfig(**common, run_id="second_live"),
        client=client,
    )

    assert client.enrich_calls == 1, "Second run must not call Apollo for the same person"
    assert second_state.selected_for_enrichment == 0
    assert second_state.previously_attempted_skipped == 1
    assert second_state.credits_used == 0
    assert second_state.rejected[0]["reason"] == "previously_attempted_apollo_matched_no_email"


def test_attempt_ledger_auto_backfills_historical_raw_response(tmp_path: Path):
    historical_dir = tmp_path / "out" / "runs" / "old_live_run"
    historical_dir.mkdir(parents=True)
    raw_payload = {
        "batch_start_index": 0,
        "batch_size": 1,
        "credits_reported": 1,
        "details": [{
            "first_name": "Historical",
            "last_name": "Person",
            "organization_name": "Historical Company",
        }],
        "response": {
            "matches": [{
                "id": "historical-apollo-id",
                "first_name": "Historical",
                "last_name": "Person",
                "name": "Historical Person",
                "email": "",
                "organization": {"name": "Historical Company"},
            }],
            "credits_consumed": 1,
        },
    }
    import json
    (historical_dir / "offsetx_apollo_bulk_match_raw_responses.jsonl").write_text(
        json.dumps(raw_payload) + "\n",
        encoding="utf-8",
    )

    inbox = tmp_path / "queue" / "inbox"
    inbox.mkdir(parents=True)
    pd.DataFrame([{
        "First Name": "Historical",
        "Last Name": "Person",
        "Title": "Climate Manager",
        "Company Name": "Historical Company",
    }]).to_csv(inbox / "historical.csv", index=False)
    exclusions = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email"]).to_csv(exclusions, index=False)
    client = CountingNoEmailApolloClient()

    state = run_existing_poi_enrichment(
        ExistingPoiEnrichmentConfig(
            exclusions=[exclusions],
            outdir=tmp_path / "out",
            input_dir=inbox,
            processing_dir=tmp_path / "queue" / "processing",
            processed_dir=tmp_path / "queue" / "processed",
            failed_dir=tmp_path / "queue" / "failed",
            exclusion_dir=tmp_path / "old_pois",
            credit_cap=5,
            batch_size=1,
            run_id="new_run",
        ),
        client=client,
    )

    assert state.attempt_ledger_backfilled == 1
    assert state.previously_attempted_skipped == 1
    assert state.selected_for_enrichment == 0
    assert state.credits_used == 0
    assert client.enrich_calls == 0


def test_empty_inbox_raises_clean_domain_error_without_creating_run_dir(tmp_path: Path):
    from offsetx_apollo_builder.existing_poi_enrichment import NoInputFilesError

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[],
        outdir=tmp_path / "out",
        input_dir=tmp_path / "queue" / "inbox",
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=tmp_path / "queue" / "processed",
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        dry_run=True,
        run_id="empty_inbox",
    )

    import pytest

    with pytest.raises(NoInputFilesError):
        run_existing_poi_enrichment(cfg)

    assert not (tmp_path / "out" / "runs" / "empty_inbox").exists()


def test_reuse_latest_processed_preserves_archive_and_processes_copy(tmp_path: Path):
    processed = tmp_path / "queue" / "processed"
    processed.mkdir(parents=True)
    archived = processed / "archived.csv"
    _write_repeat_person(archived)

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[],
        outdir=tmp_path / "out",
        input_dir=tmp_path / "queue" / "inbox",
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=processed,
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        dry_run=True,
        run_id="reuse_latest",
        reuse_latest_processed=True,
    )

    state = run_existing_poi_enrichment(cfg)

    assert archived.exists(), "The archived source must remain untouched"
    assert state.input_rows_seen == 1
    assert state.selected_for_enrichment == 1
    assert len(list(processed.glob("*.csv"))) == 2, "A new processed copy should be archived for the new run"
    assert list((tmp_path / "queue" / "processing").glob("*")) == []


def test_nonempty_duplicate_run_id_stops_before_claiming_inbox_file(tmp_path: Path):
    from offsetx_apollo_builder.existing_poi_enrichment import RunOutputExistsError

    inbox = tmp_path / "queue" / "inbox"
    inbox.mkdir(parents=True)
    source = inbox / "source.csv"
    _write_repeat_person(source)

    run_dir = tmp_path / "out" / "runs" / "same_id"
    run_dir.mkdir(parents=True)
    (run_dir / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=tmp_path / "queue" / "processed",
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=5,
        dry_run=True,
        run_id="same_id",
    )

    import pytest

    with pytest.raises(RunOutputExistsError):
        run_existing_poi_enrichment(cfg)

    assert source.exists(), "Output collision must be detected before the inbox file is claimed"
    assert list((tmp_path / "queue" / "processing").glob("*")) == []


class FailingApolloClient:
    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        raise RuntimeError("simulated Apollo outage")


def test_apollo_failure_moves_claimed_file_to_failed_not_processed(tmp_path: Path):
    inbox = tmp_path / "queue" / "inbox"
    inbox.mkdir(parents=True)
    _write_repeat_person(inbox / "source.csv")

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=tmp_path / "queue" / "processed",
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=1,
        batch_size=1,
        run_id="apollo_failure",
    )

    import pytest

    with pytest.raises(RuntimeError, match="simulated Apollo outage"):
        run_existing_poi_enrichment(cfg, client=FailingApolloClient())

    assert list((tmp_path / "queue" / "processing").glob("*")) == []
    assert list((tmp_path / "queue" / "processed").glob("*")) == []
    assert len(list((tmp_path / "queue" / "failed").glob("*.csv"))) == 1
    assert (tmp_path / "out" / "runs" / "apollo_failure" / "run_failed.json").exists()


class PositionalNullApolloClient:
    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        assert len(details) == 2
        return {
            "matches": [
                None,
                {
                    "id": "second-id",
                    "first_name": details[1]["first_name"],
                    "last_name": details[1]["last_name"],
                    "name": f"{details[1]['first_name']} {details[1]['last_name']}",
                    "email": "second@example.com",
                    "email_status": "verified",
                    "organization": {"name": details[1]["organization_name"]},
                },
            ],
            "credits_consumed": 2,
        }


def test_positional_null_match_does_not_shift_email_to_wrong_person(tmp_path: Path):
    inbox = tmp_path / "queue" / "inbox"
    inbox.mkdir(parents=True)
    pd.DataFrame([
        {"First Name": "First", "Last Name": "Missing", "Company Name": "One Co", "Title": "Manager"},
        {"First Name": "Second", "Last Name": "Found", "Company Name": "Two Co", "Title": "Director"},
    ]).to_csv(inbox / "two.csv", index=False)

    cfg = ExistingPoiEnrichmentConfig(
        exclusions=[],
        outdir=tmp_path / "out",
        input_dir=inbox,
        processing_dir=tmp_path / "queue" / "processing",
        processed_dir=tmp_path / "queue" / "processed",
        failed_dir=tmp_path / "queue" / "failed",
        exclusion_dir=tmp_path / "old_pois",
        credit_cap=2,
        batch_size=2,
        run_id="positional_null",
    )

    state = run_existing_poi_enrichment(cfg, client=PositionalNullApolloClient())

    assert len(state.accepted) == 1
    assert state.accepted[0]["Full Name"] == "Second Found"
    assert state.accepted[0]["Email"] == "second@example.com"
    assert any(row["reason"] == "enriched_no_match" and row["name"] == "First Missing" for row in state.rejected)
