from pathlib import Path

import pandas as pd

from offsetx_apollo_builder.runner import RunConfig, run


class FakeApolloClient:
    def __init__(self):
        self.search_calls = 0
        self.enrich_calls = 0

    def people_search(self, payload):
        self.search_calls += 1
        if self.search_calls > 1:
            return {"people": []}
        people = []
        for i in range(1, 6):
            people.append({
                "id": f"{i:024x}",
                "first_name": f"First{i}",
                "last_name": f"Last{i}",
                "title": "Trade Compliance Manager",
                "has_email": True,
                "organization": {"name": f"Company{i}", "primary_domain": f"company{i}.com"},
            })
        return {"people": people}

    def bulk_people_enrich(self, details, reveal_personal_emails=False):
        self.enrich_calls += 1
        matches = []
        for d in details:
            matches.append({
                "id": d["id"],
                "first_name": "First",
                "last_name": "Last",
                "name": "First Last",
                "title": "Trade Compliance Manager",
                "email": f"{d['id']}@example.com",
                "email_status": "verified",
                "organization": {"name": "Company", "estimated_num_employees": 1000},
            })
        return {"matches": matches, "credits_consumed": len(matches)}


def test_credit_cap_stops_at_cap(tmp_path: Path):
    exclusions = tmp_path / "exclusions.csv"
    pd.DataFrame(columns=["Full Name", "Company / Organisation", "Apollo Person ID", "Email"]).to_csv(exclusions, index=False)
    cfg = RunConfig(exclusions=[exclusions], outdir=tmp_path / "out", target_count=5, credit_cap=3, batch_size=10, pages_per_category=1)
    state = run(cfg, client=FakeApolloClient())
    assert len(state.accepted) == 3
    assert state.credits_used == 3
