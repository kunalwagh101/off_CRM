"""A command's explicit import/skip choice cannot change a foreign installation."""
import uuid

import pytest
from cryptography.fernet import Fernet
from offsetx_apollo_builder import db_cli
from offsetx_apollo_builder.ai.context import ContextLayer
from offsetx_apollo_builder.db.hosted import HostedStorage, HostedStorageError
from offsetx_apollo_builder.outreach.engine import OutreachEngine

OWNER = str(uuid.UUID(int=1))
FOREIGN = str(uuid.UUID(int=2))


@pytest.fixture
def isolated_install_database():
    # Ownership is physical-database wide. Schemas cannot isolate independent
    # install tests or simultaneous pytest/review commands anymore.
    import os
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    base = os.getenv('OFF_CRM_TEST_POSTGRES_URL', '')
    if not base:
        pytest.skip('requires disposable PostgreSQL CREATEDB test role')
    import psycopg
    from psycopg import sql
    name = 'offcrm_install_'+uuid.uuid4().hex
    parts = urlsplit(base)
    query = urlencode([(key,value) for key,value in parse_qsl(parts.query) if key != 'options'])
    target = urlunsplit(parts._replace(path='/'+name, query=query))
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        yield target
    finally:
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@pytest.fixture(params=['sqlite', 'postgres'])
def owned_target(request, tmp_path, monkeypatch):
    target = request.getfixturevalue('isolated_install_database') if request.param == 'postgres' else str(tmp_path/'hosted.db')
    key = Fernet.generate_key().decode()
    store = HostedStorage(target, key)
    store.claim_install(OWNER)
    store.write('customer-canary', 'must remain exact')
    root = tmp_path/'source'
    root.mkdir()
    (root/'ai_quota.json').write_text('{"local":{"calls":7}}')
    (root/'automation.json').write_text('{"enabled":true,"interval_seconds":30}')
    context = ContextLayer(root/'ai_context.db')
    context.start_task(workspace_id='alpha', title='Private retained plan')
    context.close()
    engine = OutreachEngine(root/'crm.db')
    engine.create_campaign(name='Private retained campaign')
    engine.close()
    monkeypatch.setenv('OFFSETX_DATABASE_URL', target)
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', key)
    monkeypatch.setenv('OFFSETX_INSTALL_ID', FOREIGN)
    monkeypatch.setenv('OFFSETX_DATA_DIR', str(root))
    try:
        yield store, root, tmp_path/'archive'
    finally:
        store.close()


def snapshots(store, root):
    rows = [dict(row) for row in store.connection.execute('SELECT * FROM offcrm_documents ORDER BY name').fetchall()]
    files = {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file() and path.relative_to(root).parts[0] != 'logs'}
    return rows, files


@pytest.mark.parametrize('command', ['import-local', 'import-crm', 'import-timers', 'import-context'])
@pytest.mark.parametrize('choice', ['--yes', '--skip'])
def test_actual_import_commands_refuse_foreign_install_before_archive_or_mutation(owned_target, command, choice):
    store, root, archive = owned_target
    before = snapshots(store, root)
    args = [command, choice]
    if command == 'import-local':
        args += ['--data-dir', str(root)]
    elif command == 'import-crm':
        args += ['--database', str(root/'crm.db')]
    elif command == 'import-timers':
        args += ['--data-dir', str(root), '--archive-dir', str(archive)]
    else:
        args += ['--source', str(root/'ai_context.db'), '--archive', str(archive/'context.db')]
    assert db_cli.main(args) == 2
    assert snapshots(store, root) == before
    assert not archive.exists()


@pytest.mark.parametrize('kind', ['local', 'crm', 'timers', 'context'])
@pytest.mark.parametrize('skip', [False, True])
def test_direct_import_helpers_cannot_bypass_the_cli_identity_guard(owned_target, kind, skip):
    store, root, archive = owned_target
    before = snapshots(store, root)
    with pytest.raises(HostedStorageError, match='another install'):
        if kind == 'local':
            from offsetx_apollo_builder.hosted_import import import_local, skip_local
            (skip_local if skip else import_local)(store, root)
        elif kind == 'crm':
            from offsetx_apollo_builder.outreach.store_copy import import_crm, skip_crm
            skip_crm(store, root/'crm.db') if skip else import_crm(store, root/'crm.db', store.target)
        elif kind == 'timers':
            from offsetx_apollo_builder.db.timer_import import migrate_timers
            migrate_timers(store, root, archive, import_settings=not skip)
        else:
            from offsetx_apollo_builder.db.context_import import import_context
            import_context(root/'ai_context.db', store.target, archive/'context.db', skip=skip)
    assert snapshots(store, root) == before
    assert not archive.exists()


@pytest.mark.parametrize('identity', ['', 'invalid', str(uuid.UUID(int=0))])
@pytest.mark.parametrize('command', ['import-local', 'import-crm', 'import-timers', 'import-context'])
@pytest.mark.parametrize('choice', ['--yes', '--skip'])
def test_missing_or_invalid_identity_cannot_make_an_import_decision(owned_target, monkeypatch, identity, command, choice):
    store, root, archive = owned_target
    monkeypatch.setenv('OFFSETX_INSTALL_ID', identity)
    before = snapshots(store, root)
    arguments = {'import-local':['--data-dir',str(root)], 'import-crm':['--database',str(root/'crm.db')],
        'import-timers':['--data-dir',str(root),'--archive-dir',str(archive)],
        'import-context':['--source',str(root/'ai_context.db'),'--archive',str(archive/'context.db')]}
    assert db_cli.main([command, choice, *arguments[command]]) == 2
    assert snapshots(store, root) == before and not archive.exists()


@pytest.mark.parametrize('stored', ['not-a-uuid', str(uuid.UUID(int=0)), FOREIGN])
@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_invalid_or_foreign_stored_owner_refuses_without_even_initializing_key_check(tmp_path, request, backend, stored):
    target = request.getfixturevalue('isolated_install_database') if backend == 'postgres' else str(tmp_path/'hosted.db')
    store = HostedStorage(target, Fernet.generate_key().decode())
    try:
        store.write('install.identity.v1', stored)
        store.write('customer-canary', 'must remain exact')
        before = [dict(row) for row in store.connection.execute('SELECT * FROM offcrm_documents ORDER BY name').fetchall()]
        with pytest.raises(HostedStorageError, match='another install'):
            store.claim_install(OWNER)
        assert [dict(row) for row in store.connection.execute('SELECT * FROM offcrm_documents ORDER BY name').fetchall()] == before
    finally:
        store.close()


def test_lost_key_recovery_refuses_foreign_install_and_preserves_keys(owned_target):
    from offsetx_apollo_builder.db.hosted import PROVIDER_KEYS
    store, root, archive = owned_target
    store.write(PROVIDER_KEYS, store.fernet.encrypt(b'{"fixture":"private"}').decode())
    before = snapshots(store, root)
    assert db_cli.main(['forget-provider-keys', '--target',store.target,'--yes']) == 2
    assert snapshots(store, root) == before


def test_same_install_can_recover_lost_key_without_having_the_old_key(owned_target, monkeypatch):
    from offsetx_apollo_builder.db.hosted import PROVIDER_KEYS, KEY_CHECK
    store, root, archive = owned_target
    store.write(PROVIDER_KEYS, store.fernet.encrypt(b'{"fixture":"private"}').decode())
    monkeypatch.setenv('OFFSETX_INSTALL_ID', OWNER)
    monkeypatch.delenv('OFFSETX_SECRETS_KEY')
    assert db_cli.main(['forget-provider-keys', '--target',store.target,'--yes']) == 0
    assert store.read(PROVIDER_KEYS) is None and store.read(KEY_CHECK) is None
    assert store.read('install.identity.v1') == OWNER
    assert store.read('customer-canary') == 'must remain exact'
    replacement = HostedStorage(store.target, Fernet.generate_key().decode())
    try:
        replacement.claim_install(OWNER)
    finally:
        replacement.close()


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_first_claim_race_is_atomic_on_actual_backend(tmp_path, request, backend):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    target = request.getfixturevalue('isolated_install_database') if backend == 'postgres' else str(tmp_path/'hosted.db')
    key = Fernet.generate_key().decode()
    stores = [HostedStorage(target, key) for _ in range(2)]
    for store in stores:
        store.probe()
    barrier = threading.Barrier(2)
    def claim(pair):
        store, identity = pair
        barrier.wait(timeout=5)
        try:
            store.claim_install(identity)
            return identity
        except HostedStorageError:
            return None
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, zip(stores, (OWNER, FOREIGN))))
        winners = [identity for identity in results if identity]
        assert len(winners) == 1
        assert stores[0].read('install.identity.v1') == winners[0]
        assert stores[1].read('install.identity.v1') == winners[0]
    finally:
        for store in stores:
            store.close()


@pytest.mark.parametrize('kind', ['content', 'companions'])
def test_previously_guarded_imports_cannot_write_key_check_after_owner_key_recovery(owned_target, monkeypatch, kind):
    store, root, archive = owned_target
    with monkeypatch.context() as owner:
        owner.setenv('OFFSETX_INSTALL_ID', OWNER)
        store.forget_provider_keys()
    if kind == 'content':
        from offsetx_apollo_builder.imagery.store import ImageStore
        content = ImageStore(root/'imagery.db', assets_dir=root/'assets')
        content.create_brief(campaign_id='fixture', brief='Private retained image', workspace_id='alpha')
        content.close()
    else:
        from offsetx_apollo_builder.ai.tools import ToolRegistry
        from offsetx_apollo_builder.agent.companions import CompanionRegistry
        tools = ToolRegistry(root/'tools.db')
        profiles = CompanionRegistry(root, tools=tools, memory_backend=None)
        profiles.create(workspace_id='alpha', name='Preserved', instructions='Private instructions')
        profiles.close()
        tools.close()
    before = snapshots(store, root)
    foreign = HostedStorage(store.target, Fernet.generate_key().decode())
    try:
        with pytest.raises(HostedStorageError, match='another install'):
            if kind == 'content':
                from offsetx_apollo_builder.db.content_import import import_content
                import_content(root/'imagery.db', foreign, archive/'content.db', kind='imagery')
            else:
                from offsetx_apollo_builder.db.companion_import import import_companions
                import_companions(root/'tools.db', foreign, archive/'profiles.db')
        assert snapshots(store, root) == before
        assert not archive.exists()
    finally:
        foreign.close()


@pytest.mark.parametrize("concurrent", [False, True])
def test_distinct_postgres_schemas_do_not_let_independent_installs_share_database(isolated_install_database, concurrent):
    import psycopg
    from psycopg import sql
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    extra = 'foreign_install_'+uuid.uuid4().hex[:16]
    parts = urlsplit(isolated_install_database)
    query = [(k,v) for k,v in parse_qsl(parts.query) if k != 'options']
    second_target = urlunsplit(parts._replace(query=urlencode([*query,('options','-csearch_path='+extra)])))
    key = Fernet.generate_key().decode()
    first = HostedStorage(isolated_install_database, key)
    second = HostedStorage(second_target, key)
    try:
        with psycopg.connect(isolated_install_database, autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(extra)))
        if concurrent:
            import threading
            from concurrent.futures import ThreadPoolExecutor
            for storage in (first,second):
                storage.probe()
            barrier = threading.Barrier(2)
            def claim(pair):
                storage, identity = pair
                barrier.wait(timeout=5)
                try:
                    storage.claim_install(identity)
                    return identity
                except HostedStorageError:
                    return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(claim, ((first,OWNER),(second,FOREIGN))))
            assert sum(bool(item) for item in results) == 1
            winner = next(item for item in results if item)
            successful, refused = (first,second) if results[0] else (second,first)
        else:
            first.claim_install(OWNER)
            with pytest.raises(HostedStorageError, match='another install'):
                second.claim_install(FOREIGN)
            successful, refused, winner = first, second, OWNER
        assert successful.read('install.identity.v1') == winner
        assert refused.read('install.identity.v1') is None
        assert refused.read('secrets_key_check') is None
        # Distinct namespaces are valid for the same logical install.
        refused.claim_install(winner)
        assert refused.read('install.identity.v1') == winner
    finally:
        first.close()
        second.close()
        with psycopg.connect(isolated_install_database, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(extra)))


def test_row_security_on_claim_table_is_refused_even_for_existing_owner(isolated_install_database):
    store = HostedStorage(isolated_install_database, Fernet.generate_key().decode())
    try:
        store.claim_install(OWNER)
        store.connection.execute('ALTER TABLE offcrm_documents ENABLE ROW LEVEL SECURITY')
        with pytest.raises(HostedStorageError, match='row security'):
            store.claim_install(OWNER)
    finally:
        store.close()


def test_unsupported_current_claim_view_is_rejected_before_evaluating_it(isolated_install_database):
    store = HostedStorage(isolated_install_database, Fernet.generate_key().decode())
    try:
        store.claim_install(OWNER)
        db = store.connection
        db.execute('CREATE SEQUENCE view_evaluations')
        db.execute("CREATE FUNCTION mark_read(value TEXT) RETURNS TEXT LANGUAGE plpgsql VOLATILE AS $$ BEGIN PERFORM nextval('view_evaluations'); RETURN value; END $$")
        db.execute('ALTER TABLE offcrm_documents RENAME TO saved_documents')
        db.execute('CREATE VIEW offcrm_documents AS SELECT name,mark_read(body) AS body,updated_at FROM saved_documents')
        with pytest.raises(HostedStorageError, match='non-table'):
            store.claim_install(OWNER)
        assert db.execute('SELECT is_called FROM view_evaluations').fetchone()['is_called'] is False
    finally:
        store.close()
