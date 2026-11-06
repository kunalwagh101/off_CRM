"""Trusted schema selection must be local to each PostgreSQL transaction."""
import uuid
import os
from urllib.parse import urlsplit, urlunsplit
from concurrent.futures import ThreadPoolExecutor
import pytest
from offsetx_apollo_builder.db import DatabaseError, open_database


@pytest.fixture()
def pooler_target():
    target = os.getenv('OFF_CRM_TEST_PGBOUNCER_URL', '')
    direct = os.getenv('OFF_CRM_TEST_POSTGRES_URL', '')
    if not target or not direct:
        pytest.skip('requires the disposable transaction-pooler CI target')
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    parsed = urlsplit(target)
    admin_url = urlunsplit(parsed._replace(path='/pgbouncer'))
    with psycopg.connect(admin_url, autocommit=True, row_factory=dict_row, cursor_factory=psycopg.ClientCursor) as pooler:
        assert 'PgBouncer' in pooler.execute('SHOW VERSION').fetchone()['version']
        config = {row['key']: row['value'] for row in pooler.execute('SHOW CONFIG')}
        assert config['pool_mode'] == 'transaction'
        assert config['default_pool_size'] == '1'
        assert config['server_reset_query_always'] == '1'
    database = 'offcrm_ns_pool_' + uuid.uuid4().hex
    with psycopg.connect(direct, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    try:
        yield urlunsplit(parsed._replace(path='/' + database))
    finally:
        with psycopg.connect(direct, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))


@pytest.fixture(params=['direct', 'transaction_pooler'])
def namespaces(request):
    isolated_postgres_target = request.getfixturevalue('isolated_postgres_target' if request.param == 'direct' else 'pooler_target')
    names = ['crm_ws_' + uuid.uuid4().hex for _ in range(2)]
    with open_database(isolated_postgres_target) as admin:
        for name in names:
            admin.execute(f'CREATE SCHEMA "{name}"')
    try:
        yield isolated_postgres_target, names
    finally:
        with open_database(isolated_postgres_target) as admin:
            for name in names:
                admin.execute(f'DROP SCHEMA "{name}" CASCADE')


def test_alternating_concurrent_equal_keys_never_cross_namespace(namespaces):
    target, names = namespaces
    stores = [open_database(target, namespace=name) for name in names]
    try:
        for index, store in enumerate(stores):
            store.execute('CREATE TABLE people(id TEXT PRIMARY KEY, email TEXT UNIQUE, campaign TEXT)')
            store.execute('INSERT INTO people VALUES(?,?,?)', ['same-id', 'same@example.com', f'private-{index}'])
        def read(index):
            for _ in range(20):
                assert stores[index].execute('SELECT campaign FROM people').fetchone()['campaign'] == f'private-{index}'
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(read, range(2)))
        # Closing the raw transport simulates a dropped idle connection. The
        # adapter may reconnect before the next statement, retaining its owner.
        stores[0].raw.close()
        assert stores[0].execute('SELECT campaign FROM people').fetchone()['campaign'] == 'private-0'
    finally:
        for store in stores:
            store.close()


def test_schema_selection_does_not_persist_on_a_pooled_server_session(namespaces):
    target, names = namespaces
    with open_database(target, namespace=names[0]) as store:
        original = store.raw.execute('SELECT current_schema() AS value').fetchone()['value']
        with store.transaction():
            store.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            assert store.execute('SELECT current_schema() AS value').fetchone()['value'] == names[0]
        assert store.raw.execute('SELECT current_schema() AS value').fetchone()['value'] == original
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.execute('CREATE TABLE rolled_back(id TEXT)')
                raise RuntimeError('after write')
        assert not store.columns('rolled_back')
        assert store.raw.execute('SELECT current_schema() AS value').fetchone()['value'] == original


def test_namespace_does_not_fall_back_to_the_control_schema(namespaces):
    target, names = namespaces
    with open_database(target) as admin:
        admin.execute('CREATE TABLE control_private(id TEXT)')
    with open_database(target, namespace=names[0]) as store:
        assert not store.columns('control_private')
        with pytest.raises(Exception) as failure:
            store.execute('SELECT * FROM control_private')
        assert getattr(failure.value, 'sqlstate', '') == '42P01'
    with pytest.raises(DatabaseError, match='namespace'):
        open_database(target, namespace='crm_ws_' + uuid.uuid4().hex)


def test_invalid_namespace_is_refused_before_connecting_or_creating_a_file(tmp_path):
    for name in ('public, private', 'public;DROP SCHEMA public', 'x' * 64, '', 'public', 'pg_catalog', 'information_schema'):
        with pytest.raises(DatabaseError, match='namespace'):
            open_database('postgresql://invalid.invalid/test', namespace=name)
    path = tmp_path / 'must-not-exist.db'
    with pytest.raises(DatabaseError, match='namespace'):
        open_database(path, namespace='crm_ws_valid')
    assert not path.exists()


def test_real_crm_engines_keep_equal_emails_and_private_campaigns_separate(namespaces):
    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.models import ContactInput
    target, names = namespaces
    engines = []
    try:
        for index, name in enumerate(names):
            workspace = 'alpha' if index == 0 else 'beta'
            engine = OutreachEngine(target, workspace_id=workspace, storage_namespace=name)
            engines.append(engine)
            campaign = engine.create_campaign(name='PRIVATE '+workspace)
            contact = engine.store.create_manual_campaign_contact(campaign, ContactInput(
                full_name='Anita Rao', email='same@example.com', company='Example Exports', category='CBAM'))
            assert contact['email'] == 'same@example.com'
            assert engine.email_expert.memory.workspace_id == workspace
        alpha, beta = engines
        assert [row['name'] for row in alpha.store.list_campaigns()[0]] == ['PRIVATE alpha']
        assert [row['name'] for row in beta.store.list_campaigns()[0]] == ['PRIVATE beta']
        foreign = alpha.store.list_campaigns()[0][0]['id']
        with pytest.raises(KeyError):
            beta.store.get_campaign(foreign)
    finally:
        for engine in engines:
            engine.close()
