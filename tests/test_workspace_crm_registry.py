"""A leased native factory binds whole CRM books without query rewriting."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import pytest
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.outreach.workspace_registry import WorkspaceCrmRegistry, CrmRoutingError
from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock, WorkspaceBusy

pytestmark = pytest.mark.crm_sqlite_only("Exercises local SQLite namespace topology; PostgreSQL registry coverage is separate")


def registry_for(tmp_path, **kwargs):
    return WorkspaceCrmRegistry(root_target=str(tmp_path/'data'/'outreach.db'), data_dir=tmp_path/'data',
        known_workspaces=lambda: {'local', 'alpha', 'beta'}, **kwargs)


def test_fresh_registry_isolates_equal_emails_private_campaigns_and_memory(tmp_path):
    registry = registry_for(tmp_path)
    try:
        ids = {}
        for workspace in ('alpha', 'beta'):
            with registry.lease(workspace) as engine:
                campaign = engine.create_campaign(name='PRIVATE '+workspace)
                ids[workspace] = campaign
                engine.store.create_manual_campaign_contact(campaign, ContactInput(
                    full_name='Anita Rao', email='same@example.com', company='Example Exports', category='CBAM'))
                engine.email_expert.memory.add_manual(content='PRIVATE '+workspace+' memory')
        with registry.lease('beta') as engine:
            assert [row['name'] for row in engine.store.list_campaigns()[0]] == ['PRIVATE beta']
            with pytest.raises(KeyError):
                engine.store.get_campaign(ids['alpha'])
            assert engine.store.search_memory_items('', workspace_id='alpha')[1] == 0
        with sqlite3.connect(tmp_path/'data'/'outreach.db') as old:
            with pytest.raises(sqlite3.DatabaseError):
                old.execute('SELECT * FROM campaigns').fetchall()
    finally:
        registry.close()


def test_initialized_but_empty_legacy_schema_can_activate_without_assignment(tmp_path):
    root = tmp_path/'data'/'outreach.db'
    with OutreachStore(root) as legacy:
        legacy.initialize()
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha') as engine:
            assert engine.store.list_campaigns()[1] == 0
    finally:
        registry.close()


def test_existing_legacy_rows_require_an_explicit_manifest_without_assignment(tmp_path):
    root = tmp_path/'data'/'outreach.db'
    old = OutreachEngine(root)
    try:
        campaign = old.create_campaign(name='Keep legacy ownership undecided')
        with pytest.raises(CrmRoutingError, match='manifest'):
            registry_for(tmp_path)
        assert old.store.get_campaign(campaign)['name'] == 'Keep legacy ownership undecided'
        assert not Path(str(root)+'.workspaces').exists()
    finally:
        old.close()


def test_idle_cache_eviction_reopens_the_same_durable_workspace(tmp_path):
    registry = registry_for(tmp_path, max_cached=1)
    try:
        with registry.lease('alpha') as first:
            campaign = first.create_campaign(name='Alpha survives eviction')
        with registry.lease('beta') as second:
            assert second is not first and second.store.list_campaigns()[1] == 0
        with registry.lease('alpha') as reopened:
            assert reopened is not first
            assert reopened.store.get_campaign(campaign)['name'] == 'Alpha survives eviction'
    finally:
        registry.close()


def test_active_leases_prevent_eviction_and_unsafe_shutdown(tmp_path):
    registry = registry_for(tmp_path, max_cached=1)
    try:
        with registry.lease('alpha') as engine:
            campaign = engine.create_campaign(name='In-flight work')
            with pytest.raises(CrmRoutingError, match='busy'):
                with registry.lease('beta'):
                    pass
            with pytest.raises(CrmRoutingError, match='active'):
                registry.close()
            assert engine.store.get_campaign(campaign)
    finally:
        registry.close()
    with pytest.raises(CrmRoutingError, match='closed'):
        with registry.lease('alpha'):
            pass


def test_restart_retains_ready_book_and_refuses_silent_recreation(tmp_path):
    first = registry_for(tmp_path)
    with first.lease('alpha') as engine:
        campaign = engine.create_campaign(name='Persistent alpha')
        target = engine.store.path
    first.close()
    second = registry_for(tmp_path)
    with second.lease('alpha') as engine:
        assert engine.store.get_campaign(campaign)['name'] == 'Persistent alpha'
    second.close()
    target.unlink()
    third = registry_for(tmp_path)
    try:
        with pytest.raises(CrmRoutingError, match='restore'):
            with third.lease('alpha'):
                pass
        assert not target.exists()
    finally:
        third.close()


def test_request_cannot_choose_unknown_or_malformed_workspace_storage(tmp_path):
    registry = registry_for(tmp_path)
    try:
        for workspace in ('../alpha', 'public', 'missing', 'alpha;DROP TABLE campaigns', ''):
            with pytest.raises(CrmRoutingError):
                with registry.lease(workspace):
                    pass
    finally:
        registry.close()


def test_two_process_style_registries_converge_on_one_customer_book(tmp_path):
    registries = [registry_for(tmp_path), registry_for(tmp_path)]
    try:
        def create(index):
            with registries[index].lease('alpha') as engine:
                return engine.create_campaign(name='Replica '+str(index))
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(create, range(2)))
        assert len(set(ids)) == 2
        with registries[0].lease('alpha') as engine:
            assert {row['name'] for row in engine.store.list_campaigns()[0]} == {'Replica 0', 'Replica 1'}
    finally:
        for registry in registries:
            registry.close()


def test_closed_registry_does_not_call_a_retired_authentication_store(tmp_path):
    calls = []
    registry = WorkspaceCrmRegistry(root_target=str(tmp_path/'outreach.db'), data_dir=tmp_path,
        known_workspaces=lambda: calls.append('authentication') or {'alpha'})
    registry.close()
    with pytest.raises(CrmRoutingError, match='closed'):
        with registry.lease('alpha'):
            pass
    assert calls == []


def test_cached_file_replacement_is_refused_before_customer_reads(tmp_path):
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha') as engine:
            engine.create_campaign(name='Original private data')
            target = engine.store.path
        target.rename(target.with_suffix('.old'))
        target.touch()
        with pytest.raises(CrmRoutingError, match='replaced'):
            with registry.lease('alpha'):
                pass
    finally:
        registry.close()


def test_ready_book_with_foreign_ownership_is_refused_after_restart(tmp_path):
    registry = registry_for(tmp_path)
    with registry.lease('alpha') as engine:
        target = engine.store.path
    registry.close()
    with sqlite3.connect(target) as changed:
        changed.execute("UPDATE crm_workspace_identity SET workspace_id='beta'")
    restarted = registry_for(tmp_path)
    try:
        with pytest.raises(CrmRoutingError, match='ownership'):
            with restarted.lease('alpha'):
                pass
    finally:
        restarted.close()


def test_shutdown_closes_every_book_even_when_one_close_fails(tmp_path, monkeypatch):
    registry = registry_for(tmp_path)
    with registry.lease('alpha') as alpha, registry.lease('beta') as beta:
        pass
    closed = []
    for workspace, engine in [('alpha', alpha), ('beta', beta)]:
        original = engine.close
        def close(original=original, workspace=workspace):
            original()
            closed.append(workspace)
            if workspace == 'alpha':
                raise OSError('simulated failed shutdown')
        monkeypatch.setattr(engine, 'close', close)
    with pytest.raises(CrmRoutingError, match='close'):
        registry.close()
    assert closed == ['alpha', 'beta']


@pytest.mark.parametrize('damage', ['remove_root', 'empty_root', 'remove_receipt'])
def test_missing_control_metadata_never_hides_existing_customer_books(tmp_path, damage):
    registry = registry_for(tmp_path)
    with registry.lease('alpha') as engine:
        engine.create_campaign(name='Must remain recoverable')
        book = engine.store.path
    registry.close()
    root = tmp_path/'data'/'outreach.db'
    if damage == 'remove_root':
        root.unlink()
    elif damage == 'empty_root':
        root.write_bytes(b'')
    else:
        with sqlite3.connect(root) as changed:
            changed.execute('DELETE FROM crm_workspace_routing')
    with pytest.raises(CrmRoutingError, match='restore'):
        registry_for(tmp_path)
    with sqlite3.connect(book) as customer:
        assert customer.execute('SELECT name FROM campaigns').fetchone()[0] == 'Must remain recoverable'
    assert len(list(Path(str(root)+'.workspaces').iterdir())) == 1


def test_cached_ownership_change_is_refused_without_waiting_for_restart(tmp_path):
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha') as engine:
            engine.create_campaign(name='Alpha customer data')
            target = engine.store.path
        with sqlite3.connect(target) as changed:
            changed.execute("UPDATE crm_workspace_identity SET workspace_id='beta'")
        with pytest.raises(CrmRoutingError, match='ownership'):
            with registry.lease('alpha'):
                pass
    finally:
        registry.close()


@pytest.mark.parametrize('replace', [False, True])
def test_live_control_file_loss_is_refused_before_yielding(tmp_path, replace):
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha') as engine:
            engine.create_campaign(name='Customer under original routing')
        root = tmp_path/'data'/'outreach.db'
        root.rename(root.with_suffix('.old'))
        if replace:
            root.touch()
        with pytest.raises(CrmRoutingError, match='restore'):
            with registry.lease('alpha'):
                pass
    finally:
        registry.close()


def test_external_sqlite_layout_is_refused_before_creating_an_incomplete_backup_topology(tmp_path):
    external = tmp_path/'external.db'
    with pytest.raises(CrmRoutingError, match='data directory'):
        WorkspaceCrmRegistry(root_target=str(external), data_dir=tmp_path/'data', known_workspaces=lambda: {'alpha'})
    assert not external.exists()


def test_new_control_and_customer_files_are_private(tmp_path):
    if __import__('os').name == 'nt':
        pytest.skip('POSIX file mode acceptance; Windows uses directory ACLs')
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha') as engine:
            assert engine.store.path.stat().st_mode & 0o777 == 0o600
        assert (tmp_path/'data'/'outreach.db').stat().st_mode & 0o777 == 0o600
    finally:
        registry.close()


def test_constructor_cannot_open_databases_during_exclusive_recovery(tmp_path):
    data = tmp_path/'data'
    constructed = None
    try:
        with WorkspaceLock(data, exclusive=True):
            with pytest.raises(WorkspaceBusy):
                constructed = registry_for(tmp_path)
        assert not data.exists()
        assert not (data/'outreach.db').exists()
    finally:
        if constructed:
            constructed.close()


def test_runtime_can_pass_its_existing_startup_lease_without_nested_locking(tmp_path):
    data = tmp_path/'data'
    with WorkspaceLock(data, exclusive=True) as startup:
        registry = registry_for(tmp_path, startup_lease=startup)
    try:
        with registry.lease('alpha') as engine:
            assert engine.create_campaign(name='Started under fenced recovery')
    finally:
        registry.close()


def test_expired_or_foreign_startup_lease_cannot_bypass_recovery(tmp_path):
    foreign = WorkspaceLock(tmp_path/'other', exclusive=True)
    with foreign:
        with pytest.raises(CrmRoutingError, match='lease'):
            registry_for(tmp_path, startup_lease=foreign)
    with pytest.raises(CrmRoutingError, match='lease'):
        registry_for(tmp_path, startup_lease=foreign)
    assert not (tmp_path/'data'/'outreach.db').exists()


def test_pending_restore_journal_refuses_constructor_and_live_leases(tmp_path):
    registry = registry_for(tmp_path)
    try:
        with registry.lease('alpha'):
            pass
        (tmp_path/'.data.restore-journal.json').write_text('{}')
        with pytest.raises(CrmRoutingError, match='restore'):
            with registry.lease('alpha'):
                pass
        with pytest.raises(CrmRoutingError, match='restore'):
            registry_for(tmp_path)
    finally:
        registry.close()


def test_constructor_holds_recovery_fence_through_database_initialization(tmp_path, monkeypatch):
    import threading
    entered, finish = threading.Event(), threading.Event()
    original = WorkspaceCrmRegistry._open
    def paused(self, *args):
        entered.set()
        assert finish.wait(10), 'test did not release initialization'
        return original(self, *args)
    monkeypatch.setattr(WorkspaceCrmRegistry, '_open', paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(registry_for, tmp_path)
        try:
            assert entered.wait(10)
            with pytest.raises(WorkspaceBusy):
                with WorkspaceLock(tmp_path/'data', exclusive=True):
                    pass
        finally:
            finish.set()
        future.result(timeout=10).close()


def test_recovery_fence_precedes_known_workspace_database_access(tmp_path):
    calls = []
    registry = WorkspaceCrmRegistry(root_target=str(tmp_path/'outreach.db'), data_dir=tmp_path,
        known_workspaces=lambda: calls.append('authentication') or {'alpha'})
    try:
        with WorkspaceLock(tmp_path, exclusive=True):
            with pytest.raises(WorkspaceBusy):
                with registry.lease('alpha'):
                    pass
        assert calls == []
    finally:
        registry.close()


def test_ready_book_missing_a_customer_table_is_not_silently_reinitialized(tmp_path):
    registry = registry_for(tmp_path)
    with registry.lease('alpha') as engine:
        target = engine.store.path
        template = engine.store.list_templates()[0][0]
        template.update(subject_template='Private customer wording')
        engine.store.upsert_template(template)
    registry.close()
    with sqlite3.connect(target) as damaged:
        damaged.execute('DROP TABLE email_templates')
    restarted = registry_for(tmp_path)
    try:
        with pytest.raises(CrmRoutingError, match='restore'):
            with restarted.lease('alpha'):
                pass
        with sqlite3.connect(target) as damaged:
            assert not damaged.execute("SELECT 1 FROM sqlite_master WHERE name='email_templates'").fetchone()
    finally:
        restarted.close()
