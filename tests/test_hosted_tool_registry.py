"""Tool pins and run receipts follow the actual hosted storage target."""
import pytest
import sqlite3
import json
import os
import time
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from offsetx_apollo_builder.ai.tools import ToolRegistry, ToolError, ToolRun
from offsetx_apollo_builder.db import open_database
from offsetx_apollo_builder.db.hosted import HostedStorage
from offsetx_apollo_builder.db.content_import import import_content, ContentImportError
from offsetx_apollo_builder.db.companion_import import import_companions, CompanionImportError
from offsetx_apollo_builder.agent.companions import CompanionRegistry
from offsetx_apollo_builder.ai import tool_cli
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from test_postgres_namespaces import pooler_target  # noqa: F401 - real transaction-pooler fixture


def register(registry, workspace='alpha'):
    return registry.register(name='private-tests', repository_url='https://github.com/kunalwagh101/off_CRM',
        commit_sha='a'*40, image='python:3.12-slim', command=['pytest', '-q'], workspace_id=workspace)


@pytest.fixture(params=['sqlite', 'postgres', 'transaction_pooler'])
def tool_target(request, tmp_path):
    if request.param == 'transaction_pooler':
        return request.getfixturevalue('pooler_target')
    return str(tmp_path/'hosted.db') if request.param == 'sqlite' else request.getfixturevalue('isolated_postgres_target')


def test_hosted_pins_disabled_state_and_receipts_survive_reopen(tool_target, tmp_path):
    local = tmp_path/'local'/'ai_tools.db'
    registry = ToolRegistry(local, database_target=tool_target)
    try:
        alpha = register(registry)
        beta = register(registry, 'beta')
        registry.set_enabled(alpha.id, False, workspace_id='alpha')
        run = ToolRun(id='receipt', tool_id=alpha.id, tool_name=alpha.name,
            argv=['pytest', '-q'], exit_code=0, stdout='private result', stderr='',
            duration_ms=4, status='ran')
        registry._record_run(run, alpha, workspace_id='alpha')
    finally:
        registry.close()
    assert not local.exists()
    reopened = ToolRegistry(local, database_target=tool_target)
    try:
        assert reopened.get(alpha.id, workspace_id='alpha').enabled is False
        assert reopened.get(alpha.id, workspace_id='beta') is None
        assert reopened.get(beta.id, workspace_id='beta').enabled is True
        assert reopened.runs(workspace_id='alpha')[0]['id'] == 'receipt'
        assert reopened.runs(workspace_id='beta') == []
    finally:
        reopened.close()


def test_hosted_cached_connection_uses_a_real_rollback_boundary(tool_target, tmp_path):
    registry = ToolRegistry(tmp_path/'local'/'ai_tools.db', database_target=tool_target)
    try:
        tool = register(registry)
        with pytest.raises(RuntimeError, match='late failure'):
            with registry.connection() as conn:
                conn.execute('DELETE FROM ai_tools WHERE id=?', [tool.id])
                raise RuntimeError('late failure')
        assert registry.get(tool.id, workspace_id='alpha') is not None
        # Readiness uses a direct read on the cached connection; a later
        # context must still open and finish its own transaction.
        assert registry.connection().execute('SELECT 1 AS ok').fetchone()['ok'] == 1
        assert registry.list(workspace_id='alpha')[0].id == tool.id
    finally:
        registry.close()


def test_legacy_tool_pins_refuse_silent_hosted_cutover(tool_target, tmp_path):
    local = tmp_path/'local'/'ai_tools.db'
    old = ToolRegistry(local)
    try:
        tool = register(old)
        with pytest.raises(ToolError, match='import-content'):
            ToolRegistry(local, database_target=tool_target)
        assert old.get(tool.id, workspace_id='alpha') is not None
        with open_database(tool_target) as hosted:
            assert not hosted.columns('ai_tools')
    finally:
        old.close()


class EmptyMemory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


def test_archive_first_tool_then_profile_grant_cutover_is_complete(tool_target, tmp_path):
    source = tmp_path/'old'/'ai_tools.db'
    tools = ToolRegistry(source)
    profiles = CompanionRegistry(source.parent, tools=tools, memory_backend=EmptyMemory())
    tool = register(tools)
    tools._record_run(ToolRun(id='legacy-receipt', tool_id=tool.id, tool_name=tool.name,
        argv=['pytest', '-q'], exit_code=0, stdout='public historical fixture', stderr='',
        duration_ms=2**35), tool, workspace_id='alpha')
    profile = profiles.create(workspace_id='alpha', name='Private reviewer', instructions='Review only.',
                               granted_tool_ids=[tool.id])
    profiles.close()
    tools.close()
    hosted = HostedStorage(tool_target, Fernet.generate_key().decode())
    archive = tmp_path/'private'/'tool-archive.db'
    try:
        with pytest.raises(ContentImportError, match='reactivate-tools'):
            import_content(source, hosted, archive, kind='tools')
        assert not archive.exists()
        counts = import_content(source, hosted, archive, kind='tools', reactivate_tools=True)
        assert counts == {'ai_tools': 1, 'ai_tool_runs': 1}
        with sqlite3.connect(archive) as original:
            assert original.execute('SELECT id FROM ai_tools').fetchone()[0] == tool.id
            assert json.loads(original.execute('SELECT granted_tool_ids FROM agent_companions').fetchone()[0]) == [tool.id]
        profile_archive = tmp_path/'private'/'profile-archive.db'
        with pytest.raises(CompanionImportError, match='tool grants'):
            import_companions(source, hosted, profile_archive)
        imported = import_companions(source, hosted, profile_archive, accept_tool_grants=True)
        assert imported['agent_companions'] == 1
        remote_tools = ToolRegistry(source, database_target=tool_target)
        try:
            remote = CompanionRegistry(source.parent, tools=remote_tools, memory_backend=EmptyMemory(), hosted_storage=hosted)
            assert remote.require(profile.id, workspace_id='alpha').granted_tool_ids == (tool.id,)
            assert remote_tools.get(tool.id, workspace_id='alpha') is not None
            assert remote_tools.get(tool.id, workspace_id='beta') is None
            assert remote_tools.runs(workspace_id='alpha')[0]['duration_ms'] == 2**35
            remote.close()
        finally:
            remote_tools.close()
        # Exercise the documented inverse on a disposable copy. The retained
        # original archive itself is never opened for writes or downgraded.
        inverse = tmp_path/'inverse'
        inverse.mkdir(mode=0o700)
        shutil.copy2(archive, inverse/'ai_tools.db')
        old_tools = ToolRegistry(inverse/'ai_tools.db')
        old_profiles = CompanionRegistry(inverse, tools=old_tools, memory_backend=EmptyMemory())
        try:
            assert old_tools.get(tool.id, workspace_id='alpha').enabled is True
            assert old_tools.runs(workspace_id='alpha')[0]['duration_ms'] == 2**35
            assert old_profiles.require(profile.id, workspace_id='alpha').granted_tool_ids == (tool.id,)
        finally:
            old_profiles.close()
            old_tools.close()
    finally:
        hosted.close()


def test_corrupt_executable_recipe_is_refused_before_import(tool_target, tmp_path):
    source = tmp_path/'old'/'ai_tools.db'
    tools = ToolRegistry(source)
    tool = register(tools)
    tools.set_enabled(tool.id, False, workspace_id='alpha')
    tools.close()
    with sqlite3.connect(source) as corrupt:
        corrupt.execute("UPDATE ai_tools SET repository_url='file:///private/source'")
    hosted = HostedStorage(tool_target, Fernet.generate_key().decode())
    archive = tmp_path/'private'/'corrupt.db'
    try:
        with pytest.raises(ContentImportError, match='recipe'):
            import_content(source, hosted, archive, kind='tools')
        assert not archive.exists()
        assert not hosted.connection.columns('ai_tools')
    finally:
        hosted.close()


def test_real_cli_and_app_share_hosted_pins_and_revocation(tool_target, tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('OFFSETX_DATABASE_URL', tool_target)
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', key)
    data = tmp_path/'runtime'
    cli = ['--data-dir', str(data)]
    assert tool_cli.main(cli+['register', '--name', 'owner-tests', '--repo',
        'https://github.com/kunalwagh101/off_CRM', '--commit', 'a'*40,
        '--image', 'python:3.12-slim', '--', 'pytest', '-q']) == 0
    assert not (data/'ai_tools.db').exists()
    token = 'hosted-tool-owner-'+'x'*40
    settings = AppSettings(project_root=Path.cwd(), database_path=data/'crm.db', data_dir=data,
        export_dir=data/'exports', frontend_dist=tmp_path/'missing', secrets_key=key,
        api_token=token, allowed_hosts=('testserver',))
    with TestClient(create_app(settings)) as app:
        headers = {'X-Offsetx-Token': token}
        response = app.get('/api/v1/companion-tools', headers=headers)
        assert response.status_code == 200, response.text
        assert [row['name'] for row in response.json()['items']] == ['owner-tests']
        tool_id = response.json()['items'][0]['id']
        profile = app.post('/api/v1/companions', headers=headers,
            json={'name':'Durable reviewer', 'instructions':'Review public facts.', 'granted_tool_ids':[tool_id]})
        assert profile.status_code == 201, profile.text
        profile_id = profile.json()['id']
        assert tool_cli.main(cli+['disable', 'owner-tests']) == 0
        assert app.get('/api/v1/companion-tools', headers=headers).json()['items'] == []
        assert tool_cli.main(cli+['enable', 'owner-tests']) == 0
        assert app.get('/api/v1/companion-tools', headers=headers).json()['items'][0]['name'] == 'owner-tests'
    shutil.rmtree(data)
    with TestClient(create_app(settings)) as restarted:
        profile = restarted.get('/api/v1/companions/'+profile_id, headers=headers)
        assert profile.status_code == 200, profile.text
        assert profile.json()['granted_tool_ids'] == [tool_id]
        assert restarted.get('/api/v1/companion-tools', headers=headers).json()['items'][0]['id'] == tool_id


@pytest.mark.parametrize('denial', ['foreign_install', 'wrong_master_key'])
def test_foreign_install_cli_cannot_modify_hosted_tools(tool_target, tmp_path, monkeypatch, denial, capsys):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('OFFSETX_DATABASE_URL', tool_target)
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', key)
    cli = ['--data-dir', str(tmp_path/'runtime')]
    assert tool_cli.main(cli+['list']) == 0
    wrong_key = Fernet.generate_key().decode()
    if denial == 'foreign_install':
        monkeypatch.setenv('OFFSETX_INSTALL_ID', str(uuid.uuid4()))
    else:
        monkeypatch.setenv('OFFSETX_SECRETS_KEY', wrong_key)
    assert tool_cli.main(cli+['list']) == 2
    assert not (tmp_path/'runtime'/'ai_tools.db').exists()
    output = capsys.readouterr()
    assert key not in output.out+output.err and wrong_key not in output.out+output.err


def test_two_registry_writers_serialize_duplicate_registration_and_close_all_cached_transports(tool_target, tmp_path):
    registries = [ToolRegistry(tmp_path/f'local-{i}'/'ai_tools.db', database_target=tool_target) for i in range(2)]
    try:
        def attempt(registry):
            try:
                return register(registry).id
            except ToolError:
                return 'duplicate'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, registries))
        assert outcomes.count('duplicate') == 1
        assert len(registries[0].list(workspace_id='alpha')) == 1
        # These include transports created by worker threads. A runtime close
        # must close all of them, then the existing generation protocol may
        # reopen the same durable target on the next registry operation.
        transports = [connection for registry in registries for connection in registry._connections]
        for registry in registries:
            registry.close()
        for connection in transports:
            with pytest.raises(Exception, match='closed'):
                connection.execute('SELECT 1')
        assert len(registries[0].list(workspace_id='alpha')) == 1
    finally:
        for registry in registries:
            registry.close()


def test_explicit_profile_migration_never_accepts_foreign_tool_grants(tool_target, tmp_path):
    source = tmp_path/'old'/'ai_tools.db'
    local_tools = ToolRegistry(source)
    local_profiles = CompanionRegistry(source.parent, tools=local_tools, memory_backend=EmptyMemory())
    alpha = register(local_tools)
    profile = local_profiles.create(workspace_id='alpha', name='Private reviewer', instructions='Private.',
        granted_tool_ids=[alpha.id])
    local_profiles.close()
    local_tools.close()
    remote_tools = ToolRegistry(tmp_path/'remote'/'ai_tools.db', database_target=tool_target)
    beta = register(remote_tools, 'beta')
    with remote_tools.connection() as database:
        database.execute('UPDATE ai_tools SET id=? WHERE id=?', [alpha.id, beta.id])
    hosted = HostedStorage(tool_target, Fernet.generate_key().decode())
    try:
        with pytest.raises(CompanionImportError, match='foreign tool grants'):
            import_companions(source, hosted, tmp_path/'private'/'denied.db', accept_tool_grants=True)
        with sqlite3.connect(source) as original:
            assert original.execute('SELECT id FROM agent_companions').fetchone()[0] == profile.id
            assert original.execute('SELECT count(*) FROM ai_tools').fetchone()[0] == 1
        assert not hosted.connection.columns('agent_companions')
    finally:
        hosted.close()
        remote_tools.close()


def test_companions_can_use_the_hosted_registry_transaction_without_a_separate_document_store(tool_target, tmp_path):
    tools = ToolRegistry(tmp_path/'local'/'ai_tools.db', database_target=tool_target)
    profiles = None
    try:
        tool = register(tools)
        profiles = CompanionRegistry(tmp_path/'local', tools=tools, memory_backend=EmptyMemory())
        profile = profiles.create(workspace_id='alpha', name='SQL reviewer', instructions='Review facts.',
            granted_tool_ids=[tool.id])
        skill = profiles.create_skill(workspace_id='alpha', name='Check', content='Check evidence.')
        assert profiles.require(profile.id, workspace_id='alpha').granted_tool_ids == (tool.id,)
        assert profiles.get(profile.id, workspace_id='beta') is None
        assert profiles.list_skills(workspace_id='alpha')[0].id == skill.id
        assert not (tmp_path/'local'/'ai_tools.db').exists()
    finally:
        if profiles:
            profiles.close()
        tools.close()


@pytest.mark.parametrize('alias', ['same_path', 'hardlink'])
def test_hosted_tool_target_cannot_alias_its_legacy_source(tmp_path, alias):
    source = tmp_path/'source.db'
    ToolRegistry(source).close()
    target = source if alias == 'same_path' else tmp_path/'hardlink.db'
    if alias == 'hardlink':
        os.link(source, target)
    with pytest.raises(ToolError, match='different'):
        ToolRegistry(source, database_target=str(target))
    with sqlite3.connect(source) as original:
        assert not original.execute("SELECT 1 FROM sqlite_master WHERE name='offcrm_schema'").fetchone()


def test_hosted_tool_startup_does_not_follow_a_dangling_legacy_symlink(tmp_path):
    source = tmp_path/'source.db'
    source.symlink_to(tmp_path/'missing.db')
    target = tmp_path/'hosted.db'
    with pytest.raises(ToolError, match='symbolic link'):
        ToolRegistry(source, database_target=str(target))
    assert not target.exists()


def test_native_companion_initializers_share_the_document_store_ddl_lock(isolated_postgres_target, tmp_path, monkeypatch):
    target = isolated_postgres_target
    registries = [ToolRegistry(tmp_path/f'local-{i}'/'ai_tools.db', database_target=target) for i in range(2)]
    pids = []
    for registry in registries:
        original = registry.connection
        def connected(original=original):
            connection = original()
            pid = connection.database.raw.info.backend_pid
            if pid not in pids:
                pids.append(pid)
            return connection
        monkeypatch.setattr(registry, 'connection', connected)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with open_database(target) as blocker:
                with blocker.transaction():
                    blocker.execute('SELECT pg_advisory_xact_lock(?)', [7_103_206_302])
                    futures = [pool.submit(CompanionRegistry, tmp_path/f'local-{i}', tools=registry,
                        memory_backend=EmptyMemory()) for i, registry in enumerate(registries)]
                    deadline = time.monotonic()+2
                    waiting = 0
                    while time.monotonic() < deadline:
                        if len(pids) == 2:
                            waiting = blocker.execute(
                                "SELECT count(*) AS n FROM pg_locks WHERE locktype='advisory' "
                                'AND NOT granted AND classid::bigint=? AND objid::bigint=? AND pid IN (?,?)',
                                [7_103_206_302 >> 32, 7_103_206_302 & 0xffffffff, *pids]).fetchone()['n']
                            if waiting == 2:
                                break
                        time.sleep(.02)
                    assert waiting == 2, 'both constructor styles must serialize on the shared DDL lock'
                    assert not any(future.done() for future in futures)
            for future in futures:
                future.result(timeout=5).close()
    finally:
        for registry in registries:
            registry.close()


@pytest.mark.parametrize('value', ['mysql://owner:PRIVATE_URL_CANARY@invalid/db',
    Path('postgresql://owner:PRIVATE_URL_CANARY@invalid/db')])
def test_unsupported_or_folded_tool_database_url_never_becomes_a_local_file(tmp_path, monkeypatch, value):
    monkeypatch.chdir(tmp_path)
    opened = None
    try:
        with pytest.raises(ToolError) as failure:
            opened = ToolRegistry(value)
        assert 'PRIVATE_URL_CANARY' not in str(failure.value)
        assert not list(tmp_path.iterdir())
    finally:
        if opened:
            opened.close()


def test_cli_rejects_unsupported_database_url_before_claim_or_filename_creation(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OFFSETX_DATABASE_URL', 'mysql://owner:PRIVATE_URL_CANARY@invalid/db')
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', Fernet.generate_key().decode())
    assert tool_cli.main(['--data-dir', str(tmp_path/'data'), 'list']) == 2
    assert not (tmp_path/'mysql:').exists()
    output = capsys.readouterr()
    assert 'PRIVATE_URL_CANARY' not in output.out+output.err
