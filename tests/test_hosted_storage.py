"""S-06.03.02: keys, settings and logins live in the hosted database.

On Render's free plan the data folder is wiped on every deploy, restart and
spin-down. With `OFFSETX_DATABASE_URL` and `OFFSETX_SECRETS_KEY` set once, what
a person types into the app — a provider key, limits, a trust change and its
reason, a colleague's login — and what the app counts and records about it must
outlive that folder, on any PostgreSQL host (DD-70).

Every test runs with the "database" as a SQLite file kept outside the data
folder, and again against a real PostgreSQL when `OFF_CRM_TEST_POSTGRES_URL` is
set — each in a schema of its own, dropped afterwards:

    OFF_CRM_TEST_POSTGRES_URL='postgresql://offcrm:…@127.0.0.1:5432/offcrm_test'
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder import db_cli
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.db import open_database
from offsetx_apollo_builder.db.connection import DatabaseUnavailable
from offsetx_apollo_builder.db.hosted import HostedStorage
from offsetx_apollo_builder.db.schema import ensure_schema, schema_version
from offsetx_apollo_builder.privacy import SubjectIdentity

API = "/api/v1"
TOKEN = "hosted-install-token-" + "z" * 24
SESSION_SECRET = "hosted-session-secret-" + "s" * 32
MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])
needs_postgres = pytest.mark.skipif(
    not POSTGRES_URL, reason="set OFF_CRM_TEST_POSTGRES_URL to a postgresql:// URL to run these"
)

#: What the stores of phase 1 leave in the data folder when they are not hosted.
ON_DISK_WHEN_LOCAL = (
    "ai_workspaces.json", "ai_provider_keys.enc", ".ai_master.key", "ai_quota.json",
    ".ai_workspace_write_lock.sqlite3", "workspace_auth.db", "ai_egress.db",
)


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
def hosted_url(request, tmp_path):
    if request.param == "sqlite":
        yield str(tmp_path / "database-elsewhere" / "offcrm.sqlite3")
        return
    with _postgres_schema() as url:
        yield url


@pytest.fixture
def postgres_url():
    if not POSTGRES_URL:
        pytest.skip("set OFF_CRM_TEST_POSTGRES_URL to a postgresql:// URL to run these")
    with _postgres_schema() as url:
        yield url


def _settings(data: Path, secrets_key: str = "") -> AppSettings:
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
    app = create_app(_settings(data, secrets_key))
    with TestClient(app, headers={"X-Offsetx-Token": TOKEN}) as client:
        yield app, client


def _left_on_disk(data: Path) -> list[str]:
    return sorted(
        path.name for path in data.rglob("*")
        if path.is_file() and path.name.startswith(ON_DISK_WHEN_LOCAL)
    )


def _connect(client, api_key: str = "nvapi-outlives-the-disk"):
    connected = client.post(f"{API}/ai/providers/nvidia/connect", json={
        "api_key": api_key, "model_ids": [MODEL], "requests_per_day": 200, "max_spend_usd_per_day": 5,
    })
    assert connected.status_code == 200, connected.text


def _new_key() -> str:
    return Fernet.generate_key().decode()


# ── what moves, survives ─────────────────────────────────────────────────────

def test_keys_settings_trust_counters_logins_and_the_log_outlive_the_disk(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    key = _new_key()
    first = tmp_path / "first"
    with _running(first, key) as (app, client):
        _connect(client)
        raised = client.post(f"{API}/ai/providers/deepseek/trust", json={
            "tier": "B", "reason": "Our signed terms with DeepSeek"})
        assert raised.status_code == 200, raised.text
        made = client.post(f"{API}/workspaces", json={
            "username": "colleague", "workspace_id": "beta", "password": "beta-password-1"})
        assert made.status_code == 201, made.text
        app.state.ai_quota.record("nvidia", spend_usd=0.25)
        app.state.ai_egress_log.record(provider_id="nvidia", status="ok", task_type="survival-check")
        assert _left_on_disk(first) == []
    shutil.rmtree(first)  # the disk is gone, as on a free-plan deploy

    second = tmp_path / "second"
    with _running(second, key) as (app, client):
        rows = {row["id"]: row for row in client.get(f"{API}/ai/providers").json()["providers"]}
        nvidia, deepseek = rows["nvidia"], rows["deepseek"]
        assert (nvidia["connected"], nvidia["has_key"]) == (True, True)
        assert (nvidia["requests_per_day"], nvidia["max_spend_usd_per_day"]) == (200, 5)
        assert app.state.ai_workspaces.key_for("local", "nvidia") == "nvapi-outlives-the-disk"
        assert deepseek["effective_tier"] == "B"
        assert deepseek["override"]["trust_reason"] == "Our signed terms with DeepSeek"
        assert nvidia["usage"]["day_spend_usd"] == 0.25
        logged = client.get(f"{API}/ai/egress-log").json()["items"]
        assert [item["task_type"] for item in logged] == ["survival-check"]
        login = client.post(f"{API}/auth/login", json={"username": "colleague", "password": "beta-password-1"})
        assert login.status_code == 200, login.text
        assert _left_on_disk(second) == []


def test_the_database_holds_each_key_only_as_ciphertext_its_key_opens(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    key = _new_key()
    with _running(tmp_path / "data", key) as (_, client):
        _connect(client, "nvapi-only-ever-ciphertext")
    database = open_database(hosted_url)
    try:
        documents = {row["name"]: row["body"] for row in database.execute(
            "SELECT name, body FROM offcrm_documents").fetchall()}
    finally:
        database.close()
    everything = json.dumps(documents)
    assert "nvapi-only-ever-ciphertext" not in everything
    assert key not in everything, "the key that opens the keys is never stored beside them"
    opened = json.loads(Fernet(key.encode()).decrypt(documents["ai_provider_keys"].encode()))
    assert opened == {"local::nvidia": "nvapi-only-ever-ciphertext"}


# ── what is refused, and says what to do ──────────────────────────────────────

def test_a_database_without_a_secrets_key_is_refused_with_the_next_step(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with pytest.raises(ValueError) as refused:
        create_app(_settings(tmp_path / "data"))
    assert "OFFSETX_SECRETS_KEY" in str(refused.value)
    assert "offsetx-db new-secrets-key" in str(refused.value)


def test_a_secrets_key_without_a_database_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="OFFSETX_DATABASE_URL"):
        create_app(_settings(tmp_path / "data", _new_key()))


def test_a_secrets_key_that_is_not_a_key_is_refused_without_repeating_it(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with pytest.raises(ValueError) as refused:
        create_app(_settings(tmp_path / "data", "my-memorable-password"))
    assert "is not a key" in str(refused.value)
    assert "offsetx-db new-secrets-key" in str(refused.value)
    assert "my-memorable-password" not in str(refused.value)


@pytest.mark.parametrize("keys_stored", [True, False], ids=["with-keys", "before-any-key"])
def test_a_different_key_on_the_same_database_is_refused_at_start(hosted_url, tmp_path, monkeypatch, keys_stored):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "first", _new_key()) as (_, client):
        if keys_stored:
            _connect(client)
    with pytest.raises(ValueError) as refused:
        create_app(_settings(tmp_path / "second", _new_key()))
    assert "does not open" in str(refused.value)
    assert "offsetx-db forget-provider-keys" in str(refused.value)


# ── what the hosted database must withstand ───────────────────────────────────

def test_two_writers_at_once_lose_neither_change(hosted_url, tmp_path):
    key = _new_key()
    hosted = [HostedStorage(hosted_url, key) for _ in range(2)]  # two processes' connections
    stores = [
        WorkspaceAISettingsStore(tmp_path / f"disk-{index}", ProviderRegistry(), hosted=storage)
        for index, storage in enumerate(hosted)
    ]
    start = threading.Barrier(2)
    failures: list[BaseException] = []

    def write(index: int) -> None:
        try:
            start.wait()
            for turn in range(15):
                stores[index].save(f"workspace-{index}", {"positioning_line": f"turn {turn}"})
        except BaseException as exc:  # noqa: BLE001 - reported below
            failures.append(exc)

    threads = [threading.Thread(target=write, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    try:
        assert failures == []
        assert [stores[0].raw(f"workspace-{index}")["positioning_line"] for index in range(2)] == ["turn 14"] * 2
    finally:
        for storage in hosted:
            storage.close()


def test_a_schema_step_runs_once_however_often_the_store_opens(hosted_url):
    ran: list[int] = []

    def create_probe(database) -> None:
        ran.append(1)
        database.execute("CREATE TABLE probe_rows (id TEXT PRIMARY KEY)")

    for _ in range(3):
        database = open_database(hosted_url)
        try:
            ensure_schema(database, "probe", (create_probe,))
        finally:
            database.close()
    database = open_database(hosted_url)
    try:
        assert (ran, schema_version(database, "probe")) == ([1], 1)
    finally:
        database.close()


@needs_postgres
def test_a_connection_the_server_dropped_is_reopened(postgres_url):
    database = open_database(postgres_url)
    try:
        database.idle_check_seconds = 0
        pid = database.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        killer = open_database(postgres_url)
        try:
            killer.execute("SELECT pg_terminate_backend(?)", [pid])
        finally:
            killer.close()
        assert database.execute("SELECT 1 AS one").fetchone()["one"] == 1
    finally:
        database.close()


@needs_postgres
def test_a_statement_that_failed_is_not_sent_again(postgres_url):
    database = open_database(postgres_url)
    try:
        database.execute("CREATE TABLE sent_once (id TEXT PRIMARY KEY)")
        database.idle_check_seconds = 3600  # no check first: the failure lands on the statement
        pid = database.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        killer = open_database(postgres_url)
        try:
            killer.execute("SELECT pg_terminate_backend(?)", [pid])
            with pytest.raises(DatabaseUnavailable):
                database.execute("INSERT INTO sent_once VALUES ('a')")
            assert killer.execute("SELECT count(*) AS n FROM sent_once").fetchone()["n"] == 0
        finally:
            killer.close()
        # Whether it ran is unknown to the caller, so it is theirs to decide;
        # the connection itself is reopened for whatever comes next.
        assert database.execute("SELECT count(*) AS n FROM sent_once").fetchone()["n"] == 0
    finally:
        database.close()


def test_readiness_checks_the_hosted_database(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        assert client.get("/health/ready").status_code == 200

        def unreachable(*_args, **_kwargs):
            raise ConnectionError("the database host did not answer")

        monkeypatch.setattr(app.state.hosted_storage, "probe", unreachable)
        answer = client.get("/health/ready")
        assert answer.status_code == 503
        assert "hosted_storage:ConnectionError" in answer.json()["detail"]["components"]


def test_a_privacy_request_reaches_a_hosted_login(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        made = client.post(f"{API}/workspaces", json={
            "username": "alice@example.com", "workspace_id": "local", "password": "alice-password-123"})
        assert made.status_code == 201, made.text
        subject = SubjectIdentity.from_mapping({"emails": ["alice@example.com"]})
        found = next(item for item in app.state.privacy.access(subject)["stores"]
                     if item["store"] == "workspace_accounts")
        assert found["count"] == 1
        preview = app.state.privacy.preview(subject)
        from offsetx_apollo_builder.privacy import DELETE_CONFIRMATION
        receipt = app.state.privacy.delete(preview["request_id"], subject, confirmation=DELETE_CONFIRMATION)
        assert receipt["complete"] is True
        assert client.post(f"{API}/auth/login", json={
            "username": "alice@example.com", "password": "alice-password-123"}).status_code in (401, 404)


# ── the operator's two commands ───────────────────────────────────────────────

def test_new_secrets_key_prints_a_key_the_app_accepts(capsys):
    assert db_cli.main(["new-secrets-key"]) == 0
    printed = capsys.readouterr().out
    assert "OFFSETX_SECRETS_KEY" in printed
    key = next(word for word in printed.split() if len(word) == 44 and word.endswith("="))
    Fernet(key.encode())


def test_a_lost_key_is_given_up_only_on_purpose(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "first", _new_key()) as (_, client):
        _connect(client)
    replacement = _new_key()
    assert db_cli.main(["forget-provider-keys"]) == 2
    with pytest.raises(ValueError, match="does not open"):
        create_app(_settings(tmp_path / "second", replacement))
    assert db_cli.main(["forget-provider-keys", "--yes"]) == 0
    with _running(tmp_path / "third", replacement) as (_, client):
        nvidia = next(row for row in client.get(f"{API}/ai/providers").json()["providers"] if row["id"] == "nvidia")
        # The connection and its limits stay; only the key must be pasted again.
        assert (nvidia["connected"], nvidia["has_key"], nvidia["requests_per_day"]) == (True, False, 200)


def test_the_eval_tool_reads_the_same_hosted_keys_as_the_app(hosted_url, tmp_path, monkeypatch):
    from offsetx_apollo_builder.ai import eval_cli

    key = _new_key()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "app", key) as (_, client):
        _connect(client, "nvapi-for-the-eval-tool")
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    _, workspaces, _, _ = eval_cli._build(tmp_path / "tool")
    assert workspaces.key_for("local", "nvidia") == "nvapi-for-the-eval-tool"
    assert _left_on_disk(tmp_path / "tool") == []


def test_a_database_that_stops_answering_gets_a_sentence_not_a_bare_500(hosted_url, tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        storage = app.state.hosted_storage
        storage.close()
        storage.target = "postgresql://nobody:not-the-password@127.0.0.1:1/gone"
        answer = client.get(f"{API}/ai/providers")
        assert answer.status_code == 503, answer.text
        detail = answer.json()["detail"]
        assert "cannot reach its database" in detail
        # What failed and where goes to the server's log, not to every login.
        assert "127.0.0.1" not in detail and "not-the-password" not in detail
