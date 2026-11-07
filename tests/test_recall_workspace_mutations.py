"""An indexed message identifier never authorizes another workspace's mutation."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from offsetx_apollo_builder.ai.recall import SentMailIndex, Redactor
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def seed(index, owner='alpha', identifier='shared-message', body='Original supplier evidence'):
    return index.index_message({'id':identifier, 'direction':'outbound', 'subject':'Supplier evidence',
        'body':body, 'campaign_contact_id':'shared-membership'}, redactor=Redactor(), workspace_id=owner)


def test_message_collision_cannot_replace_another_workspace_content_or_search_index(tmp_path):
    index = SentMailIndex(tmp_path/'recall.db')
    try:
        seed(index)
        with pytest.raises(ValueError, match='another workspace'):
            seed(index, 'beta', body='Foreign confidential replacement')
        assert index.recent(workspace_id='alpha')[0].body == 'Original supplier evidence'
        assert index.search('supplier', workspace_id='alpha')
        assert index.search('supplier', workspace_id='beta') == []
    finally:
        index.close()


def test_scoped_reply_and_deletion_preserve_foreign_rows_and_return_actual_counts(tmp_path):
    index = SentMailIndex(tmp_path/'recall.db')
    try:
        seed(index)
        seed(index, 'beta', 'beta-message')
        index.mark_replied('shared-message', workspace_id='beta')
        assert index.stats('alpha')['replied'] == 0
        index.mark_replied('shared-message', workspace_id='alpha')
        assert index.stats('alpha')['replied'] == 1
        assert index.forget_message('shared-message', workspace_id='beta') == 0
        assert index.forget_contact('shared-membership', workspace_id='beta') == 1
        assert index.search('supplier', workspace_id='alpha')
        assert index.forget_message('shared-message', workspace_id='alpha') == 1
        assert index.forget_message('shared-message', workspace_id='alpha') == 0
        assert index.search('supplier', workspace_id='alpha') == []
    finally:
        index.close()


def test_signed_forget_cannot_delete_foreign_message_or_contact(tmp_path):
    token = 'recall-owner-'+'r'*40
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path/'crm.db',
        data_dir=tmp_path/'data', export_dir=tmp_path/'exports', frontend_dist=tmp_path/'missing',
        api_token=token, allowed_hosts=('testserver',)))
    with TestClient(app) as client:
        seed(app.state.ai_recall)
        seed(app.state.ai_recall, 'beta', 'beta-message')
        owner = {'X-Offsetx-Token':token}
        assert client.post('/api/v1/workspaces', headers=owner, json={'username':'beta',
            'workspace_id':'beta', 'password':'beta-password-123'}).status_code == 201
        assert client.post('/api/v1/auth/login', json={'username':'beta', 'password':'beta-password-123'}).status_code == 200
        assert client.post('/api/v1/ai/recall/forget', json={'message_id':'shared-message'}).json() == {'removed':0}
        assert client.post('/api/v1/ai/recall/forget', json={'campaign_contact_id':'shared-membership'}).json() == {'removed':1}
        assert app.state.ai_recall.stats('alpha')['indexed'] == 1
        assert app.state.ai_recall.search('supplier', workspace_id='alpha')


def test_failed_reindex_preserves_canonical_content_and_fts_together(tmp_path):
    index = SentMailIndex(tmp_path/'recall.db')
    try:
        seed(index)
        index.connection.execute("CREATE TRIGGER fail_reindex BEFORE UPDATE ON sent_mail BEGIN SELECT RAISE(ABORT, 'test refusal'); END")
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError, match='test refusal'):
            seed(index, body='replacement')
        assert index.recent(workspace_id='alpha')[0].body == 'Original supplier evidence'
        assert index.search('supplier', workspace_id='alpha')
        assert index.search('replacement', workspace_id='alpha') == []
    finally:
        index.close()


def test_search_never_trusts_fts_workspace_without_canonical_owner(tmp_path):
    index = SentMailIndex(tmp_path/'recall.db')
    try:
        seed(index)
        index.connection.execute("UPDATE sent_mail_fts SET workspace_id='beta'")
        assert index.search('supplier', workspace_id='beta') == []
    finally:
        index.close()


def test_two_registry_writers_cannot_adopt_same_message_for_different_owners(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    indexes = [SentMailIndex(tmp_path/'recall.db') for _ in range(2)]
    fence = threading.Barrier(2)
    def write(pair):
        index, owner = pair
        fence.wait(timeout=5)
        try:
            seed(index, owner)
            return owner
        except ValueError:
            return None
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = list(pool.map(write, zip(indexes, ('alpha', 'beta'))))
        assert len([owner for owner in winners if owner]) == 1
        winner = next(owner for owner in winners if owner)
        loser = 'beta' if winner == 'alpha' else 'alpha'
        assert indexes[0].search('supplier', workspace_id=winner)
        assert indexes[0].search('supplier', workspace_id=loser) == []
    finally:
        for index in indexes:
            index.close()


def test_privacy_recall_deletion_binds_subject_workspace(tmp_path):
    from offsetx_apollo_builder.outreach.store import OutreachStore
    from offsetx_apollo_builder.outreach.models import ContactInput
    from offsetx_apollo_builder.privacy import SentMailPrivacyAdapter, SubjectIdentity
    store = OutreachStore(tmp_path/'crm.db')
    store.initialize()
    index = SentMailIndex(tmp_path/'recall.db')
    try:
        contact = store.upsert_contact(ContactInput(full_name='Fixture', email='fixture@example.com'))
        campaign = store.create_campaign(name='Privacy fixture', daily_send_limit=10)
        membership, _ = store.add_contact_to_campaign(campaign, contact)
        for owner in ('alpha', 'beta'):
            index.index_message({'id':owner, 'direction':'outbound', 'subject':'Supplier evidence',
                'body':'Evidence', 'campaign_contact_id':membership}, redactor=Redactor(), workspace_id=owner)
        adapter = SentMailPrivacyAdapter(index, store)
        subject = SubjectIdentity(workspace_id='beta', emails=('fixture@example.com',))
        assert adapter.delete(subject) == {'redacted_sent_mail':1}
        assert index.stats('alpha')['indexed'] == 1
        assert index.stats('beta')['indexed'] == 0
    finally:
        index.close()
        store.close()


def test_http_rebuild_refuses_unowned_legacy_source_before_reading_it(tmp_path, monkeypatch, capsys):
    token = 'recall-rebuild-'+'r'*40
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path/'crm.db',
        data_dir=tmp_path/'data', export_dir=tmp_path/'exports', frontend_dist=tmp_path/'missing',
        api_token=token, allowed_hosts=('testserver',)))
    with TestClient(app) as client:
        seed(app.state.ai_recall)
        def forbidden_read(*args, **kwargs):
            pytest.fail('unowned CRM must not be enumerated by a workspace rebuild')
        monkeypatch.setattr(app.state.engine.store, 'list_campaigns', forbidden_read)
        owner = {'X-Offsetx-Token':token}
        response = client.post('/api/v1/ai/recall/rebuild', headers=owner)
        assert response.status_code == 409
        assert response.json()['detail']['error'] == 'crm_ownership_required'
        detail = response.json()['detail']
        assert 'ownership migration' in detail['message']
        assert 'Reference: '+detail['error_id'] in detail['message']
        import json
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
        failures = [row for row in records if row.get('error_id') == detail['error_id']]
        assert len(failures) == 1 and failures[0]['operation'] == 'recall.rebuild'
        assert 'Original supplier evidence' not in json.dumps(records)
        assert client.post('/api/v1/workspaces', headers=owner, json={'username':'beta',
            'workspace_id':'beta', 'password':'beta-password-123'}).status_code == 201
        assert client.post('/api/v1/auth/login', json={'username':'beta', 'password':'beta-password-123'}).status_code == 200
        assert client.post('/api/v1/ai/recall/rebuild').status_code == 409
        assert app.state.ai_recall.stats('alpha')['indexed'] == 1
        assert app.state.ai_recall.stats('beta')['indexed'] == 0
