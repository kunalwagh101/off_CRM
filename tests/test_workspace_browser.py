"""Workspace browser lifecycle, migration and protocol-boundary acceptance."""
import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.browser.identity import ConnectionStore, platform
from offsetx_apollo_builder.browser.revoke import disconnect
from offsetx_apollo_builder.browser.session import BrowserSession, find_browser, free_port, open_session
from offsetx_apollo_builder.browser.trace import Trace
from offsetx_apollo_builder.browser.vault import SessionVault, VaultError, VaultLocked


@pytest.fixture
def vault(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as module
    monkeypatch.setattr(module, '_keychain_master', lambda create: (None, ''))
    return SessionVault(tmp_path, passphrase='test-only-workspace-passphrase')


def legacy(vault):
    vault.seal('alice', 'linkedin', {'cookies':[{'name':'li_at','value':'ALICE','domain':'.linkedin.com','path':'/'}]})
    path = vault._path('alice', 'linkedin')
    envelope = json.loads(path.read_text())
    key = vault._account_key(envelope)
    envelope['wrapped_key'] = vault._master_fernet.encrypt(key).decode()
    envelope['version'] = 1
    path.write_text(json.dumps(envelope))
    return path, path.read_bytes()


def test_legacy_migration_requires_owner_verification_and_destroys_owned_backup_on_revoke(vault, tmp_path):
    path, before = legacy(vault)
    with pytest.raises(VaultLocked, match='legacy|Legacy|migration'):
        vault.unseal('alice', 'linkedin')
    with pytest.raises(VaultLocked, match='Verify'):
        vault.migrate_legacy('alice','linkedin',confirmation='')
    assert path.read_bytes() == before
    vault.migrate_legacy('alice','linkedin',confirmation='MIGRATE VERIFIED WORKSPACE SESSION')
    assert vault.unseal('alice','linkedin')['cookies'][0]['value'] == 'ALICE'
    backup = path.with_suffix(path.suffix+'.v1.bak')
    assert json.loads(backup.read_text())['version'] == 1
    calls=[]
    class Connection:
        async def send(self, method, params=None, **kw):
            calls.append((method,kw))
            return {}
    page = SimpleNamespace(connection=Connection(),workspace_id='alice',browser_context_id='ctx',session_id='tab')
    asyncio.run(disconnect(page,platform('linkedin'),ConnectionStore(tmp_path/'connections'),vault,Trace.open(tmp_path/'trace',run_id='workspace-test'), 'alice'))
    assert calls == [('Network.deleteCookies', {'session_id':'tab'})]
    assert not path.exists() and not backup.exists()


def test_failed_legacy_migration_restores_original(vault, monkeypatch):
    path, before = legacy(vault)
    def fail(*a, **kw):
        raise OSError('test disk failure')
    monkeypatch.setattr(vault, 'seal', fail)
    with pytest.raises(OSError, match='disk failure'):
        vault.migrate_legacy('alice','linkedin',confirmation='MIGRATE VERIFIED WORKSPACE SESSION')
    assert json.loads(path.read_text()) == json.loads(before)


def test_cookie_capture_and_restore_use_only_bound_page_session(vault):
    calls=[]
    class Connection:
        async def send(self, method, params=None, **kw):
            calls.append((method,params,kw))
            return {'cookies':[{'name':'li_at','value':'ALICE','domain':'.linkedin.com','path':'/'}]}
    page=SimpleNamespace(connection=Connection(),workspace_id='alice',browser_context_id='alice-context',session_id='alice-tab')
    async def run():
        await vault.capture(page,platform('linkedin'),'alice')
        await vault.restore(page,platform('linkedin'),'alice')
    asyncio.run(run())
    assert [call[0] for call in calls] == ['Network.getCookies','Network.setCookies']
    assert all(call[2] == {'session_id':'alice-tab'} for call in calls)
    page.browser_context_id=''
    with pytest.raises(VaultError, match='isolated'):
        asyncio.run(vault.capture(page,platform('linkedin'),'alice'))
    assert len(calls)==2


def test_workspace_context_allocation_is_concurrent_and_disposal_is_scoped():
    calls=[]
    class Connection:
        async def send(self,method,params=None,**kw):
            calls.append((method,params))
            await asyncio.sleep(0)
            if method == 'Target.createBrowserContext':
                return {'browserContextId':f'context-{len(calls)}'}
            if method == 'Target.createTarget':
                return {'targetId':f'target-{len(calls)}'}
            return {'sessionId':'tab-session'}
    session=BrowserSession(Connection(),'test',0)
    async def run():
        ids=await asyncio.gather(*(session.workspace_context('alice') for _ in range(10)))
        assert len(set(ids))==1
        alice=ids[0]
        bob=await session.workspace_context('bob')
        assert bob!=alice
        await session.new_tab(workspace_id='alice')
        await session.close_workspace('alice')
        assert session.workspace_contexts=={'bob':bob}
        assert ('Target.createTarget',{'url':'about:blank','browserContextId':alice}) in calls
        assert calls[-1]==('Target.disposeBrowserContext',{'browserContextId':alice})
    asyncio.run(run())
    assert sum(method=='Target.createBrowserContext' for method,_ in calls)==2


@pytest.mark.skipif(not find_browser(), reason='Chrome is not installed')
def test_real_chrome_workspace_cookies_are_isolated_and_restore_after_context_restart(vault, tmp_path):
    async def run():
        flags=('--no-sandbox',) if os.geteuid()==0 else ()
        session=await open_session(profile_dir=tmp_path/'chrome',port=free_port(),headless=True,extra_flags=flags)
        try:
            alice=await session.workspace_page('alice')
            bob=await session.workspace_page('bob')
            await session.connection.send('Network.setCookies',{'cookies':[{'name':'li_at','value':'ALICE','domain':'.linkedin.com','path':'/','secure':True}]},session_id=alice.session_id)
            await vault.capture(alice,platform('linkedin'),'alice')
            other=await session.connection.send('Network.getCookies',{'urls':['https://www.linkedin.com/']},session_id=bob.session_id)
            assert other['cookies']==[]
            await session.close_workspace('alice')
            alice=await session.workspace_page('alice')
            await vault.restore(alice,platform('linkedin'),'alice')
            own=await session.connection.send('Network.getCookies',{'urls':['https://www.linkedin.com/']},session_id=alice.session_id)
            assert [(c['name'],c['value']) for c in own['cookies']]==[('li_at','ALICE')]
            other=await session.connection.send('Network.getCookies',{'urls':['https://www.linkedin.com/']},session_id=bob.session_id)
            assert other['cookies']==[]
        finally:
            await session.close(quit_browser=True)
    asyncio.run(run())


def test_parallel_workspaces_share_one_durable_os_keychain_master(tmp_path, monkeypatch):
    """Separate vault directories must not race to replace a shared OS master."""
    from concurrent.futures import ThreadPoolExecutor
    import secrets
    import threading
    import time
    from offsetx_apollo_builder.browser import vault as module
    stored=[None]
    def backend(create):
        if stored[0] is not None:
            return stored[0], 'test-os-keychain'
        if not create:
            return None, ''
        key=secrets.token_bytes(32)
        time.sleep(0.05)
        stored[0]=key
        return key, 'test-os-keychain'
    for name in ('_linux_keychain','_macos_keychain','_windows_dpapi'):
        monkeypatch.setattr(module,name,backend)
    monkeypatch.setattr(module,'_keychain_lock_directory',lambda:tmp_path/'os-keychain-lock',raising=False)
    start=threading.Barrier(2)
    def create(identity):
        start.wait(timeout=5)
        vault=SessionVault(tmp_path/identity)
        vault.seal(identity,'linkedin',{'cookies':[{'name':'li_at','value':identity,'domain':'.linkedin.com'}]})
        return vault
    with ThreadPoolExecutor(max_workers=2) as pool:
        vaults=list(pool.map(create,['alice','bob']))
    # A process restart reads the OS store, not either process's old root bytes.
    for identity in ('alice','bob'):
        reopened=SessionVault(tmp_path/identity)
        assert reopened.unseal(identity,'linkedin')['cookies'][0]['value']==identity


def test_unavailable_common_keychain_lock_never_creates_a_master(monkeypatch):
    from offsetx_apollo_builder.browser import vault as module
    calls=[]
    monkeypatch.setattr(module,'_keychain_backend',lambda create:calls.append(create) or (None,''))
    def unavailable():
        raise OSError('test read-only OS state directory')
    monkeypatch.setattr(module,'_keychain_lock_directory',unavailable)
    assert module._keychain_master(True)==(None,'')
    assert calls==[False]


def test_existing_os_master_is_reused_without_creating_or_rotating(monkeypatch):
    from offsetx_apollo_builder.browser import vault as module
    calls=[]
    monkeypatch.setattr(module,'_keychain_backend',lambda create:calls.append(create) or (b'x'*32,'test-keychain'))
    assert module._keychain_master(True)==(b'x'*32,'test-keychain')
    assert calls==[False]
