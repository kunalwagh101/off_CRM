"""Real PostgreSQL ownership, transaction and scheduler durability contracts."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from offsetx_apollo_builder.agent.routines import RoutineStore, RoutineError
from offsetx_apollo_builder.meetings.store import MeetingStore, MeetingError


def test_routine_hosted_restart_precise_schedule_and_atomic_claim(isolated_postgres_target):
    store = RoutineStore(isolated_postgres_target)
    now = 1793977200.123456
    routine = store.create(workspace_id='alpha', name='Evidence check', goal='Read public evidence',
        target_url='https://example.com', trigger_type='interval', interval_seconds=60, now=now)
    from offsetx_apollo_builder.db import open_database
    with open_database(isolated_postgres_target) as actual:
        assert actual.columns("agent_routines"), "Rows must live in actual PostgreSQL"
    reopened = RoutineStore(isolated_postgres_target)
    assert reopened.require(routine.id, workspace_id='alpha').next_due_at == now + 60
    with pytest.raises(RoutineError):
        reopened.require(routine.id, workspace_id='beta')
    with pytest.raises(RoutineError, match='already exists'):
        reopened.create(workspace_id='alpha', name='Evidence check', goal='Read public evidence',
            target_url='https://example.com', trigger_type='interval', interval_seconds=60, now=now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: RoutineStore(isolated_postgres_target).claim_due(now=now+61), range(2)))
    assert sum(len(rows) for rows in claims) == 1


def test_meeting_hosted_chunk_claims_are_atomic_and_scoped(isolated_postgres_target):
    store = MeetingStore(isolated_postgres_target)
    meeting = store.create(workspace_id='alpha', title='Evidence review')
    from offsetx_apollo_builder.db import open_database
    with open_database(isolated_postgres_target) as actual:
        assert actual.columns("meetings"), "Rows must live in actual PostgreSQL"
    reopened = MeetingStore(isolated_postgres_target)
    assert reopened.require(meeting['id'], workspace_id='alpha')['title'] == 'Evidence review'
    with pytest.raises(MeetingError):
        reopened.require(meeting['id'], workspace_id='beta')
    def claim(_):
        try:
            return MeetingStore(isolated_postgres_target).claim_chunk(meeting_id=meeting['id'],
                workspace_id='alpha', sequence=0, sha256='digest', audio_bytes=3_000_000_000)[0]
        except MeetingError:
            return 'refused'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == ['claimed', 'refused']


@pytest.mark.parametrize('kind', ['routines', 'meetings'])
def test_legacy_metadata_import_archives_and_preserves_exact_rows(isolated_postgres_target, tmp_path, monkeypatch, kind):
    import sqlite3
    from cryptography.fernet import Fernet
    from offsetx_apollo_builder import db_cli
    data = tmp_path / 'data'
    if kind == 'routines':
        source = data / 'agent_routines.db'
        original = RoutineStore(source).create(workspace_id='alpha', name='Evidence', goal='Read evidence',
            target_url='https://example.com', trigger_type='event', event_name='evidence.ready', enabled=False)
    else:
        source = data / 'meeting_transcripts.db'
        original = MeetingStore(source).create(workspace_id='alpha', title='Evidence')
    archive = tmp_path / 'private' / 'archive.db'
    monkeypatch.setenv('OFFSETX_DATABASE_URL', isolated_postgres_target)
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('OFFSETX_DATA_DIR', str(data))
    assert db_cli.main(['import-content', '--kind', kind, '--source', str(source), '--archive', str(archive), '--yes']) == 0
    table = 'agent_routines' if kind == 'routines' else 'meetings'
    with sqlite3.connect(source) as local, sqlite3.connect(archive) as saved:
        assert local.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
        assert saved.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 1
    if kind == 'routines':
        assert RoutineStore(isolated_postgres_target).require(original.id, workspace_id='alpha').name == 'Evidence'
    else:
        assert MeetingStore(isolated_postgres_target).require(original['id'], workspace_id='alpha')['title'] == 'Evidence'


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_store_connection_rolls_back_all_writes_on_failure(backend, tmp_path, request):
    crm_target = str(tmp_path / 'atomicity.db') if backend == 'sqlite' else request.getfixturevalue('isolated_postgres_target')
    from offsetx_apollo_builder.db.store_connection import StoreConnection
    with StoreConnection(str(crm_target)) as connection:
        connection.execute('CREATE TABLE bridge_atomicity (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
    with pytest.raises(RuntimeError, match='after first write'):
        with StoreConnection(str(crm_target)) as connection:
            connection.execute("INSERT INTO bridge_atomicity VALUES(1, 'must roll back')")
            raise RuntimeError('after first write')
    with StoreConnection(str(crm_target)) as connection:
        assert connection.execute('SELECT * FROM bridge_atomicity').fetchall() == []


def test_hosted_privacy_adapters_find_and_delete_only_subject_workspace(isolated_postgres_target):
    from offsetx_apollo_builder.privacy import AgentRoutinePrivacyAdapter, MeetingTranscriptPrivacyAdapter, SubjectIdentity
    routines = RoutineStore(isolated_postgres_target)
    meetings = MeetingStore(isolated_postgres_target)
    rows = {}
    for workspace in ('alpha', 'beta'):
        routine = routines.create(workspace_id=workspace, name='Subject evidence', goal='Review anita@example.com',
            target_url='https://example.com', trigger_type='event', event_name='evidence.ready')
        meeting = meetings.create(workspace_id=workspace, title='Evidence for anita@example.com')
        rows[workspace] = (routine.id, meeting['id'])
    subject = SubjectIdentity(workspace_id='alpha', emails=('anita@example.com',))
    for adapter in (AgentRoutinePrivacyAdapter(isolated_postgres_target), MeetingTranscriptPrivacyAdapter(isolated_postgres_target)):
        assert adapter.find(subject), 'Hosted state must appear in privacy inventory'
        assert any(adapter.delete(subject).values())
        assert adapter.find(subject) == []
    assert routines.get(rows['alpha'][0], workspace_id='alpha') is None
    with pytest.raises(MeetingError, match='not found'):
        meetings.require(rows['alpha'][1], workspace_id='alpha')
    assert routines.require(rows['beta'][0], workspace_id='beta')
    assert meetings.require(rows['beta'][1], workspace_id='beta')


def test_overdue_routine_migration_requires_explicit_reactivation(isolated_postgres_target, tmp_path, monkeypatch):
    import sqlite3
    from cryptography.fernet import Fernet
    from offsetx_apollo_builder import db_cli
    data = tmp_path / 'data'
    source = data / 'agent_routines.db'
    original = RoutineStore(source).create(workspace_id='alpha', name='Old scheduled work', goal='Read public evidence',
        target_url='https://example.com', trigger_type='interval', interval_seconds=60, now=1, enabled=True)
    monkeypatch.setenv('OFFSETX_DATABASE_URL', isolated_postgres_target)
    monkeypatch.setenv('OFFSETX_SECRETS_KEY', Fernet.generate_key().decode())
    archive = tmp_path / 'private' / 'routines.db'
    args = ['import-content', '--kind', 'routines', '--source', str(source), '--archive', str(archive), '--yes']
    assert db_cli.main(args) == 2
    with sqlite3.connect(source) as connection:
        assert connection.execute('SELECT id FROM agent_routines').fetchone()[0] == original.id
    assert not archive.exists()
    assert db_cli.main([*args, '--reactivate-routines']) == 0
    assert [row.id for row in RoutineStore(isolated_postgres_target).claim_due(now=100)] == [original.id]
