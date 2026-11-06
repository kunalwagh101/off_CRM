"""Actual signed requests cannot read, approve or plant another workspace's memory."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def test_memory_reads_writes_stats_approval_and_feedback_are_workspace_owned(tmp_path):
    token = 'memory-owner-' + 'm' * 40
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path / 'crm.db',
        data_dir=tmp_path / 'data', export_dir=tmp_path / 'exports', frontend_dist=tmp_path / 'missing',
        api_token=token, allowed_hosts=('testserver',)))
    with TestClient(app) as client:
        owner = {'X-Offsetx-Token': token}
        assert client.get('/api/v1/memory').status_code == 401
        saved = client.post('/api/v1/memory', headers=owner, json={'content': 'OWNER PRIVATE EVIDENCE'}).json()
        for workspace in ('alpha', 'beta'):
            assert client.post('/api/v1/workspaces', headers=owner, json={'username': workspace,
                'workspace_id': workspace, 'password': workspace+'-password-123'}).status_code == 201
        assert client.post('/api/v1/auth/login', json={'username': 'beta', 'password': 'beta-password-123'}).status_code == 200
        assert client.get('/api/v1/memory').json()['items'] == []
        stats = client.get('/api/v1/memory/stats').json()
        assert stats['total'] == 0 and stats['workspace_id'] == 'beta'
        assert stats['backend'] == ('postgres' if app.state.engine.store.backend == 'postgres' else 'sqlite_local')
        assert client.patch('/api/v1/memory/'+saved['id'], json={'approved': False}).status_code == 404
        assert client.post('/api/v1/memory', json={'content': 'Injected owner fact', 'workspace_id': 'local'}).status_code == 422
        beta = client.post('/api/v1/memory', json={'content': 'BETA PRIVATE EVIDENCE'}).json()
        assert beta['workspace_id'] == 'beta'
        assert [row['id'] for row in client.get('/api/v1/memory').json()['items']] == [beta['id']]
        campaign = client.post('/api/v1/campaigns', json={'name': 'Beta feedback'}).json()['id']
        imported = client.post(f'/api/v1/campaigns/{campaign}/contacts/import', files={'file': (
            'contacts.csv', b'Full Name,Email,Company,Category\nAnita Rao,anita@example.com,Example Exports,CBAM\n', 'text/csv')})
        assert imported.status_code == 200
        contact = client.get(f'/api/v1/campaigns/{campaign}/contacts').json()['items'][0]
        assert client.patch(f'/api/v1/campaigns/{campaign}/contacts/'+contact['id'], json={
            'outcome_label': 'positive', 'notes': 'BETA PRIVATE FEEDBACK'}).status_code == 200
        generated = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate', json={'stages': ['initial']})
        assert generated.json()['generated'] == 1
        draft = client.get(f'/api/v1/campaigns/{campaign}/drafts').json()['items'][0]
        assert client.patch(f'/api/v1/campaigns/{campaign}/drafts/'+draft['id'], json={
            'subject': draft['subject'], 'body': draft['body']+'\nBETA PRIVATE EDIT'}).status_code == 200
        assert client.post(f'/api/v1/campaigns/{campaign}/drafts/bulk-replace', json={
            'draft_ids': [draft['id']], 'find': 'BETA PRIVATE EDIT', 'replace': 'BETA PRIVATE CORRECTION',
            'preview_only': False}).status_code == 200
        inbox = tmp_path / 'data' / 'mail' / 'inbox'
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / 'reply.json').write_text(json.dumps({'id': 'beta-reply-1', 'from': 'anita@example.com',
            'subject': 'Re: evidence', 'body': 'PRIVATE RECEIVED EMAIL MUST NOT BECOME MEMORY'}))
        reply = client.post(f'/api/v1/campaigns/{campaign}/replies/sync', json={'mode': 'local'})
        assert reply.status_code == 200 and reply.json()['matched'] == 1, reply.text
        rows = client.get('/api/v1/memory').json()['items']
        assert rows and all(row['workspace_id'] == 'beta' for row in rows)
        assert any(row['kind'] == 'labelled_outcome' for row in rows)
        assert any(row['kind'] == 'human_correction' for row in rows)
        assert any(row['kind'] == 'reply_observation' for row in rows)
        assert 'PRIVATE RECEIVED EMAIL' not in str(rows)
        client.cookies.clear()
        assert client.post('/api/v1/auth/login', json={'username': 'alpha', 'password': 'alpha-password-123'}).status_code == 200
        assert client.get('/api/v1/memory?workspace_id=beta').json()['items'] == []
        assert client.patch('/api/v1/memory/'+beta['id'], json={'approved': False}).status_code == 404
        client.cookies.clear()
        own_rows = client.get('/api/v1/memory', headers=owner).json()['items']
        assert [row['id'] for row in own_rows] == [saved['id']]
        assert 'BETA PRIVATE' not in str(own_rows)
