"""The full-root SQLite recovery image includes every customer CRM file."""
import hashlib
import shutil
import json
import sqlite3
import pytest
from offsetx_apollo_builder.outreach.backup import (
    create_encrypted_backup, restore_encrypted_backup, discard_restore_safety,
    validate_encrypted_backup,
)
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.outreach.workspace_registry import WorkspaceCrmRegistry


@pytest.mark.crm_sqlite_only("Exercises full-root SQLite CRM files; PostgreSQL multi-schema recovery is covered separately")
def test_full_root_restores_two_private_crm_files_with_equal_emails(tmp_path):
    data = tmp_path / 'source'
    database = data / 'outreach.db'
    with OutreachStore(database) as admin:
        admin.initialize()
    paths = {}
    template_ids = {}
    for workspace in ('alpha', 'beta'):
        relative = 'crm_workspaces/' + hashlib.sha256(workspace.encode()).hexdigest()[:32] + '/crm.db'
        paths[workspace] = relative
        engine = OutreachEngine(data / relative, workspace_id=workspace)
        try:
            campaign = engine.create_campaign(name='PRIVATE ' + workspace)
            engine.store.create_manual_campaign_contact(campaign, ContactInput(
                full_name='Anita Rao', email='same@example.com', company='Example Exports', category='CBAM'))
            engine.email_expert.memory.add_manual(content='PRIVATE '+workspace+' evidence')
            template = engine.store.list_templates()[0][0]
            template.update(subject_template='PRIVATE '+workspace+' wording', active=False)
            engine.store.upsert_template(template)
            template_ids[workspace] = template['id']
        finally:
            engine.close()
    encrypted = create_encrypted_backup(database_path=database, data_dir=data, passphrase='private-disposable-backup')
    manifest = validate_encrypted_backup(encrypted, passphrase='private-disposable-backup')
    assert manifest
    shutil.rmtree(data)
    destination = tmp_path / 'restored'
    result = restore_encrypted_backup(encrypted, database_path=destination/'outreach.db',
                                      data_dir=destination, passphrase='private-disposable-backup')
    try:
        for workspace, relative in paths.items():
            engine = OutreachEngine(destination / relative, workspace_id=workspace)
            try:
                campaigns, total = engine.store.list_campaigns()
                assert total == 1 and campaigns[0]['name'] == 'PRIVATE '+workspace
                assert engine.store.campaign_contacts(campaigns[0]['id'])[0]['email'] == 'same@example.com'
                memories, count = engine.store.search_memory_items('', workspace_id=workspace)
                assert count == 1 and memories[0]['content'] == 'PRIVATE '+workspace+' evidence'
                assert engine.store.search_memory_items('', workspace_id='beta' if workspace == 'alpha' else 'alpha')[1] == 0
                template = next(row for row in engine.store.list_templates(active_only=False)[0] if row['id'] == template_ids[workspace])
                assert template['subject_template'] == 'PRIVATE '+workspace+' wording' and template['active'] is False
            finally:
                engine.close()
    finally:
        discard_restore_safety(result)


@pytest.mark.crm_sqlite_only('Actual routed SQLite root and books; PostgreSQL recovery has a separate gate')
def test_routing_receipt_and_closed_legacy_views_survive_encrypted_restore(tmp_path):
    def open_registry(data):
        return WorkspaceCrmRegistry(root_target=str(data/'outreach.db'), data_dir=data,
                                    known_workspaces=lambda: {'alpha', 'beta'})
    data = tmp_path/'source'
    registry = open_registry(data)
    for workspace in ('alpha', 'beta'):
        with registry.lease(workspace) as engine:
            engine.create_campaign(name='Restored private '+workspace)
    registry.close()
    encrypted = create_encrypted_backup(database_path=data/'outreach.db', data_dir=data,
                                        passphrase='disposable-registry-recovery')
    assert validate_encrypted_backup(encrypted, passphrase='disposable-registry-recovery')
    shutil.rmtree(data)
    destination = tmp_path/'restored'
    result = restore_encrypted_backup(encrypted, database_path=destination/'outreach.db',
        data_dir=destination, passphrase='disposable-registry-recovery')
    restored = None
    try:
        # A pending restore must not open the normal runtime. Validate the
        # disposable candidate's authenticated snapshot/rows before accepting
        # it, then prove normal registry reopening after acceptance.
        with sqlite3.connect(destination/'outreach.db') as control:
            receipt = json.loads(control.execute('SELECT document FROM crm_workspace_routing').fetchone()[0])
        for workspace, binding in receipt['namespaces'].items():
            book = destination/'outreach.db.workspaces'/receipt['generation']/(binding['key']+'.db')
            with sqlite3.connect(book) as candidate:
                assert candidate.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert candidate.execute('SELECT workspace_id FROM crm_workspace_identity').fetchone()[0] == workspace
                assert candidate.execute('SELECT name FROM campaigns').fetchone()[0] == 'Restored private '+workspace
        discard_restore_safety(result)
        restored = open_registry(destination)
        for workspace in ('alpha', 'beta'):
            with restored.lease(workspace) as engine:
                rows, count = engine.store.list_campaigns()
                assert count == 1 and rows[0]['name'] == 'Restored private '+workspace
    finally:
        if restored:
            restored.close()
        discard_restore_safety(result)
