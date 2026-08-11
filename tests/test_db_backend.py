"""The database backend seam, and the egress log on both sides of it.

off_CRM is SQLite-first and stays that way for one owner on one machine. This
exists for the case SQLite genuinely cannot serve — and the case that is live
today is a deployment whose disk does not survive a restart. `BUILD_STATE` §6.4:
`OFFSETX_DATA_DIR` points at `/tmp` on Render, so **the egress log resets on
every restart**. That log is the record of exactly what data left to which
provider, and the security argument of the whole system is that the guarantee is
verified rather than trusted. A verification trail that resets verifies nothing.

So the egress log is the first store across, and these tests run it against
**both** backends. The Postgres half is skipped unless `OFF_CRM_TEST_POSTGRES_URL`
is set, the same way the live Docker sandbox test is skipped — a test that
silently passes because it did not run is worse than one that says it was
skipped.

The other group of tests here is the `?` → `%s` translation, which is where the
subtle bugs live: a `?` or a `%` inside a string literal must survive untouched.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.log import SCHEMA, EgressLog
from offsetx_apollo_builder.db import (
    DATABASE_URL_ENV,
    DatabaseError,
    SQLiteDatabase,
    describe_target,
    is_postgres_url,
    open_database,
    resolve_target,
    translate_params,
)
from offsetx_apollo_builder.db.copy import copy_egress_log

POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_URL else [])
needs_postgres = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set OFF_CRM_TEST_POSTGRES_URL to a postgresql:// URL to run these",
)


@pytest.fixture(params=BACKENDS)
def log(request, tmp_path: Path):
    """One egress log per backend, starting empty each time."""
    if request.param == "sqlite":
        item = EgressLog(tmp_path / "egress.db")
    else:
        item = EgressLog(POSTGRES_URL)
        item.connection.executescript("DROP TABLE IF EXISTS ai_egress_log")
        item.connection.executescript(SCHEMA)
    yield item
    item.close()


def _record(log: EgressLog, **overrides):
    fields = dict(
        provider_id="nvidia",
        provider_name="NVIDIA NIM",
        jurisdiction="US",
        tier="B",
        policy="standard",
        data_class="campaign",
        task_type="draft_email",
        status="ok",
        duration_ms=120,
        payload={"person": {"title": "Head of Trade"}},
        payload_summary={"fields": 1},
        response_text="drafted",
    )
    fields.update(overrides)
    return log.record(**fields)


# ─────────────────────────────────────────────────────────────────────────────
# Translation — where the subtle bugs are
# ─────────────────────────────────────────────────────────────────────────────


def test_placeholders_become_psycopg_style():
    assert translate_params("SELECT * FROM t WHERE a = ? AND b = ?") == (
        "SELECT * FROM t WHERE a = %s AND b = %s"
    )


def test_a_question_mark_inside_a_string_literal_is_left_alone():
    """The reason this is a walker and not a regex.

    A blind replace rewrites data, and the corruption is invisible until someone
    reads the row back.
    """
    assert translate_params("SELECT * FROM t WHERE q = 'why?' AND a = ?") == (
        "SELECT * FROM t WHERE q = 'why?' AND a = %s"
    )


def test_literal_percent_is_escaped_because_psycopg_would_eat_it():
    """psycopg treats `%` as a placeholder marker whenever parameters exist."""
    assert translate_params("SELECT ? WHERE n LIKE '50%'") == (
        "SELECT %s WHERE n LIKE '50%%'"
    )
    assert translate_params("SELECT a % b FROM t WHERE c = ?") == (
        "SELECT a %% b FROM t WHERE c = %s"
    )


def test_a_doubled_quote_does_not_end_the_literal():
    """'it''s' is one string, so the `?` after it is still data."""
    assert translate_params("SELECT 'it''s ok?' , ? FROM t") == (
        "SELECT 'it''s ok?' , %s FROM t"
    )


def test_double_quoted_identifiers_are_respected():
    assert translate_params('SELECT "odd?name" FROM t WHERE a = ?') == (
        'SELECT "odd?name" FROM t WHERE a = %s'
    )


def test_the_real_queries_translate_without_touching_their_literals():
    """The escape clause in the CRM's LIKE filters is the awkward real case."""
    original = "SELECT * FROM contacts WHERE full_name LIKE ? ESCAPE '\\' LIMIT ?"
    assert translate_params(original) == (
        "SELECT * FROM contacts WHERE full_name LIKE %s ESCAPE '\\' LIMIT %s"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Choosing a backend
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "target,expected",
    [
        ("postgresql://user@host/db", True),
        ("postgres://user@host/db", True),
        ("local_data/ai_egress.db", False),
        ("/var/lib/off_crm/egress.db", False),
        ("", False),
    ],
)
def test_only_an_explicit_postgres_scheme_means_postgres(target, expected):
    """Anything else is a path.

    A mistyped DSN must not silently create an empty SQLite file and look like
    it worked — which is what a looser rule ("contains a colon"?) would do.
    """
    assert is_postgres_url(target) is expected


def test_a_path_object_is_never_a_url():
    assert is_postgres_url(Path("postgresql://not-really")) is False


def test_target_resolution_order(monkeypatch, tmp_path):
    """Explicit beats environment beats default.

    The middle rung is what lets a deployment set one variable without every
    call site learning about it; the top rung is what keeps a test's scratch
    file safe from an environment variable reaching in.
    """
    monkeypatch.setenv(DATABASE_URL_ENV, "postgresql://from-env/db")
    assert resolve_target("postgresql://explicit/db") == "postgresql://explicit/db"
    assert resolve_target(None, default=tmp_path / "x.db") == "postgresql://from-env/db"

    monkeypatch.delenv(DATABASE_URL_ENV)
    assert resolve_target(None, default=tmp_path / "x.db") == str(tmp_path / "x.db")

    with pytest.raises(DatabaseError) as exc:
        resolve_target(None)
    assert DATABASE_URL_ENV in str(exc.value)


def test_describing_a_target_never_prints_the_password():
    described = describe_target("postgresql://kunal:hunter2@db.example.com:5432/off_crm")
    assert "hunter2" not in described
    assert "kunal" in described
    assert "db.example.com" in described


def test_a_missing_psycopg_says_how_to_install_it(monkeypatch):
    """The failure an owner will actually hit first.

    "No module named psycopg" is a stack trace; this is a sentence with the
    command in it.
    """
    import builtins

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("No module named 'psycopg'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(DatabaseError) as exc:
        open_database("postgresql://host/db")
    assert "pip install" in str(exc.value)
    assert "[postgres]" in str(exc.value)


def test_sqlite_keeps_its_pragmas(tmp_path):
    """The seam must not change how SQLite behaves — every existing test relies on it."""
    database = SQLiteDatabase(str(tmp_path / "x.db"))
    try:
        mode = database.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
    finally:
        database.close()


# ─────────────────────────────────────────────────────────────────────────────
# The egress log, on both backends
# ─────────────────────────────────────────────────────────────────────────────


def test_a_record_round_trips(log):
    row_id = _record(log)
    stored = log.get(row_id)
    assert stored is not None
    assert stored["provider_id"] == "nvidia"
    assert stored["tier"] == "B"
    assert stored["payload"] == {"person": {"title": "Head of Trade"}}
    assert stored["findings"] == []


def test_listing_filters_and_counts(log):
    _record(log, provider_id="nvidia", status="ok")
    _record(log, provider_id="mistral", status="blocked")
    _record(log, provider_id="mistral", status="ok")

    items, total = log.list()
    assert total == 3 and len(items) == 3

    items, total = log.list(provider_id="mistral")
    assert total == 2
    assert {item["provider_id"] for item in items} == {"mistral"}

    _, blocked = log.list(status="blocked")
    assert blocked == 1


def test_the_list_view_never_carries_the_full_payload(log):
    """The list is a summary; the payload needs a deliberate `get`.

    It is the most sensitive column in the database — the exact text that left
    the machine — so it does not ride along in a screen that renders fifty rows.
    """
    _record(log)
    items, _ = log.list()
    assert "payload" not in items[0]
    assert "payload_summary" in items[0]


def test_stats_group_without_relying_on_a_sqlite_ism(log):
    """The query that Postgres rejected and SQLite quietly allowed.

    `SELECT provider_id, provider_name, jurisdiction, COUNT(*) … GROUP BY
    provider_id` runs on SQLite and picks an arbitrary row for the ungrouped
    columns. Postgres refuses it outright, which is how the bug was found.
    """
    _record(log, provider_id="nvidia", provider_name="NVIDIA NIM", status="ok")
    _record(log, provider_id="nvidia", provider_name="NVIDIA NIM", status="blocked")
    _record(log, provider_id="mistral", provider_name="Mistral", status="failed")

    stats = log.stats()
    assert stats["calls"] == 3
    assert stats["blocked"] == 1
    assert stats["failed"] == 1
    assert {row["tier"]: row["calls"] for row in stats["by_tier"]} == {"B": 3}
    providers = {row["provider_id"]: row for row in stats["by_provider"]}
    assert providers["nvidia"]["calls"] == 2
    assert providers["nvidia"]["provider_name"] == "NVIDIA NIM"
    assert providers["mistral"]["jurisdiction"] == "US"


def test_clearing_by_workspace_leaves_the_others(log):
    _record(log, workspace_id="local")
    _record(log, workspace_id="other")
    assert log.clear(workspace_id="other") == 1
    items, total = log.list()
    assert total == 1 and items[0]["workspace_id"] == "local"


def test_a_payload_containing_a_percent_sign_survives(log):
    """`%` is the character psycopg treats as a placeholder marker.

    It arrives as a *parameter* rather than as SQL, so it must pass through
    untouched — including into the JSON that comes back out.
    """
    row_id = _record(log, payload={"note": "margin is 40% and rising", "q": "why?"})
    stored = log.get(row_id)
    assert stored["payload"]["note"] == "margin is 40% and rising"
    assert stored["payload"]["q"] == "why?"


def test_the_backend_names_itself(log):
    assert log.backend in {"sqlite", "postgres"}


# ─────────────────────────────────────────────────────────────────────────────
# Moving an existing log across
# ─────────────────────────────────────────────────────────────────────────────


@needs_postgres
def test_copying_an_existing_log_into_postgres(tmp_path):
    source = tmp_path / "egress.db"
    origin = EgressLog(source)
    for index in range(25):
        _record(origin, provider_id=f"p{index % 3}", duration_ms=index)
    origin.close()

    destination = EgressLog(POSTGRES_URL)
    destination.connection.executescript("DROP TABLE IF EXISTS ai_egress_log")
    destination.close()

    result = copy_egress_log(source, POSTGRES_URL)
    assert result.ok
    assert result.rows_written == 25
    assert result.destination_total == 25
    assert result.source_total == 25, "the source must not be modified"

    moved = EgressLog(POSTGRES_URL)
    try:
        items, total = moved.list(limit=50)
        assert total == 25
        assert moved.get(items[0]["id"])["payload"] == {
            "person": {"title": "Head of Trade"}
        }
    finally:
        moved.close()


@needs_postgres
def test_copying_twice_writes_nothing_the_second_time(tmp_path):
    """Re-running has to be safe, or an interrupted copy leaves an operator guessing."""
    source = tmp_path / "egress.db"
    origin = EgressLog(source)
    _record(origin)
    origin.close()

    destination = EgressLog(POSTGRES_URL)
    destination.connection.executescript("DROP TABLE IF EXISTS ai_egress_log")
    destination.close()

    first = copy_egress_log(source, POSTGRES_URL)
    second = copy_egress_log(source, POSTGRES_URL)
    assert first.rows_written == 1
    assert second.rows_written == 0
    assert second.skipped_existing == 1
    assert second.destination_total == 1


def test_copying_to_sqlite_is_refused(tmp_path):
    """It is a file copy, and pretending otherwise invites a half-done one."""
    source = tmp_path / "egress.db"
    origin = EgressLog(source)
    origin.connection  # the connection is lazy; touch it so the file exists
    origin.close()
    with pytest.raises(DatabaseError) as exc:
        copy_egress_log(source, str(tmp_path / "other.db"))
    assert "postgresql://" in str(exc.value)


def test_copying_from_a_missing_file_says_so(tmp_path):
    with pytest.raises(DatabaseError) as exc:
        copy_egress_log(tmp_path / "nope.db", "postgresql://host/db")
    assert "Nothing to copy" in str(exc.value)


def test_the_copied_columns_match_the_schema():
    """A column added to the log without updating the copy list must fail loudly.

    Copying with `SELECT *` across two engines leaves column order to chance,
    and a new column would shift every value one place to the left. So the list
    is explicit — and this test is what keeps it honest.
    """
    from offsetx_apollo_builder.db.copy import EGRESS_COLUMNS

    declared = [
        line.strip().split()[0]
        for line in SCHEMA.splitlines()
        if line.startswith("    ") and not line.strip().startswith(("CREATE", ")", "--"))
    ]
    assert list(EGRESS_COLUMNS) == declared
