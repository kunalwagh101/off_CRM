"""Actual registry acceptance on a dedicated database and transaction pooler."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.db import open_database
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.outreach.workspace_registry import WorkspaceCrmRegistry, CrmRoutingError
from test_postgres_namespaces import pooler_target  # noqa: F401 - reusable real-pooler fixture


@pytest.fixture(params=['direct', 'transaction_pooler'])
def registry_database(request, monkeypatch):
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('OFFSETX_INSTALL_ID', str(uuid.uuid4()))
    if request.param == 'transaction_pooler':
        yield request.getfixturevalue('pooler_target')
        return
    base = os.getenv('OFF_CRM_TEST_POSTGRES_URL')
    if not base:
        pytest.skip('requires a disposable real PostgreSQL server')
    import psycopg
    from psycopg import sql
    name = 'offcrm_registry_' + uuid.uuid4().hex
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        yield urlunsplit(urlsplit(base)._replace(path='/'+name))
    finally:
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def make_registry(target, directory):
    return WorkspaceCrmRegistry(root_target=target, data_dir=directory,
                                known_workspaces=lambda: {'alpha', 'beta'}, max_cached=1)


def test_real_registry_concurrent_initialization_eviction_restart_and_missing_book(registry_database, tmp_path):
    target = registry_database
    books = [make_registry(target, tmp_path) for _ in range(2)]
    try:
        def write(index):
            with books[index].lease('alpha') as engine:
                return engine.create_campaign(name='Alpha '+str(index))
        with ThreadPoolExecutor(max_workers=2) as pool:
            alpha_ids = list(pool.map(write, range(2)))
        with books[0].lease('alpha') as alpha:
            alpha.store.create_manual_campaign_contact(alpha_ids[0], ContactInput(
                full_name='Alpha Private', email='same@example.com', company='Alpha Ltd', category='CBAM'))
        with books[0].lease('beta') as beta:
            campaign = beta.create_campaign(name='Beta Private')
            beta.store.create_manual_campaign_contact(campaign, ContactInput(
                full_name='Beta Private', email='same@example.com', company='Beta Ltd', category='CBAM'))
            with pytest.raises(KeyError):
                beta.store.get_campaign(alpha_ids[0])
        with books[0].lease('alpha') as alpha:
            assert {row['name'] for row in alpha.store.list_campaigns()[0]} == {'Alpha 0', 'Alpha 1'}
        with open_database(target) as legacy:
            with pytest.raises(Exception, match='Workspace routing is active'):
                legacy.execute('SELECT * FROM contacts').fetchall()
    finally:
        for book in books:
            book.close()
    restarted = make_registry(target, tmp_path)
    try:
        with restarted.lease('beta') as beta:
            assert beta.store.get_campaign(campaign)['name'] == 'Beta Private'
            namespace = beta.store.namespace
    finally:
        restarted.close()
    with open_database(target) as admin:
        admin.execute(f'DROP SCHEMA "{namespace}" CASCADE')
    missing = make_registry(target, tmp_path)
    try:
        with pytest.raises(CrmRoutingError, match='missing'):
            with missing.lease('beta'):
                pass
    finally:
        missing.close()


def test_nonempty_legacy_visible_through_search_path_cannot_be_hidden(registry_database, tmp_path, request):
    # PgBouncer intentionally rejects startup options. This search_path
    # topology is a direct-server migration test, not a pooler assertion.
    if request.node.callspec.params['registry_database'] == 'transaction_pooler':
        pytest.skip('startup options are not part of the pooler contract')
    old = OutreachEngine(registry_database)
    try:
        campaign = old.create_campaign(name='Legacy private data')
        with open_database(registry_database) as admin:
            admin.execute('CREATE SCHEMA control_shadow')
        parts = urlsplit(registry_database)
        options = dict(parse_qsl(parts.query))
        options['options'] = '-csearch_path=control_shadow,public'
        shadow = urlunsplit(parts._replace(query=urlencode(options)))
        with pytest.raises(CrmRoutingError, match='schema'):
            make_registry(shadow, tmp_path)
        assert old.store.get_campaign(campaign)['name'] == 'Legacy private data'
    finally:
        old.close()


def test_lost_control_receipt_cannot_create_a_parallel_customer_generation(registry_database, tmp_path):
    registry = make_registry(registry_database, tmp_path)
    with registry.lease('alpha') as engine:
        campaign = engine.create_campaign(name='Retain actual customer data')
        namespace = engine.store.namespace
    registry.close()
    with open_database(registry_database) as admin:
        admin.execute('DROP TABLE crm_workspace_routing')
    with pytest.raises(CrmRoutingError, match='restore'):
        make_registry(registry_database, tmp_path)
    with open_database(registry_database, namespace=namespace) as original:
        assert original.execute('SELECT name FROM campaigns WHERE id=?', [campaign]).fetchone()['name'] == 'Retain actual customer data'


def test_cached_missing_postgres_book_is_refused_before_yielding_engine(registry_database, tmp_path):
    registry = make_registry(registry_database, tmp_path)
    try:
        with registry.lease('alpha') as engine:
            namespace = engine.store.namespace
        with open_database(registry_database) as admin:
            admin.execute(f'DROP SCHEMA "{namespace}" CASCADE')
        with pytest.raises(CrmRoutingError, match='restore'):
            with registry.lease('alpha'):
                pytest.fail('Missing customer namespace must not yield a cached engine')
    finally:
        registry.close()


def test_cached_postgres_ownership_change_is_refused_before_yielding(registry_database, tmp_path):
    registry = make_registry(registry_database, tmp_path)
    try:
        with registry.lease('alpha') as engine:
            namespace = engine.store.namespace
        with open_database(registry_database, namespace=namespace) as changed:
            changed.execute("UPDATE crm_workspace_identity SET workspace_id='beta'")
        with pytest.raises(CrmRoutingError, match='ownership'):
            with registry.lease('alpha'):
                pass
    finally:
        registry.close()


def test_initialized_empty_postgres_legacy_schema_can_activate(registry_database, tmp_path):
    with OutreachStore(registry_database) as legacy:
        legacy.initialize()
    registry = make_registry(registry_database, tmp_path)
    try:
        with registry.lease('alpha') as engine:
            assert engine.store.list_campaigns()[1] == 0
    finally:
        registry.close()
