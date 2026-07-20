from pathlib import Path

import pandas as pd

import offsetx_apollo_builder.runner as runner_module
from offsetx_apollo_builder.categories import CATEGORIES, SearchCategory
from offsetx_apollo_builder.locked_categories import LOCKED_CATEGORIES
from offsetx_apollo_builder.runner import RunConfig, run


class ManyPeopleApolloClient:
    def __init__(self, count: int = 6):
        self.count = count
        self.search_calls = 0

    def people_search(self, payload):
        self.search_calls += 1
        if self.search_calls > 1:
            return {"people": []}
        return {
            "people": [
                {
                    "id": f"{i:024x}",
                    "first_name": f"First{i}",
                    "last_name": f"Last{i}",
                    "name": f"First{i} Last{i}",
                    "title": "Trade Compliance Manager",
                    "has_email": True,
                    "organization": {"name": f"Company{i}", "primary_domain": f"company{i}.com"},
                }
                for i in range(1, self.count + 1)
            ]
        }

    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        return {
            "matches": [
                {
                    "id": detail["id"],
                    "first_name": "First",
                    "last_name": "Last",
                    "name": "First Last",
                    "title": "Trade Compliance Manager",
                    "email": f"{detail['id']}@example.com",
                    "email_status": "verified",
                    "organization": {"name": f"Org-{detail['id']}"},
                }
                for detail in details
            ],
            "credits_consumed": len(details),
        }


def _empty_exclusion(tmp_path: Path) -> Path:
    path = tmp_path / "empty.csv"
    pd.DataFrame(columns=["Email", "Apollo Person ID"]).to_csv(path, index=False)
    return path


def test_search_categories_exactly_match_locked_categories():
    assert tuple(category.name for category in CATEGORIES) == LOCKED_CATEGORIES
    assert len(CATEGORIES) == 9


def test_live_category_cap_is_enforced_during_acceptance(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "CATEGORIES",
        [SearchCategory(name="CBAM / Trade Compliance", person_titles=["trade compliance manager"], max_accept=2)],
    )
    state = run(
        RunConfig(
            exclusions=[_empty_exclusion(tmp_path)],
            outdir=tmp_path / "out",
            target_count=5,
            credit_cap=5,
            batch_size=5,
            pages_per_category=1,
            run_id="cap_live",
        ),
        client=ManyPeopleApolloClient(),
    )
    assert len(state.accepted) == 2
    assert state.category_counts["CBAM / Trade Compliance"] == 2
    assert any(row["reason"] == "category_cap_reached_before_enrichment" for row in state.rejected)
    assert set(row["Assigned To"] for row in state.accepted) == {"Kunal", "Sahil"}


def test_dry_run_honours_target_count_instead_of_selecting_every_search_result(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "CATEGORIES",
        [SearchCategory(name="CBAM / Trade Compliance", person_titles=["trade compliance manager"], max_accept=10)],
    )
    state = run(
        RunConfig(
            exclusions=[_empty_exclusion(tmp_path)],
            outdir=tmp_path / "out",
            target_count=3,
            credit_cap=10,
            batch_size=5,
            pages_per_category=1,
            dry_run=True,
            run_id="cap_dry",
        ),
        client=ManyPeopleApolloClient(),
    )
    assert sum(state.category_selected_counts.values()) == 3
    assert state.credits_used == 0
    assert any(row["reason"] == "target_count_reached_before_enrichment" for row in state.rejected)
