"""S-06.01.01: credentials and browser material stay within their workspace."""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.ai.errors import RegistryError
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
from offsetx_apollo_builder.browser.identity import platform
from offsetx_apollo_builder.browser.vault import SessionVault, VaultError, VaultLocked


def registry():
    return ProviderRegistry(Path(__file__).parents[1]/'config/providers.yaml')


def test_nonlocal_workspace_never_inherits_global_provider_key(tmp_path, monkeypatch):
    monkeypatch.setenv('OFFSETX_AI_OPENAI_KEY', 'GLOBAL-LOCAL-ONLY')
    store = WorkspaceAISettingsStore(tmp_path, registry())
    assert store.key_for('local', 'openai') == 'GLOBAL-LOCAL-ONLY'
    assert store.key_for('alice', 'openai') == ''


def test_corrupt_stored_key_cannot_silently_fall_back_to_another_credential(tmp_path, monkeypatch):
    store = WorkspaceAISettingsStore(tmp_path, registry())
    store.set_key('local', 'openai', 'stored')
    store.secret_path.write_bytes(b'corrupt ciphertext')
    monkeypatch.setenv('OFFSETX_AI_OPENAI_KEY', 'DIFFERENT-CREDENTIAL')
    with pytest.raises(RegistryError):
        store.key_for('local', 'openai')


def test_concurrent_workspace_key_writes_cannot_erase_each_other(tmp_path, monkeypatch):
    initial = WorkspaceAISettingsStore(tmp_path, registry())
    initial.set_key('local', 'openai', 'local-seed')
    stores = [WorkspaceAISettingsStore(tmp_path, registry()) for _ in range(2)]
    barrier = threading.Barrier(2)
    for store in stores:
        original = store._write_secrets
        def write(*args, original=original, **kwargs):
            barrier.wait(timeout=5)
            return original(*args, **kwargs)
        monkeypatch.setattr(store, '_write_secrets', write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(s.set_key, workspace, 'openai', value)
                   for s, workspace, value in zip(stores, ('alice','bob'), ('ALICE','BOB'))]
        for future in futures:
            future.result()
    check = WorkspaceAISettingsStore(tmp_path, registry())
    assert check.key_for('alice','openai') == 'ALICE'
    assert check.key_for('bob','openai') == 'BOB'


def test_vault_envelope_cannot_be_relabelled_as_another_workspace(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as module
    monkeypatch.setattr(module, '_keychain_master', lambda create: (None, ''))
    vault = SessionVault(tmp_path, passphrase='test-only-long-passphrase')
    vault.seal('alice','linkedin',{'cookies':[{'name':'li_at','value':'ALICE','domain':'.linkedin.com'}]})
    raw = json.loads(vault._path('alice','linkedin').read_text())
    raw['workspace_id'] = 'bob'
    vault._path('bob','linkedin').write_text(json.dumps(raw))
    with pytest.raises(VaultLocked):
        vault.unseal('bob','linkedin')


def test_capture_refuses_a_foreign_workspace_before_touching_browser(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as module
    monkeypatch.setattr(module, '_keychain_master', lambda create: (None, ''))
    vault = SessionVault(tmp_path, passphrase='test-only-long-passphrase')
    calls=[]
    class Connection:
        async def send(self, method, params=None, **kwargs):
            calls.append((method,params))
            return {'cookies':[{'name':'li_at','value':'ALICE','domain':'.linkedin.com'}]}
    page=SimpleNamespace(connection=Connection(),workspace_id='alice',browser_context_id='context-alice',session_id='tab-a')
    with pytest.raises(VaultError):
        asyncio.run(vault.capture(page,platform('linkedin'),'bob'))
    assert calls == []


@pytest.mark.parametrize('workspace', ['../alice','alice::openai','Alice','a/b',''])
def test_ambiguous_workspace_identifiers_are_refused(tmp_path, workspace):
    store=WorkspaceAISettingsStore(tmp_path,registry())
    with pytest.raises(ValueError):
        store.set_key(workspace,'openai','value')


def test_bound_store_rejects_another_workspace_and_namespaced_env_is_distinct(tmp_path,monkeypatch):
    from offsetx_apollo_builder.workspaces import workspace_env
    bound=WorkspaceAISettingsStore(tmp_path,registry(),workspace_id='alice')
    monkeypatch.setenv(workspace_env('alice','AI_OPENAI_KEY'),'ALICE-ENV')
    monkeypatch.setenv(workspace_env('bob','AI_OPENAI_KEY'),'BOB-ENV')
    assert bound.key_for('alice','openai')=='ALICE-ENV'
    with pytest.raises(RegistryError):
        bound.key_for('bob','openai')
    with pytest.raises(RegistryError):
        bound.save('bob',{'positioning_line':'escape'})


def test_broker_rejects_foreign_settings_before_credential_resolution(tmp_path):
    from offsetx_apollo_builder.ai.broker import EgressBroker, WorkspaceEgressSettings
    from offsetx_apollo_builder.ai.payload import EgressRequest
    from offsetx_apollo_builder.ai.tiers import DataClass
    from offsetx_apollo_builder.ai.errors import PolicyViolation
    calls=[]
    broker=EgressBroker(registry=registry(),credential_resolver=lambda p:calls.append(p),workspace_id='alice')
    with pytest.raises(PolicyViolation,match='workspace'):
        broker.plan(EgressRequest(task_type='write_code',data_class=DataClass.PUBLIC),WorkspaceEgressSettings(workspace_id='bob'))
    assert calls==[]


def test_legacy_key_and_settings_migration_is_explicit_scoped_and_rollback_safe(tmp_path):
    store=WorkspaceAISettingsStore(tmp_path,registry())
    # Construct the documented old combined format under the owner's local root.
    store._write_secrets({'alice::openai':'ALICE','bob::openai':'BOB'})
    store.settings_path.write_text(json.dumps({'alice':{'workspace_id':'alice','providers':{},'positioning_line':'A'},
                                              'bob':{'workspace_id':'bob','providers':{},'positioning_line':'B'}}))
    original=store.secret_path.read_bytes()
    assert store.key_for('alice','openai')==''
    report=store.migrate_legacy_workspace('alice')
    assert report['providers_migrated']==1
    assert store.key_for('alice','openai')=='ALICE'
    assert store.key_for('bob','openai')==''
    assert store.raw('alice')['positioning_line']=='A'
    assert store.secret_path.read_bytes()==original
    with pytest.raises(RegistryError,match='already exists'):
        store.migrate_legacy_workspace('alice')
    assert 'ALICE' not in str(report)


def test_legacy_provider_paths_do_not_inherit_other_workspace_environment(tmp_path, monkeypatch):
    from offsetx_apollo_builder.outreach import provider_profiles as profiles
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.workspaces import workspace_env
    monkeypatch.setenv('OPENAI_API_KEY', 'OWNER-ONLY')
    own = workspace_env('alice', 'AI_OPENAI_KEY')
    monkeypatch.setenv(own, 'ALICE')
    monkeypatch.setenv(workspace_env('bob', 'AI_OPENAI_KEY'), 'BOB')
    monkeypatch.setenv(workspace_env('alice', 'SESSION_SECRET'), 'SESSION')
    seen = []
    monkeypatch.setattr(profiles, 'create_provider', lambda config, **kw: seen.append(kw.get('environ')) or object())
    profiles.create_guarded_provider(ProviderConfig(provider_type='openai'), workspace_id='alice')
    store = profiles.ProviderProfileStore(tmp_path, workspace_id='alice')
    store._provider({'id':'p', 'provider_type':'openai'}, {})
    assert seen == [{own:'ALICE'}, {own:'ALICE'}]


def test_nonlocal_provider_cannot_execute_a_host_command(tmp_path):
    from offsetx_apollo_builder.outreach.provider_profiles import ProviderProfileStore, create_guarded_provider
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.outreach.providers import ProviderError
    with pytest.raises((ValueError, ProviderError), match='local'):
        ProviderProfileStore(tmp_path, workspace_id='alice').upsert({'provider_type':'local_command','name':'escape'})
    with pytest.raises(ProviderError, match='local'):
        create_guarded_provider(ProviderConfig(provider_type='local_command'), workspace_id='alice')


def test_scoped_app_settings_cannot_be_relabelled(tmp_path):
    from offsetx_apollo_builder.api.config import AppSettings
    settings = AppSettings(project_root=tmp_path, database_path=tmp_path/'crm.db', data_dir=tmp_path/'data', export_dir=tmp_path/'exports', frontend_dist=tmp_path/'frontend', workspace_id='alice').scoped()
    settings.workspace_id = 'bob'
    with pytest.raises(ValueError, match='identity'):
        settings.scoped()


def test_concurrent_processes_preserve_same_workspace_provider_keys(tmp_path):
    import subprocess
    import sys
    script = '''
import sys
from pathlib import Path
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
from offsetx_apollo_builder.ai.registry import ProviderRegistry
store=WorkspaceAISettingsStore(Path(sys.argv[1]),ProviderRegistry(Path('config/providers.yaml')))
for n in range(8):
    store.set_key('alice',sys.argv[2],sys.argv[2]+'-value')
'''
    processes=[subprocess.Popen([sys.executable,'-c',script,str(tmp_path),provider])
               for provider in ('openai','anthropic','gemini','mistral')]
    for process in processes:
        assert process.wait(timeout=30)==0
    store=WorkspaceAISettingsStore(tmp_path,registry())
    for provider in ('openai','anthropic','gemini','mistral'):
        assert store.key_for('alice',provider)==provider+'-value'


def test_symlinked_workspace_secret_is_refused(tmp_path):
    from offsetx_apollo_builder.workspaces import workspace_directory
    store=WorkspaceAISettingsStore(tmp_path,registry())
    own=workspace_directory(tmp_path,'alice')
    own.mkdir(parents=True)
    target=tmp_path/'owner-keys'
    target.write_bytes(b'owner-secret')
    (own/'ai_provider_keys.enc').symlink_to(target)
    with pytest.raises(RegistryError):
        store.key_for('alice','openai')
    assert target.read_bytes()==b'owner-secret'


def test_key_migration_failure_leaves_source_and_destination_retryable(tmp_path, monkeypatch):
    from offsetx_apollo_builder.ai import workspace as module
    store=WorkspaceAISettingsStore(tmp_path,registry())
    store._write_secrets({'alice::openai':'ALICE'})
    store.settings_path.write_text(json.dumps({'alice':{'workspace_id':'alice','providers':{}}}))
    before=store.secret_path.read_bytes()
    original=module._atomic_json
    def fail(*a, **kw):
        raise OSError('test migration disk failure')
    monkeypatch.setattr(module,'_atomic_json',fail)
    with pytest.raises(OSError,match='disk failure'):
        store.migrate_legacy_workspace('alice')
    assert store.secret_path.read_bytes()==before
    assert not (tmp_path/'workspaces/alice/ai_provider_keys.enc').exists()
    monkeypatch.setattr(module,'_atomic_json',original)
    assert store.migrate_legacy_workspace('alice')['providers_migrated']==1


def test_workspace_cookie_binding_cannot_enable_an_authenticator_with_no_secret():
    from offsetx_apollo_builder.api.auth import DemoSessionAuth
    auth=DemoSessionAuth(username='owner',password='test-only-password',session_secret='',session_hours=1,audience='alice')
    assert not auth.enabled
