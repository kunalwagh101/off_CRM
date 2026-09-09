"""Regressions for three defects found in the 2026-09-08 security audit.

Each test here failed before its fix and would fail again if the fix were
reverted. They are grouped because they share an origin — an audit rather than a
feature — and separating them would hide that these are the *found* bugs rather
than designed behaviour.

None of them is exotic. All three are what happens when code written for one
user at a time meets a threadpool and a network.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time

import pytest

from offsetx_apollo_builder.api.auth import DemoSessionAuth, LoginAttemptLimiter
from offsetx_apollo_builder.outreach.store import OutreachStore


# ── 1. concurrent transactions on one shared connection ─────────────────────


def _probe_store(tmp_path) -> OutreachStore:
    store = OutreachStore(tmp_path / "audit.db")
    store.initialize()
    store.connection.execute(
        "CREATE TABLE IF NOT EXISTS audit_probe (id INTEGER PRIMARY KEY, who TEXT)"
    )
    store.connection.commit()
    return store


def test_concurrent_transactions_do_not_lose_writes(tmp_path):
    """The one that cost forty rows.

    `check_same_thread=False` hands one connection to every thread and FastAPI
    runs 193 of its 206 handlers in a threadpool, so two requests really do
    arrive here at once. `sqlite3.threadsafety` is 3, which serialises one
    *statement* and does nothing for a transaction made of several.

    Before the fix this lost exactly half its rows: one thread raised "cannot
    start a transaction within a transaction" and the other thread's commit and
    rollback acted on its open transaction. Four threads rather than two,
    because a bug that needs a precise interleaving should be given more chances
    to appear, not fewer.
    """
    store = _probe_store(tmp_path)
    writers, rows_each = 4, 40
    barrier = threading.Barrier(writers)
    errors: list[tuple[str, str]] = []

    def write(name: str) -> None:
        try:
            barrier.wait(timeout=10)
            for index in range(rows_each):
                with store.transaction() as conn:
                    conn.execute("INSERT INTO audit_probe (who) VALUES (?)", (f"{name}-{index}",))
        except Exception as exc:  # noqa: BLE001 - the failure is the assertion
            errors.append((name, f"{type(exc).__name__}: {exc}"))

    threads = [threading.Thread(target=write, args=(name,)) for name in "ABCD"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == [], f"a concurrent writer failed: {errors}"
    total = store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0]
    assert total == writers * rows_each, f"lost {writers * rows_each - total} committed rows"


def test_an_immediate_transaction_is_also_serialised(tmp_path):
    """`claim_next` — the email worker's exclusive claim — uses `immediate=True`.

    BEGIN IMMEDIATE takes SQLite's *file* lock, which protects this database
    from other processes. It cannot protect a connection from itself, so the
    claim was only exclusive between processes and not between threads.
    """
    store = _probe_store(tmp_path)
    barrier = threading.Barrier(3)
    errors: list[str] = []

    def claim(name: str) -> None:
        try:
            barrier.wait(timeout=10)
            for index in range(25):
                with store.transaction(immediate=True) as conn:
                    conn.execute("INSERT INTO audit_probe (who) VALUES (?)", (f"{name}-{index}",))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=claim, args=(name,)) for name in "XYZ"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == [], errors
    assert store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 75


def test_a_failing_transaction_still_rolls_back_and_releases(tmp_path):
    """A lock that is not released on the error path turns data loss into a hang."""
    store = _probe_store(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as conn:
            conn.execute("INSERT INTO audit_probe (id, who) VALUES (1, 'first')")
            conn.execute("INSERT INTO audit_probe (id, who) VALUES (1, 'clash')")

    assert store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 0

    done = threading.Event()

    def after() -> None:
        with store.transaction() as conn:
            conn.execute("INSERT INTO audit_probe (who) VALUES ('after')")
        done.set()

    thread = threading.Thread(target=after)
    thread.start()
    thread.join(timeout=10)
    assert done.is_set(), "the write lock was not released by the failing transaction"


# ── 2. the login limiter grew without bound ─────────────────────────────────


def test_the_login_limiter_forgets_a_client_once_its_window_closes():
    """Pruning emptied each deque and left the key, so the dict only ever grew.

    The key is a client address, and one IPv6 /64 — a single residential
    allocation — is 18 quintillion of them. Measured at 50,000 retained keys
    with every window long expired.
    """
    limiter = LoginAttemptLimiter()
    for index in range(2_000):
        limiter.failed(f"2001:db8::{index:x}", now=0.0)
    assert len(limiter._attempts) == 2_000

    for index in range(2_000):
        limiter.allowed(f"2001:db8::{index:x}", now=100_000.0)

    assert len(limiter._attempts) == 0, "expired clients are still held in memory"


def test_forgetting_expired_clients_does_not_weaken_the_limit():
    """The fix must not become a way to reset the counter by asking politely."""
    limiter = LoginAttemptLimiter(maximum=5, window_seconds=300)
    for _ in range(5):
        limiter.failed("198.51.100.7", now=1.0)

    for moment in (1.0, 2.0, 100.0, 299.0):
        assert limiter.allowed("198.51.100.7", now=moment) is False, moment
    assert limiter.allowed("198.51.100.7", now=1_000.0) is True


# ── 3. the username was a timing oracle ─────────────────────────────────────


def test_a_wrong_username_compares_the_password_anyway():
    """`and` short-circuits, so a wrong username returned before the password
    was ever compared — and that difference is measurable. The constant-time
    comparison underneath is wasted if the call above it branches.

    Asserted structurally rather than by timing: a wall-clock test of a
    microsecond difference is flaky on shared CI and would be deleted within a
    month. This counts comparisons instead, which is the property that matters.
    """
    import hmac

    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    calls: list[int] = []
    real = hmac.compare_digest

    def counting(left, right):
        calls.append(1)
        return real(left, right)

    hmac.compare_digest = counting
    try:
        calls.clear()
        auth.authenticate("owner", "wrong-password-entirely")
        with_right_user = len(calls)

        calls.clear()
        auth.authenticate("not-the-owner", "wrong-password-entirely")
        with_wrong_user = len(calls)
    finally:
        hmac.compare_digest = real

    assert with_wrong_user == with_right_user == 2, (
        "a wrong username skips the password comparison, which leaks which "
        "usernames are real"
    )


def test_authentication_still_answers_correctly():
    """The obvious thing to break while removing a short circuit."""
    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    assert auth.authenticate("owner", "a-long-enough-password") is True
    assert auth.authenticate("owner", "wrong") is False
    assert auth.authenticate("wrong", "a-long-enough-password") is False
    assert auth.authenticate("", "") is False


def test_a_session_token_still_round_trips_and_expires():
    auth = DemoSessionAuth(
        username="owner", password="a-long-enough-password", session_secret="s" * 32,
        session_hours=1,
    )
    token = auth.issue(now=1_000)
    assert auth.verify(token, now=1_000).username == "owner"
    assert auth.verify(token, now=1_000 + 3601) is None
    assert auth.verify(token[:-2] + "xx", now=1_000) is None


# ── 4. the local API is no longer open to whatever can reach the port ───────
#
# Two controls, added 2026-09-08. Both are tested against a production-shaped
# config — the harness opt-out (`allow_unauthenticated`) is off here, because a
# test that runs with the check disabled proves nothing about the check.

import json

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _real_settings(tmp_path, **overrides) -> AppSettings:
    base = dict(
        project_root=tmp_path,
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "no-dist",
        api_token="k" * 40,
        allowed_hosts=("testserver",),
    )
    base.update(overrides)
    return AppSettings(**base)


def test_a_local_install_will_not_start_without_authentication(tmp_path):
    """The fail-open this closes: with nothing configured, every route used to
    answer 200 to anyone who could reach the port. Loopback is not an exemption —
    an unauthenticated local API is readable by every other process and user on
    the machine.

    Refused at construction rather than per request, so the failure is a startup
    error somebody sees rather than a service quietly handing out contacts.
    """
    with pytest.raises(ValueError, match="requires an API token"):
        create_app(_real_settings(tmp_path, api_token=""))


def test_loopback_requires_the_token_like_everywhere_else(tmp_path):
    settings = _real_settings(tmp_path, host="127.0.0.1")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/dashboard").status_code == 401
        authorised = client.get(
            "/api/v1/dashboard", headers={"Authorization": f"Bearer {settings.api_token}"}
        )
        assert authorised.status_code == 200


def test_a_wrong_token_is_refused(tmp_path):
    settings = _real_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get(
            "/api/v1/dashboard", headers={"Authorization": "Bearer " + "k" * 39 + "j"}
        ).status_code == 401


def test_a_host_this_server_does_not_answer_to_is_refused(tmp_path):
    """DNS rebinding is what makes "it only listens on localhost" untrue: a page
    points a name it controls at 127.0.0.1 and reaches the API with the browser's
    cooperation. CORS does not stop the request being made — it only stops the
    attacker reading the reply — and a rebound name looks same-origin anyway.
    """
    settings = _real_settings(tmp_path)
    headers = {"Authorization": f"Bearer {settings.api_token}"}
    with TestClient(create_app(settings)) as client:
        for host in ("rebind.attacker.test", "rebind.attacker.test:8766", "evil.example"):
            answer = client.get("/api/v1/dashboard", headers={**headers, "Host": host})
            assert answer.status_code == 421, f"{host} was answered"
            assert "does not answer to the host" in answer.json()["detail"]


def test_the_hosts_this_server_does_answer_to_still_work(tmp_path):
    """A control that refuses everything is not a control, it is an outage."""
    settings = _real_settings(tmp_path, allowed_hosts=("testserver", "crm.example"))
    headers = {"Authorization": f"Bearer {settings.api_token}"}
    with TestClient(create_app(settings)) as client:
        for host in ("127.0.0.1:8766", "localhost:8766", "[::1]:8766", "crm.example",
                     "CRM.example", "testserver"):
            answer = client.get("/api/v1/dashboard", headers={**headers, "Host": host})
            assert answer.status_code == 200, f"{host} was refused"


def test_the_host_check_runs_before_the_public_path_exemption(tmp_path):
    """Otherwise the unauthenticated endpoints are a rebinding target of their own."""
    settings = _real_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get(
            "/api/v1/meta", headers={"Host": "rebind.attacker.test"}
        ).status_code == 421
        assert client.get("/api/v1/meta").status_code == 200


def test_a_provisioned_token_is_strong_stable_and_private(tmp_path, monkeypatch):
    """A local install gets a token rather than an error it must fix by hand.

    `0600` is not theatre. Anything able to read this file can already open the
    SQLite database beside it, so it adds no secret — it closes the gap between
    "can read my files" and "can reach my API", which is where a browser
    extension, another user account, or a rebinding page sits.
    """
    for name in ("OFFSETX_LOCAL_API_TOKEN", "OFFSETX_DEMO_USERNAME",
                 "OFFSETX_DEMO_PASSWORD", "OFFSETX_SESSION_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(tmp_path / "data" / "crm.db"))

    first = AppSettings.from_env(tmp_path)
    assert len(first.api_token) >= 32

    token_file = tmp_path / "data" / AppSettings.TOKEN_FILENAME
    assert oct(token_file.stat().st_mode & 0o777) == "0o600"
    assert AppSettings.from_env(tmp_path).api_token == first.api_token, "token changed on restart"


def test_provisioning_never_overwrites_a_token_the_owner_chose(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSETX_LOCAL_API_TOKEN", "o" * 44)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(tmp_path / "data" / "crm.db"))
    settings = AppSettings.from_env(tmp_path)
    assert settings.api_token == "o" * 44
    assert not (tmp_path / "data" / AppSettings.TOKEN_FILENAME).exists()


def test_the_advertised_token_header_is_the_one_the_server_reads(tmp_path):
    """CORS advertised `X-off-CRM-Token` while the server read `x-offsetx-token`,
    so a client that followed the advertisement was refused."""
    settings = _real_settings(tmp_path)
    app = create_app(settings)
    advertised = {
        header.lower()
        for middleware in app.user_middleware
        for header in (middleware.kwargs.get("allow_headers") or [])
    }
    with TestClient(app) as client:
        answer = client.get(
            "/api/v1/dashboard", headers={"X-Offsetx-Token": settings.api_token}
        )
    assert answer.status_code == 200, "the header the server reads does not work"
    assert "x-offsetx-token" in advertised, "the server reads a header CORS does not allow"


# ── 5. a bare statement no longer joins somebody else's transaction ─────────
#
# S-06.02.09. The lock added on 2026-09-08 made two transactions safe against
# each other. It left this: a statement run outside any transaction joined
# whatever transaction another thread had open, and was committed or rolled back
# with work it had nothing to do with.


def test_a_bare_write_is_not_rolled_back_by_someone_else_s_failure(tmp_path):
    """The demonstration that named the story.

        thread A   BEGIN, INSERT 'holder', raise  -> ROLLBACK
        thread B   INSERT 'bystander'             -> reported success
        surviving rows: []

    B's write was destroyed by A's failure, and B was told it succeeded. Every
    bare write here must survive every rolled-back transaction beside it.
    """
    store = _probe_store(tmp_path)
    rounds, bystanders = 12, 4
    barrier = threading.Barrier(bystanders + 1)
    errors: list[str] = []

    def failing_transactions() -> None:
        try:
            barrier.wait(timeout=20)
            for index in range(rounds):
                try:
                    with store.transaction() as conn:
                        conn.execute("INSERT INTO audit_probe (who) VALUES (?)", (f"doomed-{index}",))
                        raise RuntimeError("this request failed")
                except RuntimeError:
                    pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"holder: {type(exc).__name__}: {exc}")

    def bare_writes(name: str) -> None:
        try:
            barrier.wait(timeout=20)
            for index in range(rounds):
                store.connection.execute(
                    "INSERT INTO audit_probe (who) VALUES (?)", (f"{name}-{index}",)
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=failing_transactions)]
    threads += [threading.Thread(target=bare_writes, args=(f"bare{n}",)) for n in range(bystanders)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "a thread never finished — deadlock"
    assert errors == [], errors

    rows = [row[0] for row in store.connection.execute("SELECT who FROM audit_probe").fetchall()]
    assert not [row for row in rows if row.startswith("doomed")], "a failed transaction committed"
    assert len(rows) == rounds * bystanders, (
        f"expected every bare write to survive, {rounds * bystanders - len(rows)} were lost"
    )


def test_a_bare_write_is_not_committed_early_by_someone_else(tmp_path):
    """The mirror of the last one. A bare write must not be made durable by
    another thread's commit before its own statement finished — and a read must
    not see a transaction's uncommitted rows as though they were saved."""
    store = _probe_store(tmp_path)
    started, may_commit = threading.Event(), threading.Event()
    seen: list[int] = []

    def holder() -> None:
        with store.transaction() as conn:
            conn.execute("INSERT INTO audit_probe (who) VALUES ('uncommitted')")
            started.set()
            may_commit.wait(timeout=10)

    def reader() -> None:
        started.wait(timeout=10)
        may_commit.set()
        # Blocks until the transaction above releases, which is the point: the
        # count it sees is a settled one, never a half-finished transaction.
        seen.append(store.connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0])

    threads = [threading.Thread(target=holder), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), "deadlock"
    assert seen == [1], f"reader saw {seen}, expected the committed row only"


def test_the_guard_still_behaves_like_a_connection(tmp_path):
    """155 call sites reach through this object. Replacing it is only safe if it
    keeps the shape they were written against."""
    import sqlite3

    store = _probe_store(tmp_path)
    connection = store.connection

    assert connection.row_factory is sqlite3.Row
    cursor = connection.execute("INSERT INTO audit_probe (who) VALUES ('shape')")
    assert isinstance(cursor, sqlite3.Cursor)
    assert cursor.lastrowid is not None
    connection.commit()

    row = connection.execute("SELECT who FROM audit_probe").fetchone()
    assert row["who"] == "shape", "row_factory did not survive the wrapper"

    connection.executemany(
        "INSERT INTO audit_probe (who) VALUES (?)", [("a",), ("b",)]
    )
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 3

    connection.executescript("INSERT INTO audit_probe (who) VALUES ('script');")
    assert connection.execute("SELECT COUNT(*) FROM audit_probe").fetchone()[0] == 4

    # The escape hatch is named, so anything opting out of the guarantee says so.
    assert isinstance(connection.raw, sqlite3.Connection)

    manual = connection.cursor()
    manual.execute("SELECT COUNT(*) FROM audit_probe")
    assert manual.fetchone()[0] == 4


def test_backup_reaches_the_real_connection_underneath(tmp_path):
    """`Connection.backup` needs a real connection as its target, not a wrapper —
    the one call site would raise a TypeError if this were forwarded naively."""
    import sqlite3

    store = _probe_store(tmp_path)
    store.connection.execute("INSERT INTO audit_probe (who) VALUES ('saved')")
    store.connection.commit()

    other = OutreachStore(tmp_path / "copy.db")
    store.connection.backup(other.connection)
    assert other.connection.execute("SELECT who FROM audit_probe").fetchone()[0] == "saved"
    other.close()


def test_no_shared_connection_escapes_the_guard():
    """The check that survives me.

    Not "one connection in the package" — `backup.py` opens short-lived,
    function-local ones to copy and integrity-check a file, and those are
    correct: never shared, always closed in a `finally`. The hazard is a
    connection **stored on an object**, because that is the one two threads
    reach at once. So the rule is about assignment, not about counting, and it
    is checked with `ast` rather than a regex so a line break cannot hide one.
    """
    import ast
    import pathlib

    offenders = []
    for path in pathlib.Path("offsetx_apollo_builder/outreach").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            # Only attribute targets: `self.connection = ...` outlives the call,
            # a local `source = ...` does not.
            if not any(isinstance(target, ast.Attribute) for target in node.targets):
                continue
            for inner in ast.walk(node.value):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "connect"
                    and isinstance(inner.func.value, ast.Name)
                    and inner.func.value.id == "sqlite3"
                ):
                    wrapped = isinstance(node.value, ast.Call) and (
                        getattr(node.value.func, "id", "") == "GuardedConnection"
                    )
                    if not wrapped:
                        offenders.append(f"{path}:{node.lineno}")

    assert offenders == [], (
        "a long-lived connection is assigned without GuardedConnection, which "
        f"reopens the hazard: {offenders}"
    )


def test_the_connection_is_opened_in_autocommit():
    """Python's default isolation level opens a transaction before any DML and
    leaves it open, which is what made a bare statement joinable in the first
    place. The guard serialises; this is what stops there being anything to
    join."""
    import inspect

    from offsetx_apollo_builder.outreach import store as module

    source = inspect.getsource(module.OutreachStore.__init__)
    assert "isolation_level=None" in source
