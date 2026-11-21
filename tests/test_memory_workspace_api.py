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
        # D-451: workspace-owned memory remains usable, but legacy campaign
        # writes are refused until its rows have explicit workspace ownership.
        assert client.post('/api/v1/campaigns', json={'name': 'Blocked beta feedback'}).status_code == 403
        assert client.get('/api/v1/campaigns').status_code == 403
        # A login cookie takes priority over the install token. Drop the beta
        # cookie before testing authenticated owner actions: never use an
        # owner header to impersonate local while still logged in as beta.
        client.cookies.clear()
        campaign = client.post('/api/v1/campaigns', headers=owner, json={'name': 'Owner feedback'}).json()['id']
        imported = client.post(f'/api/v1/campaigns/{campaign}/contacts/import', headers=owner, files={'file': (
            'contacts.csv', b'Full Name,Email,Company,Category\nAnita Rao,anita@example.com,Example Exports,CBAM\n', 'text/csv')})
        assert imported.status_code == 200
        contact = client.get(f'/api/v1/campaigns/{campaign}/contacts', headers=owner).json()['items'][0]
        assert client.patch(f'/api/v1/campaigns/{campaign}/contacts/'+contact['id'], headers=owner, json={
            'outcome_label': 'positive', 'notes': 'OWNER PRIVATE FEEDBACK'}).status_code == 200
        generated = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate', headers=owner, json={'stages': ['initial']})
        assert generated.json()['generated'] == 1
        draft = client.get(f'/api/v1/campaigns/{campaign}/drafts', headers=owner).json()['items'][0]
        assert client.patch(f'/api/v1/campaigns/{campaign}/drafts/'+draft['id'], headers=owner, json={
            'subject': draft['subject'], 'body': draft['body']+'\nOWNER PRIVATE EDIT'}).status_code == 200
        assert client.post(f'/api/v1/campaigns/{campaign}/drafts/bulk-replace', headers=owner, json={
            'draft_ids': [draft['id']], 'find': 'OWNER PRIVATE EDIT', 'replace': 'OWNER PRIVATE CORRECTION',
            'preview_only': False}).status_code == 200
        inbox = tmp_path / 'data' / 'mail' / 'inbox'
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / 'reply.json').write_text(json.dumps({'id': 'beta-reply-1', 'from': 'anita@example.com',
            'subject': 'Re: evidence', 'body': 'PRIVATE RECEIVED EMAIL MUST NOT BECOME MEMORY'}))
        reply = client.post(f'/api/v1/campaigns/{campaign}/replies/sync', headers=owner, json={'mode': 'local'})
        assert reply.status_code == 200 and reply.json()['matched'] == 1, reply.text
        # Owner-generated observations remain with local; beta cannot see
        # them just because an install-wide campaign exists.
        owner_observations = client.get('/api/v1/memory', headers=owner).json()['items']
        assert any(row['kind'] == 'labelled_outcome' for row in owner_observations)
        assert any(row['kind'] == 'human_correction' for row in owner_observations)
        assert any(row['kind'] == 'reply_observation' for row in owner_observations)
        assert 'PRIVATE RECEIVED EMAIL' not in str(owner_observations)
        # Return to beta to prove the owner observations were never exposed.
        assert client.post('/api/v1/auth/login', json={'username': 'beta',
            'password': 'beta-password-123'}).status_code == 200
        rows = client.get('/api/v1/memory').json()['items']
        assert [row['id'] for row in rows] == [beta['id']]
        assert all(row['workspace_id'] == 'beta' for row in rows)
        assert 'PRIVATE RECEIVED EMAIL' not in str(rows)
        client.cookies.clear()
        assert client.post('/api/v1/auth/login', json={'username': 'alpha', 'password': 'alpha-password-123'}).status_code == 200
        assert client.get('/api/v1/memory?workspace_id=beta').json()['items'] == []
        assert client.patch('/api/v1/memory/'+beta['id'], json={'approved': False}).status_code == 404
        client.cookies.clear()
        own_rows = client.get('/api/v1/memory', headers=owner).json()['items']
        assert saved['id'] in [row['id'] for row in own_rows]
        assert all(row['workspace_id'] == 'local' for row in own_rows)
        assert 'BETA PRIVATE' not in str(own_rows)



def test_new_memory_returns_its_own_receipt_after_more_than_thousand_records(tmp_path):
    """D-487: a saved fact must not return 500 because the first page is full."""
    token = "memory-owner-large-" + "m" * 40
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing", api_token=token,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        store = client.app.state.engine.store
        for index in range(1001):
            store.add_memory_item(
                workspace_id="local", kind="playbook", scope="global",
                content=f"Existing seed fact {index}",
            )
        # Use an explicitly future timestamp, not a wall-clock tie, to prove
        # that the next saved item is outside the first 1,000 returned rows.
        with store.transaction() as connection:
            connection.execute(
                "UPDATE memory_items SET updated_at = ? WHERE workspace_id = ?",
                ("2099-01-01T00:00:00+00:00", "local"),
            )
        response = client.post(
            "/api/v1/memory",
            json={"content": "Latest fact is saved with its exact ID"},
            headers={"X-Offsetx-Token": token},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["workspace_id"] == "local"
        assert body["content"] == "Latest fact is saved with its exact ID"
        assert body["id"]
        actual = store._row(
            "SELECT id FROM memory_items WHERE workspace_id = ? AND content = ?",
            ("local", "Latest fact is saved with its exact ID"),
        )
        assert actual is not None and body["id"] == actual["id"]
        assert store.get_memory_item(body["id"], workspace_id="local")["id"] == body["id"]
        assert store.get_memory_item(body["id"], workspace_id="beta") is None
        # D-488: an ordinary memory list must not silently stop at record 1,000.
        page, total = store.search_memory_items(
            "", workspace_id="local", limit=10, offset=1000,
        )
        assert total == 1002
        assert len(page) == 2
        foreign_page, foreign_total = store.search_memory_items(
            "", workspace_id="beta", limit=10, offset=1000,
        )
        assert foreign_page == [] and foreign_total == 0
        # D-488: a newer exact keyword must also be found when its timestamp
        # puts it outside the old hard-coded 1,000-candidate SQL window.
        matches, count = store.search_memory_items(
            "Latest", workspace_id="local", limit=10,
        )
        assert count == 1
        assert [item["id"] for item in matches] == [body["id"]]
        assert "_memory_rank" not in matches[0]
