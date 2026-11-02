"""F-06.22 duplicate-contact review: safe, bounded, read-only acceptance tests."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.crm_operations import CRMOperations
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.sales import SalesTracker


def _duplicates(tmp_path: Path):
    engine = OutreachEngine(tmp_path / "duplicates.db")
    def contact(name, email):
        return engine.store.upsert_contact(ContactInput(
            full_name=name, email=email, company="Test Ltd", title="Buyer",
        ))

    first = contact("Alice One", "alice@example.com")
    second = contact("Alice Two", "other@example.com")
    third = contact("Bob One", "bob@example.com")
    fourth = contact("Bob Two", "yet-another@example.com")
    orphan = contact("Nobody", "unique@example.com")
    # Simulate existing/imported legacy variants that bypass normal upsert dedupe.
    engine.store.connection.execute(
        "UPDATE contacts SET email = ? WHERE id = ?",
        (" ALICE@example.com ", second),
    )
    engine.store.connection.execute(
        "UPDATE contacts SET email = ? WHERE id = ?",
        (" BOB@example.com ", fourth),
    )
    return engine, (first, second, third, fourth, orphan)


def test_duplicate_groups_are_stable_bounded_and_never_merge(tmp_path):
    engine, ids = _duplicates(tmp_path)
    try:
        service = CRMOperations(engine.store, SalesTracker(engine.store))
        before = engine.store._row("SELECT COUNT(*) AS n FROM contacts")["n"]
        result = service.contact_duplicates()
        assert result["total"] == 2
        assert [x["normalized_email"] for x in result["items"]] == [
            "alice@example.com", "bob@example.com",
        ]
        assert [x["contact_count"] for x in result["items"]] == [2, 2]
        assert [x["full_name"] for x in result["items"][0]["contacts"]] == [
            "Alice One", "Alice Two",
        ]
        assert {x["id"] for x in result["items"][0]["contacts"]} == set(ids[:2])
        assert result["items"][0]["has_more"] is False
        assert result["items"][0]["contact_count"] == len(result["items"][0]["contacts"])
        assert "notes" not in result["items"][0]["contacts"][0]
        assert "source_json" not in result["items"][0]["contacts"][0]
        assert service.contact_duplicates(limit=1, offset=1)["total"] == 2
        assert service.contact_duplicates(offset=2)["items"] == []
        assert engine.store._row("SELECT COUNT(*) AS n FROM contacts")["n"] == before
        assert "review" in result["identity_note"].lower()
    finally:
        engine.close()


def test_duplicate_search_is_literal_and_validation_rejects_bad_pages(tmp_path):
    engine, _ = _duplicates(tmp_path)
    try:
        service = CRMOperations(engine.store, SalesTracker(engine.store))
        assert service.contact_duplicates(search="ALICE")["total"] == 1
        for text in ("%", "_", "%' OR 1=1 --"):
            assert service.contact_duplicates(search=text)["total"] == 0
        for kwargs in ({"limit": 0}, {"limit": 26}, {"offset": -1},
                       {"search": "x" * 101}):
            with pytest.raises(ValueError):
                service.contact_duplicates(**kwargs)
    finally:
        engine.close()


def test_duplicate_group_previews_are_capped_even_when_many_match(tmp_path):
    engine, _ = _duplicates(tmp_path)
    try:
        for i in range(4):
            item = engine.store.upsert_contact(ContactInput(
                full_name=f"Another {i}", email=f"temp-{i}@example.com",
            ))
            # Distinct whitespace variants preserve current unique lower(email)
            # index, but all belong in the same trim-normalised review group.
            engine.store.connection.execute(
                "UPDATE contacts SET email = ? WHERE id = ?",
                (" " * (i + 1) + "alice@example.com", item),
            )
        group = CRMOperations(engine.store, SalesTracker(engine.store)).contact_duplicates(
            search="alice",
        )["items"][0]
        assert group["contact_count"] == 6
        assert len(group["contacts"]) == 3
        assert group["has_more"] is True
    finally:
        engine.close()


def test_duplicate_api_requires_auth_and_has_strict_input_bounds(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "api.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "none",
        api_token="d" * 40, allowed_hosts=("testserver",),
    )
    url = "/api/v1/crm/duplicates"
    auth = {"Authorization": "Bearer " + "d" * 40}
    with TestClient(create_app(settings)) as client:
        assert client.get(url).status_code == 401
        response = client.get(url, headers=auth)
        assert response.status_code == 200, response.text
        assert response.json()["items"] == []
        for params in ({"limit": 26}, {"limit": 0}, {"offset": -1},
                       {"search": "x" * 101}):
            assert client.get(url, headers=auth, params=params).status_code == 422
        assert client.get(url, headers=auth,
                          params={"search": "%' OR 1=1 --"}).status_code == 200


def test_imported_tabs_and_newlines_are_email_outer_whitespace(tmp_path):
    """An old imported email with CR/LF/tab is the same review key."""
    engine, (first, second, _, _, _) = _duplicates(tmp_path)
    try:
        another = engine.store.upsert_contact(ContactInput(
            full_name="Alice Three", email="temporary@example.com",
        ))
        engine.store.connection.execute(
            "UPDATE contacts SET email = ? WHERE id = ?",
            ("\t ALICE@example.com \r\n", another),
        )
        service = CRMOperations(engine.store, SalesTracker(engine.store))
        result = service.contact_duplicates(search="Alice")
        assert result["total"] == 1
        group = result["items"][0]
        assert group["normalized_email"] == "alice@example.com"
        assert group["contact_count"] == 3
        assert {v["id"] for v in group["contacts"]} == {first, second, another}
    finally:
        engine.close()


def test_unreasonably_large_pagination_is_rejected_before_database(tmp_path):
    """Prevent integer overflow and expensive unbounded OFFSET requests."""
    engine, _ = _duplicates(tmp_path)
    try:
        service = CRMOperations(engine.store, SalesTracker(engine.store))
        with pytest.raises(ValueError):
            service.contact_duplicates(offset=1_000_001)
    finally:
        engine.close()

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "bounds.db",
        data_dir=tmp_path / "bounds-data",
        export_dir=tmp_path / "bounds-export",
        frontend_dist=tmp_path / "none",
        api_token="x" * 40, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        endpoint = "/api/v1/crm/duplicates"
        assert client.get(endpoint, params={"offset": "999999999999999999999999"}).status_code == 401
        headers = {"Authorization": "Bearer " + "x" * 40}
        for bad in ("1000001", "999999999999999999999999"):
            response = client.get(endpoint, params={"offset": bad}, headers=headers)
            assert response.status_code == 422, response.text
