"""Three independent Contacts features: filtered export, facets and marked-only."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.contact_export import (
    ContactExportError,
    MAX_EXPORT_ROWS,
    contact_list_csv,
)


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token="t" * 40,
        allowed_hosts=("testserver",),
    )


def _rows(response):
    assert response.status_code == 200, response.text
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_filters_facets_marked_only_and_export_are_authenticated(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        created = client.post(
            "/api/v1/campaigns",
            headers={"Authorization": "Bearer " + "t" * 40},
            json={"name": "Customer intake"},
        )
        assert created.status_code == 201, created.text
        campaign = created.json()["id"]
        base = f"/api/v1/campaigns/{campaign}/contacts"
        contents = (
            "Full Name,Email,Company,Category,Public Hook,Hook Source\n"
            "Sample One,one@example.com,One,CBAM,Company published evidence,https://example.com/one\n"
            "Sample Two,two@example.com,Two,ESG,Company announced verification,https://example.com/two\n"
            "Sample Three,three@example.com,Three,CBAM,Company launched a public plan,https://example.com/three\n"
        ).encode()
        headers = {"Authorization": "Bearer " + "t" * 40}
        assert client.get(base).status_code == 401
        assert client.get(base + "/facets").status_code == 401
        assert client.get(base + "/download").status_code == 401

        uploaded = client.post(
            base + "/import", headers=headers,
            files={"file": ("people.csv", contents, "text/csv")},
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["added"] == 3
        response = client.get(base, headers=headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 3

        facets = client.get(base + "/facets", headers=headers)
        assert facets.status_code == 200
        assert set(facets.json()["categories"]) == {item["category"] for item in items}
        assert set(facets.json()["variants"]) == {item["variant_id"] for item in items}

        marked = items[0]
        changed = client.patch(
            f"{base}/{marked['id']}", headers=headers, json={"checkbox": True},
        )
        assert changed.status_code == 200, changed.text

        selected = client.get(base, headers=headers, params={"selected_only": True})
        assert selected.status_code == 200
        assert selected.json()["total"] == 1
        assert selected.json()["items"][0]["id"] == marked["id"]

        filtered = client.get(
            base,
            headers=headers,
            params={"category": marked["category"], "variant_id": marked["variant_id"], "selected_only": True},
        )
        assert filtered.json()["total"] == 1

        exported = client.get(base + "/download", headers=headers, params={"selected_only": True})
        assert exported.status_code == 200, exported.text
        assert exported.headers["cache-control"] == "no-store"
        assert "attachment" in exported.headers["content-disposition"]
        exported_rows = _rows(exported)
        assert len(exported_rows) == 1
        assert exported_rows[0]["Full Name"] == marked["full_name"]
        assert exported_rows[0]["Selected"] == "Yes"
        assert "notes" not in exported_rows[0]
        assert "messages" not in exported_rows[0]


def test_download_covers_503_rows_and_never_executes_spreadsheet_formulas():
    class PagedStore:
        def __init__(self):
            self.rows = [
                {
                    "id": str(i),
                    "full_name": ("=HYPERLINK(\"https://example.org\",\"click\")" if i == 0 else f"Person {i:03d}"),
                    "email": f"person{i}@example.com",
                    "company": "Example", "category": "CBAM", "variant_id": "A",
                    "checkbox": i % 2 == 0, "status": "new", "sent_count": 1,
                    "notes": "CONFIDENTIAL INTERNAL NOTES",
                }
                for i in range(503)
            ]
            self.calls = []
        def list_campaign_contacts(self, campaign_id, **kwargs):
            self.calls.append(kwargs)
            all_rows = self.rows
            return all_rows[kwargs["offset"]:kwargs["offset"] + kwargs["limit"]], len(all_rows)
    store = PagedStore()
    result = contact_list_csv(store, "campaign-1", search="public", selected_only=True)
    rows = list(csv.DictReader(io.StringIO(result.decode("utf-8-sig"))))
    assert len(rows) == 503
    assert store.calls[0]["limit"] == 500
    assert store.calls[1]["offset"] == 500
    assert all(call["search"] == "public" and call["selected_only"] for call in store.calls)
    assert rows[0]["Full Name"].startswith("'=HYPERLINK")
    assert rows[502]["Full Name"] == "Person 502"
    assert "CONFIDENTIAL INTERNAL NOTES" not in result.decode("utf-8-sig")


def test_export_refuses_incomplete_or_excessively_large_files():
    class TooLarge:
        def list_campaign_contacts(self, *_args, **_kwargs):
            return [], MAX_EXPORT_ROWS + 1
    with pytest.raises(ContactExportError, match="narrow the filters"):
        contact_list_csv(TooLarge(), "c1")

    class Vanishing:
        def list_campaign_contacts(self, *_args, **kwargs):
            if kwargs["offset"] == 0:
                return [{"id": "a", "full_name": "A"}], 2
            return [], 2
    with pytest.raises(ContactExportError, match="changed while exporting"):
        contact_list_csv(Vanishing(), "c1")
