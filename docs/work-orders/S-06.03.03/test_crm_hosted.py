"""S-06.03.03: the CRM lives in the hosted database.

Phase 1 (`S-06.03.02`) moved keys, settings and logins into the database
`OFFSETX_DATABASE_URL` names. The CRM — campaigns, contacts, drafts, sends,
replies, delivery jobs — stayed in `OFFSETX_OUTREACH_DB`, a file on a disk the
free plan wipes. These tests hold the CRM to the same promise: what a person
typed survives the disk, on SQLite and PostgreSQL alike, and an existing SQLite
CRM can be copied across and back with every table's count reconciled.

The PostgreSQL half runs when `OFF_CRM_TEST_POSTGRES_URL` is set, each test in
a schema of its own, dropped afterwards:

    OFF_CRM_TEST_POSTGRES_URL='postgresql://postgres@127.0.0.1:55432/postgres'
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore

API = "/api/v1"
TOKEN = "hosted-crm-token-" + "z" * 24
SESSION_SECRET = "hosted-crm-session-secret-" + "s" * 32
POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])


def _in_schema(url: str, schema: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}options=-csearch_path%3D{schema}"


@contextmanager
def _postgres_schema():
    import psycopg

    schema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    try:
        yield _in_schema(POSTGRES_URL, schema)
    finally:
        with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture(params=BACKENDS)
def crm_target(request, tmp_path):
    """Where the CRM lives: a SQLite file, or a PostgreSQL schema of its own."""
    if request.param == "sqlite":
        yield str(tmp_path / "database-elsewhere" / "crm.sqlite3")
        return
    with _postgres_schema() as url:
        yield url


@pytest.fixture
def postgres_target():
    if not POSTGRES_URL:
        pytest.skip("set OFF_CRM_TEST_POSTGRES_URL to a postgresql:// URL to run these")
    with _postgres_schema() as url:
        yield url


def _open(target: object) -> OutreachStore:
    store = OutreachStore(target)
    store.initialize()
    # Asserted on every open: the store used to take a PostgreSQL URL as a file
    # name, so a test "on PostgreSQL" passed against a SQLite file in the
    # working folder (D-217).
    assert store.backend == ("postgres" if str(target).startswith("postgresql") else "sqlite")
    return store


def _seed(store: OutreachStore) -> dict[str, str]:
    contact = store.upsert_contact(
        ContactInput(full_name="Asha Rao", email="asha@acme.example", company="Acme Corp")
    )
    campaign = store.create_campaign(name="Autumn launch", daily_send_limit=20)
    return {"contact": contact, "campaign": campaign}


def _counts(target: object) -> dict[str, int]:
    with _open(target) as store:
        return store.table_counts()


# ── the store, on either backend ─────────────────────────────────────────────

def test_a_contact_and_a_campaign_outlive_the_store_that_wrote_them(crm_target):
    with _open(crm_target) as store:
        ids = _seed(store)
    with _open(crm_target) as store:
        assert store.get_contact(ids["contact"])["company"] == "Acme Corp"
        assert store.get_campaign(ids["campaign"])["name"] == "Autumn launch"


def test_opening_twice_changes_nothing_the_second_time(crm_target):
    with _open(crm_target) as store:
        _seed(store)
        before = store.table_counts()
    with _open(crm_target) as store:
        assert store.table_counts() == before


def test_search_ignores_case_on_every_backend(crm_target):
    # SQLite's LIKE ignores ASCII case and PostgreSQL's does not, so the same
    # query found "Acme" on one backend and silently nothing on the other.
    with _open(crm_target) as store:
        ids = _seed(store)
        store.add_contact_to_campaign(ids["campaign"], ids["contact"])
        campaigns, total = store.list_campaigns(search="autumn")
        assert (total, [row["name"] for row in campaigns]) == (1, ["Autumn launch"])
        members, total = store.list_campaign_contacts(ids["campaign"], search="ACME")
        assert total == 1 and members[0]["full_name"] == "Asha Rao"


def test_a_duplicate_is_refused_as_the_backends_integrity_error(crm_target):
    with _open(crm_target) as store:
        _seed(store)
        with pytest.raises(store.integrity_error):
            store.connection.execute(
                "INSERT INTO contacts(id, identity_key, full_name, created_at, updated_at)"
                " SELECT ?, identity_key, full_name, created_at, updated_at FROM contacts LIMIT 1",
                (str(uuid.uuid4()),),
            )


def test_a_failed_transaction_leaves_nothing_behind(crm_target):
    with _open(crm_target) as store:
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.create_campaign(name="Never kept", daily_send_limit=5)
                raise RuntimeError("the request failed half way")
        assert store.list_campaigns(search="never kept")[1] == 0


def test_no_postgres_column_is_narrower_than_its_sqlite_value(postgres_target):
    # SQLite's REAL is 8 bytes and its INTEGER up to 8; PostgreSQL's REAL is 4
    # bytes (about 7 digits) and its INTEGER 4 (about 2.1 billion).
    import psycopg

    _open(postgres_target).close()
    schema = postgres_target.rsplit("%3D", 1)[1]
    with psycopg.connect(POSTGRES_URL) as admin:
        types = admin.execute(
            "SELECT data_type, count(*) FROM information_schema.columns"
            " WHERE table_schema = %s GROUP BY data_type",
            (schema,),
        ).fetchall()
    found = dict(types)
    assert sum(found.values()) > 300, found  # the schema really is there
    assert not {"real", "integer", "smallint"} & set(found), found


def test_a_postgres_url_never_becomes_a_file(postgres_target, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _open(postgres_target).close()
    assert list(tmp_path.iterdir()) == []


# ── copying an existing CRM across, and back ─────────────────────────────────

def test_the_copy_reconciles_every_table_and_so_does_the_inverse(tmp_path, postgres_target):
    from offsetx_apollo_builder.outreach.store_copy import copy_crm

    source = tmp_path / "existing.db"
    with _open(source) as store:
        ids = _seed(store)
        store.add_contact_to_campaign(ids["campaign"], ids["contact"])
    original = _counts(source)
    assert sum(original.values()) >= 3

    forward = copy_crm(source, postgres_target)
    assert forward.ok, forward.describe()
    assert _counts(postgres_target) == original

    returned = tmp_path / "returned.db"
    inverse = copy_crm(postgres_target, returned)
    assert inverse.ok, inverse.describe()
    assert _counts(returned) == original
    with _open(returned) as store:
        assert store.get_contact(ids["contact"])["company"] == "Acme Corp"


def test_the_copy_refuses_a_destination_that_already_holds_a_crm(tmp_path, postgres_target):
    from offsetx_apollo_builder.outreach.store_copy import CrmCopyError, copy_crm

    source = tmp_path / "existing.db"
    with _open(source) as store:
        _seed(store)
    with _open(postgres_target) as store:
        store.create_campaign(name="Already here", daily_send_limit=5)
    with pytest.raises(CrmCopyError, match="already holds"):
        copy_crm(source, postgres_target)
    assert [row["name"] for row in _open(postgres_target).list_campaigns()[0]] == ["Already here"]


def test_the_copy_leaves_its_source_untouched(tmp_path, postgres_target):
    from offsetx_apollo_builder.outreach.store_copy import copy_crm

    source = tmp_path / "existing.db"
    with _open(source) as store:
        _seed(store)
    before = source.read_bytes()
    assert copy_crm(source, postgres_target).ok
    with sqlite3.connect(source) as reader:
        reader.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert source.read_bytes() == before


# ── the app: the CRM follows OFFSETX_DATABASE_URL ────────────────────────────

def _settings(data: Path, secrets_key: str) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=data / "offsetx_outreach.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=data.parent / "no-frontend",
        host="127.0.0.1",
        api_token=TOKEN,
        session_secret=SESSION_SECRET,
        allowed_hosts=("testserver",),
        secrets_key=secrets_key,
    )


@contextmanager
def _running(data: Path, secrets_key: str):
    with TestClient(create_app(_settings(data, secrets_key)), headers={"X-Offsetx-Token": TOKEN}) as client:
        yield client


def test_a_campaign_made_in_the_app_outlives_the_disk(crm_target, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", crm_target)
    key = Fernet.generate_key().decode()
    first = tmp_path / "first"
    with _running(first, key) as client:
        made = client.post(f"{API}/campaigns", json={"name": "Survives the deploy"})
        assert made.status_code == 201, made.text
        assert not (first / "offsetx_outreach.db").exists()
    shutil.rmtree(first)  # the disk is gone, as on a free-plan deploy

    with _running(tmp_path / "second", key) as client:
        listed = client.get(f"{API}/campaigns", params={"search": "survives"}).json()
        assert [item["name"] for item in listed["items"]] == ["Survives the deploy"]


def test_a_local_crm_left_behind_stops_the_start_and_names_the_import(crm_target, tmp_path, monkeypatch):
    data = tmp_path / "own-disk"
    with _open(data / "offsetx_outreach.db") as store:
        _seed(store)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", crm_target)
    with pytest.raises(Exception, match="offsetx-db import-crm"):
        create_app(_settings(data, Fernet.generate_key().decode()))


def test_with_no_database_url_the_crm_stays_in_its_file(tmp_path, monkeypatch):
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    data = tmp_path / "local"
    with TestClient(create_app(_settings(data, "")), headers={"X-Offsetx-Token": TOKEN}) as client:
        assert client.post(f"{API}/campaigns", json={"name": "Local only"}).status_code == 201
    with sqlite3.connect(data / "offsetx_outreach.db") as reader:
        assert reader.execute("SELECT name FROM campaigns").fetchall() == [("Local only",)]
