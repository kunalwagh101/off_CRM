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


# ── the fresh-context review's findings (D-206 to D-215) ──────────────────────

DEAD_DATABASE = "postgresql://nobody:not-the-password@127.0.0.1:1/gone"


def _cut_off(app) -> None:
    """The hosted database stops answering, for every hosted store at once."""
    for store in (app.state.hosted_storage, app.state.workspace_auth):
        store.close()
    app.state.hosted_storage.target = DEAD_DATABASE
    app.state.workspace_auth._target = DEAD_DATABASE


@pytest.mark.parametrize("value", [
    "host=127.0.0.1 port=5432 dbname=offcrm user=offcrm password=the-password",
    '"postgresql://offcrm:the-password@127.0.0.1:5432/offcrm"',
    "offcrm.sqlite3",
    "psql://offcrm:the-password@127.0.0.1:5432/offcrm",
], ids=["libpq-key-value", "quoted-url", "relative-path", "psql-scheme"])
def test_a_database_setting_that_is_not_a_url_is_refused_and_never_becomes_a_file(value, tmp_path, monkeypatch):
    """D-206: such a value used to be a SQLite file in the working directory,
    named after the string — password included — on the disk a deploy wipes."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", value)
    with pytest.raises(ValueError) as refused:
        create_app(_settings(tmp_path / "data", _new_key()))
    assert "postgresql://" in str(refused.value)
    assert "the-password" not in str(refused.value)
    assert sorted(path.name for path in tmp_path.iterdir()) == []


def test_an_answer_already_billed_survives_the_database_going_away(hosted_url, tmp_path, monkeypatch):
    """D-207: the counters were first read after the call, so a database that
    went away meanwhile threw a billed answer away and told the user to retry."""
    from offsetx_apollo_builder.ai import broker as broker_module

    calls: list[str] = []
    holder: dict[str, object] = {}

    class _Model:
        last_usage = None

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            calls.append("billed")
            _cut_off(holder["app"])  # the database goes while the model thinks
            return "the answer the provider produced"

    monkeypatch.setattr(broker_module, "create_provider", lambda config, *, environ: _Model())
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        holder["app"] = app
        connected = client.post(f"{API}/ai/providers/openai/connect", json={
            "api_key": "openai-test-key", "model_ids": ["gpt-4o-mini"]})
        assert connected.status_code == 200, connected.text
        ran = client.post(f"{API}/ai/run", json={"instructions": "Say hello.", "data_class": "public"})
        assert (ran.status_code, len(calls)) == (200, 1), ran.text


def test_nothing_is_billed_when_the_counters_cannot_be_read_first(hosted_url, tmp_path, monkeypatch):
    from offsetx_apollo_builder.ai import broker as broker_module

    calls: list[str] = []

    class _Model:
        last_usage = None

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            calls.append("billed")
            return "never asked"

    monkeypatch.setattr(broker_module, "create_provider", lambda config, *, environ: _Model())
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        assert client.post(f"{API}/ai/providers/openai/connect", json={
            "api_key": "openai-test-key", "model_ids": ["gpt-4o-mini"]}).status_code == 200
        _cut_off(app)
        ran = client.post(f"{API}/ai/run", json={"instructions": "Say hello.", "data_class": "public"})
        assert (ran.status_code, calls) == (503, [])


@needs_postgres
def test_a_connection_asks_the_network_to_notice_a_silent_drop(postgres_url):
    """D-208: with no bound, a check on a flow a load balancer forgot waited
    until TCP gave up — about fifteen minutes — holding the store's lock."""
    database = open_database(postgres_url)
    try:
        parameters = database.raw.info.get_parameters()
        assert parameters.get("tcp_user_timeout") == "15000"
        assert parameters.get("keepalives_idle") == "15"
    finally:
        database.close()
    joiner = "&" if "?" in postgres_url else "?"
    chosen = open_database(f"{postgres_url}{joiner}keepalives_idle=60")
    try:
        assert chosen.raw.info.get_parameters().get("keepalives_idle") == "60", "the URL's own choice wins"
    finally:
        chosen.close()


def test_a_signed_in_browser_gets_the_sentence_during_an_outage(hosted_url, tmp_path, monkeypatch):
    """D-209: the session check runs in the middleware, which the 503 handler
    did not cover — every signed-in request answered a bare 500."""
    from offsetx_apollo_builder.api.auth import SESSION_COOKIE

    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        assert client.post(f"{API}/workspaces", json={
            "username": "colleague", "workspace_id": "beta", "password": "beta-password-1"}).status_code == 201
        signed_in = TestClient(app, raise_server_exceptions=False)
        assert signed_in.post(f"{API}/auth/login", json={
            "username": "colleague", "password": "beta-password-1"}).status_code == 200
        assert signed_in.cookies.get(SESSION_COOKIE)
        _cut_off(app)
        answer = signed_in.get(f"{API}/ai/providers")
        assert answer.status_code == 503, answer.text
        assert "cannot reach its database" in answer.json()["detail"]
        assert signed_in.get("/health/live").status_code == 200, "being alive does not need the database"


def _local_install_with_data(data: Path, monkeypatch) -> None:
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    with _running(data, "") as (app, client):
        _connect(client, "nvapi-on-the-disk")
        assert client.post(f"{API}/ai/providers/deepseek/trust", json={
            "tier": "B", "reason": "Signed terms, recorded on the disk"}).status_code == 200
        assert client.post(f"{API}/workspaces", json={
            "username": "colleague", "workspace_id": "beta", "password": "beta-password-1"}).status_code == 201
        app.state.ai_quota.record("nvidia", spend_usd=0.5)


def test_switching_on_beside_a_folder_that_holds_data_is_refused_with_both_choices(hosted_url, tmp_path, monkeypatch):
    """D-210: the logins, keys and trust on the disk were silently hidden."""
    data = tmp_path / "local_data"
    _local_install_with_data(data, monkeypatch)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with pytest.raises(ValueError) as refused:
        create_app(_settings(data, _new_key()))
    message = str(refused.value)
    for named in ("ai_workspaces.json", "ai_provider_keys.enc", "workspace_auth.db",
                  "offsetx-db import-local --yes", "offsetx-db import-local --skip"):
        assert named in message


def test_import_local_brings_the_folder_into_the_database(hosted_url, tmp_path, monkeypatch):
    data = tmp_path / "local_data"
    _local_install_with_data(data, monkeypatch)
    key = _new_key()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    before = sorted(path.name for path in data.iterdir())
    assert db_cli.main(["import-local", "--data-dir", str(data)]) == 2, "nothing happens without --yes"
    assert db_cli.main(["import-local", "--data-dir", str(data), "--yes"]) == 0
    assert db_cli.main(["import-local", "--data-dir", str(data), "--yes"]) == 2, "never imports over what is there"
    assert sorted(path.name for path in data.iterdir()) == before, "the files are left as they were"
    with _running(data, key) as (app, client):
        rows = {row["id"]: row for row in client.get(f"{API}/ai/providers").json()["providers"]}
        assert app.state.ai_workspaces.key_for("local", "nvidia") == "nvapi-on-the-disk"
        assert rows["deepseek"]["override"]["trust_reason"] == "Signed terms, recorded on the disk"
        assert rows["nvidia"]["usage"]["day_spend_usd"] == 0.5
        assert client.post(f"{API}/auth/login", json={
            "username": "colleague", "password": "beta-password-1"}).status_code == 200


def test_skip_keeps_the_database_as_it_is_and_says_so_once(hosted_url, tmp_path, monkeypatch):
    data = tmp_path / "local_data"
    _local_install_with_data(data, monkeypatch)
    key = _new_key()
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    monkeypatch.setenv("OFFSETX_SECRETS_KEY", key)
    assert db_cli.main(["import-local", "--data-dir", str(data), "--skip"]) == 0
    with _running(data, key) as (app, client):
        assert app.state.ai_workspaces.key_for("local", "nvidia") == ""
    assert (data / "ai_provider_keys.enc").exists(), "skipping deletes nothing"


def test_a_key_read_the_database_could_not_answer_is_not_the_providers_fault(hosted_url, tmp_path, monkeypatch):
    """D-211: it failed over, counted a call nothing sent, logged the database's
    address where every login can read it, and could blame the provider's key."""
    from offsetx_apollo_builder.ai import broker as broker_module
    from offsetx_apollo_builder.db.connection import DatabaseUnavailable

    called: list[str] = []
    monkeypatch.setattr(broker_module, "create_provider",
                        lambda config, *, environ: called.append(config.model) or None)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", hosted_url)
    with _running(tmp_path / "data", _new_key()) as (app, client):
        for provider, model in (("mistral", "mistral-small-latest"), ("nvidia", MODEL)):
            assert client.post(f"{API}/ai/providers/{provider}/connect", json={
                "api_key": f"{provider}-test-key", "model_ids": [model]}).status_code == 200

        def broken(_workspace_id):
            def resolve(_provider_id):
                raise DatabaseUnavailable("postgres at postgresql://u:***@db.internal/x stopped answering")
            return resolve

        monkeypatch.setattr(app.state.ai_workspaces, "credential_resolver", broken)
        ran = client.post(f"{API}/ai/run", json={"instructions": "Say hello.", "data_class": "public"})
        assert ran.status_code == 503, ran.text
        assert called == [], "no provider was asked, so none was failed over to"
        assert client.get(f"{API}/ai/egress-log").json()["items"] == []
        assert all(not state.day_count for state in app.state.ai_quota._states.values())
        assert app.state.ai_broker._failures == {}


@needs_postgres
def test_a_dropped_connection_at_begin_or_commit_is_the_databases_sentence(postgres_url):
    """D-212: BEGIN and COMMIT on a dropped connection raised the driver's own
    error, which the screens showed as a bare 500."""
    from offsetx_apollo_builder.db.connection import DatabaseUnavailable

    database = open_database(postgres_url)
    killer = open_database(postgres_url)
    try:
        def drop() -> None:
            pid = database.raw.info.backend_pid
            killer.execute("SELECT pg_terminate_backend(?)", [pid])

        database.execute("SELECT 1")
        drop()
        with pytest.raises(DatabaseUnavailable, match="nothing in it ran"):
            with database.transaction():
                database.execute("SELECT 1")
        database.execute("CREATE TABLE IF NOT EXISTS commits (id TEXT)")
        with pytest.raises(DatabaseUnavailable, match="unknown"):
            with database.transaction():
                database.execute("INSERT INTO commits VALUES ('a')")
                drop()
    finally:
        killer.close()
        database.close()


def test_no_message_or_description_repeats_the_database_password(hosted_url, tmp_path, monkeypatch, capsys):
    """D-213: a password in the URL's query string, or a scheme the driver could
    not read, came back in the start-up refusal and the commands' output."""
    from offsetx_apollo_builder.db import describe_target
    from offsetx_apollo_builder.db.connection import DatabaseUnavailable

    assert "hunter2" not in describe_target("postgresql://kunal@db.example.com/off?password=hunter2&sslmode=require")
    assert "sslmode=require" in describe_target("postgresql://kunal@db.example.com/off?password=hunter2&sslmode=require")
    with pytest.raises(DatabaseUnavailable) as failed:
        open_database("postgresql://offcrm:not-the-password@127.0.0.1:1/gone")
    assert "not-the-password" not in str(failed.value)
    monkeypatch.setenv("OFFSETX_DATABASE_URL", "postgresql://offcrm@127.0.0.1:1/gone?password=not-the-password")
    assert db_cli.main(["forget-provider-keys", "--yes"]) == 2
    assert "not-the-password" not in capsys.readouterr().err


def test_two_instances_starting_together_both_start(hosted_url, tmp_path, monkeypatch):
    """D-214: the configured login was checked for, then created, so the second
    of two instances starting at once failed on the unique key."""
    from offsetx_apollo_builder.api.auth import WorkspaceAuthStore

    stores = [WorkspaceAuthStore(tmp_path / f"auth-{index}.db", session_secret=SESSION_SECRET,
                                 session_hours=8, database_target=hosted_url) for index in range(2)]
    try:
        stores[0].bootstrap(username="owner", password="owner-password-12")
        # The second checked before the first created it: it reaches the insert.
        monkeypatch.setattr(stores[1], "_connection", stores[1]._connection)
        original_execute = stores[1]._hosted().execute

        missed: list[str] = []

        def miss_the_first_check(sql, params=None):
            if sql.startswith("SELECT 1 FROM workspace_users") and not missed:
                missed.append(sql)
                return original_execute("SELECT 1 FROM workspace_users WHERE 1 = 0")
            return original_execute(sql, params)

        monkeypatch.setattr(stores[1]._hosted(), "execute", miss_the_first_check)
        stores[1].bootstrap(username="owner", password="owner-password-12")
        assert stores[1].authenticate("owner", "owner-password-12") is not None
    finally:
        for store in stores:
            store.close()


def test_the_classifier_never_blames_a_provider_for_the_database():
    """D-211, at its root: a database's "password authentication failed" read
    as the provider rejecting its key, telling the owner to replace a good key."""
    from offsetx_apollo_builder.ai.failures import FailureAction, classify
    from offsetx_apollo_builder.db.connection import DatabaseUnavailable

    failure = classify(DatabaseUnavailable(
        'Could not connect to postgres at postgresql://u:***@db/x: password authentication failed for user "u"'))
    assert failure.kind.value != "auth"
    assert failure.action is FailureAction.STOP_REQUEST
    assert not failure.counts_against_provider
    assert "database" in failure.owner_action and "key" in failure.owner_action
