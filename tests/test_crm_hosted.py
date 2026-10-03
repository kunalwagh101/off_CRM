"""S-06.03.03: the CRM lives in the hosted database.

Phase 1 (`S-06.03.02`) moved keys, settings and logins into the database
`OFFSETX_DATABASE_URL` names. The CRM — campaigns, contacts, drafts, sends,
replies, delivery jobs — stayed in `OFFSETX_OUTREACH_DB`, a file on a disk the
free plan wipes. These tests hold the CRM to the same promise: what a person
typed survives the disk, on SQLite and PostgreSQL alike.

The tests arrive with the task that makes them pass; the rest wait beside the
work order, `docs/work-orders/S-06.03.03/test_crm_hosted.py`.

The PostgreSQL half runs when `OFF_CRM_TEST_POSTGRES_URL` is set, each test in
a schema of its own, dropped afterwards:

    OFF_CRM_TEST_POSTGRES_URL='postgresql://postgres@127.0.0.1:55432/postgres'
"""
from __future__ import annotations

import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

from offsetx_apollo_builder.db import DatabaseError
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.schema import CRM_TABLES
from offsetx_apollo_builder.outreach.store import OutreachStore

POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])
CRM_WRITE_LOCK = 7_103_206_302


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
    # With OFF_CRM_TEST_CRM_ON_POSTGRES=1 the harness opens every path on
    # PostgreSQL too (`tests/conftest.py`).
    on_postgres = str(target).startswith("postgresql") or os.getenv("OFF_CRM_TEST_CRM_ON_POSTGRES") == "1"
    assert store.backend == ("postgres" if on_postgres else "sqlite")
    return store


def _seed(store: OutreachStore) -> dict[str, str]:
    contact = store.upsert_contact(
        ContactInput(full_name="Asha Rao", email="asha@acme.example", company="Acme Corp")
    )
    campaign = store.create_campaign(name="Autumn launch", daily_send_limit=20)
    return {"contact": contact, "campaign": campaign}


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


def test_every_crm_table_is_counted(crm_target):
    # The copy tool reconciles these counts, so a table missing from them is a
    # table a copy could drop without anything noticing.
    with _open(crm_target) as store:
        if store.backend == "sqlite":
            made = {
                row["name"] for row in store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                    " AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\'"
                    " AND name NOT LIKE 'expert\\_chunks\\_fts%' ESCAPE '\\'"
                )
            }
        else:
            made = {
                row["table_name"] for row in store.connection.execute(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
                    " AND table_name <> 'offcrm_schema'"
                )
            }
        assert set(store.table_counts()) == made == set(CRM_TABLES)
        assert len(CRM_TABLES) == 31


def test_a_duplicate_is_refused_as_the_backends_integrity_error(crm_target):
    with _open(crm_target) as store:
        _seed(store)
        with pytest.raises(store.integrity_error):
            store.connection.execute(
                "INSERT INTO contacts(id, identity_key, full_name, created_at, updated_at)"
                " SELECT ?, identity_key, full_name, created_at, updated_at FROM contacts LIMIT 1",
                (str(uuid.uuid4()),),
            )
        assert store.table_counts()["contacts"] == 1


def test_a_failed_transaction_leaves_nothing_behind(crm_target):
    # Counted, not searched: search ignores case on SQLite only until task c,
    # so a search here would find nothing on PostgreSQL whether or not the
    # rollback worked.
    with _open(crm_target) as store:
        _seed(store)
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.create_campaign(name="Never kept", daily_send_limit=5)
                raise RuntimeError("the request failed half way")
        assert store.table_counts()["campaigns"] == 1


def test_a_nested_failure_undoes_only_the_inner_work(crm_target):
    with _open(crm_target) as store:
        with store.transaction():
            store.create_campaign(name="Kept", daily_send_limit=5)
            with pytest.raises(RuntimeError):
                with store.transaction():
                    store.create_campaign(name="Undone", daily_send_limit=5)
                    raise RuntimeError("the inner step failed")
        assert [row["name"] for row in store.list_campaigns()[0]] == ["Kept"]


def test_an_immediate_transaction_holds_other_processes_back(postgres_target):
    import psycopg

    with _open(postgres_target) as store, psycopg.connect(POSTGRES_URL, autocommit=True) as other:
        def free() -> bool:
            taken = other.execute("SELECT pg_try_advisory_lock(%s)", (CRM_WRITE_LOCK,)).fetchone()[0]
            if taken:
                other.execute("SELECT pg_advisory_unlock(%s)", (CRM_WRITE_LOCK,))
            return taken

        with store.transaction(immediate=True):
            assert not free()
        assert free()
        with store.transaction():
            assert free()  # an ordinary transaction does not take it


def test_no_postgres_column_is_narrower_than_its_sqlite_value(postgres_target):
    # SQLite's REAL is 8 bytes and its INTEGER up to 8; PostgreSQL's REAL is 4
    # bytes (about 7 digits) and its INTEGER 4 (about 2.1 billion).
    import psycopg

    _open(postgres_target).close()
    schema = postgres_target.rsplit("%3D", 1)[1]
    with psycopg.connect(POSTGRES_URL) as admin:
        types = admin.execute(
            "SELECT data_type, count(*) FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name = ANY(%s) GROUP BY data_type",
            (schema, list(CRM_TABLES)),
        ).fetchall()
    found = dict(types)
    assert sum(found.values()) > 300, found  # the schema really is there
    assert not {"real", "integer", "smallint"} & set(found), found


def test_a_postgres_url_never_becomes_a_file(postgres_target, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _open(postgres_target).close()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("target", [
    "mysql://crm:s3cret-pass@db.example/crm",
    "psql://crm:s3cret-pass@db.example/crm",
    "sqlite:///home/crm/s3cret-pass.db",
])
def test_a_url_of_another_kind_is_refused_and_never_repeated(target, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabaseError) as refused:
        OutreachStore(target)
    assert "s3cret-pass" not in str(refused.value)
    assert "postgresql://" in str(refused.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", [
    "postgresql://crm:s3cret-pass@db.example/crm",
    "mysql://crm:s3cret-pass@db.example/crm",
])
def test_a_url_in_the_crm_file_setting_is_refused_however_it_arrives(value, tmp_path, monkeypatch):
    # The route D-217 was reachable by: `OFFSETX_OUTREACH_DB` becomes a resolved
    # `Path`, which folds "postgresql://" to "postgresql:/" — no "://" left.
    from offsetx_apollo_builder.data_paths import database_path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", value)
    for given in (database_path(tmp_path), Path(value)):
        with pytest.raises(DatabaseError) as refused:
            OutreachStore(given)
        assert "s3cret-pass" not in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_an_ordinary_path_with_a_colon_still_opens(tmp_path):
    with _open(tmp_path / "crm 10:30" / "a:b.db") as store:
        assert store.table_counts()["campaigns"] == 0


# ── task c: one SQL for both backends ────────────────────────────────────────

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


def test_a_repeated_answer_replaces_the_one_saved(crm_target):
    with _open(crm_target) as store:
        store.save_idempotency("campaigns", "key-1", {"id": "first"})
        store.save_idempotency("campaigns", "key-1", {"id": "second"})
        assert store.get_idempotency("campaigns", "key-1") == {"id": "second"}
        assert store.table_counts()["idempotency_records"] == 1


def test_the_same_expert_text_is_kept_once_and_found(crm_target):
    with _open(crm_target) as store:
        text = "Lead with the outcome the buyer already wants, then the proof."
        assert store.add_expert_chunk(document_name="Playbook", content=text) is True
        assert store.add_expert_chunk(document_name="Playbook copy", content=text) is False
        assert store.table_counts()["expert_chunks"] == 1
        assert [row["document_name"] for row in store.search_expert_chunks("buyer outcome")] == ["Playbook"]


# ── task d: the CRM's other modules, and the safety the SQLite guard gave ────
#
# `tests/test_security_audit.py` proves these properties for SQLite's
# `GuardedConnection`, through its own probe table, `sqlite3.IntegrityError`
# and `row[0]`. The same properties, on a CRM table, through the store's own
# error class, for both backends.

def _put(conn, key: str) -> None:
    conn.execute(
        "INSERT INTO idempotency_records (scope, request_key, response_json, created_at)"
        " VALUES ('probe', ?, '{}', '2026-10-03T00:00:00+00:00')",
        (key,),
    )


def _probes(store: OutreachStore) -> list[str]:
    return sorted(
        row["request_key"] for row in store.connection.execute(
            "SELECT request_key FROM idempotency_records WHERE scope = 'probe'"
        ).fetchall()
    )


def _run(threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "a thread never finished — deadlock"


def test_concurrent_transactions_lose_no_writes(crm_target):
    with _open(crm_target) as store:
        barrier, errors = threading.Barrier(4), []

        def write(name: str) -> None:
            try:
                barrier.wait(timeout=10)
                for index in range(40):
                    with store.transaction() as conn:
                        _put(conn, f"{name}-{index}")
            except Exception as exc:  # noqa: BLE001 - the failure is the assertion
                errors.append(f"{name}: {type(exc).__name__}: {exc}")

        _run([threading.Thread(target=write, args=(name,)) for name in "ABCD"])
        assert errors == []
        assert len(_probes(store)) == 160


def test_immediate_transactions_from_threads_are_serialised(crm_target):
    with _open(crm_target) as store:
        barrier, errors = threading.Barrier(3), []

        def claim(name: str) -> None:
            try:
                barrier.wait(timeout=10)
                for index in range(25):
                    with store.transaction(immediate=True) as conn:
                        _put(conn, f"{name}-{index}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {type(exc).__name__}: {exc}")

        _run([threading.Thread(target=claim, args=(name,)) for name in "XYZ"])
        assert errors == []
        assert len(_probes(store)) == 75


def test_a_failing_transaction_rolls_back_and_releases(crm_target):
    with _open(crm_target) as store:
        with pytest.raises(store.integrity_error):
            with store.transaction() as conn:
                _put(conn, "first")
                _put(conn, "first")
        assert _probes(store) == []

        done = threading.Event()

        def after() -> None:
            with store.transaction() as conn:
                _put(conn, "after")
            done.set()

        _run([threading.Thread(target=after)])
        assert done.is_set(), "the failing transaction did not release the lock"
        assert _probes(store) == ["after"]


def test_a_bare_write_survives_another_threads_failed_transaction(crm_target):
    with _open(crm_target) as store:
        rounds, bystanders = 12, 4
        barrier, errors = threading.Barrier(bystanders + 1), []

        def failing() -> None:
            try:
                barrier.wait(timeout=20)
                for index in range(rounds):
                    try:
                        with store.transaction() as conn:
                            _put(conn, f"doomed-{index}")
                            raise RuntimeError("this request failed")
                    except RuntimeError:
                        pass
            except Exception as exc:  # noqa: BLE001
                errors.append(f"holder: {type(exc).__name__}: {exc}")

        def bare(name: str) -> None:
            try:
                barrier.wait(timeout=20)
                for index in range(rounds):
                    _put(store.connection, f"{name}-{index}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {type(exc).__name__}: {exc}")

        _run([threading.Thread(target=failing)]
             + [threading.Thread(target=bare, args=(f"bare{n}",)) for n in range(bystanders)])
        assert errors == []
        kept = _probes(store)
        assert not [key for key in kept if key.startswith("doomed")], "a failed transaction committed"
        assert len(kept) == rounds * bystanders


def test_a_read_never_sees_another_threads_uncommitted_rows(crm_target):
    with _open(crm_target) as store:
        started, may_commit, seen = threading.Event(), threading.Event(), []

        def holder() -> None:
            with store.transaction() as conn:
                _put(conn, "uncommitted")
                started.set()
                may_commit.wait(timeout=10)

        def reader() -> None:
            started.wait(timeout=10)
            may_commit.set()
            seen.append(len(_probes(store)))  # waits for the commit, then counts

        _run([threading.Thread(target=holder), threading.Thread(target=reader)])
        assert seen == [1]


def test_lead_search_ignores_case_on_every_backend(crm_target):
    from offsetx_apollo_builder.outreach.sales import SalesTracker

    with _open(crm_target) as store:
        sales = SalesTracker(store)
        sales.create_lead({"lead_name": "Asha Rao", "company": "Acme Corp", "email": "asha@acme.example"})
        leads, total = sales.list_leads(search="ACME")
        assert total == 1 and leads[0]["lead_name"] == "Asha Rao"


def test_local_backup_is_refused_while_the_crm_is_on_postgres(postgres_target):
    # `outreach/backup.py` archives the CRM's file; on PostgreSQL there is
    # none, and the answer was "CRM database does not exist". Hosted backups
    # are `S-06.03.04`.
    from types import SimpleNamespace

    from fastapi import HTTPException

    from offsetx_apollo_builder.api.production_runtime import _require_local_backup

    with _open(postgres_target) as store:
        local = SimpleNamespace(target="")
        state = SimpleNamespace(
            hosted_storage=None, engine=SimpleNamespace(store=store),
            ai_egress_log=local, video_store=local, gtm_store=local,
        )
        with pytest.raises(HTTPException) as refused:
            _require_local_backup(state)
        assert refused.value.status_code == 409
        assert "PostgreSQL" in refused.value.detail


def test_a_closed_store_stays_closed(crm_target):
    # PostgreSQL's connection reopens itself after the server drops it. It
    # also reopened after the store was closed on purpose, so a reference held
    # past a restore's close went on reading and writing (D-222).
    import sqlite3

    store = _open(crm_target)
    store.close()
    with pytest.raises((sqlite3.ProgrammingError, DatabaseError)):
        store.connection.execute("SELECT 1")
