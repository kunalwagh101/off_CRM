"""Running the CRM suite against PostgreSQL (`S-06.03.03`).

`S-06.03.03` is DONE only when the CRM's tests pass on SQLite and PostgreSQL
alike. Rewriting every test to take a backend would be a diff across dozens of
files and a second copy of each test to keep in step. So the backend is swapped
underneath them instead:

    OFF_CRM_TEST_POSTGRES_URL='postgresql://postgres@127.0.0.1:55432/postgres' \\
    OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q

In that mode every `OutreachStore(path)` a test opens — directly, through
`OutreachEngine`, or through `create_app` — opens a PostgreSQL schema of its
own instead. The same path within one test is the same schema, because tests
close a store and open it again to prove something survived. Each schema is
dropped when the test ends. With the variable unset, nothing here does anything.

A test about SQLite itself has no PostgreSQL form: one that reads the CRM's
*file* — `sqlite3.connect` on it, its bytes, a backup archive of it — or
upgrades an old SQLite file, or tests SQLite's own connection object
(`GuardedConnection`). It is marked `@pytest.mark.crm_sqlite_only("why")` and
skipped in that mode only, with its reason in the report. Where the property
it protects also holds on PostgreSQL, the reason names the test in
`tests/test_crm_hosted.py` that proves it on both. Nothing else may be marked:
any other failure in that mode is a bug in the CRM's PostgreSQL path.
"""
from __future__ import annotations

import functools
import os
import uuid
from pathlib import Path

import pytest

CRM_ON_POSTGRES = os.getenv("OFF_CRM_TEST_CRM_ON_POSTGRES", "").strip() == "1"
POSTGRES_URL = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()


def in_schema(url: str, schema: str) -> str:
    """The URL with `schema` first on the search path, so tables land in it."""
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}options=-csearch_path%3D{schema}"


@pytest.fixture(autouse=True)
def _disposable_install_identity(monkeypatch, request):
    # Each isolated test is one logical install, stable across its restarts.
    # Tests for absent/different identities explicitly unset/override this.
    monkeypatch.setenv("OFFSETX_INSTALL_ID", str(uuid.uuid5(uuid.NAMESPACE_URL, request.node.nodeid)))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "crm_sqlite_only(reason): about SQLite itself — the CRM's file, an old file's "
        "upgrade, or SQLite's connection object — so skipped when OFF_CRM_TEST_CRM_ON_POSTGRES=1",
    )
    if CRM_ON_POSTGRES and not POSTGRES_URL:
        raise pytest.UsageError(
            "OFF_CRM_TEST_CRM_ON_POSTGRES=1 runs the CRM on PostgreSQL, so it needs "
            "OFF_CRM_TEST_POSTGRES_URL set to a postgresql:// URL as well."
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("crm_sqlite_only")
        if marker is None:
            continue
        reason = str(marker.args[0]).strip() if marker.args else ""
        if not reason:
            # An unexplained skip is how a real failure gets hidden.
            raise pytest.UsageError(f"{item.nodeid}: crm_sqlite_only needs a reason.")
        if CRM_ON_POSTGRES:
            item.add_marker(pytest.mark.skip(reason=f"SQLite only: {reason}"))


@pytest.fixture(autouse=True)
def _crm_on_postgres(monkeypatch: pytest.MonkeyPatch):
    if not CRM_ON_POSTGRES:
        yield
        return

    import psycopg

    from offsetx_apollo_builder.outreach import store as store_module

    schemas: dict[str, str] = {}
    original = store_module.OutreachStore.__init__

    # `wraps`, so a test that reads the store's own `__init__` — the audit's
    # autocommit check — still reads the store's, not this.
    @functools.wraps(original)
    def opened_on_postgres(self, target, *args, **kwargs):
        # Only a file path moves. A URL of any kind — folded by `Path` or not —
        # goes to the store as given, so its refusal is still tested here.
        if not store_module.names_a_url(target):
            key = str(Path(target).resolve())
            if key not in schemas:
                schemas[key] = f"crm_{uuid.uuid4().hex[:12]}"
                with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
                    admin.execute(f'CREATE SCHEMA "{schemas[key]}"')
            target = in_schema(POSTGRES_URL, schemas[key])
        original(self, target, *args, **kwargs)
        backend = getattr(self, "backend", None)
        if backend != "postgres":
            # Asserted, never assumed: the store once took a PostgreSQL URL as
            # a SQLite file name, and every test "on PostgreSQL" passed (D-217).
            self.close()
            raise AssertionError(
                f"The CRM opened on {backend or 'an unknown backend'}, not PostgreSQL (D-217)."
            )

    monkeypatch.setattr(store_module.OutreachStore, "__init__", opened_on_postgres)
    try:
        yield
    finally:
        if schemas:
            with psycopg.connect(POSTGRES_URL, autocommit=True) as admin:
                for schema in schemas.values():
                    admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def isolated_postgres_target():
    from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
    base = os.getenv('OFF_CRM_TEST_POSTGRES_URL')
    if not base:
        pytest.skip('requires a disposable real PostgreSQL server')
    import psycopg
    from psycopg import sql
    schema = 'content_' + uuid.uuid4().hex
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    parts = urlsplit(base)
    options = dict(parse_qsl(parts.query))
    options['options'] = (options.get('options', '') + ' -csearch_path=' + schema).strip()
    try:
        yield urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(options, quote_via=quote), ''))
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
