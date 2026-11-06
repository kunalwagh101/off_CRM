"""Bundled defaults must not overwrite durable customer decisions on restart."""
import json
from offsetx_apollo_builder.outreach.engine import OutreachEngine


def test_default_restart_preserves_customer_template_edits_and_disabled_state(tmp_path):
    target = tmp_path / 'crm.db'
    first = OutreachEngine(target)
    try:
        template = first.store.list_templates()[0][0]
        template.update(subject_template='PRIVATE CUSTOMER SUBJECT', body_template='Private reviewed wording', active=False)
        first.store.upsert_template(template)
        identifier = template['id']
    finally:
        first.close()
    reopened = OutreachEngine(target)
    try:
        templates, _ = reopened.store.list_templates(active_only=False)
        restored = next(row for row in templates if row['id'] == identifier)
        assert restored['subject_template'] == 'PRIVATE CUSTOMER SUBJECT'
        assert restored['body_template'] == 'Private reviewed wording'
        assert restored['active'] is False
    finally:
        reopened.close()


def test_explicit_template_file_can_intentionally_update_an_existing_template(tmp_path):
    target = tmp_path / 'crm.db'
    first = OutreachEngine(target)
    try:
        template = first.store.list_templates()[0][0]
        template.update(subject_template='Owner-chosen new wording', active=True)
    finally:
        first.close()
    selected = tmp_path / 'chosen-templates.json'
    selected.write_text(json.dumps({'templates': [template]}))
    reopened = OutreachEngine(target, template_file=selected)
    try:
        assert next(row for row in reopened.store.list_templates()[0] if row['id'] == template['id'])['subject_template'] == 'Owner-chosen new wording'
    finally:
        reopened.close()


def test_late_invalid_explicit_import_rolls_back_earlier_template_updates(tmp_path):
    import pytest
    engine = OutreachEngine(tmp_path / 'crm.db')
    try:
        template = engine.store.list_templates()[0][0]
        original = template['subject_template']
        template['subject_template'] = 'Must not survive a rejected batch'
        selected = tmp_path / 'invalid-batch.json'
        selected.write_text(json.dumps({'templates': [template, {'id': 'invalid-late-entry'}]}))
        with pytest.raises(ValueError, match='missing'):
            engine.email_expert.seed_templates(selected)
        assert next(row for row in engine.store.list_templates()[0] if row['id'] == template['id'])['subject_template'] == original
    finally:
        engine.close()


def test_actual_http_template_import_is_atomic_for_late_invalid_input(tmp_path):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings
    token = 'template-owner-'+'t'*40
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path/'crm.db',
        data_dir=tmp_path/'data', export_dir=tmp_path/'exports', frontend_dist=tmp_path/'missing',
        api_token=token, allowed_hosts=('testserver',)))
    with TestClient(app, headers={'X-Offsetx-Token': token}) as client:
        template = client.get('/api/v1/templates').json()['items'][0]
        original = template['subject_template']
        template['subject_template'] = 'Must not survive a rejected HTTP batch'
        response = client.post('/api/v1/templates/import', json={'templates': [template, {'id': 'bad-last'}]})
        assert response.status_code == 422, response.text
        actual = next(row for row in client.get('/api/v1/templates').json()['items'] if row['id'] == template['id'])
        assert actual['subject_template'] == original


def test_postgres_default_seed_cannot_overwrite_a_concurrent_customer_insert(isolated_postgres_target):
    import time
    from concurrent.futures import ThreadPoolExecutor
    import psycopg
    from offsetx_apollo_builder.outreach.store import OutreachStore
    initializer = OutreachStore(isolated_postgres_target)
    writer = OutreachStore(isolated_postgres_target)
    initializer.initialize()
    writer.initialize()
    bundled = {'id': 'race-template', 'name': 'Bundled', 'stage': 'initial', 'variant_id': 'A',
               'subject_template': 'Bundled subject', 'body_template': 'Bundled wording', 'active': True}
    customer = {**bundled, 'subject_template': 'PRIVATE CUSTOMER CHOICE', 'active': False}
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with writer.transaction():
                writer.upsert_template(customer)
                future = pool.submit(initializer.import_templates, [bundled], preserve_existing=True)
                deadline = time.monotonic() + 5
                with psycopg.connect(isolated_postgres_target, autocommit=True) as admin:
                    while time.monotonic() < deadline:
                        row = admin.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',
                            [initializer.database.raw.info.backend_pid]).fetchone()
                        if row and row[0] == 'Lock':
                            break
                        time.sleep(0.02)
                    else:
                        raise AssertionError('Bootstrap did not reach the concurrent uniqueness conflict')
            future.result(timeout=5)
        actual = initializer.list_templates(active_only=False)[0][0]
        assert actual['subject_template'] == 'PRIVATE CUSTOMER CHOICE' and actual['active'] is False
    finally:
        writer.close()
        initializer.close()
