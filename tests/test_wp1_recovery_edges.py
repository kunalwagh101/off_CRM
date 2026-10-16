"""Production recovery boundaries: corrupt archives, isolation and restart."""
import io
import json
import sqlite3
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api import create_app
from offsetx_apollo_builder.outreach import OutreachStore
from offsetx_apollo_builder.outreach import backup
from test_audit_wp1 import PASSPHRASE, _settings, _sqlite


def _alter_archive(content, change):
    salt = content[len(backup.MAGIC):len(backup.MAGIC) + 16]
    cipher = Fernet(backup._key(PASSPHRASE, salt))
    with zipfile.ZipFile(io.BytesIO(cipher.decrypt(content[len(backup.MAGIC) + 16:]))) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files['manifest.json'])
    change(manifest, files)
    files['manifest.json'] = json.dumps(manifest).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return backup.MAGIC + salt + cipher.encrypt(output.getvalue())


def _backup(tmp_path):
    data = tmp_path / 'source'
    _sqlite(data / 'crm.db', 'before')
    return backup.create_encrypted_backup(database_path=data / 'crm.db', data_dir=data, passphrase=PASSPHRASE)


@pytest.mark.parametrize('path', ['../../escape.db', '/absolute.db', 'a/../escape.db', 'a\\escape.db'])
def test_manifest_destination_traversal_is_rejected(tmp_path, path):
    content = _alter_archive(_backup(tmp_path), lambda m, f: m.update(database_relative_to_data=path))
    with pytest.raises(ValueError):
        backup.validate_encrypted_backup(content, passphrase=PASSPHRASE)


def test_empty_durable_files_are_restorable(tmp_path):
    data = tmp_path / 'source'
    _sqlite(data / 'crm.db', 'before')
    (data / 'empty.txt').touch()
    content = backup.create_encrypted_backup(database_path=data / 'crm.db', data_dir=data, passphrase=PASSPHRASE)
    backup.validate_encrypted_backup(content, passphrase=PASSPHRASE)
    target = tmp_path / 'target'
    result = backup.restore_encrypted_backup(content, database_path=target / 'different-name.db', data_dir=target, passphrase=PASSPHRASE)
    with sqlite3.connect(target / 'different-name.db') as connection:
        assert connection.execute('SELECT value FROM probe').fetchone()[0] == 'before'
    assert (target / 'empty.txt').read_bytes() == b''
    backup.discard_restore_safety(result)


def test_backup_refuses_symlink_outside_workspace(tmp_path):
    data = tmp_path / 'data'
    _sqlite(data / 'crm.db', 'before')
    (tmp_path / 'private.txt').write_text('outside the recovery boundary')
    (data / 'link').symlink_to(tmp_path / 'private.txt')
    with pytest.raises(ValueError, match='symbolic'):
        backup.create_encrypted_backup(database_path=data / 'crm.db', data_dir=data, passphrase=PASSPHRASE)


@pytest.mark.crm_sqlite_only(
    "tests SQLite's GuardedConnection — its commit, rollback, cursor or row[0]; the same properties on both backends are test_crm_hosted.py's concurrency tests"
)
def test_bare_cursor_write_waits_for_rollback_then_autocommits(tmp_path):
    with OutreachStore(tmp_path / 'crm.db') as store:
        store.connection.execute('CREATE TABLE probe(value TEXT)')
        entered, attempted = threading.Event(), threading.Event()
        def rollback():
            with pytest.raises(RuntimeError):
                with store.transaction() as connection:
                    connection.execute("INSERT INTO probe VALUES ('rolled-back')")
                    entered.set()
                    assert attempted.wait(3)
                    raise RuntimeError('rollback')
        def bare_write():
            assert entered.wait(3)
            attempted.set()
            cursor = store.connection.cursor()
            assert cursor.execute('SELECT * FROM probe').fetchall() == []
            cursor.execute('INSERT INTO probe VALUES (:value)', {'value': 'durable'})
        with ThreadPoolExecutor(2) as executor:
            futures = [executor.submit(rollback), executor.submit(bare_write)]
            for future in futures:
                future.result(timeout=5)
    with sqlite3.connect(tmp_path / 'crm.db') as connection:
        assert connection.execute('SELECT value FROM probe').fetchall() == [('durable',)]


def test_readiness_probes_live_auxiliary_connection(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get('/health/ready').status_code == 200
        app.state.video_store.connection.close()
        response = client.get('/health/ready')
        assert response.status_code == 503
        assert 'video' in response.text


def test_oversized_export_is_rejected_before_encrypting(tmp_path, monkeypatch):
    import os
    data = tmp_path / 'data'
    _sqlite(data / 'crm.db', 'before')
    (data / 'large.bin').write_bytes(os.urandom(2 * 1024 * 1024))
    def forbidden(*args, **kwargs):
        pytest.fail('oversized archive reached encryption')
    monkeypatch.setattr(Fernet, 'encrypt', forbidden)
    with pytest.raises(ValueError, match='limit|large'):
        backup.create_encrypted_backup(database_path=data / 'crm.db', data_dir=data, passphrase=PASSPHRASE, max_bytes=1024 * 1024)


def _export(client):
    response = client.post('/api/v1/backups/export', json={'passphrase': PASSPHRASE})
    assert response.status_code == 200, response.text
    return response.content


def _restore(client, content):
    return client.post('/api/v1/backups/restore', files={'file': ('workspace.oxbackup', content)}, data={'passphrase': PASSPHRASE})


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_failed_rebind_rolls_back_and_routes_remain_usable(tmp_path, monkeypatch):
    from offsetx_apollo_builder.api import production_runtime as runtime
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        content = _export(client)
        identifier = app.state.engine.store.create_campaign(name='Must survive rollback', daily_send_limit=10)
        real_rebind = runtime._rebind_runtime
        attempts = []
        def fail_once(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError('injected reopening failure')
            return real_rebind(*args, **kwargs)
        monkeypatch.setattr(runtime, '_rebind_runtime', fail_once)
        response = _restore(client, content)
        assert response.status_code == 422
        assert app.state.engine.store.get_campaign(identifier)['name'] == 'Must survive rollback'
        for route in ('/health/ready', '/api/v1/sales/dashboard', '/api/v1/campaigns', '/api/v1/ai/chats', '/api/v1/email-delivery/jobs'):
            assert client.get(route).status_code == 200, route
        assert not app.state.recovery_gate.maintenance


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_failed_rollback_keeps_maintenance_closed(tmp_path, monkeypatch):
    from offsetx_apollo_builder.api import production_runtime as runtime
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        content = _export(client)
        def fail(*args, **kwargs):
            raise OSError('injected service failure')
        monkeypatch.setattr(runtime, '_rebind_runtime', fail)
        assert _restore(client, content).status_code == 503
        assert client.get('/health/ready').status_code == 503
        assert client.get('/api/v1/campaigns').status_code == 503
        assert client.get('/health/live').status_code == 200
        assert app.state.recovery_gate.failed


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_restore_waits_for_full_response_and_rejects_new_requests(tmp_path):
    from starlette.responses import StreamingResponse
    app = create_app(_settings(tmp_path))
    entered, release = threading.Event(), threading.Event()
    async def stream():
        import asyncio
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        yield b'finished'
    app.add_api_route('/api/v1/long-running', lambda: StreamingResponse(stream()), methods=['GET'])
    with TestClient(app) as client, ThreadPoolExecutor(2) as executor:
        content = _export(client)
        in_flight = executor.submit(client.get, '/api/v1/long-running')
        assert entered.wait(3)
        restoration = executor.submit(_restore, client, content)
        try:
            import time
            until = time.monotonic() + 3
            while not app.state.recovery_gate.maintenance and time.monotonic() < until:
                time.sleep(0.01)
            assert app.state.recovery_gate.maintenance
            assert not restoration.done()
            assert client.get('/health/ready').status_code == 503
            assert client.get('/api/v1/campaigns').status_code == 503
            assert client.post('/api/v1/backups/export', json={'passphrase': PASSPHRASE}).status_code == 409
        finally:
            release.set()
        assert in_flight.result(timeout=5).status_code == 200
        assert restoration.result(timeout=5).status_code == 200
        assert client.get('/health/ready').status_code == 200


def test_all_thread_local_connections_close_before_state_swap(tmp_path):
    """Every store that opens a connection per thread closes all of them, not
    only the calling thread's. The tool registry did not: the companion routes
    and the readiness probe left it open on the old workspace (D-131)."""
    from offsetx_apollo_builder.ai.cache import ResponseCache
    from offsetx_apollo_builder.ai.recall import SentMailIndex
    from offsetx_apollo_builder.ai.tools import ToolRegistry
    for store in (ResponseCache(tmp_path / 'cache.db'), SentMailIndex(tmp_path / 'recall.db'),
                  ToolRegistry(tmp_path / 'ai_tools.db')):
        def read_connection():
            candidate = store.connection
            return candidate if isinstance(candidate, sqlite3.Connection) else candidate()
        with ThreadPoolExecutor(2) as executor:
            connection = executor.submit(read_connection).result()
        store.close()
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')
        read_connection().execute('SELECT 1')
        store.close()


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_full_workspace_restore_relocates_assets_and_preserves_secrets(tmp_path):
    settings = _settings(tmp_path / 'original')
    app = create_app(settings)
    with TestClient(app) as client:
        cid = app.state.engine.store.create_campaign(name='Permanent customer campaign', daily_send_limit=10)
        for name in ('ai_context', 'ai_recall', 'ai_egress_log', 'image_store', 'video_store', 'distribution_store'):
            connection = getattr(app.state, name).connection
            connection.execute('CREATE TABLE audit_state(value TEXT)')
            connection.execute("INSERT INTO audit_state VALUES ('durable')")
        asset = settings.data_dir / 'image_assets' / 'test.png'
        asset.write_bytes(b'unit-test asset; live codec evidence runs separately')
        app.state.image_store.connection.execute("INSERT INTO image_assets(id,brief_id,campaign_id,path,created_at) VALUES(?,?,?,?,?)", ('asset', 'brief', cid, str(asset), '2026-09-08'))
        app.state.provider_profiles.upsert({'id': 'restore-profile', 'name': 'Production provider', 'provider_type': 'openai', 'model': 'synthetic'}, owner='local', api_key='synthetic-offline-test-key')
        signing_key = (settings.data_dir / 'email_unsubscribe.key').read_bytes()
        content = _export(client)
    target_settings = _settings(tmp_path / 'recovered')
    target_app = create_app(target_settings)
    with TestClient(target_app) as client:
        assert _restore(client, content).status_code == 200
        restored_asset = target_app.state.image_store.get_asset('asset')
        assert restored_asset['path'] == str(target_settings.data_dir / 'image_assets/test.png')
        assert (target_settings.data_dir / 'email_unsubscribe.key').read_bytes() == signing_key
        assert (target_settings.data_dir / 'email_unsubscribe.key').stat().st_mode & 0o077 == 0
        for name in ('ai_context', 'ai_recall', 'ai_egress_log', 'image_store', 'video_store', 'distribution_store'):
            assert getattr(target_app.state, name).connection.execute('SELECT value FROM audit_state').fetchone()[0] == 'durable'
        assert client.post('/api/v1/provider-profiles/restore-profile/test', json={'live_probe': False}).json()['status'] == 'configured'
    # Another process-shaped application startup reads the same durable root.
    with TestClient(create_app(target_settings)) as client:
        assert client.get('/health/ready').status_code == 200
        assert client.get('/api/v1/campaigns').json()['items'][0]['id'] == cid
        assert (target_settings.data_dir / 'image_assets/test.png').read_bytes() == asset.read_bytes()


def test_backup_routes_require_authentication(tmp_path):
    settings = _settings(tmp_path)
    settings.api_token = 'x' * 40
    settings.allow_unauthenticated = False
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/backups/export', json={'passphrase': PASSPHRASE}).status_code == 401
        assert _restore(client, b'bad').status_code == 401


def test_oversized_multipart_body_is_refused_before_parsing_finishes(tmp_path):
    settings = _settings(tmp_path)
    settings.backup_max_bytes = 1024 * 1024
    with TestClient(create_app(settings)) as client:
        assert _restore(client, b'x' * (settings.backup_max_bytes + 100000)).status_code == 413
        assert client.get('/health/ready').status_code == 200


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_external_worker_lease_prevents_workspace_replacement(tmp_path):
    from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        content = _export(client)
        with WorkspaceLock(settings.data_dir):
            assert _restore(client, content).status_code == 409
        assert _restore(client, content).status_code == 200


def test_concurrent_api_writes_are_all_durable_after_restart(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client, ThreadPoolExecutor(8) as executor:
        responses = list(executor.map(lambda i: client.post('/api/v1/campaigns', json={'name': f'Customer {i}'}), range(40)))
        errors = [
            {"index": index, "status": response.status_code, "detail": response.json().get("detail")}
            for index, response in enumerate(responses)
            if response.status_code != 201
        ]
        assert not errors, f"Concurrent campaign writes returned errors: {errors}"
        invalid_ids = [
            {"index": index, "id": response.json().get("id"), "name": response.json().get("name")}
            for index, response in enumerate(responses)
            if not isinstance(response.json().get("id"), str) or not response.json().get("id")
        ]
        assert not invalid_ids, f"HTTP 201 campaign-create returned invalid IDs: {invalid_ids}"
        ids = {response.json()['id'] for response in responses}
        assert len(ids) == 40, "Every successful create response must have a distinct campaign ID"
    with TestClient(create_app(settings)) as client:
        saved = {row['id'] for row in client.get('/api/v1/campaigns?limit=100').json()['items']}
        assert saved == ids, f"Durable campaign mismatch; missing={ids - saved}, unexpected={saved - ids}"


@pytest.mark.parametrize('crash', ['old_moved', 'new_installed', 'committed'])
def test_interrupted_swap_recovers_on_next_start(tmp_path, crash):
    import os
    import subprocess
    import sys
    data = tmp_path / 'data'
    _sqlite(data / 'crm.db', 'backup-value')
    content = backup.create_encrypted_backup(database_path=data / 'crm.db', data_dir=data, passphrase=PASSPHRASE)
    archive = tmp_path / 'backup.oxbackup'
    archive.write_bytes(content)
    _sqlite(data / 'crm.db', 'live-value')
    script = r'''
import os, sys
from pathlib import Path
from offsetx_apollo_builder.outreach import backup
root, phase = Path(sys.argv[1]), sys.argv[2]
data = root / 'data'
replace = os.replace
def crash_replace(source, target):
    replace(source, target)
    if (phase == 'old_moved' and Path(source) == data) or (phase == 'new_installed' and Path(target) == data):
        os._exit(77)
os.replace = crash_replace
write = backup._write_journal
def crash_commit(path, journal):
    write(path, journal)
    if phase == 'committed' and journal['state'] == 'committed':
        os._exit(77)
backup._write_journal = crash_commit
result = backup.restore_encrypted_backup((root / 'backup.oxbackup').read_bytes(), database_path=data / 'crm.db', data_dir=data, passphrase='synthetic-backup-passphrase')
backup.discard_restore_safety(result)
'''
    process = subprocess.run([sys.executable, '-c', script, str(tmp_path), crash], env=dict(os.environ), capture_output=True, timeout=15)
    assert process.returncode == 77, process.stderr.decode()
    assert backup.recover_interrupted_restore(database_path=data / 'crm.db', data_dir=data)
    with sqlite3.connect(data / 'crm.db') as connection:
        assert connection.execute('SELECT value FROM probe').fetchone()[0] == ('backup-value' if crash == 'committed' else 'live-value')
    assert not backup.recover_interrupted_restore(database_path=data / 'crm.db', data_dir=data)


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_legacy_corrupt_database_is_rejected_before_maintenance(tmp_path):
    import os
    salt = os.urandom(16)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('manifest.json', '{"schema_version": 1}')
        archive.writestr('outreach.db', 'not a database')
    content = backup.MAGIC + salt + Fernet(backup._key(PASSPHRASE, salt)).encrypt(output.getvalue())
    app = create_app(_settings(tmp_path))
    with TestClient(app, raise_server_exceptions=False) as client:
        original = app.state.engine
        assert _restore(client, content).status_code == 422
        assert app.state.engine is original
        assert client.get('/health/ready').status_code == 200


def test_configured_root_owns_default_database_and_gmail_token(tmp_path, monkeypatch):
    from offsetx_apollo_builder.api.config import AppSettings
    for name in ('OFFSETX_OUTREACH_DB', 'OFFSETX_GMAIL_TOKEN'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('OFFSETX_DATA_DIR', str(tmp_path / 'durable'))
    settings = AppSettings.from_env(tmp_path)
    assert settings.database_path.parent == settings.data_dir
    assert settings.gmail_token.parent == settings.data_dir


def test_production_rejects_missing_persistent_mount(monkeypatch):
    from pathlib import Path
    from offsetx_apollo_builder.api.config import AppSettings
    settings = AppSettings(project_root=Path('/app'), database_path=Path('/var/lib/offcrm/data/crm.db'), data_dir=Path('/var/lib/offcrm/data'), export_dir=Path('/var/lib/offcrm/data/exports'), frontend_dist=Path('/app/frontend/dist'), persistent_mount=Path('/var/lib/offcrm'), production=True, api_token='synthetic-production-test-token-000000')
    settings.validate()
    monkeypatch.setattr(Path, 'is_mount', lambda self: False)
    with pytest.raises(ValueError, match='not mounted'):
        settings.prepare()


@pytest.mark.parametrize('operation', ['raw-commit', 'raw-rollback', 'cursor-insert'])
@pytest.mark.crm_sqlite_only(
    "tests SQLite's GuardedConnection — its commit, rollback, cursor or row[0]; the same properties on both backends are test_crm_hosted.py's concurrency tests"
)
def test_other_thread_cannot_finish_the_owned_transaction(tmp_path, operation):
    with OutreachStore(tmp_path / 'crm.db') as store:
        store.connection.execute('CREATE TABLE probe(value TEXT)')
        entered, attempted = threading.Event(), threading.Event()
        def owner():
            with store.transaction() as connection:
                connection.execute("INSERT INTO probe VALUES ('owned')")
                entered.set()
                assert attempted.wait(3)
        def other():
            assert entered.wait(3)
            attempted.set()
            if operation == 'raw-commit':
                store.connection.commit()
            elif operation == 'raw-rollback':
                store.connection.rollback()
            else:
                store.connection.cursor().execute("INSERT INTO probe VALUES ('other')")
        with ThreadPoolExecutor(2) as executor:
            futures = [executor.submit(owner), executor.submit(other)]
            for future in futures:
                future.result(timeout=5)
        assert store.connection.execute("SELECT value FROM probe WHERE value='owned'").fetchone()[0] == 'owned'


def test_readiness_rejects_missing_or_changed_local_signing_key(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        key = settings.data_dir / 'email_unsubscribe.key'
        original = key.read_bytes()
        key.unlink()
        assert client.get('/health/ready').status_code == 503
        key.write_bytes(b'changed-signing-key-that-breaks-existing-links')
        assert client.get('/health/ready').status_code == 503
        key.write_bytes(original)
        assert client.get('/health/ready').status_code == 200


@pytest.mark.parametrize('reject_restore', [False, True])
@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_file_managed_authentication_follows_restore_and_rollback(tmp_path, monkeypatch, reject_restore):
    from offsetx_apollo_builder.api import production_runtime as runtime

    def managed(folder):
        settings = _settings(folder)
        settings.allow_unauthenticated = False
        settings.ensure_api_token()
        return settings

    source = managed(tmp_path / 'source')
    source_token = source.api_token
    with TestClient(create_app(source), headers={'Authorization': 'Bearer ' + source_token}) as client:
        content = _export(client)
    target = managed(tmp_path / 'target')
    previous_token = target.api_token
    app = create_app(target)
    with TestClient(app, headers={'Authorization': 'Bearer ' + previous_token}) as client:
        if reject_restore:
            rebind = runtime._rebind_runtime
            def fail_restored_generation(state, settings, **kwargs):
                rebind(state, settings, **kwargs)
                if settings.api_token == source_token:
                    raise RuntimeError('injected restored-service failure')
            monkeypatch.setattr(runtime, '_rebind_runtime', fail_restored_generation)
        response = _restore(client, content)
        assert response.status_code == (422 if reject_restore else 200), response.text
        accepted = previous_token if reject_restore else source_token
        refused = source_token if reject_restore else previous_token
        assert client.get('/api/v1/campaigns', headers={'Authorization': 'Bearer ' + accepted}).status_code == 200
        assert client.get('/api/v1/campaigns', headers={'Authorization': 'Bearer ' + refused}).status_code == 401
        assert target.api_token == (target.data_dir / target.TOKEN_FILENAME).read_text().strip() == accepted
        assert client.get('/health/ready').status_code == 200
        (target.data_dir / target.TOKEN_FILENAME).unlink()
        assert client.get('/health/ready').status_code == 503
        (target.data_dir / target.TOKEN_FILENAME).write_text('corrupt-credential-\u20b9' * 5)
        assert client.get('/health/ready').status_code == 503


def test_invalid_production_root_does_not_create_credentials(tmp_path, monkeypatch):
    from offsetx_apollo_builder.api.config import AppSettings
    root = tmp_path / 'refused-production-root'
    monkeypatch.setenv('OFFSETX_PRODUCTION', '1')
    monkeypatch.setenv('OFFSETX_DATA_DIR', str(root))
    with pytest.raises(ValueError, match='temporary'):
        AppSettings.from_env(tmp_path)
    assert not root.exists()


def _external_db_generations(tmp_path):
    """A CRM database outside the data directory, as a local install with its
    own OFFSETX_OUTREACH_DB has. Returns (db, data, backup of 50 rows); the live
    database then holds 400 different rows."""
    data, db = tmp_path / "data", tmp_path / "crm" / "outreach.db"
    data.mkdir()
    db.parent.mkdir()

    def seed(prefix, count, width):
        connection = sqlite3.connect(db)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE IF NOT EXISTS t(v TEXT)")
        connection.execute("DELETE FROM t")
        connection.executemany("INSERT INTO t VALUES (?)", [(prefix + "x" * width,)] * count)
        connection.commit()
        connection.close()

    seed("backup-", 50, 200)
    (data / "settings.json").write_text("{}")
    content = backup.create_encrypted_backup(database_path=db, data_dir=data, passphrase=PASSPHRASE)
    seed("live-", 400, 300)
    return db, data, content


def _write_and_die(db, prefix, count):
    """Commit rows in WAL mode and exit without closing: the rows exist only in
    the WAL beside the database, as they do after a crash or an OOM kill."""
    import subprocess
    import sys

    subprocess.run([sys.executable, "-c", (
        "import os, sqlite3\n"
        f"c = sqlite3.connect({str(db)!r})\n"
        "c.execute('PRAGMA journal_mode=WAL')\n"
        f"c.executemany('INSERT INTO t VALUES (?)', [({prefix!r} + 'z' * 300,)] * {count})\n"
        "c.commit()\n"
        "os._exit(0)\n"
    )], check=True)
    assert db.with_name(db.name + "-wal").exists()


def _rows(db):
    connection = sqlite3.connect(db)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        return dict(connection.execute(
            "SELECT substr(v, 1, instr(v, '-')), count(*) FROM t GROUP BY 1"
        ).fetchall())
    finally:
        connection.close()


def test_an_external_database_rolls_back_without_the_restored_wal(tmp_path):
    """The restored database is reopened — start-up seeds templates, so it is
    always written — and the process dies before the commit. The next start
    put the original file back beside the restored generation's WAL, and
    SQLite replayed it: 'Rowid out of order', 26 of 400 rows left (D-126)."""
    db, data, content = _external_db_generations(tmp_path)
    backup.restore_encrypted_backup(content, database_path=db, data_dir=data, passphrase=PASSPHRASE)
    _write_and_die(db, "restored-", 300)

    assert backup.recover_interrupted_restore(database_path=db, data_dir=data)
    assert _rows(db) == {"live-": 400}


def test_an_external_databases_own_wal_moves_with_it_and_comes_back(tmp_path):
    """The other direction. Rows the live database holds only in its WAL must
    not be replayed over the restored file, and must come back with the
    original on rollback — they are committed data (D-126)."""
    db, data, content = _external_db_generations(tmp_path)
    _write_and_die(db, "late-", 100)

    backup.restore_encrypted_backup(content, database_path=db, data_dir=data, passphrase=PASSPHRASE)
    assert _rows(db) == {"backup-": 50}

    assert backup.recover_interrupted_restore(database_path=db, data_dir=data)
    assert _rows(db) == {"live-": 400, "late-": 100}


def test_maintenance_drains_without_python_311(monkeypatch):
    """`asyncio.timeout` is Python 3.11+. The package supports 3.10, where it
    made every backup and restore answer 500 (D-128)."""
    import asyncio

    from offsetx_apollo_builder.api.production_runtime import RecoveryGate

    monkeypatch.delattr(asyncio, "timeout", raising=False)
    gate = RecoveryGate()
    gate.DRAIN_SECONDS = 0.05

    async def scenario():
        assert await gate.enter_request()
        with pytest.raises((TimeoutError, asyncio.TimeoutError)):
            await gate.begin_maintenance()
        # A drain that timed out lets traffic back in, and still counts it.
        assert not gate.maintenance
        assert await gate.enter_request()
        await gate.leave_request()
        await gate.leave_request()
        await gate.begin_maintenance()
        assert gate.maintenance

    asyncio.run(scenario())


def _timers(tmp_path):
    from offsetx_apollo_builder.agent.routines import RoutineService, RoutineStore
    from offsetx_apollo_builder.distribution.automation import ContentAutomationService
    from offsetx_apollo_builder.outreach.automation import AutomationService

    def nothing(*args, **kwargs):
        return None

    return [
        AutomationService(tmp_path / "automation.json", engine_factory=nothing,
                          mail_provider_factory=nothing, own_email_factory=lambda: ""),
        ContentAutomationService(tmp_path / "content.json", trends_factory=nothing,
                                 pipeline_factory=nothing, distribution_factory=nothing),
        RoutineService(RoutineStore(tmp_path / "routines.db"), runner=nothing),
    ]


def test_a_timer_started_again_while_stopping_keeps_running(tmp_path):
    """A backup that cannot wait for a long scheduled run gives up and starts
    the timers again. `start` returned early while the old loop was still
    finishing, and that loop then ended: the scheduled jobs stopped, silently,
    until the next restart (D-133)."""
    import asyncio

    async def scenario():
        for timer in _timers(tmp_path):
            await timer.start()
            loop = timer._task
            stopping = asyncio.ensure_future(timer.stop())
            await asyncio.sleep(0)
            await timer.start()
            await asyncio.sleep(0.05)
            assert not loop.done(), type(timer).__name__
            await timer.stop()
            await stopping
            assert loop.done()

    asyncio.run(scenario())


@pytest.mark.crm_sqlite_only(
    "a local backup or restore archives the CRM's SQLite file; on PostgreSQL it is refused (test_crm_hosted.py::test_local_backup_is_refused_while_the_crm_is_on_postgres), and hosted backups are S-06.03.04"
)
def test_a_long_scheduled_run_refuses_the_backup_instead_of_holding_requests(tmp_path, monkeypatch):
    """Maintenance closed the request gate, then waited — with no bound — for
    the scheduled jobs: a routine waiting half an hour for a browser lease held
    every request at 503. The jobs are stopped first now, within a bound, while
    requests still flow; one that will not stop refuses the backup (D-133)."""
    import asyncio

    import offsetx_apollo_builder.api.production_runtime as runtime

    monkeypatch.setattr(runtime, "TIMER_STOP_SECONDS", 0.2, raising=False)
    app = create_app(_settings(tmp_path))
    seen = []

    class LongRun:
        async def start(self):
            seen.append("start")

        async def stop(self):
            seen.append(("stop", app.state.recovery_gate.maintenance))
            if len(seen) == 1:
                await asyncio.sleep(3)

    with TestClient(app) as client:
        app.state.agent_routines = LongRun()
        response = client.post("/api/v1/backups/export", json={"passphrase": PASSPHRASE})
        assert response.status_code == 409, response.headers.get("content-type")
        assert "scheduled" in response.json()["detail"]
        assert seen[0] == ("stop", False)
        assert "start" in seen
        assert client.get("/health/ready").status_code == 200
